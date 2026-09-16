# Definition of Done

> Status: **accepted** (2026-07-08). This is the engine's stamped copy — the runtime
> stopping case for the development loop.

A change is **Done** when all of the following conditions hold, evaluated against the
governing spec. The definition is **evaluator-agnostic**: it states *what must hold* — not
who checks it, in what order, or what happens on failure.

- Terms in ⟨angle brackets⟩ are bound per spec by the instantiation (§Instantiation).
- Every check carries a mode: `[machine]` a script decides; `[rubric]` an agent applies
  the named rubric; `[judgment]` an agent exercises adversarial judgment against the named
  instantiation-produced rubric.
- Two revisions anchor every check: the **revision under evaluation** (the delivered
  change) and the **base revision** (the revision the change was built from). Conditions
  comparing "before" and "after" compare exactly these two.

## Conditions

### 1. Required tests exist and pass

1.1 The ⟨existing-behavior gate⟩ passes at the revision under evaluation. `[machine]`

1.2 Every test type required by the request's declared type(s) exists and passes:
    **feature** — an acceptance-scenario test per acceptance criterion; **bug fix** — a
    regression test that fails at the base revision and passes at the revision under
    evaluation; **refactor** — the ⟨declared observable surface⟩, minus the requested
    deltas, is identical between the base revision and the revision under evaluation;
    **other** — the test types the spec explicitly establishes. Mixed types take the
    union of their types' requirements. `[machine]`

1.3 The delivered change conforms to its declared request type(s): the work as built has
    not outgrown the classification that selected its test requirements. `[judgment:
    classification rubric]`

### 2. The tests test the spec

2.1 Every acceptance criterion traces to at least one test that exercises it.
    `[machine — derived from tags]`

2.2 The tests are sufficient to demonstrate their criteria, and are
    behavioral/black-box: each asserts an observable outcome and is invariant under
    reimplementation — a different implementation behind the same interface still
    passes it — never coupling to implementation structure or internal calls.
    `[judgment: sufficiency rubric]`

### 3. The evidence fulfills its promises

3.1 Every promise in the ⟨evidence plan⟩ is fulfilled: each delivered artifact shows what
    its promise declares, under the declared condition. `[rubric: the promise itself]`

3.2 Every artifact records the revision it was generated from, the checkpoint it was
    captured at, and the re-runnable command or procedure that produced it. `[machine]`

3.3 Each artifact is **reproducible**: its recorded command, executed against the
    revision under evaluation, yields an artifact that fulfills the same promise.
    Reproduction is judged by promise-equivalence, not bit-identity. `[machine or
    rubric, per artifact type]`

3.4 When the governing spec's interface-surface determination is **non-trivial**, each
    **interface-observable** acceptance criterion's evidence includes **at least a still
    image — never a log alone** (`[machine]` — a still image is present, so the criterion
    is not demonstrated by a log alone) **and a video wherever the interaction and capture
    capability make one feasible** (`[judgment]` — a feasible-but-absent video is a
    finding; an infeasible one is not). Each is judged **against the approved wireframe,
    named as the evidence promise's reference**, so the check is the promise's own rubric
    (3.1) comparing the built result to the wireframe — **no new rubric is introduced
    here**.

### 4. Traceability holds in both directions

4.1 No gaps: every requirement maps, via tags, to implementation and evidence.
    `[machine — derived from tags]`

4.2 No orphans: every change in the delivered change-set (base revision → revision under
    evaluation), at commit-equivalent granularity, is tagged to a requirement or tagged
    `ENABLING` with a stated reason. `[machine — derived from tags]`

4.3 Tags are true: each tagged change serves its requirement; each `ENABLING` change is
    genuinely enabling. `[judgment: tag-truth and enabling rubrics]`

### 5. The work is grounded in the spec

5.1 Every decision embodied in the work is grounded in the spec. `[judgment: grounding
    rubric]`

5.2 The gap record is closed: no gap marker associated with the work lacks a resolving
    spec amendment. `[machine — gap and amendment records]`

### 6. Demonstrated at the required fidelity

6.1 Each criterion's evidence provenance (3.2) names the checkpoint the spec requires for
    that criterion. `[machine]` *(Pre-Environments placeholder: this verifies the
    required checkpoint was named and used; checkpoint adequacy arrives with the
    Environments phase. A **runtime-only interface surface** — one that exists only while
    a server or application runs — has its Done-side visual evidence (3.4)
    checkpoint-deferred under this placeholder until the Environments phase, mirroring the
    Definition of Ready's pre-Environments capture minimum.)*

### 7. The harm-class dispositions hold

7.1 Every criterion and evidence promise attached to a disposition is satisfied — a
    disposition's demands are requirements like any other, evaluated under conditions
    1–4. `[via conditions 1–4]`

7.2 Each disposition is true of the delivered result — the approach did not falsify what
    was true of the request. `[judgment: disposition rubric]`

*(That every harm class **has** a disposition in the spec is a Readiness guarantee, not a
Done condition — see the coverage map. Likewise, that the declared type and dispositions
were plausible at Ready is Readiness; conditions 1.3 and 7.2 check what the delivered
result did to them.)*

## Exclusions

- **Intent is not gated.** "Is this what I actually wanted?" belongs to the human
  acceptance touchpoint. Evaluation may attach advisory intent flags; they never gate
  Done.
- **Nothing is checked by taste.** Every check above carries one of the three modes.

## Instantiation

This is the generic engine definition. Per spec, an instantiation — produced during
grilling, part of the spec — binds every ⟨term⟩ and provides the named rubrics:
classification (1.3), sufficiency (2.2), tag-truth and enabling (4.3), grounding (5.1),
disposition (7.2). Defaults (the request-type mapping in 1.2, the harm list in 7) are
fixed engine content — never blank; in v1 they are not adopter-configurable (only the
existing-behavior gate is bound by adopter config).
