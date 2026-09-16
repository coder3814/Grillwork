"""Phase 2 — strict config loading for commands that use config."""

import hashlib
from pathlib import Path

import pytest
from conftest import install, write_config
from grillwork import config


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _init(tmp_path):
    install(tmp_path)


def test_load_after_init(tmp_path):
    _init(tmp_path)
    cfg = config.load(tmp_path)
    assert cfg.builder == "claude-code"
    assert cfg.spec_home == ".grillwork/specs"
    assert cfg.spec_home_path == tmp_path / ".grillwork" / "specs"


def test_find_root_walks_up(tmp_path):
    _init(tmp_path)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert config.find_root(nested) == tmp_path


def test_load_without_install_raises(tmp_path):
    with pytest.raises(config.ConfigError):
        config.load(tmp_path)


def test_load_malformed_raises(tmp_path):
    _init(tmp_path)
    (tmp_path / ".grillwork" / "settings" / "config.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(config.ConfigError):
        config.load(tmp_path)


def test_load_missing_keys_raises(tmp_path):
    _init(tmp_path)
    # Valid JSON, but `spec_home` is absent — the missing-key path, not the malformed one.
    write_config(tmp_path, {"builder": "claude-code"})
    with pytest.raises(config.ConfigError):
        config.load(tmp_path)


def test_integration_target_defaults_empty_and_round_trips(tmp_path):
    # Unset in a default install (an optional binding like the gate) …
    install(tmp_path)
    assert config.load(tmp_path).integration_target == ""

    # … and survives a round-trip when the adopter sets it.
    install(tmp_path / "other", integration_target="main")
    assert config.load(tmp_path / "other").integration_target == "main"


def _write_config(tmp_path, **extra):
    """A minimal hand-written config carrying the two required keys plus ``extra`` sections."""
    return write_config(
        tmp_path, {"spec_home": ".grillwork/specs", "builder": "claude-code", **extra}
    )


def test_evidence_defaults_when_section_absent(tmp_path):
    # Spec 010 R-007: no `evidence:` section at all -> `commit: true` / `push: false` at
    # read time, and load writes nothing back.
    path = _write_config(tmp_path)
    before = _sha(path)
    cfg = config.load(tmp_path)
    assert cfg.evidence_commit is True
    assert cfg.evidence_push is False
    assert _sha(path) == before, "config.load must not write to the adopter's config"


def test_evidence_partial_section_takes_defaults(tmp_path):
    # Spec 010 R-007: present-but-partial is not an error — each absent key takes its own
    # default independently.
    _write_config(tmp_path, evidence={"push": True})
    cfg = config.load(tmp_path)
    assert cfg.evidence_commit is True  # absent key -> default
    assert cfg.evidence_push is True  # present key -> as written

    _write_config(tmp_path, evidence={"commit": False})
    cfg = config.load(tmp_path)
    assert cfg.evidence_commit is False
    assert cfg.evidence_push is False


def test_hooks_section_parsed_as_data(tmp_path):
    # Spec 010 R-004: the `hooks:` section is read as event -> list of argv-list commands.
    # Load carries it as data; shape validation belongs to fire time / `grillwork check`.
    _write_config(
        tmp_path,
        hooks={"on-transition": [["python", "hooks/sync.py"], ["notify-send", "grillwork"]]},
    )
    cfg = config.load(tmp_path)
    assert cfg.hooks == {
        "on-transition": [["python", "hooks/sync.py"], ["notify-send", "grillwork"]]
    }

    # No `hooks:` section -> an empty mapping, nothing bound.
    _write_config(tmp_path)
    assert config.load(tmp_path).hooks == {}


def test_obsolete_tracker_keys_ignored(tmp_path):
    # Spec 010 R-014/R-015: the retired `tracker` / `github_*` keys are treated as any
    # unknown key — ignored, never surfaced, never an error. No migration machinery.
    _write_config(
        tmp_path,
        tracker="github",
        github_owner="acme",
        github_project_number=2,
        github_repo="acme/widgets",
    )
    cfg = config.load(tmp_path)
    assert not hasattr(cfg, "tracker")
    assert not hasattr(cfg, "github_owner")
    # The load still resolves everything it does own.
    assert cfg.builder == "claude-code"
    assert cfg.evidence_commit is True and cfg.evidence_push is False
