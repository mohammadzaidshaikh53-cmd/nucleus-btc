# Exact target-predicate vNext: measured outcome B

The original **20–30 TH/s equivalent exact valid Bitcoin work** target is
unchanged and unachieved. The requested offline engine is implemented in the
existing repository. The tested reduced product, opaque carry/parity lineage,
bounded refinement and inverse target-demand mechanisms are falsified as useful
mining shortcuts in these fixtures. This is a bounded negative result, not a
proof that every possible SHA shortcut is impossible.

## Implemented vertical slice and trust boundary

`family_ir/symbolic.py` represents fixed/free nonce, permitted version, bounded
nTime and template-derived extranonce/Merkle work without constructing K-sized
arrays. Implicit iteration and `construct()` fail explicitly. Scope fingerprints
bind the header, permissions, bounds, coinbase, Merkle branch and fixed bits.
One-header setup/audits are explicit; fallback is linear in K and reports its
candidate counts. Candidate solution storage can grow with matches.

`ir/target_predicate.py` specializes the existing exact scalar SHA graph, folds
constants, shares expressions and slices from a single Boolean root for the
inclusive raw-digest little-endian uint256 comparison. A digest view remains
for abstract analysis and independent checking; both views' storage is reported.
Equality can require all eight words, so backward slicing does not make full
SHA cheap. The all-maximum-target predicate simplifies to true. Header, coinbase
padding boundaries and each Merkle sibling use complete standard SHA-256d.

`family_ir/domains.py` combines known bits, power-of-two residues, bounded odd
moduli 3/5, input-bit GF(2) relations, unsigned carry envelopes, sparse Boolean
polynomials and target intervals. Reduction exchanges implied facts through at
most four iterations by default. Degree/term limits widen an entire expression
to TOP. Odd modular sums subtract the wrap carry and require that carry to be
known; uncertain carry cannot establish an odd residue. Addition's bit-level
sum/carry recurrence, Boolean identities and bit permutations define the sound
transfer contracts. Exhaustive reduced operands and random uint32 cases are
regression checks of these contracts, not universal proofs from sampling.

`ir/predicate_rewrite.py` is a bounded exact local equivalence pass, separate
from enumerative FamilyEGraph. It checks named uint32 proof identities and can
instantiate independently verified, source-qualified universal bit-local
lemmas. Finite-scope lemmas cannot authorize unrestricted symbolic rewrites.
Rewritten graphs remain diagnostic until certificate binding supports them.

`verify/certificates.py` independently replays conservative mask/carry transfers
and validates scope, target, source, byte order, rule identity and contradiction.
Supported large-scope schemas are interval and projected known-mask parity or
power-of-two residue contradictions. General learned cross-word, nonlinear or
signed-carry certificates are **not implemented**; unsupported or unreproduced
proofs retain the family. Optional finite-exact proofs declare and enumerate
at most 256 candidates. Random audits never authorize rejection.

`target_engine.py` persists source-qualified binary refinement trees with
durable per-leaf intent. An independent structural checker establishes exact
partition coverage without candidate lists. Pilots compare actual target
information gain per cost. Leaf/depth/time/economic/memory limits retain work.
Contiguous nonce leaves call the unchanged champion scan; overflow splits the
same range and failures retry it on hashlib. Other leaves stream bounded header
batches. Above the execution budget, the complete retained scope is explicitly
SCHEDULED rather than reported as hashed.

Workspace compilation delegates actual SV2 flags, version masks, time and
Extended extranonce bounds to the established adapter. Version/extranonce are
outer dimensions because they invalidate shared preparation; nonce/time are
inner dimensions. This is a reuse heuristic, not an optimized hierarchy or a
claim that a workspace is luckier. Local fixtures carry no live permission claim.
No transaction selection or ordering is used as extra hash space.

## Fresh champion and permanent design budgets

The same OpenCL full-unroll/alternate-Boolean/local-size-64 champion passed a
fresh 16,384-header differential check, independent-reference subset and 20
changed-job/equality scan cases. Nine warmed held-out timing windows at K=2^22
measured **1.541662 GH/s**. Startup compilation is excluded from steady-state
throughput and separately recorded. Power and J/TH remain null.

| Required exact throughput | Required speedup over fresh champion | Allowed normalized total cost |
| --- | ---: | ---: |
| 20 TH/s | 12,973.012x | 0.0000770831 |
| 30 TH/s | 19,459.518x | 0.0000513887 |

These are dynamically calculated requirements, not attained results. Production
kernel, oracle, serialization and protocol behavior were preserved.

## Measurements and causal failures

The primary experiment has 120 pipelines: three unseen serialized jobs, K=256,
65,536 and 16,777,216, four observables, share/network-style fixtures plus loose,
equality, target=1 and maximum-target diagnostics. The share fixture is difficulty
256. Network-style nBits `0x17020000` is an explicit synthetic fixture at roughly
140.735 trillion difficulty; it is not an observed block or current network
difficulty. K=256 receives exhaustive independent predicate/fallback audits.
Larger audits sample eight assignments solely for regression.

Every timed row includes setup, compilation, rewrite, abstract proof, checking,
independent audit, actual GPU survivor work and solution validation. Its baseline
has the exact same family/target, a warmup and five raw warmed GPU samples.
F_analysis includes setup/proof/audit cost divided by that baseline. Full speedup
uses baseline divided by total measured pipeline wall time. Audit time inside
fallback is already included in fallback wall time and must not be added twice.
This deliberately complete offline-laboratory cost is distinct from an
unimplemented production integration.

| Mechanism | Best realistic-target pipeline/GPU at K=2^24 | Minimum F_analysis at that K | Useful rho |
| --- | ---: | ---: | ---: |
| Known masks ablation | 0.023071x | 42.4714 | 0 |
| Reduced product | 0.021305x | 45.9499 | 0 |
| Opaque carry/XOR lineage | 0.018597x | 52.8290 | 0 |
| Initial backward packing-view probe | 0.021543x | 45.3940 | 0 |
| Corrected inverse-demand, three fresh jobs | 0.019833x | 49.4850 | 0 |

These are descriptive best observations, not confidence-qualified improvements.
All nontrivial large-family target intervals are universal: information=0,
exact rho=0, useful rho=0, Q=-log10(1-rho)=0. Singleton rejection certificates
pass independent checks, but provide no large-family mining advantage.

The product proves all 32 bits of `x+~x=0xffffffff` where masks alone do not.
Cross-domain reductions also recover a few early SHA facts, but message-schedule,
Ch/Maj and carry expansion exceed degree/term limits. For nonce widths 16/24,
all retained state polynomial/known-bit information disappears by zero-based
round 7 of the variable header compression; width 8 loses it by round 8.
Both remaining complete compressions still execute in the exact oracle/fallback.

An append-only precision provenance supplement corrects one instrumentation
boundary: the initial round profile counted live abstract nodes but omitted
dead constants eliminated by folding. The current profile includes those exact
constants and labels genuinely untracked dead state bits separately. Nine
fresh profiles recover 256 known bits throughout the constant first header
compression; the variable-compression loss rounds 7/8 and zero target
information are unchanged. Old zero counts for folded constant states must not
be interpreted as TOP.

The first causal follow-up keeps exact XOR equations in existential opaque
Boolean/carry atoms rather than expanding high-degree polynomials. It avoids
some polynomial expansion, but frees the relations between those atoms. One
sample records 31,822 opaque carry atoms and 111,035 support widenings; no output
bit or target bound becomes known. This is a different observable with the same
negative full-target outcome, not a larger ANF budget.

The second follow-up pushes the necessary zero high digest word backward through
proved inverse operations. Its initial view stopped at byte-packing OR nodes.
The corrected exact pre-packing state binding passes parity, crosses the final
feed-forward constant addition and creates 64 conditional known bits. It then
stops at ADD32 with two unknown operands in each of three new jobs. These are
necessary conditions on possible solutions, not 64 bits of family target
discrimination. Without a joint relation, the inverse remains universal; no
candidate is pruned.

Six refinement trials compare economic cutoff and bounded pilots for product,
lineage and backward views. All retain one leaf at depth zero. Economic trials
stop because proof cost already exceeds conventional hashing; unrestricted
pilots find zero target-information gain. Best complete refinement/fallback
pipeline is 0.034073x the GPU; best pilot trial is 0.007010x. Coverage proofs
retain all 2^24 candidates. Few leaves here mean refinement aborted, not success.

Five conceptual widths from 2^8 to 2^56 allocate no candidate array. The largest
uses 5,884 digest-view nodes, 6,904 predicate-view nodes and 297,898 combined
serialized graph bytes. A separate tracemalloc run peaks at **9,879,271 bytes**
of Python allocations; driver/device storage and process RSS are excluded.
Its timing is instrumented and excluded from economics. The descriptive analysis
slope is approximately 0.000073, but precision is TOP throughout. No measured
same-family GPU baseline or speedup is claimed for conceptual-only 2^32/2^56;
all work is retained and scheduled. A flat universal abstraction is not sublinear
exact mining.

## Falsification gates and retained frontier

Exact predicate parity, nonenumerating workspace storage, transfer regression,
toy reduced-product precision and bounded partition coverage pass. The gate
requiring nontrivial full-SHA target discrimination with scaling fails. Useful
exact rejection on unseen realistic targets also fails. Performance optimization
and production pruning are therefore not justified by these results.

The distinct unresolved frontier is a **nonenumerating joint message-schedule,
carry and Boolean invariant** that survives both complete variable SHA
compressions, narrows the negotiated target and has an independent certificate.
No such invariant has been discovered or proved here. Opening another branch
requires a concrete relation, declared scope, sound transfer/checker and a
bounded information-retention test. Reopening exhausted affine/cube/SAT branches
unchanged, increasing budgets or claiming speed from TOP are not valid next steps.

## Supervisor, validation and reproducibility

The `predicate-vnext` selector profile replaces the old exploration floor with
predicate/domain/product/refinement/certificate/lemma/compiler species. The
corrected inverse-demand species was added only after the packing loss was
observed. Across three persisted runs, the real isolated supervisor completed
26 steps, including periodic regression and benchmark workers, resumed its
checkpoint and reached `frontier-complete`. No production promotion occurred.
Research promotion is explicitly blocked. Legacy selector behavior remains
available for historical tests; it is not this profile's exploration floor.

Lemma memory is bounded by class and database capacity. Canonical statement,
scope, proof, checker/source, costs, domains, reuse and failure boundaries are
stored. The learned bit-local identity `x^(x&y)=x&~y` is universally proved by
complete Boolean cases plus bit-position independence, independently checked
and consumable by bounded pattern substitution. Finite proofs retain their
input scope. Trace agreement and solver UNKNOWN cannot create PROVEN knowledge.
Reuse/source/scope violations are tested; no learned lemma yields a mining gain.

The separate lemma-reuse receipt measures construction/proof/checking, rejects
the earlier source's record, refreshes its independently proved scope, consumes
it through the actual store and rewrite pass and records reuse_count=1. Sixteen
fresh uint32 substitution regressions pass. This is reuse of a local identity,
not a family rejection or mining improvement.

All three full local runs: **117 tests, 116 passed, one optional HIP skip**, requiring
native, discrete OpenCL GPU and authenticated local SV2 fixtures. Nineteen new
test methods cover tiny/full predicate parity, derived Merkle/padding, widening,
cross-domain precision, independent rejection, tampering, partition coverage,
recovery, memory/source limits, finite/universal lemma reuse, worker payloads,
exhaustion and promotion denial. HIP SDK remains unavailable. Hosted Windows/
Linux CI validates CPU/native/locked Rust/encrypted protocol paths; local GPU
evidence remains separate. Code checkpoints 348043b and 5aca097 passed hosted CI;
the final published revision has its own hosted run.

Baseline a319bde's **74 historical result files and 120 protected files** compare
unchanged by canonical Git blob, including oracle, Bitcoin, GPU, protocol,
native, solver, original FamilyIR, old result documents and old plans.
Historical primary measurements are bound to commit 8a46261; the corrected
inverse follow-up is bound to the following revision and new source fingerprints.
No historical JSON or result document was rewritten.

Raw evidence: `results/predicate-vnext-champion-01.json`,
`predicate-vnext-experiments-01.json`, `predicate-vnext-inverse-followup-01.json`,
`predicate-vnext-supervisor-01/02/03.json`, `predicate-vnext-tests-01/02/03.json`,
`predicate-vnext-integrity-01.json`, `predicate-vnext-precision-provenance-01.json`
and `predicate-vnext-lemma-reuse-01.json`.

Reproduce against the current source using **fresh output filenames**:

```powershell
python scripts/test_runner.py --require-native --require-gpu --require-sv2 --output results/predicate-vnext-tests-04.json
python scripts/predicate_vnext.py champion --output results/predicate-vnext-champion-02.json
python scripts/predicate_vnext.py experiments --champion results/predicate-vnext-champion-02.json --output results/predicate-vnext-experiments-02.json
python scripts/predicate_vnext.py inverse-followup --champion results/predicate-vnext-champion-02.json --output results/predicate-vnext-inverse-followup-02.json
python scripts/predicate_vnext.py supervisor --steps 30 --directory results/evolution/predicate-vnext-replay --output results/predicate-vnext-supervisor-04.json
```

The current experiment command includes the corrected inverse view; it should
not be expected to reproduce the historical packing-view probe's intermediate
loss node. Seeds/configuration and raw samples identify each measured run.
Clocks, thermals and background load are uncontrolled. No SHA break, power
saving, pool acceptance, BTC earnings or achieved 20–30 TH/s is claimed.
