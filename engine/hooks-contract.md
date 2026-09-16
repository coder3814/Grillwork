# The Grillwork hook contract

Contract version: 5

This is the engine's boundary at the repository's edge, and it has two halves. **Outward:**
a small set of lifecycle events at which the engine runs commands the adopter configured —
the engine never names what a hook is *for*, there are only commands run at events.
**Inward:** a small set of commands a harness may run to read what the engine knows. The
**repo is the interface**: the payload a hook receives is a doorbell, and the files are the
source of truth.

**Versioning rule.** The contract version above is a single integer, bumped whenever either
side of this boundary moves significantly: **the engine's behavior at it** — the events, the
payload, the read surface, or the semantics documented here — or **the code that manages
it**, meaning the engine's own dispatch and read-surface implementation together with the
worked examples an adopter copies as the reference. The number exists to say "re-check your
harness," and a harness is as exposed to a reworked reference implementation as to a changed
payload. An engine release that moves neither is not a bump.

- **v2** added a first-install event; **v3** removed it, and the install-time events with it.
- **v4** added the read surface, previously reachable only by importing the engine's Python
  package — not a boundary a harness in another language could cross.
- **v5** states what a hook owes the dry run (below, and again in the publish protocol), and
  reworks both worked examples so that a copy runs where it lands: the reference publisher
  now answers the rehearsal before it reads anything, and each example's own tests reach the
  engine by the walk and the read surface rather than by an import or a fixed depth.

## The events and their trigger sites

| Event | Fires |
|---|---|
| `on-spec-created` | when a spec file first exists (`new-spec`). |
| `on-transition` | on **every** status change (`spec-status --set`) — regressions included (`verified → building`, `ready → drafting`). The payload's old/new pair is how a hook distinguishes a send-back; the engine holds no notion of "forward." |
| `publish-evidence` | when a spec turns `verified` — before the human approve — and only when the `evidence:` section's `push` boolean is true. Unlike the others, this event is **awaited** (see the publish protocol below). |

**There are no install-time events** (`on-upgrade` removed in contract v3, after the
first-install event in v2). Installation is a prompt an agent follows, not a command this
engine runs, so the engine is never present at the moment a repo is set up or refreshed — it
has nothing to ring from. Every event above is a loop event, fired by the command that caused
it. A harness that needs to react to a method update watches the files, which are committed
and therefore diffable.

## The payload

Transport is environment variables layered on the hook's inherited environment — a
doorbell, nothing more. The hook reads what it needs from the files.

| Variable | Carried by | Meaning |
|---|---|---|
| `GRILLWORK_EVENT` | every event | the event name. |
| `GRILLWORK_SPEC_PATH` | spec-scoped events (`on-spec-created`, `on-transition`, `publish-evidence`) | absolute path to the spec file, as seen from where the trigger ran. |
| `GRILLWORK_OLD_STATUS` / `GRILLWORK_NEW_STATUS` | `on-transition` | the status pair — present on every change, regression or not. |
| `GRILLWORK_DRY_RUN` | `fire-hooks <event>` only | set to `1` when the payload is synthetic (the dry-run); never set on a real event. |

**A dry-run payload is invented, and a hook must answer it before it reads anything.**
`fire-hooks <event>` fills the payload with placeholders — including a `GRILLWORK_SPEC_PATH`
that **deliberately does not exist**, since a hook has to tolerate a vanished path in any
case. So a hook that validates its payload first fails the one run whose purpose is to prove
it works, and its exit code says so about fiction rather than about the wiring. Check
`GRILLWORK_DRY_RUN` before anything else the payload feeds, report on stderr, do nothing
observable, and succeed. This bites hardest for `publish-evidence`, the one event whose exit
code is read on a real fire: the rehearsal is spawned detached like any other, so a publisher
that fails its own dry run fails it **silently**.

## The read surface

What a harness needs that the files alone do not plainly say — which of a bundle's files are
artifacts rather than the textual account, what the acceptance package holds, what the
lifecycle's stages are — the engine **prints**. These commands are part of this contract and
change only with its version.

Run them as `python .grillwork/engine/lib/grillwork <command>` from anywhere, with paths as
given. Each prints **one JSON object on stdout and nothing else**; warnings and errors go to
stderr, and a failure is a nonzero exit. That is the whole transport, so a harness in any
language can read it.

| Command | Prints |
|---|---|
| `statuses` | `{"statuses": [...]}` — the lifecycle stages, **in order** |
| `spec-status <spec>` | `{"path": …, "status": …}` — one spec's current stage |
| `evidence-artifacts <spec>` | `{"dir": …, "artifacts": [...]}` — the bundle directory, and the files in it that are artifact **bytes** rather than the account (`bundle.md`, `manifest.json`, `.gitignore`) |
| `package <spec>` | the neutral acceptance-package model (below) |

`package` prints the whole model, so a renderer never returns to the spec files for a part of
it: `state`, `status`, `summary`, `what_was_done`, `evidence`, `evidence_map_present`,
`verdict`, `base_sha`, `candidate_sha`, `findings`, `amendments`, `bundle_present`,
`missing_sections`. Absent content is `null` (or an empty list) rather than an error — a spec
not yet built is an ordinary state a harness still has to show. Each `evidence` row carries
`criterion`, `shows`, and `artifacts`, each artifact an object of `ref` (the bundle's own
spec-dir-relative cell, verbatim) and `present` (whether that file is on disk). Forming URLs
from any of it is the harness's job; the engine forms none.

**Restating any of this in a harness is out of contract.** A copied rule is a fork that
drifts, and these are exactly the facts that change without a spec file changing.

**Finding the engine is the one thing not printed**, since a harness must locate it before it
can ask anything. Walk up from `GRILLWORK_SPEC_PATH` (or the hook's own location) to the
nearest directory holding `.grillwork/` — **including the starting directory itself** — and
treat that as the repo root. Deriving it from the working directory is wrong: hooks fire from
wherever the trigger ran, which for a mid-build transition is the build's worktree.

## Configuration binding

Hooks are bound in `.grillwork/settings/config.json` under a `hooks:` section: each event
binds a **list of commands**, each an **argv list** — e.g.
`["python", "hooks/sync.py"]` — run in binding order **without a shell**, so Windows and
POSIX behave identically and no argv element is ever shell-interpreted. An event with no
binding (absent, commented out, or an empty list) is simply skipped. A binding that is
not an argv list (e.g. a bare string) is a config error: at fire time it is skipped with
a warning naming the remedy, and `fire-hooks <event>` surfaces it ahead of a real trigger.

## Failure semantics

- **Full detachment.** Every event except `publish-evidence` is fire-and-forget: the
  hook is spawned **fully detached** — the trigger never waits, never raises, and never
  changes its exit code. The engine warns on stderr **only for a spawn failure**
  (command missing, not executable); a hook that starts and then fails is its own
  responsibility to log.
- **Concurrency and ordering.** Detached hooks may run **concurrently and out of order**
  relative to their triggers and to each other. Treat the payload as a doorbell and
  derive state from the files, never from the payload alone.
- **Firing location.** Hooks fire from **wherever the triggering command runs** — no
  path rebasing. Mid-build transitions fire from the build's worktree, so
  `GRILLWORK_SPEC_PATH` may point into a build worktree and the hook sees live build
  state not yet on the trunk. A detached hook may also **outlive its trigger** and find
  that worktree already gone (removed at close): a hook must tolerate a **vanished
  path** rather than assume `GRILLWORK_SPEC_PATH` still exists.

## The publish protocol (`publish-evidence`)

The one awaited event. It fires at the `verified` flip when `push` is true, and its
outcome gates evidence pruning — never the flip or the acceptance.

- **At most one command** may be bound — one exit code, one stdout parse, one success
  record. A multi-destination publish is one wrapper script the adopter writes. More
  than one bound command, or `push: true` with none bound, warns and records no success.
- **Success is exit code 0, alone.** On success the engine records it (with a
  timestamp) in the spec's `evidence/manifest.json`.
- **stdout protocol.** The hook prints one `<artifact-name> <url>` pair per line on
  stdout; on exit 0 the engine records the URLs beside the artifact hashes. A stdout
  line that is not such a pair is ignored with a warning — success is governed by the
  exit code alone, never by stdout shape.
- **A failed publish never blocks** `verified` or acceptance; it only blocks the prune of
  artifact bytes.
- **A dry run publishes nothing and exits 0.** `fire-hooks publish-evidence` spawns the bound
  command detached with a synthetic payload, so it proves only that the command starts —
  never the protocol. Answer `GRILLWORK_DRY_RUN` first (see the payload above) and claim no
  URL: there is none to claim, and a URL claimed here would be recorded against nothing.
