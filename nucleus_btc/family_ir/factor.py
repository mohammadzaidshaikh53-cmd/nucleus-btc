"""Blocked multioperand carry automata with exact finite-family sharing."""
from .word import FamilyWord, MASK

def blocked_sum(words, block_bits=8):
    if block_bits not in (4, 8, 16): raise ValueError("Carry blocks must be 4, 8 or 16 bits")
    if not words or len({len(w.values) for w in words}) != 1: raise ValueError("Mismatched family words")
    size = len(words[0].values); m = len(words); mask = (1 << block_bits)-1
    outputs = [0] * size; incoming = [0] * size; signatures = [[] for _ in range(size)]
    unique_sums = []; unique_transfers = []; tables = []
    for shift in range(0, 32, block_bits):
        sums = [sum((w.values[i] >> shift) & mask for w in words) for i in range(size)]
        # Each block is a tiny function of carry-in 0..m-1. Identical
        # functions share a table; low output residues still cost work.
        pool = {}; transfer_pool = {}
        for i, value in enumerate(sums):
            if value not in pool:
                pool[value] = tuple(((value+c) & mask, (value+c) >> block_bits) for c in range(m))
            transfer = tuple(x[1] for x in pool[value]); transfer_pool.setdefault(transfer, len(transfer_pool))
            signatures[i].append(transfer_pool[transfer])
            out, incoming[i] = pool[value][incoming[i]]; outputs[i] |= out << shift
        unique_sums.append(len(pool)); unique_transfers.append(len(transfer_pool)); tables.append(len(pool)*m)
    signatures = tuple(tuple(x) for x in signatures)
    return FamilyWord(tuple(x & MASK for x in outputs), signatures), {
        "Ucarry": len(set(signatures)), "Uresidual": len(set(outputs)),
        "block_unique_sums": unique_sums, "block_unique_transfers": unique_transfers,
        "table_entries": sum(tables), "composition_steps": size*(32//block_bits),
        "block_bits": block_bits, "K": size}

def factored_boolean(words, function):
    pool = {}; out = []
    for values in zip(*(w.values for w in words)):
        if values not in pool: pool[values] = function(*values) & MASK
        out.append(pool[values])
    return FamilyWord(tuple(out)), len(pool)
