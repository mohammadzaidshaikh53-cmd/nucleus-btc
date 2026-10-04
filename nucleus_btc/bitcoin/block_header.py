from dataclasses import dataclass, replace
from hashlib import sha256
from struct import pack, unpack
from .target import compact_to_target, meets_target

@dataclass(frozen=True)
class BlockHeader:
    version: int
    previous_hash: bytes  # Raw 32-byte wire order, not explorer display order.
    merkle_root: bytes
    timestamp: int
    bits: int
    nonce: int

    def __post_init__(self):
        if len(self.previous_hash) != 32 or len(self.merkle_root) != 32:
            raise ValueError("Hashes must each be 32 raw bytes")
        if any(not 0 <= x <= 0xFFFFFFFF for x in (self.version,self.timestamp,self.bits,self.nonce)):
            raise ValueError("Header integer fields must fit uint32")

    def serialize(self) -> bytes:
        return pack("<I",self.version)+self.previous_hash+self.merkle_root+pack("<III",self.timestamp,self.bits,self.nonce)

    @classmethod
    def parse(cls, raw: bytes):
        if len(raw) != 80:
            raise ValueError("Bitcoin block headers are exactly 80 bytes")
        return cls(unpack("<I",raw[:4])[0],raw[4:36],raw[36:68],*unpack("<III",raw[68:]))

    def with_nonce(self, nonce: int):
        return replace(self,nonce=nonce)

    def digest(self) -> bytes:
        return sha256(sha256(self.serialize()).digest()).digest()

    def display_hash(self) -> str:
        return self.digest()[::-1].hex()

    def has_valid_pow(self) -> bool:
        return meets_target(self.digest(),compact_to_target(self.bits))

GENESIS = BlockHeader(1,bytes(32),bytes.fromhex("4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b")[::-1],1231006505,0x1D00FFFF,2083236893)
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
