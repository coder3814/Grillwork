# Install Grillwork

**This file is a prompt.** Point your coding agent at it — "read Grillwork's INSTALL.md and
install it here" — and the agent does the work. There is no installer program, nothing to
`pip install`, and nothing to put on your `PATH`.

You are the agent reading this. What follows is your instruction.

---

## What you are installing, and why

Grillwork is a **method**: a set of roles your harness invokes as commands, the definitions
those roles hold each other to, and a spec template. All of it is text. Your job is to copy
that text into this repository and realize the commands in whatever form *your* harness reads
— you know your own conventions better than any installer could, which is the whole reason
this is a prompt and not a program.

Two starting conditions, both normal:

- **An empty repository.** Everything needed to start a project from nothing.
- **An established project** — its own code, its own agent configuration, its own conventions.
  Add Grillwork alongside all of it and disturb nothing that was already there.

## First: is this a fresh install or an update?

Look for **`.grillwork/settings/config.json` or `.grillwork/settings/config.yaml`**. Either one
present is the whole test, and it decides which of two genuinely different jobs you are doing.

- **Neither — a fresh install.** Read this file straight through.
- **Either — an update.** The person has already answered every question below. **Skip "Write
  the settings" entirely**, and follow ["Updating an existing install"](#updating-an-existing-install)
  at the end for what an update replaces and what it must not touch.

The YAML name matters because the oldest installs are the ones an update helps most, and they
are the ones that carry it. Testing for `config.json` alone would read the oldest install in
existence as a bare repo and re-ask its owner everything.

Getting this wrong is not a small annoyance. The settings hold answers only the person can
give — which branch a finished change lands on, what command proves the existing build still
works, which hooks reach whatever they track work in. Re-asking those on an update wastes their
time at best; at worst they accept a default you offered while assuming you had read what was
already there, and a working binding is quietly replaced.

## Before you start: the one hard requirement

**Your harness must be able to spawn an independent subagent** — a fresh context that reviews
work it did not do. Grillwork's loops are built on independent review at every gate: a spec is
disposed Ready by a reviewer that never saw the grilling, and a change is disposed Done by a
reviewer that never saw the build. A harness that can only ever self-review cannot run this
method, and a self-accepting loop is worse than no loop, because it produces the appearance of
review.

If your harness has no subagent primitive, **stop now**. Write nothing, and tell the person
exactly that: their harness can't run Grillwork, and half-installing it would leave a loop
that rubber-stamps its own work.

Two more prerequisites, both worth checking before you write anything — if either is missing,
stop and say so, naming what's missing:

- **Python 3.10 or newer** on `PATH` as `python`, for the deterministic helper described below.
- **git.** Not incidental: the method isolates every build on its own branch *and its own
  worktree*, and merges on acceptance. A repo not under git can hold the specs but cannot run the
  development loop.

## What to write

Copy from this repository into the target repo. Everything is plain text and every byte is
identical on every machine — no absolute paths, no usernames, nothing machine-specific. That
is deliberate: the person is going to commit these files, and their colleague's fresh clone
has to work unchanged.

**Copy `engine/` to `.grillwork/engine/`, with one exception.** That is the whole rule. What
you are copying:

| | What it is |
|---|---|
| `roles/` | The eight roles — the method itself |
| `definitions/` | The Definition of Done and the Definition of Ready |
| `spec-template.md` | The spec every grilling fills in |
| `hooks-contract.md` | The lifecycle events and their payloads |
| `harness-guide.md` | How to wire hooks at the repo's edge |
| `lib/` | The deterministic helper (see below) |

**The exception is `engine/commands/`**, which does *not* get copied verbatim — it is realized
into your harness's own layout instead. See "Realize the commands" below.

Copy **wholesale**: replace the directory, never merge it file-by-file. A half-updated engine,
where one role is new and another is old, is the failure mode this instruction exists to
prevent.

**Copy the source, not what running it produced.** `lib/` is an executable Python package, so
the copy you are reading from may carry `__pycache__/` directories from someone having run or
tested it. That bytecode is *generated*, never *installed* — it embeds the absolute path it was
compiled from, which is exactly the machine-specific content this whole design exists to keep
out. **Skip every `__pycache__/` directory as you copy.** The engine ships a `lib/.gitignore`
that keeps any later-generated bytecode out of git; your job is only to not carry it in.

## Realize the commands

`engine/commands/` holds fourteen files. Each has frontmatter naming what it is:

- `kind: command` — something the person invokes directly (`/grillwork-specify` and the rest).
- `kind: subagent` — something a role dispatches; these are the independent reviewers, and
  they are why the subagent requirement above is non-negotiable.
- `tools:` — when present, the tools that subagent should be restricted to.

Write each one where **your** harness looks for it, in **your** harness's format. For Claude
Code that means `.claude/commands/grillwork-<name>.md` and `.claude/agents/grillwork-<name>.md`.
For another harness, use its equivalent — you know it; this file deliberately doesn't guess.

**What you write is pinned, so that two agents realizing the same version produce the same
file.** Everything installed is committed and compared by plain diff, so "the agent used its
judgment" cannot mean "the output varies." Exactly this, and nothing else:

- **The body is verbatim**, with one substitution: `{{ARGS}}` → your harness's argument
  placeholder (Claude Code: `$ARGUMENTS`). Do not reword, reformat, summarize, or add a
  preamble, however much you would like to.
- **Keep every `python .grillwork/engine/lib/grillwork …` invocation exactly as written.** It is
  repo-relative on purpose, so the file is identical on every machine. It assumes the working
  directory is the repo root, which is where agent commands run.
- **Carry `description` verbatim**, and — where present — `tools`, into the frontmatter,
  spelled the way your harness spells them. **The description is not a summary you may
  improve.** Each one deliberately spends most of its length warning you off: saying that the
  command runs only when a person names it, or that the subagent is internal to a running
  command and inert outside one. That text is load-bearing — see "Grillwork is invoked, never
  ambient" below — and shortening it to the capability half is the single easiest way to
  reinstall the bug it exists to prevent. Carry `name` too wherever your harness needs it
  rather than deriving it from the filename. Add no other key: not a model, not a colour, not a
  permission. If your harness truly requires one more, it is part of realizing for that
  harness — say so when you report what you wrote.
- **Drop `kind:`.** It is Grillwork's routing key and you have just consumed it: it told you
  which of the two directories the file belongs in. It means nothing to your harness.
- **Open the file with a do-not-edit banner**, in whatever comment syntax the format takes:

  ```
  Installed by Grillwork from engine/commands/ — do not edit.
  Re-running the install prompt rewrites this file wholesale.
  ```

  These are the only files Grillwork writes outside `.grillwork/`, sitting among the person's
  own commands. The banner is what stops someone editing one and losing the edit at the next
  update, with no idea why.

Prefix everything you write with `grillwork-`. That prefix is reserved, so your files sit next
to the person's own commands without colliding, and so removing Grillwork later is obvious
rather than archaeological.

## Grillwork is invoked, never ambient

**Installing Grillwork must not change what an agent does with an ordinary request.** A repo
with the method installed behaves exactly like one without it until somebody names a
`grillwork-*` command. Nothing the method owns — no role, no reviewer, no lifecycle status
change, no spec file written — happens on any other trigger.

This is easy to break and the break is quiet, so it is worth naming the failure. Told to go
work on an already-defined piece of work, an agent that can see a command advertising
itself as "grills a request into a complete spec" will match on that description and start
interrogating the person instead of doing the work they asked for. Nothing malfunctioned; the
agent chose a tool that looked apt. The same thing happens at the other end when an agent
reads a spec and finds a subagent offering to implement a unit of a build.

Two rules follow, and both are yours to honor as you realize the files:

- **Realize the descriptions as written.** They are worded to disqualify rather than to
  advertise, and that wording is the only signal a harness consults when an agent picks
  something on its own judgment.
- **Add no trigger of your own.** Do not write Grillwork into the repo's agent instructions,
  a memory file, a hook, an always-on rule, or anything else that would make the method apply
  to work nobody asked it to touch. The two commands are the whole entry surface. If the
  person wants their agents to always route work through Grillwork, that is theirs to add
  deliberately and theirs to remove — not something an install decides for them.

The roles enforce this from their side too: each one checks that it was dispatched from inside
a real run and refuses out of band rather than complying quietly. You are the other half.

## Write the settings

**Skip this entire section if `.grillwork/settings/config.json` already exists** — that is an
update, the answers below are already made, and re-asking them is the failure this section is
guarded against. Go to ["Updating an existing install"](#updating-an-existing-install).

Otherwise: write `.grillwork/settings/config.json`. Ask the person for anything you can't
determine from the repo, and offer what you found as the default:

```json
{
  "spec_home": ".grillwork/specs",
  "builder": "claude-code",
  "gate": "",
  "integration_target": "",
  "source": {
    "repo": "https://github.com/coder3814/Grillwork",
    "ref": "main"
  }
}
```

- **`spec_home`** — where specs are written. Match the repo's conventions if it has one.
- **`builder`** — the harness you just realized the commands for.
- **`gate`** — the command that proves existing behavior still works, e.g. `pytest` or
  `npm test`. Look for it in the repo before asking; leave empty if there genuinely isn't one.
- **`integration_target`** — the branch a finished change lands on. Usually the default branch.
- **`source`** — where this install came from, so an update needs no argument. Write the repo
  you are installing *from* and the ref you are on; if you were pointed at a local checkout,
  write that checkout's `origin` remote rather than its path, because a path on your machine
  is exactly the kind of thing that must not end up in a committed file. Leave the section out
  and the update falls back to the canonical repo above, which is right far more often than it
  is wrong — but record it when you know it, because a fork that omits it silently updates
  itself from upstream.

Two optional sections, both documented in `hooks-contract.md` and `harness-guide.md`. Leave
them out unless the person asks:

- **`hooks`** — commands to spawn at lifecycle events (`on-spec-created`, `on-transition`,
  `publish-evidence`), each an argv list. This is how a tracker, a notifier, or anything else
  outside the repo gets wired in.
- **`evidence`** — `{"commit": true, "push": false}` by default: whether evidence artifacts
  are committed, and whether they're published to external storage.

## The deterministic helper

`.grillwork/engine/lib/grillwork/` is a small Python package the roles shell out to for the handful of
operations that must be exact every time: minting a spec's sequence number, moving its status
through the lifecycle, counting open gap markers, hashing evidence. It runs in place —
`python .grillwork/engine/lib/grillwork <command>` — with the standard library alone. Nothing to
install, and it's committed with the repo so every clone has the same one.

Everything else the method does is the roles' own work, in prose, in the files you just copied.

## Finish

Tell the person what you wrote and where. Then verify, don't assume:

```bash
python .grillwork/engine/lib/grillwork config
```

That prints the resolved settings as JSON. If it does, the install is real.

Point them at `.grillwork/engine/roles/griller.md` for what happens next, and mention that
everything you wrote is meant to be committed.

## Updating an existing install

Running this prompt again is safe and is how the method is updated. An update is the same
writing as a fresh install with one section removed and one step added, and it **asks the
person nothing**.

**You are most likely reading a staged copy.** `/grillwork-upgrade` runs

```bash
python .grillwork/engine/lib/grillwork fetch-engine
```

which reads the `source` recorded in the repo's settings, refuses unless the git working tree
is clean — an update keeps no backup, because git is the undo — downloads that source's
archive, and extracts it to a temp directory outside the repo. The JSON it prints names the
staged `engine/` you copy from and the `install_doc` you are reading now, and reports
`current: true` when the installed engine is already identical to it — line endings aside,
because a downloaded archive ships LF where a Windows checkout may hold CRLF — in which case
there is nothing to do and the right answer is to say so and stop. When the update is finished,
delete the `staged` directory the JSON names; nothing else will.

That is the whole reason the fetch is a separate step: it stages, and nothing more. It never
writes into `.grillwork/`. The four steps below are still yours, and they are read from the
engine being updated *to* rather than from the one being updated away from.

If there is no staged copy — you were pointed at a checkout directly — nothing changes. Copy
from that checkout instead; the four steps are the same.

**Do exactly four things:**

1. **Replace `.grillwork/engine/` wholesale** — the same copy described in "What to write",
   directory-for-directory rather than file-by-file.
2. **Re-realize every command**, exactly as "Realize the commands" describes. They carry a
   do-not-edit banner precisely so that this overwrite is safe.
3. **Sweep the orphans.** Delete any `grillwork-*` command or subagent file you did **not** just
   write. The prefix is reserved, so anything else wearing it is a file from an older version
   that the current one no longer has — a command since removed, or one renamed. Nothing else
   deletes these: step 2 only overwrites the names it knows, so without this step a retired
   command survives every future update, still offering itself to any agent that reads its
   description. Say what you removed.
4. **Touch nothing else.** In particular, do not open `settings/config.json` to check it, and do
   not ask about anything in it.

**The one exception, for installs old enough to need it:** if the settings are a
`config.yaml` rather than a `config.json`, that is an install from a Grillwork that used YAML.
Convert it — carry every setting across unchanged, write `config.json`, delete the old file —
and still ask nothing. You are transcribing their existing answers into the format the helper
now reads, not collecting them again. Say that you converted it.

**What an update must leave exactly as it found it**: `settings/config.json`, the curated
`settings/improvements.md`, and every spec under the spec home with its findings and evidence.
Those are the person's and the loops' — written by the runtime, never by an install. If you
find yourself about to ask which branch changes land on, or what the test command is, you have
taken the fresh-install branch by mistake.

### Checking whether a repo is current

Because everything installed is committed and byte-identical to its source, **checking whether
a repo is current is a plain directory comparison** —
`diff -r engine/ <repo>/.grillwork/engine/ --exclude=commands --exclude=__pycache__`, ignoring
`commands/`, which is realized rather than copied, and the generated bytecode, which was never
installed in the first place. There is no version handshake and
nothing to interrogate; what is installed is what is in git. `fetch-engine` runs exactly that
comparison against what it just downloaded and reports it as `current` and `differing`, so the
check needs no checkout on disk. **Leave alone everything the person
or the loops produced**: their specs and the findings beside them, their `config.json`, and the
curated `improvements.md` under `.grillwork/settings/`. Those are theirs; the engine is not.

## Updating from a version that has no `/grillwork-upgrade`

There is nothing special to do, and nothing to install first. `/grillwork-upgrade` only fetches
the source and hands you back to this file; the update path above is the real mechanism, and it
has always been reachable the same way the original install was — **point the agent at this file
and say the repo already has Grillwork.** The shortcut's absence costs you one sentence of
typing, not a capability.

An install predating the `source` setting is likewise fine: with no source recorded, the fetch
falls back to the canonical repository and says which one it used. **Do not write the setting
in on its behalf** — `config.json` is the person's, and an update does not edit it.

Two leftovers appear only in installs old enough to predate the current shape. Neither is
deleted by the update path, because neither is something an install ever wrote:

- **`.grillwork/tracker/`** — the built-in board, removed when tracking became the adopter's own
  harness wired through the hook contract. It is generated output with no engine behind it any
  more.
- **Per-Builder compiled realizations**, from when the install was a program rather than a
  prompt, and anything else under `.grillwork/` that is neither `engine/`, `settings/`, nor the
  spec home.

**Report these; do not delete them.** They are dead, but they are also the person's, and an
update that quietly removes files it did not write has exceeded what it was asked to do. Name
them, say what each was, and let them decide.

## Removing Grillwork

Realized into the person's repo as **`/grillwork-uninstall`**, whose command body
(`engine/commands/grillwork-uninstall.md`) is the definition of what removal is — read it there
rather than looking for a procedure here.

The direction is deliberate. An update needs the engine you are updating *to*, so its procedure
belongs in this file, which travels with that engine. A removal needs no source at all, so its
procedure belongs with the install being removed — where it is present and current even when
this file is nowhere in reach.
