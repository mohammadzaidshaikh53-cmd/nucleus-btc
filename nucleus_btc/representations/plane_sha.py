"""Full exact SHA256d in live bit planes, without retaining an expanding DAG."""
from struct import unpack
from time import perf_counter
from hashlib import sha256
from .symbolic import Circuit
from ..oracle.sha256 import IV,header_midstate
from ..bitcoin.target import meets_target,UINT256_MAX

class PlaneCircuit(Circuit):
    def __init__(self,count):
        self.mask=(1<<count)-1;self.round=0;self.additions=0;self.carry_ones=0;self.carry_bits=0;self.economic_deadline=None
    def stage(self,name):self.phase=name
    def finish_stage(self):pass
    def const(self,x):return [self.mask if (x>>i)&1 else 0 for i in range(32)]
    def bx(self,a,b):return [x^y for x,y in zip(a,b)]
    def band(self,a,b):return [x&y for x,y in zip(a,b)]
    def inv(self,a):return [x^self.mask for x in a]
    def add(self,a,b):
        carry=0;out=[];self.additions+=1
        for x,y in zip(a,b):
            p=x^y;out.append(p^carry);carry=(x&y)|(p&carry)
            self.carry_ones+=carry.bit_count();self.carry_bits+=self.mask.bit_length()
        return out

def plane_family(header,start,nonce_bits,target=1,verify=True):
    if len(header)!=80 or not 1<=nonce_bits<=20 or start%(1<<nonce_bits) or start+(1<<nonce_bits)>1<<32:raise ValueError("Aligned bounded nonce family required")
    if not 0<target<=UINT256_MAX:raise ValueError("Invalid target")
    count=1<<nonce_bits;begun=perf_counter();c=PlaneCircuit(count)
    nonce=c.const(start)
    for i in range(nonce_bits):
        run=1<<i;nonce[i]=(c.mask//((1<<run)+1))<<run
    word=[nonce[(3-i//8)*8+i%8] for i in range(32)]
    block=[c.const(x) for x in unpack(">3I",header[64:76])]+[word,c.const(0x80000000)]+[c.const(0) for _ in range(10)]+[c.const(640)]
    construction=perf_counter()-begun;t=perf_counter()
    first=c.compress([c.const(x) for x in header_midstate(header)],block)
    second=c.compress([c.const(x) for x in IV],first+[c.const(0x80000000)]+[c.const(0) for _ in range(6)]+[c.const(256)])
    computation=perf_counter()-t;t=perf_counter()
    # Comparison applies in Bitcoin's little-endian digest-integer order.
    bits=[second[i//32][(3-(i%32)//8)*8+i%8] for i in range(256)]
    equal=c.mask;greater=0
    for i in range(255,-1,-1):
        if (target>>i)&1:equal&=bits[i]
        else:greater|=equal&bits[i];equal&=bits[i]^c.mask
    feasible=greater^c.mask;found=[];pending=feasible
    # A target producing too many solutions is handled with an explicit bound.
    if pending.bit_count()>4096:raise ValueError("Plane result capacity exceeded; split/retry with smaller family")
    while pending:
        bit=pending&-pending;found.append(start+bit.bit_length()-1);pending^=bit
    comparison=perf_counter()-t;elapsed=perf_counter()-begun;t=perf_counter()
    encoded=[[x.to_bytes((count+7)//8,"little") for x in word] for word in second]
    lanes=range(count) if count<=4096 else sorted(set([0,count-1]+[(i*count)//64 for i in range(64)]+[n-start for n in found]))
    if verify:
        for lane in lanes:
            digest=b"".join(sum(((encoded[j][i][lane//8]>>(lane%8))&1)<<i for i in range(32)).to_bytes(4,"big") for j in range(8))
            raw=header[:76]+(start+lane).to_bytes(4,"little")
            expected=sha256(sha256(raw).digest()).digest()
            if digest!=expected or bool((feasible>>lane)&1)!=meets_target(expected,target):raise AssertionError("Bit-plane full SHA/target mismatch")
    return {"status":"full_sha256d_parity_passed","representation":"bit-planes","count":count,"nonce_bits":nonce_bits,
            "solutions":found,"completed_rounds":c.round,"construction_seconds":construction,"compute_seconds":computation,
            "target_seconds":comparison,"total_seconds":elapsed,"audit_seconds":perf_counter()-t,
            "audited_candidates":len(lanes) if verify else 0,"exhaustive_audit":verify and count<=4096,
            "carry_density":c.carry_ones/c.carry_bits,"ripple_carry_depth":32,"additions":c.additions,
            "live_state_minimum_bytes":32*8*((count+7)//8),"cryptanalytic_discovery":False}
