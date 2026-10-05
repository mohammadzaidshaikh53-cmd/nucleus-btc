# Mining transport and validation

V1 and SV2 are selectable from the ignored local pool configuration. Every
submitted header is checked by the independent Python SHA256d oracle. Positive
pool acknowledgements alone increment accepted counts. The bounded evidence
ring records timestamp, serialized header, raw digest, target, nonce, job id
and acknowledgement, without worker passwords or wallet data.

V1 supports TCP and normal certificate-verified TLS, subscribe/authorize,
difficulty on subsequent jobs, extranonce changes, bounded outstanding requests,
stale rejection, out-of-order share replies, duplicate suppression and at most
three fresh connections. Repeated work keeps a bounded nonce/extranonce cursor.
TLS failure closes the socket. Reconnect discards all previous connection jobs.

SV2 uses the official `noise_sv2` 2.0.0 library through a locked Rust helper.
The helper has no network or wallet access. Pin the upstream authority using
`authority_pubkey` (32-byte hex) or the checksummed authority in the URL path.
No plaintext fallback or unpinned initiation is supported. The [security
specification](https://stratumprotocol.org/specification/04-protocol-security/)
defines the authenticated Noise handshake and encrypted header/payload chunks.

The core mining client implements setup version 2, standard and extended
channels, future/active jobs, previous-hash activation, target epochs, group
addressing, channel updates, extranonce prefix changes, share submit/reject/
aggregated success, bounded backpressure, authenticated endpoint reconnect
with the same authority, and channel shutdown. Version rolling uses the
conservative 16-bit BIP320 subset within the current specification's general
purpose version space; fixed-version and per-job rolling restrictions take
precedence. It does not perform transaction selection or job declaration.
Coinbase fragments must serialize a stripped transaction for txid hashing.

Build with an installed Cargo toolchain:

```text
python scripts/build_sv2.py --fixtures
python scripts/test_runner.py --require-native --require-sv2
```

Production builds omit the `fixtures` feature. The separate fixture executable
contains a synthetic authority for local tests only. Windows and Linux CI build
both separately and require the encrypted integration tests to execute.

V1 configuration (`config/local.json`, ignored):

```json
{"pool_url":"stratum+ssl://YOUR_POOL:PORT","worker":"YOUR_WORKER","password":"x","backend":"opencl","batch_size":1048576}
```

SV2 configuration:

```json
{"pool_url":"stratum2+tcp://YOUR_POOL:PORT","worker":"YOUR_WORKER","authority_pubkey":"YOUR_32_BYTE_AUTHORITY_HEX","extended":true,"backend":"opencl","batch_size":1048576}
```

Run only after replacing all placeholders with actual pool settings:

```text
python -m nucleus_btc mine --config config/local.json --seconds 60 --output results/live-session-NEW.json
```

Local encrypted standard/extended mock sessions passed, including independently
serialized wire fields, exact CPU hashes, fragmented multichunk ciphertext,
tamper rejection, delayed rejection evidence and fresh reconnect state. These
tests establish local implementation behavior. External pool interoperability,
accepted live shares and BTC accounting remain unverified until actual pool
settings are provided. No J/TH or payout is inferred from mock acknowledgements.
