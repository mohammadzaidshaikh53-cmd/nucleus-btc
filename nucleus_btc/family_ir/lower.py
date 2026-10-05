"""Exact finite bit-plane lowering; conversions are charged by the caller."""
from .word import FamilyWord
from ..representations.bitslice import encode_words,decode_words,add_planes

class PlaneWord:
    def __init__(self,planes,count): self.planes=planes;self.count=count
    def __and__(self,other):
        if isinstance(other,int): return PlaneWord([p if (other>>i)&1 else 0 for i,p in enumerate(self.planes)],self.count)
        return PlaneWord([a&b for a,b in zip(self.planes,other.planes)],self.count)
    def __xor__(self,other): return PlaneWord([a^b for a,b in zip(self.planes,other.planes)],self.count)
    def __or__(self,other): return PlaneWord([a|b for a,b in zip(self.planes,other.planes)],self.count)
    def __invert__(self): return PlaneWord([p^((1<<self.count)-1) for p in self.planes],self.count)
    def __rshift__(self,n): return PlaneWord(self.planes[n:]+[0]*n,self.count)
    def __lshift__(self,n): return PlaneWord([0]*n+self.planes[:32-n],self.count)
    def materialize(self): return FamilyWord(tuple(decode_words(self.planes,self.count)))

def bitplane_boolean(words,function):
    converted=[PlaneWord(encode_words(w.values),len(w.values)) for w in words]
    return function(*converted).materialize()

def bitplane_add(words):
    count=len(words[0].values);planes=encode_words(words[0].values)
    for word in words[1:]: planes=add_planes(planes,encode_words(word.values))
    return FamilyWord(tuple(decode_words(planes,count)))
