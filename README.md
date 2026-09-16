# Grillwork

**An engine that grills you for a complete spec, then uses each build to grill better.**

Grillwork is the method and its engine: **definition-bounded loops** that grill a request
into a proven spec and build it to a proven Done, **independent adversarial review** at
every level — no agent accepts its own work — **evidence** that makes "done" falsifiable,
a human involved at just **two points** (approving the spec, judging the result), and a
**learning loop** that improves the grilling itself. It is tool- and platform-neutral,
distributed as its own repo and applied as an **overlay onto an existing project**, with
any Builder capable of running independent reviewers. Everything between the two human
touchpoints is a function of the spec.

> This paragraph is the **definition of record**: everything else links here rather than
> restate it.

> **Status:** early.
> **Both halves are built** — the `v1` spec factory *and* the `v2` development loop — and the
> engine was run on its own development: its own features were specified, built, verified and
> accepted through the loops end to end, before the method was separated out from the repo that
> authors it. See [the roadmap](#status--roadmap).

## The problem

The normal way you work with an AI is to tell it what you want and hope you covered
everything. You didn't — you never do. The gaps don't announce themselves; they surface
later as a wrong result, after the work is already built on top of them. And because an
autonomous agent can't be steered mid-task the way a human teammate can, every gap you
left is a gap it silently guessed at.

Two things make this worse in an unattended setting:

- **You're the bottleneck for completeness, but you don't know what's missing.** Knowing
  what to specify is expert work. Most of the burden lands on the person least able to see
  the holes.
- **The agent grades its own homework.** An agent that measures its own completion will
  declare victory on incomplete work, confidently.

## What Grillwork does about it

Grillwork inverts both. It **pulls** the specification out of you by questioning instead of
waiting for you to push a complete one, and it **never lets the authoring agent certify its
own work** — an independent reviewer has to agree first.

You don't tell it everything up front and hope. It interrogates you until the request is
complete enough to build, and a separate reviewer confirms it, so nothing gets
rubber-stamped.

## The core model

Grillwork treats a development process not as a phase pipeline with gates, but as a set of
**nested autonomous agent work loops**, each bounded by a measurable **stopping case**. An
agent can run a loop unattended precisely because it can measure its own completion. Three
ideas make each loop work — they are the whole system:

1. **Definitions are stopping cases.** The *Definition of Ready* terminates the
   spec-generation loop; the *Definition of Done* terminates the development loop. A
   definition isn't a quality bar sitting beside the work — it's the machine-checkable
   termination condition that makes unattended looping possible at all.

2. **Grilling is how a loop reaches its stopping case.** Rather than the user pushing a
   complete request, the agent **interrogates** the user to pull what's missing, using the
   definition as its rubric, until the gap between "what was told" and "what the definition
   requires" closes. This lowers the user's burden from *knowing what to specify* to
   *answering what is asked*.

3. **Adversarial review is how the system trusts completion.** No agent accepts its own
   work. An independent reviewer takes a genuine devil's-advocate stance — not
   rubber-stamping, not granting premises — and tests whether the stopping case was truly
   reached. **Self-measurement proposes; independent adversarial review disposes.** It
   applies to every kind of work — spec, code, tests — not just application code.

## The development process that improves itself

Grilling and building are not two tools bolted together — they form a single cycle with the
specification at its center. The interrogation draws a spec out of you; the change is then built
from it **unattended**, bounded by the Definition of Done. That build is the proving ground for the
spec: every question it is forced to ask, and every refinement you make once you can finally see
the result, marks a place the interrogation didn't dig deep enough. Grillwork records those, and
the Curator distills them into questions the Griller asks **up front on the next spec**.

So the real output is not any single spec — it is an interrogation that gets sharper each time it
runs. You shape the spec and judge the result; the process learns to need less of both. This is
not aspirational: a gap found during an early build already became a recorded finding, then a
curated lesson, so the next spec is grilled on that class of gap before it can recur.

## The lifecycle

A change moves through Grillwork as a single status, from first draft to closed. Two of the
transitions are **yours** — approving the spec and accepting the result; every other step is an
agent reaching a measurable stopping case. That status field is the spine the whole engine turns
on.

**Two commands drive the whole lifecycle**, one per half, and each runs to a decision that is
yours. Nothing bridges them: an approved spec sits and waits until you start the build.

```
   ┌─ /grillwork-specify ──────────────────────────────────────┐
   │                                                           │
   │   drafting ────▶ ready ────▶ approved                     │
   │                          ★ you approve, and the run ends  │
   └───────────────────────────────────────────────────────────┘

         ⋮   an approved spec waits here indefinitely.
         ⋮   nothing starts the build except you naming it.

   ┌─ /grillwork-build ────────────────────────────────────────┐
   │                                                           │
   │   building ────▶ verified ────▶ accepted ────▶ closed     │
   │                            ★ you accept, and it merges,   │
   │                              publishes and cleans up      │
   └───────────────────────────────────────────────────────────┘
```

Inside `/grillwork-specify`, the Griller grills to a proposed-Ready spec and convenes the
independent DoR review that disposes it; a NOT READY verdict is a lap inside the run, not
something handed back to you. Inside `/grillwork-build`, the Builder isolates the work on its own
branch, dispatches Coders behind independent Code Reviewers, convenes the DoD review that
disposes the result, and — once you accept — merges, publishes and cleans up.

**The commands** — what each does, and who moves it:

| Command | What it does | Moves status | Driven by |
|---|---|---|---|
| `/grillwork-specify` | Grills a request into a Definition-of-Ready-complete spec, convenes the independent Ready review, and presents the spec for your approval | `drafting → ready → approved` | Griller (agent), then **you** |
| `/grillwork-build` | Orchestrates the build — dispatches Coders, gates each through a Code Reviewer — convenes the independent DoD review, presents the result for your acceptance, then merges, publishes and cleans up | `approved → building → verified → accepted → closed` | Builder (agent), then **you** |
| `/grillwork-curate` | Distills what grilling missed into the improvements list the Griller reads | — *(learning loop)* | Curator (agent) |

Four more exist as **re-entry points**, for resuming a run that was interrupted rather than for
ordinary use — `/grillwork-review` to dispose a spec again on its own, `/grillwork-approve` to
approve one left at `ready`, `/grillwork-accept` to take delivery of a result left at `verified`,
and `/grillwork-close` to finish a change left `accepted` but unpublished. Each re-enters a step
of the run it belongs to; none of them is a rung you are expected to climb by hand.

Two more are **maintenance**, touching the installation rather than any spec —
`/grillwork-upgrade <source>` updates the engine to a newer version without re-asking a single
question the first install already settled, and `/grillwork-uninstall` removes Grillwork
altogether, deleting the engine and the commands while asking before it goes near your specs or
settings.

**Grillwork runs only when you name it.** Installing the method does not change what your agents
do with an ordinary request: a repo with Grillwork behaves exactly like one without it until one
of these commands is invoked. Telling an agent to go work on an already-defined piece of work
gets you that work, not an interrogation — and reading a Grillwork spec is not an instruction to
build it. That is enforced from both sides: the commands are worded to disqualify themselves from
being picked on an agent's own judgment, and every role checks that it was dispatched from a real
run and refuses out loud when it wasn't.

`verified` means **proven and merge-ready, not yet merged** — the merge lands when you accept.
Each build runs isolated on its own branch and worktree, while specs are authored on the trunk so
their numbers cannot collide: isolate the *build*, keep the *numbering* on the trunk.

**End to end**, a change travels:

1. **Install & attach** — point your agent at [`INSTALL.md`](INSTALL.md); it writes the method
   into your repo and realizes the commands for your harness.
2. **Grill it to an approved spec** — `/grillwork-specify <request>` interrogates you into a
   spec, convenes an independent reviewer that confirms it meets the Definition of Ready, and
   presents the result for your approval. A NOT READY verdict is a lap of the same run, not your
   problem to drive. The run ends the moment you approve.
3. **Decide to build it** — nothing happens until you say so. An approved spec is a document
   sitting in your repo; your agents can read it, work from it, or ignore it, and none of that
   starts the loop.
4. **Build it** — `/grillwork-build <spec>` orchestrates the change behind independent reviewers,
   convenes the reviewer that disposes it against the Definition of Done, and presents the
   verified result for your judgment. On your **yes** it merges, publishes, cleans up its branch
   and closes. Again, a rejection is a lap of the same loop.
5. **Learn from it** — `/grillwork-curate` folds what grilling missed back into the questioning,
   so the next spec starts sharper.

## The method vs. the three concerns

Only the **method** — the loops, definitions, grilling, and review — is truly "the
process." The method never names a specific tool, platform, or location. Everything
project-specific plugs in through three substitutable concerns that each adopter supplies:

- **the Tracker** — where work is tracked and made visible. The engine ships no tracker
  binding: it fires versioned lifecycle **hook events** at the repo's edge, and the adopter's
  own harness attaches whatever tracking system it likes against them — a stamped
  harness-building guide and a worked GitHub Projects example show how.
- **the Builder** — who or what authors the change: an autonomous AI, vendor-pluggable
  (Claude / Codex / Cursor). This assumption is *why* the spec bar is so high — an
  unattended AI can't be steered mid-task, so completeness must be front-loaded.
- **the Environments** — where code is executed, tested, and deployed: a pipeline of
  checkpoints at increasing fidelity, each step more real than the last.

The litmus test of correctness: any real process should be describable as "the Grillwork
core method + one particular configuration." If nothing project-specific is left in the
engine, the boundary is real.

## How it's delivered

Grillwork is its own versioned repo, **applied as an overlay** onto a project that already
exists. It is **not** a template you clone to start a project, and it does not own or
restructure the target's code.

That makes one boundary load-bearing — the framework-vs-app-code line. The **engine**
(definitions, roles, loop machinery) is a projection of a pinned Grillwork version, stamped
into `.grillwork/engine/`; **instance data** (your specs, config, and the lessons the loop
learns) is your repo's own. Both live in one tree, so the line is *provenance*, not location,
and the rule that matters is that **a re-stamp never overwrites what the runtime produced**.

## What it does end to end

Grillwork runs the whole process — the spec *and* the change built from it:

- **Behavior:** grill a requester to a Definition-of-Ready-complete, adversarially-reviewed
  spec; then, on approval, orchestrate the build, verify it against the Definition of Done,
  and — on the human's acceptance — merge it. Every gap the build exposes feeds back into the
  next spec's grilling.
- **Output:** the spec as a **file committed into the adopter's own repo**, and the verified
  change merged onto the integration target. The **repo is the interface**: acceptance reads
  the spec file and its evidence bundle; any board or dashboard is a downstream projection an
  adopter builds through the hook contract.
- **Primary user:** a **single responding user** — a solo builder working with an AI — who
  requests the change, answers the interrogation, approves the spec, and judges the result.
- **Human touchpoints:** two — approving the Ready spec, and accepting the verified result.
  Everything between is a function of the spec.

Both stopping cases — the **Definition of Ready** and the **Definition of Done** — are accepted,
and the runtime for both loops is built.

## Status & roadmap

Grillwork's own features were built through the loops before the method was separated out from
the repo that authors it.

- **v1 — the specification loop** (built): the spec factory — grill a request to a Ready,
  adversarially-reviewed spec.
- **v2 — the development loop** (built, 2026-07-11): take an **approved** spec toward release.
  The **Builder orchestrates** — it decomposes the work, dispatches Coders, and gates
  each unit through an independent Code Reviewer before accepting it (recursively; no agent
  accepts its own work) — then proposes the result Done and convenes the review that judges it.
  That independent **DoD-Reviewer**, blind to the build, disposes against the Definition of Done —
  running the derivation hunt for
  ungrounded decisions — and marks it `verified`: proven and merge-ready, but not merged. The
  human accepts the result (the merge lands on acceptance), and a **Curator** distills what
  grilling missed back into the questioning — the learning loop that makes the next spec sharper.
- **The engine boundary — hooks in, trackers out** (built): the engine stops at the repo's
  edge. In place of built-in tracker integrations it exposes a versioned **hook contract** —
  named lifecycle events (`on-spec-created`, `on-transition`, `publish-evidence`)
  that invoke adopter-configured commands — plus a configurable
  **evidence disposition**: `commit` and `push` booleans, an always-written
  `evidence/manifest.json`, and publish-gated pruning. The earlier built-in board
  (specs 001–002) is removed; the GitHub Projects binding (specs 007–008) lives on as the
  worked example in `examples/github-projects/`, wired like any adopter harness. Tracker
  integrations are adopter harness now, not engine work — the installed guide is the
  deliverable, not more bindings.
- **Installation became a prompt** (2026-07-25): the installer CLI, the per-Builder compiler
  and the adapter registry are removed. An adopter's own agent reads
  [`INSTALL.md`](INSTALL.md) and writes the engine into their repo, which means everything
  installed is byte-identical everywhere and therefore committed — a fresh clone has the loops
  with no install step. The deterministic helper stayed, vendored into the repo and run in
  place on the standard library alone.
- **Ahead:** the **Environments** — running, testing, and deploying at increasing fidelity.
  Nothing else is queued.

## Install

**Prerequisites**

- **Python ≥ 3.10** on `PATH` as `python` — for the small deterministic helper the roles call
- **git** — builds run on their own branch and worktree
- **an agent that can spawn an independent subagent** — today that is
  **[Claude Code](https://claude.com/claude-code)**. Every gate in the method is disposed by a
  reviewer that did not do the work, so a harness that can only self-review cannot run it.

**Installing.** There is nothing to install. Grillwork is text: get a copy of this repository
and point your agent at [`INSTALL.md`](INSTALL.md) —

```
read Grillwork's INSTALL.md and install it into this repo
```

— and the agent writes the method into `.grillwork/` and realizes the `/grillwork-*` commands
in whatever form your harness reads. Nothing goes on your `PATH`, no package is installed, and
every file it writes is identical on every machine, so you commit them and a colleague's fresh
clone has the loops without an install step.

Re-running the same prompt is how you update: the method is re-copied wholesale, and your
specs, findings, and settings are left alone.

## Quickstart

From inside **the repo you want to work on** — either an established project or an empty
repository you're starting from scratch — install as above, then work in your Builder:

```
/grillwork-specify  add CSV export to the reports page
```

It interrogates you until the spec meets the Definition of Ready, writes it to
`.grillwork/specs/<NNN>-<slug>/spec.md`, has an independent reviewer dispose it, and presents it
for your approval — then stops. The spec sits there until you decide to build it:

```
/grillwork-build  .grillwork/specs/001-add-csv-export/spec.md
```

which orchestrates the change behind independent reviewers, presents the verified result for
your acceptance, and on your yes merges, publishes and cleans up.

The spec files themselves and `python .grillwork/engine/lib/grillwork spec-status` are the out-of-box view of where every
spec stands. For anything richer — a board, notifications, a dashboard — the engine fires
lifecycle hook events at every spec creation and status change; the stamped guide at
`.grillwork/engine/harness-guide.md` walks your own Builder through wiring a harness against
them, with two worked examples beside it — the GitHub Projects sync in
`examples/github-projects/` for a detached hook, and `examples/publish-local/` for the awaited
`publish-evidence` one.

## Development

Grillwork is a method distributed as text, plus a small standard-library-only helper. From a
checkout:

```bash
uv run pytest                        # the test suite
uv run ruff check .                  # lint
python engine/lib/grillwork statuses # the helper answering, from source
```

This repo **authors** the method; it does not install it. There is no `.grillwork/` here, so the
helper's install-dependent commands (`config`, `new-spec`, `spec-status` and the rest) have
nothing to resolve against and say so rather than guessing — the suite exercises them against
throwaway installs it builds in temp directories.

The helper carries the operations that must be exact every time: `new-spec`, `next-seq`,
`markers`, `tasks-path`, `build-branch`, `config`, `spec-status`, `record-finding`,
`evidence-manifest`, `prune-evidence`, `fire-hooks`. In an **adopter's** repo it is vendored at
`.grillwork/engine/lib/grillwork/` and run in place, so the invocation is one repo-relative path
that is identical on every machine and needs nothing installed. `uv` is used here only for this
repo's own test runner and linter; an adopter needs neither.

Hooks have no command of their own: they fire automatically when a spec is created or changes
status. In an adopter's repo, `python .grillwork/engine/lib/grillwork fire-hooks <event>`
dry-runs the hooks bound to an event with a synthetic payload.

The `/grillwork-*` commands your Builder invokes are written by the install prompt from
`engine/commands/` — the sources live in this repo alongside `engine/roles/` and
`engine/definitions/`, and are tabulated under [The lifecycle](#the-lifecycle).

How the engine is put together — and what each role does — is in the role definitions
themselves, under [`engine/roles/`](engine/roles/). Each is the authority on its own role.

## Documentation

Everything Grillwork ships is plain text, and the engine is its own documentation. Read in
this order:

1. [`INSTALL.md`](INSTALL.md) — what an install consists of. There is no installer program:
   an adopter's own agent reads this file and writes the method into their repo, which makes
   it the normative statement of what an install *is*.
2. [`engine/definitions/`](engine/definitions/) — the two normative stopping cases: the
   [Definition of Done](engine/definitions/definition-of-done.md), and the
   [Definition of Ready](engine/definitions/definition-of-ready.md) derived from it.
   Everything else in the method exists to reach one of them.
3. [`engine/roles/`](engine/roles/) — the eight roles that *are* the method: Griller,
   DoR-Reviewer, Builder, Coder, Code Reviewer, Acceptance-Test Writer, DoD-Reviewer and
   Curator. Each file is the authority on what that role does, and on what it refuses to do.
4. [`engine/spec-template.md`](engine/spec-template.md) — the document a grilling fills in.
   It is the Definition of Ready rendered as sections, so "which sections are thin" and
   "which conditions are still open" are the same question.
5. [`engine/hooks-contract.md`](engine/hooks-contract.md) and
   [`engine/harness-guide.md`](engine/harness-guide.md) — the versioned lifecycle events the
   engine fires at the repo's edge, and how to wire your own tracker, notifier or publisher
   against them without the engine ever naming one.
6. [`examples/`](examples/) — two worked harnesses against that contract:
   `github-projects/` for a detached hook, and `publish-local/` for the awaited
   `publish-evidence` one.

## Glossary

- **Work loop** — an autonomous agent process bounded by a measurable stopping case.
- **Stopping case** — the machine-checkable condition that terminates a loop.
- **Definition of Ready (DoR)** — the stopping case for the spec-generation loop.
- **Definition of Done (DoD)** — the stopping case for the development loop.
- **Grilling** — interrogation that pulls missing information from the user, driven by a
  definition as its rubric.
- **Adversarial review** — an independent reviewer confirming a stopping case was genuinely
  reached, taking a devil's-advocate stance.
- **Overlay** — Grillwork's form of delivery: attached to an existing repo without owning
  its code.
- **Engine vs. instance data** — the engine ships in the Grillwork repo; the adopter's
  specs, config, and learned data live in theirs.
- **The Tracker / the Builder / the Environments** — the three substitutable,
  adopter-supplied concerns the method plugs into.
