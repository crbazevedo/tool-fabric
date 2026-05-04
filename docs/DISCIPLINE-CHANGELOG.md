# Discipline Changelog

Audit trail for changes to **discipline primitives** in `tool-fabric` —
the gates, scripts, and Makefile targets that enforce methodology rules
on every PR. Pairs with `RELEASE-NOTES.md` (which tracks features) and
`docs/VISION.md` (which tracks strategy).

This file is the audit trail for the discipline itself. Every change
to a primitive must add an entry here in the same PR — that pairing
will be enforced by CI as soon as a `discipline-change-check` lands
(planned for W3).

## Entry format

```
## YYYY-MM-DD — PR #N — &lt;one-line summary&gt;
- **Change:** &lt;what the primitive now does that it didn't before&gt;
- **Why:** &lt;the empirical pattern or operator decision motivating the change&gt;
- **Operator:** &lt;who authorised it&gt;
```

---

## 2026-05-04 — PR #TBD — chore: dfg-harness instrumented; v0.3.0 plan seeded

- **Change:** Adds `.dfg/` skeleton + `.claude/settings.json` (11 hooks)
  via `dfg-harness instrument --v2`. Authors `docs/VISION.md` (discovery
  output), `.dfg/plan.yaml` (10-wave / 7-phase decomposition for v0.3.0),
  `docs/RELEASE-NOTES.md` and this file.
- **Why:** First external repo to be governed end-to-end by dfg-harness.
  Operator directive 2026-05-04: "I need a demo where we instrument
  dfg-harness in that repo. Understand it. Understand where it is going
  / vision / next steps. Propose / refine (2-turns) with Operator.
  Approves the plan. And then we plan the phases, sprints, waves. Offer
  to spawn it. Complete first wave flawlessly."
- **Operator:** Carlos Azevedo (turn-1 + turn-2 approval, 2026-05-04).

---
