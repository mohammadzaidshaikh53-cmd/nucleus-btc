"""Exact carry-save identity modulo 2^32; does not bypass SHA's later bit dependencies."""
def carry_save(a,b,c):
    if any(not 0<=x<=0xFFFFFFFF for x in (a,b,c)):raise ValueError("Expected uint32 operands")
    return a^b^c,((a&b)|(a&c)|(b&c))<<1 & 0xFFFFFFFF

def nonlinear_boundary_experiment(samples=256):
    """Refute naive componentwise Ch/Sigma on redundant words; not all possible hybrids."""
    from random import Random
    rng=Random(881);mask=0xffffffff;examples={}
    rotate=lambda x,n:((x>>n)|(x<<(32-n)))&mask
    sigma=lambda x:rotate(x,6)^rotate(x,11)^rotate(x,25)
    for _ in range(samples):
        a,b,c,f,g=[rng.getrandbits(32) for _ in range(5)];s,carry=carry_save(a,b,c);value=(s+carry)&mask
        ch=lambda x:(x&f)^((~x&mask)&g)
        for name,actual,naive in (("Ch",ch(value),(ch(s)+ch(carry))&mask),("Sigma",sigma(value),(sigma(s)+sigma(carry))&mask)):
            if actual!=naive and name not in examples:examples[name]={"sum_word":s,"carry_word":carry,"f":f,"g":g,"resolved_result":actual,"naive_componentwise_result":naive}
    return {"status":"naive_rules_refuted","seed":881,"samples":samples,"counterexamples":examples,
            "scope":"Exact counterexamples to the specified naive rule only; other redundant nonlinear representations remain research frontier"}
