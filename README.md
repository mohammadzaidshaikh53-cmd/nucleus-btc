# Nucleus-BTC

For GitHub setup and future updates, follow [docs/GITHUB.md](docs/GITHUB.md).

An executable Bitcoin proof-of-work research project for this Windows machine.
The working implementation includes a C++20 core, AMD GPU execution through
OpenCL, an independent SHA-256 reference, a bounded optimizer, and exact symbolic
experiments. It has no third-party Python dependencies.

The project has measured ordinary GPU mining improvements. It has **not** found
a SHA-256 shortcut, demonstrated ASIC competitiveness, measured energy efficiency,
or received a live Bitcoin pool acknowledgement. The included historical and
synthetic fixtures are diagnostic evidence, not newly earned BTC.

## Start here

Open PowerShell in this folder and run:

```powershell
.\Start-Nucleus.ps1
```

This builds the native core if needed, runs the tests, verifies the GPU, benchmarks
the baseline, evaluates optimizer candidates, confirms the selected configuration
against fresh fixtures, measures batch scaling, tries bounded symbolic methods,
and searches a small historical genesis nonce range. Results are saved in
`results/`. Every command is finite. A failing correctness gate stops the pipeline.

The launchers use the locally bundled Python runtime when present, otherwise
`python` from PATH. Python 3.11+ is required. MSVC Build Tools are detected with
`vswhere`; no global installations are performed.

For individual stages:

```powershell
.\scripts\run.ps1 doctor
.\scripts\run.ps1 hash
.\scripts\test.ps1
.\scripts\run.ps1 verify --backend opencl --samples 16384 --output results/verification.json
.\scripts\run.ps1 benchmark --output results/gpu-baseline.json
.\scripts\run.ps1 optimize --output results/optimizer.json
.\scripts\run.ps1 confirm --output results/confirmation.json
.\scripts\run.ps1 benchmark --champion --output results/gpu-champion.json
.\scripts\run.ps1 scaling --champion --output results/family-scaling.json
.\scripts\run.ps1 research --representation dag --output results/symbolic-dag.json
.\scripts\run.ps1 research --representation bdd --max-nodes 100000 --output results/symbolic-bdd.json
.\scripts\run.ps1 portfolio --output results/research-portfolio.json
.\scripts\run.ps1 scan --champion --output results/genesis-scan.json
.\scripts\run.ps1 status
.\scripts\research-loop.ps1 -Steps 16 -Seconds 3600
.\scripts\run.ps1 family --count 65536 --output results/adaptive-family.json
.\scripts\run.ps1 planes --nonce-bits 8 --output results/bit-planes.json
```

The equivalent portable commands are `python -m nucleus_btc ...` and
`python -m unittest discover -s tests -v` from this folder. Installing with pip is
optional; running directly from the checkout keeps native binaries next to their
source. An installed Python package alone does not install the native libraries.

## Implemented components

| Path | Working behavior |
| --- | --- |
| `nucleus_btc/bitcoin/` | 80-byte headers, byte order, compact targets, inclusive target comparison, coinbase serialization, Merkle roots, bounded permitted workspaces |
| `nucleus_btc/oracle/` | Independent pure Python SHA-256 and SHA-256d, compression and midstate verification |
| `native/` | C++20 exact CPU library and command-line hasher; optional HIP source |
| `nucleus_btc/gpu/` | Hashlib, native CPU, OpenCL GPU and optional HIP adapters; digest batches and nonce scans |
| `nucleus_btc/verify/` | Known-block, randomized-header, independent-reference, changed-job and exhaustive scan checks |
| `nucleus_btc/nucleus/` | Paired benchmark promotions, bounded SQLite PROVEN/DEAD/FRONTIER memory, diverse research retries |
| `nucleus_btc/representations/` | Exact bit-plane addition, carry-save arithmetic, Boolean DAG, reduced ordered BDD, full remaining SHA-256d symbolic circuit |
| `nucleus_btc/solver/` | Exact target constraints, bounded DPLL SAT, DAG-to-CNF encoding, pruning audits/cost accounting, overflow family splitting |
| `nucleus_btc/protocol/` | Stratum V1 job handling and finite mining session; offline SV2 framing and standard-channel state |
| `tests/` | Correctness, rejected wrong challengers, overflow retries, bounded storage, symbolic parity and mock pool integration |
| `config/` | Example pool settings and documented research defaults |
| `results/` | Measurements, verification records, optimizer history, bounded knowledge database |

## Backends and builds

The default is OpenCL. The installed AMD driver exposes the discrete `gfx1102`
board with approximately 16 GiB VRAM. The driver also exposes an integrated GPU
and duplicate platform entries. `doctor` lists them; index 0 currently selects
the first discrete board. Review device order after a driver update.

OpenCL compiles `gpu/exact.cl` through the installed driver, so a HIP SDK is not
needed for the working GPU path. The optimized nonce scan reuses the conventional
first-block SHA midstate. This is established mining optimization, not novel
family compression. Each remaining candidate is still independently hashed.

Build the native CPU core with:

```powershell
.\scripts\build-native.ps1
.\scripts\run.ps1 verify --backend native
```

On other platforms, with CMake and a C++20 compiler:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
python -m nucleus_btc verify --backend native
```

HIP source is present behind the explicit CMake option
`-DNUCLEUS_ENABLE_HIP=ON`. It requires an SDK supporting the selected GPU and has
**not** been compiled or executed here. Its current adapter supports header
digest batches; the working mining scan uses OpenCL. SDK-specific Windows
integration may require additional configuration.

## Optimization and measurement

The optimizer now generates full SHA word graphs with per-round Boolean mutation,
exact addition rewrites, schedule choices and crossover between diverse species.
An independent interpreter verifies graphs before OpenCL lowering. It verifies
each compiled candidate before seven alternating-order A/B pairs on
previously unseen serialized header fixtures. Promotion requires the lower 95%
paired bootstrap speedup bound to exceed 1.02. A second `confirm` stage compares
the winner directly against the original baseline on new fixtures, after warmup.

`PROVEN` means a tested implementation improvement within recorded preconditions.
It does not mean a formal proof of universal equivalence or a mining breakthrough.
With no power measurement, the selected champion is a **provisional throughput
champion**, not a work-per-joule champion.

Reported end-to-end throughput includes steady-state host calls, buffer setup,
kernel execution and result collection. Startup kernel compilation is excluded
and labeled. GPU event timing is separately reported. Fixtures, repeat counts,
measurement windows and raw paired ratios are preserved.

The benchmark warms the GPU but does not control clocks, thermals or background
applications. Confidence intervals cover sampled timing variation, not every
systematic effect. Performance is a local observation and should be remeasured
after source, driver, clock or hardware changes.

Without actual power data, `power_watts` and `joules_per_terahash` are null. To
calculate efficiency, provide a simultaneous measured whole-system average:

```powershell
.\scripts\run.ps1 benchmark --champion --watts YOUR_MEASURED_WATTS
```

The software does not infer power from GPU TDP or pretend that a nominal board
rating is a measurement. Pool fees, electricity cost, BTC price, and difficulty
are outside the implementation's throughput measurements.

## Research branches and retries

The symbolic engine constructs both remaining SHA-256 compressions (128 rounds)
for a small exact nonce family, including the Bitcoin target comparator. The
first compression of the 80-byte header is already captured in the standard
midstate. Every completed experiment exhaustively checks all represented digests
and accepted/rejected candidates against independent ordinary hashing.

`portfolio` tries a DAG, then BDDs with different resource budgets and family
sizes. A bounded failure is recorded and the next direction is tried. The
production GPU is never replaced by these experiments. Tests demonstrate that
tiny exact symbolic families can work while costing vastly more than hashing.

Node-budget collapse is reported as a resource observation, not the economic
collapse metric Rc. Batching can make measured cost curves appear sublinear
because fixed launch overhead is amortized. `scaling` explicitly identifies the
ordinary linear algorithm and does not promote an apparent alpha below one to
a cryptanalytic discovery.

The SAT engine reports SAT, UNSAT or UNKNOWN. Budget exhaustion produces UNKNOWN,
which cannot authorize pruning. Numerical interval rejection requires the lower
bound to be strictly above the target, because equality is accepted. Pruning
audits check for lost valid solutions. All analysis, construction, proof and
survivor costs must be included in any proposed advantage.

The knowledge store limits both record count and per-record serialized size.
`evolve` runs isolated bounded workers and resumes from transactional SQLite
execution intents. Ctrl+C stops at a safe checkpoint; process crashes leave the
same pending identity for a bounded retry. Exported JSON is a view, not the
authoritative checkpoint. OS locks prevent two supervisors sharing state.
Eight species include generated graphs, adaptive families, carry/bit planes,
structural cost hunts, full SHA CNF and alternate representations. Periodic
tests and champion timing are mandatory. `--forever` is explicit and still
respects the supplied time budget. No research launcher connects to a pool.

Adaptive symbolic work stops when its construction cost exceeds conventional
family hashing, splits disjoint nonce ranges and preserves all unresolved
solutions through exact native fallback. Bit planes execute all remaining 128
rounds; ANF adds a bounded polynomial branch. These are research mechanisms,
with current economic evidence favoring ordinary independent hashing.

Failed approaches are retained as compact records rather than raw traces.
`config/research.json` documents initial policy values; current command flags and
module defaults are authoritative. This file is not a dynamic configuration
loader.

## Live Bitcoin work

No pool URL or worker was supplied, so no external mining session was started.
The working compatibility client uses **Stratum V1**. Copy
`config/pool.example.json` to `config/local.json`, supply an actual Bitcoin pool
endpoint and worker, then run a finite session:

```powershell
.\scripts\run.ps1 mine --config config/local.json --seconds 60 --output results/live-session.json
```

Only this command initiates a pool connection. It validates the backend before
connecting, subscribes and authorizes, handles job/difficulty/extranonce updates,
avoids overlapping nonce work, independently verifies every submitted share,
and counts only positive server acknowledgements as accepted. Buffer overflow
retries the same workspace with smaller batches. Connection setup has three
bounded retries; mid-session disconnects terminate rather than submit work from
an invalid session. The V1 adapter supports conventional, pool-provided stripped
coinbase parts and fixed version/time; it does not enable version negotiation.

`stratum+ssl` uses normal certificate verification. No credentials are written
to benchmark reports. Never confuse the mock pool tests with live acceptance.
Accepted pool shares also do not establish payout or BTC balance; those depend
on the pool's accounting and payout rules.

The **SV2** module currently implements offline framing, share payload encoding,
future-job activation and target epochs. Authenticated encrypted transport and
live channel establishment are pending. It must not be represented as a complete
SV2 pool client. See [STATUS.md](STATUS.md) and [docs/ROADMAP.md](docs/ROADMAP.md).
