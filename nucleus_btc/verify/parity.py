from hashlib import sha256
from random import Random
from ..oracle.sha256 import sha256d
from ..bitcoin.block_header import GENESIS
from ..bitcoin.target import UINT256_MAX,meets_target,compact_to_target

def verify_backend(backend,samples=1024,seed=8237):
    if not 16<=samples<=1<<20:raise ValueError("Parity sample count must be 16..2^20")
    rng=Random(seed);headers=[GENESIS.serialize(),bytes(80),bytes([255])*80]+[rng.randbytes(80) for _ in range(samples-3)]
    expected=[sha256(sha256(h).digest()).digest() for h in headers]
    actual=backend.hash_headers(headers)
    if len(actual)!=len(expected) or actual!=expected:raise AssertionError("Backend digest mismatch")
    # Reference implementation is independent of hashlib and accelerated cores.
    for h,digest in zip(headers[:16],actual[:16]):
        if sha256d(h)!=digest:raise AssertionError("Independent oracle mismatch")
    scan_cases=0
    if hasattr(backend,"scan"):
        for start in [0,0xFFFFFF80,GENESIS.nonce-64]:
            count=128;h=GENESIS.serialize();headers=[h[:76]+n.to_bytes(4,"little") for n in range(start,start+count)]
            hashes=[sha256(sha256(x).digest()).digest() for x in headers]
            if backend.hash_nonces(h,start,count)!=hashes:raise AssertionError("Nonce family mismatch")
            for target in [1,compact_to_target(GENESIS.bits),UINT256_MAX//4,UINT256_MAX]:
                expected_n=[start+i for i,d in enumerate(hashes) if meets_target(d,target)]
                actual_n=backend.scan(h,start,count,target,capacity=count).nonces
                if sorted(actual_n)!=expected_n:raise AssertionError("Scan lost or invented a solution")
                scan_cases+=1
        # Vary the complete header, including the job-dependent midstate and tail.
        for h in headers_for_jobs(rng,8):
            count=65;start=rng.randrange(0,(1<<32)-count)
            family=[h[:76]+n.to_bytes(4,"little") for n in range(start,start+count)]
            hashes=[sha256(sha256(x).digest()).digest() for x in family]
            if backend.hash_nonces(h,start,count)!=hashes:raise AssertionError("Changed-job midstate mismatch")
            target=max(1,int.from_bytes(hashes[32],"little"))
            expected_n=[start+i for i,d in enumerate(hashes) if meets_target(d,target)]
            if sorted(backend.scan(h,start,count,target,capacity=count).nonces)!=expected_n:raise AssertionError("Changed-job target/equality scan mismatch")
            scan_cases+=1
    return {"headers_tested":samples,"independent_reference_headers":16,"scan_cases":scan_cases,"passed":True,"proof_of_universal_equivalence":False}

def headers_for_jobs(rng,count):
    return [rng.randbytes(80) for _ in range(count)]
