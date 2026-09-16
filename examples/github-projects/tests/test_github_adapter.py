"""The adapter itself — one spec projected onto the board, against the in-memory fake.

These drive :func:`github_projects.sync_spec` directly with the harness's own settings, which
is exactly what the hook entry script calls once it has read the doorbell. Every assertion is
on **board state** (which issues exist, what option their chosen field carries, open/closed) —
never on which client method was called, so any equivalent adapter still passes.
``tests/test_tracker_github.py`` covers the same ground through ``hook.py`` and the payload;
this file is the adapter without the wiring.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import github_projects
import pytest
from harness_engine import new_spec, set_status

# --- adapter behaviour (fake-board state) ------------------------------------------------


def test_new_spec_creates_one_open_drafting_issue(spec_repo, fake_board, harness_settings):
    path, sid = new_spec(spec_repo, "Alpha Feature")

    github_projects.sync_spec(path, harness_settings(spec_repo))

    assert len(fake_board.issues_for(sid)) == 1  # exactly one issue, no duplicate
    record = fake_board.issues[sid]
    assert record["open"] is True
    assert record["fields"].get("Status") == "drafting"  # the option `drafting` maps to
    assert record["on_project"] is True
    assert sid in record["body"]  # body carries the spec id via the marker


def test_status_set_is_reflected(spec_repo, fake_board, harness_settings):
    path, sid = new_spec(spec_repo, "Alpha")

    set_status(path, "accepted")
    github_projects.sync_spec(path, harness_settings(spec_repo))

    assert fake_board.issues[sid]["fields"].get("Status") == "accepted"


def test_repeat_trigger_no_duplicate(spec_repo, fake_board, harness_settings):
    settings = harness_settings(spec_repo)
    path, sid = new_spec(spec_repo, "Alpha")

    github_projects.sync_spec(path, settings)
    set_status(path, "ready")
    github_projects.sync_spec(path, settings)  # second sync for the same spec

    assert len(fake_board.issues_for(sid)) == 1
    assert fake_board.issues[sid]["fields"].get("Status") == "ready"


def test_close_at_closed_and_reopen_on_leaving(spec_repo, fake_board, harness_settings):
    settings = harness_settings(spec_repo)
    path, sid = new_spec(spec_repo, "Alpha")

    set_status(path, "closed")
    github_projects.sync_spec(path, settings)
    assert fake_board.issues[sid]["fields"].get("Status") == "closed"
    assert fake_board.issues[sid]["open"] is False

    set_status(path, "accepted")
    github_projects.sync_spec(path, settings)
    assert fake_board.issues[sid]["open"] is True


def test_sync_raises_on_board_failure(spec_repo, fake_board, harness_settings):
    # The raise the entry script reports: sync_spec itself propagates GitHubError.
    path, _ = new_spec(spec_repo, "Alpha")
    fake_board.fail = True

    with pytest.raises(github_projects.GitHubError):
        github_projects.sync_spec(path, harness_settings(spec_repo))


def test_incomplete_map_names_the_settings_file(spec_repo, fake_board, harness_settings):
    # A map missing a stage is the settings' fault, and the message says where to fix it —
    # checked whole, before the board is touched at all.
    path, _ = new_spec(spec_repo, "Alpha")
    settings = harness_settings(spec_repo, mapping={"drafting": "Status"})

    with pytest.raises(github_projects.GitHubError) as raised:
        github_projects.sync_spec(path, settings)

    assert "settings.yaml" in str(raised.value)
    assert fake_board.issues == {}  # nothing was written


# --- reading the spec file (the doorbell is only a doorbell) ------------------------------


def test_read_spec_reads_the_file_not_the_payload(spec_repo):
    """The doorbell only names a spec; everything projected is read from the files.

    The status now arrives through the engine's own model — the real helper, spawned against
    this fixture install — rather than a second parse of the header the engine owns. Same
    principle, one restatement fewer: the file is still the truth, and the harness is no longer
    the one deciding how to read it."""
    import grillwork_cli

    path, sid = new_spec(spec_repo, "Alpha Feature")
    set_status(path, "verified")

    read = github_projects.read_spec(path, grillwork_cli.package(spec_repo, path)["status"])

    assert read.spec_id == sid
    assert read.status == "verified"
    assert "Alpha Feature" in read.title


# --- board enumeration + settings validation (`hook.py --check`) --------------------------


def test_check_lists_fields_and_validates_the_map(fake_board):
    fake_board.fields = {"Stage": ["Todo", "Done"], "Priority": ["P1"]}

    assert github_projects.single_select_fields("o", "2", "o/r") == [
        ("Stage", ["Todo", "Done"]),
        ("Priority", ["P1"]),
    ]

    # A field/option the board does not have is named, so `--check` can report it.
    with pytest.raises(github_projects.GitHubError) as raised:
        github_projects.validate_mapping("o", "2", "o/r", "Stage", {"drafting": "Icebox"})
    assert "Icebox" in str(raised.value)

    with pytest.raises(github_projects.GitHubError) as raised:
        github_projects.validate_mapping("o", "2", "o/r", "Missing", {"drafting": "Todo"})
    assert "Missing" in str(raised.value)

    # The matching field + options validate silently.
    github_projects.validate_mapping("o", "2", "o/r", "Stage", {"drafting": "Todo"})


def test_check_reports_an_unreachable_board(fake_board):
    fake_board.reachable = False

    with pytest.raises(github_projects.GitHubError):
        github_projects.single_select_fields("o", "2", "o/r")


# --- identity resolution ------------------------------------------------------------------


def _git_repo_with_origin(root: Path, url: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(root)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", url], capture_output=True, check=True)


def test_resolve_identity_from_url_and_remote(tmp_path):
    root = tmp_path / "r"
    _git_repo_with_origin(root, "https://github.com/acme/widgets.git")

    owner, number, repo = github_projects.resolve_identity(
        owner="", project_number="", repo="",
        project_url="https://github.com/users/acme/projects/2", root=root,
    )
    assert (owner, number, repo) == ("acme", "2", "acme/widgets")


def test_resolve_identity_explicit_overrides(tmp_path):
    root = tmp_path / "r"
    _git_repo_with_origin(root, "https://github.com/acme/widgets.git")

    owner, number, repo = github_projects.resolve_identity(
        owner="acme", project_number="9", repo="acme/thing",
        project_url="https://github.com/orgs/other/projects/3", root=root,
    )
    assert (owner, number, repo) == ("acme", "9", "acme/thing")


def test_resolve_identity_no_remote_leaves_defaults_empty(tmp_path):
    # No git origin to default from: owner/repo stay empty, explicit number is kept (no raise).
    owner, number, repo = github_projects.resolve_identity(
        owner="", project_number="5", repo="", project_url="", root=tmp_path,
    )
    assert owner == ""
    assert repo == ""
    assert number == "5"
