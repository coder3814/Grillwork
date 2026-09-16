---
name: grillwork-review
kind: command
description: "Independently review a proposed-Ready spec against the Definition of Ready. Explicit invocation only, and rarely needed directly — /grillwork-specify runs this review inside itself; invoke it standalone only to re-review a spec out of band."
---

Re-run the Definition-of-Ready disposal on a spec, out of band.

The spec:

{{ARGS}}

**You do not normally need this.** `/grillwork-specify` convenes this review inside itself and
absorbs a bounce without leaving the run. This command is for disposing a spec on its own —
after a hand edit, say, or when an earlier run was interrupted before its reviewer ran.

Spawn the `grillwork-dor-reviewer` subagent to review the spec, and pass it only the spec path
— not the grilling conversation or your reasoning; its independence depends on a fresh context.
Relay its verdict (READY / NOT READY); if NOT READY, ensure the findings are recorded as
`[GAP]` markers and re-grill. Only a person approves a Ready spec.
