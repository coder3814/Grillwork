# Definition of Ready

> Status: **accepted** (2026-07-09). This is the engine's stamped copy — the runtime
> stopping case for the grilling loop. Derived (2026-07-08) from the accepted Definition of
> Done (`definition-of-done.md`, stamped beside this file).

**The purpose of a spec is to carry development to Done without a single additional
question.** Ready is the claim that this purpose is met: the spec already contains
everything the work will consume. Every condition below is a projection of that one
property — a named, cheaply-checkable way a spec commonly falls short of it — and
condition 6.2 tests the property itself, end to end. A spec that satisfies every
condition yet still forces a question mid-build has failed Ready by definition; the
question routes back as a spec amendment. (This is the north star of
the model — "development is a pure function of the spec" — made
enforceable.)

A spec is **Ready** when all of the following conditions hold, evaluated over the spec
(including its instantiation) and the repo it targets. The definition is
**evaluator-agnostic**: it states *what must hold* — not who checks it, in what order, or
what happens on failure.

- Terms in ⟨angle brackets⟩ are engine defaults, some bound by adopter configuration
  (§Defaults).
- Every check carries a mode: `[machine]` a script decides; `[rubric]` an agent applies
  the named rubric; `[judgment]` an agent exercises adversarial judgment against the
  named rubric.
- Ready is a property of the spec — **Ready is not approved.** Approval of a Ready spec
  is the human touchpoint that follows (§Exclusions).

## Conditions

### 1. The request is classified

1.1 The spec declares the request's type(s) from the ⟨request-type taxonomy⟩; a mixed
    request enumerates all its types. `[machine]`

1.2 The declared type(s) fit the request as specified. `[judgment: classification
    rubric]`

1.3 The required test types are enumerated: the union of the declared types'
    requirements; for **other**, the spec itself establishes them. `[machine]`

1.4 For refactors, the ⟨declared observable surface⟩ is named, with the requested deltas
    listed and excluded from it. `[machine — presence; fit is covered by 1.2]`

### 2. Requirements are addressable and testable

2.1 Every requirement **and every acceptance criterion** carries a stable ID — the
    handles the Done-time trace tags against, which must survive amendment without
    renumbering. `[machine]`

2.2 Every required test type has concrete acceptance criteria. `[machine — presence]`

2.3 Every criterion names observable behavior — something a test can exercise and a
    delivered result can fail — statable as a behavioral/black-box acceptance test:
    an observable outcome, invariant under reimplementation (a different
    implementation behind the same interface still passes), not coupled to
    implementation structure. `[judgment: sufficiency rubric]`

2.4 For bug fixes, the defect's failing scenario is specified: the input or state that
    triggers it, and the observed-vs-expected behavior at the base revision — what the
    regression test's fails-at-base half is derived from. `[machine — presence; adequacy
    via 2.3]`

### 3. The evidence plan is complete and falsifiable

3.1 Every criterion has an evidence promise whose artifact type comes from the
    ⟨artifact menu⟩. `[machine]`

3.2 Every promise follows the template: *artifact + what it will show + under what
    condition or action*. `[rubric: the template]`

3.3 Every promise is specific enough to falsify — a delivered artifact could fail it.
    `[judgment: falsifiability rubric]`

3.4 Every promise states how its artifact will be generated. `[machine — presence]`

3.5 Every criterion names the checkpoint its evidence must come from. `[machine]`
    *(Pre-Environments placeholder: named, not yet judged for adequacy.)*

*(For an interface-observable criterion, when the interface-surface determination (§8) is
non-trivial, the evidence promise carries the still-image-floor-plus-video-when-feasible
visual artifact naming the approved wireframe as its reference — stated in §8.3, not
duplicated here.)*

### 4. The adopter bindings are referenced

4.1 The spec references the adopter-configured ⟨existing-behavior gate⟩. `[machine]`

4.2 If that gate is empty or trivially weak, the spec carries an explicit disposition of
    that fact — a vacuously green gate protects exactly the adopters most at risk.
    `[judgment: disposition rubric]`

### 5. The harm classes are disposed

5.1 Every class in the ⟨harm list⟩ has an explicit disposition. *"Not applicable,
    because X"* is a valid disposition; silence is not. `[machine — presence]`

5.2 Each disposition is adequate: its stated reason is true of the request as specified.
    `[judgment: disposition rubric]`

5.3 Each non-trivial disposition's demands appear as requirements — criteria and evidence
    promises like any other, flowing into conditions 2–3. `[machine]`

### 6. The spec grounds the work

6.1 The instantiation is complete: every ⟨term⟩ the Definition of Done consumes is bound,
    and the named rubrics exist — classification, sufficiency, falsifiability, tag-truth
    and enabling, grounding, disposition, and — when the interface-surface determination
    (§8) is non-trivial — interface-grounding. `[machine — presence]`

6.2 A complete task decomposition is derivable from the spec and the target repo without
    a single new question: every decision the decomposition requires is grounded in the
    spec. This is the definition's purpose (see preamble) tested directly, end to end —
    conditions 1–5 and 7 catch its common failure modes early and cheaply. `[judgment:
    grounding rubric]`

6.3 No gap or clarification marker remains open against the spec. `[machine]`

6.4 The spec is versioned. `[machine]`

### 7. The boundaries are defined

*A request arrives as an idea, not a spec; Ready includes the shape investigation gave
it. These conditions check the residue that boundary negotiation leaves in the spec —
not that investigation "happened."*

7.1 The spec states its scope in both directions: alongside what is requested, it names
    what is adjacent but excluded. `[machine — presence]`

7.2 Every exclusion carries a reason — an exclusion is a disposition ("out of scope,
    because X"), so *considered-and-rejected* is distinguishable from *never-considered*.
    Silence about an adjacent concern is not a boundary. `[judgment: disposition rubric]`

7.3 Each requirement's edge behavior — limits, empty and extreme inputs, failure paths —
    is either specified by a criterion or explicitly excluded under 7.1. `[judgment:
    sufficiency rubric]`

7.4 Deferrals are explicit: anything negotiated out of *this* spec but kept alive appears
    as a named deferral with its reason — deferred-by-decision is distinguishable from
    dropped-by-silence. `[machine — presence]`

*(That nothing raised in negotiation was silently dropped is the grilling loop's
reconciliation duty — the negotiation record is process exhaust, outside this
definition's evaluation objects. See the grilling-loop notes.)*

### 8. The interface surface is grounded

*A request that renders or serves something a person looks at is under-determined by prose:
the builder invents layout and interaction the spec never settled, and the judge cannot tell
whether it is right until it is rendered. These conditions ground that surface at spec time,
parallel to §5 (harm) and §7 (boundaries).*

8.1 The spec states an **interface-surface determination** — does this work render or serve
    something a user observes? — with three mutually exclusive, exhaustive outcomes:
    **non-trivial** (renders or serves a user-observable interface → wireframe and visual
    evidence required); **trivial, because ⟨reason⟩** (one obvious element with nothing to
    lay out → skippable with a stated reason); **not applicable, because ⟨reason⟩** (nothing
    a user observes → neither required). Silence is not a valid outcome. Presence is
    `[machine]`; the adequacy of a trivial/not-applicable reason is `[judgment: disposition
    rubric]`. The determination is **derived and human-verified** like the request type
    (§1), and **re-derived after any change, not latched**.

8.2 When the determination is **non-trivial**, the spec carries a **static wireframe stored
    beside the spec** — a sibling of the spec file, like its evidence directory: the
    wireframe is **present** `[machine]` and **grounds the interface's structure, fields,
    states, and interaction** `[judgment: interface-grounding rubric]`. *Fidelity* — a
    wireframe, never a visual design: it fixes structure, fields, states, and the flow of
    interaction; it does **not** fix colors, fonts, or pixels, and a mockup that pins
    aesthetics is rejected. *Medium* — static, dependency-free, matched to the surface (a
    static HTML file for a web page; a text or ASCII sketch for a terminal interface); never
    a named tool. This is a **grounding** condition — the Builder needs the visual target to
    build unattended — not an acceptance condition.

8.3 When the determination is **non-trivial**, each **interface-observable** acceptance
    criterion's evidence promise carries **at least a still image (never a log alone) plus a
    video wherever the interaction and capture capability make one feasible**, and names the
    **approved wireframe as the promise's reference** — so the Done-side check (Definition of
    Done 3.1) compares the built result to the wireframe. This condition is the normative
    home of that rule; the evidence-plan conditions (§3) point here rather than restate it.
    `[machine — presence of the visual promise; judgment: the promise's own rubric at Done]`

## Exclusions

- **Approval is not gated.** Ready asserts the spec is *complete enough to build from
  unattended* — not that it is what the human wants. Approving the Ready spec is the
  human touchpoint that follows, and rejection there is a spec amendment that re-earns
  Ready.
- **Nothing is checked by taste.** Every check above carries one of the three modes.

## Defaults

This is the generic engine definition. The ⟨request-type taxonomy⟩ (feature / bug fix /
refactor / other), ⟨artifact menu⟩ (images, videos, log files, example outputs, other),
⟨harm list⟩ (data integrity, security, performance), and ⟨existing-behavior gate⟩ are
engine defaults, never blank. In v1 only the ⟨existing-behavior gate⟩ is bound by adopter
configuration; the taxonomy, artifact menu, and harm list ship as fixed engine content
(adding config surface later is backwards-compatible). The
⟨artifact menu⟩ carries, per artifact type, the mode of the Done-time reproduction check
(machine for logs and outputs, rubric for visual artifacts), so no check's mode is left
undetermined. The rubrics
named by `[judgment]` checks are carried by the spec's instantiation (produced during
grilling), so the same rubrics serve Ready here and Done later.

**Pre-Environments capture minimum.** Until the Environments phase, the visual evidence a
non-trivial interface surface (§8) demands is captured from a **static, self-contained
surface a headless renderer can open from a path** — a self-contained HTML file at a
`file://` path (inline styling, no server, no network), or, for a terminal interface, the
text/ASCII surface itself — by a **per-spec procedure named in the evidence promise's
"Generated by"**; the engine ships no capture tool and adds no dependency. A **runtime-only
surface** — one that exists only while a server or application runs, such as a served web app
or a desktop application — is **not** in this minimum: it still carries its **wireframe at
Ready**, but its **Done-side visual evidence is checkpoint-deferred** under the existing
pre-Environments placeholder (§3.5 / Definition of Done 6.1) until the Environments phase.
