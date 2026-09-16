"""Phase 2 — the deterministic naming helpers are pure, so they are tested directly."""

import pytest
from grillwork import naming


def test_next_sequence_empty(tmp_path):
    assert naming.next_sequence(tmp_path) == "001"


def test_next_sequence_increments_past_highest(tmp_path):
    (tmp_path / "001-alpha").mkdir()
    (tmp_path / "007-bravo").mkdir()
    (tmp_path / "not-a-spec").mkdir()
    (tmp_path / "009-loose-file.md").write_text("x")  # files are ignored; only dirs count
    assert naming.next_sequence(tmp_path) == "008"


def test_next_sequence_missing_dir(tmp_path):
    assert naming.next_sequence(tmp_path / "nope") == "001"


def test_slugify():
    assert naming.slugify("Let users export their data as CSV") == "let-users-export-their-data-as-csv"
    assert naming.slugify("  Fix: the __broken__ thing!!  ") == "fix-the-broken-thing"
    assert naming.slugify("???") == "spec"


def test_spec_dirname():
    assert naming.spec_dirname("003", "export-csv") == "003-export-csv"


def test_build_branch_name():
    # Engine-namespaced under grillwork/build/, derived from the spec's <NNN>-slug folder — the
    # single name the Builder creates, approve merges, and close deletes.
    assert naming.build_branch_name("specs/006-github-projects/spec.md") == "grillwork/build/006-github-projects"


def test_markers():
    text = "intro [GAP G-001: max file size?] middle [GAP G-002: on empty input?] end"
    assert naming.find_markers(text) == [("G-001", "max file size?"), ("G-002", "on empty input?")]
    assert naming.find_markers("none") == []


def test_markers_span_newlines():
    # A marker wrapped across a line break must still be found, or `grillwork markers`
    # could report zero open markers while a human-visible GAP remains.
    text = "before [GAP G-001: what happens\non empty input?] after"
    assert naming.find_markers(text) == [("G-001", "what happens\non empty input?")]


def test_marker_template_reference_does_not_match():
    # The literal template reference in role docs uses G-### (no digits) and must never
    # be counted as an open marker.
    assert naming.find_markers("[GAP G-###: what is missing]") == []


_HEADER ="# Spec: X\n\n| | |\n|---|---|\n| **ID** | 001-x |\n| **Status** | accepted |\n"


def test_read_status():
    assert naming.read_status(_HEADER) == "accepted"
    assert naming.read_status("no status row here") is None


def test_read_status_changed_absent_is_none():
    # A spec authored before the field existed has no "Status changed" row.
    assert naming.read_status_changed(_HEADER) is None


_TS = "2026-07-12T19:24:56+00:00"


def test_set_status_round_trips_and_preserves_row_shape():
    out = naming.set_status(_HEADER, "building", _TS)
    assert naming.read_status(out) == "building"
    # Only the value changed; the surrounding table scaffolding is intact.
    assert "| **Status** | building |" in out
    assert "| **ID** | 001-x |" in out
    # The transition stamps a companion "Status changed" row (inserted here, since _HEADER
    # has none), directly beneath the Status row.
    assert "| **Status** | building |\n| **Status changed** | 2026-07-12T19:24:56+00:00 |" in out
    assert naming.read_status_changed(out) == _TS


def test_set_status_overwrites_status_changed_never_accumulates():
    # The stamp is the *current* status's change time — a later transition overwrites it, so
    # the header never grows a running history of past statuses.
    once = naming.set_status(_HEADER, "building", "2026-01-01T00:00:00+00:00")
    twice = naming.set_status(once, "verified", "2026-02-02T00:00:00+00:00")
    assert twice.count("**Status changed**") == 1  # one row, overwritten in place
    assert naming.read_status(twice) == "verified"
    assert naming.read_status_changed(twice) == "2026-02-02T00:00:00+00:00"
    assert "2026-01-01T00:00:00+00:00" not in twice


def test_set_status_rejects_unknown_value():
    # A typo must fail loud rather than write a nonsense status into the header.
    with pytest.raises(ValueError):
        naming.set_status(_HEADER, "in-dev", _TS)


def test_set_status_requires_a_status_row():
    with pytest.raises(ValueError):
        naming.set_status("# Spec with no status row", "closed", _TS)
