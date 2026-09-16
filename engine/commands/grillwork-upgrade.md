---
name: grillwork-upgrade
kind: command
description: "Update this repository's Grillwork to a newer engine, keeping every answer the original install already collected. Explicit invocation only — run it when a person asks to update Grillwork, never on your own judgment."
---

Update the Grillwork installed in this repository, without re-asking anything the original
install already settled.

An optional source — a ref to fetch, a repository URL, or a path to a local checkout:

{{ARGS}}

Nothing is required. The repository records where its Grillwork came from, so the ordinary case
is that this command was invoked bare.

## Fetch the source

```bash
python .grillwork/engine/lib/grillwork fetch-engine
```

Pass `--ref <branch-tag-or-sha>` or `--repo <url>` if the person named one above. It reads the
recorded source, refuses unless the git working tree is clean, downloads that source's archive,
and stages it in a temp directory outside the repo. Report the `origin` it used — an adopter
who installed from a fork needs to see which source was reached for, and only they can tell you
it is the wrong one.

If it prints `"current": true`, the installed engine is already byte-identical to the source.
**Say so and stop.** There is no update to perform, and performing one anyway produces a diff
of nothing for the person to review.

If the person named a local checkout rather than a URL, skip the fetch and use that checkout as
the staged source. Everything below is unchanged.

The output names two paths that matter: `source`, the Grillwork tree you copy from, and
`staged`, the temp directory holding it. **Delete `staged` when the update is finished** — the
fetch deliberately leaves it behind for you to copy from, so nothing else will.

## Follow the source's own update path

**The update procedure is deliberately not written here.** Read the `install_doc` the fetch
staged — `INSTALL.md` in the staged source — and follow its **update path**, the branch it
takes when a repo already has an install.

That indirection is the point. `INSTALL.md` travels with the engine you are updating *to*, so it
is always the version that knows what its own update involves. A copy of the procedure kept in
this file would be the version you are updating *away from*, and would go stale in exactly the
situation it exists to handle.

## What tells you it went right

The engine and every realized command are replaced wholesale, and orphaned `grillwork-*` files
from older versions are swept. `settings/config.json`, `settings/improvements.md`, and every
spec with its findings and evidence are left exactly as they were. And **you are asked
nothing** — not about the integration target, the gate, hooks, or the spec home. Those answers
already exist in the repo. An update that starts asking them has taken the fresh-install branch
by mistake; stop, say so, and take the update path instead.

The result is an uncommitted diff for the person to review. Do not commit it for them, and do
not keep a backup of what you replaced — the clean tree the fetch insisted on is what makes git
the undo.
