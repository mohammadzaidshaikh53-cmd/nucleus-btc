from dataclasses import dataclass, replace
from time import perf_counter
from functools import cached_property,lru_cache
from .dimensions import DimensionKind
from ..bitcoin.block_header import BlockHeader
from ..bitcoin.merkle import apply_coinbase_branch

@dataclass(frozen=True)
class HeaderFamily:
    header: BlockHeader
    dimensions: tuple
    min_time: int | None = None
    max_time: int | None = None
    coinbase_prefix: bytes = b""
    coinbase_suffix: bytes = b""
    extranonce: bytes = b""
    merkle_branch: tuple[bytes, ...] = ()

    def __post_init__(self):
        if self.width > 352: raise ValueError("Header workspace exceeds supported dimension count")
        seen = {}
        for d in self.dimensions:
            mask = sum(1 << b for b in d.bits)
            if seen.get(d.kind, 0) & mask: raise ValueError("Overlapping dimensions duplicate candidates")
            seen[d.kind] = seen.get(d.kind, 0) | mask
            if d.kind == DimensionKind.CUSTOM: raise ValueError("Custom header mapping must be supplied by another family type")
            if d.kind == DimensionKind.EXTRANONCE:
                if not self.extranonce or max(d.bits) >= 8 * len(self.extranonce): raise ValueError("Extranonce dimension needs fixed-size template suffix")
                if any(len(x) != 32 for x in self.merkle_branch): raise ValueError("Malformed cached Merkle sibling")
        if DimensionKind.EXTRANONCE in seen and DimensionKind.MERKLE_TAIL in seen:
            raise ValueError("Cannot override a derived Merkle root")
        # Bound all combinations, not just the base timestamp.
        time_mask = seen.get(DimensionKind.NTIME, 0)
        lo = self.header.timestamp & ~time_mask
        hi = lo | time_mask
        if time_mask and (self.min_time is None or self.max_time is None or not self.min_time <= lo <= hi <= self.max_time):
            raise ValueError("Timestamp family exceeds negotiated bounds")

    @property
    def width(self): return sum(d.width for d in self.dimensions)
    @property
    def count(self): return 1 << self.width
    @property
    def variables(self): return tuple((d.kind.value, b) for d in self.dimensions for b in d.bits)

    def candidate(self, index):
        if not 0 <= index < self.count: raise ValueError("Candidate outside family")
        h = self.header; offset = 0; extra = int.from_bytes(self.extranonce, "little")
        for d in self.dimensions:
            change = d.changes((index >> offset) & ((1 << d.width) - 1)); offset += d.width
            if d.kind == DimensionKind.NONCE32: h = replace(h, nonce=h.nonce ^ change)
            elif d.kind == DimensionKind.VERSION_ROLL_BITS: h = replace(h, version=h.version ^ change)
            elif d.kind == DimensionKind.NTIME: h = replace(h, timestamp=h.timestamp ^ change)
            elif d.kind == DimensionKind.MERKLE_TAIL:
                tail = int.from_bytes(h.merkle_root[-4:], "little") ^ change
                h = replace(h, merkle_root=h.merkle_root[:-4] + tail.to_bytes(4, "little"))
            elif d.kind == DimensionKind.EXTRANONCE: extra ^= change
        if any(d.kind == DimensionKind.EXTRANONCE for d in self.dimensions):
            h = replace(h, merkle_root=self._derive_root(extra))
        return h

    @cached_property
    def _derive_root(self):
        @lru_cache(maxsize=256)
        def derive(extra):
            cb=self.coinbase_prefix+extra.to_bytes(len(self.extranonce),'little')+self.coinbase_suffix
            if len(cb)>=6 and cb[4:6]==b'\x00\x01':raise ValueError('Witness coinbase requires txid stripping')
            return apply_coinbase_branch(cb,list(self.merkle_branch))
        return derive

    def construct(self):
        if self.count > 1<<20: raise ValueError("Materialization budget exceeded; split the conceptual workspace first")
        t = perf_counter(); headers = [self.candidate(i).serialize() for i in range(self.count)]
        if len(set(headers))!=len(headers): raise ValueError("Derived header alias detected; explicit duplicate accounting required")
        return headers, perf_counter() - t

    def hierarchy(self):
        return {"outer_variables": [v for d in self.dimensions if d.affects_first_block for v in [(d.kind.value, b) for b in d.bits]],
                "inner_variables": [v for d in self.dimensions if not d.affects_first_block for v in [(d.kind.value, b) for b in d.bits]],
                "protocol_sources": [d.protocol_source for d in self.dimensions],
                "bitcoin_validity": "permitted header workspace; pool template/consensus validity is external",
                "merkle_tail_is_diagnostic": any(d.kind == DimensionKind.MERKLE_TAIL for d in self.dimensions)}
