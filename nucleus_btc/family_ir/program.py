from dataclasses import dataclass,replace
from random import Random
from .transition import MODES

@dataclass(frozen=True)
class Stage:
    start:int
    representation:str
    split_variable:int|None=None

@dataclass(frozen=True)
class RepresentationProgram:
    stages:tuple[Stage,...]
    def __post_init__(self):
        if not self.stages or self.stages[0].start!=0 or list(s.start for s in self.stages)!=sorted(set(s.start for s in self.stages)):
            raise ValueError("Program must cover all rounds with strictly ordered stages starting at zero")
        if any(not 0<=s.start<128 or s.representation not in MODES or s.split_variable is not None and not 0<=s.split_variable<24 for s in self.stages):
            raise ValueError("Invalid representation stage")
        if len(self.stages)>16: raise ValueError("Program exceeds bounded stage count")
    def mode_at(self,round_index):
        if not 0<=round_index<128: raise ValueError("Round outside full remaining SHA")
        return next(s.representation for s in reversed(self.stages) if s.start<=round_index)
    def splits_at(self,round_index):
        return tuple(s.split_variable for s in self.stages if s.start==round_index and s.split_variable is not None)
    def mutate(self,seed,width):
        rng=Random(seed);stages=list(self.stages);index=rng.randrange(len(stages));s=stages[index];choice=seed%5
        if choice==0 and index: stages[index]=replace(s,start=rng.randrange(1,128))
        elif choice==1: stages[index]=replace(s,representation=rng.choice(MODES))
        elif choice==2: stages[index]=replace(s,split_variable=rng.randrange(width) if width else None)
        elif choice==3 and len(stages)<16: stages.append(Stage(rng.randrange(1,128),rng.choice(MODES)))
        elif choice==4 and len(stages)>1: stages.pop(max(1,index))
        unique={s.start:s for s in stages};return RepresentationProgram(tuple(unique[k] for k in sorted(unique)))
    def crossover(self,other,cut):
        if not 1<=cut<128: raise ValueError("Crossover cut out of range")
        stages=[s for s in self.stages if s.start<cut]+[Stage(cut,other.mode_at(cut))]+[s for s in other.stages if s.start>cut]
        return RepresentationProgram(tuple(stages[:16]))

def execute_program(family,program,block_bits=8):
    if any(s.split_variable is not None and s.split_variable>=family.width for s in program.stages): raise ValueError("Split variable outside current family")
    from .state import evaluate_family
    return evaluate_family(family,block_bits=block_bits,program=program)
