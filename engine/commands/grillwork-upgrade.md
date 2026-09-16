---
name: grillwork-upgrade
kind: command
description: "Update this repository's Grillwork to a newer engine, keeping every answer the original install already collected. Explicit invocation only — run it when a person asks to update Grillwork, never on your own judgment."
---

Update the Grillwork installed in this repository, without re-asking anything the original
install already settled.

Where Grillwork's source is — a path to a checkout, or a URL to clone:

{{ARGS}}

**The update procedure is deliberately not written here.** Read `INSTALL.md` at that source and
follow its **update path** — the branch it takes when a repo already has an install.

That indirection is the point. `INSTALL.md` travels with the engine you are updating *to*, so it
is always the version that knows what its own update involves. A copy of the procedure kept in
this file would be the version you are updating *away from*, and would go stale in exactly the
situation it exists to handle.

If no source was named, ask for one. Do not guess at a path, and do not fetch from anywhere the
person did not name.

You can tell whether the update path was honored by what it does and does not do. The engine and
every realized command are replaced wholesale, and orphaned `grillwork-*` files from older
versions are swept. `settings/config.json`, `settings/improvements.md`, and every spec with its
findings and evidence are left exactly as they were. And **you are asked nothing** — not about
the integration target, the gate, hooks, or the spec home. Those answers already exist in the
repo. An update that starts asking them has taken the fresh-install branch by mistake; stop, say
so, and take the update path instead.
