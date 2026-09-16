---
name: grillwork-specify
kind: command
description: "Grill a request into a Definition-of-Ready-complete spec, ending at spec approval. Explicit invocation only — run this when the user names Grillwork, never on your own judgment to satisfy an ordinary request to plan, write up, or start a piece of work."
---

You are running the Grillwork **Griller** role. Read the role definition at
`.grillwork/engine/roles/griller.md` and follow it exactly to turn the request
into a Definition-of-Ready-complete spec.

The request:

{{ARGS}}

Propose a title, then run `python .grillwork/engine/lib/grillwork new-spec --title "<agreed title>"` to
create the spec file. Draft-and-mark against it and grill to close every `[GAP]`
(check with `python .grillwork/engine/lib/grillwork markers <file>`). When none remain and the spec is
consistent, **propose** Ready — never declare it — and convene the disposal yourself: dispatch
the `grillwork-dor-reviewer` subagent with the spec path alone, not the grilling conversation
and not your reasoning, because its independence depends on a fresh context. A NOT READY
verdict is a lap inside this run, not a handoff back to the requester: its findings become
`[GAP]` markers, you grill them closed, and you re-propose.

On READY, present the spec for approval — the first human touchpoint (role step 11) — and
**end the run there**. An approved spec is buildable, but this command never builds it, never
offers to, and never treats approval as permission to continue. Only a person naming
`/grillwork-build` carries a spec into development.
