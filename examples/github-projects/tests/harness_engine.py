"""Where these tests get engine content: from the install this harness was copied into.

This directory is copied into an adopter's repo and owned there, so its tests run at a depth
nobody here can predict, with nothing installed and no packaging of their own. Two ways of
reaching the engine look fine in Grillwork's own repo and work nowhere else:

- **importing the vendored ``grillwork`` package**, which resolves only where an import path
  happens to be arranged for it (Grillwork's ``pyproject.toml`` arranges one, which is how
  this suite came to pass there and only there);
- **counting parents** up to ``<repo>/engine``, which lands somewhere real at exactly one
  depth — the depth nobody who copies this directory will ever run it at.

So these tests do what the harness does: walk up to the install (``grillwork_cli.repo_root``)
and run its vendored helper (``grillwork_cli.call``). Engine content is asked for, never
imported, and the answer is the engine the adopter actually has.

There is one other place this directory legitimately runs: Grillwork's own repo, which authors
it and is deliberately **not** an adopter of itself, so there is no install above to walk to.
There the engine is the source at ``<repo>/engine``, and the branch below stages a copy of it
into an install shape so that everything past it — ``grillwork_cli.call`` included, which
resolves the helper at ``.grillwork/engine/lib/grillwork`` exactly as it does in production —
still runs against a real install rather than against a special case. An adopter never reaches
that branch: their install is found first, and ``INSTALL.md`` sits only beside an engine that
is being authored.

This is a module of its own rather than more of ``conftest.py`` because a test module has to
import these by name, and ``conftest`` is not a name a copy can rely on: an adopter who copies
two Grillwork examples has two ``tests/conftest.py``, and a bare ``from conftest import ...``
then resolves to whichever one reached ``sys.path`` first.
"""

from __future__ import annotations

import atexit
import shutil
import sys
import tempfile
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_EXAMPLE_DIR = _TESTS_DIR.parent

# The harness's own modules sit one directory up (they are a harness, not an installed
# package). Importing this module is what puts them within reach — of the conftest, and of
# every test that drives `hook`, `compose` or `settings`.
if str(_EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLE_DIR))

import grillwork_cli  # noqa: E402 — after the sys.path line above, by design

#: The Grillwork install these tests are part of, found by walking up from this file — the
#: same walk the hook does from a spec path, and the one thing a copy cannot ask the engine for.
INSTALL_ROOT = grillwork_cli.repo_root(__file__)

#: The installed method, which fixtures copy to build throwaway repos of their own.
ENGINE = INSTALL_ROOT / ".grillwork" / "engine"

if not (ENGINE / "lib" / "grillwork").is_dir():
    # No install above us. Either this is Grillwork's own repo (see the module docstring), or
    # the harness was copied somewhere Grillwork was never installed.
    _authored = next(
        (
            parent / "engine"
            for parent in (_TESTS_DIR, *_TESTS_DIR.parents)
            if (parent / "engine" / "lib" / "grillwork").is_dir()
            and (parent / "INSTALL.md").is_file()
        ),
        None,
    )
    if _authored is None:
        raise RuntimeError(
            f"no Grillwork engine at {ENGINE} — these tests run against the install this harness "
            f"was copied into, and there is none above {_TESTS_DIR}. Install Grillwork in this "
            "repo (see the engine repo's INSTALL.md) and run them again."
        )
    INSTALL_ROOT = Path(tempfile.mkdtemp(prefix="grillwork-authored-engine-"))
    atexit.register(shutil.rmtree, INSTALL_ROOT, ignore_errors=True)
    ENGINE = INSTALL_ROOT / ".grillwork" / "engine"
    shutil.copytree(_authored, ENGINE, ignore=shutil.ignore_patterns("__pycache__"))


def engine(*args: str) -> dict:
    """Run the installed helper and return its JSON — the tests' half of the same seam
    ``grillwork_cli`` is for the harness."""
    return grillwork_cli.call(INSTALL_ROOT, *args)


#: The lifecycle, from the engine rather than from a list kept here in parallel with it.
SPEC_STATUSES = tuple(engine("statuses")["statuses"])

# The board the harness's own settings.example.yaml describes, used by the tests that are not
# about a particular board shape: one "Status" field carrying the seven lifecycle names, mapped
# stage-for-stage onto itself (the identity map).
IDENTITY_FIELD = "Status"
IDENTITY_MAP = {status: status for status in SPEC_STATUSES}


def new_spec(root, title):
    """A new spec in ``root``, made by the engine's own `new-spec`. Returns
    ``(spec_path, spec_id)``.

    Any hook the fixture repo binds fires from here, as it would for any other caller — these
    fixtures bind none, so nothing is spawned."""
    created = engine("new-spec", "--title", title, str(root))
    return Path(created["path"]), created["id"]


def set_status(spec_path, status):
    """Move a spec to a status through the engine's own write path — the state the harness
    will read back."""
    engine("spec-status", str(spec_path), "--set", status)
