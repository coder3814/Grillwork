"""The GitHub-flavored issue body this harness renders (originally spec 009's compose suite).

The account of a change has to be readable in one place, so a person can approve it or send it
back by reading that place alone. Grillwork forms the neutral **model** (what
``grillwork package <spec>`` prints, a pure function of the spec directory); this harness turns
it into markdown for a GitHub issue. These tests drive the **real renderer against fixture
spec directories**: no fake board, no ``gh`` transport.

- ``compose.compose_body(spec_path, settings) -> str`` — the issue body, per the four
  lifecycle states. Reads **only** ``settings.root``, ``settings.repo`` and
  ``settings.integration_target`` (so these tests hand it a lightweight stand-in), forming
  SHA-pinned repo URLs:
    * evidence link = ``https://github.com/<repo>/blob/<candidate_sha>/<repo-relative path>``
      where the repo-relative path is the spec dir relative to ``settings.root`` joined with
      the bundle's ``evidence/<name>`` cell;
    * diff link (part 5) = ``https://github.com/<repo>/compare/<base_sha>...<candidate_sha>``.

``evidence/bundle.md`` (R-002) carries four fixed sections the compose parses: ``## What was
done`` (part 2 prose), ``## Revisions`` (``Base:`` / ``Candidate:`` SHAs), ``## Evidence map``
(a ``Criterion | Shows | Artifact(s)`` table, one row per acceptance criterion, artifact cell
= spec-dir-relative ``evidence/<name>``), and ``## Verdict`` (appended by the DoD-Reviewer at
the ``verified`` flip; absent until then).

Assertions are black-box: on the composed body string and its section structure — never on
renderer internals or which helper was called. A different implementation behind the same
``compose_body`` must still pass. Each test fails under its own negation (a dropped evidence
row, a branch-name link, a mixed pre-``verified`` body, a lost section on close, a silent
degenerate case).
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from harness_engine import engine, set_status


def _compose(spec_path, cfg):
    """Compose the issue body through the real renderer, from the same model the engine prints.

    The renderer takes the model as plain data, and the model is **asked for** rather than
    formed here — ``grillwork package <spec>``, one subprocess per compose. Forming it
    in-process (``package.build_model``) would have been cheaper and was what this did, but it
    imported the engine, which resolves only where an import path happens to be arranged; a
    copied harness has none. Asking is what works at any depth.

    ``compose`` is imported lazily here — never at module load — so a module-level import error
    can never abort collection for the rest of the suite."""
    import compose

    model = engine("package", str(spec_path))
    return compose.compose_body(model, spec_path, cfg)


# --- fixture constants (distinctive so assertions cannot pass by accident) ----------------

REPO = "acme/widgets"
SPEC_ID = "042-sample-feature"
# Two clearly distinct 40-hex SHAs, so "the body pins to the candidate" is a real check.
BASE = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"
CAND = "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e"
STAMP = "2026-07-19T00:00:00+00:00"

SUMMARY = "This build makes the tracked item carry the full acceptance package."
WHAT_DONE = "Composed the item body from the spec directory and the evidence bundle, neutrally."
V2_DESC = "Formalized evidence/bundle.md as the single combined on-disk record."
FINDING_LINE = "the diff-link base SHA had no on-disk source until the bundle Revisions section"

# One evidence-map row per acceptance criterion — C-001 through C-009 (mirrors the real spec).
CRITERIA = [f"C-{n:03d}" for n in range(1, 10)]

COMPARE_URL = f"https://github.com/{REPO}/compare/{BASE}...{CAND}"


# --- fixture builders ---------------------------------------------------------------------


def _bundle_md(*, base, candidate, what_done, rows, verdict):
    """Render an ``evidence/bundle.md`` with the four fixed sections (R-002). ``rows`` is a
    list of ``(criterion, shows, [artifact-relpath, ...])``; ``verdict`` None omits the
    (reviewer-appended) ``## Verdict`` section, modelling a bundle before the ``verified`` flip.
    (A bundle missing a *required* section is modelled inline by C-008's e2 case.)"""
    lines = [
        "## What was done",
        "",
        what_done,
        "",
        "## Revisions",
        "",
        f"Base: {base}",
        f"Candidate: {candidate}",
        "",
        "## Evidence map",
        "",
        "| Criterion | Shows | Artifact(s) |",
        "|---|---|---|",
    ]
    for crit, shows, arts in rows:
        lines.append(f"| {crit} | {shows} | {' '.join(arts)} |")
    if verdict is not None:
        lines += ["", "## Verdict", "", verdict]
    return "\n".join(lines) + "\n"


def _write_spec(spec_dir, *, status, summary, amendments):
    """Write a minimal, valid ``spec.md`` carrying the header the compose reads (ID, Status,
    Status changed, Type(s)), a ``## Summary`` (part 1), and a ``## Amendments`` table (part 7).
    ``amendments`` is a list of ``(version, date, desc)`` rows beyond the always-present initial
    row; an empty list leaves only the initial row (C-008's amendments-degenerate case)."""
    spec_dir.mkdir(parents=True, exist_ok=True)
    rows = ["| 1 | (initial) | Initial draft |"]
    for ver, date, desc in amendments:
        rows.append(f"| {ver} | {date} | {desc} |")
    content = (
        "# Spec: Sample Feature\n\n"
        "| | |\n|---|---|\n"
        f"| **ID** | {SPEC_ID} |\n"
        f"| **Version** | {1 + len(amendments)} |\n"
        f"| **Status** | {status} |\n"
        f"| **Status changed** | {STAMP} |\n"
        "| **Type(s)** | feature |\n\n"
        "## Summary\n\n"
        f"{summary}\n\n"
        "## Amendments\n\n"
        "| Version | Date | What changed, and the gap or rejection that drove it |\n"
        "|---|---|---|\n" + "\n".join(rows) + "\n"
    )
    spec_path = spec_dir / "spec.md"
    spec_path.write_text(content, encoding="utf-8")
    return spec_path


def _complete_verified(root, status="verified"):
    """A fully-populated spec directory: populated ``evidence/`` (one artifact per criterion),
    a complete ``evidence/bundle.md`` (all four sections; one Evidence-map row per criterion),
    a ``findings.md``, and two amendment rows. Returns the ``spec.md`` path."""
    spec_dir = root / ".grillwork" / "specs" / SPEC_ID
    ev = spec_dir / "evidence"
    ev.mkdir(parents=True)
    for crit in CRITERIA:
        (ev / f"{crit}.log").write_text(f"log artifact for {crit}\n", encoding="utf-8")
    rows = [(crit, f"shows for {crit}", [f"evidence/{crit}.log"]) for crit in CRITERIA]
    (ev / "bundle.md").write_text(
        _bundle_md(
            base=BASE,
            candidate=CAND,
            what_done=WHAT_DONE,
            rows=rows,
            verdict=(
                "DONE — disposed by the independent DoD review against the Definition of "
                f"Done, at revision {CAND}, on 2026-07-19."
            ),
        ),
        encoding="utf-8",
    )
    (spec_dir / "findings.md").write_text(
        f"# Findings — {SPEC_ID}\n\nPost-Ready shortfalls.\n\n"
        f"- **gap:** {FINDING_LINE} · **why:** compose needs a pinned base · **phase:** build\n",
        encoding="utf-8",
    )
    return _write_spec(
        spec_dir, status=status, summary=SUMMARY, amendments=[(2, "2026-07-18", V2_DESC)]
    )


def _cfg(root, repo=REPO):
    """A lightweight stand-in exposing only ``.root`` and ``.repo`` — the whole of the settings
    surface ``compose_body`` reads."""
    return SimpleNamespace(root=Path(root), repo=repo)


# --- black-box readers of the composed body -----------------------------------------------


def _section(body, heading):
    """The body of a ``## <heading>`` section in the composed markdown — from the heading line
    to the next ``## `` heading or EOF; None when absent. A read of the body's own
    wireframe-defined section structure (``## What was done`` / ``## Evidence`` / ``## Verdict``
    / ``## Findings`` / ``## Amendments``), not of any compose internal."""
    m = re.search(
        rf"^##[ \t]+{re.escape(heading)}[ \t]*$\n?(.*?)(?=^##[ \t]|\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    return m.group(1) if m else None


def _urls(body):
    """Every absolute http(s) URL in the body (link targets or bare URLs)."""
    return re.findall(r"https?://[^\s)\]<>\"']+", body)


def _link_targets(body):
    """Every markdown-link target ``[text](target)`` in the body."""
    return re.findall(r"\[[^\]]*\]\(([^)]+)\)", body)


# --- C-001 --------------------------------------------------------------------------------


def test_verified_body_carries_all_seven_parts(tmp_path):
    # At `verified`, the composed item body is the wireframe's State C: all seven package parts
    # carrying the spec's actual content, with one evidence row per acceptance criterion.
    spec_path = _complete_verified(tmp_path)
    body = _compose(spec_path, _cfg(tmp_path))

    assert "Status: verified" in body  # it is the verified body

    # Part 1 — the spec summary (what was asked).
    assert SUMMARY in body

    # Part 2 — the what-was-done account under its heading.
    what = _section(body, "What was done")
    assert what is not None, "no `## What was done` section"
    assert WHAT_DONE in what

    # Part 3 — the per-criterion evidence table: one row per acceptance criterion, none missing.
    evidence = _section(body, "Evidence")
    assert evidence is not None, "no `## Evidence` section"
    for crit in CRITERIA:
        assert crit in evidence, f"evidence row for {crit} missing"
        assert f"shows for {crit}" in evidence, f"shows-text for {crit} missing"

    # Part 4 — the DoD verdict, naming the pinned candidate revision.
    verdict = _section(body, "Verdict")
    assert verdict is not None, "no `## Verdict` section"
    assert "DONE" in verdict
    assert CAND in verdict

    # Part 5 — the base -> candidate diff link.
    assert COMPARE_URL in body

    # Part 6 — the build's findings.
    findings = _section(body, "Findings")
    assert findings is not None, "no `## Findings` section"
    assert FINDING_LINE in findings

    # Part 7 — the spec's amendment history.
    amendments = _section(body, "Amendments")
    assert amendments is not None, "no `## Amendments` section"
    assert V2_DESC in amendments


# --- C-002 --------------------------------------------------------------------------------


def test_links_pin_to_candidate_sha(tmp_path):
    # Every evidence link in a github-binding body is a SHA-pinned repo URL at the candidate
    # revision, with a repo-relative path under the spec's evidence/ — never a branch name.
    spec_path = _complete_verified(tmp_path)
    body = _compose(spec_path, _cfg(tmp_path))

    urls = _urls(body)
    blob = [u for u in urls if "/blob/" in u]
    assert blob, "no evidence (blob) links in the verified body"
    for u in blob:
        assert CAND in u, f"evidence link not pinned to the candidate SHA: {u}"
        assert REPO in u, f"evidence link not on the configured repo: {u}"
        assert f"/blob/{CAND}/" in u, f"evidence link not SHA-pinned: {u}"
        assert "/.grillwork/specs/" in u and "/evidence/" in u, f"path not under evidence/: {u}"

    # The exact repo-relative, SHA-pinned URL for a known artifact.
    expected = (
        f"https://github.com/{REPO}/blob/{CAND}"
        f"/.grillwork/specs/{SPEC_ID}/evidence/C-001.log"
    )
    assert expected in body, f"expected pinned evidence URL absent:\n{expected}"

    # No link (and nothing else) pins to the deletable build branch — a branch-name link fails.
    assert "grillwork/build/" not in body
    for target in _link_targets(body):
        assert "grillwork/build/" not in target, f"link pins to a branch name: {target}"


# --- C-003 --------------------------------------------------------------------------------

_LIFECYCLE = ["drafting", "ready", "approved", "building", "verified", "accepted", "closed"]
_STATE_A = {"drafting", "approved", "building"}
_STATE_B = {"ready"}
_STATE_C = {"verified"}
_STATE_D = {"accepted", "closed"}


def test_lifecycle_states_render_per_wireframe(tmp_path):
    # One fixture stepped through all seven statuses; each body matches its wireframe state.
    # The complete bundle/evidence/findings are present on disk the whole time, so this proves
    # the state is gated on **status**, not on file presence (the never-mixes invariant).
    spec_path = _complete_verified(tmp_path)
    cfg = _cfg(tmp_path)

    for status in _LIFECYCLE:
        set_status(spec_path, status)
        body = _compose(spec_path, cfg)
        assert SUMMARY in body, status
        assert f"Status: {status}" in body, status

        if status in _STATE_A:
            # State A: summary + status and nothing more — no CTA, no package/evidence.
            assert "Waiting on you" not in body, status
            assert "## What was done" not in body, status
            assert "## Evidence" not in body, status
            assert "## Verdict" not in body, status

        elif status in _STATE_B:
            # State B: adds the awaiting-acceptance CTA with a spec link; still no package.
            assert "Waiting on you" in body, status
            assert "acceptance" in body, status
            assert _link_targets(body), "no spec link in State B"
            assert "spec.md" in body, "the awaiting-acceptance CTA links the spec"
            assert "## What was done" not in body, status
            assert "## Evidence" not in body, status
            assert "## Verdict" not in body, status

        elif status in _STATE_C:
            # State C: adds the approve CTA + the full seven-part package.
            assert "Waiting on you" in body, status
            assert "approve-or-send-back" in body, status
            for heading in ("## What was done", "## Evidence", "## Verdict",
                            "## Findings", "## Amendments"):
                assert heading in body, f"{heading} missing at {status}"

        else:  # State D — decided
            # State D: the package persists, the status line is updated, the CTA is gone.
            assert "Waiting on you" not in body, status
            assert "## What was done" in body, status
            assert "## Evidence" in body, status
            assert "## Verdict" in body, status

    # The never-mixes invariant, stated directly: no package/evidence content before verified.
    for status in ("drafting", "ready", "approved", "building"):
        set_status(spec_path, status)
        body = _compose(spec_path, cfg)
        assert "## What was done" not in body, status
        assert "## Evidence" not in body, status


# --- C-007 --------------------------------------------------------------------------------


def test_close_preserves_package(tmp_path):
    # Driving verified -> accepted -> closed must lose none of the package: the package region
    # (from `## What was done` to EOF) is byte-identical across the three states — only the
    # status line and the CTA (both above that region) may differ.
    spec_path = _complete_verified(tmp_path, status="verified")
    cfg = _cfg(tmp_path)

    body_v = _compose(spec_path, cfg)
    set_status(spec_path, "accepted")
    body_a = _compose(spec_path, cfg)
    set_status(spec_path, "closed")
    body_c = _compose(spec_path, cfg)

    assert "## What was done" in body_v

    def region(body):
        return body[body.index("## What was done"):]

    assert region(body_a) == region(body_v), "package region changed at accepted"
    assert region(body_c) == region(body_v), "package region changed at closed"

    closed_region = region(body_c)
    for heading in ("## Evidence", "## Verdict", "## Findings", "## Amendments"):
        assert heading in closed_region, f"{heading} lost by close"

    assert "Status: closed" in body_c
    assert "Waiting on you" not in body_c  # State D drops the CTA


# --- C-008 --------------------------------------------------------------------------------


def test_degenerate_contents_compose_explicitly(tmp_path):
    # Each degenerate case: compose does NOT raise, and the affected part renders its explicit
    # note. Exact-quoted notes ("none recorded", "none — built from version 1 unchanged") are
    # asserted literally; the others are asserted with tolerant patterns grounded in the spec's
    # own descriptive words ("no artifacts", "missing-artifact note", "bundle-incomplete note").

    # (a) Absent/empty evidence/ -> the Evidence section states no artifacts are present.
    root = tmp_path / "a"
    spec_dir = root / ".grillwork" / "specs" / SPEC_ID
    ev = spec_dir / "evidence"
    ev.mkdir(parents=True)  # dir present but empty of artifacts
    (ev / "bundle.md").write_text(
        _bundle_md(base=BASE, candidate=CAND, what_done=WHAT_DONE, rows=[],
                   verdict=f"DONE — at revision {CAND}."),
        encoding="utf-8",
    )
    (spec_dir / "findings.md").write_text("# Findings\n\n- **gap:** x · **why:** y\n",
                                          encoding="utf-8")
    spec_path = _write_spec(spec_dir, status="verified", summary=SUMMARY,
                            amendments=[(2, "2026-07-18", V2_DESC)])
    body = _compose(spec_path, _cfg(root))
    evidence = _section(body, "Evidence")
    assert evidence is not None, "Evidence section absent on empty evidence/"
    assert re.search(r"no artifacts?", evidence, re.IGNORECASE), evidence
    assert "/blob/" not in evidence, "no artifact links when there are no artifacts"

    # (b) Absent findings.md -> "none recorded".
    root = tmp_path / "b"
    spec_dir = root / ".grillwork" / "specs" / SPEC_ID
    ev = spec_dir / "evidence"
    ev.mkdir(parents=True)
    (ev / "C-001.log").write_text("x\n", encoding="utf-8")
    (ev / "bundle.md").write_text(
        _bundle_md(base=BASE, candidate=CAND, what_done=WHAT_DONE,
                   rows=[("C-001", "shows", ["evidence/C-001.log"])],
                   verdict=f"DONE — at revision {CAND}."),
        encoding="utf-8",
    )
    # no findings.md written
    spec_path = _write_spec(spec_dir, status="verified", summary=SUMMARY,
                            amendments=[(2, "2026-07-18", V2_DESC)])
    body = _compose(spec_path, _cfg(root))
    findings = _section(body, "Findings")
    assert findings is not None, "Findings section absent when findings.md is absent"
    assert "none recorded" in findings, findings

    # (c) Amendments with only the initial row -> "none — built from version 1 unchanged".
    root = tmp_path / "c"
    spec_dir = root / ".grillwork" / "specs" / SPEC_ID
    ev = spec_dir / "evidence"
    ev.mkdir(parents=True)
    (ev / "C-001.log").write_text("x\n", encoding="utf-8")
    (ev / "bundle.md").write_text(
        _bundle_md(base=BASE, candidate=CAND, what_done=WHAT_DONE,
                   rows=[("C-001", "shows", ["evidence/C-001.log"])],
                   verdict=f"DONE — at revision {CAND}."),
        encoding="utf-8",
    )
    (spec_dir / "findings.md").write_text("# Findings\n\n- **gap:** x · **why:** y\n",
                                          encoding="utf-8")
    spec_path = _write_spec(spec_dir, status="verified", summary=SUMMARY, amendments=[])
    body = _compose(spec_path, _cfg(root))
    amendments = _section(body, "Amendments")
    assert amendments is not None, "Amendments section absent"
    assert "none — built from version 1 unchanged" in amendments, amendments

    # (d) An evidence-map row whose artifact file is absent -> that row renders an explicit
    #     missing-artifact note while other rows render normally.
    root = tmp_path / "d"
    spec_dir = root / ".grillwork" / "specs" / SPEC_ID
    ev = spec_dir / "evidence"
    ev.mkdir(parents=True)
    (ev / "present.log").write_text("x\n", encoding="utf-8")  # C-001's artifact exists
    # C-002's artifact (missing.log) is deliberately never created
    (ev / "bundle.md").write_text(
        _bundle_md(base=BASE, candidate=CAND, what_done=WHAT_DONE,
                   rows=[("C-001", "present shows", ["evidence/present.log"]),
                         ("C-002", "missing shows", ["evidence/missing.log"])],
                   verdict=f"DONE — at revision {CAND}."),
        encoding="utf-8",
    )
    (spec_dir / "findings.md").write_text("# Findings\n\n- **gap:** x · **why:** y\n",
                                          encoding="utf-8")
    spec_path = _write_spec(spec_dir, status="verified", summary=SUMMARY,
                            amendments=[(2, "2026-07-18", V2_DESC)])
    body = _compose(spec_path, _cfg(root))
    evidence = _section(body, "Evidence")
    assert evidence is not None
    rows = [ln for ln in evidence.splitlines() if ln.strip().startswith("|")]
    row_present = next(ln for ln in rows if "C-001" in ln)
    row_missing = next(ln for ln in rows if "C-002" in ln)
    # The present row renders a normal SHA-pinned link.
    assert "/blob/" in row_present and "present.log" in row_present, row_present
    # The missing row renders an explicit note, not a link to the absent file.
    assert re.search(r"missing|not found|absent|no such", row_missing, re.IGNORECASE), row_missing
    assert "/blob/" not in row_missing, "the missing row must not link a non-existent artifact"

    # (e1) bundle.md absent at verified -> the bundle-sourced parts render a bundle-incomplete
    #      note; the sync does not fail; the non-bundle parts still compose.
    root = tmp_path / "e1"
    spec_dir = root / ".grillwork" / "specs" / SPEC_ID
    ev = spec_dir / "evidence"
    ev.mkdir(parents=True)
    (ev / "C-001.log").write_text("x\n", encoding="utf-8")  # evidence present, but no bundle.md
    (spec_dir / "findings.md").write_text("# Findings\n\n- **gap:** x · **why:** y\n",
                                          encoding="utf-8")
    spec_path = _write_spec(spec_dir, status="verified", summary=SUMMARY,
                            amendments=[(2, "2026-07-18", V2_DESC)])
    body = _compose(spec_path, _cfg(root))  # must not raise
    assert re.search(r"bundle", body, re.IGNORECASE), body
    assert re.search(r"incomplete|unavailable|not available|missing", body, re.IGNORECASE), body
    assert SUMMARY in body  # part 1 still composes
    assert "## Findings" in body  # part 6 still composes from findings.md

    # (e2) bundle.md present but missing a required section (## Revisions) at verified ->
    #      the affected parts render a bundle-incomplete note; the sync does not fail.
    root = tmp_path / "e2"
    spec_dir = root / ".grillwork" / "specs" / SPEC_ID
    ev = spec_dir / "evidence"
    ev.mkdir(parents=True)
    (ev / "C-001.log").write_text("x\n", encoding="utf-8")
    (ev / "bundle.md").write_text(
        "## What was done\n\n" + WHAT_DONE + "\n\n"
        "## Evidence map\n\n"
        "| Criterion | Shows | Artifact(s) |\n|---|---|---|\n"
        "| C-001 | shows | evidence/C-001.log |\n\n"
        "## Verdict\n\nDONE — at revision " + CAND + ".\n",  # NO `## Revisions` section
        encoding="utf-8",
    )
    (spec_dir / "findings.md").write_text("# Findings\n\n- **gap:** x · **why:** y\n",
                                          encoding="utf-8")
    spec_path = _write_spec(spec_dir, status="verified", summary=SUMMARY,
                            amendments=[(2, "2026-07-18", V2_DESC)])
    body = _compose(spec_path, _cfg(root))  # must not raise
    assert re.search(r"bundle", body, re.IGNORECASE), body
    assert re.search(r"incomplete|unavailable|not available|missing", body, re.IGNORECASE), body


# --- C-003 (regression: the ready spec link is a followable GitHub URL) --------------------


def test_ready_state_spec_link_is_followable_github_url(tmp_path):
    # R-002: the ready call-to-action's spec link must resolve once the trunk is pushed. GitHub
    # resolves a link inside an issue body against the issue URL, not the repo tree, so a bare
    # repo-relative path is not followable — the State-B link must be a full blob URL to the spec
    # on the integration target, never a bare `.grillwork/...` path.
    spec_path = _complete_verified(tmp_path)
    set_status(spec_path, "ready")

    # Default cfg (no integration_target): the link is a full GitHub blob URL to spec.md.
    body = _compose(spec_path, _cfg(tmp_path))
    targets = _link_targets(body)
    assert targets, "no spec link in the ready (State B) body"
    spec_links = [t for t in targets if t.endswith("/spec.md")]
    assert spec_links, f"no spec.md link target in the ready body: {targets}"
    for t in spec_links:
        assert t.startswith("https://github.com/"), f"spec link is not a full GitHub URL: {t}"
        assert t.endswith("/spec.md"), t
        assert REPO in t, f"spec link not on the configured repo: {t}"
    # No link target is a bare repo-relative path (the un-followable form R-002 rules out).
    for t in targets:
        assert not t.startswith(".grillwork/"), f"link target is a bare relative path: {t}"

    # With a configured integration_target, the branch segment of the blob URL is that value.
    branch = "main"
    cfg = SimpleNamespace(root=Path(tmp_path), repo=REPO, integration_target=branch)
    body = _compose(spec_path, cfg)
    spec_links = [t for t in _link_targets(body) if t.endswith("/spec.md")]
    assert spec_links, "no spec.md link target with integration_target set"
    for t in spec_links:
        assert f"/blob/{branch}/" in t, f"branch segment is not the integration target: {t}"
