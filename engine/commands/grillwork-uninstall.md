---
name: grillwork-uninstall
kind: command
description: "Remove Grillwork from this repository — the engine and every realized command. Explicit invocation only, and destructive: run it when a person asks to remove Grillwork, never on your own judgment and never as a step inside something else."
---

Remove Grillwork from this repository.

**This is the definition of what removal is.** The install prompt's "Removing Grillwork"
section points here rather than restating it — removal needs no engine source to copy from, so
it belongs with the install that is being removed rather than with the one you would install.

Grillwork owns exactly two things, and removing it is deleting both:

1. **The engine** — `.grillwork/engine/`: the copied method and its vendored helper.
2. **The realized commands** — every `grillwork-*` command and subagent file, in whichever
   directories your harness reads them from. The prefix is reserved, so *everything* under it
   is Grillwork's, including files left over from an older version that the current one no
   longer writes.

Everything else under `.grillwork/` was produced by the person or by the loops, and is
**theirs, not Grillwork's**: `settings/config.json`, the curated `settings/improvements.md`, and
every spec under the spec home with its findings and evidence beside it. Deleting those throws
away the record of work that actually happened, and "remove Grillwork" does not imply it.

So **ask, once, before touching any of it**, with both outcomes named plainly:

- **Keep the record** — delete the engine and the commands; leave `.grillwork/settings/` and the
  specs where they are. They stay readable as ordinary markdown, and nothing runs against them.
  Recommend this one: it is the reversible half of the choice.
- **Remove everything** — delete `.grillwork/` entirely as well.

Before they answer, say whether the repo is under git, and if it is, that the content is
recoverable either way (`git log -- .grillwork`). A choice made while unsure what is lost is not
the choice they meant to make.

Never decide on their behalf, and never delete instance data because it looked orphaned.

Finally, report exactly what you deleted and what you left standing. The deletions are a change
like any other: say so, and leave committing them to the person.
