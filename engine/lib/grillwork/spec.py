"""Spec file creation — the deterministic scaffolding the Griller invokes (B1/B2).

Assigns the sequence number and slug, and writes the initial draft from the engine
template. The *content* (draft-and-mark, grilling) is the Griller role's job; this only
does the mechanical file creation, so the LLM never chooses a path or number.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import config, naming


def _now_stamp() -> str:
    """The current instant as an ISO-8601 UTC timestamp (seconds precision) — the value
    stamped into a spec's "Status changed" row when its status is set."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_spec(start: Path, title: str) -> dict:
    """Create a new draft spec from ``title``; return its seq, slug, id, and path."""
    cfg = config.load(start)
    cfg.spec_home_path.mkdir(parents=True, exist_ok=True)

    seq = naming.next_sequence(cfg.spec_home_path)
    slug = naming.slugify(title)
    spec_id = f"{seq}-{slug}"
    spec_dir = cfg.spec_home_path / naming.spec_dirname(seq, slug)
    if spec_dir.exists():
        raise FileExistsError(f"{spec_dir} already exists")
    spec_dir.mkdir(parents=True)
    path = spec_dir / naming.SPEC_FILENAME

    template = cfg.spec_template_path
    if not template.exists():
        raise FileNotFoundError(
            f"no spec template at {template} — the installed method is incomplete; "
            "re-run the install by pointing your agent at Grillwork's INSTALL.md"
        )
    content = (
        template.read_text(encoding="utf-8")
        .replace("{{TITLE}}", title)
        .replace("{{ID}}", spec_id)
        .replace("{{STATUS_CHANGED}}", _now_stamp())  # the drafting status's change time
    )
    path.write_text(content, encoding="utf-8")
    return {"seq": seq, "slug": slug, "id": spec_id, "path": str(path)}


def record_finding(spec_path: Path, gap: str, why: str, phase: str | None = None) -> dict:
    """Append a learning-loop finding to the spec's findings.md; return {path, count}.

    A finding is a post-Ready shortfall — a gap that had to be asked after the spec was
    approved, with the *why*. It is the raw material the curator distills across specs into
    settings/improvements.md, so the Griller can pre-empt the gap-class next time. Recording
    is a deterministic append (structured one line per finding) so the format never drifts and
    the LLM never hand-formats the log.
    """
    p = Path(spec_path)
    findings = p.with_name(naming.FINDINGS_FILENAME)
    if not findings.exists():
        findings.write_text(
            f"# Findings — {p.parent.name}\n\n"
            "Post-Ready shortfalls: gaps that had to be asked after the spec was approved, with\n"
            "the why. Raw material for the learning loop's curate step "
            "(→ settings/improvements.md).\n\n",
            encoding="utf-8",
        )
    tail = f" · **phase:** {phase}" if phase else ""
    with findings.open("a", encoding="utf-8") as fh:
        fh.write(f"- **gap:** {gap} · **why:** {why}{tail}\n")
    count = sum(1 for line in findings.read_text(encoding="utf-8").splitlines() if line.startswith("- "))
    return {"path": str(findings), "count": count}


def spec_status(path: Path, new: str | None = None, changed_at: str | None = None) -> dict:
    """Read the spec's status, or set it when ``new`` is given.

    Returns ``{"path", "status"}`` on a read and additionally ``"previous"`` and ``"changed_at"``
    on a set. Setting a status stamps the transition time into the spec's "Status changed" row;
    ``changed_at`` defaults to the current instant (callers, chiefly tests, may pass a fixed
    value). The lifecycle transition itself (who may move approved->building) is the roles'
    responsibility; this only performs the deterministic header edit so the LLM never rewrites
    the row by hand.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    current = naming.read_status(text)
    if new is None:
        return {"path": str(p), "status": current}
    stamp = changed_at or _now_stamp()
    p.write_text(naming.set_status(text, new, stamp), encoding="utf-8")
    return {"path": str(p), "status": new, "previous": current, "changed_at": stamp}
