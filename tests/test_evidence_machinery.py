"""Scaffolding tests for the evidence machinery (spec 010, unit U3) — the module-level
seams under the acceptance suite in tests/test_evidence.py: stdout-protocol parsing, the
account-file exclusion, manifest determinism, the gitignore funnel, awaited-spawn failure,
and success invalidation. All local, no network."""

from __future__ import annotations

import json
from pathlib import Path

from grillwork import config, evidence, hooks


def _install(root: Path, *, commit: bool = True, push: bool = False) -> Path:
    settings = root / ".grillwork" / "settings"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "config.json").write_text(
        json.dumps(
            {
                "spec_home": ".grillwork/specs",
                "builder": "claude-code",
                "evidence": {"commit": commit, "push": push},
            }
        , indent=2),
        encoding="utf-8",
    )
    return root


def _spec_with_evidence(root: Path, artifacts: dict[str, str]) -> Path:
    spec_dir = root / ".grillwork" / "specs" / "001-alpha"
    ev = spec_dir / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "bundle.md").write_text("# Bundle\n", encoding="utf-8")
    for name, content in artifacts.items():
        (ev / name).write_text(content, encoding="utf-8")
    return spec_dir / "spec.md"


def test_parse_stdout_pairs_and_malformed_warning(capsys):
    """Two-token lines are pairs; blank lines are skipped silently; any other non-blank
    line is ignored with a warning (R-009: exit code governs, not stdout shape)."""
    urls = evidence._parse_publish_stdout(
        "a.txt https://x/a\n\nnot-a-pair\nb.txt https://x/b extra\nc.txt https://x/c\n"
    )
    assert urls == {"a.txt": "https://x/a", "c.txt": "https://x/c"}
    err = capsys.readouterr().err
    assert err.count("warning:") == 2
    assert "not-a-pair" in err


def test_manifest_excludes_account_files_and_is_deterministic(tmp_path):
    """The account files (bundle.md, manifest.json, .gitignore) are never artifact entries
    (R-009); two runs over unchanged bytes produce identical manifests (deterministic)."""
    root = _install(tmp_path, commit=False)
    spec_path = _spec_with_evidence(root, {"b.txt": "bb\n", "a.txt": "aa\n"})
    evidence.write_manifest(spec_path)
    manifest = evidence.evidence_dir(spec_path) / "manifest.json"
    first = manifest.read_text(encoding="utf-8")
    data = json.loads(first)
    assert [e["name"] for e in data["artifacts"]] == ["a.txt", "b.txt"]
    assert data["hash_algorithm"] == "sha256"
    assert all(e["hash"].startswith("sha256:") for e in data["artifacts"])
    # A second run (the .gitignore now also present) is byte-identical.
    evidence.write_manifest(spec_path)
    assert manifest.read_text(encoding="utf-8") == first


def test_gitignore_maintained_by_engine_writes(tmp_path):
    """commit: false → the per-dir .gitignore exists with the re-includes; flipping to
    true removes it on the next engine write; the repo-level .gitignore is untouched
    (R-008)."""
    root = _install(tmp_path, commit=False)
    spec_path = _spec_with_evidence(root, {"a.txt": "aa\n"})
    evidence.write_manifest(spec_path)
    gitignore = evidence.evidence_dir(spec_path) / ".gitignore"
    text = gitignore.read_text(encoding="utf-8")
    for line in ("*", "!bundle.md", "!manifest.json", "!.gitignore"):
        assert line in text.splitlines()
    assert not (root / ".gitignore").exists()  # never the repo-level file

    _install(root, commit=True)
    evidence.write_manifest(spec_path)
    assert not gitignore.exists()
    assert not (root / ".gitignore").exists()


def test_prune_deletes_only_artifacts_ungated_when_push_false(tmp_path):
    """commit: false, push: false — artifacts go ungated; the account files stay
    (R-011)."""
    root = _install(tmp_path, commit=False, push=False)
    spec_path = _spec_with_evidence(root, {"a.txt": "aa\n", "b.txt": "bb\n"})
    evidence.write_manifest(spec_path)
    ok, pruned = evidence.prune(spec_path)
    assert ok and sorted(pruned) == ["a.txt", "b.txt"]
    ev = evidence.evidence_dir(spec_path)
    assert not (ev / "a.txt").exists() and not (ev / "b.txt").exists()
    assert (ev / "bundle.md").exists() and (ev / "manifest.json").exists()


def test_prune_is_noop_when_commit_true(tmp_path):
    """commit: true evidence is never pruned — a no-op, not a refusal (R-011)."""
    root = _install(tmp_path, commit=True, push=False)
    spec_path = _spec_with_evidence(root, {"a.txt": "aa\n"})
    evidence.write_manifest(spec_path)
    ok, pruned = evidence.prune(spec_path)
    assert ok and pruned == []
    assert (evidence.evidence_dir(spec_path) / "a.txt").exists()


def test_run_awaited_spawn_failure_warns_and_returns_none(capsys):
    """A command that cannot start is a spawn failure: warned, returned as None — it
    counts as a failed publish (R-010)."""
    proc = hooks.run_awaited(
        ["grillwork-no-such-cmd-zzz"], {"GRILLWORK_EVENT": "publish-evidence"}
    )
    assert proc is None
    assert "grillwork-no-such-cmd-zzz" in capsys.readouterr().err


def test_invalidate_strips_urls_and_timestamp(tmp_path):
    """Invalidation removes the whole publish record — the timestamp and every recorded
    URL — while the hashes stay (R-010/C-013)."""
    root = _install(tmp_path, commit=True)
    spec_path = _spec_with_evidence(root, {"a.txt": "aa\n"})
    evidence.write_manifest(spec_path)
    ev = evidence.evidence_dir(spec_path)
    cfg = config.load(spec_path)
    evidence._record_success(cfg, ev, {"a.txt": "https://x/a"})
    assert evidence.has_publish_success(ev)

    evidence._invalidate_success(cfg, ev)
    assert not evidence.has_publish_success(ev)
    data = json.loads((ev / "manifest.json").read_text(encoding="utf-8"))
    assert "published_at" not in data
    assert all("url" not in entry for entry in data["artifacts"])
    assert data["artifacts"][0]["hash"].startswith("sha256:")
