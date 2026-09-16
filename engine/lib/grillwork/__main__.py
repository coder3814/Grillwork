"""Entry point for `python .grillwork/engine/lib/grillwork <command>`.

Running a *directory* puts that directory on `sys.path` and executes this file as a top-level
module, so there is no package context and a relative import would fail. Adding the parent
makes `grillwork` importable as the package it is — which is what lets the invocation stay one
repo-relative path with nothing to install and nothing to resolve.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from grillwork.cli import main  # noqa: E402 — must follow the sys.path line above

if __name__ == "__main__":
    raise SystemExit(main())
