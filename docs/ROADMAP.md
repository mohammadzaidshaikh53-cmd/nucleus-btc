# Step-by-step development and acceptance gates

| Stage | Implementation and current gate | Remaining evidence |
| --- | --- | --- |
| 0: independent oracle | Pure Python SHA, known vectors, padding boundaries, genesis and target semantics pass | Continue differential validation when code changes |
| 1: exact baseline | Native C++ and installed OpenCL GPU run; randomized digest and exhaustive scan tests pass | Sustained simultaneous whole-system power measurement |
| 2: self-optimizer | Bounded kernel candidate generation, gated promotions, confidence intervals, fresh confirmation and persistence run | Recheck performance on real received jobs and multiple machines |
| 3: family measurements | Non-wrapping workspaces and batch costs through 2^24 candidates run | Demonstrate savings beyond launch amortization and standard midstate reuse |
| 4: representations | Bit-plane/carry primitives, DAG/BDD, full SHA symbolic families and collapse tracking run | Scalable economic advantage; current methods are slower or hit resource limits |
| 5: pruning | Full finite-family target circuits, SAT UNKNOWN handling, exhaustive lost-solution audits and complete cost equation exist | Cheap useful pruning on large full-SHA Bitcoin families; not demonstrated |
| 6: structural families | Negotiated version/time workspace validation and amortization accounting exist | A proven structural property with positive measured lifetime value; not discovered |
| 7: pool validation | V1 compatibility client and mock integration pass; offline SV2 standard-channel logic exists | Actual pool/worker, accepted live BTC shares; implement and verify authenticated SV2 transport |
| 8: economics | No profitability claim or assumed power baseline | BTC accounting, pool fees, electricity cost and measured efficiency |

The report's long-term target remains an open cryptanalytic research question.
No amount of repeated retries can guarantee that the desired shortcut exists.
Retries here are bounded, change the mechanism or resource budget, preserve
failure evidence, and never relax exactness to manufacture success.

The next practical milestone is a finite session against a user-configured
Bitcoin pool, with accepted/rejected/stale/unacknowledged counts preserved.
Power should be measured concurrently. A genuine full-SHA pruning discovery
needs an exactness argument, independent implementation, unseen live jobs and
cost accounting before it can enter production.
