from decimal import Decimal,localcontext

UINT256_MAX = (1 << 256) - 1
MAINNET_POW_LIMIT = int("00000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffff",16)
DIFFICULTY_ONE = 0xFFFF << (8*(0x1D-3))

def compact_to_target(bits: int, pow_limit: int = UINT256_MAX) -> int:
    if not 0 <= bits <= 0xFFFFFFFF:
        raise ValueError("nBits must be uint32")
    size, word = bits >> 24, bits & 0x007FFFFF
    if size <= 3:
        word >>= 8*(3-size)
        target = word
    else:
        target = word << (8*(size-3))
    negative = word != 0 and bool(bits & 0x00800000)
    overflow = word != 0 and (size > 34 or (word > 0xFF and size > 33) or (word > 0xFFFF and size > 32))
    if negative or overflow or target == 0 or target > pow_limit:
        raise ValueError("Negative, zero, overflowing or out-of-limit target")
    return target

def target_to_compact(target: int) -> int:
    if not 0 < target <= UINT256_MAX:
        raise ValueError("Target must be a positive uint256")
    size = (target.bit_length()+7)//8
    word = target << (8*(3-size)) if size <= 3 else target >> (8*(size-3))
    if word & 0x00800000:
        word >>= 8
        size += 1
    return (size << 24) | (word & 0x007FFFFF)

def meets_target(digest: bytes, target: int) -> bool:
    if len(digest) != 32 or not 0 < target <= UINT256_MAX:
        raise ValueError("Expected a 32-byte digest and positive uint256 target")
    # Bitcoin Core accepts hash <= target, including equality.
    return int.from_bytes(digest, "little") <= target

def difficulty_target(difficulty: str | int | Decimal) -> int:
    d = Decimal(difficulty)
    if not d.is_finite() or d <= 0:
        raise ValueError("Difficulty must be positive and finite")
    if len(d.as_tuple().digits)>4096:raise ValueError("Difficulty precision exceeds input budget")
    # Decimal's default 28 digits would corrupt a full 256-bit target even at difficulty 1.
    # Clamp extreme exponents before converting to an integer to avoid giant allocations.
    with localcontext() as context:
        context.prec=max(100,len(d.as_tuple().digits)+90)
        if d>=Decimal(DIFFICULTY_ONE):return 1
        if d<=Decimal(DIFFICULTY_ONE)/Decimal(UINT256_MAX):return UINT256_MAX
        return min(UINT256_MAX,max(1,int(Decimal(DIFFICULTY_ONE)/d)))
