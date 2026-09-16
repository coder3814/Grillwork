"""Fetching and staging the engine an update is updating to.

The network is never touched here: `fetch-engine --archive` reads a local zip, which is the
same path an offline adopter takes, so the download is the only untested line and every check
around it — the shape of the archive, the clean-tree refusal, the currency comparison — is
exercised against real files.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest
from conftest import ENGINE, install, run, write_config
from grillwork import config, source


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _commit_all(root: Path) -> None:
    """Make ``root`` a git repo with a clean tree — the state an update requires."""
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "install")


def _archive(tmp_path: Path, engine_src: Path | None = None, wrapper: str = "Grillwork-main") -> Path:
    """Build a zip shaped like a GitHub source archive: one wrapper directory holding the
    engine and the install prompt.

    ``engine_src`` defaults to this repo's own ``engine/``. The currency tests pass the
    *installed* engine instead, because the test fixture installs only the subset the helper
    reads — a difference of the fixture's making, not the kind of drift being asserted on.
    """
    engine_src = ENGINE if engine_src is None else engine_src
    staging = tmp_path / "archive-src" / wrapper
    shutil.copytree(engine_src, staging / "engine")
    (staging / "INSTALL.md").write_text("# Install Grillwork\n", encoding="utf-8")
    zip_path = tmp_path / "source.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in staging.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(staging.parent).as_posix())
    return zip_path


@pytest.fixture(autouse=True)
def _sweep_staging():
    """Staging deliberately outlives the fetch — the update copies from it — so the test suite
    sweeps what it created rather than leaving a temp directory per assertion."""
    before = set(Path(tempfile.gettempdir()).glob("grillwork-update-*"))
    yield
    for leftover in set(Path(tempfile.gettempdir()).glob("grillwork-update-*")) - before:
        shutil.rmtree(leftover, ignore_errors=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An installed, committed repo — the starting state of every update."""
    root = install(tmp_path / "repo")
    _commit_all(root)
    return root


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
    result = run(["config", str(repo)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["source_repo"] == source.DEFAULT_REPO


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


def test_fetch_refuses_a_dirty_tree(repo, tmp_path):
    (repo / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    result = run(["fetch-engine", "--archive", str(_archive(tmp_path)), str(repo)])
    assert result.exit_code == 1
    assert "not clean" in result.output


def test_fetch_refuses_outside_git(tmp_path):
    root = install(tmp_path / "nogit")
    result = run(["fetch-engine", "--archive", str(_archive(tmp_path)), str(root)])
    assert result.exit_code == 1
    assert "git is the undo" in result.output


# --------------------------------------------------------------------------------------
# Staging
# --------------------------------------------------------------------------------------


def test_fetch_stages_the_source_outside_the_repo(repo, tmp_path):
    result = run(["fetch-engine", "--archive", str(_archive(tmp_path)), str(repo)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)

    staged = Path(payload["staged"])
    assert Path(payload["engine"]).is_dir()
    assert Path(payload["install_doc"]).is_file()
    # `staged` is the whole of what was created, so naming it is enough to clean up after.
    assert Path(payload["source"]).is_relative_to(staged)
    # Outside the repo, so a staged update can never be committed by accident.
    assert repo not in staged.parents and staged != repo
    # Nothing under .grillwork/ was touched: staging is all this command does.
    assert not (repo / ".grillwork" / "engine" / "commands").exists()


def test_fetch_reports_current_when_the_engine_matches(repo, tmp_path):
    # An archive byte-identical to what is installed: there is nothing for an update to do.
    archive = _archive(tmp_path, repo / ".grillwork" / "engine")
    result = run(["fetch-engine", "--archive", str(archive), str(repo)])
    payload = json.loads(result.stdout)
    assert payload["current"] is True
    assert payload["differing"] == []


def test_fetch_reports_what_differs(repo, tmp_path):
    (repo / ".grillwork" / "engine" / "roles" / "griller.md").write_text("stale\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "drift")
    result = run(["fetch-engine", "--archive", str(_archive(tmp_path)), str(repo)])
    payload = json.loads(result.stdout)
    assert payload["current"] is False
    assert "roles/griller.md" in payload["differing"]


def test_currency_ignores_realized_commands_and_bytecode(repo, tmp_path):
    # `commands/` is realized into the harness's layout rather than copied, and bytecode was
    # never installed — neither is drift, and reporting them would make every repo look stale.
    engine = repo / ".grillwork" / "engine"
    archive = _archive(tmp_path, engine)
    (engine / "commands").mkdir()
    (engine / "commands" / "grillwork-specify.md").write_text("realized\n", encoding="utf-8")
    (engine / "roles" / "__pycache__").mkdir()
    (engine / "roles" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "realized")

    payload = json.loads(run(["fetch-engine", "--archive", str(archive), str(repo)]).stdout)
    assert payload["current"] is True


def test_fetch_refuses_an_archive_that_is_not_grillwork(repo, tmp_path):
    bogus = tmp_path / "bogus.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr("something/readme.txt", "not grillwork")
    result = run(["fetch-engine", "--archive", str(bogus), str(repo)])
    assert result.exit_code == 1
    assert "does not look like a Grillwork source" in result.output


def test_fetch_refuses_a_missing_archive(repo, tmp_path):
    result = run(["fetch-engine", "--archive", str(tmp_path / "absent.zip"), str(repo)])
    assert result.exit_code == 1
    assert "No such archive" in result.output


def test_overrides_beat_the_recorded_source(repo, tmp_path):
    # `--ref` without `--archive` would download; assert the resolution instead, which is what
    # the override exists to change.
    write_config(
        repo,
        {
            "spec_home": ".grillwork/specs",
            "builder": "claude-code",
            "source": {"repo": "https://example.com/team/fork", "ref": "v2"},
        },
    )
    _git(repo, "commit", "-qam", "source")
    payload = json.loads(run(["fetch-engine", "--archive", str(_archive(tmp_path)), str(repo)]).stdout)
    assert (payload["repo"], payload["ref"]) == ("https://example.com/team/fork", "v2")


def test_currency_survives_line_ending_differences(repo, tmp_path):
    # A GitHub archive ships LF; a Windows checkout with core.autocrlf on holds the same
    # content as CRLF. Byte-comparing those calls every file drift and the "already current,
    # stop" answer never fires — so the comparison normalizes, as git does.
    engine = repo / ".grillwork" / "engine"
    archive = _archive(tmp_path, engine)
    for path in engine.rglob("*.md"):
        lf = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(lf.replace(b"\n", b"\r\n"))
    # No commit: with autocrlf on, git normalizes these back and sees no change at all,
    # which is exactly the point — the drift is in the bytes on disk, not in the history.

    payload = json.loads(run(["fetch-engine", "--archive", str(archive), str(repo)]).stdout)
    assert payload["current"] is True
