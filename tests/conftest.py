"""Shared test fixtures.

Installation is a prompt an agent follows (INSTALL.md), not a command this code exposes — so
the suite can no longer build a fixture repo by calling `overlay.init`. `install()` below
writes the same shape the prompt describes: the method under `.grillwork/engine/`, the
settings under `.grillwork/settings/config.json`. It is deliberately the *minimum* the
deterministic helper reads, not a full install: the compiled command files are the agent's
half of the job and no Python here touches them.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from grillwork import cli, realize


@dataclass(frozen=True)
class Result:
    """One CLI invocation's outcome. ``stdout`` is the JSON channel a role parses; ``output``
    is both streams together, for asserting on human-facing error text."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


def run(argv: list[str]) -> Result:
    """Invoke the CLI in-process with ``argv``, capturing both streams."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(argv)
        except SystemExit as e:  # argparse's own exits (bad usage, --help)
            code = e.code if isinstance(e.code, int) else 1
    return Result(exit_code=code, stdout=out.getvalue(), stderr=err.getvalue())

# The engine as this repo authors it — the source the install prompt copies from.
ENGINE = Path(__file__).resolve().parent.parent / "engine"

# What the install prompt writes when the adopter accepts every default: the two required
# keys, and the two optional bindings present but empty — an adopter fills them in, and an
# empty string is how "not bound yet" reads.
DEFAULT_CONFIG = {
    "spec_home": ".grillwork/specs",
    "builder": "claude-code",
    "gate": "",
    "integration_target": "",
}


def method_text(*parts: str) -> str:
    """Read a method file by its path parts, e.g. method_text('roles', 'griller.md')."""
    return ENGINE.joinpath(*parts).read_text(encoding="utf-8")


def install(root: Path, **settings) -> Path:
    """Install Grillwork into ``root`` the way the prompt does; return ``root``.

    Keyword settings override the defaults (``spec_home``, ``builder``, ``gate``,
    ``integration_target``) and may add sections (``hooks``, ``evidence``). A value of None
    removes that key, so a test can build a deliberately incomplete config.
    """
    root = Path(root)
    engine = root / ".grillwork" / "engine"
    engine.mkdir(parents=True, exist_ok=True)
    for name in ("roles", "definitions"):
        shutil.copytree(ENGINE / name, engine / name, dirs_exist_ok=True)
    for name in ("spec-template.md", "harness-guide.md", "hooks-contract.md"):
        shutil.copy2(ENGINE / name, engine / name)

    config = {**DEFAULT_CONFIG, **settings}
    config = {k: v for k, v in config.items() if v is not None}
    write_config(root, config)
    return root


def write_config(root: Path, config: dict) -> Path:
    """Write ``config`` as the repo's settings, creating the directory. Returns the path."""
    path = Path(root) / ".grillwork" / "settings" / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def installed(tmp_path: Path) -> Path:
    """A tmp repo with Grillwork installed at its defaults."""
    return install(tmp_path)


# --------------------------------------------------------------------------------------
# Updating an install. Shared because the realization tests and the fetch tests drive the
# same command from opposite ends.
# --------------------------------------------------------------------------------------

# The profile a Claude Code install writes. Nothing in the engine knows these values; they are
# the adopter's record of how their own install realized the commands.
CLAUDE_PROFILE = {
    "format": "yaml-frontmatter",
    "argument_placeholder": "$ARGUMENTS",
    "banner": "<!-- {text} -->",
    "extension": ".md",
    "targets": {"command": ".claude/commands", "subagent": ".claude/agents"},
}


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def commit(root: Path, message: str = "install") -> None:
    git(root, "add", "-A")
    subprocess.run(
        [
            "git", "-C", str(root),
            "-c", "user.email=test@example.com",
            "-c", "user.name=Test",
            "commit", "-qm", message,
        ],
        check=True,
        capture_output=True,
    )


def source_archive(
    tmp_path: Path, engine_src: Path | None = None, wrapper: str = "Grillwork-main"
) -> Path:
    """Build a zip shaped like a GitHub source archive: one wrapper directory holding the
    engine and the install prompt.

    ``engine_src`` defaults to this repo's own ``engine/`` — the real thing, commands and all,
    so the realization is exercised against the files an adopter actually receives.
    """
    engine_src = ENGINE if engine_src is None else engine_src
    staging = tmp_path / "archive-src" / wrapper
    shutil.copytree(engine_src, staging / "engine", ignore=shutil.ignore_patterns("__pycache__"))
    (staging / "INSTALL.md").write_text("# Install Grillwork\n", encoding="utf-8")
    zip_path = tmp_path / "source.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in staging.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(staging.parent).as_posix())
    return zip_path


def update(root: Path, archive: Path) -> dict:
    """Run the update and return its JSON, asserting it succeeded."""
    result = run(["update", "--archive", str(archive), str(root)])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


@pytest.fixture(autouse=True)
def no_staging_left_behind():
    """An update must leave nothing in the temp directory, on success or failure alike — the
    whole reason the download is deleted in a `finally`. Asserted around every test rather than
    in one, so no future path can quietly start leaking."""
    before = set(Path(tempfile.gettempdir()).glob("grillwork-update-*"))
    yield
    leaked = set(Path(tempfile.gettempdir()).glob("grillwork-update-*")) - before
    assert not leaked, f"staging left behind: {sorted(leaked)}"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An installed, committed repo with a realization profile — the ordinary starting state
    of an update."""
    root = install(tmp_path / "repo")
    (root / ".grillwork" / "settings" / realize.PROFILE_FILENAME).write_text(
        json.dumps(CLAUDE_PROFILE, indent=2) + "\n", encoding="utf-8"
    )
    git(root, "init", "-q")
    commit(root)
    return root
