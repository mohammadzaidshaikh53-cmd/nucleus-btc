from dataclasses import dataclass,replace
from .block_header import BlockHeader

@dataclass(frozen=True)
class WorkFamily:
    """Headers in an explicitly permitted workspace; not full block validation."""
    header: BlockHeader
    start_nonce: int
    count: int
    version_mask: int = 0
    min_time: int | None = None
    max_time: int | None = None

    def __post_init__(self):
        if not 0 <= self.start_nonce <= 0xFFFFFFFF or not 0 < self.count <= (1 << 32)-self.start_nonce:
            raise ValueError("Nonce family must not wrap or duplicate candidates")
        if not 0 <= self.version_mask <= 0xFFFFFFFF:
            raise ValueError("Version mask must be uint32")
        lo = self.header.timestamp if self.min_time is None else self.min_time
        hi = self.header.timestamp if self.max_time is None else self.max_time
        if not 0 <= lo <= self.header.timestamp <= hi <= 0xFFFFFFFF:
            raise ValueError("Timestamp is outside negotiated bounds")

    def headers(self):
        for n in range(self.start_nonce,self.start_nonce+self.count):
            yield self.header.with_nonce(n).serialize()

    def roll(self, version: int | None = None, timestamp: int | None = None):
        v = self.header.version if version is None else version
        t = self.header.timestamp if timestamp is None else timestamp
        if (v ^ self.header.version) & (~self.version_mask & 0xFFFFFFFF):
            raise ValueError("Version changes exceed negotiated mask")
        lo = self.header.timestamp if self.min_time is None else self.min_time
        hi = self.header.timestamp if self.max_time is None else self.max_time
        if not lo <= t <= hi: raise ValueError("Timestamp outside negotiated bounds")
        return replace(self,header=replace(self.header,version=v,timestamp=t))
