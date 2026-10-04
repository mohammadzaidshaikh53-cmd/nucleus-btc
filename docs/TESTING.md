# What the verification establishes

Run `scripts/test.ps1`. The runner saves test totals and skip reasons in
`results/test-suite.json`. The optional HIP test is skipped until its library
is built; that skip does not validate HIP. During this build, OpenCL and native
backends were required rather than silently skipped.

For a required-device run:

```powershell
python scripts/test_runner.py --require-gpu --require-native
```

The suite checks:

- FIPS known digest, padding boundary lengths and independent SHA parity.
- Known Bitcoin genesis header serialization, digest and encoded target.
- Exact target equality, sign/overflow/zero rejection and full difficulty precision.
- Independent randomized digest batches in C++ and OpenCL, including byte-extreme headers.
- Nonce zero, final uint32 nonce, non-multiple workgroup batches and changed job midstates.
- Exhaustive scan parity at targets yielding zero, sparse and many solutions.
- Target equality on a digest chosen from a candidate in the scanned family.
- Overflow detection and split retries preserving every candidate and solution.
- Deliberately wrong challengers rejected before benchmarking/promotion.
- Merkle mutation flags, coinbase serialization and negotiated version/time boundaries.
- Bit-plane and carry-save identities, bounded DAG sharing and BDD truth tables.
- Both remaining SHA-256d compression blocks and the target predicate in a small symbolic family.
- Tseitin gate truth tables and DPLL results against 100 exhaustively solved small formulas.
- SAT budget exhaustion reporting UNKNOWN, never an UNSAT certificate.
- Knowledge budgets, timing confidence gates and pruning false-negative detection.
- Fragmented/bounded protocol lines, V1 byte conventions, difficulty epochs and stale-job rejection.
- A socket-pair mock pool that subscribes, authorizes, independently validates submitted shares,
  rejects duplicate work and returns acknowledgements. It is not a live BTC pool.
- SV2 frame fragmentation, share payload encoding, future-job activation and stable active targets.

Randomized and exhaustive finite tests provide evidence for the tested input
space; they do not prove universal kernel equivalence. Pool acknowledgements
alone do not prove pruning preserves all solutions. Any new pruning mechanism
requires a correctness argument and loss-of-solutions audits in addition to
checking its surviving hashes.

Timing measurements and correctness tests serve different purposes. Tests run
outside timing windows. The final confirmation uses fresh header fixtures and
alternating A/B order, with startup compilation excluded and explicit warmup.
