"""Shared test infrastructure for the GitHub Projects harness — its fakes, moved here with it.

The harness's only connection to GitHub is the module-level factory
``github_projects.board_client(settings) -> BoardClient``. These tests must run network-free,
so they substitute an in-memory :class:`FakeBoard` at exactly that seam via monkeypatch — the
`--check` enumeration and every projection then talk to the fake instead of real ``gh``. Tests
assert the resulting **board state** (which issues exist, which option each item's chosen field
carries, their open/closed state, project membership) — never which client method was called,
so any equivalent reimplementation of the harness still passes.

**The board-client surface this fake mirrors:**

- ``board_client(settings)`` builds a client bound to the settings' board identity **and their
  chosen single-select field** (``settings.status_field``) — so the fake reads the chosen field
  from the settings it is handed, exactly as the real client does. The identity-only target the
  enumeration path builds carries no chosen field (the fake tolerates that: the field is simply
  unbound).
- ``single_select_fields() -> list[tuple[str, list[str]]]`` — every single-select field on the
  board with its option names, **in board order**.
- ``set_item_status(item, option_name)`` — set the **chosen** field to the named option.
- ``find_issue`` / ``create_issue`` / ``update_issue`` / ``add_to_project`` /
  ``set_issue_state``.

The fakes and the fixtures live here; where the tests get **engine** content — the install
they were copied into, and how they ask it things — lives in ``harness_engine.py`` beside
this file, and importing it below is also what puts the harness's own modules on ``sys.path``
(they sit one directory up: they are a harness, not an installed package). That is all it
takes for a plain ``pytest`` to collect and run these, here or from a copy at any depth.
``github_projects`` itself is imported lazily at the ``FakeBoard`` raise sites, so a
module-level import error can never abort the whole session at collection.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from harness_engine import ENGINE, IDENTITY_FIELD, IDENTITY_MAP, SPEC_STATUSES


class FakeIssue:
    """Opaque handle the adapter receives from ``find_issue`` / ``create_issue`` and passes
    back to ``update_issue`` / ``add_to_project`` / ``set_issue_state``. It carries a reference
    to the fake board's mutable record so those ops mutate board state in place. The adapter
    treats it as opaque (it never inspects these internals)."""

    def __init__(self, record: dict) -> None:
        self.record = record


class FakeItem:
    """Opaque project-item handle the adapter receives from ``add_to_project`` and passes to
    ``set_item_status``. Also references the same mutable board record."""

    def __init__(self, record: dict) -> None:
        self.record = record


class FakeBoard:
    """An in-memory stand-in for a GitHub Projects v2 board, substituted at the
    ``gh``/board-client boundary.

    Construction knobs (a test tweaks these before firing a sync):

    - ``reachable`` — when False, enumerating the board (:meth:`single_select_fields`) raises
      ``GitHubError``, simulating ``gh`` missing / unauthenticated / the project not found.
    - ``fields`` — the board's single-select fields as ``{field name: [option names]}``, in board
      order; defaults to one "Status" field carrying the seven lifecycle names. ``{}`` models a
      board with **no** single-select field — the harness rejects that rather than adding one.
    - ``fail`` — when True, every projection op raises ``GitHubError`` (a transient network /
      rate-limit error, or a since-removed column).

    Inspectable state read by assertions:

    - :attr:`issues` — a dict keyed by ``spec_id``; each entry records ``title``, ``body``,
      ``fields`` (``{field name: option name}`` — what the board holds for that item), ``open``
      (bool), and ``on_project`` (bool). For a correct find-or-create adapter there is exactly
      one issue per spec.

      What ``fields`` does and does not prove: the fake *is* the client, and it takes the field
      it writes from the settings it is handed — so a `fields` assertion proves the **option**
      came from the settings' map and landed on the **configured** field, but it cannot prove the
      client resolved that field from the settings rather than hard-coding one. This is inherent
      to substituting at ``board_client(settings)`` — the harness's one door to GitHub — not a
      gap in the assertion.
    - :meth:`issues_for` — the raw list of issues carrying a spec's marker, so a duplicate
      (a wrong adapter that creates instead of updating) is observable as board state.
    """

    def __init__(
        self,
        *,
        reachable: bool = True,
        fields: dict[str, list[str]] | None = None,
        fail: bool = False,
    ) -> None:
        self.reachable = reachable
        # Default to a lifecycle-shaped board: one single-select "Status" field whose options are
        # the seven lifecycle names. A test models any other board by assigning ``fields``.
        self.fields = (
            {"Status": list(SPEC_STATUSES)}
            if fields is None
            else {name: list(options) for name, options in fields.items()}
        )
        self.fail = fail
        # The field this client was built against (``settings.status_field``) — the one the
        # projection writes to. Unbound until settings naming one are handed to ``board_client``.
        self.chosen_field: str | None = None
        # The board as GitHub holds it: a list of issue records. ``create_issue`` appends; a
        # correct adapter find-or-creates, so there is one record per spec_id.
        self._board: list[dict] = []

    def bind(self, settings) -> None:
        """Adopt the chosen single-select field from the settings the client is built with —
        what the real client does at construction (``board_client(settings)``). The enumeration
        path's identity-only target carries no chosen field, which leaves it unbound."""
        self.chosen_field = getattr(settings, "status_field", "") or None

    # --- enumeration (`hook.py --check`) --------------------------------------------------

    def single_select_fields(self) -> list[tuple[str, list[str]]]:
        """Every single-select field on the board with its option names, in board order — what
        ``hook.py --check`` prints, and what its map validation re-reads. ``[]`` when the board
        has none. Raises ``GitHubError`` when the board is unreachable."""
        import github_projects  # lazy: keep conftest import-safe

        if not self.reachable:
            raise github_projects.GitHubError(
                "GitHub board unreachable: gh is missing/unauthenticated or the project was "
                "not found. Run `gh auth login` and check the project owner/number."
            )
        return [(name, list(options)) for name, options in self.fields.items()]

    # --- projection (sync-time) ----------------------------------------------------------

    def find_issue(self, spec_id: str) -> FakeIssue | None:
        """The one issue whose body carries the ``grillwork-spec:<spec_id>`` marker, else None.
        The fake correlates by ``spec_id`` directly (its body carries the marker)."""
        self._maybe_fail()
        for record in self._board:
            if record["spec_id"] == spec_id:
                return FakeIssue(record)
        return None

    def create_issue(self, spec_id: str, title: str, body: str) -> FakeIssue:
        """Create an issue (its body already contains the correlation marker). Always appends a
        new record — as GitHub's create does — so a non-idempotent adapter shows up as a
        duplicate in :meth:`issues_for`."""
        self._maybe_fail()
        record = {
            "spec_id": spec_id,
            "title": title,
            "body": body,
            "fields": {},
            "open": True,
            "on_project": False,
        }
        self._board.append(record)
        return FakeIssue(record)

    def update_issue(self, issue: FakeIssue, title: str, body: str) -> None:
        """Update the issue's title/body in place."""
        self._maybe_fail()
        issue.record["title"] = title
        issue.record["body"] = body

    def add_to_project(self, issue: FakeIssue) -> FakeItem:
        """Ensure the issue is a project item (idempotent); return the item."""
        self._maybe_fail()
        issue.record["on_project"] = True
        return FakeItem(issue.record)

    def set_item_status(self, item: FakeItem, option_name: str) -> None:
        """Set the **chosen** single-select field to ``option_name``. Raises ``GitHubError``
        naming what is missing when no field is bound, when the bound field is no longer on the
        board, or when the option is not one of that field's (a since-renamed/deleted column).

        These messages are deliberately **board-side only**: they name what GitHub does not
        have, and never the harness's remedy for it. Naming a remedy is the adapter's job (its
        missing-map raise names `settings.yaml`), and a fake that volunteered it would let that
        assertion pass on the fake's own words."""
        self._maybe_fail()
        import github_projects  # lazy: keep conftest import-safe

        field = self.chosen_field
        if not field:
            raise github_projects.GitHubError(
                "no single-select field was named for this board, so there is no field to set "
                "an option on."
            )
        if field not in self.fields:
            raise github_projects.GitHubError(f"the single-select field {field!r} is not on the board.")
        if option_name not in self.fields[field]:
            raise github_projects.GitHubError(
                f"option {option_name!r} is not on the board's {field!r} field."
            )
        item.record["fields"][field] = option_name

    def set_issue_state(self, issue: FakeIssue, *, open: bool) -> None:  # noqa: A002 — GitHub's field name
        """Close (``open=False``) or reopen (``open=True``) the issue."""
        self._maybe_fail()
        issue.record["open"] = open

    # --- state read by assertions --------------------------------------------------------

    @property
    def issues(self) -> dict[str, dict]:
        """The board keyed by ``spec_id`` — one record per spec for a correct adapter."""
        return {record["spec_id"]: record for record in self._board}

    def issues_for(self, spec_id: str) -> list[dict]:
        """Every issue on the board carrying ``spec_id``'s marker (board state, not a call
        count) — its length reveals a duplicate a non-idempotent adapter would leave."""
        return [record for record in self._board if record["spec_id"] == spec_id]

    def _maybe_fail(self) -> None:
        import github_projects  # lazy: keep conftest import-safe

        if self.fail:
            raise github_projects.GitHubError(
                "GitHub API error (simulated network/rate-limit failure). Retry later or check "
                "`gh` connectivity."
            )


@pytest.fixture
def fake_board(monkeypatch):
    """Install a fresh :class:`FakeBoard` at ``github_projects.board_client`` for one test and
    return it, so the test can shape the board (``fake_board.fields = {...}``,
    ``fake_board.fail = True``, …) before it fires a sync. The single instance is returned for
    every ``board_client(settings)`` call, so the enumeration and every projection share its
    state — while each call rebinds the chosen field from the settings it is handed, exactly as
    building a real client does."""
    import github_projects

    board = FakeBoard()

    def _client(settings):
        board.bind(settings)
        return board

    monkeypatch.setattr(github_projects, "board_client", _client)
    return board


@pytest.fixture
def harness_settings():
    """A settings factory: ``harness_settings(root, field=..., mapping=...)`` builds the
    harness's own :class:`settings.Settings` for a repo — the settings file's parsed shape,
    without a file, so a test binds a board in one line. Any loader that produces the same
    values satisfies these tests."""
    import settings as settings_module

    def _make(root, *, field=IDENTITY_FIELD, mapping=None, integration_target=""):
        return settings_module.Settings(
            root=Path(root),
            owner="acme",
            project_number="2",
            repo="acme/widgets",
            status_field=field,
            status_map=dict(IDENTITY_MAP if mapping is None else mapping),
            integration_target=integration_target,
        )

    return _make


@pytest.fixture
def spec_repo(tmp_path):
    """A real Grillwork install to read specs out of — the harness reads spec FILES, so the
    tests give it real ones rather than fixtures shaped like them.

    Installation is a prompt an agent follows, not a callable, so this writes the same shape
    that prompt describes: the method under `.grillwork/engine/` (the spec template is what
    `new_spec` reads), the deterministic helper under `.grillwork/engine/lib/` (which the
    harness *runs* — engine content is asked for, not imported, so these tests spawn the real
    helper rather than stubbing it), and the settings beside it.

    The engine is copied from :data:`ENGINE` — the install these tests are part of — so the
    fixture is a copy of a real install rather than of anything particular to Grillwork's own
    repo. Copied whole, because which of its files an install consists of is the install's
    business, not this fixture's."""
    import json

    root = tmp_path / "repo"
    shutil.copytree(ENGINE, root / ".grillwork" / "engine",
                    ignore=shutil.ignore_patterns("__pycache__"))

    settings = root / ".grillwork" / "settings"
    settings.mkdir(parents=True)
    (settings / "config.json").write_text(
        json.dumps(
            {
                "spec_home": ".grillwork/specs",
                "builder": "claude-code",
                "gate": "",
                "integration_target": "",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return root
