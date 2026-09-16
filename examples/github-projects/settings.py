"""The harness's OWN settings — deliberately not Grillwork's config.

The engine names no tracker, so nothing about this board lives in
`.grillwork/settings/config.json`. What the harness needs, the harness carries: a
`settings.yaml` beside this file (see `settings.example.yaml`), with every value overridable
by a `GRILLWORK_GH_*` environment variable so CI can bind a board without a file.

    owner            GitHub project owner   (blank -> the repo's git origin)
    project_number   GitHub project number  (required)
    project_url      a Projects v2 URL, an alternative to owner + number
    repo             owner/name holding the issues (blank -> the repo's git origin)
    status_field     the single-select field the sync writes
    status_map       every lifecycle stage -> one of that field's options

`root` is not a setting: it is derived from the spec path the doorbell names, by walking up to
the directory holding `.grillwork/` — the contract's own instruction to derive state from the
files rather than from the payload. That walk lives in `grillwork_cli.py`, beside the engine
calls it locates.

Reading a settings **file** needs PyYAML; a pure-environment binding needs nothing but the
standard library, so the import is deferred to the read.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SETTINGS_FILENAME = "settings.yaml"

# One environment override per file key; `GRILLWORK_GH_SETTINGS` names a settings file elsewhere.
_ENV_PREFIX = "GRILLWORK_GH_"
_SCALAR_KEYS = ("owner", "project_number", "project_url", "repo", "status_field", "integration_target")


class SettingsError(Exception):
    """The harness's settings are absent, unreadable, or incomplete."""


@dataclass
class Settings:
    """Everything the sync reads. Attribute names are the harness's own — the engine's config
    object is never passed in here."""

    root: Path
    owner: str = ""
    project_number: str = ""
    repo: str = ""
    status_field: str = ""
    status_map: dict[str, str] = field(default_factory=dict)
    integration_target: str = ""


def load(root: Path, *, settings_path: Path | None = None) -> Settings:
    """The harness's settings for the repo at ``root``: the settings file (this directory's
    `settings.yaml`, or `$GRILLWORK_GH_SETTINGS`) with `GRILLWORK_GH_*` environment overrides
    layered on top. Raises :class:`SettingsError` when nothing binds a board.

    Identity is resolved the way the adapter's :func:`~github_projects.resolve_identity`
    resolves it, so `owner` / `repo` may be left blank and default from the repo's git origin.
    """
    data = _read_file(settings_path)
    for key in _SCALAR_KEYS:
        env = os.environ.get(f"{_ENV_PREFIX}{key.upper()}")
        if env is not None:
            data[key] = env

    import github_projects  # local import: settings.py stays importable without the adapter

    owner, number, repo = github_projects.resolve_identity(
        owner=str(data.get("owner", "") or ""),
        project_number=str(data.get("project_number", "") or ""),
        project_url=str(data.get("project_url", "") or ""),
        repo=str(data.get("repo", "") or ""),
        root=root,
    )
    missing = [name for name, value in (("project_number", number), ("repo", repo), ("owner", owner)) if not value]
    if missing:
        raise SettingsError(
            f"the GitHub Projects harness has no {', '.join(missing)}. Set them in "
            f"{SETTINGS_FILENAME} (or the matching {_ENV_PREFIX}* variables)."
        )
    return Settings(
        root=Path(root),
        owner=owner,
        project_number=number,
        repo=repo,
        status_field=str(data.get("status_field", "") or ""),
        status_map={str(k): str(v) for k, v in (data.get("status_map") or {}).items()},
        integration_target=str(data.get("integration_target", "") or ""),
    )


def _read_file(settings_path: Path | None) -> dict:
    path = Path(settings_path or os.environ.get(f"{_ENV_PREFIX}SETTINGS") or Path(__file__).with_name(SETTINGS_FILENAME))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    # PyYAML is imported here rather than at the top so an environment-only binding — no
    # settings file at all — needs nothing beyond the standard library.
    try:
        import yaml
    except ModuleNotFoundError as e:
        raise SettingsError(
            f"reading {path} needs PyYAML, which is not installed (`pip install pyyaml`). "
            f"Alternatively remove the file and bind the board with {_ENV_PREFIX}* environment "
            f"variables alone, which needs no dependency."
        ) from e
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SettingsError(f"could not parse {path}: {e}") from e
    return loaded if isinstance(loaded, dict) else {}
