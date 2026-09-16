"""The engine seam — everything this harness gets from Grillwork, and how it gets it.

A harness sits on the far side of the engine's boundary, and the boundary is the **repo**: the
payload is a doorbell, the files are the truth, and what the engine knows about those files it
prints. So this harness asks for engine content the same way the roles do — by running the
vendored helper and reading its JSON — rather than by importing it.

That is a deliberate reversal. This example used to `from grillwork.package import build_model`,
which worked in Grillwork's own repo and nowhere else: a copied harness has no import path to
the vendored package, and a harness written in PowerShell or Node could not have imported it at
any depth. The engine promises to name no vendor, tracker, cloud or repo layout; a Python import
at its edge quietly made Python the exception. Shelling out costs one process per call and
removes the exception.

Three things this harness needs and does not restate:

    package(root, spec)   the neutral acceptance-package model — the seven parts, the revision
                          pins, the evidence rows, the degenerate-content flags
    statuses(root)        the spec lifecycle, in order, so `status_map` can be checked whole
    repo_root(path)       the walk up to the directory holding `.grillwork/` — the one thing
                          that cannot be asked for, since finding the engine is what the walk
                          is for, so the contract states the rule instead

Every call is repo-relative from a `root` the caller supplies, so nothing here knows where the
harness was copied to. The walk lives here rather than in `hook.py` because it belongs to this
seam — it is how the seam is located — and because everything that needs it (the entry script,
the harness's own tests) can then have it without importing the board adapter.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# The vendored helper, repo-relative: an install writes it here and nowhere else.
_HELPER = Path(".grillwork") / "engine" / "lib" / "grillwork"


def repo_root(path) -> Path:
    """The repo root for a path: the nearest directory holding `.grillwork/`, starting with
    the path itself. Falls back to the path's parent, so a stray path still yields something
    rather than raising.

    The path itself is a candidate on purpose: `--check` is run from the repo root, and a
    directory is never among its own `parents`."""
    resolved = Path(path).resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".grillwork").is_dir():
            return candidate
    return resolved.parent


class EngineError(Exception):
    """The engine helper could not be run, failed, or did not print JSON."""


def call(root, *args: str) -> dict:
    """Run ``python .grillwork/engine/lib/grillwork <args>`` under ``root`` and parse its JSON.

    Run with this interpreter (``sys.executable``) rather than whatever ``python`` resolves to,
    so the hook and the helper cannot end up on different Pythons."""
    command = [sys.executable, str(Path(root) / _HELPER), *args]
    try:
        proc = subprocess.run(command, capture_output=True, text=True)
    except OSError as e:
        raise EngineError(f"could not run the Grillwork helper at {Path(root) / _HELPER}: {e}") from e
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip() or f"exit {proc.returncode}"
        raise EngineError(f"`grillwork {args[0]}` failed: {detail}")
    try:
        return json.loads(proc.stdout)
    except ValueError as e:
        raise EngineError(f"`grillwork {args[0]}` did not print JSON: {proc.stdout!r}") from e


def package(root, spec_path) -> dict:
    """The neutral acceptance-package model for a spec, as data. Rendering it is this harness's
    own job (see ``compose.py``); forming it is never."""
    return call(root, "package", str(spec_path))


def statuses(root) -> list[str]:
    """The spec lifecycle statuses, in order — the list a board needs one column per."""
    return list(call(root, "statuses")["statuses"])
