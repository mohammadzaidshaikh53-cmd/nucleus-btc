"""Exact carry-save identity modulo 2^32; does not bypass SHA's later bit dependencies."""
def carry_save(a,b,c):
    if any(not 0<=x<=0xFFFFFFFF for x in (a,b,c)):raise ValueError("Expected uint32 operands")
    return a^b^c,((a&b)|(a&c)|(b&c))<<1 & 0xFFFFFFFF
