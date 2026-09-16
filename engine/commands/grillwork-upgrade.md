---
name: grillwork-upgrade
kind: command
description: "Update this repository's Grillwork to a newer engine, keeping every answer the original install already collected. Explicit invocation only — run it when a person asks to update Grillwork, never on your own judgment."
---

Update the Grillwork installed in this repository. Run one command:

```bash
python .grillwork/engine/lib/grillwork update
```

That is the whole update. It reads the source this repo records, refuses unless the git working
tree is clean, downloads that source, replaces `.grillwork/engine/` wholesale, rewrites every
realized `grillwork-*` command and subagent from the profile the install recorded, deletes any
that the current version no longer has, and removes everything it downloaded. Nothing it
fetched outlives it; what it leaves behind is an uncommitted diff.

It asks nothing, and neither should you. `settings/config.json`, the curated
`settings/improvements.md`, and every spec with its findings and evidence are the person's and
the loops' — an update never touches them. If you find yourself about to ask which branch
changes land on or what the test command is, something has gone wrong; stop and say so.

An optional source — a ref, or a repository URL:

{{ARGS}}

Nothing is required. If the person named one, pass it: `--ref <branch-tag-or-sha>` or
`--repo <url>`.

## Report what it did

The command prints JSON. Turn it into a sentence or two for the person:

- **`origin`** — where it fetched from. Say it. Someone who installed from a fork needs to see
  which source was reached for, and only they can tell you it is the wrong one.
- **`engine_changed`** — the engine files that differed. Empty means the engine was already
  current and this update changed nothing in it; say that plainly rather than implying work
  happened.
- **`written`** and **`removed`** — the realized command files rewritten, and the retired ones
  swept. Name the removals; a command disappearing from the person's harness is something they
  should hear about rather than discover.

Then tell them the diff is theirs to review and commit. Do not commit it for them, and do not
keep a copy of what was replaced — the clean tree the update insisted on is what makes git the
undo.

## If it reports `realized: false`

The engine was updated, but the command files were not, because this install has no
realization profile at `.grillwork/settings/realization.json` — it predates the profile, or was
made without one. Nothing is broken; the job is simply half done, and the other half is yours.

Realize the commands from `.grillwork/engine/commands/`, which the update just placed, exactly
as `INSTALL.md` describes: one file per source, `kind: command` and `kind: subagent` to their
separate homes in your harness, `{{ARGS}}` substituted, `kind:` dropped, descriptions carried
verbatim, the do-not-edit banner on top. Then delete any `grillwork-*` file you did not write.

Having done it, **write the profile down** so the next update does it mechanically. For a
harness whose commands are markdown with YAML frontmatter:

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

Fill it with what *your* harness uses, not what is written above. `keys` maps a source
frontmatter key to the name your harness spells it with — leave it empty when they match. The
profile is the adopter's own record, like `config.json`: an update reads it and never rewrites
it.
