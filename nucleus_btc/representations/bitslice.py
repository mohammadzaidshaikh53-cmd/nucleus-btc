"""Exact bit-plane encoding experiment, not a claimed cheaper SHA solver."""
def encode_words(words):
    if not words or any(not 0<=w<=0xFFFFFFFF for w in words):raise ValueError("Expected uint32 words")
    return [sum(((w>>bit)&1)<<i for i,w in enumerate(words)) for bit in range(32)]

def decode_words(planes,count):
    if len(planes)!=32 or count<=0 or any(p<0 or p>>count for p in planes):raise ValueError("Invalid bit planes")
    return [sum(((planes[b]>>i)&1)<<b for b in range(32)) for i in range(count)]

def add_planes(left,right):
    if len(left)!=32 or len(right)!=32:raise ValueError("Expected 32 planes")
    carry=0;out=[]
    for a,b in zip(left,right):
        out.append(a^b^carry);carry=(a&b)|(a&carry)|(b&carry)
    return out
