# Building a harness — an agent-first guide

This guide is written to be **handed to your own Builder** (your AI agent): give it this
file and ask for the integration you want. Everything it needs is in this repo — the
contract, the config surface, the dry-run, and a worked example.

Out of the box, a Grillwork install ships **bare files only**: there is no default
visibility surface. The spec files themselves and
`python .grillwork/engine/lib/grillwork spec-status <spec>` are the
out-of-box view of where every spec stands. Anything more — a synced project view, a
chat notification, a dashboard, an evidence publisher — is a **harness**: your own
commands, run by the engine at its lifecycle events. The engine never names what a hook
is for; you decide.

Four steps: read the contract, build a hook, wire the config, prove it with the dry-run.

## 1. Read the contract

Read `.grillwork/engine/hooks-contract.md` — it is short and normative. The essentials:

- Three lifecycle events: `on-spec-created`, `on-transition`, `publish-evidence`. All three
  are loop events — installation is a prompt, not a command, so nothing fires at install.
- The payload is a doorbell — `GRILLWORK_*` environment variables naming the event, the
  spec path, and (for transitions) the old/new status pair. Derive real state from the
  files, never from the payload alone.
- Every event but `publish-evidence` is fire-and-forget and fully detached; hooks may
  run concurrently and out of order, may fire from a build worktree, and must tolerate a
  spec path that has vanished by the time they read it.
- A **read surface** as well as events: the commands a harness runs to read what the
  engine knows, rather than restating it. See "Ask the engine" below.
- Note the contract version at the top. It bumps when either side of the boundary moves
  significantly — the engine's behavior at it, or the code that manages it, including the
  worked examples you copied from. That bump, and nothing else, is your signal to re-check a
  harness; the contract's own list says what each version changed.

## 2. Build a hook

A hook is any command your platform can run — a script in your repo is the usual shape.
It reads the `GRILLWORK_*` variables, opens the spec file (tolerating its absence), and
does its one job. It owns its own logging and its own settings (a harness's
configuration is the harness's, not the engine's).

**Worked examples:** two, at the Grillwork engine repo root — one per kind of event.
(Examples live in the engine's repo; they are not stamped into your install.)

- `examples/github-projects/` — the **detached** kind. The GitHub Projects sync, a full
  harness: an `on-transition` / `on-spec-created` hook that projects each spec's status
  onto a GitHub Projects view, with its own settings file and its own tests. Read it as
  the template for your own: where it reads the payload, where it re-reads the spec file,
  and how it stays silent and harmless when there is nothing to do.
- `examples/publish-local/` — the **awaited** kind. A `publish-evidence` hook, in one
  standard-library script: artifact selection, the dry run, the stdout pair protocol, and
  why its exit code matters more than a detached hook's ever does.

### Ask the engine; never restate it

Some of what a harness needs is a fact about the **engine**, not about your board or your
change: which files in a bundle are artifacts rather than the textual account, what the
acceptance package says, what the lifecycle's stages are. Every one of those is printed:

```
python .grillwork/engine/lib/grillwork package <spec>              the acceptance-package model
python .grillwork/engine/lib/grillwork evidence-artifacts <spec>   the bundle dir + its artifacts
python .grillwork/engine/lib/grillwork statuses                    the lifecycle, in order
python .grillwork/engine/lib/grillwork spec-status <spec>          one spec's status
```

Each prints one JSON object on stdout and nothing else, so any language can read it. These
are **part of the hook contract** — their shapes change only when its version does, and
`hooks-contract.md` states them. Do not copy these facts into your harness and do not import
the vendored Python package to get at them: a copy is a fork that drifts, and an import works
only from Python and only where the import path happens to be right. Run the helper and parse
the JSON.

The one thing you cannot ask for is where the engine is. Walk up from `GRILLWORK_SPEC_PATH`
(or your hook's own location) to the nearest directory holding `.grillwork/` — **including
that starting directory itself** — and treat it as the repo root. Everything above is
repo-relative from there, so your harness works wherever you put it, and a hook that fired
from a build worktree finds the right repo rather than the one you happened to run from.

**This applies to your harness's tests too.** They are the part most likely to reach for a
shortcut the runtime cannot have — an import that resolves because a test runner arranged a
path, a walk up a fixed number of directories to a layout that is yours today. Both pass
where they were written and nowhere else, which is the one property a test of a harness must
not have. Let the tests find the install by the same walk and ask its helper the same way.

## 3. Wire the config

Bind the hook in `.grillwork/settings/config.json` under `"hooks"` — each event takes a
list of commands, each an **argv list**, run without a shell:

```json
{
  "hooks": {
    "on-spec-created": [["python", "hooks/sync.py"]],
    "on-transition": [["python", "hooks/sync.py"]]
  }
}
```

An absent event is simply skipped. For `publish-evidence`, bind **at most one** command
and set `"evidence": {"push": true}` — see the contract's publish protocol for the
exit-code and stdout rules, and `examples/publish-local/` for them implemented.

## 4. Prove it with the dry-run

Fire the binding synthetically before you trust it:

```
python .grillwork/engine/lib/grillwork fire-hooks on-transition
```

That spawns every command bound to the event exactly as the real trigger would — no
shell, detached — with a synthetic payload carrying `GRILLWORK_DRY_RUN=1`, set here and
never on a real event, so your hook can tell a rehearsal from the thing itself. It
reports each hook as spawned or failed, exits nonzero if any failed to spawn, and skips
a binding that is not an argv list with a warning naming the remedy. What it proves is
the **spawn**: `publish-evidence` is really awaited with its stdout parsed, so for that
event a dry-run proves only that the command starts, never the publish protocol.

**Answer `GRILLWORK_DRY_RUN` before your hook reads anything.** The rest of that payload is
invented — the spec path it names does not exist on purpose — so every check your hook would
make is a check against fiction. Report on stderr, do nothing observable, and exit 0. Get
this backwards and your hook fails its own rehearsal on the invented input, which for a
detached event nobody even sees.

Then trigger a real event — `python .grillwork/engine/lib/grillwork new-spec --title
"scratch"`, or `spec-status --set` on a scratch spec — and watch your harness act.
