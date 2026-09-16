"""The acceptance package (spec 009) — the neutral model a binding renders.

Spec 009 makes the account of a change readable in one place, so a person can accept it or
send it back by reading that account alone (R-001). The *model* is engine content, neutral by
construction; *rendering* it — into an issue body, a page, a message — belongs to whatever the
adopter wired at the engine's boundary, never here (spec 010 R-013).

- :func:`build_model` — the neutral package model, a **pure function of the spec directory**
  (``spec.md`` + sibling ``findings.md`` + ``evidence/`` + ``evidence/bundle.md``). It carries
  no markdown, no HTML, and no URLs: the lifecycle state, the seven parts' content, the base and
  candidate SHAs, the evidence rows (criterion, shows, and the spec-dir-relative artifact refs
  exactly as the bundle wrote them), and the degenerate-content flags. The worked example under
  ``examples/github-projects/`` renders this same model into a GitHub issue body; the engine
  forms no URLs of its own.

``evidence/bundle.md`` (R-002) carries four fixed sections this module parses: ``## What was
done`` (part 2), ``## Revisions`` (``Base:`` / ``Candidate:`` SHAs — feeding the diff link and
every SHA-pinned artifact link), ``## Evidence map`` (a ``Criterion | Shows | Artifact(s)`` table,
one row per acceptance criterion; artifact cells are spec-dir-relative ``evidence/<name>`` paths),
and ``## Verdict`` (appended by the DoD-Reviewer at the ``verified`` flip; absent until then).

The model never raises (C-008): a missing artifact, an empty ``evidence/``, an absent or
incomplete bundle are reported as content and flags, and a renderer turns them into its own
explicit notes. Every parser this model needs is written here over ``naming`` and stdlib alone,
so it carries no dependency on any rendering binding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import naming

# The four wireframe lifecycle states, keyed by the spec status. The wireframe governs which
# statuses share a state (its "State A/B/C/D" headings); an unknown/absent status is the lean
# State A (nothing reviewed to show).
_STATE_BY_STATUS = {
    "drafting": "A", "approved": "A", "building": "A",
    "ready": "B",
    "verified": "C",
    "accepted": "D", "closed": "D",
}

# The bundle's four fixed sections, in the order R-002 lists them; the required set at
# ``verified`` and later (until the Verdict is appended the package cannot compose part 4).
_BUNDLE_SECTIONS = ("What was done", "Revisions", "Evidence map", "Verdict")


@dataclass(frozen=True)
class Artifact:
    """One evidence artifact as the bundle's Evidence-map cell wrote it. ``ref`` is the
    spec-dir-relative ``evidence/<name>`` path, verbatim; ``present`` is whether that file
    exists on disk under the spec directory (False drives the missing-artifact note, C-008)."""

    ref: str
    present: bool


@dataclass(frozen=True)
class EvidenceRow:
    """One acceptance criterion's evidence: the criterion id, what its artifacts show (the
    bundle cell's own words — never inferred), and its artifact refs."""

    criterion: str
    shows: str
    artifacts: tuple[Artifact, ...]


@dataclass(frozen=True)
class Package:
    """The neutral acceptance-package model — the seven parts plus the degenerate-content flags,
    with no rendering baked in. Whatever the adopter wired renders it; this is the whole of what
    the engine forms (R-006)."""

    state: str                              # wireframe lifecycle state: "A" | "B" | "C" | "D"
    status: str                             # the raw spec status
    summary: str                            # part 1 — the spec's `## Summary` (may be "")
    what_was_done: str | None               # part 2 — bundle `## What was done` (None if absent)
    evidence: tuple[EvidenceRow, ...]       # part 3 — one row per criterion (empty = no artifacts)
    evidence_map_present: bool              # whether the bundle's `## Evidence map` section exists
    verdict: str | None                     # part 4 — bundle `## Verdict` (None until appended)
    base_sha: str | None                    # from bundle `## Revisions`
    candidate_sha: str | None               # from bundle `## Revisions` (the pin for every link)
    findings: str | None                    # part 6 — findings.md content (None when absent/empty)
    amendments: tuple[tuple[str, str, str], ...]  # part 7 — (version, date, description) rows
    bundle_present: bool                    # whether evidence/bundle.md exists at all
    missing_sections: tuple[str, ...]       # required bundle sections absent at this state


# --- section / table parsers (over spec.md and evidence/bundle.md) ------------------------


def _section(text: str, heading: str) -> str | None:
    """The inner body of a ``## <heading>`` section — from the heading line to the next ``## ``
    heading or EOF; None when the heading is absent. Mirrors the readers the other engine
    modules use, reimplemented here so the compose seam depends on no binding."""
    m = re.search(
        rf"^##[ \t]+{re.escape(heading)}[ \t]*$\n?(.*?)(?=^##[ \t]|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return m.group(1) if m else None


def _clean(body: str | None) -> str | None:
    """A section body with HTML comments removed and surrounding whitespace stripped; None when
    the section was absent or held nothing but whitespace/comments."""
    if body is None:
        return None
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
    return body or None


def _table_rows(section: str) -> list[list[str]]:
    """The data rows of a pipe table in ``section`` — every ``| … |`` line, split into trimmed
    cells, with the header row and the ``|---|`` separator dropped. A row shorter than the header
    is ignored (defensive against a malformed table)."""
    rows: list[list[str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        first = cells[0] if cells else ""
        if first.lower() in ("criterion", "version"):  # the header row
            continue
        if first and set(first) <= {"-", ":"}:  # the |---| separator row
            continue
        rows.append(cells)
    return rows


def _line_value(section: str, label: str) -> str | None:
    """The value of a ``<label>: <value>`` line in ``section`` (used for the Revisions SHAs);
    None when the line is absent."""
    m = re.search(rf"(?mi)^\s*{re.escape(label)}\s*:\s*(\S+)", section)
    return m.group(1) if m else None


def _evidence_rows(bundle: str, spec_dir: Path) -> list[EvidenceRow] | None:
    """The Evidence-map rows (part 3). None when the ``## Evidence map`` section is absent (a
    bundle-incomplete condition); an empty list when the section is present but carries no data
    row (an empty ``evidence/`` — the "no artifacts" case). Each artifact ref is the cell exactly
    as written; ``present`` records whether the file exists under ``spec_dir``."""
    section = _section(bundle, "Evidence map")
    if section is None:
        return None
    rows: list[EvidenceRow] = []
    for cells in _table_rows(section):
        if len(cells) < 3:
            continue
        criterion, shows, artifacts_cell = cells[0], cells[1], cells[2]
        artifacts = tuple(
            Artifact(ref=ref, present=(spec_dir / ref).is_file())
            for ref in artifacts_cell.split()
        )
        rows.append(EvidenceRow(criterion=criterion, shows=shows, artifacts=artifacts))
    return rows


def _amendments(spec_text: str) -> tuple[tuple[str, str, str], ...]:
    """The spec's amendment history (part 7) as (version, date, description) rows, including the
    initial row. Empty only when the section is absent; a single row means "unchanged"."""
    section = _section(spec_text, "Amendments")
    if section is None:
        return ()
    return tuple(
        (cells[0], cells[1], cells[2]) for cells in _table_rows(section) if len(cells) >= 3
    )


def _findings(spec_dir: Path) -> str | None:
    """The build's findings.md content (part 6); None when the file is absent or empty (→ the
    "none recorded" note, C-008)."""
    path = spec_dir / naming.FINDINGS_FILENAME
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return content if content.strip() else None


# --- the neutral model (R-002) -----------------------------------------------------------


def build_model(spec_path: Path) -> Package:
    """The acceptance-package model for the spec at ``spec_path`` — a pure function of the spec
    directory (``spec.md`` and its ``findings.md`` / ``evidence/`` siblings). Reads every part
    from disk and reports the degenerate cases as flags; forms no markdown and no URLs, so both
    bindings render the same model (R-006)."""
    spec_path = Path(spec_path)
    spec_dir = spec_path.parent
    try:
        spec_text = spec_path.read_text(encoding="utf-8")
    except OSError:
        spec_text = ""

    status = naming.read_status(spec_text) or ""
    state = _STATE_BY_STATUS.get(status, "A")
    summary = _clean(_section(spec_text, "Summary")) or ""

    bundle_path = spec_dir / "evidence" / "bundle.md"
    try:
        bundle = bundle_path.read_text(encoding="utf-8")
        bundle_present = True
    except OSError:
        bundle = ""
        bundle_present = False

    what_was_done = _clean(_section(bundle, "What was done"))
    revisions = _section(bundle, "Revisions") or ""
    base_sha = _line_value(revisions, "Base")
    candidate_sha = _line_value(revisions, "Candidate")
    rows = _evidence_rows(bundle, spec_dir)
    evidence_map_present = rows is not None
    verdict = _clean(_section(bundle, "Verdict"))

    # Which required bundle sections are absent — what the compose step turns into per-part
    # bundle-incomplete notes at `verified`/later (C-008). Revisions counts as present only when
    # both SHAs are readable, since a half-written Revisions cannot pin a link.
    present = {
        "What was done": what_was_done is not None,
        "Revisions": base_sha is not None and candidate_sha is not None,
        "Evidence map": evidence_map_present,
        "Verdict": verdict is not None,
    }
    missing_sections = tuple(name for name in _BUNDLE_SECTIONS if not present[name])

    return Package(
        state=state,
        status=status,
        summary=summary,
        what_was_done=what_was_done,
        evidence=tuple(rows or ()),
        evidence_map_present=evidence_map_present,
        verdict=verdict,
        base_sha=base_sha,
        candidate_sha=candidate_sha,
        findings=_findings(spec_dir),
        amendments=_amendments(spec_text),
        bundle_present=bundle_present,
        missing_sections=missing_sections,
    )


# --- the model as JSON (the harness seam) ------------------------------------------------


def to_json_dict(model: Package) -> dict:
    """The same model as plain JSON-able data — what `grillwork package <spec>` prints.

    The model is engine content and rendering it is the adopter's, so the boundary between them
    has to be reachable from *any* language: a harness written in PowerShell or Node can no more
    import this dataclass than it can import the rest of the engine. This is the whole of the
    translation — field for field, `None` becoming `null` — so a binding never re-derives from
    the spec files what the engine already read."""
    return {
        "state": model.state,
        "status": model.status,
        "summary": model.summary,
        "what_was_done": model.what_was_done,
        "evidence": [
            {
                "criterion": row.criterion,
                "shows": row.shows,
                "artifacts": [
                    {"ref": a.ref, "present": a.present} for a in row.artifacts
                ],
            }
            for row in model.evidence
        ],
        "evidence_map_present": model.evidence_map_present,
        "verdict": model.verdict,
        "base_sha": model.base_sha,
        "candidate_sha": model.candidate_sha,
        "findings": model.findings,
        "amendments": [
            {"version": version, "date": date, "description": description}
            for version, date, description in model.amendments
        ],
        "bundle_present": model.bundle_present,
        "missing_sections": list(model.missing_sections),
    }
