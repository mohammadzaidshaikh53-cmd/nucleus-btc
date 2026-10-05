from dataclasses import dataclass,asdict

@dataclass(frozen=True)
class Hypothesis:
    mechanism:str
    preconditions:str
    expected_effect:str
    falsification_test:str
    cost_budget_seconds:float
    success_threshold:str
    kill_threshold:str
    def to_dict(self): return asdict(self)

def counterfactual(cause):
    if cause=="residual_saturation":
        return Hypothesis("influence-guided interior split before carry divergence","exact permitted finite family",
                          "reduce residual variety per child","include split and duplicated computation costs",90,
                          "total cost beats ordinary hashing on fresh fixtures","children preserve linear residual cost")
    if cause=="carry_saturation":
        return Hypothesis("reduced-round differential neutral-bit probe","protocol-permitted dimensions only",
                          "find relations persisting beyond early carry divergence","full SHA256d and hunt-amortization audit",90,
                          "positive full-round amortization","relation disappears or hunt cost exceeds saving")
    return Hypothesis("bounded backward cut projection","exact target necessary condition",
                      "prove a family target rejection without hashing every member","independently verify every UNSAT projection",60,
                      "proof cost below eliminated hashing","UNKNOWN or proof cost exceeds native scan")
