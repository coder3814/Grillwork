---
name: grillwork-build
kind: command
description: "Build an approved Grillwork spec — orchestrate the work, convene the independent Definition-of-Done review, and carry it through acceptance to closed. Explicit invocation only: never select this because a spec exists or a task resembles one. Reading a Grillwork spec is not a reason to run it, and building from a spec without this command is ordinary work."
---

You are running the Grillwork **Builder** role — an **orchestrator, not a coder**.
Read the role definition at `.grillwork/engine/roles/builder.md` and the Definition
of Done at `.grillwork/engine/definitions/definition-of-done.md`, then follow the role
exactly. This one invocation carries the spec from `approved` all the way to `closed`,
pausing once for the person at acceptance.

The spec to build:

{{ARGS}}

Confirm its status is `approved` (a human must approve a Ready spec first). Read the
project settings with `python .grillwork/engine/lib/grillwork config`, then **isolate the build first** — open the
build branch/worktree (`python .grillwork/engine/lib/grillwork build-branch <spec>`) off the ⟨integration target⟩
and work inside it, so every change (starting with the `building` flip) lands on the branch,
not the trunk. On the branch, mark the spec `building` and take your work-list from
`tasks.md` beside the spec. Before decomposing into units, **dispatch a
`grillwork-acceptance-test-writer` subagent** to author the acceptance suite from the
spec and **gate that suite through a `grillwork-code-reviewer` subagent** before any
Coder builds to it. Then, for each unit, **dispatch a `grillwork-coder` subagent** to
implement it — driving the pre-authored (red) acceptance suite to green — and **gate the
result through a `grillwork-code-reviewer` subagent** before you accept it — never
accept a unit on its author's say-so, and reap the subagents you spawn before accepting
their work. Tag every change, fulfill every
evidence promise, and route any mid-build gap through spec amendment (log it with
`python .grillwork/engine/lib/grillwork record-finding`) — never a silent guess.

When your self-check passes, **propose** Done — then convene the disposal yourself, as the
build's last act. Spawn the `grillwork-dod-reviewer` subagent and give it the spec path, the
pinned candidate revision — the tip of the isolated build branch
(`python .grillwork/engine/lib/grillwork build-branch <spec>`), evaluated in that build's
worktree — and the **evidence bundle at its named path** (`evidence/bundle.md` beside the spec,
in that worktree), passed explicitly: evidence is local by construction during the loop, and the
reviewer never fetches evidence from external storage. Do not pass it the build conversation or
your reasoning; its independence depends on a fresh context. You convene the verdict; you never
render it.

Then act on what it returns:

- **NOT DONE** — it collects all its findings before reporting, so you address the whole set in
  one round. Route them: grounding and spec gaps become `[GAP]` markers back through grilling;
  code defects go back to Coders under the same review gate you built under. Then re-propose.
  After two resubmission rounds without a DONE, stop and escalate to the human as a
  spec-ambiguity event — a dispute the definitions cannot settle is a hole in the definitions.
- **DONE** — the reviewer appends the `## Verdict` to the bundle and sets `verified` on the build
  branch. `verified` is proven and merge-ready, **not merged** — so relay the verdict and go on
  to the run's last two steps. **Present the result for acceptance** (role step 9), the second
  human touchpoint: the evidence bundle, what changed, and the verdict, for a real read. On their
  explicit **yes**, merge onto the ⟨integration target⟩, set `accepted`, hand this spec's findings
  to the Curator, and **finish through close-out** (role step 10) — publish the merge, re-attempt
  and prune evidence, delete the build branch and its worktree, and set `closed`. Ask once, and
  leave nothing half-finished behind you.
