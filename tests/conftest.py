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
from dataclasses import dataclass
from pathlib import Path

import pytest
from grillwork import cli


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
