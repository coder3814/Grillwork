"""Phase 4 — the Reviewer's engine assets and realizations (code parts). The review
*judgment* — catching a planted gap, converging over rounds — runs in a live Builder
session and is not headless-verifiable."""

import re
from pathlib import Path

import pytest
from conftest import method_text
from grillwork import naming

REPO_ROOT = Path(__file__).resolve().parents[1]
_ASSET_DEFINITIONS = REPO_ROOT / "engine" / "definitions"
_DOC_DEFINITIONS = REPO_ROOT / "docs" / "definitions"

# docs/ is authoring material: it explains and justifies the method, nothing installed reads it,
# and it is not published. The guards below keep it honest against the definitions, so they run
# on the machine that edits it and skip in a clone that does not carry it.
_needs_docs = pytest.mark.skipif(
    not _DOC_DEFINITIONS.exists(), reason="docs/ is authoring material and is not published"
)


def _normative(text: str) -> str:
    """A definition's normative content: its conditions, with everything that is presentation
    rather than definition removed — the `> Status:` banner, link markup, and line wrapping."""
    body = "\n".join(line for line in text.splitlines() if not line.startswith(">"))
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)  # [text](target) -> text
    return " ".join(body.split())


@_needs_docs
@pytest.mark.parametrize("definition", ["definition-of-ready.md", "definition-of-done.md"])
def test_definition_asset_matches_canonical_doc(definition):
    """Drift guard: each stamped definition must carry the same conditions as its accepted doc.

    Only the stamped copy is published; `docs/definitions/` is authoring material. So this runs
    where the second copy exists — the machine the drift would be introduced on — and skips in a
    fresh clone, which has nothing to compare and nothing that can drift.

    Each definition exists twice — canonical under `docs/definitions/`, stamped into the engine
    — so each is the drift shape this project names: a fact in two places. This is the
    comparator.

    What is compared is the **normative content**, not the bytes. The two copies differ by
    design, and must: a stamped copy carries its own banner and spells its cross-references out
    as prose, because a relative link that resolves from `docs/definitions/` does not resolve
    from `.grillwork/engine/definitions/` in an adopter's repo. Everything that is definition
    rather than presentation has to agree exactly.
    """
    asset = (_ASSET_DEFINITIONS / definition).read_text(encoding="utf-8")
    canonical = (_DOC_DEFINITIONS / definition).read_text(encoding="utf-8")
    assert _normative(asset) == _normative(canonical), (
        f"Engine asset has drifted from docs/definitions/{definition} — re-sync. "
        "(Only the status banner, link markup and wrapping may differ between the two copies.)"
    )


def test_definition_assets_carry_no_relative_links():
    """A stamped definition must not carry a markdown link to a repo path: it is read from
    `.grillwork/engine/definitions/` in an adopter's repo, where `../design/model.md` and the
    like do not exist. Cross-references are spelled out as prose instead (see each asset's
    banner) — the rule the DoD already followed and the DoR did not, until its links were found
    dangling."""
    for definition in ("definition-of-ready.md", "definition-of-done.md"):
        text = (_ASSET_DEFINITIONS / definition).read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
        assert not links, (
            f"{definition} carries markdown link(s) {links} that will dangle once stamped into "
            "an adopter's .grillwork/engine/definitions/ — spell the reference out as prose."
        )


def _flat_dor() -> str:
    """The stamped DoR with all runs of whitespace collapsed, so content needles survive
    line-wrapping."""
    return " ".join(method_text("definitions", "definition-of-ready.md").split())


def _flat_dod() -> str:
    """The stamped DoD with all runs of whitespace collapsed, so content needles survive
    line-wrapping."""
    return " ".join(method_text("definitions", "definition-of-done.md").split())


def _flat_griller() -> str:
    """The stamped Griller role with all runs of whitespace collapsed, so content needles
    survive line-wrapping."""
    return " ".join(method_text("roles", "griller.md").split())


def _flat_dor_reviewer() -> str:
    """The stamped DoR-Reviewer role with all runs of whitespace collapsed, so content needles
    survive line-wrapping."""
    return " ".join(method_text("roles", "dor-reviewer.md").split())


def _flat_dod_reviewer() -> str:
    """The stamped DoD-Reviewer role with all runs of whitespace collapsed, so content needles
    survive line-wrapping."""
    return " ".join(method_text("roles", "dod-reviewer.md").split())


def test_dor_reviewer_interface_surface_and_wireframe_check():
    """C-008: the stamped DoR-Reviewer role carries a step to check the interface-surface
    determination — present, one of the three outcomes (silence invalid), reason adequate by
    the disposition rubric — and, when non-trivial, the wireframe condition (§8.2): present,
    grounding structure/fields/states/interaction by the interface-grounding rubric, honoring
    the fidelity and medium constraints."""
    flat = _flat_dor_reviewer()
    # The determination: present, three outcomes, silence invalid, reason via disposition rubric.
    assert "interface-surface determination" in flat
    for outcome in ("non-trivial", "trivial, because", "not applicable, because"):
        assert outcome in flat, f"§8 check missing outcome label: {outcome!r}"
    assert "silence is not a valid outcome" in flat
    assert "disposition rubric" in flat
    # When non-trivial, the wireframe condition (§8.2) with its rubric and constraints.
    assert "non-trivial, check the wireframe condition (§8.2)" in flat
    assert "interface-grounding rubric" in flat
    # Fidelity: a wireframe, never a visual design.
    assert "colors, fonts, or pixels" in flat
    assert "mockup that pins aesthetics is rejected" in flat
    # Medium: static, dependency-free, matched to the surface, never a named tool.
    assert "matched to the surface, never a named tool" in flat


def test_dod_reviewer_visual_evidence_check():
    """C-012: the stamped DoD-Reviewer role carries a step to check each interface-observable
    acceptance criterion's visual evidence against the approved wireframe (DoD 3.4) — a still
    image present (never a log alone), a video where feasible (feasible-but-absent is a finding,
    infeasible is not), each judged against the approved wireframe as the evidence promise's
    reference — and scopes a runtime-only surface's visual evidence as checkpoint-deferred
    (DoD 6.1), named but not yet judged."""
    flat = _flat_dod_reviewer()
    # Triggered by the non-trivial interface-surface determination; targets interface-observable
    # criteria and checks their visual evidence against the approved wireframe (DoD 3.4).
    assert "interface-surface determination is **non-trivial**" in flat
    assert "interface-observable" in flat
    assert "visual evidence against the approved wireframe" in flat
    # The still-image floor: present, never a log alone.
    assert "still image is present — never a log alone" in flat
    # The video-where-feasible half: a feasible-but-absent video is a finding, infeasible is not.
    assert "feasible-but-absent video is a finding, an infeasible one is not" in flat
    # Judged against the approved wireframe named as the evidence promise's reference (DoD 3.1).
    assert "named as the evidence promise's reference" in flat
    # A runtime-only surface's visual evidence is checkpoint-deferred (DoD 6.1) — named, not judged.
    assert "runtime-only surface" in flat
    assert "checkpoint-deferred (6.1)" in flat


def test_griller_interface_surface_derive_and_verify():
    """C-003: the stamped Griller role carries a derive-and-verify step for the interface-
    surface determination that mirrors the classification step (step 6) and states the
    determination is re-derived after any change, not latched."""
    flat = _flat_griller()
    assert "interface-surface determination" in flat
    # Mirrors classification (step 6): derived from the request, then user-verified.
    assert "Mirror classification (step 6)" in flat
    assert "have the user verify it" in flat
    # Re-derived after any change, not latched.
    assert "not latched" in flat
    assert "re-derive it after any change" in flat


def test_griller_wireframe_authored():
    """C-007: the stamped Griller role carries a step to AUTHOR the wireframe while closing
    interface gaps (part of draft-and-mark), not merely to demand one."""
    flat = _flat_griller()
    assert "author the wireframe" in flat
    assert "stored beside the spec" in flat
    # Authored, not merely requested.
    assert "rather than leaving a marker that demands one" in flat


@_needs_docs
def test_reference_template_home_for_interface_surface():
    """C-016: the annotated reference gains an 'Interface Surface — DoR 8' home in its annotated
    idiom (no [GAP] marker), keeping its 'every DoR condition has a named home' invariant true
    now that DoR §8 exists — parallel to the stamped asset's home-per-condition guard."""
    ref = (REPO_ROOT / "docs" / "definitions" / "spec-template.md").read_text(encoding="utf-8")
    assert "## Interface Surface — DoR 8" in ref
    # The reference is annotated, not fillable: its §8 home carries no gap marker.
    start = ref.index("## Interface Surface — DoR 8")
    end = ref.index("## Classification — DoR 1", start)
    section = ref[start:end]
    assert not naming.find_markers(section), "the reference's §8 home must carry no [GAP] marker"
    assert "determination" in section
    assert "Wireframe" in section


def test_evidence_visual_points_to_wireframe():
    """C-011: both the stamped template's Evidence-Plan guidance and the stamped DoR's §3 direct
    an interface-observable criterion to a wireframe-referenced visual artifact — the template
    cross-references the Interface Surface / wireframe, and the DoR §3 cross-references §8.3."""
    template = " ".join(method_text("spec-template.md").split())
    dor = _flat_dor()
    # Template Evidence-Plan guidance cross-references the Interface Surface / wireframe.
    assert "interface-observable" in template
    assert "wireframe" in template
    # DoR §3 cross-references §8.3 (the DoR half is committed from Unit A).
    assert "when the interface-surface determination (§8) is" in dor
    assert "approved wireframe" in dor


def test_dor_interface_surface_determination():
    """C-004: the stamped DoR carries the §8 interface-surface determination — the three
    exhaustive outcomes, silence invalid, derived-and-human-verified, re-derived not latched."""
    flat = _flat_dor()
    assert "8. The interface surface is grounded" in flat
    assert "interface-surface determination" in flat
    for outcome in ("non-trivial", "trivial, because", "not applicable, because"):
        assert outcome in flat, f"§8 missing outcome label: {outcome!r}"
    assert "silence" in flat.lower(), "§8 must state that silence is not a valid outcome"
    assert "derived" in flat
    assert "not latched" in flat, "§8 must state the determination is re-derived, not latched"


def test_dor_wireframe_condition():
    """C-005: the stamped DoR carries the §8 wireframe condition with the fidelity constraint
    (no colors/fonts/pixels; mockup rejected) and the medium constraint (static,
    dependency-free, matched to the surface, no named tool)."""
    flat = _flat_dor()
    assert "static wireframe stored beside the spec" in flat
    # Fidelity: a wireframe, never a visual design.
    assert "colors, fonts, or pixels" in flat
    assert "mockup that pins aesthetics is rejected" in flat
    # Medium: static, dependency-free, matched to the surface, never a named tool.
    assert "dependency-free" in flat
    assert "matched to the surface" in flat
    assert "never a named tool" in flat


def test_dor_grounding_rubric_enumerated():
    """C-009: the stamped DoR enumerates the interface-grounding rubric in 6.1, required only
    when the interface-surface determination is non-trivial."""
    flat = _flat_dor()
    assert "interface-grounding" in flat
    assert "when the interface-surface determination (§8) is non-trivial — interface-grounding" in flat


def test_dod_visual_evidence_condition():
    """C-010: the stamped DoD carries the §3.4 visual-evidence condition — a still-image floor
    (present, machine, never a log alone) plus a video-where-feasible (judgment; a
    feasible-but-absent video is a finding, an infeasible one is not), each judged against the
    approved wireframe as the evidence promise's named reference, so the Done-side check is the
    promise's own rubric (3.1) — no new Done-side rubric is introduced."""
    flat = _flat_dod()
    # The condition triggers only when the interface-surface determination is non-trivial.
    assert "interface-surface determination is **non-trivial**" in flat
    assert "interface-observable" in flat

    # (a) The still image is the floor: present, mode [machine], and never a log alone.
    still_at = flat.index("at least a still image")
    assert "never a log alone" in flat
    assert "a still image is present" in flat
    assert "not demonstrated by a log alone" in flat
    # The [machine] mode tag governs the still-image clause (it precedes the video clause)...
    machine_at = flat.index("[machine]", still_at)

    # (b) A video is required where feasible: mode [judgment]; feasible-but-absent is a finding,
    # infeasible is not.
    video_at = flat.index("a video wherever the interaction and capture")
    judgment_at = flat.index("[judgment]", still_at)
    assert still_at < machine_at < video_at < judgment_at, (
        "the still's [machine] tag must govern the still clause and the video's [judgment] "
        "tag the video clause"
    )
    assert "feasible-but-absent video is a finding" in flat
    assert "an infeasible one is not" in flat

    # (c) Judged against the approved wireframe, named as the promise's reference.
    assert "against the approved wireframe" in flat
    assert "named as the evidence promise's reference" in flat

    # (d) It is the promise's own rubric (3.1); no new Done-side rubric is introduced.
    assert "the promise's own rubric" in flat
    assert "(3.1)" in flat
    assert "no new rubric is introduced" in flat


@_needs_docs
def test_derivation_coverage_visual_evidence_wireframe_row_and_rubric_closure():
    """C-014: the DoD↔DoR derivation map carries a coverage row mapping the Done-side
    visual-evidence condition (DoD 3.4) to the Ready-side wireframe guarantee (DoR §8), AND
    records the interface-grounding rubric under rubric closure — so the map still shows every
    DoD demand covered by a DoR guarantee and every rubric obligated by DoR 6.1."""
    doc = (REPO_ROOT / "docs" / "definitions" / "dod-dor-derivation.md").read_text(encoding="utf-8")
    flat = " ".join(doc.split())
    # (a) A coverage-map row maps DoD 3.4 (visual evidence) to the DoR §8 wireframe guarantee:
    # the determination (8.1), the wireframe grounding structure/fields/states/interaction (8.2),
    # and the wireframe-referenced visual-evidence promise (8.3).
    assert "3.4 interface visual evidence" in flat
    assert "(DoR 8.1)" in flat
    assert "grounding the interface's structure/fields/states/interaction (DoR 8.2)" in flat
    assert "(DoR 8.3)" in flat
    # (b) Rubric closure records the interface-grounding rubric, obligated by DoR 6.1 conditionally.
    assert "interface-grounding rubric" in flat
    assert "obligated by DoR 6.1" in flat
    assert "when the interface-surface determination is non-trivial" in flat


def test_capture_minimum_and_runtime_only_deferral():
    """C-013: the pre-Environments capture minimum is named — a static, self-contained surface
    rendered from a path, captured by a per-spec procedure named in "Generated by", with the
    engine adding no capture tool or dependency — and a runtime-only surface's Done-side visual
    evidence is scoped checkpoint-deferred in BOTH the DoR §Defaults capture minimum (Unit A)
    and the DoD 6.1 placeholder (this unit)."""
    dor = _flat_dor()
    dod = _flat_dod()

    # DoR §Defaults — the capture minimum names a static, self-contained, path-opened surface.
    assert "Pre-Environments capture minimum" in dor
    assert "static, self-contained surface a headless renderer can open from a path" in dor
    # ...captured by a per-spec procedure named in the evidence promise's "Generated by".
    assert "per-spec procedure named in the evidence promise's" in dor
    assert '"Generated by"' in dor
    # ...and the engine ships no capture tool and adds no dependency.
    assert "the engine ships no capture tool and adds no dependency" in dor
    # A runtime-only surface keeps its wireframe at Ready but its Done-side evidence is deferred.
    assert "runtime-only surface" in dor
    assert "Done-side visual evidence is checkpoint-deferred" in dor

    # DoD 6.1 mirrors it: a runtime-only interface surface's Done-side visual evidence is
    # checkpoint-deferred under the pre-Environments placeholder until Environments.
    assert "runtime-only interface surface" in dod
    assert "Done-side visual evidence (3.4)" in dod
    assert "checkpoint-deferred under this placeholder" in dod
