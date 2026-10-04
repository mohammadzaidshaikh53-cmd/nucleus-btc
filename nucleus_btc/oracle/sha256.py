"""Independent FIPS 180-4 SHA-256; no hashlib in this reference module."""
from struct import pack, unpack

MASK = 0xFFFFFFFF
IV = (0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
      0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19)
K = (
    0x428A2F98,0x71374491,0xB5C0FBCF,0xE9B5DBA5,0x3956C25B,0x59F111F1,0x923F82A4,0xAB1C5ED5,
    0xD807AA98,0x12835B01,0x243185BE,0x550C7DC3,0x72BE5D74,0x80DEB1FE,0x9BDC06A7,0xC19BF174,
    0xE49B69C1,0xEFBE4786,0x0FC19DC6,0x240CA1CC,0x2DE92C6F,0x4A7484AA,0x5CB0A9DC,0x76F988DA,
    0x983E5152,0xA831C66D,0xB00327C8,0xBF597FC7,0xC6E00BF3,0xD5A79147,0x06CA6351,0x14292967,
    0x27B70A85,0x2E1B2138,0x4D2C6DFC,0x53380D13,0x650A7354,0x766A0ABB,0x81C2C92E,0x92722C85,
    0xA2BFE8A1,0xA81A664B,0xC24B8B70,0xC76C51A3,0xD192E819,0xD6990624,0xF40E3585,0x106AA070,
    0x19A4C116,0x1E376C08,0x2748774C,0x34B0BCB5,0x391C0CB3,0x4ED8AA4A,0x5B9CCA4F,0x682E6FF3,
    0x748F82EE,0x78A5636F,0x84C87814,0x8CC70208,0x90BEFFFA,0xA4506CEB,0xBEF9A3F7,0xC67178F2)

def rotr(x: int, n: int) -> int:
    return ((x >> n) | (x << (32-n))) & MASK

def compress(state: tuple[int, ...], block: bytes) -> tuple[int, ...]:
    if len(state) != 8 or len(block) != 64:
        raise ValueError("SHA compression needs eight words and a 64-byte block")
    w = list(unpack(">16I", block))
    for i in range(16, 64):
        s0 = rotr(w[i-15],7) ^ rotr(w[i-15],18) ^ (w[i-15] >> 3)
        s1 = rotr(w[i-2],17) ^ rotr(w[i-2],19) ^ (w[i-2] >> 10)
        w.append((w[i-16] + s0 + w[i-7] + s1) & MASK)
    a,b,c,d,e,f,g,h = state
    for i in range(64):
        s1 = rotr(e,6) ^ rotr(e,11) ^ rotr(e,25)
        ch = (e & f) ^ ((~e) & g)
        t1 = (h + s1 + ch + K[i] + w[i]) & MASK
        s0 = rotr(a,2) ^ rotr(a,13) ^ rotr(a,22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (s0 + maj) & MASK
        a,b,c,d,e,f,g,h = (t1+t2)&MASK,a,b,c,(d+t1)&MASK,e,f,g
    return tuple((x+y)&MASK for x,y in zip(state,(a,b,c,d,e,f,g,h)))

def sha256(data: bytes) -> bytes:
    if len(data) >= 1 << 61:
        raise ValueError("SHA-256 input exceeds its encoded bit length")
    padded = data + b"\x80" + b"\x00" * ((55-len(data)) % 64) + pack(">Q", len(data)*8)
    state = IV
    for pos in range(0, len(padded), 64):
        state = compress(state, padded[pos:pos+64])
    return pack(">8I", *state)

def sha256d(data: bytes) -> bytes:
    return sha256(sha256(data))

def header_midstate(header: bytes) -> tuple[int, ...]:
    if len(header) != 80:
        raise ValueError("Bitcoin headers are exactly 80 bytes")
    return compress(IV, header[:64])

def finish_header(midstate: tuple[int, ...], tail: bytes) -> bytes:
    if len(tail) != 16:
        raise ValueError("Header tail must be 16 bytes")
    first = pack(">8I", *compress(midstate, tail+b"\x80"+b"\x00"*39+pack(">Q",640)))
    return sha256(first)
