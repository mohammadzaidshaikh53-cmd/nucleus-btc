from dataclasses import dataclass
from hashlib import sha256
from time import perf_counter
from ..bitcoin.block_header import BlockHeader
from ..bitcoin.target import meets_target,UINT256_MAX

MAX_BATCH = 1 << 24

class BackendUnavailable(RuntimeError): pass
class ResultOverflow(RuntimeError): pass

def validate_range(header: bytes,start: int,count: int):
    if len(header) != 80 or not 0 <= start <= 0xFFFFFFFF or not 0 < count <= min(MAX_BATCH,(1<<32)-start):
        raise ValueError("Expected 80-byte header and non-wrapping nonce range of 1..2^24")

@dataclass
class ScanResult:
    nonces: list[int]
    examined: int
    wall_seconds: float
    kernel_seconds: float | None = None

class HashlibBackend:
    name = "hashlib"
    def hash_headers(self,headers: list[bytes]) -> list[bytes]:
        if not headers or len(headers)>MAX_BATCH or any(len(h)!=80 for h in headers):
            raise ValueError("Expected a nonempty bounded batch of 80-byte headers")
        return [sha256(sha256(h).digest()).digest() for h in headers]
    def hash_nonces(self,header: bytes,start: int,count: int) -> list[bytes]:
        validate_range(header,start,count)
        return self.hash_headers([header[:76]+n.to_bytes(4,"little") for n in range(start,start+count)])
    def scan(self,header: bytes,start: int,count: int,target: int,capacity: int=4096) -> ScanResult:
        validate_range(header,start,count)
        if not 0 < target <= UINT256_MAX or capacity <= 0: raise ValueError("Invalid target/capacity")
        begun=perf_counter();found=[]
        for n in range(start,start+count):
            raw=header[:76]+n.to_bytes(4,"little")
            if meets_target(sha256(sha256(raw).digest()).digest(),target):
                found.append(n)
                if len(found)>capacity: raise ResultOverflow("Too many solutions; retry a smaller batch")
        return ScanResult(found,count,perf_counter()-begun)
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

def get_backend(name: str, **kwargs):
    if name == "hashlib": return HashlibBackend()
    if name in ("native","native-full"):
        from .native import NativeBackend
        return NativeBackend(reuse=name=="native")
    if name == "hip":
        from .hip import HIPBackend
        return HIPBackend()
    if name == "opencl":
        from .opencl import OpenCLBackend
        return OpenCLBackend(**kwargs)
    raise ValueError(f"Unknown backend: {name}")
