from hashlib import sha256

def sha256d(data: bytes) -> bytes:
    return sha256(sha256(data).digest()).digest()

def merkle_root(leaves: list[bytes]) -> tuple[bytes,bool]:
    """Raw txid bytes; also returns Core-style duplicate-sibling mutation flag."""
    if not leaves:
        return bytes(32),False
    if any(len(x) != 32 for x in leaves):
        raise ValueError("Merkle leaves must be raw 32-byte hashes")
    level,mutated = list(leaves),False
    while len(level) > 1:
        mutated |= any(level[i] == level[i+1] for i in range(0,len(level)-1,2))
        if len(level) % 2:
            level.append(level[-1])
        level = [sha256d(level[i]+level[i+1]) for i in range(0,len(level),2)]
    return level[0],mutated

def apply_coinbase_branch(coinbase: bytes, branch: list[bytes]) -> bytes:
    root = sha256d(coinbase)
    for sibling in branch:
        if len(sibling) != 32:
            raise ValueError("Merkle siblings must be 32 raw bytes")
        root = sha256d(root+sibling)
    return root
