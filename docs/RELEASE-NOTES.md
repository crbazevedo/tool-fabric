# Release notes

## v0.3.0 — TBD (in development)

**Theme:** linter completeness, schema v2, benchmark expansion, first
external adoption surface.

This release is the first one **governed by dfg-harness** end-to-end.
The harness was instrumented on 2026-05-04 (chore PR — bootstrap). See
`docs/VISION.md` for the strategy underpinning the v0.3 plan and
`.dfg/plan.yaml` for the wave decomposition.

Highlights to come (see plan; each wave updates this section as it
closes):

- **W1** — Substrate seed + deliberately-small first unit
  (`fabric-lint --version` flag).
- **W2–W3** — Linter completeness; full 16-rule coverage with
  cross-rule consistency tests.
- **W4** — Schema v2 (nested concepts, `since`, `deprecated_by`).
- **W5–W6** — Benchmark expansion (500-tool scale, long-tail compositional).
- **W7–W8** — Adoption surface (GitHub Action, first external registry
  imports `.tool-fabric.yaml`).
- **W9** — Quickstart &lt; 5 min; troubleshooting guide; man pages.
- **W10** — Release ceremony (tag + program-close retro).

## v0.2.0 — 2026-04-13

Multi-model scale benchmark (Haiku 4.5 / Sonnet 4.6 / Opus 4.6 ×
OLD/NEW × 41/150 tools). Governance lift +14pp / +14pp@hit3 / +10pp
across models. Cost-efficiency receipt: Haiku + governance ≈ Opus
ungoverned at 1/15× cost.

## v0.1.0 — 2026-04-13

Initial scaffold — formal SPEC.md, JSON Schema, 12 linter checks
(E001-E005, W001-W004, I001-I003), CLI (check / report / init),
CARLOS-OS example registry, three-tier benchmark protocol.
