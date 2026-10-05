"""Exhaustive Boolean truth-table diagnostics, never sampled proof claims."""
from collections import Counter
from math import log2
from .state import evaluate_family

def binary_rank(rows):
    basis = {}
    for value in rows:
        while value:
            pivot = value.bit_length()-1
            if pivot in basis: value ^= basis[pivot]
            else: basis[pivot] = value; break
    return len(basis)

def word_profile(word):
    values=word.values; counts=Counter(values); terms=word.anf()
    degrees=[max((i.bit_count() for i,t in enumerate(terms) if (t>>bit)&1),default=0) for bit in range(32)]
    deps=[sum(1<<v for v in d) for d in word.dependencies]
    residuals=Counter(word.nonlinear_residual)
    carry_divergence=[]
    if word.carry_residual:
        for b in range(word.width):
            pairs=[(i,i^(1<<b)) for i in range(len(values)) if not i&(1<<b)]
            carry_divergence.append(sum(word.carry_residual[a]!=word.carry_residual[c] for a,c in pairs)/len(pairs))
    return {"K":len(values),"unique":len(counts),"sharing_ratio":len(values)/len(counts),
            "entropy_proxy_bits":-sum(n/len(values)*log2(n/len(values)) for n in counts.values()),
            "bit_dependency_masks":deps,"bit_live_variables":[x.bit_count() for x in deps],
            "bit_anf_degree":degrees,"affine":max(degrees)<=1,
            "Nnodes":sum(t.bit_count() for t in terms),"Nresidual":len(residuals),
            "residual_description_bits":32*len(residuals)+len(values)*max(1,(len(residuals)-1).bit_length()),
            "carry_dependency_width":sum(x>0 for x in carry_divergence),"carry_variable_divergence":carry_divergence,
            "unique_counts_exhaustive":True}

def dependency_profile(family, block_bits=8):
    if family.width>8: raise ValueError("Exact per-bit ANF profile limited to 8 variables")
    rows=[]; states={}; carry=[]
    def observe(r,name,word,metric):
        if name in ("W","Sigma0","Sigma1","Ch","Maj","T1","T2",*"abcdefgh"):
            rows.append({"round":r,"word":name,**word_profile(word)})
        if name in "abcdefgh" and len(name)==1:
            states.setdefault(r,{})[name]=word.values
            if name=="h":
                vectors=[sum(states[r][letter][i]<<(32*j) for j,letter in enumerate("abcdefgh")) for i in range(family.count)]
                first=vectors[0]; different=[v^first for v in vectors]
                rows.append({"round":r,"word":"state256","K":family.count,"unique":len(set(vectors)),
                             "binary_affine_rank":binary_rank(different),"sharing_ratio":family.count/len(set(vectors)),
                             "explicit_bits":256*family.count,
                             "unique_table_description_bits":256*len(set(vectors))+family.count*max(1,(len(set(vectors))-1).bit_length()),
                             "unique_counts_exhaustive":True})
                del states[r]
        if name=="T1" and metric: carry.append({"round":r,**metric})
    digests,timing=evaluate_family(family,block_bits,observe)
    expected=[family.candidate(i).digest() for i in range(family.count)]
    if digests!=expected: raise AssertionError("Profile execution differs from hashlib")
    return {"schema":1,"family":family.hierarchy(),"variables":family.variables,
            "rows":rows,"carry":carry,"timing":timing,"exhaustive_full_sha256d_parity":True,
            "node_metric":"exact ANF nonzero bit terms; not expression DAG nodes",
            "rank_metric":"rank of candidate state XOR base; exact finite-family diagnostic"}
