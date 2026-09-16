# Worked example — publish a spec's evidence

This is an **adopter harness**, not part of the engine, and a companion to
[`../github-projects/`](../github-projects/README.md): that one shows a *detached* hook, this
one shows the **awaited** one. It is here to be read and copied. It is never written into your
repo by the install prompt.

`publish-evidence` fires when a spec turns `verified` — before the human acceptance — and only
when the evidence disposition's `push` boolean is true. Its job is to put the artifact bytes
somewhere that outlives the repo, so that Grillwork may later prune them from it.

This example "publishes" by copying the artifacts into a directory on the same machine and
printing `file://` URLs. That is deliberately trivial: what is worth copying is everything
*around* the upload, because `publish-evidence` is the only event with a protocol.

## Why this event is different

| | every other event | `publish-evidence` |
|---|---|---|
| the engine | spawns it detached and never waits | **awaits** it |
| the exit code | ignored | **is** the success — 0, and nothing else |
| stdout | ignored | **parsed**: `<artifact-name> <url>` per line |
| a failure | the hook's own business | never blocks `verified` or acceptance; blocks only the prune of artifact bytes |

At most **one** command may be bound. Multiple destinations are one wrapper script you write —
one exit code, one stdout parse, one success record.

On exit 0 the engine records each URL beside its artifact's hash in the spec's
`evidence/manifest.json`, with a success timestamp. That record is what later permits
`grillwork prune-evidence` to delete the bytes. So an over-eager exit 0 is the genuinely
dangerous failure mode here: it can authorize deleting evidence that was never published.

## The five things it gets right

1. **`GRILLWORK_DRY_RUN=1` is answered first, and always succeeds.** `grillwork fire-hooks
   publish-evidence` sets it to prove the wiring, with a payload that is invented down to a
   spec path that does not exist. So the flag is checked before anything needs the files: the
   script reports what it can see on stderr, publishes nothing, claims no URL, and exits 0.
   Check it later — after "is there a spec?", after reading the bundle — and the rehearsal
   fails on its own invented input, silently, because the engine spawns it detached and never
   reads the exit code. That is worse than no rehearsal: it trains an adopter to expect a red
   one.
2. **Stdout is pure protocol.** Only `<artifact-name> <url>` lines. Progress, counts, and
   errors go to stderr. A line that is not a pair is dropped with a warning by the engine, so
   a chatty uploader wrapped without silencing it produces noise in the log and no URLs where
   you expected them.
3. **The engine says which files are artifacts.** `grillwork evidence-artifacts <spec>` prints
   the bundle directory and the files in it that are artifact bytes rather than the textual
   account (`bundle.md`, `manifest.json`, `.gitignore`). Restating that rule is how a publisher
   ends up uploading the engine's own bookkeeping — including the very `manifest.json` your
   URLs are about to be written into.
4. **The repo root comes from the spec path.** The hook fires from wherever the `verified`
   flip ran, which is the build's worktree — not your repo root, and not a stable working
   directory. Walk up from `GRILLWORK_SPEC_PATH` to the directory holding `.grillwork/`.
5. **Failure is honest.** Any error exits nonzero, so no success is recorded and the bytes
   stay. A failed publish costs a retry at close; a falsely successful one costs the evidence.

One more, learned the hard way: **stage before handing artifacts to a third-party uploader.**
Some uploaders write their own bookkeeping — a `manifest.json` of their own, a checksum file —
into the directory you point them at, which would overwrite the bundle's account files. Copy
out first; never point another tool at `evidence/` itself.

## Wiring it

**`<publisher>` below is yours to substitute** — the directory you copied this one to, written
relative to your repo root (`tools/publish-evidence`, say). Nothing else in the wiring changes,
and nothing here cares where you put it: `publish.py` walks up from the spec path it is handed
to find your repo, and everything it runs is repo-relative from there.

1. **Prerequisites:** none. This example is standard library only. It runs the vendored
   Grillwork helper — `python .grillwork/engine/lib/grillwork evidence-artifacts <spec>` — to
   ask which files are artifacts, which needs nothing installed either: the helper is committed
   with your repo and runs in place.

2. **Choose a destination.** `GRILLWORK_PUBLISH_DIR` names it; without one this example writes
   to `<repo>/.grillwork/published/<spec-dir>/`, which you should add to your `.gitignore` —
   evidence published back into the repo it is being pruned from helps nobody. A real
   publisher points at an object store or artifact server.

3. **Turn the disposition on** in `.grillwork/settings/config.json`, so the event fires at
   all. `push: true` is what makes the event fire; `commit: false` is what makes publishing
   worth doing, since it is the artifact bytes staying out of git that the prune later
   removes:

   ```json
   {
     "evidence": {
       "commit": false,
       "push": true
     }
   }
   ```

4. **Bind it** in the same file — at most one command:

   ```json
   {
     "hooks": {
       "publish-evidence": [["python", "<publisher>/publish.py"]]
     }
   }
   ```

5. **Prove the wiring** without publishing:

   ```
   python .grillwork/engine/lib/grillwork fire-hooks publish-evidence
   ```

   The engine spawns the bound command with a synthetic payload carrying
   `GRILLWORK_DRY_RUN=1`, and reports whether it spawned — that is all it can report, since it
   spawns the command detached. To see what your publisher *says*, run it yourself with the
   same shape of payload and a real spec:

   ```
   GRILLWORK_EVENT=publish-evidence GRILLWORK_DRY_RUN=1 \
     GRILLWORK_SPEC_PATH=$PWD/.grillwork/specs/<spec>/spec.md \
     python <publisher>/publish.py
   ```

   Either way it exits 0 and publishes nothing.

   Note what the rehearsal cannot tell you: it reports the **spawn**, and `python` spawns
   whatever path you hand it, so a `<publisher>` left unsubstituted still reads as `spawned`.
   Being the awaited event, that one is caught in the end regardless — the first real
   `verified` flip warns that the command exited nonzero and records no publish success. It
   costs nothing but the prune: the flip stands, and the bytes stay until a publish works.

## The files

| File | What it is |
|---|---|
| `publish.py` | the whole harness: selection, dry run, publish, the stdout protocol |
| `tests/` | its tests — they drive the real script against fixture bundles and assert on its stdout, stderr and exit code |

The tests come with the directory because you own it once you copy it, and they are meant to
run where you put it: `pytest` in this directory, at whatever depth, needing nothing but
pytest and the Grillwork install they sit inside. They find that install the way the script
does — the walk up to `.grillwork/` — and vendor its helper into each fixture repo, so the
`evidence-artifacts` call is a real subprocess rather than a stub.
