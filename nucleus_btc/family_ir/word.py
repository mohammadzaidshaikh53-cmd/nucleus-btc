from dataclasses import dataclass
from functools import cached_property

MASK = 0xffffffff

@dataclass(frozen=True)
class FamilyWord:
    values: tuple[int, ...]
    carry_residual: tuple = ()

    def __post_init__(self):
        if not self.values or len(self.values) & (len(self.values)-1) or any(not 0 <= v <= MASK for v in self.values):
            raise ValueError("Family word needs 2^n exact uint32 values")
    @property
    def width(self): return len(self.values).bit_length()-1
    @property
    def shared_component(self): return self.values[0]
    @cached_property
    def affine_GF2_component(self):
        return tuple(self.values[1 << b] ^ self.values[0] for b in range(self.width))
    @cached_property
    def nonlinear_residual(self):
        linear = [self.shared_component] * len(self.values)
        for i in range(1, len(linear)):
            low = i & -i; linear[i] = linear[i ^ low] ^ self.affine_GF2_component[low.bit_length()-1]
        return tuple(x ^ y for x, y in zip(self.values, linear))
    @cached_property
    def dependencies(self):
        return tuple(tuple(b for b in range(self.width) if any(((self.values[i] ^ self.values[i ^ (1 << b)]) >> bit) & 1 for i in range(len(self.values)) if not i & (1 << b))) for bit in range(32))
    def materialize(self, candidate_index):
        if not 0 <= candidate_index < len(self.values): raise ValueError("Candidate outside word")
        out = self.shared_component ^ self.nonlinear_residual[candidate_index]
        for b, term in enumerate(self.affine_GF2_component):
            if candidate_index & (1 << b): out ^= term
        return out & MASK
    def anf(self):
        terms = list(self.values)
        for b in range(self.width):
            for i in range(len(terms)):
                if i & (1 << b): terms[i] ^= terms[i ^ (1 << b)]
        return terms
