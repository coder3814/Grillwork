"""Hook dispatch — the engine's boundary at the repo's edge (spec 010).

Generalized from the spec-004 tracker seam (R-014): the trigger sites (``new-spec``,
``spec-status --set``) ring a doorbell at named lifecycle events, and
the commands the adopter bound in config.json's ``hooks:`` section are spawned for it. The
engine never names what a hook is *for* — there is no tracker concept here, only commands
run at events.

The contract this module implements:

- **Configuration (R-004):** ``hooks:`` binds each event to a **list of commands**, each an
  **argv list**, run in binding order **without a shell** — Windows and POSIX behave
  identically. An event with no binding (absent, commented out, or an empty list) is simply
  skipped. A binding that is not an argv list is skipped with a stderr warning naming the
  remedy.
- **Payload (R-003):** environment variables on top of the inherited environment —
  ``GRILLWORK_EVENT``, ``GRILLWORK_SPEC_PATH``, and for transitions ``GRILLWORK_OLD_STATUS``
  / ``GRILLWORK_NEW_STATUS``. A doorbell, nothing more: the hook derives state from the
  files.
- **Detachment and totality (R-005, semantics carried over from the seam):** fire-and-forget
  hooks are spawned **fully detached** — the trigger never waits, never raises, and never
  changes its exit code. The engine warns on stderr only for a **spawn** failure (command
  missing, not executable); a hook that starts and then fails is its own responsibility to
  log. (``publish-evidence``, the one *awaited* event, reuses the same binding resolution
  through :func:`run_awaited`; its protocol lives in :mod:`.evidence`.)
- **Firing location (R-006):** hooks fire from wherever the triggering command runs — no
  path rebasing. Mid-build transitions fire from the build worktree and
  ``GRILLWORK_SPEC_PATH`` points into it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import config

# The contract's events (settled at contract v3; v4 added a read surface and v5 the dry-run
# requirement, neither of them an event). The
# one place the engine enumerates them: the config
# template lists them for the adopter, and `fire-hooks` rejects anything else.
#
# There are deliberately no install-time events. Installation is a prompt an agent follows,
# not a command the engine runs, so the engine is never present at the moment a repo is set
# up or refreshed — it has nothing to ring from. Every event here is a loop event, fired by
# the command that caused it.
EVENTS = (
    "on-spec-created",
    "on-transition",
    "publish-evidence",
)


def fire_spec_event(
    event: str,
    spec_path: Path,
    *,
    old_status: str | None = None,
    new_status: str | None = None,
) -> None:
    """Fire a spec-scoped event (``on-spec-created``; ``on-transition`` with the old/new
    pair). The install is located by walking up from the spec path, so the trigger site
    passes the path it already holds (R-006: no rebasing — inside a worktree, the payload
    points into that worktree)."""
    payload = {
        "GRILLWORK_EVENT": event,
        "GRILLWORK_SPEC_PATH": str(Path(spec_path).resolve()),
    }
    if old_status is not None:
        payload["GRILLWORK_OLD_STATUS"] = old_status
    if new_status is not None:
        payload["GRILLWORK_NEW_STATUS"] = new_status
    _dispatch(Path(spec_path), event, payload)


def _dispatch(start: Path, event: str, payload: dict[str, str]) -> None:
    """Resolve the event's bindings from config and spawn each, detached, in binding order.

    Total by contract: never raises, never changes the trigger's exit code. An unreadable
    or absent config resolves no binding, which is the skipped case (R-004).
    """
    try:
        cfg = config.load(start)
    except Exception:  # noqa: BLE001 — total by contract: no readable config, nothing bound
        return
    env = {**os.environ, **payload}
    for argv in _argv_lists(event, cfg.hooks.get(event)):
        _spawn_detached(argv, env)


def _argv_lists(event: str, bound) -> list[list[str]]:
    """The event's bindings as validated argv lists, in binding order.

    Absent / empty bindings are skipped silently (R-004). A binding that is not an argv
    list — a bare string, or a ``hooks:`` value that is not a list of commands — is a config
    error: skipped here with a warning naming the remedy (``fire-hooks`` surfaces the
    same shapes ahead of time)."""
    if not bound:
        return []
    if not isinstance(bound, list):
        _warn(
            f"hook binding for {event!r} must be a list of argv-list commands "
            f"(got {bound!r}); write it as e.g.\n"
            f'  {event}:\n    - ["python", "hooks/sync.py"]'
        )
        return []
    commands: list[list[str]] = []
    for entry in bound:
        if is_argv_list(entry):
            commands.append([str(element) for element in entry])
        else:
            _warn(
                f"hook command for {event!r} is not an argv list ({entry!r}) and was "
                'skipped; write each command as an argv list, e.g. '
                '["python", "hooks/sync.py"].'
            )
    return commands


def is_argv_list(entry) -> bool:
    """Is one bound command a well-formed argv list (R-004)? A non-empty list of scalars —
    a bare string, an empty list, or a nested structure is not. The single home of the shape
    rule: fire time skips a bad shape with a warning, `fire-hooks` surfaces it ahead of
    time (R-017), and both must mean the same thing by "argv list"."""
    return (
        isinstance(entry, list)
        and bool(entry)
        and not any(isinstance(element, (list, dict)) for element in entry)
    )


def _spawn_detached(argv: list[str], env: dict[str, str]) -> None:
    """Spawn one hook command fully detached — no shell, no wait, no inherited stdio — from
    the trigger's own working directory (R-005/R-006). Warns on stderr only when the spawn
    itself fails (command missing, not executable); a hook that starts and then fails is
    silent from the engine's side."""
    try:
        _popen_detached(argv, env)
    except Exception as exc:  # noqa: BLE001 — total by contract (R-005): anything Popen
        # raises means the hook never started, which IS a spawn failure — the one case the
        # engine warns for. Not just OSError: e.g. an argv element carrying an embedded NUL
        # (reachable from adopter config, YAML `"\0"`) raises ValueError, and a narrower
        # catch would let it escape and change the trigger's exit code.
        _warn(
            f"hook command {argv[0]!r} could not be spawned ({exc}); the triggering "
            "change was saved. Check the `hooks:` section in "
            ".grillwork/settings/config.json."
        )


def _popen_detached(argv: list[str], env: dict[str, str]) -> None:
    """The detached spawn itself — raises on a spawn failure, so the caller decides whether
    that is a stderr warning (the trigger sites) or a per-hook report line (`--fire`)."""
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        # Windows detachment: its own process group, no console window, no wait.
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        # POSIX detachment: its own session, so it outlives the trigger.
        kwargs["start_new_session"] = True
    subprocess.Popen(argv, env=env, **kwargs)  # noqa: S603 — adopter-authored command, no shell


def dry_run(start: Path, event: str) -> list[tuple[list[str], str | None]]:
    """`fire-hooks <event>` (R-017): spawn every command bound to ``event`` with
    a SYNTHETIC payload and report the outcome per hook.

    Returns one ``(argv, error)`` pair per bound command, in binding order — ``error`` is
    None when the spawn succeeded, otherwise the reason it did not. What the rehearsal
    proves is the *spawn*: the same no-shell, detached invocation the fire-and-forget events
    use at their trigger sites. ``publish-evidence`` is fired the same way here, which
    is NOT its real invocation — really it is awaited and its stdout parsed
    (:func:`run_awaited`) — so for that event a dry-run proves only that the command starts,
    never the publish protocol. The payload is invented, and it says so:
    ``GRILLWORK_DRY_RUN=1`` is set exactly here and never on a real event, so a hook can tell
    a rehearsal from the thing itself.
    """
    if event not in EVENTS:
        raise ValueError(
            f"unknown hook event {event!r}; the contract's events are: {', '.join(EVENTS)}"
        )
    cfg = config.load(start)
    env = {**os.environ, **_synthetic_payload(event, cfg)}
    results: list[tuple[list[str], str | None]] = []
    for argv in _argv_lists(event, cfg.hooks.get(event)):
        try:
            _popen_detached(argv, env)
        except Exception as exc:  # noqa: BLE001 — same spawn-failure surface as the trigger
            # sites; here it is reported per hook instead of warned, which is the point of
            # the dry-run.
            results.append((argv, str(exc)))
        else:
            results.append((argv, None))
    return results


def _synthetic_payload(event: str, cfg) -> dict[str, str]:
    """The rehearsal's doorbell: exactly the variables the contract gives this event (R-003),
    with invented values, plus ``GRILLWORK_DRY_RUN``. The spec path is deliberately a
    placeholder that does not exist — a hook must tolerate a vanished path anyway (R-006)."""
    payload = {"GRILLWORK_EVENT": event, "GRILLWORK_DRY_RUN": "1"}
    payload["GRILLWORK_SPEC_PATH"] = str(cfg.spec_home_path / "000-grillwork-dry-run" / "spec.md")
    if event == "on-transition":
        payload["GRILLWORK_OLD_STATUS"] = "drafting"
        payload["GRILLWORK_NEW_STATUS"] = "ready"
    return payload


def run_awaited(argv: list[str], payload: dict[str, str]) -> subprocess.CompletedProcess | None:
    """Run one hook command AWAITED — the single exception to detachment (R-005):
    ``publish-evidence`` must report success or failure, so the trigger waits, captures
    stdout (the ``<artifact-name> <url>`` protocol, R-009), and reads the exit code. Same
    no-shell invocation and doorbell-env payload as the detached path, from the trigger's
    own working directory. Returns the completed process, or None on a spawn failure
    (warned) — a spawn failure counts as a failed run (R-010)."""
    env = {**os.environ, **payload}
    try:
        return subprocess.run(  # noqa: S603 — adopter-authored command, no shell
            argv, env=env, capture_output=True, encoding="utf-8", errors="replace"
        )
    except Exception as exc:  # noqa: BLE001 — same totality rationale as _spawn_detached:
        # anything raised here means the command never started, which IS a spawn failure.
        _warn(
            f"hook command {argv[0]!r} could not be spawned ({exc}). Check the `hooks:` "
            "section in .grillwork/settings/config.json."
        )
        return None


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)
