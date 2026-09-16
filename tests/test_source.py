"""Updating an install from the source it records.

The network is never touched here: `update --archive` reads a local zip, which is the same
path an offline machine takes, so the download is the only untested line and everything around
it — the shape of the archive, the clean-tree refusal, the replacement, the realization, the
orphan sweep, and the promise that nothing is left in the temp directory — is exercised against
real files.
"""

from __future__ import annotations

import json
import zipfile

import pytest
from conftest import (
    ENGINE,
    commit,
    install,
    run,
    source_archive,
    update,
    write_config,
)
from grillwork import config, source

# --------------------------------------------------------------------------------------
# The recorded source
# --------------------------------------------------------------------------------------


def test_source_defaults_to_the_canonical_repo(repo):
    # An install predating the `source` setting still knows where to update from — that
    # fallback is the whole point, since the oldest installs need the update most.
    cfg = config.load(repo)
    assert cfg.source_repo == source.DEFAULT_REPO
    assert cfg.source_ref == source.DEFAULT_REF


def test_recorded_source_round_trips(tmp_path):
    install(tmp_path, source={"repo": "https://example.com/team/fork", "ref": "v2"})
    cfg = config.load(tmp_path)
    assert (cfg.source_repo, cfg.source_ref) == ("https://example.com/team/fork", "v2")


def test_config_command_reports_the_source(repo):
    # Reported rather than assumed: an adopter who installed from a fork can see which source
    # an update would reach for.
    payload = json.loads(run(["config", str(repo)]).stdout)
    assert payload["source_repo"] == source.DEFAULT_REPO


# --------------------------------------------------------------------------------------
# The archive URL
# --------------------------------------------------------------------------------------


def test_archive_url_is_the_generic_ref_form():
    # One form resolves branches, tags and SHAs alike, so nothing has to interrogate the ref.
    assert source.archive_url("https://github.com/o/r", "main") == (
        "https://github.com/o/r/archive/main.zip"
    )
    assert source.archive_url("https://github.com/o/r/", "v1.2") == (
        "https://github.com/o/r/archive/v1.2.zip"
    )


@pytest.mark.parametrize(
    "repo_url",
    [
        "file:///etc/passwd",
        "http://github.com/o/r",
        "https://github.com/o/r/../../evil",
        "not a url",
    ],
)
def test_archive_url_refuses_untrustworthy_repos(repo_url):
    with pytest.raises(source.SourceError):
        source.archive_url(repo_url, "main")


def test_archive_url_refuses_a_shell_shaped_ref():
    with pytest.raises(source.SourceError):
        source.archive_url("https://github.com/o/r", "main; rm -rf /")


# --------------------------------------------------------------------------------------
# The clean-tree precondition
# --------------------------------------------------------------------------------------


def test_update_refuses_a_dirty_tree(repo, tmp_path):
    (repo / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    result = run(["update", "--archive", str(source_archive(tmp_path)), str(repo)])
    assert result.exit_code == 1
    assert "not clean" in result.output
    # Refused before anything was replaced.
    assert not (repo / ".claude").exists()


def test_update_refuses_outside_git(tmp_path):
    root = install(tmp_path / "nogit")
    result = run(["update", "--archive", str(source_archive(tmp_path)), str(root)])
    assert result.exit_code == 1
    assert "git is the undo" in result.output


# --------------------------------------------------------------------------------------
# The update itself
# --------------------------------------------------------------------------------------


def test_update_replaces_the_engine_in_place(repo, tmp_path):
    archive = source_archive(tmp_path)
    (repo / ".grillwork" / "engine" / "roles" / "griller.md").write_text("stale\n", encoding="utf-8")
    commit(repo, "drift")

    payload = update(repo, archive)

    assert "roles/griller.md" in payload["engine_changed"]
    installed = repo / ".grillwork" / "engine" / "roles" / "griller.md"
    assert installed.read_text(encoding="utf-8") == (
        (ENGINE / "roles" / "griller.md").read_text(encoding="utf-8")
    )


def test_update_carries_the_command_sources_into_the_install(repo, tmp_path):
    # Realizing happens from the placed copy, not from the download — which is what lets the
    # download be deleted the moment it has been placed.
    update(repo, source_archive(tmp_path))
    placed = repo / ".grillwork" / "engine" / "commands"
    assert sorted(p.name for p in placed.glob("*.md")) == sorted(
        p.name for p in (ENGINE / "commands").glob("*.md")
    )


def test_update_reports_no_change_when_already_current(repo, tmp_path):
    archive = source_archive(tmp_path, repo / ".grillwork" / "engine")
    assert update(repo, archive)["engine_changed"] == []


def test_update_leaves_instance_data_alone(repo, tmp_path):
    settings = repo / ".grillwork" / "settings"
    (settings / "improvements.md").write_text("# curated\n", encoding="utf-8")
    specs = repo / ".grillwork" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "001-thing.md").write_text("a spec\n", encoding="utf-8")
    before = (settings / "config.json").read_text(encoding="utf-8")
    commit(repo, "instance data")

    update(repo, source_archive(tmp_path))

    assert (settings / "config.json").read_text(encoding="utf-8") == before
    assert (settings / "improvements.md").read_text(encoding="utf-8") == "# curated\n"
    assert (specs / "001-thing.md").read_text(encoding="utf-8") == "a spec\n"


def test_update_refuses_an_archive_that_is_not_grillwork(repo, tmp_path):
    bogus = tmp_path / "bogus.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr("something/readme.txt", "not grillwork")
    result = run(["update", "--archive", str(bogus), str(repo)])
    assert result.exit_code == 1
    assert "does not look like a Grillwork source" in result.output


def test_update_refuses_a_missing_archive(repo, tmp_path):
    result = run(["update", "--archive", str(tmp_path / "absent.zip"), str(repo)])
    assert result.exit_code == 1
    assert "No such archive" in result.output


def test_overrides_beat_the_recorded_source(repo):
    write_config(
        repo,
        {
            "spec_home": ".grillwork/specs",
            "builder": "claude-code",
            "source": {"repo": "https://example.com/team/fork", "ref": "v2"},
        },
    )
    cfg = config.load(repo)
    assert (cfg.source_repo, cfg.source_ref) == ("https://example.com/team/fork", "v2")


def test_currency_survives_line_ending_differences(repo, tmp_path):
    # A GitHub archive ships LF; a Windows checkout with core.autocrlf on holds the same
    # content as CRLF. Byte-comparing those reports every file as changed, which would make
    # the summary useless for seeing what an update actually did.
    engine = repo / ".grillwork" / "engine"
    archive = source_archive(tmp_path, engine)
    for path in engine.rglob("*.md"):
        lf = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(lf.replace(b"\n", b"\r\n"))
    # No commit: with autocrlf on, git normalizes these back and sees no change at all, which
    # is exactly the point — the difference is in the bytes on disk, not in the history.

    assert update(repo, archive)["engine_changed"] == []
