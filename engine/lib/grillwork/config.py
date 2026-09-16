"""Config loading for commands that *use* config (strict).

Distinct from `overlay.init`'s tolerant read: a command that grills or reviews cannot
proceed on a missing or malformed config, so this loader fails loud. It also locates the
Grillwork root by walking up from a start directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Raised when no valid Grillwork config can be loaded."""


@dataclass(frozen=True)
class Config:
    root: Path
    spec_home: str
    builder: str
    gate: str
    integration_target: str
    # The `hooks:` section as configured (spec 010 R-004): event name -> list of argv-list
    # commands. Kept as data; shape validation happens at fire time (the dispatcher skips a
    # non-argv binding with a warning) and by `fire-hooks`. Frozen dataclass: the
    # mutable default needs a factory.
    hooks: dict = field(default_factory=dict)
    # The evidence disposition (spec 010 R-007): two independent booleans. An absent
    # `evidence:` section, or an absent individual key, takes its default — `commit: true`
    # / `push: false`, today's behavior exactly.
    evidence_commit: bool = True
    evidence_push: bool = False

    @property
    def spec_home_path(self) -> Path:
        return self.root / self.spec_home

    @property
    def improvements_path(self) -> Path:
        """The curated cross-spec learning log (the curator writes it, the Griller reads it)."""
        return self.root / ".grillwork" / "settings" / "improvements.md"

    @property
    def spec_template_path(self) -> Path:
        """The spec template, read from the method installed in this repo rather than from a
        copy bundled in this package: the installed files are the source of truth, so an
        adopter reading the template sees exactly what `new-spec` will write."""
        return self.root / ".grillwork" / "engine" / "spec-template.md"


def find_root(start: Path) -> Path:
    """Walk up from ``start`` to the repo containing ``.grillwork/settings/config.json``."""
    start = Path(start).resolve()
    for d in (start, *start.parents):
        if (d / ".grillwork" / "settings" / "config.json").exists():
            return d
    raise ConfigError(
        "No Grillwork install found (looked for .grillwork/settings/config.json). "
        "Install it by pointing your agent at Grillwork's INSTALL.md."
    )


def load(start: Path) -> Config:
    root = find_root(start)
    config_path = root / ".grillwork" / "settings" / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ConfigError(f"config.json is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError("config.json must be a mapping of settings.")
    missing = [k for k in ("spec_home", "builder") if not data.get(k)]
    if missing:
        raise ConfigError(f"config.json is missing required keys: {', '.join(missing)}")
    # Unknown keys — including the obsolete `tracker` / `github_*` bindings (spec 010
    # R-014/R-015) — are ignored, as any unknown key always has been.
    hooks = data.get("hooks")
    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    commit = evidence.get("commit")
    push = evidence.get("push")
    return Config(
        root=root,
        spec_home=str(data["spec_home"]),
        builder=str(data["builder"]),
        gate=str(data.get("gate", "")),
        integration_target=str(data.get("integration_target", "")),
        hooks=dict(hooks) if isinstance(hooks, dict) else {},
        evidence_commit=True if commit is None else bool(commit),
        evidence_push=False if push is None else bool(push),
    )
