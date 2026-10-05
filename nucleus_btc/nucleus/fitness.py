"""Exactness is a prerequisite; multi-objective measurements are never blended."""
from dataclasses import dataclass,asdict
from math import log10

@dataclass(frozen=True)
class Fitness:
    correctness_passed:bool
    H:float|None=None
    E:float|None=None
    alpha:float|None=None
    Rc:int|None=None
    rho:float|None=None
    F:float|None=None
    phi:float=1.
    M:int|None=None
    K:int|None=None
    def measurements(self):
        if self.correctness_passed is not True:raise ValueError("Bit-exact validation is a hard fitness gate")
        if self.rho is not None and not 0<=self.rho<=1 or self.F is not None and self.F<0 or not 0<=self.phi<=1:raise ValueError("Invalid economic fitness")
        cost=self.F+(1-self.rho)*self.phi if self.F is not None and self.rho is not None else None
        return {**asdict(self),"Q":-log10(1-self.rho) if self.rho is not None and self.rho<1 else None,
                "S":1/cost if cost is not None and cost>0 else None,
                "Q_scope":"finite measured family only; all-rejected Q is undefined here","energy_scope":"measured only; null when unavailable"}
