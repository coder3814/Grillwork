"""A GitHub Projects board sync — the worked example of an adopter harness.

This is **harness code, not engine code**. Grillwork rings a doorbell (the hook contract's
`on-spec-created` / `on-transition` events) and this adapter reads the spec files and
projects them onto a GitHub Projects v2 board: one real Issue per spec (in ``repo``), added
to the configured project, its item's **chosen single-select field** (``status_field``)
carrying the option the harness's settings map the spec's lifecycle stage to (``status_map``),
open through drafting→accepted and closed at ``closed``. The board's columns can be named
anything: the map places the card, never a name match. The projection is one-way and
downstream — nothing here reads the board back.

Everything it needs comes from the harness's OWN settings (``settings.py`` — a settings file
beside this module, or environment), never from Grillwork's config: the engine names no
tracker.

The module's only door to GitHub is the factory :func:`board_client`. In production it returns
a real client that shells out to ``gh`` (GitHub Projects v2 is GraphQL-only, so writes go via
``gh api graphql``); it stores and handles **no** credentials — authentication is ``gh``'s,
held in the OS keyring. The tests substitute an in-memory fake at exactly this factory, so no
test performs network I/O; the client's method surface below is the fixed boundary that fake
mirrors.

Every board operation raises :class:`GitHubError` on failure. :func:`sync_spec` lets it
propagate to the hook entry script (``hook.py``), which reports it and exits nonzero — the
hook's own business, since a detached hook's failure never touches the engine.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import compose
import grillwork_cli


class GitHubError(Exception):
    """Any GitHub board failure — ``gh`` missing/unauthenticated, network/rate-limit, an
    unreachable or not-found project, or a malformed response. Raised by every board op; the
    seam downgrades it at trigger time (R-004), :func:`validate_mapping` hard-fails on it at
    config time (008 R-005)."""


# The stable correlation marker embedded in an issue body: the one anchor that ties a spec to
# its issue for idempotent find-or-create (C-003a/c). Defined once so the adapter that *writes*
# it and the real client that *searches* for it can never drift apart.
def _marker(spec_id: str) -> str:
    return f"<!-- grillwork-spec: {spec_id} -->"


# --- identity resolution (settings-time) --------------------------------------------------

_PROJECT_URL_RE = re.compile(
    r"github\.com/(?:users|orgs)/(?P<owner>[^/]+)/projects/(?P<number>\d+)"
)
# The owner/name of a github.com origin remote, https or ssh, with an optional `.git` suffix.
_REMOTE_RE = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<name>.+?)(?:\.git)?/?$")


def _parse_project_url(url: str) -> tuple[str, str]:
    """(owner, number) parsed from a Projects v2 URL (``/users/<o>/projects/<n>`` or
    ``/orgs/<o>/projects/<n>``); ("", "") when it does not match. Best-effort, never raises —
    presence validation is a separate tier (Unit C / R-008)."""
    m = _PROJECT_URL_RE.search(url)
    return (m.group("owner"), m.group("number")) if m else ("", "")


def _git_remote_identity(root) -> tuple[str, str]:
    """(owner, "<owner>/<name>") from ``root``'s git ``origin`` remote; ("", "") when there is
    no repo, no origin, or a non-github remote. Never raises — an absent default is left empty
    and validated elsewhere (R-008)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return ("", "")
    if result.returncode != 0:
        return ("", "")
    m = _REMOTE_RE.search(result.stdout.strip())
    if not m:
        return ("", "")
    owner = m.group("owner")
    return (owner, f"{owner}/{m.group('name')}")


def resolve_identity(*, owner: str, project_number: str, project_url: str, repo: str, root) -> tuple[str, str, str]:
    """Resolve ``(owner, project_number, repo)`` from the given inputs — how the harness's
    settings may leave owner/repo blank and still bind.

    Precedence: an explicit value wins; then the value parsed from ``project_url`` (owner,
    number); then, for owner and repo, the default read from ``root``'s git ``origin`` remote.
    Anything still unresolved is returned as an empty string — this does not raise on a missing
    value (the settings loader reports what is still missing)."""
    url_owner, url_number = _parse_project_url(project_url) if project_url else ("", "")
    remote_owner, remote_repo = _git_remote_identity(root)
    resolved_owner = owner or url_owner or remote_owner
    resolved_number = project_number or url_number
    resolved_repo = repo or remote_repo
    return (resolved_owner, resolved_number, resolved_repo)


# --- board enumeration + settings validation ---------------------------------------------


def single_select_fields(owner: str, project_number: str, repo: str) -> list[tuple[str, list[str]]]:
    """Every single-select field on the board with its option names, in board order — what
    ``hook.py --check`` prints so the adopter can see the field and option names to put in
    ``settings.yaml``.

    Doubles as a connectivity check: a missing/unauthenticated ``gh`` or an unreachable /
    not-found project raises :class:`GitHubError` here. Returns ``[]`` for a board carrying no
    single-select field — this harness never adds one.

    Identity-only, like :func:`validate_mapping`: it only enumerates, so no chosen field is
    named.
    """
    return board_client(
        SimpleNamespace(owner=owner, project_number=project_number, repo=repo)
    ).single_select_fields()


def validate_mapping(owner: str, project_number: str, repo: str, field: str, mapping: dict[str, str]) -> None:
    """Check that the settings' chosen single-select field and every option their map targets
    are actually on the board — so a column renamed or deleted since the settings were written
    is caught by ``hook.py --check`` rather than at the next spec change. Raises
    :class:`GitHubError` naming the missing field/option.

    Reads the board through a client of its **own**, deliberately: a client caches the board's
    metadata for its lifetime, so re-checking against a snapshot already held would check
    nothing. The identity-only target below names no chosen field — this only enumerates.
    """
    fields = dict(
        board_client(
            SimpleNamespace(owner=owner, project_number=project_number, repo=repo)
        ).single_select_fields()
    )
    if field not in fields:
        raise GitHubError(
            f"the single-select field {field!r} is not on the GitHub project. Set `status_field` "
            "in settings.yaml to one of the fields the board has."
        )
    missing = sorted({option for option in mapping.values() if option not in fields[field]})
    if missing:
        raise GitHubError(
            f"the board's {field!r} field does not have the mapped options: {', '.join(missing)}. "
            "Add them to the board, or map onto the options it has in settings.yaml."
        )


# --- reading one spec (the doorbell names it; the file is the truth) ----------------------

# The spec header rows this harness reads for its own purposes: the engine's spec files carry a
# `| **ID** | … |` header row and an `# <title>` heading, and neither is part of the acceptance
# package. The status is not read here — the engine's model already carries it.
_ID_ROW_RE = re.compile(r"^\|\s*\*\*ID\*\*\s*\|\s*(?P<value>.+?)\s*\|", re.MULTILINE)
_TITLE_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.MULTILINE)


class SpecRead(SimpleNamespace):
    """What this harness needs from one spec file: ``spec_id``, ``title``, ``status``, ``path``."""


def read_spec(spec_path, status: str) -> SpecRead:
    """Read the spec file the doorbell named, for the two things the engine's model does not
    carry — the board issue's identity and its title. The payload is only a doorbell:
    everything projected onto the board is read from the files here, so a hook that runs late
    or out of order still projects the current state (the contract's own instruction).

    ``status`` comes from the model rather than from a second parse of the header: which row
    holds it and how it is spelled are the engine's, and a harness that re-derives it is one
    header change away from being wrong.

    Raises ``OSError`` when the file is gone (a spec deleted between trigger and hook) — the
    entry script reports that and exits nonzero."""
    spec_path = Path(spec_path)
    text = spec_path.read_text(encoding="utf-8")
    id_match = _ID_ROW_RE.search(text)
    title_match = _TITLE_RE.search(text)
    return SpecRead(
        path=spec_path,
        spec_id=id_match.group("value") if id_match else "",
        title=title_match.group("title") if title_match else "",
        status=status,
    )


# --- the projection ----------------------------------------------------------------------


def _status_map(settings, statuses) -> dict[str, str]:
    """The settings' stage -> option map, confirmed to cover **every** lifecycle stage.

    Checked whole, up front, rather than per spec: an incomplete map is itself the fault, not
    just a fault for the specs that happen to sit on an unmapped stage. Looking each spec's
    stage up as it came would let a map that can place today's specs pass silently and strand
    the rest at their next transition — the complaint is owed at the first sync.

    ``statuses`` is the engine's own list (``grillwork statuses``), not a copy of it kept here:
    a lifecycle that gains a stage should fail this check on the next sync, which a hard-coded
    list would silently pass.
    """
    mapping = settings.status_map or {}
    unmapped = [status for status in statuses if not mapping.get(status)]
    if unmapped:
        raise GitHubError(
            "these settings map no board column for: "
            f"{', '.join(unmapped)}. Give every lifecycle stage a column under `status_map` in "
            "settings.yaml."
        )
    return dict(mapping)


def sync_spec(spec_path, settings) -> None:
    """Project the spec at ``spec_path`` onto the configured board — this module's entry point,
    the one ``hook.py`` calls for a spec-scoped event.

    One spec, not a scan: the doorbell names the spec, and find-or-create by the body's hidden
    correlation marker makes a repeat fire idempotent (the same spec never gains a second
    issue). Does **not** catch :class:`GitHubError` — the entry script reports it."""
    # Engine content first, before the board is touched at all: the lifecycle the map is checked
    # whole against, and the neutral model this harness renders.
    mapping = _status_map(settings, grillwork_cli.statuses(settings.root))
    model = grillwork_cli.package(settings.root, spec_path)
    spec = read_spec(spec_path, model["status"])
    if not spec.spec_id or not spec.status:
        raise GitHubError(
            f"{spec.path} carries no readable spec ID / status row, so there is nothing to place."
        )
    if spec.status not in mapping:
        raise GitHubError(f"no board column is mapped for the stage {spec.status!r}.")
    client = board_client(settings)
    # The full acceptance package, composed as a pure function of the spec directory; the hidden
    # correlation marker is appended here (kept out of the composed body) so find_issue ties the
    # issue to its spec without the reader ever seeing it.
    body = f"{compose.compose_body(model, spec.path, settings)}\n\n{_marker(spec.spec_id)}"
    title = spec.title or spec.spec_id
    issue = client.find_issue(spec.spec_id)
    if issue is None:
        issue = client.create_issue(spec.spec_id, title, body)
    else:
        client.update_issue(issue, title, body)
    item = client.add_to_project(issue)
    # The option the settings map this stage to — several stages may share one (collapse), and
    # an option no stage maps to is never named here.
    client.set_item_status(item, mapping[spec.status])
    # Keyed on the `closed` STAGE, never the column: a stage sharing `closed`'s option still
    # leaves its issue open.
    client.set_issue_state(issue, open=(spec.status != "closed"))


# --- the board-client boundary -----------------------------------------------------------


def board_client(settings):
    """The single ``gh``/board-client boundary. Production returns the real ``gh``-backed client
    built from the settings' ``owner`` / ``project_number`` / ``repo`` and the single-select
    field it writes to, ``status_field`` (duck-typed — a :class:`settings.Settings`, or the
    small identity-only target :func:`validate_mapping` builds, which names no chosen field: it
    only enumerates, so the field is simply left unbound). The tests monkeypatch this factory to
    return an in-memory fake, so every test runs network-free."""
    return _GhBoardClient(
        settings.owner,
        settings.project_number,
        settings.repo,
        getattr(settings, "status_field", ""),
    )


class _Issue:
    """Opaque issue handle the real client hands the adapter and gets back — the adapter never
    inspects it (mirrors the fake's ``FakeIssue``)."""

    def __init__(self, number: int, node_id: str) -> None:
        self.number = number
        self.node_id = node_id


class _Item:
    """Opaque project-item handle (a project item's node id)."""

    def __init__(self, item_id: str) -> None:
        self.item_id = item_id


class _SingleSelectField:
    """One single-select field on the board: its node id and its option ids by option name, in
    board order (the order the options appear in a column list)."""

    def __init__(self, field_id: str, options: dict[str, str]) -> None:
        self.field_id = field_id
        self.options = options


class _ProjectMeta:
    """The board metadata one project query yields: the project's node id and **every**
    single-select field on it, keyed by name, in board order — the person picks one of them, so
    the client can no longer hold just "Status" (008 R-001 / R-002)."""

    def __init__(self, project_id: str, fields: dict[str, _SingleSelectField]) -> None:
        self.project_id = project_id
        self.fields = fields


# One introspection query answers everything the client needs about the board: the project node
# id, and every single-select field with its id, name, and the id of each of its options by name.
# `repositoryOwner` covers a user- or org-owned project (both implement `ProjectV2Owner`). Spec
# 007 asked for `field(name: "Status")`; the field is the person's to choose, so this enumerates
# them all and the inline fragment keeps only the single-select ones (the rest match nothing and
# come back as empty nodes).
_PROJECT_QUERY = """
query($owner: String!, $number: Int!) {
  repositoryOwner(login: $owner) {
    ... on ProjectV2Owner {
      projectV2(number: $number) {
        id
        fields(first: 50) {
          nodes {
            ... on ProjectV2SingleSelectField {
              id
              name
              options { id name }
            }
          }
        }
      }
    }
  }
}
"""

_ADD_ITEM_MUTATION = """
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
"""

_SET_STATUS_MUTATION = """
mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId, itemId: $itemId, fieldId: $fieldId,
    value: {singleSelectOptionId: $optionId}
  }) {
    projectV2Item { id }
  }
}
"""


class _GhBoardClient:
    """The real board client: every op shells out through ``gh`` — ``gh api graphql`` for the
    Projects v2 board (GraphQL-only) and ``gh issue`` for issue create/edit/close. No Python
    HTTP or auth dependency and no stored credentials (R-002(b)). Any nonzero ``gh`` exit, a
    missing ``gh``, or an unparseable response becomes :class:`GitHubError` with a remedy."""

    def __init__(self, owner: str, project_number: str, repo: str, status_field: str = "") -> None:
        self.owner = owner
        self.project_number = project_number
        self.repo = repo
        # The single-select field the person chose — the one field this client writes. Unbound
        # ("") when built from an identity-only target that names none (:func:`validate_mapping`).
        self.status_field = status_field
        self._meta: _ProjectMeta | None = None  # cached per client (one client per trigger scan)

    # -- gh transport --------------------------------------------------------------------

    def _gh(self, args: list[str]) -> str:
        try:
            result = subprocess.run(["gh", *args], capture_output=True, text=True)
        except FileNotFoundError as e:
            raise GitHubError(
                "the GitHub CLI `gh` was not found. Install it and run `gh auth login`."
            ) from e
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise GitHubError(
                f"`gh {args[0]}` failed: {detail}. Check `gh auth login`, the project "
                "owner/number, or retry."
            )
        return result.stdout

    def _loads(self, out: str, what: str):
        try:
            return json.loads(out)
        except json.JSONDecodeError as e:
            raise GitHubError(f"could not parse the gh {what} response: {e}") from e

    def _graphql(self, query: str, **variables) -> dict:
        args = ["api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            # `-F` sends a typed (int) field for the project number; `-f` sends a raw string for
            # node ids/logins. GraphQL's `Int!` rejects a quoted string, so the split matters.
            flag = "-F" if isinstance(value, int) and not isinstance(value, bool) else "-f"
            args += [flag, f"{key}={value}"]
        payload = self._loads(self._gh(args), "GraphQL")
        if payload.get("errors"):
            raise GitHubError(
                f"GitHub GraphQL error: {payload['errors']}. Check the project owner/number and "
                "`gh auth status`."
            )
        return payload

    def _project_meta(self) -> _ProjectMeta:
        if self._meta is None:
            try:
                number = int(self.project_number)
            except (TypeError, ValueError) as e:
                raise GitHubError(
                    f"project_number must be a number, got {self.project_number!r}."
                ) from e
            payload = self._graphql(_PROJECT_QUERY, owner=self.owner, number=number)
            owner_node = (payload.get("data") or {}).get("repositoryOwner")
            if not owner_node:
                raise GitHubError(
                    f"GitHub owner {self.owner!r} was not found. Check the owner and `gh auth login`."
                )
            project = owner_node.get("projectV2")
            if not project:
                raise GitHubError(
                    f"GitHub project #{self.project_number} was not found for {self.owner!r}. "
                    "Check the project number."
                )
            fields: dict[str, _SingleSelectField] = {}
            for node in ((project.get("fields") or {}).get("nodes") or []):
                if not node.get("name"):  # not a single-select field: the fragment matched nothing
                    continue
                fields[node["name"]] = _SingleSelectField(
                    node["id"], {o["name"]: o["id"] for o in node.get("options", [])}
                )
            self._meta = _ProjectMeta(project["id"], fields)
        return self._meta

    # -- enumeration (config-time, 008 R-001 / R-002 / R-005) ----------------------------

    def single_select_fields(self) -> list[tuple[str, list[str]]]:
        """Every single-select field on the board with its option names, in board order — what
        the setup conversation offers the person and what the pre-write re-validation re-reads.
        ``[]`` when the board has none (setup hard-fails there; Grillwork never adds one,
        R-002). Raises :class:`GitHubError` when the project is unreachable / not found or
        ``gh`` is missing/unauthenticated (R-008)."""
        meta = self._project_meta()
        return [(name, list(field.options)) for name, field in meta.fields.items()]

    # -- projection (trigger-time) -------------------------------------------------------

    def find_issue(self, spec_id: str):
        """The one issue in ``github_repo`` whose body carries ``spec_id``'s marker, else None.
        Narrows with a repo issue search, then confirms the exact marker in the body (search is
        fuzzy; the marker is the authority)."""
        marker = _marker(spec_id)
        out = self._gh(
            [
                "issue", "list", "--repo", self.repo, "--state", "all",
                "--search", f"grillwork-spec {spec_id} in:body",
                "--json", "number,id,body", "--limit", "100",
            ]
        )
        for it in self._loads(out, "issue list"):
            if marker in (it.get("body") or ""):
                return _Issue(it["number"], it["id"])
        return None

    def create_issue(self, spec_id: str, title: str, body: str):
        """Create the issue in ``github_repo`` (its ``body`` already carries the marker) and
        return a handle carrying its node id."""
        url = self._gh(
            ["issue", "create", "--repo", self.repo, "--title", title, "--body", body]
        ).strip()
        number = url.rstrip("/").split("/")[-1]
        return self._view_issue(number)

    def _view_issue(self, number: str):
        data = self._loads(
            self._gh(["issue", "view", str(number), "--repo", self.repo, "--json", "number,id"]),
            "issue view",
        )
        return _Issue(data["number"], data["id"])

    def update_issue(self, issue, title: str, body: str) -> None:
        self._gh(
            ["issue", "edit", str(issue.number), "--repo", self.repo, "--title", title, "--body", body]
        )

    def add_to_project(self, issue):
        """Ensure the issue is an item of the configured project (``addProjectV2ItemById`` is
        idempotent — a re-add returns the existing item); return the item handle."""
        meta = self._project_meta()
        data = self._graphql(_ADD_ITEM_MUTATION, projectId=meta.project_id, contentId=issue.node_id)
        return _Item(data["data"]["addProjectV2ItemById"]["item"]["id"])

    def set_item_status(self, item, option_name: str) -> None:
        """Set the **chosen** single-select field to the named option — the option the caller
        resolved from the person's map, not a lifecycle status name (008 R-003). Raises
        :class:`GitHubError` naming what the board lacks when no field is bound, when the chosen
        field is no longer there, or when the option is not one of that field's — a column
        renamed or deleted since setup, which the seam downgrades at a trigger (R-004)."""
        meta = self._project_meta()
        if not self.status_field:
            raise GitHubError(
                "no single-select field was named for this board, so there is no field to set an "
                "option on."
            )
        field = meta.fields.get(self.status_field)
        if field is None:
            raise GitHubError(f"the single-select field {self.status_field!r} is not on the board.")
        option_id = field.options.get(option_name)
        if option_id is None:
            raise GitHubError(
                f"option {option_name!r} is not on the board's {self.status_field!r} field."
            )
        self._graphql(
            _SET_STATUS_MUTATION,
            projectId=meta.project_id,
            itemId=item.item_id,
            fieldId=field.field_id,
            optionId=option_id,
        )

    def set_issue_state(self, issue, *, open: bool) -> None:  # noqa: A002 — GitHub's field name
        """Close (``open=False``) or reopen (``open=True``) the issue."""
        self._gh(["issue", "reopen" if open else "close", str(issue.number), "--repo", self.repo])
