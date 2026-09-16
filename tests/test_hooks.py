"""Acceptance suite for spec 010 (the engine boundary: hooks in, trackers out) — the hook
contract half: C-001..C-006, C-014, C-015, C-017, C-018.

Authored blind from the spec, before implementation (the Acceptance-Test Writer role): every
test drives the engine through its observable seams — the CLI (`grillwork.cli.app` under
CliRunner, the suite's existing idiom), the file system of a fresh stamped install, the
recorded environment of spawned hook processes, and doc content. No test asserts
engine-internal structure, except test_tracker_machinery_removed (C-015), where file
presence/absence in `src/grillwork/` is itself the requirement.

Hook doubles are Python scripts invoked as `[sys.executable, script, ...]` argv lists
(Windows/POSIX portable, no shell), and each is *harder* than a real hook in the dimension
under test (falsifiability rubric): a genuinely blocking hook for detachment (C-005), a
poisoned argv element for shell interpretation (C-003), both a spawn-failing and a
nonzero-exiting hook for the two failure kinds (C-004). Detached-hook assertions go through
completion markers the hook itself writes, and every spawned double is awaited via its
marker/record before the test ends, so teardown never races a detached child (the spec's
proof-mechanism notes). Everything runs on a local checkout, no network.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from conftest import ENGINE, install, run

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The contract's events (R-002, as amended by contract v2 — the first-install event was
# removed as unreachable). The contract doc and the stamped config must name all four tokens,
# and neither may resurrect a first-install one (`_RETIRED_EVENT`).
_EVENTS = ("on-spec-created", "on-transition", "publish-evidence", "on-upgrade")
_RETIRED_EVENT = "on-install"

# The doorbell payload's transport (R-003) — the variables the contract doc must name.
_PAYLOAD_VARS = (
    "GRILLWORK_EVENT",
    "GRILLWORK_SPEC_PATH",
    "GRILLWORK_OLD_STATUS",
    "GRILLWORK_NEW_STATUS",
    "GRILLWORK_ROOT",
    "GRILLWORK_ENGINE_VERSION",
)


# --- shared drivers ----------------------------------------------------------------------


def _stderr(result):
    try:
        return result.stderr or ""
    except (ValueError, AttributeError):
        return ""


def _all_output(result):
    return (result.output or "") + _stderr(result)


def _init(root: Path) -> Path:
    """A fresh Grillwork install stamped into ``root`` through the CLI (black-box)."""
    root.mkdir(parents=True, exist_ok=True)
    return install(root)


def _config_path(root: Path) -> Path:
    return root / ".grillwork" / "settings" / "config.json"


def _configure(root: Path, *, hooks=None, evidence=None) -> None:
    """Bind ``hooks:`` (event -> list of argv-list commands, R-004) and/or the ``evidence:``
    booleans (R-007) by rewriting the install's config as data. Comments are lost, which is
    fine: these tests read behavior, and only C-001 reads the raw init-written text (on a
    fresh install this helper never touched)."""
    path = _config_path(root)
    data = json.loads(path.read_text(encoding="utf-8")) or {}
    if hooks is not None:
        data["hooks"] = hooks
    if evidence is not None:
        data["evidence"] = evidence
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _new_spec(root: Path, title: str = "Alpha") -> dict:
    result = run(["new-spec", "--title", title, str(root)])
    assert result.exit_code == 0, _all_output(result)
    return json.loads(result.stdout)


def _set_status(spec_path, status: str):
    return run(["spec-status", str(spec_path), "--set", status])


def _read_status(spec_path) -> str:
    result = run(["spec-status", str(spec_path)])
    assert result.exit_code == 0, _all_output(result)
    return json.loads(result.stdout)["status"]


def _wait_for(predicate, message: str, timeout: float = 15.0) -> None:
    """Poll for a detached hook's observable effect (its own completion marker/record) —
    the trigger never waits for it (R-005), so the test must."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    assert predicate(), message


def _script(dirpath: Path, name: str, body: str) -> Path:
    path = dirpath / name
    path.write_text(body, encoding="utf-8")
    return path


def _same_path(a, b) -> bool:
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def _under(child, parent) -> bool:
    c = os.path.normcase(str(Path(child).resolve()))
    p = os.path.normcase(str(Path(parent).resolve()))
    return c == p or c.startswith(p + os.sep)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True,
    )


# The recorder double: appends one JSON line per invocation — its GRILLWORK_* environment
# (the doorbell payload, R-003) and any extra argv elements it was handed (so C-003 can see
# a poisoned element arrive verbatim). The single appended write is the hook's own
# completion marker: a test waits for its line before asserting or cleaning up.
_RECORDER = """\
import json, os, sys
record = {
    "argv": sys.argv[2:],
    "env": {k: v for k, v in os.environ.items() if k.startswith("GRILLWORK_")},
}
with open(sys.argv[1], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\\n")
"""

# A genuinely blocking hook (harder than a real hook in the detachment dimension, C-005):
# it holds until the test writes the release file, then writes its completion marker.
_BLOCKER = """\
import os, sys, time
release, marker = sys.argv[1], sys.argv[2]
deadline = time.time() + 60
while not os.path.exists(release) and time.time() < deadline:
    time.sleep(0.05)
with open(marker, "w", encoding="utf-8") as fh:
    fh.write("done")
"""

# A hook that starts, proves it started (the marker), then exits nonzero — the
# started-then-failed kind C-004 distinguishes from a spawn failure.
_FAILER = """\
import sys
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    fh.write("started")
sys.exit(3)
"""


def _records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _payload(record: dict) -> dict:
    """The variables the ENGINE added to the hook's environment — inherited GRILLWORK_* vars
    (e.g. a developer's own shell) are excluded by value, so the 'nothing more' half of
    R-003's doorbell can be asserted as set equality."""
    return {k: v for k, v in record["env"].items() if os.environ.get(k) != v}


def _bind_recorder(root: Path, work: Path, events, *extra_argv: str) -> Path:
    """Bind the recorder to ``events``; return the records file its lines land in."""
    recorder = _script(work, "recorder.py", _RECORDER)
    records = work / "records.jsonl"
    cmd = [sys.executable, str(recorder), str(records), *extra_argv]
    _configure(root, hooks={event: [cmd] for event in events})
    return records


# --- C-001 -------------------------------------------------------------------------------


# --- C-002 -------------------------------------------------------------------------------


def test_events_fire_with_doorbell_payload(tmp_path):
    """C-002 — a recorder bound to `on-spec-created` and `on-transition` receives the
    doorbell: `new-spec` yields the event name + the new spec's path; each `spec-status
    --set` yields the correct old/new pair — the regression (`approved -> drafting`)
    included, because the engine holds no notion of "forward" (R-002/R-003)."""
    root = _init(tmp_path / "repo")
    records = _bind_recorder(root, tmp_path, ("on-spec-created", "on-transition"))

    created = _new_spec(root)
    _wait_for(lambda: len(_records(records)) >= 1,
              "on-spec-created never reached the bound hook")
    payload = _payload(_records(records)[0])
    assert payload.get("GRILLWORK_EVENT") == "on-spec-created"
    assert _same_path(payload.get("GRILLWORK_SPEC_PATH", ""), created["path"])
    assert set(payload) == {"GRILLWORK_EVENT", "GRILLWORK_SPEC_PATH"}, (
        f"on-spec-created payload is the doorbell and nothing more; got {sorted(payload)}"
    )

    assert _set_status(created["path"], "approved").exit_code == 0
    _wait_for(lambda: len(_records(records)) >= 2,
              "on-transition (drafting -> approved) never reached the bound hook")
    payload = _payload(_records(records)[1])
    assert payload.get("GRILLWORK_EVENT") == "on-transition"
    assert _same_path(payload.get("GRILLWORK_SPEC_PATH", ""), created["path"])
    assert payload.get("GRILLWORK_OLD_STATUS") == "drafting"
    assert payload.get("GRILLWORK_NEW_STATUS") == "approved"
    assert set(payload) == {
        "GRILLWORK_EVENT", "GRILLWORK_SPEC_PATH", "GRILLWORK_OLD_STATUS", "GRILLWORK_NEW_STATUS",
    }, f"on-transition payload is the doorbell and nothing more; got {sorted(payload)}"

    # The regression: a send-back fires like any other status change.
    assert _set_status(created["path"], "drafting").exit_code == 0
    _wait_for(lambda: len(_records(records)) >= 3,
              "on-transition (approved -> drafting regression) never reached the bound hook")
    payload = _payload(_records(records)[2])
    assert payload.get("GRILLWORK_OLD_STATUS") == "approved"
    assert payload.get("GRILLWORK_NEW_STATUS") == "drafting"


# --- C-003 -------------------------------------------------------------------------------


def test_no_shell_interpretation(tmp_path):
    """C-003 — an argv element full of shell metacharacters reaches the hook verbatim as a
    single argument, and no shell side effect occurs (invocation without a shell, R-004)."""
    root = _init(tmp_path / "repo")
    poison = "&& echo poisoned > poison.txt"
    records = _bind_recorder(root, tmp_path, ("on-transition",), poison)

    created = _new_spec(root)
    assert _set_status(created["path"], "accepted").exit_code == 0
    _wait_for(lambda: len(_records(records)) >= 1, "the poisoned-argv hook never fired")

    assert _records(records)[0]["argv"] == [poison], (
        "the metacharacter element must arrive verbatim as ONE argument"
    )
    for where in {Path.cwd(), root, tmp_path}:
        assert not (where / "poison.txt").exists(), (
            f"a shell interpreted the argv element: {where / 'poison.txt'} exists"
        )


# --- C-004 -------------------------------------------------------------------------------


def test_spawn_failure_is_nonfatal(tmp_path):
    """C-004 — a SPAWN failure (command missing) leaves the trigger exiting 0 with the flip
    persisted, and warns on stderr naming the command; a hook that starts and then exits
    nonzero produces no engine warning at all (its failure is its own to log, R-005)."""
    root = _init(tmp_path / "repo")
    created = _new_spec(root)

    # (1) spawn failure: the bound command does not exist.
    missing = "grillwork-no-such-hook-cmd-xyz"
    _configure(root, hooks={"on-transition": [[missing]]})
    result = _set_status(created["path"], "accepted")
    assert result.exit_code == 0, _all_output(result)
    assert _read_status(created["path"]) == "accepted"  # the flip persisted
    assert missing in _stderr(result), (
        f"the spawn-failure warning must name the command; stderr={_stderr(result)!r}"
    )

    # (2) started-then-failed: the hook spawns fine, writes its marker, exits 3.
    failer = _script(tmp_path, "failer.py", _FAILER)
    marker = tmp_path / "failer-marker.txt"
    _configure(root, hooks={"on-transition": [[sys.executable, str(failer), str(marker)]]})
    result = _set_status(created["path"], "building")
    assert result.exit_code == 0, _all_output(result)
    assert _read_status(created["path"]) == "building"
    stderr = _stderr(result)
    assert "warn" not in stderr.lower() and "failer" not in stderr, (
        f"a hook's own nonzero exit must produce NO engine warning; stderr={stderr!r}"
    )
    _wait_for(marker.exists, "the nonzero-exiting hook was never spawned at all")


# --- C-005 -------------------------------------------------------------------------------


def test_hooks_are_detached(tmp_path):
    """C-005 — a genuinely blocking hook does not delay its trigger: the CLI returns while
    the hook's completion marker is still absent, and the marker appears afterward without
    any further engine call (fully detached spawn, R-005)."""
    root = _init(tmp_path / "repo")
    blocker = _script(tmp_path, "blocker.py", _BLOCKER)
    release = tmp_path / "release.txt"
    marker = tmp_path / "blocker-marker.txt"
    _configure(root, hooks={"on-transition": [[sys.executable, str(blocker), str(release), str(marker)]]})

    created = _new_spec(root)
    result = _set_status(created["path"], "accepted")
    assert result.exit_code == 0, _all_output(result)
    assert not marker.exists(), (
        "the trigger returned only after the blocking hook finished — dispatch is not detached"
    )

    release.write_text("go", encoding="utf-8")  # not an engine call
    _wait_for(marker.exists, "the detached hook never completed after release "
                             "(it was never spawned, or was killed with its trigger)")


# --- C-006 -------------------------------------------------------------------------------


def test_fires_from_worktree(tmp_path):
    """C-006 — a transition executed inside a linked git worktree fires the hook with
    `GRILLWORK_SPEC_PATH` pointing into that worktree — hooks fire from wherever the
    triggering command runs, and the harness sees live build state (R-006)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _init(repo)
    records = _bind_recorder(repo, tmp_path, ("on-transition",))
    created = _new_spec(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed")

    worktree = tmp_path / "wt"
    _git(repo, "worktree", "add", "--detach", str(worktree))
    rel = Path(created["path"]).resolve().relative_to(repo.resolve())
    wt_spec = worktree / rel
    assert wt_spec.exists()

    result = _set_status(wt_spec, "accepted")
    assert result.exit_code == 0, _all_output(result)
    _wait_for(lambda: len(_records(records)) >= 1, "the worktree transition fired no hook")
    payload = _payload(_records(records)[0])
    assert _under(payload.get("GRILLWORK_SPEC_PATH", ""), worktree), (
        f"GRILLWORK_SPEC_PATH must point into the worktree; "
        f"got {payload.get('GRILLWORK_SPEC_PATH')!r}"
    )


# --- C-014 -------------------------------------------------------------------------------


def test_reviewer_input_names_bundle_path(tmp_path):
    """C-014 — the installed `roles/dod-reviewer.md` and the build command that convenes the
    DoD review name the evidence bundle's path as an explicit reviewer input (R-012), and
    neither instructs fetching evidence from external storage during verification (content
    assertions over stamped/compiled files — the Evidence Plan's stated mechanism)."""
    root = _init(tmp_path / "repo")
    fetch = re.compile(r"(?i)(fetch|download)\w*[^\n]{0,60}(evidence|bundle|artifact)")
    negated = re.compile(r"(?i)\b(never|not|no)\b")

    for path in (
        root / ".grillwork" / "engine" / "roles" / "dod-reviewer.md",
        ENGINE / "commands" / "grillwork-build.md",
    ):
        assert path.exists(), f"{path} is missing"
        text = path.read_text(encoding="utf-8")
        assert re.search(r"(?i)evidence bundle", text), (
            f"{path.name} does not name the evidence bundle as reviewer input"
        )
        assert re.search(r"(?i)path", text), (
            f"{path.name} does not name the bundle's PATH as the explicit input"
        )
        for line in text.splitlines():
            if negated.search(line):
                continue  # "never fetches from external storage" is the required statement
            assert not fetch.search(line), (
                f"{path.name} instructs fetching evidence during verification: {line!r}"
            )


# --- C-015 -------------------------------------------------------------------------------


def test_tracker_machinery_removed(tmp_path):
    """C-015 — the removal is total (R-013/R-014). File presence/absence in `src/grillwork/`
    is itself the requirement here — the one criterion where the spec's sufficiency rubric
    allows asserting on the source tree — plus the CLI/config surfaces, black-box."""
    src = _REPO_ROOT / "engine" / "lib" / "grillwork"
    assert not (src / "board.py").exists(), "board.py must be removed from the engine"
    assert not (src / "github.py").exists(), "github.py must leave the engine"
    assert "compose_body" not in (src / "package.py").read_text(encoding="utf-8"), (
        "package.py must no longer carry the GitHub-flavored renderer (compose_body)"
    )

    # The CLI offers no set-tracker (typer: unknown command is a usage error, exit 2).
    result = run(["set-tracker", "local", str(tmp_path)])
    assert result.exit_code == 2, "`grillwork set-tracker` must no longer exist"

    # A fresh install: config output carries no tracker/github_* keys; no tracker seeding.
    root = _init(tmp_path / "repo")
    shown = run(["config", str(root)])
    assert shown.exit_code == 0, _all_output(shown)
    data = json.loads(shown.output)
    assert "tracker" not in data, "`grillwork config` must not report a tracker key"
    assert not any(key.startswith("github_") for key in data), (
        f"`grillwork config` must not report github_* keys; got {sorted(data)}"
    )
    assert not (root / ".grillwork" / "tracker").exists(), (
        "init must seed no .grillwork/tracker/"
    )


# --- C-017 -------------------------------------------------------------------------------


# --- C-018 -------------------------------------------------------------------------------


def test_guide_and_docs_synced(tmp_path):
    """C-018 — the stamped harness guide exists and walks contract -> build -> wire ->
    dry-run, pointing at the worked example (R-018); the enumerated living docs carry no
    reference to the removed machinery (the scoped token grep, R-019); the stamped role
    assets carry no bare `board`/`tracker` token (the silent-rot class); the builder role's
    step-2 parenthetical is reworded to the R-006 reality; and the design-of-record docs
    describe the hook contract and the amended reviewer input."""
    root = _init(tmp_path / "repo")

    # (1) the guide: present, the four-step walkthrough, the worked-example pointer.
    guide = root / ".grillwork" / "engine" / "harness-guide.md"
    assert guide.exists(), "init did not stamp .grillwork/engine/harness-guide.md"
    guide_text = guide.read_text(encoding="utf-8")
    assert _RETIRED_EVENT not in guide_text, (
        f"the guide names {_RETIRED_EVENT!r}, an event no adopter can receive"
    )
    for pattern, step in (
        (r"(?i)contract", "read the contract"),
        (r"(?i)hook", "build a hook"),
        (r"(?i)config", "wire the config"),
        (r"(?i)dry[- ]?run|--fire", "prove it with the dry-run"),
    ):
        assert re.search(pattern, guide_text), f"the guide does not walk the step: {step}"
    assert "examples/github-projects" in guide_text, (
        "the guide must point at the extracted worked example"
    )

    # (2) the published prose: no reference to the removed machinery. `tracker:` / `github_`
    # match the config keys case-sensitively, so prose like "the Tracker" is not a false
    # positive. The list is what ships — design docs and CLAUDE.md are authoring material and
    # are not published, so a fresh clone has nothing else to check and this cannot depend on
    # a file that is absent.
    enumerated = ("README.md",)
    # `_RETIRED_EVENT` joins the removed machinery: an event no adopter can receive must not
    # be advertised in a living doc either, or the prose re-promises what the engine dropped.
    removed_tokens = (
        "set-tracker", "board.py", "Tracker.html", "tracker:", "github_", _RETIRED_EVENT,
    )
    for rel in enumerated:
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        for token in removed_tokens:
            assert token not in text, f"{rel} still references removed machinery: {token!r}"

    # (3) the stamped role assets: no bare board/tracker token at all — the class the
    # scoped-token grep above cannot catch. Word-boundary, case-insensitive ("keyboard"
    # and "dashboard" do not match).
    roles_dir = root / ".grillwork" / "engine" / "roles"
    for role in sorted(roles_dir.glob("*.md")):
        text = role.read_text(encoding="utf-8")
        for token in (r"\bboard\b", r"\btracker\b"):
            assert not re.search(token, text, re.IGNORECASE), (
                f"roles/{role.name} carries a bare {token} token"
            )

    # (4) the builder role's step-2 parenthetical, reworded per R-019(b): mid-build flips
    # happen on the branch in its worktree while the trunk's spec stays `approved` until the
    # merge. (The OLD wording's "board" is already forbidden by (3); this asserts the
    # replacement reality is stated.)
    builder_text = (roles_dir / "builder.md").read_text(encoding="utf-8")
    assert re.search(r"(?i)worktree", builder_text)
    assert re.search(r"(?i)approved[\s\S]{0,300}merge", builder_text), (
        "builder.md must state the trunk's spec file stays approved until the merge"
    )

