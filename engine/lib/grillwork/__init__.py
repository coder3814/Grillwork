"""Grillwork — an overlay engine for spec-driven autonomous agent loops.

There is deliberately no version number here. This package is *vendored* — copied into an
adopter's repository and committed — so "which Grillwork is in this repo?" is answered by the
files themselves: `git log -- .grillwork/engine` for when, and a plain `diff -r` against the
engine repo for whether it is current. A literal kept beside them could only ever agree with
them or lie, and the one that used to live here never moved across five contract versions.

What *is* versioned is the boundary an adopter's own code is written against — the events, the
payload, and the read surface in `hooks-contract.md`, under a single integer that bumps when
either the engine's behavior at that boundary or the code managing it moves significantly.
That number means something because something depends on it.
"""
