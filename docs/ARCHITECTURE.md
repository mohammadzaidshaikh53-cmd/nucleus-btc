# Architecture and trust boundaries

FamilyIR lives in `nucleus_btc/family_ir/`, independently of scalar IR. It
constructs only explicitly permitted finite header workspaces, preserves exact
uint32 values across representations and maps strided candidate indices
deterministically. Conceptual large workspaces require splitting before bounded
materialization. Carry transfer tables and conditional models are research
representations, not production replacements. Unknown projections retain work;
UNSAT cones require independent reproduction. See the measured Phase-II report.

```text
                    pool job / supplied header / fixture
                                   |
                     Bitcoin workspace construction
                                   |
                  exact CPU or OpenCL production backend
                                   |
                 independent CPU validation of solutions
                                   |
              V1/TLS or authenticated SV2 -> pool acknowledgement

    bounded research queue -> candidate kernels / exact representations
                                   |
               parity + exhaustive scan checks + paired timings
                                   |
                   SQLite PROVEN / DEAD / FRONTIER
                                   |
                      provisional throughput champion
```

The optimizer generates exact word IR and lowers it into the GPU compression
function. It has no mechanism to rewrite
the independent oracle or consensus serialization. Research results are data;
they are not executable instructions. All arbitrary submitted header digests
are calculated with exact SHA-256d, with raw digest bytes distinguished from
Bitcoin explorer display order.

Targets are positive uint256 values. Compact decoding checks sign, overflow,
zero and an optional network proof-of-work limit. Header PoW checking is only
one consensus condition: this project does not validate the complete chain,
transaction set, witness commitments, or contextual timestamp/difficulty rules.
The pool supplies those templates; local fixtures make no claim of new blocks.

The native full-header baseline hashes all three compression blocks. Its nonce
variant reuses the standard constant first-block midstate and performs the
remaining two compressions. The OpenCL mining kernel uses the latter path.
This known 3-to-2 block saving belongs in the baseline when evaluating novelty.

Digest batch kernels are used for broad parity checks. Mining kernels return
only passing nonces, with an atomic bounded result buffer. Overflow raises an
error and never silently discards solutions. Split retries include their time
in end-to-end cost.

GPU resources have explicit lifetimes. OpenCL is accessed through ctypes using
complete pointer-sized function signatures. Queues, kernels, programs, buffers,
events and contexts are released after use. A backend instance is owned by one
thread; sharing its mutable kernel arguments across threads is unsupported.

Persistent knowledge records are bounded and JSON serializable. A current
champion is protected during consolidation. Historical measurements must be
reverified after environment changes; a stored result is not an enduring
performance guarantee.

Supervisor SQLite state is FULL synchronous. Intent, attempt count and identity
are persisted before an isolated worker launches. Completed result and checkpoint
are written transactionally; production promotions use compare-and-swap and an
atomic receipt. OS locks survive stale lock files while releasing on process
death. JSON exports use fsync plus atomic replacement. Historical measurements
are never overwritten by supervisor workers.

Word IR graphs are topological, structurally hashed and serialized canonically.
Generated C/OpenCL uses liveness-based temporary reuse. Common expressions,
dead-node removal, equivalent Ch/Maj, modular reassociation, carry-save and
message schedule order are exact; their performance is measured separately.

The symbolic SHA engine and target circuit are exact for their finite input
family. Bitslicing, carry-save arithmetic, DAG sharing, BDD canonicalization and
SAT solving are independently tested primitives. None currently offers a
measured cheaper path than ordinary hashing on Bitcoin work.

Hybrid representations convert at round boundaries and include the conversion
cost; transient Boolean nodes are reclaimed between rounds. Full SMT bit vectors
lower the word IR, audit constant assignments against the immutable oracle, and
never reject an UNKNOWN family. Adaptive policy stores bounded economic/growth
observations, adjusts thresholds and preserves exhaustive fallback coverage.

The reference Rust Noise helper handles pinned authority authentication and
encrypted frames over bounded local IPC. Synthetic server authorities exist only
in a separate fixture build. V1/SV2 reconnect uses fresh job state and preserves
acknowledged statistics. CPU recovery retries the exact failed GPU range.
