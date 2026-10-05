# Phase II measured decision — 5 October 2026

**NO LARGE ADVANTAGE FOUND.** Outcome B: no new family advantage over the
verified ordinary GPU. Exactness and meaningful negative evidence are achieved;
sublinear Bitcoin mining, cheap pruning, energy savings and BTC payout are not.

| Required metric | Measured result and scope |
| --- | --- |
| Current champion | OpenCL, full unroll, alternate Boolean identities, local size 64, gfx1102 |
| Current HPS | Fresh Phase-II size-64 median **1.567 GH/s**; earlier 1.634 GH/s preserved |
| Current power | null; no trustworthy measured whole-system power |
| Current alpha | Algorithmic alpha = 1 for ordinary independent hashing with standard midstate reuse |
| Best family alpha | **0.98** descriptive nonnegative fixed-overhead fit; no algorithmic sublinearity demonstrated |
| Best beta_carry | **0.06271**, 16-bit transfer signatures at remaining round 95; output-residue beta = 1 |
| Best Rc | Economic collapse before round 0 in the prefix fixture: construction exceeds the warmed GPU scan. Global optimum unmeasured |
| Best rho | Exact prefix rho = 1 on target-1 fixtures; **economically useful rho = 0** |
| Best Q | Useful pruning Q = 0; exact all-rejected finite-family Q is undefined/null under the existing contract |
| Best F | **1020.44**, prefix proof time / warmed GPU scan time, K=256 |
| Best exact speedup | Phase-II full-family evaluator / GPU: **0.001394x** maximum across measured sizes; production remains faster |
| Live share accepted? | No; config/local.json absent, continued local testing |
| BTC payout proven? | No; balance/payout unmeasured |

## Exact family mechanisms and limits

FamilyIR is separate from scalar IR. Its dimensions identify nonce, permitted
version bits, bounded nTime and extranonce-derived coinbase/Merkle changes.
Arbitrary Merkle-tail changes are diagnostic and cannot claim SV2 permission.
Conceptual 56-bit standard workspaces are represented without materializing
them; finite materialization is bounded and duplicate aliases raise an error.
Merkle-path siblings are invariant; derived roots use a bounded outer cache.

FamilyWord splits an exact finite word into a constant, GF(2) affine basis,
nonlinear XOR residual and carry information. Exhaustive materialization and
full three-compression SHA256d parity pass. Programs mutate/crossover
representations and transition rounds, insert/delete stages, and split an
interior assignment variable at a round boundary. Strided fallback covers
all mapped candidates without gaps or duplicates. Native stages currently use
ordinary uint32 operations in the research interpreter; finite lookup DAG and
bit-plane cone conversions are exact but have substantial materialization cost.
This is not an optimized GPU lowering of FamilyIR.

The profiler reports exact per-bit variable support, ANF degree and term counts,
carry influence, schedule uniqueness, state uniqueness, entropy proxies and
binary affine rank. These are exhaustive finite-family diagnostics, not lower
bounds on all SHA algorithms. For K=64, states become distinct at nonce
injection and affine rank reaches 63 by round 7. At round 15, nonlinear XOR
residuals have 12/58/248 unique values for K=16/64/256, and degree 4/6/8.
The affine basis forces residual zero at the base and one-bit assignments;
these forced zeros must not be mistaken for useful compression.

## Full-family scaling and carry frontier

K=256/1024/4096/16384, three fresh fixtures each, and all 4/8/16-bit blocked
carry forms were evaluated through full SHA256d. Every digest was compared
with hashlib. Construction, midstate, computation, transitions and audit are
recorded separately; total-cost speedups include the independent audit.
GPU/native baselines scan the same nonce set.

| Carry block | Fixed-overhead alpha fit | K=16384 representation seconds | Same warmed GPU scan seconds |
| --- | --- | --- | --- |
| 4 bits | 1.01 | 80.55 | 0.000244 |
| 8 bits | 0.98 | 47.58 | 0.000244 |
| 16 bits | 1.20 | 57.14 | 0.000244 |

Raw `Uresidual` in the scaling artifact counts unique **modular output
residues**, not the separately profiled GF(2) XOR residual. At round 15,
16-bit Ucarry grows only 9→14 while unique output residues grow 256→16384.
Small transfer-function pools leave candidate-specific sum construction,
lookup/indexing, composition and nonlinear output work. Alpha fits include
Python overhead and some concurrent CPU diagnostic load; they do not qualify
as an INTERESTING sublinear result. Logical word size is an estimate, not RSS.

## Distinct follow-ups

- Influence-guided splitting chose nonce bit 11 at round 4. Split execution
  cost 0.264 s versus 0.238 s before the 1.485 s pilot/total cost. Coverage
  passed; economics failed.
- Conditional GF(2) models grouped by carry signatures compressed one early
  T1 word to 10.2% of explicit storage at round 3. By round 4 the optimistic
  descriptor cost 157%, and later rounds cost 244–344%. The causal follow-up
  is DEAD; signature dictionary cost would worsen the comparison.
- Five executable representation genomes pass downstream full-hash parity.
  Transitions/materialization do not beat production hashing.
- Bounded local equality saturation covers Ch, Maj, Sigma1 and blocked T1
  additions, with scalar/wave32/family/carry/register cost proxies. Extraction
  is tested through full hashes; local cone timing is not a GPU victory.
- Nonce, nonce/version and nonce/nTime differential hunts have no surviving
  full-state reuse and negative hunt amortization. Reduced-round low activity
  is never a share predictor or pruning certificate.
- Early lossy MITM projections are universal after relaxing omitted bits and
  carries. UNKNOWN retains all work. An exact final-H7 backward cone can be
  UNSAT, independently reproduced over its finite cut values.
- Z3 5.1.0 verified a bounded carry cone with 12,288 independent integer checks.
  CaDiCaL, Kissat and CryptoMiniSat binaries were unavailable. These local
  certificates do not prove a full-SHA shortcut.
- Exact final-word comparison rejects after second-compression round 60,
  skipping three rounds and seven net feedforward additions per candidate.
  It rejects all K=256 target-1 fixture candidates, but F≈1020 versus the GPU.
  Equal/less prefixes retain work. Earlier raw prefix artifacts incorrectly
  named rho/F as Q; a separate correction preserves their original timings,
  restores Q=-log10(1-rho), and labels rho/F separately.
- Version/nonce hierarchy verifies four midstates sharing 256 second-block
  schedules: known midstate/message-schedule reuse, an ASICBoost-class baseline
  principle, not a new attack.

## Hardware, protocol and recovery

Local release: 90 tests, 89 passed and one optional HIP skip. Final code checkpoint
6f7da99 passed [Windows/Linux CI](https://github.com/mohammadzaidshaikh53-cmd/nucleus-btc/actions/runs/37312027317).
Hosted CI does not establish GPU or external-pool interoperability. Git-blob
integrity verification confirms all 37 historical result files and the independent
SHA reference unchanged.

Nine fresh alternating A/B pairs per local size 32/64/128/256, with 4096
parity headers and scan checks, show no confidence-qualified >2% improvement.
Local size 32 is tested; actual hardware wavefront mode is unmeasured.
No production promotion occurred. HIP is absent. The portable exact Boolean
matrix proxy is slower; optional HIP/rocWMMA Sigma1 source is preserved but
uncompiled and unverified. See [HIP setup](HIP-SETUP.md).

SV2 uses the current specification's BIP323 mask 0x1fffffe0 (bits 5–28), subject
to SetupConnection.Success fixed-version restrictions and ExtendedJob flags.
BIP323 is Draft; deployed-pool interoperability remains an external gate.
Tests cover nonce exhaustion, unique version assignments, mask violations,
disabled rolling and cached extended Merkle construction. No wallet settings
changed and no live mining ran.

The saturation selector removes exhausted branches from its exploration floor.
Eight new classes have bounded budgets; when exhausted, the supervisor stops
at a resumable frontier instead of reopening old scalar/BDD branches. One
oversized differential result failed, was compacted without losing diagnostics,
and passed the isolated rerun. Checkpoints survive restarts.

## What should never be repeated unchanged

Do not inflate BDD/DAG budgets, rerun generic full-SHA SAT timeouts, cycle old
carry-save variants, mistake compact carry counts for cheap state, or treat
reduced-round activity as full-SHA mining evidence. Do not infer power, TH/s
or BTC earnings from these local fixtures.

Next distinct hypothesis: a **signed carry-constrained backward middle cut**,
preserving relations omitted by today's universal projection. Start with the
bounded MITM/cone runner and explicit known schedule constraints; require an
independently verified necessary relation. Kill it if omitted variables still
make the projection universal or proof cost exceeds eliminated hashing.
This is an unresolved research frontier, not an achieved mechanism.

## Reproduction and evidence

Use the project Python environment (optional local research Z3 on PYTHONPATH).
Choose fresh output paths; existing evidence is never overwritten.

```powershell
python scripts/phase_ii.py profile --bits 6 --output results/dependency-frontier-next.json
python scripts/phase_ii.py scaling --output results/phase-ii-scaling-next.json
python scripts/phase_ii.py probes --output results/phase-ii-probes-next.json
python scripts/phase_ii.py cones --output results/phase-ii-cones-next.json
python scripts/phase_ii.py gpu --output results/phase-ii-gpu-next.json
python scripts/phase_ii.py supervisor --output results/phase-ii-resume-next.json
```

Evidence: dependency-frontier-phase-ii-01/02 JSON + CSV, phase-ii-family-scaling-01,
phase-ii-structure-probes-01/02/03, phase-ii-conditional-residual-01,
phase-ii-egraph-01, phase-ii-solver-cones-01, phase-ii-local-sizes-01 and all
numbered supervisor/test records. Historical Phase-I results remain unchanged.

Primary references consulted: [FIPS 180-4](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf),
[SV2 Mining Protocol](https://stratumprotocol.org/specification/05-mining-protocol/),
[BIP323](https://github.com/bitcoin/bips/blob/master/bip-0323.mediawiki),
[Hanke, AsicBoost](https://arxiv.org/abs/1604.00575),
[Aoki, Guo, Matusiewicz, Sasaki and Wang, step-reduced SHA-2 preimages](https://orbit.dtu.dk/en/publications/preimages-for-step-reduced-sha-2/),
[New Records in Collision Attacks on SHA-2](https://eprint.iacr.org/2024/349).
Reduced-step papers supply decomposition ideas; they do not break full Bitcoin
SHA256d. Their attack costs are not mining speedups.
