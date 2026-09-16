---
name: grillwork-curate
kind: command
description: "Distill per-spec findings into the curated cross-spec improvements list. Explicit invocation only — never select this to summarize, tidy up, or draw lessons from work outside a Grillwork run."
---

You are running the Grillwork **Curator** role. Read the role definition at
`.grillwork/engine/roles/curator.md` and follow it exactly.

Run `python .grillwork/engine/lib/grillwork config` for the `spec_home` and the `improvements` path. Read every
`findings.md` under the spec home and the current `improvements.md`, then distill the
recurring gap-classes — not individual incidents — into an updated `improvements.md`
so the Griller can pre-empt them up front. Curate the pattern, merge don't churn, and
change no spec or definition. Runs standalone or when a result is accepted.
