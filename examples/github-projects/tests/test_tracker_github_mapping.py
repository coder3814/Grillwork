"""The map-driven projection: the settings' map places the card, never a name match.

The board bound here has columns named nothing like the lifecycle stages (`Todo` /
`In Progress` / `Done`, plus one column no stage maps to), so an implementation that placed a
card by matching the stage's *name* to an option name cannot pass. Several stages collapse onto
one column, and the issue's open/closed state keys on the `closed` **stage**, not on the column
it shares.

Every assertion reads observable board state (which option the item's chosen field carries, its
open/closed state), never which client method was called.
"""

from __future__ import annotations

import github_projects
import pytest
from harness_engine import new_spec, set_status

STAGE_FIELD = "Stage"
# A NON-conforming board: three workflow columns, none named after a lifecycle stage, plus
# `Icebox` — a column no stage maps to, which must never be written.
STAGE_OPTIONS = ["Todo", "In Progress", "Done", "Icebox"]
# The settings' map: seven stages collapsed onto three columns. Declared in lifecycle order so
# a walk over it is a walk through the lifecycle.
COLLAPSED_MAP = {
    "drafting": "Todo",
    "ready": "Todo",
    "approved": "Todo",
    "building": "In Progress",
    "verified": "In Progress",
    "accepted": "Done",
    "closed": "Done",
}


@pytest.fixture
def collapsed(spec_repo, fake_board, harness_settings):
    """A harness bound to the non-conforming board with the collapsed map."""
    fake_board.fields = {STAGE_FIELD: list(STAGE_OPTIONS)}
    return harness_settings(spec_repo, field=STAGE_FIELD, mapping=COLLAPSED_MAP)


def _sync(path, settings):
    github_projects.sync_spec(path, settings)


def _record(fake_board, spec_id):
    """The spec's one board record. Asserted (not indexed) so a spec that never made it onto
    the board reads as a named failure rather than a KeyError."""
    assert spec_id in fake_board.issues, f"no board card for {spec_id}"
    return fake_board.issues[spec_id]


def _option(fake_board, spec_id, field=STAGE_FIELD):
    """The option the spec's board item carries on ``field`` — None if the field was never set."""
    return _record(fake_board, spec_id)["fields"].get(field)


def test_status_maps_to_option(spec_repo, fake_board, collapsed):
    """Each stage lands on the option the MAP assigns it, on the chosen field. The board has no
    column named after any stage, so only the map can place the card. Collapse is honored:
    `building` and `verified` both land on the shared "In Progress" — including two specs
    sitting there at once — and `Icebox`, which no stage maps to, is never written."""
    alpha, alpha_id = new_spec(spec_repo, "Alpha")

    for stage, option in COLLAPSED_MAP.items():
        set_status(alpha, stage)
        _sync(alpha, collapsed)
        assert _option(fake_board, alpha_id) == option, stage

    bravo, bravo_id = new_spec(spec_repo, "Bravo")
    set_status(alpha, "building")
    _sync(alpha, collapsed)
    set_status(bravo, "verified")
    _sync(bravo, collapsed)
    assert COLLAPSED_MAP["building"] == COLLAPSED_MAP["verified"] == "In Progress"
    assert _option(fake_board, alpha_id) == "In Progress"
    assert _option(fake_board, bravo_id) == "In Progress"

    # A column no stage maps to is never touched.
    assert "Icebox" not in {record["fields"].get(STAGE_FIELD) for record in fake_board.issues.values()}


def test_new_spec_mapped(spec_repo, fake_board, collapsed):
    """A brand-new spec's card carries the option mapped to `drafting` ("Todo"), on the chosen
    field: exactly one card, on the project, open, its body carrying the spec id."""
    path, sid = new_spec(spec_repo, "Alpha Feature")
    _sync(path, collapsed)

    assert len(fake_board.issues_for(sid)) == 1
    record = _record(fake_board, sid)
    assert record["fields"] == {STAGE_FIELD: COLLAPSED_MAP["drafting"]}  # only the chosen field
    assert record["open"] is True
    assert record["on_project"] is True
    assert sid in record["body"]


def test_close_by_state(spec_repo, fake_board, collapsed):
    """The issue's open/closed state follows the `closed` STAGE, not the column. With `accepted`
    and `closed` collapsed onto the same option ("Done"), a spec at `accepted` has an OPEN issue
    and a spec at `closed` a CLOSED one — both carrying that same shared option. And leaving
    `closed` reopens the issue while the card stays on "Done"."""
    assert COLLAPSED_MAP["accepted"] == COLLAPSED_MAP["closed"] == "Done"  # the collapse under test

    alpha, alpha_id = new_spec(spec_repo, "Alpha")
    bravo, bravo_id = new_spec(spec_repo, "Bravo")
    set_status(alpha, "accepted")
    _sync(alpha, collapsed)
    set_status(bravo, "closed")
    _sync(bravo, collapsed)

    accepted, closed = _record(fake_board, alpha_id), _record(fake_board, bravo_id)
    assert accepted["fields"].get(STAGE_FIELD) == "Done"  # same column ...
    assert closed["fields"].get(STAGE_FIELD) == "Done"
    assert accepted["open"] is True                       # ... different issue state
    assert closed["open"] is False

    # Leaving `closed` reopens the issue; the column is unchanged (both stages map to "Done").
    set_status(bravo, "accepted")
    _sync(bravo, collapsed)
    assert _record(fake_board, bravo_id)["open"] is True
    assert _option(fake_board, bravo_id) == "Done"
