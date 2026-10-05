# Validation gates

Phase-II local release: 90 tests, 89 passed, optional HIP skipped. New gates
include exhaustive FamilyWord reconstruction, full SHA256d family parity,
interior split coverage, executable genome transitions, independently reproduced
solver UNSAT cones, inclusive little-endian early target comparisons, SV2 mask
and exhaustion accounting, bounded worker payloads and saturation completion.
Family scaling independently checks every digest through K=16384. Local-size
timings have nine alternating fresh pairs each. Hosted CI covers CPU/native/
encrypted-protocol paths; GPU and optional HIP hardware remain separate.

The immutable reference is `nucleus_btc/oracle/sha256.py`; hashlib supplies an
additional independent implementation. Generated candidates do not edit either.

Before promotion require known Bitcoin and padding vectors, random serialized
headers, nonce-range parity, changed Merkle/version/time fixtures, full inclusive
uint256 target comparisons, overflow/lost-solution audits and a fresh large
holdout. A single bit mismatch rejects the candidate. Finite randomized testing
is evidence, never a formal proof of universal equivalence.

Each rewrite documents its uint32 identity and preconditions. Exhaustive reduced
domains and random uint32 tests verify templates, and full SHA differential
tests verify composition and lowering. Incorrect challengers must be rejected.

Performance follows correctness: warmup, alternating paired A/B order, independent
heldout fixtures, end-to-end and GPU-event time, raw samples and bootstrap bounds.
Driver/device/source/config metadata is mandatory. Power and thermals remain null
unless measured; sensor estimates are distinct from external meter observations.

Hosted Windows/Linux CI builds the native core and runs CPU tests. Locally run
`python scripts/test_runner.py --require-native --require-gpu` and large generated
candidate holdout verification. Historical genesis work and mock shares do not
constitute new BTC. Live claims require actual positive pool responses and
secret-free header/digest/target evidence.

CI additionally builds locked Rust production/fixture helpers and requires local
encrypted standard/extended SV2 tests. Optional Z3 is installed in CI. Universal
SMT UNSAT equivalence proofs cover only the named uint32 rewrite templates;
full generated algorithms still require independent differential verification.
Large-family representation audits are sampled and labeled. Saved report writers
choose a fresh filename whenever an existing measurement would be overwritten.
