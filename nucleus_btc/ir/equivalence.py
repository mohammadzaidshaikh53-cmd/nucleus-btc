from hashlib import sha256
from random import Random
from .sha import header_digest
from ..oracle.sha256 import sha256d
from ..bitcoin.block_header import GENESIS

def verify_graph(graph,samples=32,seed=923):
    if not 3<=samples<=4096:raise ValueError("Bounded interpreter sample count")
    rng=Random(seed);headers=[GENESIS.serialize(),bytes(80),bytes([255])*80]+[rng.randbytes(80) for _ in range(samples-3)]
    for h in headers:
        expected=sha256(sha256(h).digest()).digest()
        if header_digest(graph,h)!=expected or sha256d(h)!=expected:raise AssertionError("Generated IR/oracle bit mismatch")
    return {"passed":True,"full_sha256d_headers":samples,"independent_oracle":True,"formal_proof":False}
