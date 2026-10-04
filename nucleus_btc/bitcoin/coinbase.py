from struct import pack

def compact_size(n: int) -> bytes:
    if not 0 <= n < 1 << 64:
        raise ValueError("CompactSize out of range")
    if n < 253: return bytes([n])
    if n <= 0xFFFF: return b"\xfd"+pack("<H",n)
    if n <= 0xFFFFFFFF: return b"\xfe"+pack("<I",n)
    return b"\xff"+pack("<Q",n)

def script_number(n: int) -> bytes:
    if n < 0: raise ValueError("Height must be nonnegative")
    if not n: return b""
    result = n.to_bytes((n.bit_length()+7)//8,"little")
    return result + (b"\x00" if result[-1]&0x80 else b"")

def height_push(height: int) -> bytes:
    if not 0 <= height <= 0x7FFFFFFF: raise ValueError("Height out of range")
    if height == 0: return b"\x00"
    if height <= 16: return bytes([0x50+height])
    raw = script_number(height)
    return bytes([len(raw)])+raw

def build_coinbase(height: int, extranonce: bytes, payout_script: bytes, value: int) -> bytes:
    """Non-witness coinbase serialization; not a complete consensus block builder."""
    script = height_push(height)+extranonce
    if not 2 <= len(script) <= 100: raise ValueError("Coinbase scriptSig must be 2..100 bytes")
    if not 0 <= value <= 21_000_000*100_000_000: raise ValueError("Payout out of range")
    return (pack("<I",1)+b"\x01"+bytes(32)+b"\xff"*4+compact_size(len(script))+script+b"\xff"*4+
            b"\x01"+pack("<Q",value)+compact_size(len(payout_script))+payout_script+pack("<I",0))
