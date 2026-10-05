"""Exact template rewrites and deterministic diverse mutation/crossover.

Algebraic identities hold independently on each bit or modulo 2^32. Tests are
finite evidence; this module does not pretend empirical tests are formal proofs.
"""
from dataclasses import dataclass,asdict
from random import Random

@dataclass(frozen=True)
class Rewrite:
    id:str
    preconditions:str
    semantics:str
    backends:tuple[str,...]=("interpreter","opencl","cpp")

LIBRARY=[Rewrite("ch-xor","uint32 words","(x&y)^(~x&z) == z^(x&(y^z))"),
         Rewrite("ch-mux","uint32 bit mask; not Boolean scalar","Ch(x,y,z) == bitselect(z,y,x)"),
         Rewrite("maj-or","uint32 words","xy ^ xz ^ yz == xy | z(x|y)"),
         Rewrite("maj-xor","uint32 words","Maj(x,y,z) == xy ^ z(x^y)"),
         Rewrite("add-reassociate","uint32 modular arithmetic only","Associativity modulo 2^32"),
         Rewrite("carry-save","uint32 operands; final carry resolved","a+b+c == (a^b^c)+((ab|ac|bc)<<1) mod 2^32"),
         Rewrite("stream-schedule","topological dependencies preserved","Compute message word immediately before its round"),
         Rewrite("constant-cse-dead","same uint32 semantics","Fold constants, structural hash, omit unreachable nodes"),
         Rewrite("rotate-compose","rotation counts modulo 32","ROTR(ROTR(x,a),b)=ROTR(x,(a+b)%32)")]

SPECIES=("scalar","mux","mixed","carry-save","balanced","scheduled","crossover","register-aware")

def genome(index,seed=20261005,parents=None):
    if index<0:raise ValueError("Nonnegative candidate index required")
    rng=Random(seed+index);species=SPECIES[index%len(SPECIES)]
    # Different per-round programs, not merely a fixed list of compiler flags.
    ch=[1]*64;maj=[1]*64
    if species=="mux":ch=[2]*64
    elif species in ("mixed","crossover"):
        ch=[rng.randrange(3) for _ in range(64)];maj=[rng.randrange(3) for _ in range(64)]
    elif species=="scalar":ch=[0]*64;maj=[0]*64
    if parents:
        cut=rng.randrange(1,64);ch=parents[0]["ch"][:cut]+parents[-1]["ch"][cut:]
        maj=parents[-1]["maj"][:cut]+parents[0]["maj"][cut:]
        for _ in range(4):ch[rng.randrange(64)]=rng.randrange(3)
    elif index>=len(SPECIES):
        for _ in range(4):
            ch[rng.randrange(64)]=rng.randrange(3);maj[rng.randrange(64)]=rng.randrange(3)
    return {"ch":ch,"maj":maj,"addition":"carry-save" if species=="carry-save" else "balanced" if species=="balanced" else "chain" if species=="register-aware" else "nary",
            "schedule":"precompute" if species=="scheduled" else "stream"}

def catalog():return [asdict(r) for r in LIBRARY]
