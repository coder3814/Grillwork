"""Test infrastructure for the publish-evidence example.

The example is a single script sitting one directory up (a harness, not an installed package),
so the path line below puts it on ``sys.path`` — that is all a plain ``uv run pytest`` needs to
collect and run these, here or from a copy.

The fixtures build a **real install shape**: the engine's deterministic helper vendored at
`.grillwork/engine/lib/grillwork`, because the harness asks the engine which files in a bundle
are artifacts rather than deciding for itself. That call is a real subprocess in these tests —
no stub — so the seam is exercised rather than described.

The helper they vendor is the one belonging to **the install this directory was copied into**,
found with the harness's own walk (``publish.repo_root``). Counting parents to Grillwork's own
`engine/` would land somewhere real at exactly one depth — the depth nobody who copies this
directory will ever run it at.

The one exception is that depth itself: Grillwork's own repo authors this example and is
deliberately **not** an adopter of itself, so no install sits above these tests there. The
fallback below reaches the authored source instead, anchored on the `INSTALL.md` that only ever
sits beside an engine being authored — never in a repo that merely installed one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

_EXAMPLE_DIR = Path(__file__).resolve().parents[1]

if str(_EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLE_DIR))

import publish  # noqa: E402 — after the sys.path line above, by design

_TESTS_DIR = Path(__file__).resolve().parent
_ENGINE_LIB = publish.repo_root(__file__) / ".grillwork" / "engine" / "lib" / "grillwork"

if not _ENGINE_LIB.is_dir():
    # No install above us — either Grillwork's own repo (see the module docstring), or a copy
    # somewhere Grillwork was never installed.
    _ENGINE_LIB = next(
        (
            parent / "engine" / "lib" / "grillwork"
            for parent in (_TESTS_DIR, *_TESTS_DIR.parents)
            if (parent / "engine" / "lib" / "grillwork").is_dir()
            and (parent / "INSTALL.md").is_file()
        ),
        _ENGINE_LIB,
    )

if not _ENGINE_LIB.is_dir():
    raise RuntimeError(
        f"no Grillwork engine at {_ENGINE_LIB} — these tests vendor the engine from the install "
        f"this harness was copied into, and there is none above {_TESTS_DIR}. "
        "Install Grillwork in this repo (see the engine repo's INSTALL.md) and run them again."
    )


def vendor_engine(root: Path) -> Path:
    """Put the engine's helper where an install puts it, and return ``root``."""
    shutil.copytree(_ENGINE_LIB, root / ".grillwork" / "engine" / "lib" / "grillwork")
    return root


@pytest.fixture
def adopter_repo(tmp_path):
    """A repo with Grillwork installed and nothing else — the floor every fixture builds on."""
    return vendor_engine(tmp_path / "repo")


@pytest.fixture
def bundle(adopter_repo):
    """One spec with an evidence bundle: three artifacts and all three account files. Returns
    the spec path.

    The account files are present on purpose — the selection rule is the thing most easily got
    wrong, and publishing `manifest.json` would put the engine's own record where the artifact
    URLs go."""
    spec_dir = adopter_repo / ".grillwork" / "specs" / "007-a-spec"
    evidence = spec_dir / "evidence"
    evidence.mkdir(parents=True)

    spec = spec_dir / "spec.md"
    spec.write_text("# 007 — a spec\n", encoding="utf-8")

    for name in ("C-001-suite.log", "C-002-manual.log", "screenshot.png"):
        (evidence / name).write_text(f"contents of {name}\n", encoding="utf-8")
    (evidence / "bundle.md").write_text("## Verdict\nDONE\n", encoding="utf-8")
    (evidence / "manifest.json").write_text('{"artifacts": []}\n', encoding="utf-8")
    (evidence / ".gitignore").write_text("*\n", encoding="utf-8")

    return spec
