# Target-directed continuation

The immutable target is 20–30 TH/s equivalent valid Bitcoin work on the stated
hardware, through lower total cost for exact SHA256d families. No smaller
performance milestone replaces it. Keep live testing local as requested.

Hypothesis: backward target constraints plus exact signed carries and the
second-SHA message schedule can reject whole families without independent full
hashing. UNKNOWN and SAT retain all work. Only independently verified UNSAT
may establish rejection, and verification costs count.

1. Reproduce the checkpoint and restore existing solver access if needed.
2. Test a nonenumerating known-bit boundary abstraction. Construct an inverse
   round witness when its state becomes unconstrained; record why it cannot prune.
3. Change the mechanism to a joint affine hull across cut state and first digest,
   retaining cross-word constraints omitted by the independent-word projection.
4. Compare signed-carry and direct bit-vector suffix encodings with exact message
   schedule relations, bounded solve time and rank budgets, fresh fixtures and
   exhaustive independent checks. Include all prefix/hull/proof/audit costs.
5. Measure joint-rank growth with K and total GPU-relative economics. Reject any
   branch whose useful constraints disappear or whose construction already costs
   more than saved hashing. Preserve the existing production champion.
6. Record the next distinct unresolved mechanism and commit verified evidence.

This experiment is bounded; repeated timeout increases and unchanged Phase-II
approaches are excluded. No finite experiment can guarantee the target exists.

## Evaluated checkpoint

Completed steps 1–5 and changed mechanisms twice after failure: solver-free
target-word parity elimination, then 168 nonce/version subspace configurations.
Results: 75 UNKNOWN/6 UNSAT bounded solver queries; six algebraic UNSAT proofs
at K=4/16; full target-word rank at K>=64; full joint rank at K=1024. Best new
complete pipeline 0.24457x GPU. No useful pruning or champion promotion.
98 local tests pass with the expected single optional HIP skip (97 passed).
See `docs/MIDDLE-CUT-RESULTS.md` and append-only raw evidence. The target remains
unachieved. The next nonlinear nonenumerating boundary relation is unresolved.

References: FIPS 180-4, https://csrc.nist.gov/pubs/fips/180-4/upd1/final;
specialized differential constraint motivation, https://eprint.iacr.org/2024/349.
The latter concerns reduced-step collisions and does not supply a mining attack.
