"""Exact full SHA256d family evaluator. Trace callbacks never affect execution."""
from struct import pack, unpack
from time import perf_counter
from .word import FamilyWord, MASK
from .factor import blocked_sum, factored_boolean
from ..oracle.sha256 import IV, K, compress, rotr

def evaluate_family(family, block_bits=8, observer=None, program=None, prefix_target=None,boolean_forms=None):
    forms=boolean_forms or {'Ch':'canonical','Maj':'canonical'}
    if forms.get('Ch','canonical') not in ('canonical','select') or forms.get('Maj','canonical') not in ('canonical','factored'):raise ValueError('Unvalidated Boolean form')
    started = perf_counter(); headers, construction = family.construct(); size = family.count
    cache = {}; midstates = []
    for h in headers:
        prefix = h[:64]
        if prefix not in cache: cache[prefix] = compress(IV, prefix)
        midstates.append(cache[prefix])
    prep = perf_counter()-started-construction
    state = [FamilyWord(tuple(s[j] for s in midstates)) for j in range(8)]
    blocks = [h[64:]+b"\x80"+bytes(39)+pack(">Q",640) for h in headers]
    carry_metrics = []; transition_seconds = 0.; modes = {}; compute_start = perf_counter()
    active_mode = "carry-residual"; partitions = [tuple(range(size))]; split_events=[]
    def emit(round_index, name, word, carry=None):
        if observer: observer(round_index, name, word, carry)
    def boolean(words, fn):
        if active_mode == "native": return FamilyWord(tuple(fn(*v)&MASK for v in zip(*(w.values for w in words))))
        if active_mode == "bitplane":
            from .lower import bitplane_boolean
            return bitplane_boolean(words, fn)
        return factored_boolean(words, fn)[0]
    def add(words, round_index, name):
        if active_mode == "native": result = FamilyWord(tuple(sum(v)&MASK for v in zip(*(w.values for w in words)))); metric = None
        elif active_mode == "bitplane":
            from .lower import bitplane_add
            result = bitplane_add(words); metric = None
        else:
            if len(partitions)==1: result, metric = blocked_sum(words, block_bits)
            else:
                merged=[0]*size;metrics=[]
                for indices in partitions:
                    part,m=blocked_sum(tuple(FamilyWord(tuple(w.values[i] for i in indices)) for w in words),block_bits)
                    for i,v in zip(indices,part.values): merged[i]=v
                    metrics.append(m)
                result=FamilyWord(tuple(merged));metric={"Ucarry":sum(m['Ucarry'] for m in metrics),"Uresidual":sum(m['Uresidual'] for m in metrics),"K":size,"block_bits":block_bits,"children":len(partitions)}
            if name == "T1": carry_metrics.append({"round": round_index, **metric})
        emit(round_index, name, result, metric); return result
    for compression in range(2):
        initial = state; a,b,c,d,e,f,g,h = state
        w = [FamilyWord(tuple(unpack(">16I", block)[j] for block in blocks)) for j in range(16)]
        for t in range(64):
            r = compression*64+t
            if program:
                for variable in program.splits_at(r):
                    ts=perf_counter();partitions=[tuple(i for i in group if ((i>>variable)&1)==value) for group in partitions for value in (0,1)]
                    partitions=[g for g in partitions if g]
                    transition_seconds+=perf_counter()-ts;split_events.append({"round":r,"variable":variable,"children":len(partitions),"covered":sum(map(len,partitions))})
                desired = program.mode_at(r)
                if desired != active_mode:
                    from .transition import convert
                    ts = perf_counter(); a,b,c,d,e,f,g,h = [convert(x, desired) for x in (a,b,c,d,e,f,g,h)]
                    transition_seconds += perf_counter()-ts; active_mode = desired
            modes[active_mode] = modes.get(active_mode, 0)+1
            if t >= 16:
                x = boolean((w[t-15],), lambda x: rotr(x,7)^rotr(x,18)^(x>>3))
                y = boolean((w[t-2],), lambda x: rotr(x,17)^rotr(x,19)^(x>>10))
                w.append(add((w[t-16],x,w[t-7],y),r,"schedule_add"))
            emit(r,"W",w[t])
            s1 = boolean((e,),lambda x: rotr(x,6)^rotr(x,11)^rotr(x,25)); emit(r,"Sigma1",s1)
            ch = boolean((e,f,g),(lambda x,y,z:z^(x&(y^z))) if forms.get('Ch')=='select' else (lambda x,y,z:(x&y)^((~x)&z))); emit(r,"Ch",ch)
            t1 = add((h,s1,ch,FamilyWord((K[t],)*size),w[t]),r,"T1")
            s0 = boolean((a,),lambda x: rotr(x,2)^rotr(x,13)^rotr(x,22)); emit(r,"Sigma0",s0)
            maj = boolean((a,b,c),(lambda x,y,z:(x&y)|(z&(x|y))) if forms.get('Maj')=='factored' else (lambda x,y,z:(x&y)^(x&z)^(y&z))); emit(r,"Maj",maj)
            t2 = add((s0,maj),r,"T2")
            a,b,c,d,e,f,g,h = add((t1,t2),r,"a_add"),a,b,c,add((d,t1),r,"e_add"),e,f,g
            for name, word in zip("abcdefgh",(a,b,c,d,e,f,g,h)): emit(r,name,word)
            if r==124 and prefix_target is not None:
                if not 0<prefix_target<1<<256: raise ValueError("Invalid prefix target")
                # After round index 60 of the second compression, e becomes
                # f,g,h during the last three shifts. Thus final H7 is known.
                high=[int.from_bytes(pack('>I',(IV[7]+x)&MASK),'little') for x in e.values]
                bound=prefix_target>>224
                rejected=[i for i,x in enumerate(high) if x>bound]
                if len(rejected)==size:
                    return None,{"K":size,"status":"exact_prefix_rejected","exact_full_sha256d":False,
                                 "rejection_proof":"H7=IV7+e_after_second_round60; bswap32(H7)>target>>224",
                                 "known_high_words":high,"rejected":rejected,"rho":1.,
                                 "construction_seconds":construction,"midstate_seconds":prep,
                                 "compute_seconds":perf_counter()-compute_start,"transition_seconds":transition_seconds,
                                 "total_seconds":perf_counter()-started,"saved_compression_rounds":3*size,
                                 "saved_feedforward_additions_net":7*size}
        state = [add((x,y),compression*64+63,"feedforward") for x,y in zip(initial,(a,b,c,d,e,f,g,h))]
        if compression == 0:
            blocks = [pack(">8I",*(x.values[i] for x in state))+b"\x80"+bytes(23)+pack(">Q",256) for i in range(size)]
            state = [FamilyWord((x,)*size) for x in IV]
    digests = [pack(">8I",*(x.values[i] for x in state)) for i in range(size)]
    compute = perf_counter()-compute_start
    return digests, {"K":size,"construction_seconds":construction,"midstate_seconds":prep,
                     "compute_seconds":compute,"transition_seconds":transition_seconds,
                     "total_seconds":perf_counter()-started,"unique_midstates":len(cache),
                     "carry":carry_metrics,"representation_rounds":modes,"split_events":split_events,"exact_full_sha256d":True}
