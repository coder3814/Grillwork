#!/usr/bin/env python
"""The worked example of a `publish-evidence` hook — the awaited one.

Bound in `.grillwork/settings/config.json` at whatever path you copied this directory to —
`<publisher>` is the one thing you substitute, e.g. `tools/publish-evidence`:

    "hooks": {
      "publish-evidence": [["python", "<publisher>/publish.py"]]
    }

`publish-evidence` is unlike every other event in the contract: the engine **waits** for it,
its exit code decides whether a publish success is recorded, and its stdout is parsed. That
makes it the one hook with a protocol to get right, so this example exists to be read rather
than to be useful — it "publishes" by copying the artifacts into a directory on this machine
and printing `file://` URLs. Replace the copy with your object store, artifact server, or
wherever evidence should outlive the repo; everything around it is the part worth keeping.

The five things a publisher must get right, all of them visible below:

1. **Answer `GRILLWORK_DRY_RUN` first, and never fail it.** `grillwork fire-hooks
   publish-evidence` sets it to prove the wiring, and the payload it sets it with is
   *synthetic* — the spec path it names deliberately does not exist, because a hook has to
   tolerate a vanished path anyway. So the dry run is answered **before** anything requires
   the files: it reports what it can, publishes nothing, prints no URL, and exits 0. A
   publisher that runs its real checks first fails its own rehearsal on invented input —
   silently, since the engine spawns the rehearsal detached and never reads the exit code —
   and teaches its adopter that a red dry run is normal.
2. **Keep stdout pure protocol.** Only `<artifact-name> <url>` lines go to stdout — the
   engine records those URLs beside the artifact hashes. Everything else is stderr. (A
   wrapper around a chatty uploader has to silence or redirect it.)
3. **Ask the engine which files are artifacts.** Which files in a spec's `evidence/` directory
   are artifact bytes and which are the textual account is the engine's rule, not yours:
   `grillwork evidence-artifacts <spec>` prints it. A publisher that restates the rule either
   drops artifacts or overwrites the record the engine is about to write URLs into.
4. **Derive the repo root from the spec path**, not from the working directory: the hook
   fires from wherever the `verified` flip ran, which is the build's worktree.
5. **Mean it by the exit code.** Success is exit 0 and nothing else; a partial publish must
   exit nonzero, because a recorded success is what later permits the artifact bytes to be
   pruned. When in doubt, fail — a failed publish never blocks `verified` or the acceptance,
   it only keeps the bytes.

Everything here is the standard library alone.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PUBLISH_EVENT = "publish-evidence"

# The vendored helper, repo-relative: an install writes it here and nowhere else.
HELPER = Path(".grillwork") / "engine" / "lib" / "grillwork"

# Where this example "publishes" to. A real publisher points somewhere that outlives the repo;
# this one writes inside it, so the destination should be in your `.gitignore`.
DEFAULT_DESTINATION = Path(".grillwork") / "published"


def repo_root(path) -> Path:
    """The repo root for a path: the nearest directory holding `.grillwork/`, starting with the
    path itself. Falls back to the path's parent, so a stray path still yields something rather
    than raising."""
    resolved = Path(path).resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".grillwork").is_dir():
            return candidate
    return resolved.parent


class EngineError(Exception):
    """The engine helper could not be run, failed, or did not print JSON."""


def artifacts(root: Path, spec_path: Path) -> tuple[Path, list[Path]]:
    """The bundle directory and the files to publish out of it, straight from the engine —
    ``(evidence_dir, artifact_paths)``.

    Run with this interpreter (``sys.executable``) rather than whatever ``python`` resolves to,
    so the hook and the helper cannot end up on different Pythons."""
    command = [sys.executable, str(Path(root) / HELPER), "evidence-artifacts", str(spec_path)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True)
    except OSError as e:
        raise EngineError(f"could not run the Grillwork helper at {Path(root) / HELPER}: {e}") from e
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip() or f"exit {proc.returncode}"
        raise EngineError(f"`grillwork evidence-artifacts` failed: {detail}")
    try:
        listed = json.loads(proc.stdout)
    except ValueError as e:
        raise EngineError(f"`grillwork evidence-artifacts` did not print JSON: {proc.stdout!r}") from e
    evidence_dir = Path(listed["dir"])
    return evidence_dir, [evidence_dir / name for name in listed["artifacts"]]


def destination_for(root: Path, spec: Path, env: dict[str, str]) -> Path:
    """Where this run would publish to: the configured directory, or one inside the repo,
    with a subdirectory per spec."""
    configured = env.get("GRILLWORK_PUBLISH_DIR", "")
    return (Path(configured) if configured else root / DEFAULT_DESTINATION) / spec.parent.name


def dry_run(spec_path: str, env: dict[str, str]) -> int:
    """The engine's rehearsal (`fire-hooks publish-evidence`), which **always succeeds**.

    Its payload is invented, down to a spec path that does not exist — so nothing read through
    it could be evidence of a defect, and every check the real path makes would be a check
    against fiction. What a rehearsal proves is the wiring: this command is bound, it starts,
    it recognizes the flag, and it publishes nothing. It reports whatever it *can* see, on
    stderr, and leaves stdout empty — a dry run has no URLs to claim.

    Run by hand against a real spec path, the same branch reports the actual plan; that is the
    useful thing to do with it, and it still exits 0."""
    if not spec_path:
        print(
            "publish-local: dry run — the payload carried no GRILLWORK_SPEC_PATH; nothing "
            "read, nothing published.",
            file=sys.stderr,
        )
        return 0

    spec = Path(spec_path)
    root = repo_root(spec)
    destination = destination_for(root, spec, env)
    if not spec.exists():
        print(
            f"publish-local: dry run — no spec at {spec}, which is expected of a rehearsal's "
            f"synthetic payload; a real publish would write to {destination}.",
            file=sys.stderr,
        )
        return 0
    try:
        evidence_dir, found = artifacts(root, spec)
    except EngineError as e:
        print(f"publish-local: dry run — {e}", file=sys.stderr)
        return 0

    names = ", ".join(path.name for path in found) or "no artifacts"
    print(
        f"publish-local: dry run — would publish {names} from {evidence_dir} to {destination}.",
        file=sys.stderr,
    )
    return 0


def main(env: dict[str, str] | None = None) -> int:
    env = dict(os.environ if env is None else env)

    # Bound to the wrong event, this is nobody's business but its own: a no-op success.
    if env.get("GRILLWORK_EVENT", PUBLISH_EVENT) != PUBLISH_EVENT:
        return 0

    spec_path = env.get("GRILLWORK_SPEC_PATH", "")

    # Before every check below: the rehearsal is answered on the payload alone, because the
    # payload is all a rehearsal has (see `dry_run`).
    if env.get("GRILLWORK_DRY_RUN"):
        return dry_run(spec_path, env)

    if not spec_path:
        print(f"publish-local: {PUBLISH_EVENT} carried no GRILLWORK_SPEC_PATH.", file=sys.stderr)
        return 1
    spec = Path(spec_path)
    if not spec.exists():
        print(f"publish-local: no spec at {spec}.", file=sys.stderr)
        return 1

    root = repo_root(spec)
    try:
        _, found = artifacts(root, spec)
    except EngineError as e:
        print(f"publish-local: {e}", file=sys.stderr)
        return 1

    destination = destination_for(root, spec, env)

    # A publisher that wraps a third-party uploader often has to stage a copy first: some
    # uploaders write their own bookkeeping (a `manifest.json` of their own, checksums) into
    # the directory they are pointed at, which would overwrite the bundle's account files.
    # Copying out, as here, is the general defense — never hand a tool the evidence directory.
    try:
        destination.mkdir(parents=True, exist_ok=True)
        published = [(path.name, shutil.copy2(path, destination / path.name)) for path in found]
    except OSError as e:
        # Partial or total, this is a failed publish: exit nonzero so no success is recorded
        # and the artifact bytes stay put.
        print(f"publish-local: {e}", file=sys.stderr)
        return 1

    for name, written in published:
        print(f"{name} {Path(written).resolve().as_uri()}")
    print(
        f"publish-local: published {len(published)} artifact(s) to {destination}.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
