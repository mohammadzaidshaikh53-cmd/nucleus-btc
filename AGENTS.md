# Nucleus-BTC map

Continue the existing exact Bitcoin project. Read `STATUS.md` first.

- Architecture and trust boundaries: `docs/ARCHITECTURE.md`.
- Research hypotheses and kill criteria: `docs/RESEARCH.md`.
- Exactness and measurement gates: `docs/VALIDATION.md`.
- Milestones and external blockers: `docs/ROADMAP.md`.
- Current execution checkpoint: `docs/exec-plans/active/nucleus-next.md`.
- Completed checkpoints: `docs/exec-plans/completed/`.

The independent oracle and Bitcoin serialization are authoritative. Generated
programs are untrusted until exact differential validation. Preserve historical
results; save new measurements under new names. Run affected tests before each
logical commit. Never force-push or log local pool credentials. Hosted CI tests
CPU/native paths; local hardware validation is separate. Research failures must
be bounded, recorded, and followed by a different viable experiment.
