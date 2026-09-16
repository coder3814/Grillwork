"""The two edges of the hook dry-run: an unbound event and an unknown event name.

The acceptance suite (`test_hooks.py`) pins that a dry-run spawns bound commands with
`GRILLWORK_DRY_RUN=1`. These cover what it does not: that firing an event nobody bound is a
reported no-op rather than silence, and that a typo'd event name fails instead of quietly
reporting success.

(The `grillwork check` cases that used to live here went with `check` itself: validating an
install is the install prompt's job now, not a command's.)
"""

from __future__ import annotations

from pathlib import Path

from conftest import install, run


def test_fire_unbound_event_is_not_a_failure(tmp_path: Path):
    """A fresh install binds nothing, so a dry-run has nothing to spawn: it says so and
    exits 0 — silence would leave an adopter unsure whether the hook ran."""
    root = install(tmp_path / "repo")
    result = run(["fire-hooks", "on-transition", str(root)])
    assert result.exit_code == 0, result.output
    assert "on-transition" in result.output


def test_fire_unknown_event_is_rejected(tmp_path: Path):
    """A typo'd event name never fires anything, so the dry-run must not report success for
    it: it fails and names the events that exist."""
    root = install(tmp_path / "repo")
    result = run(["fire-hooks", "on-transitions", str(root)])
    assert result.exit_code != 0
    assert "on-transition" in result.output
