# Nucleus-BTC map

Continue the existing exact Bitcoin project. Read `STATUS.md` first.

- Architecture and trust boundaries: `docs/ARCHITECTURE.md`.
- Research hypotheses and kill criteria: `docs/RESEARCH.md`.
- Exactness and measurement gates: `docs/VALIDATION.md`.
- Milestones and external blockers: `docs/ROADMAP.md`.
- Current execution checkpoint: `docs/exec-plans/active/nucleus-next.md`.
- Phase-II continuation and measured decision: `docs/exec-plans/active/phase-ii.md`
  and `docs/PHASE-II-RESULTS.md`; do not reopen exhausted branches unchanged.
- Completed checkpoints: `docs/exec-plans/completed/`.
- Latest target-directed research: `docs/MIDDLE-CUT-RESULTS.md` and
  `docs/exec-plans/active/middle-cut.md`. Original 20–30 TH/s target is unchanged;
  cube/affine middle-cut and target-rank hunts are evaluated negative evidence.

The independent oracle and Bitcoin serialization are authoritative. Generated
programs are untrusted until exact differential validation. Preserve historical
results; save new measurements under new names. Run affected tests before each
logical commit. Never force-push or log local pool credentials. Hosted CI tests
CPU/native paths; local hardware validation is separate. Research failures must
be bounded, recorded, and followed by a different viable experiment.
