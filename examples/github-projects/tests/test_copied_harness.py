"""The harness as an adopter actually runs it: a **copy**, at a depth of its own choosing.

Every other test in this directory exercises the harness at whatever depth it was copied to,
which is the honest shape but not the whole of it: they still run it in place, as a module of
the suite's own process. In an adopter's tree the harness is a **copy**, spawned by the engine
from wherever the trigger ran, with nothing installed and no import path arranged for it. The
first external install hit exactly the two defects that gap hides — a repo-root walk that
could not match the repo root itself, and imports that resolved only under pytest.

So this test builds a throwaway adopter repo, copies the harness into it at an unrelated
depth, and runs it as a **subprocess** with a clean environment. Nothing pytest arranges for
the suite is available to it: if the copy cannot find the repo root or reach the engine on its
own, it fails here.

The import defect was since dissolved rather than fixed — the harness asks the engine for
what it needs (``grillwork_cli.py``) instead of importing it, so there is no longer a
``sys.path`` to get wrong. What replaces that check is the seam itself, driven from the copy:
a harness at an arbitrary depth must still be able to run the vendored helper.

That fix reached the runtime and stopped at the test layer, which the same install found
next: this file located the engine by counting parents from itself, so the test written to
catch copied-harness breakage was the one test that could not run from a copy. The engine it
vendors is now the one belonging to the install this suite is part of, found by the harness's
own walk — the rule that holds at every depth, including this one.

The board binding is environment-only (``GRILLWORK_GH_*``), which also means the run needs no
settings file and therefore no PyYAML — see ``test_settings_binding.py``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import grillwork_cli
from harness_engine import ENGINE

_TESTS_DIR = Path(__file__).resolve().parent
_EXAMPLE_DIR = _TESTS_DIR.parent
# The engine to vendor into the throwaway repo: the one from the install this suite is part of
# (`harness_engine` walks to it), never one found by counting parents.
_ENGINE_LIB = ENGINE / "lib" / "grillwork"


def _adopter_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A throwaway repo with the engine vendored and this harness copied into it, at a depth
    that has nothing to do with the depth it sits at here. Returns (root, copied harness dir).

    The git origin is a real (unreachable, never contacted) github remote: it is how the test
    observes which repo the harness decided it was in. Resolve the wrong root and the harness
    finds no origin — or, worse, Grillwork's own — and the assertion below fails.
    """
    root = tmp_path / "adopter"
    harness = root / "tools" / "integrations" / "board-sync"
    harness.mkdir(parents=True)

    shutil.copytree(_ENGINE_LIB, root / ".grillwork" / "engine" / "lib" / "grillwork")
    for module in sorted(_EXAMPLE_DIR.glob("*.py")):
        shutil.copy(module, harness / module.name)

    spec_dir = root / ".grillwork" / "specs" / "001-a-first-spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        "# 001 — a first spec\n\n"
        "| | |\n|---|---|\n"
        "| **ID** | 001-a-first-spec |\n"
        "| **Status** | drafting |\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/acme/widgets.git"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return root, harness


def _clean_env(**overrides: str) -> dict[str, str]:
    """This suite's own run leaks two things a copied harness must not need: ``PYTHONPATH``
    (pytest's import path) and any ``GRILLWORK_*`` binding. Both are stripped."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH" and not k.startswith("GRILLWORK_")}
    env.update(overrides)
    return env


def _run(harness: Path, *args: str, cwd: Path, **overrides: str) -> subprocess.CompletedProcess:
    """Run the copied ``hook.py`` with a clean environment plus the given payload."""
    return subprocess.run(
        [sys.executable, str(harness / "hook.py"), *args],
        cwd=cwd,
        env=_clean_env(**overrides),
        capture_output=True,
        text=True,
    )


def _run_python(source: str, *, cwd: Path) -> subprocess.CompletedProcess:
    """Run a snippet against the copied harness, with the same clean environment."""
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=cwd,
        env=_clean_env(),
        capture_output=True,
        text=True,
    )


def test_a_copied_harness_finds_its_repo(tmp_path):
    """A transition fired at a copy: it loads, walks from the spec path up to the adopter's repo
    root, and defaults its board identity from that repo's origin. Run from an unrelated working
    directory, so nothing may lean on the cwd."""
    root, harness = _adopter_repo(tmp_path)
    spec_path = root / ".grillwork" / "specs" / "001-a-first-spec" / "spec.md"

    result = _run(
        harness,
        cwd=tmp_path,
        GRILLWORK_EVENT="on-transition",
        GRILLWORK_SPEC_PATH=str(spec_path),
        GRILLWORK_OLD_STATUS="approved",
        GRILLWORK_NEW_STATUS="building",
        GRILLWORK_DRY_RUN="1",
        GRILLWORK_GH_PROJECT_NUMBER="7",
    )

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    # The identity in the report is the proof: `acme/widgets` can only have come from the
    # adopter repo's origin, which only a correct root walk reaches.
    assert "acme/widgets project #7" in result.stdout


def test_a_copied_harness_can_reach_the_engine(tmp_path):
    """The seam, from a copy. The harness runs the vendored helper rather than importing it, so
    what has to work at an arbitrary depth is the *invocation*: the root walk, the repo-relative
    path to the helper, and the JSON coming back. Driven through the harness's own module, in a
    subprocess with no `PYTHONPATH`, exactly as the hook would."""
    root, harness = _adopter_repo(tmp_path)
    spec_path = root / ".grillwork" / "specs" / "001-a-first-spec" / "spec.md"

    result = _run_python(
        f"import sys; sys.path.insert(0, {str(harness)!r});"
        " import grillwork_cli;"
        f" print(grillwork_cli.package({str(root)!r}, {str(spec_path)!r})['status']);"
        f" print(len(grillwork_cli.statuses({str(root)!r})))",
        cwd=tmp_path,
    )

    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    status, count = result.stdout.split()
    assert status == "drafting"
    assert int(count) >= 7


def test_no_test_here_imports_conftest_by_name(tmp_path):
    """``conftest`` is not a name a copy can rely on, so nothing here may import it.

    An adopter who copies two Grillwork examples has two ``tests/conftest.py`` on
    ``sys.path``; a bare ``from conftest import ...`` then resolves to whichever one got there
    first, and one ``pytest`` run over both directories fails at collection with an
    ``ImportError`` naming symbols that do exist — in the other example. Shared helpers live in
    ``harness_engine.py``, whose name is its own.

    Structural rather than behavioral on purpose: reproducing it takes a second copied example
    and a nested pytest run, and no test of this harness's behavior can see it."""
    offenders = [
        path.name
        for path in sorted(_TESTS_DIR.glob("*.py"))
        if re.search(r"^\s*(from conftest import|import conftest)", path.read_text(encoding="utf-8"),
                     re.MULTILINE)
    ]
    assert not offenders, f"these import the ambiguous module name `conftest`: {offenders}"


def test_repo_root_matches_the_root_itself(tmp_path):
    """The walk, as a unit: the directory holding ``.grillwork/`` is its own answer, and so is
    the answer for anything beneath it.

    The root *itself* is the case that broke. ``--check`` takes no spec path and so walks from
    the working directory, which the README tells the adopter to make the repo root — and a
    directory is never among its own ``parents``. The walk ran past the repo, the board
    identity lost its origin default, and the adopter was told their settings were unbound.
    (The enumeration and map validation ``--check`` then performs are covered against the fake
    board in ``test_github_adapter.py``; what could only fail here is the walk.)"""
    root = tmp_path / "adopter"
    (root / ".grillwork" / "specs").mkdir(parents=True)

    assert grillwork_cli.repo_root(root) == root
    assert grillwork_cli.repo_root(root / ".grillwork" / "specs") == root


def test_repo_root_falls_back_rather_than_raising(tmp_path):
    """A path outside any Grillwork repo still yields something — the loader downstream is what
    reports an unbound board, not a traceback out of the walk."""
    stray = tmp_path / "nowhere" / "spec.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("", encoding="utf-8")

    assert grillwork_cli.repo_root(stray) == stray.parent
