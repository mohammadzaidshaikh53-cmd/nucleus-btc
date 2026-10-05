"""Optional exact bit-vector SHA and universal rewrite checks with bounded Z3."""
from time import perf_counter
from struct import unpack
from ..oracle.sha256 import IV,header_midstate,sha256d
from ..bitcoin.target import meets_target
from ..ir.sha import compression_graph

def lower(graph,inputs,z3):
    values=[]
    for node in graph.nodes:
        a=[values[i] for i in node.args];op=node.op
        if op=="INPUT":value=inputs[node.value]
        elif op=="CONST32":value=z3.BitVecVal(node.value,32)
        elif op=="XOR":value=a[0]^a[1]
        elif op=="AND":value=a[0]&a[1]
        elif op=="OR":value=a[0]|a[1]
        elif op=="NOT":value=~a[0]
        elif op=="ROTR":value=z3.RotateRight(a[0],node.value)
        elif op=="SHR":value=z3.LShR(a[0],node.value)
        elif op=="SHL":value=a[0]<<node.value
        elif op=="MUX":value=(a[0]&a[1])|(~a[0]&a[2])
        elif op=="ADD32":
            value=a[0]
            for operand in a[1:]:value=value+operand
        else:raise ValueError("Unsupported SMT word operation")
        values.append(value)
    return [values[i] for i in graph.outputs]

def prove_templates(timeout_ms=2000):
    import z3
    a,b,c=z3.BitVecs("a b c",32);majority=(a&b)|((a|b)&c)
    equations={"Ch":((a&b)|(~a&c),c^(a&(b^c))),"Maj":((a&b)^(a&c)^(b&c),majority),
               "carry-save":(a+b+c,(a^b^c)+(majority<<1)),"rotate-compose":(z3.RotateRight(z3.RotateRight(a,7),18),z3.RotateRight(a,25)),
               "uint32-reassociate":((a+b)+c,a+(b+c))}
    results={}
    for name,(left,right) in equations.items():
        solver=z3.Solver();solver.set(timeout=timeout_ms);solver.add(left!=right);t=perf_counter();answer=solver.check()
        results[name]={"status":str(answer).upper(),"seconds":perf_counter()-t,"universal_uint32_equivalence_proved":answer==z3.unsat}
    return {"solver":z3.get_version_string(),"templates":results,"all_proved":all(r["universal_uint32_equivalence_proved"] for r in results.values())}

def smt_family(header,start=0,nonce_bits=4,target=1,timeout_ms=250):
    try:import z3
    except ImportError:return {"status":"dependency_absent","reason":"Install nucleus-btc[research] for bounded SMT; no family rejected","family_discarded":False}
    if len(header)!=80 or not 1<=nonce_bits<=20 or start%(1<<nonce_bits) or not 0<=start<1<<32 or start+(1<<nonce_bits)>1<<32 or not 0<target<1<<256 or not 1<=timeout_ms<=10000:raise ValueError("Invalid finite SMT family")
    begun=perf_counter();graph=compression_graph();nonce=z3.BitVec("nonce",32);cv=lambda n:z3.BitVecVal(n,32)
    swapped=z3.Concat(*[z3.Extract(i+7,i,nonce) for i in (0,8,16,24)])
    def compression(state,words):return lower(graph,{**{f"s{i}":x for i,x in enumerate(state)},**{f"w{i}":x for i,x in enumerate(words)}},z3)
    block=[cv(x) for x in unpack(">3I",header[64:76])]+[swapped,cv(0x80000000)]+[cv(0)]*10+[cv(640)]
    first=compression([cv(x) for x in header_midstate(header)],block)
    output=compression([cv(x) for x in IV],first+[cv(0x80000000)]+[cv(0)]*6+[cv(256)])
    digest_integer=z3.Concat(*[z3.Extract(i+7,i,word) for word in reversed(output) for i in (0,8,16,24)])
    samples=sorted({start,start+(1<<nonce_bits)-1,start+(1<<nonce_bits)//2})
    for sample in samples:
        actual=z3.simplify(z3.substitute(digest_integer,(nonce,cv(sample)))).as_long()
        expected=int.from_bytes(sha256d(header[:76]+sample.to_bytes(4,"little")),"little")
        if actual!=expected:raise AssertionError("SMT full SHA/byte-order expression mismatch")
    solver=z3.Solver();solver.set(timeout=timeout_ms,rlimit=100000)
    solver.add(z3.UGE(nonce,cv(start)),z3.ULE(nonce,cv(start+(1<<nonce_bits)-1)))
    if target!=(1<<256)-1:solver.add(z3.ULE(digest_integer,z3.BitVecVal(target,256))) # Unsigned <= maximum is identically true.
    construction=perf_counter()-begun;t=perf_counter();answer=solver.check();status=str(answer).upper();solutions=[]
    if answer==z3.sat:
        found=solver.model().eval(nonce).as_long();raw=header[:76]+found.to_bytes(4,"little")
        if not meets_target(sha256d(raw),target):raise AssertionError("SMT model failed independent oracle")
        solutions=[found]
    return {"status":status,"representation":"SMT-bitvector","solver":z3.get_version_string(),"count":1<<nonce_bits,
            "construction_seconds":construction,"solver_seconds":perf_counter()-t,"total_seconds":perf_counter()-begun,
            "timeout_ms":timeout_ms,"solutions":solutions,"family_discarded":answer==z3.unsat,
            "full_sha_expression_audit_samples":len(samples),"independent_oracle_parity":True,
            "unknown_reason":solver.reason_unknown() if answer==z3.unknown else None,"cryptanalytic_discovery":False}
