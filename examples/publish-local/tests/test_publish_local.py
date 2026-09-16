"""The publish protocol, as an adopter's publisher has to implement it.

`publish-evidence` is the one awaited event: the engine reads this command's exit code as the
success, parses its stdout for `<artifact-name> <url>` pairs, and records them in the spec's
`evidence/manifest.json`. That record is later what permits the artifact bytes to be pruned
from the repo — so the protocol has real consequences, and a worked example is only worth
copying if its behavior is pinned.

These tests drive the real script (no fakes: it publishes to a real temporary directory) and
assert only on what the engine can actually observe — exit code, stdout, stderr, and what ended
up on disk. Any other implementation of the same protocol passes them. Each fails under its own
negation: a published account file, a progress line on stdout, a dry run that wrote, a partial
failure reported as success.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import publish
import pytest


def _payload(spec, **overrides):
    """The engine's publish payload, plus whatever a test varies."""
    env = {"GRILLWORK_EVENT": "publish-evidence", "GRILLWORK_SPEC_PATH": str(spec)}
    env.update({k: str(v) for k, v in overrides.items()})
    return env


def _pairs(stdout):
    """Stdout parsed the way the engine parses it: every non-blank line must be exactly a
    name/URL pair, or the engine drops it with a warning and the URL is lost."""
    pairs = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        assert len(parts) == 2, f"stdout line is not an `<artifact-name> <url>` pair: {line!r}"
        pairs[parts[0]] = parts[1]
    return pairs


def test_it_publishes_the_artifacts_and_reports_their_urls(bundle, tmp_path, capsys):
    """The whole point: every artifact lands at the destination, and every one is reported on
    stdout as a pair the engine can record."""
    destination = tmp_path / "published"

    code = publish.main(_payload(bundle, GRILLWORK_PUBLISH_DIR=destination))

    assert code == 0
    reported = _pairs(capsys.readouterr().out)
    assert set(reported) == {"C-001-suite.log", "C-002-manual.log", "screenshot.png"}
    for name, url in reported.items():
        landed = Path(url2pathname(urlparse(url).path))
        assert landed.is_file(), f"{name} was reported at {url}, which is not there"
        assert landed.read_text(encoding="utf-8") == f"contents of {name}\n"


def test_the_account_files_are_not_artifacts(bundle, tmp_path, capsys):
    """`bundle.md`, `manifest.json` and `.gitignore` are the change's textual record, not bytes
    to publish — and `manifest.json` is where the engine writes the URLs this run reports, so
    publishing it would be reporting the record as its own subject."""
    destination = tmp_path / "published"

    publish.main(_payload(bundle, GRILLWORK_PUBLISH_DIR=destination))

    published = {path.name for path in (destination / "007-a-spec").iterdir()}
    assert published.isdisjoint({"bundle.md", "manifest.json", ".gitignore"})


def test_stdout_carries_the_protocol_and_nothing_else(bundle, tmp_path, capsys):
    """Progress belongs on stderr. A publisher that lets its uploader talk to stdout loses the
    URLs it meant to report — the engine drops every line that is not a pair."""
    publish.main(_payload(bundle, GRILLWORK_PUBLISH_DIR=tmp_path / "published"))

    captured = capsys.readouterr()
    _pairs(captured.out)  # raises if any line is not a pair
    assert "published 3 artifact(s)" in captured.err


def test_a_dry_run_publishes_nothing(bundle, tmp_path, capsys):
    """What `fire-hooks publish-evidence` proves: the command runs and the bundle is readable.
    Nothing is written and no URL is claimed, because none exists."""
    destination = tmp_path / "published"

    code = publish.main(_payload(bundle, GRILLWORK_PUBLISH_DIR=destination, GRILLWORK_DRY_RUN="1"))

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    assert "dry run" in captured.err
    assert not destination.exists()


def test_a_dry_run_survives_the_synthetic_payload(adopter_repo, capsys):
    """The rehearsal as the engine really fires it. `fire-hooks publish-evidence` invents its
    payload and points `GRILLWORK_SPEC_PATH` at a spec that does not exist — a hook must
    tolerate a vanished path anyway — so a publisher that runs its real checks first fails the
    one run that exists to prove it works. Worse, it fails silently: the rehearsal is spawned
    detached, so nobody reads the exit code, and the adopter who copied the ordering learns
    nothing until a real publish is skipped.

    The invented path is deliberately not created here: that absence is the whole test."""
    invented = adopter_repo / ".grillwork" / "specs" / "000-grillwork-dry-run" / "spec.md"
    assert not invented.exists()

    code = publish.main(_payload(invented, GRILLWORK_DRY_RUN="1"))

    captured = capsys.readouterr()
    assert code == 0, f"the dry run failed the rehearsal: {captured.err!r}"
    assert captured.out == ""
    assert "dry run" in captured.err
    assert not (adopter_repo / ".grillwork" / "published").exists()


def test_a_dry_run_needs_no_payload_at_all(capsys):
    """The floor: a rehearsal reports and succeeds even with nothing to go on. Every publisher
    check is a check against invented input here, so none of them may decide the exit code."""
    code = publish.main({"GRILLWORK_EVENT": "publish-evidence", "GRILLWORK_DRY_RUN": "1"})

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert captured.out == ""
    assert "dry run" in captured.err


def test_the_destination_is_derived_from_the_repo_when_unset(bundle, capsys):
    """Unconfigured, the destination is found from the **spec path** — the hook fires from the
    build's worktree, so the working directory is not the repo and cannot be used."""
    publish.main(_payload(bundle))

    root = bundle.parents[3]
    assert (root / ".grillwork" / "published" / "007-a-spec" / "C-001-suite.log").is_file()


def test_a_bundle_with_no_artifacts_succeeds_silently(adopter_repo, tmp_path, capsys):
    """Nothing to publish is not a failure — but it must claim no URLs either, or the engine
    would record a publish that did not happen."""
    spec_dir = adopter_repo / ".grillwork" / "specs" / "008-empty"
    (spec_dir / "evidence").mkdir(parents=True)
    spec = spec_dir / "spec.md"
    spec.write_text("# 008\n", encoding="utf-8")

    code = publish.main(_payload(spec, GRILLWORK_PUBLISH_DIR=tmp_path / "published"))

    assert code == 0
    assert capsys.readouterr().out == ""


def test_an_unwritable_destination_is_a_failure(bundle, tmp_path, capsys, monkeypatch):
    """The consequential case. A recorded success is what later permits the bytes to be
    deleted, so a publish that did not fully happen must exit nonzero and report no URLs."""

    def refuse(*args, **kwargs):
        raise OSError("destination is full")

    monkeypatch.setattr(publish.shutil, "copy2", refuse)

    code = publish.main(_payload(bundle, GRILLWORK_PUBLISH_DIR=tmp_path / "published"))

    captured = capsys.readouterr()
    assert code != 0
    assert captured.out == ""
    assert "destination is full" in captured.err


def test_another_event_is_a_no_op(bundle, tmp_path, capsys):
    """Bound where it does not belong, it does nothing and says nothing — the contract may grow
    events, and an unknown one is never this hook's business."""
    code = publish.main(
        _payload(bundle, GRILLWORK_EVENT="on-transition", GRILLWORK_PUBLISH_DIR=tmp_path / "published")
    )

    assert code == 0
    assert capsys.readouterr().out == ""
    assert not (tmp_path / "published").exists()


@pytest.mark.parametrize(
    "payload_overrides, expected",
    [
        ({"GRILLWORK_SPEC_PATH": ""}, "no GRILLWORK_SPEC_PATH"),
        ({"GRILLWORK_SPEC_PATH": "nowhere/spec.md"}, "no spec at"),
    ],
)
def test_a_missing_spec_is_reported_not_assumed(bundle, payload_overrides, expected, capsys):
    """The doorbell can name a path that is gone — a hook may outlive the worktree it fired
    from. Either way it is a failed publish, said plainly on stderr."""
    code = publish.main(_payload(bundle, **payload_overrides))

    captured = capsys.readouterr()
    assert code != 0
    assert captured.out == ""
    assert expected in captured.err
