# Install Grillwork

**This file is a prompt.** Say it to your coding agent, from inside the repo you want it in —

```
install Grillwork into this repo from https://github.com/coder3814/Grillwork
```

— and the agent does the rest. There is no installer program, nothing to `pip install`, and
nothing to put on your `PATH`. You do not need a copy of Grillwork first; fetching it is the
agent's first step.

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

## Get the source

You were most likely given a URL and nothing else. Fetch Grillwork yourself — with your own
tools, because none of Grillwork's exist yet in this repo:

- **Download the archive** at `<repo>/archive/<ref>.zip` — `main` unless the person named a
  branch, tag or commit — and extract it. The generic archive form resolves all three alike.
- **Or clone it** somewhere outside the target repo, if that is easier for you.

Either way, put it in a temporary directory **outside the repository you are installing into**,
and **delete it when you are done**. It is scaffolding, not part of the install: everything that
matters ends up committed inside the target repo, and a stray checkout sitting next to it is
a second copy that will rot and mislead whoever finds it.

Then check what you got. It should hold `engine/` and this file at its top level; a GitHub
archive wraps both in a single `Grillwork-<ref>/` directory. If it doesn't, you have the wrong
thing — say so rather than copying it in.

**Remember the URL.** It is the one thing only this moment knows, and "Write the settings"
below records it so that updating later needs no argument. If the person pointed you at a
local checkout instead of a URL, use that checkout as the source and read its `origin` remote
for the URL to record.

## What to write

Copy from this repository into the target repo. Everything is plain text and every byte is
identical on every machine — no absolute paths, no usernames, nothing machine-specific. That
is deliberate: the person is going to commit these files, and their colleague's fresh clone
has to work unchanged.

**Copy `engine/` to `.grillwork/engine/`.** That is the whole rule. What you are copying:

| | What it is |
|---|---|
| `roles/` | The eight roles — the method itself |
| `definitions/` | The Definition of Done and the Definition of Ready |
| `commands/` | The command and subagent sources (see below) |
| `spec-template.md` | The spec every grilling fills in |
| `hooks-contract.md` | The lifecycle events and their payloads |
| `harness-guide.md` | How to wire hooks at the repo's edge |
| `lib/` | The deterministic helper (see below) |

**`commands/` is copied like everything else *and* realized on top of that.** The copy is the
source the realization reads — including every later update's, which is what lets an update
delete its download the moment it has placed it. Copying it is not a substitute for realizing
it: files sitting in `.grillwork/engine/commands/` are inert, and a harness will never find
them there. See "Realize the commands" below.

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

## Write down how you realized them

You have just made a handful of decisions only an agent running in this harness could make:
where each kind of file goes, what the argument placeholder is, how this format spells a
comment. **Record them**, in `.grillwork/settings/realization.json`, so an update can repeat
the realization mechanically instead of asking another agent to derive it again:

```json
{
  "format": "yaml-frontmatter",
  "argument_placeholder": "$ARGUMENTS",
  "banner": "<!-- {text} -->",
  "extension": ".md",
  "targets": {
    "command": ".claude/commands",
    "subagent": ".claude/agents"
  },
  "keys": {}
}
```

Those values are Claude Code's, shown to make the shape concrete. Write **yours**:

- **`targets`** — one repo-relative directory per `kind:`, which is what that key was for.
- **`argument_placeholder`** — what you substituted for `{{ARGS}}`.
- **`banner`** — a one-line comment template containing `{text}`, used for both banner lines.
- **`extension`** — the realized files' extension, dot included.
- **`keys`** — a source frontmatter key mapped to the name your harness spells it with, for
  example `{"tools": "allowed-tools"}`. Leave it empty when they match; anything unlisted is
  carried through as written.

**Write the profile only if it describes what you actually did.** `format` has one value that
can be replayed — `yaml-frontmatter`, meaning markdown with a `---`-fenced YAML header. If your
harness takes TOML, JSON, or bare files with no frontmatter at all, there is nothing honest to
record yet: leave the file out, say so when you report, and updates will hand the realization
back to an agent rather than write the wrong format and call it done.

This file is the **adopter's**, like `config.json`. An update reads it and never rewrites it.

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
- **`source`** — where this install came from, so an update needs no argument. Write the URL you
  were given in "Get the source", and the ref you fetched. Never write a path on your machine:
  that is exactly the kind of thing that must not end up in a committed file, and it is why a
  local checkout contributes its `origin` remote instead. Leave the section out and the update
  falls back to the canonical repo above, which is right far more often than it is wrong — but
  record it when you know it, and you do know it, because the person just told you.

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

**An update is one command, and it is not this file.** From the repo:

```bash
python .grillwork/engine/lib/grillwork update
```

That does the whole thing: it reads the `source` recorded in the settings, refuses unless the
git working tree is clean, downloads that source, replaces `.grillwork/engine/` wholesale,
re-realizes every command from the profile the install recorded, sweeps any `grillwork-*` file
the current version no longer has, and deletes everything it downloaded. It asks nothing,
because the answers are already in the repo. What it leaves behind is an uncommitted diff.

Read the JSON it prints and report it: `origin` says where it fetched from, `engine_changed`
lists the engine files that differed — empty means the repo was already current and nothing in
the engine changed — and `written` / `removed` list the realized commands rewritten and the
retired ones swept.

The command lives in the engine, so the version that runs is always the one being updated
*away from*. That is deliberate and safe: it copies the new engine into place before it does
anything clever, and the realization it performs is driven by the profile in the repo, not by
anything either version hard-codes.

### When the update says `realized: false`

The engine was replaced, but the commands were not, because the repo has no
`settings/realization.json` — it predates the profile, or its harness could not be described by
one. Finish by hand: realize the commands exactly as "Realize the commands" above describes,
reading from `.grillwork/engine/commands/`, which the update just placed. Then delete any
`grillwork-*` file you did not write — nothing else removes these, so a retired command
otherwise survives every future update, still offering itself to any agent that reads its
description. Say what you removed. Finally, write the profile as "Write down how you realized
them" describes, so the next update needs none of this.

### Doing it by hand

An update run by an agent from a checkout rather than by the command is the same four steps,
and they are worth naming because the command performs exactly these:

1. **Replace `.grillwork/engine/` wholesale**, directory-for-directory rather than
   file-by-file. A half-updated engine, one role new and another old, is the failure this
   prevents.
2. **Re-realize every command.** They carry a do-not-edit banner precisely so this overwrite
   is safe.
3. **Sweep the orphans** — every `grillwork-*` file you did not just write.
4. **Touch nothing else.** In particular, do not open `settings/config.json` to check it, and
   do not ask about anything in it.

**What an update must leave exactly as it found it**: `settings/config.json`,
`settings/realization.json`, the curated `settings/improvements.md`, and every spec under the
spec home with its findings and evidence. Those are the person's and the loops' — written by
the runtime, never by an install. If you find yourself about to ask which branch changes land
on, or what the test command is, you have taken the fresh-install branch by mistake.

**The one exception, for installs old enough to need it:** if the settings are a `config.yaml`
rather than a `config.json`, that is an install from a Grillwork that used YAML. Convert it —
carry every setting across unchanged, write `config.json`, delete the old file — and still ask
nothing. You are transcribing their existing answers into the format the helper now reads, not
collecting them again. Say that you converted it.

### Checking whether a repo is current

Because everything installed is committed and byte-identical to its source, **checking whether
a repo is current is a plain directory comparison** —
`diff -r engine/ <repo>/.grillwork/engine/ --exclude=__pycache__`, ignoring only the generated
bytecode, which was never installed in the first place. There is no version handshake and
nothing to interrogate; what is installed is what is in git. The `update` command runs exactly
that comparison against what it downloaded and prints it as `engine_changed`, so the check
needs no checkout on disk — and it normalizes line endings, because an archive ships LF where a
Windows checkout may hold CRLF and a byte comparison would call every file changed. **Leave
alone everything the person or the loops produced**: their specs and the findings beside them,
their `config.json`, and the curated `improvements.md` under `.grillwork/settings/`. Those are
theirs; the engine is not.

## Updating from a version that has no `/grillwork-upgrade`

An install old enough to have neither the `/grillwork-upgrade` command nor the `update`
subcommand cannot update itself, because both live in the engine it is trying to replace. The
way out is the way in: **point the agent at this file and say the repo already has Grillwork.**
It performs "Doing it by hand" above, and the install it leaves behind has the command, so this
is the last time anyone has to.

An install that predates the `source` setting but has the `update` subcommand is fine as it is:
with no source recorded, the fetch falls back to the canonical repository and says which one it
used. **Do not write the setting in on its behalf** — `config.json` is the person's, and an
update does not edit it.

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
