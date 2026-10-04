# Primary technical sources

Reviewed during implementation on 5 October 2026.

- [Bitcoin Core proof-of-work checks](https://github.com/bitcoin/bitcoin/blob/master/src/pow.cpp): compact-target limits and inclusive hash comparison.
- [Bitcoin Core chain parameters](https://github.com/bitcoin/bitcoin/blob/master/src/kernel/chainparams.cpp): independently known genesis header values and expected hashes.
- [NIST FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final): SHA-256 algorithm and byte conventions.
- [Khronos OpenCL specification](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_API.html): API lifetimes, buffers, kernel submission and event timing.
- [AMD HIP installation documentation](https://rocm.docs.amd.com/projects/HIP/en/latest/install/install.html): optional HIP environment requirements.
- [Stratum V2 protocol overview](https://stratumprotocol.org/specification/03-protocol-overview/): binary frame and field encoding.
- [Stratum V2 mining protocol](https://stratumprotocol.org/specification/05-mining-protocol/): standard jobs, activation, target changes and share fields.
- [cpuminer job handling](https://github.com/pooler/cpuminer/blob/master/cpu-miner.c) and [notification handling](https://github.com/pooler/cpuminer/blob/master/util.c): V1 byte-order and notification conventions, consulted as interoperability references.
- [ASICBoost paper](https://arxiv.org/abs/1604.00575): context for established higher-level mining reuse.

The user's Nucleus-BTC project report supplied the research architecture. Its
benchmark assumptions were not imported as measured facts. Native and Python
implementations in this project were authored for this build; no upstream
mining source tree was copied into the repository.
