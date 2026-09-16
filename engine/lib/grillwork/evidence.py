"""Evidence disposition — the manifest, the publish protocol, and the prune (spec 010,
R-007..R-011).

The two config booleans (``evidence: commit`` / ``push``, parsed in :mod:`.config`) decide
how a spec's evidence bundle is kept: whether artifact bytes enter git, and whether the
awaited ``publish-evidence`` hook runs. This module implements everything downstream of
those booleans:

- **The manifest (R-009):** ``grillwork evidence-manifest <spec>`` deterministically hashes
  every artifact file in the spec's ``evidence/`` dir — everything except the account files
  ``bundle.md``, ``manifest.json``, and ``.gitignore`` — into ``evidence/manifest.json``
  (SHA-256, recorded as ``sha256:<hex>`` beside a top-level ``hash_algorithm`` key, so the
  record self-describes). Zero artifacts still writes the manifest, with an empty list.
  Regenerating the manifest drops any prior publish record: the evidence changed, so a
  stale success must never vouch for new bytes (the same principle as R-010's re-fire
  invalidation).
- **The per-dir ``.gitignore`` (R-008):** every engine write into ``evidence/`` funnels
  through :func:`_save_manifest`, which maintains ``evidence/.gitignore`` per the ``commit``
  boolean — created (ignore artifacts, re-include the account files and itself) when
  ``commit: false``, removed on the next engine write when true. The adopter's repo-level
  ``.gitignore`` is never touched.
- **The publish protocol (R-005/R-010):** ``publish-evidence`` is the one AWAITED hook. It
  binds at most one command (zero or more than one → warning, no success record); success
  is exit code 0 alone; stdout lines of the form ``<artifact-name> <url>`` are recorded
  beside the hashes together with a success timestamp — the publish record lives in the
  manifest. A failed publish (nonzero exit, or a spawn failure) warns and never blocks the
  ``verified`` flip; it only blocks the prune. Before any (re-)fire, a prior success record
  is invalidated (C-013).
- **The prune (R-010/R-011):** ``grillwork prune-evidence <spec>`` — the only code path
  that deletes evidence (the data-integrity disposition). When ``push: true`` and no
  success is recorded, it first re-attempts the publish once. Artifact files are deleted
  iff ``commit: false``, and when ``push`` is also true only with a recorded success;
  ``commit: true`` prunes nothing (exit 0 no-op); ``bundle.md`` and ``manifest.json`` are
  never pruned. A refusal prunes nothing, warns naming the two remedies, and reports
  failure — the nonzero exit ``/grillwork-close`` halts on. Status is not this command's
  concern.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config, hooks

EVIDENCE_DIRNAME = "evidence"
MANIFEST_FILENAME = "manifest.json"
PUBLISH_EVENT = "publish-evidence"
# The textual account: never hashed as an artifact, never pruned, always trackable.
ACCOUNT_FILES = ("bundle.md", MANIFEST_FILENAME, ".gitignore")

_HASH_ALGORITHM = "sha256"
_GITIGNORE_CONTENT = (
    "# Written by Grillwork: evidence disposition `commit: false` (spec 010 R-008).\n"
    "# Artifact bytes stay out of git; the textual account stays trackable.\n"
    "*\n"
    "!bundle.md\n"
    "!manifest.json\n"
    "!.gitignore\n"
)


def evidence_dir(spec_path: Path) -> Path:
    """The spec's evidence bundle directory, beside the spec file."""
    return Path(spec_path).parent / EVIDENCE_DIRNAME


def artifact_files(ev: Path) -> list[Path]:
    """The bundle's artifact files: every top-level file except the account files, sorted.

    The one definition of "which of these are artifacts" — hashed by the manifest, deleted by
    the prune, and published by an adopter's `publish-evidence` harness (which reads it through
    `grillwork evidence-artifacts` rather than restating the rule)."""
    ev = Path(ev)
    if not ev.is_dir():
        return []
    return sorted(p for p in ev.iterdir() if p.is_file() and p.name not in ACCOUNT_FILES)


def _now_stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- the manifest (R-008/R-009) ----------------------------------------------------------


def write_manifest(spec_path: Path) -> dict:
    """Deterministically (re)write ``evidence/manifest.json`` for a spec: one filename +
    content-hash entry per artifact file, an empty list when there are none. Also maintains
    the per-dir ``.gitignore`` per the ``commit`` boolean (R-008). Returns ``{path,
    artifacts}``."""
    cfg = config.load(Path(spec_path))
    ev = evidence_dir(spec_path)
    if not ev.is_dir():
        raise FileNotFoundError(
            f"no evidence bundle at {ev} — author the bundle before generating its manifest"
        )
    data = _manifest_data(ev)
    _save_manifest(ev, data, cfg.evidence_commit)
    return {
        "path": str(ev / MANIFEST_FILENAME),
        "artifacts": [entry["name"] for entry in data["artifacts"]],
    }


def _manifest_data(ev: Path) -> dict:
    """Hash every artifact file in ``ev`` (top-level files, minus the account files) into
    fresh manifest data. Sorted by name, so the output is deterministic."""
    entries = []
    for path in artifact_files(ev):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"name": path.name, "hash": f"{_HASH_ALGORITHM}:{digest}"})
    return {"hash_algorithm": _HASH_ALGORITHM, "artifacts": entries}


def _save_manifest(ev: Path, data: dict, commit: bool) -> None:
    """The single funnel for every engine write into ``evidence/`` — writes the manifest and
    maintains the per-dir ``.gitignore`` per the ``commit`` boolean (R-008)."""
    ev.mkdir(parents=True, exist_ok=True)
    (ev / MANIFEST_FILENAME).write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    _sync_gitignore(ev, commit)


def _sync_gitignore(ev: Path, commit: bool) -> None:
    """``commit: false`` → the per-dir ``.gitignore`` exists (artifacts ignored, the account
    files and itself re-included); ``commit: true`` → it is removed. The repo-level
    ``.gitignore`` is never touched (R-008)."""
    gitignore = ev / ".gitignore"
    if commit:
        if gitignore.exists():
            gitignore.unlink()
    else:
        gitignore.write_text(_GITIGNORE_CONTENT, encoding="utf-8")


def _load_manifest(ev: Path):
    """The manifest as a mapping, or None (absent, unreadable, or not a mapping — none of
    which can carry a publish success)."""
    path = ev / MANIFEST_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def has_publish_success(ev: Path) -> bool:
    """Whether the manifest carries a recorded publish success (the timestamp the prune
    checks, R-010)."""
    data = _load_manifest(ev)
    return bool(data and data.get("published_at"))


# --- the publish protocol (R-005/R-009/R-010) --------------------------------------------


def publish_on_verified(spec_path: Path) -> None:
    """The ``verified``-flip trigger site: run the awaited publish protocol when ``push`` is
    true. Total by contract — never raises, never blocks the flip (R-005/R-010): every
    failure is a stderr warning, and stdout stays clean for the trigger's JSON."""
    try:
        cfg = config.load(Path(spec_path))
    except Exception:  # noqa: BLE001 — no readable config, no publish disposition
        return
    if not cfg.evidence_push:
        return
    try:
        attempt_publish(cfg, Path(spec_path))
    except Exception as exc:  # noqa: BLE001 — total by contract: a failed publish warns
        hooks._warn(
            f"publish-evidence failed unexpectedly ({exc}); verified stands, but no "
            "publish success was recorded."
        )


def attempt_publish(cfg: config.Config, spec_path: Path) -> bool:
    """One publish attempt: invalidate any prior success, enforce the at-most-one binding,
    await the command, and on exit 0 record its stdout URLs plus a success timestamp in the
    manifest. Returns whether a success was recorded."""
    ev = evidence_dir(spec_path)
    # Before any (re-)fire: the evidence changed, so a stale success must never gate a
    # prune of new bytes (R-010/C-013).
    _invalidate_success(cfg, ev)
    commands = hooks._argv_lists(PUBLISH_EVENT, cfg.hooks.get(PUBLISH_EVENT))
    if not commands:
        hooks._warn(
            "evidence `push: true` but no publish-evidence command is bound; no publish "
            "success recorded — the prune stays blocked. Bind one command under `hooks: "
            "publish-evidence:` in .grillwork/settings/config.json (or set `push: false`)."
        )
        return False
    if len(commands) > 1:
        hooks._warn(
            f"publish-evidence binds {len(commands)} commands but binds at most one — one "
            "exit code, one stdout parse, one success record; wrap multiple destinations "
            "in a single script. No publish success recorded — the prune stays blocked."
        )
        return False
    payload = {
        "GRILLWORK_EVENT": PUBLISH_EVENT,
        "GRILLWORK_SPEC_PATH": str(Path(spec_path).resolve()),
    }
    proc = hooks.run_awaited(commands[0], payload)
    if proc is None:
        return False  # a spawn failure counts as a failed publish (R-010); already warned
    if proc.returncode != 0:
        hooks._warn(
            f"publish-evidence command `{' '.join(commands[0])}` exited "
            f"{proc.returncode}; no publish success recorded — success is the exit code "
            "alone. The flip stands; the prune stays blocked until a publish succeeds."
        )
        return False
    _record_success(cfg, ev, _parse_publish_stdout(proc.stdout or ""))
    return True


def _parse_publish_stdout(text: str) -> dict[str, str]:
    """The stdout protocol (R-009): one ``<artifact-name> <url>`` pair per line. A non-blank
    line that is not such a pair is ignored with a warning — success is governed by the
    exit code alone, never by stdout shape."""
    urls: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) == 2:
            urls[parts[0]] = parts[1]
        else:
            hooks._warn(
                f"publish-evidence stdout line {line!r} is not an "
                "`<artifact-name> <url>` pair; ignored."
            )
    return urls


def _record_success(cfg: config.Config, ev: Path, urls: dict[str, str]) -> None:
    """Record the publish success in the manifest: each URL beside its artifact's hash,
    plus the success timestamp the prune checks (R-009/R-010)."""
    data = _load_manifest(ev) or _manifest_data(ev)
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
        data["artifacts"] = artifacts
    recorded = set()
    for entry in artifacts:
        if isinstance(entry, dict) and entry.get("name") in urls:
            entry["url"] = urls[entry["name"]]
            recorded.add(entry["name"])
    for name in urls:
        if name not in recorded:
            hooks._warn(
                f"publish-evidence reported a URL for {name!r}, which is not an artifact "
                "in the manifest; ignored."
            )
    data["published_at"] = _now_stamp()
    _save_manifest(ev, data, cfg.evidence_commit)


def _invalidate_success(cfg: config.Config, ev: Path) -> None:
    """Strip any prior publish record (URLs and timestamp) from the manifest — run before
    any (re-)fire, so a stale success never gates a prune of new bytes (R-010/C-013)."""
    data = _load_manifest(ev)
    if not data:
        return
    changed = data.pop("published_at", None) is not None
    for entry in data.get("artifacts") or []:
        if isinstance(entry, dict) and entry.pop("url", None) is not None:
            changed = True
    if changed:
        _save_manifest(ev, data, cfg.evidence_commit)


# --- the prune (R-010/R-011) -------------------------------------------------------------


def prune(spec_path: Path) -> tuple[bool, list[str]]:
    """The one code path that deletes evidence. Returns ``(ok, pruned-names)``; ``ok`` False
    is the refusal the close flow halts on (nothing was deleted). The rule: artifact files
    are pruned iff ``commit: false``, and when ``push`` is also true only with a recorded
    publish success (after the single close-time re-attempt); the account files never."""
    spec_path = Path(spec_path)
    cfg = config.load(spec_path)
    ev = evidence_dir(spec_path)
    if cfg.evidence_commit:
        return True, []  # committed evidence is never pruned — a no-op, not a refusal
    if cfg.evidence_push:
        if not has_publish_success(ev):
            # The close-time single re-attempt (R-010); a spawn failure counts as a
            # failed publish. Re-running close repeats it.
            attempt_publish(cfg, spec_path)
        if not has_publish_success(ev):
            hooks._warn(
                "prune-evidence refused: `commit: false` with `push: true` and no "
                "recorded publish success — these artifact bytes may be the only copy, so "
                "nothing was pruned. Remedies: fix the publish-evidence hook and re-run "
                "close, or set `push: false` to accept ephemeral loss."
            )
            return False, []
    pruned: list[str] = []
    for path in artifact_files(ev):
        path.unlink()
        pruned.append(path.name)
    return True, pruned
