"""Scaffolding tests for the hook dispatcher (spec 010, unit: hook dispatch core).

Complements the acceptance suite in tests/test_hooks.py (C-002..C-006), covering the
dispatcher seams no acceptance criterion gates:

- the R-004 binding-shape rules at fire time: a non-argv-list binding is skipped with a
  stderr warning naming the remedy, an absent/empty binding is skipped silently, and every
  command bound to one event is spawned;
- totality outside an install: a trigger with no reachable config fires nothing and stays
  clean.

Same idioms as the acceptance suite: hook doubles are Python scripts invoked as
`[sys.executable, script, ...]` argv lists, every detached double is awaited via the record
line it writes itself, and everything runs through the CLI (CliRunner) on a local checkout.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from conftest import install, run


def _stderr(result):
    try:
        return result.stderr or ""
    except (ValueError, AttributeError):
        return ""


def _all_output(result):
    return (result.output or "") + _stderr(result)


def _init(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return install(root)


def _configure_hooks(root: Path, hooks) -> None:
    path = root / ".grillwork" / "settings" / "config.json"
    data = json.loads(path.read_text(encoding="utf-8")) or {}
    data["hooks"] = hooks
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _new_spec(root: Path, title: str = "Alpha") -> dict:
    result = run(["new-spec", "--title", title, str(root)])
    assert result.exit_code == 0, _all_output(result)
    return json.loads(result.stdout)


def _wait_for(predicate, message: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    assert predicate(), message


_RECORDER = """\
import json, os, sys
record = {"env": {k: v for k, v in os.environ.items() if k.startswith("GRILLWORK_")}}
with open(sys.argv[1], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\\n")
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
    """The variables the engine added on top of the inherited environment."""
    return {k: v for k, v in record["env"].items() if os.environ.get(k) != v}


def _recorder_cmd(work: Path, records_name: str = "records.jsonl"):
    script = work / "recorder.py"
    script.write_text(_RECORDER, encoding="utf-8")
    records = work / records_name
    return [sys.executable, str(script), str(records)], records


def _same_path(a, b) -> bool:
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


# --- the R-004 binding-shape rules at fire time -------------------------------------------


def test_non_argv_binding_skipped_with_remedy_warning(tmp_path):
    # A bare-string command is a config error: skipped at fire time with a stderr warning
    # naming the remedy (the argv-list shape); a well-formed command bound beside it still
    # fires, and the trigger is unaffected.
    root = _init(tmp_path / "repo")
    created = _new_spec(root)
    cmd, records = _recorder_cmd(tmp_path)
    _configure_hooks(root, {"on-transition": ["python hooks/sync.py", cmd]})

    result = run(["spec-status", created["path"], "--set", "accepted"])
    assert result.exit_code == 0, _all_output(result)
    stderr = _stderr(result)
    assert "python hooks/sync.py" in stderr, "the warning must name the offending binding"
    assert "argv list" in stderr, "the warning must name the remedy (the argv-list shape)"

    _wait_for(lambda: len(_records(records)) >= 1, "the well-formed command beside it never fired")
    assert _payload(_records(records)[0]).get("GRILLWORK_NEW_STATUS") == "accepted"


def test_event_bound_to_non_list_skipped_with_warning(tmp_path):
    # An event whose whole binding is not a list of commands gets the same treatment.
    root = _init(tmp_path / "repo")
    created = _new_spec(root)
    _configure_hooks(root, {"on-transition": "python hooks/sync.py"})

    result = run(["spec-status", created["path"], "--set", "accepted"])
    assert result.exit_code == 0, _all_output(result)
    assert "argv" in _stderr(result)
    assert json.loads(result.stdout)["status"] == "accepted"


def test_absent_and_empty_bindings_skipped_silently(tmp_path):
    # An event with no binding — the key absent, or an empty list — is simply skipped:
    # no warning, no output beyond the trigger's own JSON.
    root = _init(tmp_path / "repo")
    created = _new_spec(root)

    # (1) no hooks section at all (the fresh install).
    result = run(["spec-status", created["path"], "--set", "accepted"])
    assert result.exit_code == 0, _all_output(result)
    assert _stderr(result) == ""

    # (2) the event present but bound to an empty list.
    _configure_hooks(root, {"on-transition": []})
    result = run(["spec-status", created["path"], "--set", "building"])
    assert result.exit_code == 0, _all_output(result)
    assert _stderr(result) == ""


def test_every_command_bound_to_an_event_fires(tmp_path):
    # An event binds a LIST of commands; each is spawned (in binding order — completion
    # order is deliberately unobservable: the contract allows concurrent, out-of-order
    # delivery, so this asserts both records exist, not their sequence).
    root = _init(tmp_path / "repo")
    created = _new_spec(root)
    first_cmd, first_records = _recorder_cmd(tmp_path, "first.jsonl")
    second_cmd, second_records = _recorder_cmd(tmp_path, "second.jsonl")
    _configure_hooks(root, {"on-transition": [first_cmd, second_cmd]})

    result = run(["spec-status", created["path"], "--set", "accepted"])
    assert result.exit_code == 0, _all_output(result)
    _wait_for(lambda: len(_records(first_records)) >= 1, "the first bound command never fired")
    _wait_for(lambda: len(_records(second_records)) >= 1, "the second bound command never fired")


def test_embedded_nul_argv_is_a_spawn_failure_not_a_crash(tmp_path):
    # An argv element carrying an embedded NUL (reachable from adopter config: YAML `"\0"`
    # parses to a NUL character) makes Popen raise ValueError, not OSError. Totality
    # (R-005): the hook never started, so this is a spawn failure — the trigger still
    # exits 0 with the flip persisted, stderr warns naming the command, and a well-formed
    # binding beside it still fires.
    root = _init(tmp_path / "repo")
    created = _new_spec(root)
    cmd, records = _recorder_cmd(tmp_path)
    poisoned = [sys.executable, "x\x00y"]
    _configure_hooks(root, {"on-transition": [poisoned, cmd]})

    result = run(["spec-status", created["path"], "--set", "accepted"])
    assert result.exit_code == 0, _all_output(result)
    assert json.loads(result.stdout)["status"] == "accepted"  # the flip persisted
    stderr = _stderr(result)
    assert "could not be spawned" in stderr, f"expected a spawn-failure warning; got {stderr!r}"
    # The command's basename, not the full path: the warning reprs argv[0], which escapes
    # Windows path backslashes; the basename carries none and still proves the naming.
    assert Path(sys.executable).name in stderr, "the warning must name the command"

    _wait_for(lambda: len(_records(records)) >= 1, "the well-formed command beside it never fired")


# --- totality outside an install ----------------------------------------------------------


def test_transition_outside_any_install_fires_nothing_and_stays_clean(tmp_path):
    # `spec-status --set` needs no config; with no install to read bindings from, the
    # dispatcher resolves nothing and stays silent — the trigger's own behavior is untouched.
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(
        "# Spec: Loose\n\n| | |\n|---|---|\n| **ID** | 001-loose |\n"
        "| **Status** | drafting |\n| **Status changed** | 2026-01-01T00:00:00+00:00 |\n",
        encoding="utf-8",
    )
    result = run(["spec-status", str(spec_path), "--set", "ready"])
    assert result.exit_code == 0, _all_output(result)
    assert json.loads(result.stdout)["status"] == "ready"
    assert _stderr(result) == ""
