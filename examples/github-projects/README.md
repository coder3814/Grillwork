# Worked example — sync a GitHub Projects board

This is an **adopter harness**, not part of the engine. It is here to be read and copied:
Grillwork's boundary is the repo's edge, and everything on the far side of it — what a change
looks like on your board, in your chat, on your wall display — is yours to build. This one was
the engine's own built-in GitHub tracker until spec 010 moved it out here unchanged in
substance, so it is a real harness rather than a sketch.

It is never written into your repo by the install prompt. Copy it, wire it, own it.

## What it does

On `on-spec-created` and `on-transition`, it projects the spec the doorbell names onto a
GitHub Projects v2 board:

- one Issue per spec in your issues repo, correlated by a hidden marker in the body (so a
  repeat fire updates it in place — no duplicates);
- the issue body is the full acceptance package (summary, what was done, the evidence table
  with SHA-pinned links, the verdict, findings, amendments) rendered from Grillwork's neutral
  model, printed by `grillwork package <spec>` — the model is the engine's, the markdown is
  the harness's;
- the item's chosen single-select field set to the column **your settings map** that lifecycle
  stage to (your columns can be named anything);
- the issue open through `drafting` → `accepted`, closed at `closed`, reopened if it leaves.

Authentication is the `gh` CLI's — this harness stores no credentials.

## Wiring it

**`<harness>` below is yours to substitute** — the directory you copied this one to, written
relative to your repo root. Both shapes are ordinary: keep the directory's own name
(`tools/grillwork-harness/github-projects`) or copy its contents somewhere flatter
(`tools/grillwork-harness`). Nothing in the harness knows or cares which. `hook.py` finds your
repo root by walking up from itself to the directory holding `.grillwork/`, and asks the
vendored engine for what it needs from there — so copy the files as a unit and it works at any
depth, under any name.

1. **Prerequisites:** the [`gh` CLI](https://cli.github.com) installed and `gh auth login`
   done, plus a GitHub Projects v2 board with a single-select field for your columns. If you
   bind the board with a **`settings.yaml` file** (step 2), you also need
   [PyYAML](https://pypi.org/project/PyYAML/) — `pip install pyyaml`. That is the harness's
   dependency, not the engine's: Grillwork's own helper under `.grillwork/engine/lib/` runs on
   the standard library alone, and so does this harness when the board is bound by environment
   variables instead.

2. **Settings — the harness's own, never Grillwork's config.** Copy
   `settings.example.yaml` to `settings.yaml` and fill it in. Nothing about this board goes
   into `.grillwork/settings/config.json`: the engine names no tracker. Every key is also
   settable as `GRILLWORK_GH_*` in the environment (`GRILLWORK_GH_PROJECT_NUMBER`, …), so CI
   can bind a board with no file, and `GRILLWORK_GH_SETTINGS` points at a settings file kept
   elsewhere.

3. **See your board's real field and option names, and check the map** — run this from your
   repo root:

   ```
   python <harness>/hook.py --check
   ```

   It lists every single-select field with its options, then verifies your `status_field` and
   every option your `status_map` targets is actually there.

4. **Bind it** in `.grillwork/settings/config.json` — each event takes a list of commands,
   each an argv list (no shell, so Windows and POSIX behave identically). Add the `hooks`
   key to the object already there:

   ```json
   {
     "hooks": {
       "on-spec-created": [["python", "<harness>/hook.py"]],
       "on-transition": [["python", "<harness>/hook.py"]]
     }
   }
   ```

   Kept under its own name at `tools/grillwork-harness/`, that reads
   `"tools/grillwork-harness/github-projects/hook.py"`.

5. **Prove the wiring** without touching the board:

   ```
   python .grillwork/engine/lib/grillwork fire-hooks on-transition
   ```

   The engine spawns each bound hook with a synthetic payload carrying `GRILLWORK_DRY_RUN=1`;
   this hook reports what it *would* sync and exits 0.

   What it proves is the **spawn**, and `python` spawns whatever path you hand it: a
   `<harness>` you forgot to substitute is reported as `spawned` just the same, then dies
   immediately with its output discarded. Nothing later will tell you either — a detached
   hook's failures are its own by contract. **Step 3 is what proves the path**, so run
   `--check` with the exact string you are about to put in the binding.

## How it reads the doorbell

The engine's payload is environment variables, and nothing more — a doorbell. `hook.py` reads
`GRILLWORK_EVENT` and `GRILLWORK_SPEC_PATH`, then reads the spec **file** for everything it
projects (id, title, status, summary, evidence). That is deliberate, and the contract asks for
it: hooks are spawned detached, so they can run late, out of order, or concurrently, and only
the files are authoritative. The repo root is derived by walking up from the spec path to the
directory holding `.grillwork/` rather than assuming where the trigger ran — a mid-build
transition fires from the build's worktree.

Failures are the harness's own: the engine never waits on a detached hook and never changes
its own exit code for one. `hook.py` prints to stderr and exits nonzero, and that is the end
of it — the spec change stands.

## How it reaches the engine

Some of what this harness projects is a fact about the *engine* rather than about your board:
the acceptance package's contents, and the lifecycle's list of stages. It asks for both —
`grillwork_cli.py` runs `python .grillwork/engine/lib/grillwork <command>` and parses the JSON
— rather than restating them or importing the vendored package.

That is worth copying even if you never touch a GitHub board. An import works only from Python
and only where the import path happens to be right; a harness written in PowerShell or Node
could not use one at all, and this example's own first external install broke on exactly that.
The engine names no vendor, tracker, cloud or repo layout, and printing its facts is what keeps
the same true of the language you write your harness in.

What it asks for:

| Command | What the harness does with it |
|---|---|
| `package <spec>` | the neutral acceptance-package model — `compose.py` renders it into the issue body |
| `statuses` | the lifecycle in order, to check your `status_map` covers every stage |

The one thing that cannot be asked for is where the engine *is*: `hook.py` walks up from the
spec path to the directory holding `.grillwork/`, because finding the engine is what the walk
is for.

## The files

| File | What it is |
|---|---|
| `hook.py` | the entry script the engine spawns; also `--check` |
| `grillwork_cli.py` | the engine seam: the walk that finds the install, and the calls that run its vendored helper and parse the JSON |
| `settings.py` | the harness's settings loader (file + `GRILLWORK_GH_*` env) |
| `settings.example.yaml` | the settings template to copy |
| `github_projects.py` | the adapter: read one spec, find-or-create its issue, place its card. Its single door to GitHub is `board_client()` |
| `compose.py` | renders the engine's neutral model (as printed by `grillwork package`) into a GitHub-flavored issue body |
| `tests/` | the harness's own tests. They substitute an in-memory fake board at `board_client()`, so nothing here touches the network |

The tests come with the directory because you own it once you copy it, and they are meant to
run where you put it: `pytest` in this directory, at whatever depth, needing nothing but
pytest and the Grillwork install they sit inside. They find that install the way the harness
does — the walk up to `.grillwork/` — and ask its helper for the engine content the fixtures
need. Nothing here imports the vendored `grillwork` package: an import resolves only where
some import path was arranged for it, which in a copy is nowhere.
