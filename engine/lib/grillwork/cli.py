"""Grillwork CLI entry point.

Every command prints JSON on stdout and nothing else, so a role can parse it. Human-facing
notes — warnings, hook reports — go to stderr, which keeps stdout parseable even on a bad day.

Written against the standard library alone (argparse, json): this package is *vendored* into
the adopter's repository by the install prompt and run in place as
``python .grillwork/engine/lib/grillwork <command>``, so it can carry no dependency an adopter would
have to install.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path

from . import config, evidence, hooks, naming, package, spec

# Every error kind a command can expect to hit: a bad/absent config, the filesystem, and the
# domain's own rejections (`naming.set_status` raises ValueError on an unknown status). One
# tuple, so every command fails the same way and a new command gets the treatment by using
# `_clean_exit` rather than by remembering to.
_EXPECTED_ERRORS = (
    config.ConfigError,
    FileNotFoundError,
    FileExistsError,
    ValueError,
)


class _Exit(Exception):
    """A command's own nonzero exit, distinct from an unexpected crash."""

    def __init__(self, code: int = 1) -> None:
        super().__init__(code)
        self.code = code


@contextmanager
def _clean_exit():
    """Turn the expected error kinds into a one-line message on stderr and exit 1, instead of
    dumping a raw traceback."""
    try:
        yield
    except _EXPECTED_ERRORS as e:
        print(f"Error: {e}", file=sys.stderr)
        raise _Exit(1) from e


def _emit(data: dict) -> None:
    """The one stdout convention: a single JSON object, nothing else."""
    print(json.dumps(data))


# --------------------------------------------------------------------------------------
# Commands. Each takes the parsed namespace and does its work; the parser below binds them.
# --------------------------------------------------------------------------------------


def _cmd_new_spec(args: argparse.Namespace) -> None:
    """Create a new draft spec file from a title; print its metadata as JSON."""
    with _clean_exit():
        created = spec.new_spec(args.path, args.title)
        _emit(created)
        # The spec file now exists: fire `on-spec-created`. Total by contract: never raises,
        # warns on stderr only for a spawn failure — the JSON above stays clean.
        hooks.fire_spec_event("on-spec-created", Path(created["path"]))


def _cmd_next_seq(args: argparse.Namespace) -> None:
    """Print the next spec sequence number for the configured spec home."""
    with _clean_exit():
        cfg = config.load(args.path)
        _emit({"seq": naming.next_sequence(cfg.spec_home_path)})


def _cmd_tasks_path(args: argparse.Namespace) -> None:
    """Print the path of the task-list companion beside a spec."""
    with _clean_exit():
        _emit({"path": str(Path(args.file).with_name(naming.TASKS_FILENAME))})


def _cmd_build_branch(args: argparse.Namespace) -> None:
    """Print the isolated build branch name for a spec — the one the Builder creates, accept
    merges, and close deletes, so all three agree on it."""
    with _clean_exit():
        _emit({"branch": naming.build_branch_name(Path(args.file))})


def _cmd_config(args: argparse.Namespace) -> None:
    """Print the resolved project settings the roles read at runtime."""
    with _clean_exit():
        cfg = config.load(args.path)
        _emit(
            {
                "root": str(cfg.root),
                "spec_home": cfg.spec_home,
                "builder": cfg.builder,
                "gate": cfg.gate,
                "integration_target": cfg.integration_target,
                "improvements": str(cfg.improvements_path),
            }
        )


def _cmd_spec_status(args: argparse.Namespace) -> None:
    """Print a spec's status, or set it with --set."""
    with _clean_exit():
        result = spec.spec_status(Path(args.file), args.set)
        _emit(result)
        if args.set is not None:
            # Fire `on-transition` on EVERY status change, regressions included — the old/new
            # pair is how a hook distinguishes a send-back; the engine holds no notion of
            # "forward". Write path only; the read path fires nothing. Total by contract — any
            # warning goes to stderr, so the JSON on stdout stays parseable.
            hooks.fire_spec_event(
                "on-transition",
                Path(args.file),
                old_status=result["previous"],
                new_status=result["status"],
            )
            if result["status"] == "verified":
                # `publish-evidence` fires when a spec turns verified and `push` is true — the
                # one AWAITED hook, on top of the detached on-transition doorbell above. Total
                # by contract: a failed publish warns on stderr and never blocks the flip.
                evidence.publish_on_verified(Path(args.file))


def _cmd_evidence_manifest(args: argparse.Namespace) -> None:
    """Hash the spec's evidence artifacts into the manifest (deterministic); also maintains the
    per-dir .gitignore per the evidence `commit` boolean."""
    with _clean_exit():
        _emit(evidence.write_manifest(Path(args.file)))


def _cmd_prune_evidence(args: argparse.Namespace) -> None:
    """Prune the spec's evidence artifact bytes per the disposition (the close-flow step).

    Artifacts are deleted iff `commit: false` — and when `push: true`, only with the manifest's
    recorded publish success (after one close-time re-attempt). The bundle and the manifest are
    never pruned. A refusal deletes nothing, warns, and exits nonzero — the signal the close
    flow halts on.
    """
    with _clean_exit():
        ok, pruned = evidence.prune(Path(args.file))
        _emit({"pruned": pruned})
        if not ok:
            raise _Exit(1)


def _cmd_evidence_artifacts(args: argparse.Namespace) -> None:
    """Print the spec's evidence artifacts — the bundle directory and the files in it that are
    artifact bytes rather than the textual account.

    The publish half of a harness needs exactly this and must not restate it: which files are
    the account (`bundle.md`, `manifest.json`, `.gitignore`) is the engine's rule, and a
    publisher that guesses it wrong either loses artifacts or overwrites the record."""
    with _clean_exit():
        ev = evidence.evidence_dir(Path(args.file))
        _emit(
            {
                "dir": str(ev),
                "artifacts": [p.name for p in evidence.artifact_files(ev)],
            }
        )


def _cmd_package(args: argparse.Namespace) -> None:
    """Print the neutral acceptance-package model for a spec as JSON — the seven parts, the
    revision pins, the evidence rows, and the degenerate-content flags.

    This is the engine's half of the account of a change; rendering it into an issue body, a
    page or a message is the adopter's. Printing it makes that boundary reachable from any
    language, so a harness never re-parses the spec files the engine has already read."""
    with _clean_exit():
        _emit(package.to_json_dict(package.build_model(Path(args.file))))


def _cmd_statuses(args: argparse.Namespace) -> None:
    """Print the spec lifecycle statuses, in order — what a harness needs to give every stage a
    column, a label, or a notification, without hard-coding a list that the engine owns."""
    with _clean_exit():
        _emit({"statuses": list(naming.SPEC_STATUSES)})


def _cmd_record_finding(args: argparse.Namespace) -> None:
    """Append a learning-loop finding to the spec's findings.md; print its path and count."""
    with _clean_exit():
        _emit(spec.record_finding(Path(args.file), args.gap, args.why, args.phase))


def _cmd_markers(args: argparse.Namespace) -> None:
    """Print the open markers in a spec file."""
    with _clean_exit():
        found = naming.find_markers(Path(args.file).read_text(encoding="utf-8"))
        _emit(
            {
                "count": len(found),
                "open": [{"id": i, "description": d} for i, d in found],
            }
        )


def _cmd_fire_hooks(args: argparse.Namespace) -> None:
    """Dry-run an event's bound hooks: one line per hook, spawned or not.

    Each is spawned exactly as the real trigger would, with a synthetic payload carrying
    `GRILLWORK_DRY_RUN=1`, so an adopter can prove their harness wiring without waiting for a
    real transition. Exits 1 when any hook failed to spawn.
    """
    with _clean_exit():
        results = hooks.dry_run(args.path, args.event)
    if not results:
        print(f"No hooks bound to `{args.event}` — nothing to fire.", file=sys.stderr)
        return
    print(
        f"Dry-run `{args.event}`: {len(results)} bound hook(s), payload GRILLWORK_DRY_RUN=1",
        file=sys.stderr,
    )
    failures = 0
    for argv, error in results:
        printed = " ".join(argv)
        if error is None:
            print(f"  spawned: {printed}", file=sys.stderr)
        else:
            failures += 1
            print(f"  FAILED:  {printed} - {error}", file=sys.stderr)
    if failures:
        raise _Exit(1)


# --------------------------------------------------------------------------------------
# The parser
# --------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """The whole CLI surface, in one place so `--help` and the roles agree."""
    parser = argparse.ArgumentParser(
        prog="grillwork",
        description="Grillwork — an overlay that runs software change as spec-driven agent loops.",
    )
    # No `--version`: this package is vendored and committed, so the files answer "which
    # Grillwork is this" (see the package docstring). The versioned surface is the contract.
    subs = parser.add_subparsers(dest="command", metavar="<command>")

    def add(name: str, handler, help_: str) -> argparse.ArgumentParser:
        sub = subs.add_parser(name, help=help_, description=help_)
        sub.set_defaults(handler=handler)
        return sub

    # `path` is any directory inside the repo; the root is found by walking up from it.
    def with_path(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument(
            "path", nargs="?", default=Path("."), type=Path,
            help="A directory inside the Grillwork repo (default: current directory).",
        )
        return sub

    def with_file(sub: argparse.ArgumentParser, help_: str = "A spec file.") -> argparse.ArgumentParser:
        sub.add_argument("file", type=Path, help=help_)
        return sub

    sub = add("new-spec", _cmd_new_spec, "Create a new draft spec file from a title.")
    sub.add_argument("--title", required=True, help="The agreed spec title.")
    with_path(sub)

    with_path(add("next-seq", _cmd_next_seq, "Print the next spec sequence number."))
    with_file(add("tasks-path", _cmd_tasks_path, "Print the task-list path beside a spec."))
    with_file(add("build-branch", _cmd_build_branch, "Print a spec's isolated build branch name."))
    with_path(add("config", _cmd_config, "Print the resolved project settings."))

    sub = with_file(add("spec-status", _cmd_spec_status, "Print a spec's status, or set it."))
    sub.add_argument("--set", default=None, help="New status to write to the spec header.")

    with_file(add("evidence-manifest", _cmd_evidence_manifest, "Hash the spec's evidence artifacts."))
    with_file(add("prune-evidence", _cmd_prune_evidence, "Prune evidence bytes per the disposition."))

    # The harness seam: engine content a binding needs, printed rather than imported.
    with_file(
        add("evidence-artifacts", _cmd_evidence_artifacts, "List the spec's evidence artifacts."),
        "The spec whose evidence bundle to list.",
    )
    with_file(
        add("package", _cmd_package, "Print the neutral acceptance-package model for a spec."),
        "The spec to model.",
    )
    add("statuses", _cmd_statuses, "Print the spec lifecycle statuses, in order.")

    sub = with_file(
        add("record-finding", _cmd_record_finding, "Append a learning-loop finding."),
        "The spec file the finding is against.",
    )
    sub.add_argument("--gap", required=True, help="The gap that had to be asked mid-flow.")
    sub.add_argument("--why", required=True, help="Why the spec did not already cover it.")
    sub.add_argument("--phase", default=None, help="Where it surfaced, e.g. build / dod-review.")

    with_file(
        add("markers", _cmd_markers, "Print the open [GAP] markers in a spec file."),
        "A spec file to scan for open [GAP] markers.",
    )

    sub = add("fire-hooks", _cmd_fire_hooks, "Dry-run the hooks bound to a lifecycle event.")
    sub.add_argument("event", help="The lifecycle event whose bound hooks to spawn.")
    with_path(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "handler", None) is None:
        parser.print_help(sys.stderr)
        return 2
    try:
        args.handler(args)
    except _Exit as e:
        return e.code
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised through __main__.py
    raise SystemExit(main())
