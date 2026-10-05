"""Causal follow-up: affine residuals conditioned on shared carry signatures."""
from collections import defaultdict
from time import perf_counter
from .state import evaluate_family

def fit_group(indices,values,width):
    basis={}
    for index,value in zip(indices,values):
        x=(index<<1)|1;y=value
        while x:
            pivot=x.bit_length()-1
            if pivot in basis:
                row,target=basis[pivot];x^=row;y^=target
            else:basis[pivot]=(x,y);break
    coefficients=[0]*(width+1)
    for pivot,(row,target) in sorted(basis.items()):
        for bit in range(pivot):
            if row&(1<<bit):target^=coefficients[bit]
        coefficients[pivot]=target
    residual={}
    for index,value in zip(indices,values):
        predicted=coefficients[0]
        for bit in range(width):
            if index&(1<<bit):predicted^=coefficients[bit+1]
        if predicted!=value:residual[index]=predicted^value
    return coefficients,residual

def conditioned_residual_probe(family):
    begun=perf_counter();captured={}
    def observe(r,name,word,metric):
        if name=='T1' and r in (3,4,7,15,31,63,95,127):captured[r]=word
    ds,timing=evaluate_family(family,block_bits=8,observer=observe)
    if ds!=[family.candidate(i).digest() for i in range(family.count)]:raise AssertionError('Conditional cone full-hash audit failed')
    rows=[]
    for r,word in captured.items():
        groups=defaultdict(list)
        for i,signature in enumerate(word.carry_residual):groups[signature].append(i)
        exceptions=0;description=family.count*max(1,(len(groups)-1).bit_length())
        for indices in groups.values():
            coefs,residual=fit_group(indices,[word.values[i] for i in indices],family.width)
            exceptions+=len(residual);description+=32*len(coefs)+(family.width+32)*len(residual)
            # Independent materialization of every restricted affine model.
            for index in indices:
                value=coefs[0]^residual.get(index,0)
                for bit in range(family.width):
                    if index&(1<<bit):value^=coefs[bit+1]
                if value!=word.values[index]:raise AssertionError('Conditional residual reconstruction failed')
        rows.append({'round':r,'groups':len(groups),'nonlinear_exceptions':exceptions,'description_bits':description,
                     'explicit_word_bits':32*family.count,'ratio_to_explicit':description/(32*family.count),
                     'scope':'single T1 word; excludes carry-signature dictionary, hence optimistic description bound'})
    useful=[row for row in rows if row['round']>=7 and row['ratio_to_explicit']<1]
    return {'status':'DEAD' if not useful else 'INCONCLUSIVE','failure_cause':'conditional_description_cost',
            'rows':rows,'total_hunt_and_fit_seconds':perf_counter()-begun,'full_sha256d_audited':True,
            'rho':0,'whole_hash_advantage_demonstrated':False,
            'mechanism':'condition GF2 affine coefficients on carry transfer signatures, then exact XOR exceptions'}
