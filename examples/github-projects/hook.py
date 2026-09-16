#!/usr/bin/env python
"""The hook entry script — where Grillwork's doorbell meets this harness.

Bound in `.grillwork/settings/config.json` as an argv list, at whatever path you copied this
directory to — `<harness>` here is the one thing you substitute, and nothing else in the
binding changes:

    "hooks": {
      "on-spec-created": [["python", "<harness>/hook.py"]],
      "on-transition":   [["python", "<harness>/hook.py"]]
    }

e.g. `tools/grillwork-harness/github-projects/hook.py` for a copy that kept this directory's
name, or `tools/grillwork-harness/hook.py` for one whose contents were copied flat.

The engine spawns it detached and never waits: nothing this script does can fail a Grillwork
command. It reads the payload from the environment (`GRILLWORK_EVENT`, `GRILLWORK_SPEC_PATH`,
`GRILLWORK_OLD_STATUS` / `GRILLWORK_NEW_STATUS`, `GRILLWORK_DRY_RUN`), treats it as a doorbell,
and reads everything it projects from the spec files themselves — so a hook that runs late, out
of order, or twice still writes the current state.

Two extra modes, for the adopter rather than the engine:

    python hook.py --check    list the board's single-select fields and their options, and
                              verify the configured field/map is really on the board.
    GRILLWORK_DRY_RUN=1       (what `fire-hooks <event>` sets) — report what would
                              be synced and exit 0, touching no network.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# This harness's own modules sit beside this file, wherever the adopter copied the directory to.
# Nothing else goes on the path: engine content is *asked for* rather than imported (see
# `grillwork_cli.py`), so there is no vendored package to locate and no depth to assume.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import github_projects  # noqa: E402 — after the sys.path line above, by design
import grillwork_cli  # noqa: E402
import settings as settings_module  # noqa: E402
from grillwork_cli import repo_root  # noqa: E402 — the walk that locates the engine seam

# The events this harness answers. Any other event is a no-op success: the contract may grow
# events, and an unknown one is never this hook's business.
_SPEC_EVENTS = ("on-spec-created", "on-transition")


def main(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ if env is None else env)

    if "--check" in argv:
        return _check(env)

    event = env.get("GRILLWORK_EVENT", "")
    if event not in _SPEC_EVENTS:
        return 0

    spec_path = env.get("GRILLWORK_SPEC_PATH", "")
    if not spec_path:
        print(f"github-projects: {event} carried no GRILLWORK_SPEC_PATH.", file=sys.stderr)
        return 1

    root = repo_root(spec_path)
    try:
        cfg = settings_module.load(root)
    except settings_module.SettingsError as e:
        print(f"github-projects: {e}", file=sys.stderr)
        return 1

    if env.get("GRILLWORK_DRY_RUN"):
        # The engine's dry-run: prove the wiring (this script runs, the settings load, the spec
        # is readable) without touching the board.
        print(
            f"github-projects: dry run — would sync {spec_path} onto "
            f"{cfg.repo} project #{cfg.project_number}."
        )
        return 0

    try:
        github_projects.sync_spec(spec_path, cfg)
    except (github_projects.GitHubError, grillwork_cli.EngineError, OSError) as e:
        print(f"github-projects: {e}", file=sys.stderr)
        return 1
    return 0


def _check(env: dict[str, str]) -> int:
    """`--check`: show the board's single-select fields and options, then verify the settings'
    chosen field and every mapped option are on it. The adopter runs this before wiring."""
    root = repo_root(env.get("GRILLWORK_SPEC_PATH") or Path.cwd())
    try:
        cfg = settings_module.load(root)
    except settings_module.SettingsError as e:
        print(f"github-projects: {e}", file=sys.stderr)
        return 1
    try:
        fields = github_projects.single_select_fields(cfg.owner, cfg.project_number, cfg.repo)
    except github_projects.GitHubError as e:
        print(f"github-projects: {e}", file=sys.stderr)
        return 1
    if not fields:
        print(
            "github-projects: the project has no single-select field to hold your columns. Add "
            "one on GitHub — this harness never creates or edits a project's fields.",
            file=sys.stderr,
        )
        return 1
    print(f"{cfg.repo} project #{cfg.project_number} — single-select fields:")
    for name, options in fields:
        print(f"  {name}: {', '.join(options)}")
    try:
        github_projects.validate_mapping(
            cfg.owner, cfg.project_number, cfg.repo, cfg.status_field, cfg.status_map
        )
    except github_projects.GitHubError as e:
        print(f"github-projects: {e}", file=sys.stderr)
        return 1
    print(f"OK - settings map every stage onto {cfg.status_field!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
