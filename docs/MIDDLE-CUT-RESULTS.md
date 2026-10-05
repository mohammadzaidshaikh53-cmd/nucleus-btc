# Target-directed middle-cut continuation

The objective remains **20–30 TH/s equivalent exact valid Bitcoin work on the
stated hardware**. No smaller milestone replaces it. This checkpoint does not
achieve the target and does not promote a new production kernel. The last
measured champion remains 1.567 GH/s; power remains null. Testing stays local.

## Mechanism and exactness

The hypothesis was that a compact boundary between forward SHA computation and
backward target constraints could eliminate a whole family cheaply. The new
laboratory keeps all second-SHA schedule recurrences and models modular sums
using bounded signed carry differences:

`sum(x)-sum(base) = (result-base_result) + 2^32*(carry-base_carry)`.

For up to five uint32 operands, 35-bit widened arithmetic plus a carry bound
0..(operand_count-1) makes this equivalent to exact modular addition. Universal
Z3 checks cover the two- and five-operand forms with nonzero reference carries.
Full boundary/schedule traces are checked against hashlib SHA256d. The independent
project oracle is unchanged.

At the cut after second-SHA round index 60, final digest word H7 is
`IV7 + e60 mod 2^32`. For a target whose most significant word is zero, any valid
candidate requires `e60 = -IV7 mod 2^32`. This necessary condition respects
Bitcoin's little-endian digest comparison. It is not the complete target check.

Neither SAT nor UNKNOWN discards a candidate. All code is a research laboratory,
with no automatic production pruning. Reported UNSAT family rejections receive
independent exhaustive hashlib reproduction; its cost is included.

## Results and changes of direction

1. **Nonenumerating independent known-bit cubes.** The abstract interpreter
   builds a bound for 2^8, 2^16 and 2^24 nonce families using only width+1 header
   constructions. Across three fresh fixtures, the first hash's tail-compression
   state loses all known bits by round index 8, 7 and 7 respectively. The second
   SHA state loses them by round index 3. All 45 tested cuts admit a constructive
   inverse-round witness with an exact, validly padded second-SHA schedule.
   These are witnesses in the relaxed state space, not Bitcoin solutions.
   The abstraction cannot reject these families.

2. **Joint state/digest affine hull with exact signed-carry suffix constraints.**
   This retains correlations across all eight cut words and eight first-digest
   words. Across three fixtures and cuts 31, 47, 55, 59 and 60, joint ranks for
   K=4,16,64,256,1024 are 3,15,63,255,512. At K=1024 the affine hull is the entire
   512-bit space: no affine boundary constraint remains. Of 81 bounded queries,
   75 return UNKNOWN and six UNSAT. All six rejections use the direct bit-vector
   encoding at cut 60, with K=4 or 16. No signed-carry query proves rejection
   within the configured resource budget. The best complete lab pipeline is
   0.02623x the same-family GPU baseline; useful rho=0.

3. **Solver-free target-word elimination.** Instead of repeating timed-out
   queries, Gaussian elimination directly tests whether the necessary e60 value
   belongs to the projected affine hull. UNSAT returns a parity separator checked
   independently against the original boundary values. SAT returns a verified
   affine witness, which need not be a real header. Six tiny families are rejected;
   all nine K>=64 families have full 32-bit target-word rank and remain feasible.
   The best complete pipeline is 0.24457x the GPU baseline, with F=4.0888 and
   useful rho=0. Faster proof generation did not remove candidate construction.

4. **Target-directed subspace alignment hunt.** A further changed mechanism
   searches 56 six-variable configurations per fixture: 48 adjacent, interleaved
   or seeded nonce subsets and eight nonce/version combinations. Three new
   fixtures give 168 families and 10,752 independently audited candidate target
   words. Every projection has rank 32; no useful affine target invariant is
   found. Hunt cost is 2.498 seconds, certified savings zero. Version variations
   use the SV2 mask only as a local diagnostic constraint; no live job permission
   or pool acceptance is asserted.

Decision: **NO LARGE ADVANTAGE FOUND.** These results eliminate the tested
independent-bit and affine boundary mechanisms, not every possible nonlinear
representation or cryptanalytic approach.

## Cost scope and limits

The solver comparison shares fixture preparation through cut 60 among all cut
probes; its pipeline timings include that full preparation, and are explicitly
not separate optimized per-cut timings. Its six successful proofs are all at
cut 60, where that preparation is required. The later algebraic pipeline also
uses cut 60, so its measured construction/proof/audit/fallback cost is complete.
Independent correctness audits are reported separately; independently reproducing
a pruning certificate is included in the candidate pipeline.

GPU baselines scan the identical finite contiguous nonce families, include host
and launch cost, and use five warmed samples. Tiny-family ratios are diagnostic,
not sustained hashing rates or confidence-qualified production promotions.
Python prototype overhead matters, but the full-rank loss of the necessary
affine relation is not a timing artifact. No energy estimate, payout, new share,
asymptotic speedup or impossibility proof is inferred.

Constructing the cut currently evaluates 125 of the 128 remaining SHA rounds
for each candidate after standard midstate reuse. A target-scale method needs
to avoid that independent per-candidate work, not merely accelerate the final
projection check.

## Next unresolved mechanism

The next necessary research direction is a **nonlinear relation across boundary
words that can be constructed without enumerating the family**. It must survive
the randomization observed here, include message-schedule and carry correlations,
and supply a cheaper independently checkable target-rejection proof. No concrete
relation meeting those requirements has been discovered in this checkpoint.

Do not rerun these affine/cube branches unchanged, increase generic solver
timeouts, or call an arbitrary boundary witness a real SHA preimage. A new
branch needs an explicit algebraic identity, construction algorithm and cost
prediction before implementation. The permanent target remains open.

## Evidence and reproduction

- `results/middle-cut-frontier-01.json`: cubes, signed/direct suffix queries,
  ranks, source hashes and full timing samples.
- `results/middle-cut-algebraic-01.json`: changed solver-free mechanism and costs.
- `results/middle-cut-target-rank-hunt-01.json`: changed family alignment search.
- `results/source-snapshots/middle-cut-01/`: exact pre-algebraic sources, matching
  the first experiment's recorded SHA256 values.
- `results/middle-cut-start-tests-01.json`: initial optional-solver access failure;
  no evidence was overwritten. After restoring sandbox access, startup retry
  passed 89 of 90 tests with the expected optional HIP skip.
- `results/middle-cut-release-tests-01.json`: 98 tests, 97 passed, optional HIP
  skipped; native, OpenCL and authenticated local SV2 were required.

```text
python scripts/middle_cut.py --output results/middle-cut-NEW.json
python scripts/middle_cut.py --algebra-only --output results/algebraic-NEW.json
python scripts/target_rank_hunt.py --output results/target-rank-NEW.json
python scripts/test_runner.py --require-native --require-gpu --require-sv2 --output results/tests-NEW.json
```

The signed suffix laboratory uses the existing optional Z3 dependency. Algebraic
elimination and the rank hunt need no external solver. Every result path refuses
to overwrite historical evidence.

Authoritative design references: [FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)
and [New Records in Collision Attacks on SHA-2](https://eprint.iacr.org/2024/349).
The latter motivates specialized constraints; its reduced-step collision results
do not establish a full Bitcoin SHA256d mining shortcut.
