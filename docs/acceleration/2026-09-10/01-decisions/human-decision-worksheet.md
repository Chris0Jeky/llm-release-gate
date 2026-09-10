# Human decision worksheet

The interactive deck is the authoritative way to record these. This page is a compact review surface.

| ID | Decision | Review recommendation | Required action |
|---|---|---|---|
| D02 | Align main, package identity and releases | Cut v0.1.3 | Confirm/change |
| D03 | Choose the floating-tag and licence transition | No default | Must choose |
| D06 | Choose the durable product identity | Evidence policy gate | Confirm/change |
| D07 | Create the first real consumer | Dogfood a real repo | Confirm/change |
| D08 | Interpret the trigger-driven growth rule | Dogfood counts once | Confirm/change |
| D09 | Choose the execution/adoption bridge | Snapshot/import protocol | Confirm/change |
| D13 | Set report disclosure and size policy | Disclosure profiles | Confirm/change |
| D15 | Choose the primary distribution path | Action first | Confirm/change |
| D18 | Keep or relax the no-service boundary | Artifacts only | Confirm/change |

## Hard stop

`D03` is intentionally not preselected. An agent must not move the floating `v0` tag, announce a licence transition, revert the licence or construct a dual-licensing scheme until the owner records that choice.

## Confirmation semantics

A recommended human option shown by the deck is a proposal, not approval. The exported JSON carries `confirmed: false` until the owner checks the confirmation control. The unbundler marks any dependent task blocked when the decision is unconfirmed.
