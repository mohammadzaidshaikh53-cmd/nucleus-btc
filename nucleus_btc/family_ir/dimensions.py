from dataclasses import dataclass
from enum import Enum

class DimensionKind(str, Enum):
    NONCE32 = "nonce"
    VERSION_ROLL_BITS = "version"
    NTIME = "ntime"
    MERKLE_TAIL = "merkle_tail"
    EXTRANONCE = "extranonce"
    CUSTOM = "custom"

@dataclass(frozen=True)
class Dimension:
    kind: DimensionKind
    bits: tuple[int, ...]
    permitted_mask: int
    protocol_source: str = "local diagnostic fixture"
    standard_allowed: bool = False
    extended_allowed: bool = False

    def __post_init__(self):
        object.__setattr__(self, "kind", DimensionKind(self.kind))
        if not self.bits or len(set(self.bits)) != len(self.bits):
            raise ValueError("Dimension bits must be distinct and nonempty")
        limit = 256 if self.kind == DimensionKind.EXTRANONCE else 32
        if any(not 0 <= b < limit for b in self.bits):
            raise ValueError("Dimension bit outside field")
        mask = sum(1 << b for b in self.bits)
        if self.permitted_mask < 0 or mask & ~self.permitted_mask:
            raise ValueError("Changes exceed explicitly permitted mask")
        if self.kind in (DimensionKind.MERKLE_TAIL, DimensionKind.CUSTOM) and (self.standard_allowed or self.extended_allowed):
            raise ValueError("Arbitrary Merkle/custom changes are diagnostic only")

    @property
    def width(self): return len(self.bits)
    @property
    def affects_first_block(self):
        return self.kind in (DimensionKind.VERSION_ROLL_BITS, DimensionKind.EXTRANONCE, DimensionKind.CUSTOM)
    @property
    def affects_second_block(self): return self.kind != DimensionKind.VERSION_ROLL_BITS
    @property
    def affects_coinbase_merkle(self): return self.kind == DimensionKind.EXTRANONCE

    def changes(self, assignment):
        if not 0 <= assignment < 1 << self.width: raise ValueError("Dimension assignment out of range")
        return sum(((assignment >> i) & 1) << bit for i, bit in enumerate(self.bits))
