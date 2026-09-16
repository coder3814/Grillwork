---
name: grillwork-approve
kind: command
description: "Present a Ready spec for human approval; on approval, mark it approved. Explicit invocation only, and rarely needed directly — /grillwork-specify ends at this touchpoint; invoke it standalone only to approve a spec left ready in an earlier session."
---

The Grillwork **spec-approval touchpoint** — the first of the two human touchpoints,
authorizing work that has not happened yet.

The spec:

{{ARGS}}

**You do not normally need this.** `/grillwork-specify` ends at this touchpoint already. This
command is for approving a spec that an earlier session left at `ready`.

Carry out the touchpoint exactly as **step 11 of `.grillwork/engine/roles/griller.md`** defines
it — that step is the definition, and this command only re-enters it. In short: confirm the
spec is `ready` (`python .grillwork/engine/lib/grillwork spec-status <spec>`), present the human-facing slices for a real read
rather than a rubber stamp, and on the person's explicit **yes** set `approved` and stop, because
approving is not starting. On a **no**, record what they want changed as `[GAP]` markers and
return the spec to `drafting`. Never approve on the person's behalf.
