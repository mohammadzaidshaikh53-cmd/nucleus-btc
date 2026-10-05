# Local project status - 5 October 2026

The runnable foundation and first research loop are implemented and tested.
The requested long-term SHA-256 advantage remains unproven. The user selected
continued local testing; no live pool mining was started.

## Verified build

- Native C++20 DLL and executable compile with installed MSVC Build Tools.
- OpenCL executes on the installed discrete AMD `gfx1102` GPU.
- Startup verification reproduced 33 tests: 32 passed, optional HIP skipped.
- The first engineering checkpoint adds exact word IR, generated GPU kernels,
  transactional supervisor recovery and adaptive family validation tests.
- Fresh confirmation: **1.634 GH/s**, **1.713x** original kernel; historical
  1.605 GH/s / 1.710x evidence remains unchanged in `results/confirmation.json`.
- Sixteen generated graph candidates passed parity; none earned promotion.
- Supervisor completed eight isolated experiments, retained a 145 KB checkpoint,
  resumed from SQLite and continued after failed symbolic/SAT experiments.
- Full bit-plane SHA/target parity passed exhaustively for 256 candidates.
- Adaptive BDD/native solving covered 65,536 candidates exactly; its measured
  economic collapse triggered conventional hashing rather than dropping work.
- Separate native and GPU verification each checked 16,384 randomized headers,
  an independent reference subset, and 20 exhaustive scan cases.
- The local pipeline completed through benchmarks, fresh confirmation, family
  scaling, two representation directions, a five-attempt research portfolio and
  a historical genesis nonce scan.
- The historical scan found nonce 2083236893 and the known genesis hash. This
  is verification of an existing block, not a newly mined block or BTC reward.

## Actual local measurements

| Measurement | Result | Scope |
| --- | --- | --- |
| Original OpenCL kernel, fresh paired confirmation | 0.936 GH/s median | 2^22 candidates per batch; held-out serialized fixtures |
| Selected OpenCL kernel, same confirmation | **1.605 GH/s median** | Same batch size and fixtures; steady-state end-to-end |
| Direct paired improvement | **1.710x** | Nine alternating A/B pairs; bootstrap 95% interval 1.699..1.724 |
| Selected kernel at 2^20 batches | 1.281 GH/s median | Smaller batches include more launch overhead per hash |
| Largest-three batch scaling slope | 1.113 | Observed timing slope; algorithm remains linear independent hashing |
| 4-bit nonce family, DAG with 20,000 nodes | Collapsed at round 21 | Resource budget; not a proof of impossibility |
| 4-bit family, BDD with 20,000 nodes | Collapsed at round 29 | Alternate representation tried after DAG failure |
| 4-bit family, BDD with 100,000-node budget | Full 128 remaining rounds and exact target predicate passed | About 58,600 nodes; substantially slower than ordinary hashing |
| 6-bit family, BDD with 100,000 nodes | Collapsed at round 22 | Increasing family size did not preserve compactness |
| 2-bit family, BDD | Exact full computation passes | Tiny family only; setup/evaluation still slower |

Benchmark compilation/startup is excluded and labeled. Host overhead, ordinary
midstate preparation/caching, kernel execution and collection are included in
steady-state timing. Background load, clocks and thermals remain uncontrolled.
Raw measurements are in `results/confirmation.json`, `gpu-baseline.json`,
`gpu-champion.json`, `family-scaling.json` and `research-portfolio.json`.
These are observations against this project's baseline, not a comparison with
the fastest available miner or any ASIC.

## Working source and evidence

- Exact Bitcoin headers, compact targets, full-precision difficulty conversion,
  coinbase serialization, Merkle paths and permitted workspace boundaries.
- Independent Python reference, hashlib oracle, C++ core and OpenCL batch/scan kernels.
- Kernel candidate generation, correctness gates, timing-noise gates, fresh
  confirmation, protected champion state and bounded knowledge records.
- Bit-plane/carry primitives, exact DAG/BDD SHA circuits and target constraints,
  bounded SAT, pruning audits, overhead accounting and lossless overflow retries.
- V1 pool adapter tested against a socket-pair mock server. Mock acknowledgements
  are local protocol evidence, not live pool acceptance.
- Share submission waits for pool acknowledgements when its bounded request
  window is full, times out stalled pools and discards replacement-job shares.
- Authenticated SV2 transport, standard/extended channels and local encrypted
  mock sessions pass. V1 adversarial response, TLS and reconnect tests pass.
- Current local suite: 60 tests, 59 passed, optional HIP skipped; three locked
  Rust cryptography/input tests pass. Checkpoint 1 CI passed on Windows and Linux.
- PowerShell launchers, CMake build, local CLI, documentation and saved test results.
- Generated word IR has eight diverse species, safe identity templates, structural
  CSE, deterministic serialization, exact interpreter and OpenCL/C++ lowering.
- Bayesian experiment selection schedules diverse species and periodic safety
  checks; generated production promotion requires a fresh 16,384-header holdout.
- BDD ordering, ANF monomial bounds and phase-specific collapse diagnosis are
  runnable. Current generated/carry/symbolic search found no large new advantage.

## Pending milestones

- HIP compilation and hardware verification: an SDK is not installed; its source
  is optional and explicitly unverified.
- External SV2 interoperability and live acceptance: local encrypted standard/
  extended sessions are verified, but no configured external pool exists.
- Actual pool acceptance and BTC payout: intentionally not attempted while local
  testing is selected. A real Bitcoin pool URL and worker are required later.
- Simultaneous measured whole-system power: no J/TH or profitability claim exists.
- A structural header property with positive measured amortization.
- Cheap exact pruning or scalable family compression that beats full ordinary
  hashing after all construction/proof costs. None was found in these attempts.

The ordinary GPU optimizer succeeded. The tested symbolic alternatives supplied
useful negative evidence and never replaced the production path.
