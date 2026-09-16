"""The GitHub-binding item body — the renderer half of the acceptance package.

The **neutral** package model is engine content: ``grillwork package <spec>`` reads a spec
directory (``spec.md`` + sibling ``findings.md`` + ``evidence/`` + ``evidence/bundle.md``) and
prints a model carrying no markdown, no HTML and no URLs. Rendering that model is a *binding's*
job, and this is one binding: markdown for a GitHub issue body, with SHA-pinned github.com URLs.

It takes the model as **plain data** — the parsed JSON, exactly as the helper printed it — so
this file is a pure function of that data plus the settings, and any harness in any language
renders from the same input. Fetching it is ``engine.package`` (see ``engine.py``); it reads
``root``, ``repo`` and ``integration_target`` off the harness's settings, and it is what
:func:`github_projects.sync_spec` calls on every sync.

``evidence/bundle.md`` carries four fixed sections the model parses: ``## What was done``
(part 2), ``## Revisions`` (``Base:`` / ``Candidate:`` SHAs — feeding the diff link and every
SHA-pinned artifact link), ``## Evidence map`` (a ``Criterion | Shows | Artifact(s)`` table,
one row per acceptance criterion), and ``## Verdict`` (appended by the DoD-Reviewer at the
``verified`` flip; absent until then).

Composition never raises: a missing artifact, an empty ``evidence/``, an absent or incomplete
bundle each render an explicit note in the affected part while the rest composes.
"""

from __future__ import annotations

from pathlib import Path


def compose_body(model: dict, spec_path: Path, settings) -> str:
    """The GitHub item body (markdown) for the spec at ``spec_path``, per the four lifecycle
    states, rendered from the engine's ``model`` (the parsed ``grillwork package`` output).
    Reads ``settings.root``, ``settings.repo`` and ``settings.integration_target``.
    Before ``verified`` the item is lean (State A) or carries the awaiting-acceptance
    call-to-action (State B); at ``verified`` it carries the approve call-to-action and the full
    seven-part package (State C), which persists unchanged at ``accepted`` / ``closed``
    (State D). Never raises: a degenerate part composes to an explicit note."""
    repo_rel = _repo_rel(Path(spec_path).parent, settings.root)
    header = f"{model['summary']}\n\nStatus: {model['status']}"

    if model["state"] == "A":
        return header

    if model["state"] == "B":
        # GitHub resolves a link in an issue body against the issue URL, not the repo tree, so a
        # bare repo-relative path is not followable. Render a full blob URL on the integration
        # target (the ready spec link resolves once the trunk is pushed). The branch is the
        # configured integration target, or `HEAD` — GitHub resolves `blob/HEAD/<path>` to the
        # default branch's current line — when it is unconfigured.
        branch = getattr(settings, "integration_target", "") or "HEAD"
        spec_url = f"https://github.com/{settings.repo}/blob/{branch}/{repo_rel}/spec.md"
        cta = (
            "> ⏸ Waiting on you: this spec is Ready and awaits your acceptance.\n"
            f">   Review the spec: [{repo_rel}/spec.md]({spec_url})"
        )
        return f"{header}\n\n{cta}"

    # States C and D share one byte-identical package region; only the status line and the
    # (State-C-only) call-to-action above it differ.
    package = _render_package(model, settings.repo, repo_rel)
    if model["state"] == "C":
        cta = (
            "> ⏸ Waiting on you: the result is verified and awaits your "
            "approve-or-send-back decision."
        )
        return f"{header}\n\n{cta}\n\n{package}"
    return f"{header}\n\n{package}"


def _repo_rel(spec_dir: Path, root) -> str:
    """The repo-root-relative, forward-slashed path of the spec directory (→
    ``.grillwork/specs/<id>``) — the prefix every SHA-pinned artifact URL and the spec link are
    built on. Falls back to the directory name if it does not sit under ``root``."""
    spec_dir = Path(spec_dir).resolve()
    try:
        return spec_dir.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return spec_dir.name


def _render_package(model: dict, repo: str, repo_rel: str) -> str:
    """The seven-part State-C/D package (markdown). Sourced entirely from the model, so it is a
    pure function of the spec state and byte-identical across ``verified`` / ``accepted`` /
    ``closed``."""
    base_sha, candidate_sha = model["base_sha"], model["candidate_sha"]
    if base_sha and candidate_sha:
        compare = f"https://github.com/{repo}/compare/{base_sha}...{candidate_sha}"
        delivered = (
            f"Delivered at `{candidate_sha[:12]}` · "
            f"[base...candidate diff]({compare})"
        )
    else:
        delivered = _bundle_note(model, "`## Revisions`")

    findings = model["findings"]
    parts = [
        "## What was done\n\n" + (model["what_was_done"] or _bundle_note(model, "`## What was done`")),
        delivered,
        "## Evidence\n\n" + _render_evidence(model, repo, repo_rel),
        "## Verdict\n\n" + (model["verdict"] or _bundle_note(model, "`## Verdict`")),
        "## Findings\n\n" + (findings.strip() if findings else "none recorded"),
        "## Amendments\n\n" + _render_amendments(model),
    ]
    return "\n\n".join(parts)


def _bundle_note(model: dict, section: str) -> str:
    """The explicit note a bundle-sourced part renders when it cannot compose — the whole bundle
    absent, or the required ``section`` missing. Names ``bundle`` and its incompleteness so a
    reader (and the tests) can see the part is deliberately unavailable, not silently dropped."""
    if not model["bundle_present"]:
        return "_The evidence bundle (`evidence/bundle.md`) is missing, so this part is unavailable._"
    return (
        "_The evidence bundle (`evidence/bundle.md`) is incomplete — its "
        f"{section} section is missing, so this part is unavailable._"
    )


def _render_evidence(model: dict, repo: str, repo_rel: str) -> str:
    """Part 3 — the per-criterion evidence table, one row per acceptance criterion. An absent
    ``## Evidence map`` renders a bundle-incomplete note; a present-but-empty map (no artifacts)
    renders the no-artifacts note; otherwise each artifact is a SHA-pinned blob link, and a row
    whose file is absent renders an explicit missing-artifact note in place of the link."""
    if not model["evidence_map_present"]:
        return _bundle_note(model, "`## Evidence map`")
    if not model["evidence"]:
        return "_No artifacts are recorded for this build._"
    lines = ["| Criterion | Shows | Evidence |", "|---|---|---|"]
    for row in model["evidence"]:
        cell = _evidence_cell(row, model, repo, repo_rel)
        lines.append(f"| {row['criterion']} | {row['shows']} | {cell} |")
    return "\n".join(lines)


def _evidence_cell(row: dict, model: dict, repo: str, repo_rel: str) -> str:
    """One Evidence-table cell: each artifact as a SHA-pinned blob link at the candidate
    revision, a missing-artifact note when the file is absent on disk, or a bundle-incomplete
    note when there is no candidate SHA to pin to."""
    candidate_sha = model["candidate_sha"]
    if not candidate_sha:
        return _bundle_note(model, "`## Revisions`")
    cells = []
    for art in row["artifacts"]:
        ref = art["ref"]
        if art["present"]:
            url = f"https://github.com/{repo}/blob/{candidate_sha}/{repo_rel}/{ref}"
            cells.append(f"[{ref}]({url})")
        else:
            cells.append(f"({ref} — missing: file not found on disk)")
    return " ".join(cells) if cells else "_no artifact recorded_"


def _render_amendments(model: dict) -> str:
    """Part 7 — the spec's amendment history as a table, or the explicit note when only the
    initial row exists."""
    amendments = model["amendments"]
    if len(amendments) <= 1:
        return "none — built from version 1 unchanged"
    lines = ["| Version | Date | What changed |", "|---|---|---|"]
    for row in amendments:
        lines.append(f"| {row['version']} | {row['date']} | {row['description']} |")
    return "\n".join(lines)
