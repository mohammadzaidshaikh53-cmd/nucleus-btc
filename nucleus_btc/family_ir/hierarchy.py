"""Known first-block and message-schedule reuse as a structural baseline."""
from struct import pack,unpack
from time import perf_counter
from ..oracle.sha256 import IV,K,compress,rotr,sha256

def schedule(block):
    w=list(unpack('>16I',block))
    for t in range(16,64):
        x=w[t-15];y=w[t-2]
        w.append((w[t-16]+(rotr(x,7)^rotr(x,18)^(x>>3))+w[t-7]+(rotr(y,17)^rotr(y,19)^(y>>10)))&0xffffffff)
    return tuple(w)

def scheduled_compress(initial,w):
    a,b,c,d,e,f,g,h=initial
    for t in range(64):
        t1=(h+(rotr(e,6)^rotr(e,11)^rotr(e,25))+((e&f)^((~e)&g))+K[t]+w[t])&0xffffffff
        t2=((rotr(a,2)^rotr(a,13)^rotr(a,22))+((a&b)^(a&c)^(b&c)))&0xffffffff
        a,b,c,d,e,f,g,h=(t1+t2)&0xffffffff,a,b,c,(d+t1)&0xffffffff,e,f,g
    return tuple((x+y)&0xffffffff for x,y in zip(initial,(a,b,c,d,e,f,g,h)))

def hierarchy_baseline(family):
    started=perf_counter();headers,construction=family.construct();mids={};schedules={};digests=[]
    for raw in headers:
        if raw[:64] not in mids:mids[raw[:64]]=compress(IV,raw[:64])
        if raw[64:] not in schedules:schedules[raw[64:]]=schedule(raw[64:]+b'\x80'+bytes(39)+pack('>Q',640))
        first=scheduled_compress(mids[raw[:64]],schedules[raw[64:]])
        digests.append(sha256(pack('>8I',*first)))
    total=perf_counter()-started
    if digests!=[family.candidate(i).digest() for i in range(family.count)]:raise AssertionError('Structural baseline parity failed')
    rows=[{'round':t,'unique_W':len({w[t] for w in schedules.values()}),'K':family.count,
           'unique_inner_tails':len(schedules),'invariant_across_version_midstates':True} for t in range(64)]
    return {'status':'known structural baseline','K':family.count,'unique_midstates':len(mids),'unique_second_block_schedules':len(schedules),
            'construction_seconds':construction,'total_seconds':total,'rows':rows,'exact':True,
            'novel_algorithmic_advantage':False,'scope':'known midstate/message-schedule reuse; ASICBoost-class principle, not a new attack'}
