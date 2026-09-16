---
name: grillwork-accept
kind: command
description: "Present a verified change for human acceptance; on acceptance, merge, publish and close. Explicit invocation only, and rarely needed directly — /grillwork-build ends at this touchpoint; invoke it standalone only to accept a result left verified in an earlier session."
---

The Grillwork **result-acceptance touchpoint** — the second human touchpoint, taking delivery
of the *result*, together with the close-out that follows it.

The spec:

{{ARGS}}

**You do not normally need this.** `/grillwork-build` ends at this touchpoint and carries the
accepted change through close-out in the same run. This command is for taking delivery of a
result that an earlier session left at `verified`.

Carry out **steps 9 and 10 of `.grillwork/engine/roles/builder.md`** exactly as written — those
steps are the definition, and this command only re-enters them. In short: confirm the change is
`verified` (`python .grillwork/engine/lib/grillwork spec-status <spec>`), present the evidence bundle, what changed, and the
verdict; on the person's explicit **yes** merge the build branch onto the ⟨integration target⟩,
set `accepted`, hand this spec's findings to the Curator, then publish the merge, prune
evidence, clean up the branch and worktree, and set `closed`. On a **no**, return it to
`building` with the reasons recorded. Never accept or merge on the person's behalf.
