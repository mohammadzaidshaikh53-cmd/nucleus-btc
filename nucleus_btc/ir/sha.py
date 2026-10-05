"""Full SHA-256 compression generated from exact uint32 primitives."""
from struct import unpack,pack
from .graph import Graph
from ..oracle.sha256 import K,IV

def compression_graph(spec=None):
    spec=spec or {};ch_forms=spec.get("ch",[0]*64);maj_forms=spec.get("maj",[0]*64)
    addition=spec.get("addition","nary");schedule=spec.get("schedule","stream")
    if len(ch_forms)!=64 or len(maj_forms)!=64 or any(x not in (0,1,2) for x in ch_forms+maj_forms):raise ValueError("Invalid Boolean genome")
    if addition not in ("nary","chain","balanced","carry-save") or schedule not in ("stream","precompute"):raise ValueError("Invalid SHA genome")
    g=Graph();state=[g.input(f"s{i}") for i in range(8)];w=[g.input(f"w{i}") for i in range(16)]
    bx=lambda a,b:g.node("XOR",a,b)
    band=lambda a,b:g.node("AND",a,b)
    inv=lambda a:g.node("NOT",a)
    rr=lambda a,n:g.node("ROTR",a,value=n)
    x3=lambda a,b,c:bx(bx(a,b),c)
    def add(*words):
        words=list(words)
        if addition=="carry-save":
            while len(words)>2:
                a,b,c=words[:3];majority=g.node("OR",band(a,b),band(c,g.node("OR",a,b)))
                words=[x3(a,b,c),g.node("SHL",majority,value=1)]+words[3:]
        if addition=="nary" or len(words)==2:return g.node("ADD32",*words)
        if addition=="balanced":
            while len(words)>1:words=[g.node("ADD32",*words[i:i+2]) if len(words[i:i+2])==2 else words[i] for i in range(0,len(words),2)]
            return words[0]
        value=words[0]
        for operand in words[1:]:value=g.node("ADD32",value,operand)
        return value
    def expand(i):
        x,y=w[i-15],w[i-2]
        w.append(add(w[i-16],x3(rr(x,7),rr(x,18),g.node("SHR",x,value=3)),w[i-7],x3(rr(y,17),rr(y,19),g.node("SHR",y,value=10))))
    if schedule=="precompute":
        for i in range(16,64):expand(i)
    a,b,c,d,e,f,hg,h=state
    for i in range(64):
        if i>=16 and schedule=="stream":expand(i)
        ch=(bx(band(e,f),band(inv(e),hg)) if ch_forms[i]==0 else
            bx(hg,band(e,bx(f,hg))) if ch_forms[i]==1 else g.node("MUX",e,f,hg))
        maj=(x3(band(a,b),band(a,c),band(b,c)) if maj_forms[i]==0 else
             g.node("OR",band(a,b),band(c,g.node("OR",a,b))) if maj_forms[i]==1 else bx(band(a,b),band(c,bx(a,b))))
        t1=add(h,x3(rr(e,6),rr(e,11),rr(e,25)),ch,g.const(K[i]),w[i])
        t2=add(x3(rr(a,2),rr(a,13),rr(a,22)),maj)
        a,b,c,d,e,f,hg,h=add(t1,t2),a,b,c,add(d,t1),e,f,hg
    g.outputs=[add(old,new) for old,new in zip(state,(a,b,c,d,e,f,hg,h))]
    g.validate();return g

def compress(graph,state,block):
    if len(state)!=8 or len(block)!=64:raise ValueError("Invalid compression inputs")
    words=unpack(">16I",block)
    return graph.evaluate({**{f"s{i}":x for i,x in enumerate(state)},**{f"w{i}":x for i,x in enumerate(words)}})

def header_digest(graph,header):
    if len(header)!=80:raise ValueError("Bitcoin header must be 80 bytes")
    first=compress(graph,IV,header[:64])
    first=compress(graph,first,header[64:]+b"\x80"+bytes(39)+pack(">Q",640))
    second=compress(graph,IV,pack(">8I",*first)+b"\x80"+bytes(23)+pack(">Q",256))
    return pack(">8I",*second)
