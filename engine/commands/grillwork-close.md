---
name: grillwork-close
kind: command
description: "Finalize an accepted change — publish the merge, clean up its build branch/worktree, and close. Explicit invocation only, and rarely needed directly: /grillwork-build carries an accepted change through close-out; invoke it standalone only to finish a change left accepted but unpublished."
---

The Grillwork **close-out** step — finalize an already-accepted change.

The spec:

{{ARGS}}

**You do not normally need this.** `/grillwork-build` runs close-out as its own tail. This
command is for a change left `accepted` but unpublished — most often because an earlier
close-out halted on a failed evidence publish, which it is built to let you retry.

Carry out **step 10 of `.grillwork/engine/roles/builder.md`** exactly as written — that step is
the definition, including the load-bearing ordering and the halt-before-destruction rule, and
this command only re-enters it. In short: confirm the change is `accepted`
(`python .grillwork/engine/lib/grillwork spec-status <spec>`), then publish the merge, re-attempt and prune evidence with
`python .grillwork/engine/lib/grillwork prune-evidence <spec>` (halting before any destructive step on a nonzero exit), delete the
build branch and remove its worktree, and set `closed`. Report what was pushed, pruned and
removed. This step publishes and tidies: it does not re-merge, and it does not deploy.
