"""What the harness needs installed to bind a board.

Grillwork's own promise — the engine lib runs on the standard library alone — is scoped to
``engine/lib/``, and this harness is not the engine. But an adopter reading the example's
prerequisites (the ``gh`` CLI, a Projects v2 board) had no way to learn that a third-party
package sat behind the first import, and found out from an ``ImportError``. So the dependency
is now real only where it is really used: **reading a settings file** needs PyYAML, and an
environment-only binding needs nothing.

These tests make the machine look like one without PyYAML — a finder ahead of the real import
system that refuses the name — and drive the loader both ways.
"""

from __future__ import annotations

import sys

import pytest
import settings as settings_module


class _NoYaml:
    """A meta-path finder that makes ``import yaml`` fail exactly as an absent package does."""

    def find_spec(self, name, path=None, target=None):
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'", name="yaml")
        return None


@pytest.fixture
def without_pyyaml(monkeypatch):
    """PyYAML uninstallable for the duration of one test. It is dropped from ``sys.modules``
    too: an already-imported module short-circuits before any finder is consulted."""
    monkeypatch.delitem(sys.modules, "yaml", raising=False)
    monkeypatch.setattr(sys, "meta_path", [_NoYaml(), *sys.meta_path])


def _bind_environment(monkeypatch):
    for key, value in (
        ("GRILLWORK_GH_OWNER", "acme"),
        ("GRILLWORK_GH_PROJECT_NUMBER", "7"),
        ("GRILLWORK_GH_REPO", "acme/widgets"),
    ):
        monkeypatch.setenv(key, value)


def test_an_environment_only_binding_needs_no_pyyaml(tmp_path, monkeypatch, without_pyyaml):
    """The case the module's own comment advertises — "CI can bind a board with no file". With
    no settings file to read there is nothing to parse, so nothing is imported to parse it."""
    _bind_environment(monkeypatch)

    cfg = settings_module.load(tmp_path, settings_path=tmp_path / "absent.yaml")

    assert (cfg.owner, cfg.project_number, cfg.repo) == ("acme", "7", "acme/widgets")


def test_a_settings_file_without_pyyaml_says_what_is_missing(tmp_path, monkeypatch, without_pyyaml):
    """A file the adopter wrote and the loader cannot read is reported as the dependency it is,
    with both remedies — not as an ImportError traceback out of a hook."""
    _bind_environment(monkeypatch)
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text("project_number: 7\n", encoding="utf-8")

    with pytest.raises(settings_module.SettingsError) as raised:
        settings_module.load(tmp_path, settings_path=settings_file)

    message = str(raised.value)
    assert "PyYAML" in message
    assert "GRILLWORK_GH_" in message


def test_a_settings_file_still_binds_when_pyyaml_is_present(tmp_path, monkeypatch):
    """The ordinary path, unchanged by the deferral: the file is read and its values bind.

    The one test here that needs PyYAML really installed — the two above only need it to look
    absent — so it says so and skips instead of failing on a machine that has none. That is
    the dependency the README makes conditional, kept conditional."""
    pytest.importorskip("yaml", reason="reading a settings file needs PyYAML")
    monkeypatch.delenv("GRILLWORK_GH_PROJECT_NUMBER", raising=False)
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        "owner: acme\nproject_number: 7\nrepo: acme/widgets\nstatus_field: Stage\n",
        encoding="utf-8",
    )

    cfg = settings_module.load(tmp_path, settings_path=settings_file)

    assert (cfg.owner, cfg.project_number, cfg.repo) == ("acme", "7", "acme/widgets")
    assert cfg.status_field == "Stage"
