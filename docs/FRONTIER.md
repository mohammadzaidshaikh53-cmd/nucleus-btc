# Verified boundary and runnable frontier

## Target-directed middle-cut checkpoint

The 20–30 TH/s target remains open. The next signed-carry experiment has now
been evaluated: [MIDDLE-CUT-RESULTS.md](MIDDLE-CUT-RESULTS.md). Independent-bit
cubes admit exact inverse-round witnesses; joint affine boundary constraints
vanish at rank 512 for K=1024. Direct algebraic target-word proofs remove solver
overhead, but the projected rank is already 32 at K=64. A further 168-family
nonce/version alignment hunt finds no nonuniversal target-word projection.
Best complete pipeline 0.24457x GPU; no promotion or useful pruning.

Do not repeat those mechanisms unchanged. The remaining requirement is a
nonlinear boundary relation with nonenumerating construction and a cheaper
independent proof. No such relation is established. Historical frontier below
is retained as checkpoint history, not an instruction to rerun exhausted work.

## Phase-II decision

**NO LARGE ADVANTAGE FOUND.** New exact mechanisms and full-hash scaling are in
[PHASE-II-RESULTS.md](PHASE-II-RESULTS.md). Best descriptive alpha=0.98;
output-residue beta=1. Carry-only beta=0.06271 does not reduce total work.
Conditional affine descriptors lose their advantage by round 4. Guided
nonce-bit-11 splitting costs more than unsplit work. Prefix rejection is exact
but F≈1020 versus the GPU; useful rho=0, useful Q=0. UNKNOWN retains work.

Next mechanism: signed carry relations at a backward middle cut, with explicit
schedule constraints and independently verified projection proof. The finite
cone/MITM runners are available; a useful relation remains unresolved. HIP/WMMA
compilation, external pool interoperability and power need external setup.
Do not repeat the historical exhausted branches below unchanged.

The engineering checkpoint provides exact oracle/native/OpenCL execution,
generated word IR, validated mutation/crossover, protected champion, isolated
resumable supervision, bounded knowledge, adaptive economic splitting,
representation conversions, SAT/SMT, carry experiments and authenticated mining
protocols. This is outcome B: **no large new advantage found in this search space**.
The requested 20–30 TH/s or cheaper full-SHA mechanism is not demonstrated.

## Measured hypotheses

| Direction | Actual evidence | Current decision |
| --- | --- | --- |
| Generated scalar/unrolled/scheduled/crossover graphs | 32 kernels passed parity and paired timing; second 16 ratios 0.620..1.005 relative to champion | No qualified promotion; continue novel genomes, not identical reruns |
| Full bit planes, ripple | 2^8..2^20, three fresh fixtures per size; 2^20 median 5.211 s | Economically dominated by native/GPU |
| Carry-save bit planes | Same sizes; 2^20 median 5.642 s | Delayed multioperand carry resolution works exactly but gives no gain here |
| Prefix and carry-select | Same sizes; 2^20 medians 11.942 and 10.386 s | Lower carry dependency depth does not reduce total work on this interpreter |
| DAG/BDD to live planes | Exact round-boundary conversion; passes through 2^16; 2^18 and 2^20 exceed the 64 MiB estimated plane budget | Runnable bounded species, demoted for large families |
| Full DAG/CNF | Two-candidate full SHA/target parity, 213,912 nodes, 763,979 clauses; about 0.986 s | Solver UNKNOWN; conversion/proof cost dominates hashing |
| SMT bit vectors | Complete SHA/target formula; three constant assignments independently audited; bounded solver | UNKNOWN preserves family; no pruning claim |
| Rewrite identities | Z3 proves five universal uint32 identities | Local rewrite proof only, not a full cryptanalytic advantage |
| ANF and pure BDD/DAG | Exact small-family completion or recorded node/monomial collapse | Compactness does not persist at useful family sizes |
| Structural header hunt | Measured permitted diagnostic version/time variations and hunt amortization; no verified reduction | Timing fluctuations do not identify a useful structural property |
| Naive redundant Ch/Sigma rules | Exact counterexamples to componentwise nonlinear processing | These particular shortcuts are refuted; other encodings remain open |

The warmed single-scan baselines at 2^20 were approximately 0.349 s native and
0.001519 s OpenCL. These sparse launches are distinct from sustained 1.634 GH/s
champion confirmation. Research costs include construction, conversion, audit
and isolated-process startup. Large-family parity audits sample 65–66 lanes;
families through 4096 lanes are exhaustively audited. No lost-solution guarantee
is inferred from sampling alone; the implementations use exact primitives and
also have exhaustive small-family target/byte-order tests.

Fitted bit-plane overhead-adjusted exponents are around 0.96–1.04. They are
finite descriptive fits affected by audit policy, process startup and integer
width. They do not establish algorithmic alpha <0.9. An all-rejected finite
family does not imply cheap useful pruning: analysis F includes all work, and
the observed GPU-relative speed is below 0.0003 in these implementations.

## Continue reproducibly

```text
python -m pip install -e .[research]
python scripts/build_sv2.py --fixtures
python scripts/test_runner.py --require-native --require-gpu --require-sv2
python -m nucleus_btc evolve --steps 16 --seconds 3600
python -m nucleus_btc representation-scaling --output results/planes-NEW.json
python -m nucleus_btc representation-scaling --hybrids --output results/hybrids-NEW.json
python -m nucleus_btc research --representation hybrid-bdd --nonce-bits 6 --max-nodes 20000
python -m nucleus_btc smt --nonce-bits 8 --timeout-ms 250
python -m nucleus_btc smt --templates
python -m nucleus_btc family --count 1048576
```

Build the native core first using the commands in README. On machines without
OpenCL, the supervisor keeps CPU/representation work available; GPU candidate
experiments record the environment blocker. A GPU runtime scan failure during
a mining session retries the same range on an independently verified CPU.

The supervisor persists split thresholds, ordering, transition round and bounded
observations. Economic demotion keeps all candidates and switches to conventional
hashing. Highest live nonce-bit splitting gives contiguous disjoint subfamilies;
arbitrary interior-variable splits are a different strided-workspace frontier.
The selection model is a small Bayesian counts/cost heuristic with mandatory
species coverage. No measured selection advantage or nonce prediction is claimed.

Remaining distinct research directions include genuinely cheaper nonlinear
redundant representations, strided workspace splitting, a proof method cheaper
than hashing, and backend lowering of a structural sharing mechanism. Existing
IR, hybrid and solver entry points allow these to resume without replacing the
champion. No repeated benchmark can prove that such a mechanism exists.

## External gates

No local pool configuration exists. Live V1/SV2 acceptance, received-job stress
and payout accounting require actual user pool settings; SV2 also needs its
authority key. Local mock acceptance is not live acceptance. Whole-system energy
requires a trustworthy measurement source, so E, watts and J/TH remain null.
HIP needs a supported installed SDK; OpenCL already works. Additional independent
machines and external interoperability tests need environments not available here.

Authoritative evidence: new JSON files in `results/`, `STATUS.md`, and the active
execution plan. Historical result files and the independent oracle remain intact.
