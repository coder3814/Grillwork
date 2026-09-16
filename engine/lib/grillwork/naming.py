"""Deterministic naming helpers — sequence numbers, slugs, IDs, and markers.

Pure functions over text and directory listings. The grilling prompts call these (never
improvising a path or an ID themselves), so their behavior must be exact and testable.
"""

from __future__ import annotations

import re
from pathlib import Path

_SEQ_RE = re.compile(r"^(\d{3,})-")
# The description part uses [^\]]*? (not .*?) so it spans newlines — a marker wrapped
# across lines is still matched. A literal `]` still terminates the description.
_MARKER_RE = re.compile(r"\[GAP\s+(G-\d+)(?::\s*([^\]]*?))?\]")
# The Status row in the spec header table: `| **Status** | <value> |`. Groups 1 and 3 are
# the row scaffolding kept verbatim on a set; group 2 is the value.
_STATUS_RE = re.compile(r"(\|\s*\*\*Status\*\*\s*\|\s*)([^|]*?)(\s*\|)")
# The companion "Status changed" row: `| **Status changed** | <timestamp> |`. Same shape as
# the Status row; disjoint from _STATUS_RE (that one requires the literal `**Status**`).
_STATUS_CHANGED_RE = re.compile(r"(\|\s*\*\*Status changed\*\*\s*\|\s*)([^|]*?)(\s*\|)")

# The spec lifecycle, in order — one status field flowing like a board card from a drafted
# spec all the way to landed. The spec loop owns drafting->ready->approved; the development
# loop owns building->verified->accepted; `closed` is the finalize step (`/grillwork-close`):
# the accepted change is published to the shared remote and its isolated build branch/worktree
# are cleaned up. (Production deployment stays a separate, deferred Environments concern.) A
# single ordered source so the status helper can reject an unknown value (a typo must fail
# loud, not corrupt the header).
#
# The two human words face opposite directions, and the lifecycle uses each the way ordinary
# usage does: **approval authorizes work that has not happened yet** (approved plans, approved
# requirements), **acceptance takes delivery of work already made** (acceptance testing, the
# client accepted the work). So the spec is approved and the built result is accepted — which
# also keeps the spec's *acceptance criteria* pointing at the thing they actually judge.
#   drafting  - Griller authoring; gaps open
#   ready     - passed independent DoR review
#   approved  - human approved the spec -> work may start  (human touchpoint 1)
#   building  - Builder orchestrating the change on an isolated build branch
#   verified  - passed DoD review: verified and merge-ready (not merged)
#   accepted  - human accepted the result -> merges onto the integration target (human touchpoint 2)
#   closed    - the merge is published to the remote and the build branch/worktree cleaned up
# A rejection needs no special status: it returns the card to the working state it came from
# (a failed/declined spec -> drafting; a failed/declined build -> building), with the reason
# recorded in findings.md / the Amendments record.
SPEC_STATUSES = ("drafting", "ready", "approved", "building", "verified", "accepted", "closed")


def next_sequence(spec_home: Path) -> str:
    """Next zero-padded 3-digit sequence number by scanning ``<NNN>-*/`` dirs in spec_home."""
    highest = 0
    spec_home = Path(spec_home)
    if spec_home.is_dir():
        for p in spec_home.iterdir():
            if not p.is_dir():
                continue
            m = _SEQ_RE.match(p.name)
            if m:
                highest = max(highest, int(m.group(1)))
    return f"{highest + 1:03d}"


def slugify(title: str) -> str:
    """Filename-safe slug from a human title (the agreed spec title)."""
    s = title.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "spec"


def spec_dirname(seq: str, slug: str) -> str:
    """The per-spec folder name: ``003`` + ``export-csv`` -> ``003-export-csv``."""
    return f"{seq}-{slug}"


# The three files that live inside a per-spec folder (the folder itself carries the number and
# slug, so these names are fixed).
#   SPEC_FILENAME     - the spec
#   TASKS_FILENAME    - the derived task-list companion
#   FINDINGS_FILENAME - the learning-loop raw log: one line per post-Ready shortfall (a gap that
#                       had to be asked, with the why). Curated across specs into
#                       settings/improvements.md.
SPEC_FILENAME = "spec.md"
TASKS_FILENAME = "tasks.md"
FINDINGS_FILENAME = "findings.md"


def build_branch_name(spec_path: Path) -> str:
    """The isolated build branch for a spec: engine-namespaced under ``grillwork/build/``, one
    per spec, derived from the spec's folder (which carries the unique ``<NNN>-slug``).

    A single source of truth so the three commands that touch it agree on the exact name: the
    Builder creates it off the integration target's tip, ``grillwork-accept`` merges it, and
    ``grillwork-close`` deletes it. The ``grillwork/`` prefix namespaces engine-created branches
    so cleanup never touches an adopter's own."""
    return f"grillwork/build/{Path(spec_path).parent.name}"


def find_markers(text: str) -> list[tuple[str, str]]:
    """All ``[GAP G-###: description]`` markers as (id, description) pairs, in order."""
    return [(m.group(1), (m.group(2) or "").strip()) for m in _MARKER_RE.finditer(text)]


def read_status(text: str) -> str | None:
    """The spec's declared status from its header table, or None if the row is absent."""
    m = _STATUS_RE.search(text)
    return m.group(2).strip() if m else None


def set_status(text: str, new: str, changed_at: str) -> str:
    """Return ``text`` with the Status row set to ``new`` and its companion "Status changed"
    row stamped with ``changed_at`` — the instant of this transition.

    The stamp records only the *current* status's change time: it is overwritten on every
    transition, never accumulated into a history. When the "Status changed" row is absent (a
    spec authored before this field existed), it is inserted directly beneath the Status row, so
    the stamp is always present after a transition.

    Raises ``ValueError`` on an unknown status (typos must fail loud, never corrupt the
    header) or when no Status row is present.
    """
    if new not in SPEC_STATUSES:
        raise ValueError(f"unknown spec status '{new}' (expected one of: {', '.join(SPEC_STATUSES)})")
    if not _STATUS_RE.search(text):
        raise ValueError("no Status row found in the spec header")
    text = _STATUS_RE.sub(lambda m: f"{m.group(1)}{new}{m.group(3)}", text, count=1)
    return _stamp_status_changed(text, changed_at)


def read_status_changed(text: str) -> str | None:
    """The instant the spec's current status was set, from its "Status changed" header row, or
    None if the row is absent (a spec authored before this field existed)."""
    m = _STATUS_CHANGED_RE.search(text)
    return m.group(2).strip() if m else None


def _stamp_status_changed(text: str, changed_at: str) -> str:
    """Overwrite the "Status changed" row's value, or insert the row directly beneath the
    Status row when absent. Assumes a Status row is present (``set_status`` has checked)."""
    if _STATUS_CHANGED_RE.search(text):
        return _STATUS_CHANGED_RE.sub(
            lambda m: f"{m.group(1)}{changed_at}{m.group(3)}", text, count=1
        )
    return _STATUS_RE.sub(
        lambda m: f"{m.group(0)}\n| **Status changed** | {changed_at} |", text, count=1
    )
