"""The wiring — the doorbell to the board, through ``hook.py`` exactly as the engine runs it.

The engine spawns the bound argv list with the payload in the environment. These tests call
``hook.main()`` with that same environment (and the harness's own settings file, pointed at by
``GRILLWORK_GH_SETTINGS``), so what is under test is the whole harness: read the payload, load
the settings, read the spec file, write the board. The in-memory ``fake_board`` stands in for
GitHub, so nothing here touches the network.

The one thing these prove that ``test_github_adapter.py`` cannot: the payload really is only a
doorbell. The board follows the spec **file**, even when the payload's status says otherwise —
which is what makes a late, out-of-order or repeated hook safe.

Wiring the harness the adopter's way means a settings **file**, because `status_map` is the
one setting no ``GRILLWORK_GH_*`` variable can carry — and reading that file needs PyYAML,
the harness's own conditional dependency (see the README's prerequisites). So this module
skips whole when PyYAML is absent rather than failing: without it there is no file-bound
harness to test. Everything not about the file binds without it, and still runs.
"""

from __future__ import annotations

import hook
import pytest
from harness_engine import IDENTITY_MAP, new_spec, set_status

yaml = pytest.importorskip("yaml", reason="a settings-file binding needs PyYAML")

_SETTINGS = {
    "owner": "acme",
    "project_number": "2",
    "repo": "acme/widgets",
    "status_field": "Status",
    "status_map": dict(IDENTITY_MAP),
}


def _wire(monkeypatch, tmp_path, **overrides):
    """Write the harness's settings file and point the environment at it — step 2 of the
    README's wiring, done the way an adopter would."""
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump({**_SETTINGS, **overrides}), encoding="utf-8")
    monkeypatch.setenv("GRILLWORK_GH_SETTINGS", str(path))
    return path


def _ring(monkeypatch, event, spec_path, *, old=None, new=None, dry_run=False):
    """Ring the doorbell: the payload the engine layers onto the hook's environment."""
    monkeypatch.setenv("GRILLWORK_EVENT", event)
    monkeypatch.setenv("GRILLWORK_SPEC_PATH", str(spec_path))
    for name, value in (("GRILLWORK_OLD_STATUS", old), ("GRILLWORK_NEW_STATUS", new)):
        monkeypatch.delenv(name, raising=False)
        if value is not None:
            monkeypatch.setenv(name, value)
    monkeypatch.delenv("GRILLWORK_DRY_RUN", raising=False)
    if dry_run:
        monkeypatch.setenv("GRILLWORK_DRY_RUN", "1")
    return hook.main(argv=[])


# --- the spec-created and transition events ----------------------------------------------


def test_on_spec_created_places_one_open_card(monkeypatch, tmp_path, spec_repo, fake_board):
    _wire(monkeypatch, tmp_path)
    path, sid = new_spec(spec_repo, "Alpha Feature")

    assert _ring(monkeypatch, "on-spec-created", path) == 0

    assert len(fake_board.issues_for(sid)) == 1  # exactly one issue for the spec
    record = fake_board.issues[sid]
    assert record["open"] is True
    assert record["fields"].get("Status") == "drafting"
    assert record["on_project"] is True  # added to the configured project
    assert sid in record["body"]  # body carries the spec id


def test_on_transition_follows_the_file_not_the_payload(monkeypatch, tmp_path, spec_repo, fake_board):
    # The payload is a doorbell: a hook that ran late would see a stale old/new pair. The board
    # must follow the FILE, so this rings with a deliberately stale pair and the card still
    # lands on the spec's real status.
    _wire(monkeypatch, tmp_path)
    path, sid = new_spec(spec_repo, "Alpha")
    set_status(path, "accepted")

    assert _ring(monkeypatch, "on-transition", path, old="drafting", new="ready") == 0

    assert fake_board.issues[sid]["fields"].get("Status") == "accepted"


def test_repeat_fire_leaves_one_issue(monkeypatch, tmp_path, spec_repo, fake_board):
    # Detached hooks can fire twice, or out of order: find-or-create keeps it to one issue.
    _wire(monkeypatch, tmp_path)
    path, sid = new_spec(spec_repo, "Alpha")

    _ring(monkeypatch, "on-spec-created", path)
    set_status(path, "ready")
    _ring(monkeypatch, "on-transition", path, old="drafting", new="ready")

    assert len(fake_board.issues_for(sid)) == 1
    assert fake_board.issues[sid]["fields"].get("Status") == "ready"


def test_issue_closes_at_closed_and_reopens_on_leaving(monkeypatch, tmp_path, spec_repo, fake_board):
    _wire(monkeypatch, tmp_path)
    path, sid = new_spec(spec_repo, "Alpha")

    for status in ("drafting", "ready", "approved", "building", "verified", "accepted"):
        set_status(path, status)
        _ring(monkeypatch, "on-transition", path, new=status)
        assert fake_board.issues[sid]["open"] is True, status

    set_status(path, "closed")
    _ring(monkeypatch, "on-transition", path, new="closed")
    assert fake_board.issues[sid]["fields"].get("Status") == "closed"
    assert fake_board.issues[sid]["open"] is False

    set_status(path, "accepted")
    _ring(monkeypatch, "on-transition", path, new="accepted")
    assert fake_board.issues[sid]["open"] is True


# --- the events this harness does not answer ----------------------------------------------


def test_unbound_event_is_a_silent_no_op(monkeypatch, tmp_path, spec_repo, fake_board):
    # The contract may grow events; one this harness does not answer is a success, not a crash.
    _wire(monkeypatch, tmp_path)
    path, _ = new_spec(spec_repo, "Alpha")

    assert _ring(monkeypatch, "publish-evidence", path) == 0
    assert fake_board.issues == {}


def test_dry_run_proves_the_wiring_without_touching_the_board(
    monkeypatch, tmp_path, spec_repo, fake_board, capsys
):
    # What `fire-hooks on-transition` spawns: a synthetic payload carrying
    # GRILLWORK_DRY_RUN=1. The hook reports what it would do and exits 0, board untouched.
    _wire(monkeypatch, tmp_path)
    path, _ = new_spec(spec_repo, "Alpha")

    assert _ring(monkeypatch, "on-transition", path, new="ready", dry_run=True) == 0

    assert "dry run" in capsys.readouterr().out.lower()
    assert fake_board.issues == {}


# --- failure is the harness's own ----------------------------------------------------------


def test_board_failure_exits_nonzero_and_leaves_the_spec_alone(
    monkeypatch, tmp_path, spec_repo, fake_board, capsys
):
    # A detached hook's failure is its own business: the engine never waits on it. The hook
    # reports on stderr and exits nonzero; the spec change stands.
    _wire(monkeypatch, tmp_path)
    path, _ = new_spec(spec_repo, "Alpha")
    fake_board.fail = True

    assert _ring(monkeypatch, "on-transition", path, new="drafting") == 1

    assert "github-projects" in capsys.readouterr().err.lower()
    assert path.exists()


def test_unbindable_settings_are_reported(monkeypatch, tmp_path, spec_repo, fake_board, capsys):
    # Settings that name no board: the hook says what is missing and where to set it.
    _wire(monkeypatch, tmp_path, project_number="", project_url="")
    path, _ = new_spec(spec_repo, "Alpha")

    assert _ring(monkeypatch, "on-spec-created", path) == 1

    assert "project_number" in capsys.readouterr().err
    assert fake_board.issues == {}
