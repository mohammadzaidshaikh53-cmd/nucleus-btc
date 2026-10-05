"""Full 128 remaining SHA rounds over a small exact nonce family.

Records resource collapse or exhaustive parity. Cost includes circuit construction
and evaluation; success at a tiny family does not imply scalable compression.
"""
from hashlib import sha256
from struct import unpack
from time import perf_counter
from .bool_dag import BooleanDAG,RepresentationCollapsed
from .bdd import BDD
from .anf import ANF
from ..oracle.sha256 import K,IV,header_midstate
from ..bitcoin.block_header import GENESIS,BlockHeader
from ..bitcoin.target import compact_to_target,meets_target

class EconomicCollapse(RepresentationCollapsed):pass

class Circuit:
    def __init__(self,representation):
        self.r=representation;self.round=0;self.phase="initialization";self.phase_growth={};self.economic_deadline=None
    def stage(self,name):
        self.phase=name;self.phase_growth.setdefault(name,0);self._before=len(self.r.nodes)
    def finish_stage(self):self.phase_growth[self.phase]+=len(self.r.nodes)-self._before
    def const(self,x):return [(x>>i)&1 for i in range(32)]
    def bx(self,a,b):return [self.r.node("xor",x,y) for x,y in zip(a,b)]
    def band(self,a,b):return [self.r.node("and",x,y) for x,y in zip(a,b)]
    def inv(self,a):return [self.r.node("not",x) for x in a]
    def rr(self,a,n):return a[n:]+a[:n]
    def shift(self,a,n):return a[n:]+[0]*n
    def xor3(self,a,b,c):return self.bx(self.bx(a,b),c)
    def add(self,a,b):
        carry=0;out=[]
        for x,y in zip(a,b):
            p=self.r.node("xor",x,y);out.append(self.r.node("xor",p,carry))
            # Terms are disjoint, so XOR equals OR exactly here.
            carry=self.r.node("xor",self.r.node("and",x,y),self.r.node("and",p,carry))
        return out
    def sum(self,*args):
        result=args[0]
        for word in args[1:]:result=self.add(result,word)
        return result
    def compress(self,state,block):
        w=list(block);a,b,c,d,e,f,g,h=state
        for i in range(64):
            self.round+=1
            if self.economic_deadline is not None and perf_counter()>self.economic_deadline:raise EconomicCollapse("Observed construction cost exceeded conventional family budget")
            if i>=16:
                self.stage("message_schedule")
                x,y=w[i-15],w[i-2]
                w.append(self.sum(w[i-16],self.xor3(self.rr(x,7),self.rr(x,18),self.shift(x,3)),w[i-7],self.xor3(self.rr(y,17),self.rr(y,19),self.shift(y,10))))
                self.finish_stage()
            self.stage("Ch_Maj")
            ch=self.bx(self.band(e,f),self.band(self.inv(e),g))
            maj=self.xor3(self.band(a,b),self.band(a,c),self.band(b,c))
            self.finish_stage();self.stage("T1_Sigma_carries")
            t1=self.sum(h,self.xor3(self.rr(e,6),self.rr(e,11),self.rr(e,25)),ch,self.const(K[i]),w[i])
            self.finish_stage();self.stage("T2_Sigma_carries")
            t2=self.sum(self.xor3(self.rr(a,2),self.rr(a,13),self.rr(a,22)),maj)
            self.finish_stage();self.stage("state_carries")
            a,b,c,d,e,f,g,h=self.add(t1,t2),a,b,c,self.add(d,t1),e,f,g
            self.finish_stage()
        return [self.add(old,new) for old,new in zip(state,(a,b,c,d,e,f,g,h))]

def symbolic_experiment(nonce_bits=4,max_nodes=20000,representation="dag",header=None,target=None,economic_budget_seconds=None,variable_order=None,solve_constraints=False):
    if not 1<=nonce_bits<=8 or not 64<=max_nodes<=2_000_000:raise ValueError("Research budget: 1..8 nonce bits and 64..2,000,000 nodes")
    if representation not in ("dag","bdd","anf"):raise ValueError("Choose dag, bdd or anf")
    r=BooleanDAG(max_nodes) if representation=="dag" else BDD(max_nodes) if representation=="bdd" else ANF(max_nodes);c=Circuit(r)
    header=GENESIS.serialize() if header is None else header
    parsed=BlockHeader.parse(header)
    base=parsed.nonce&~((1<<nonce_bits)-1);count=1<<nonce_bits
    order=list(range(nonce_bits)) if variable_order is None else variable_order
    if sorted(order)!=list(range(nonce_bits)):raise ValueError("Variable ordering must be a permutation")
    t=perf_counter();expected=[]
    for n in range(base,base+count):
        raw=header[:76]+n.to_bytes(4,"little");expected.append(sha256(sha256(raw).digest()).digest())
    baseline=perf_counter()-t
    began=perf_counter();trace={"representation":representation,"nonce_bits":nonce_bits,"candidates":count,"max_nodes":max_nodes,"baseline_hashlib_seconds":baseline}
    if economic_budget_seconds is not None:
        if economic_budget_seconds<=0:raise ValueError("Positive economic budget required")
        c.economic_deadline=began+economic_budget_seconds
    try:
        nonce=c.const(base)
        for i in range(nonce_bits):nonce[i]=r.node("var",str(order.index(i)))
        nonce_word=[nonce[(3-i//8)*8+i%8] for i in range(32)]
        block=[c.const(x) for x in unpack(">3I",header[64:76])]+[nonce_word,c.const(0x80000000)]+[c.const(0) for _ in range(10)]+[c.const(640)]
        first=c.compress([c.const(x) for x in header_midstate(header)],block)
        second=c.compress([c.const(x) for x in IV],first+[c.const(0x80000000)]+[c.const(0) for _ in range(6)]+[c.const(256)])
        target=compact_to_target(parsed.bits) if target is None else target
        if not 0<target<(1<<256):raise ValueError("Invalid target")
        c.stage("target_constraint")
        # Exact unsigned hash <= target circuit in Bitcoin's little-endian integer order.
        bits=[second[i//32][(3-(i%32)//8)*8+i%8] for i in range(256)]
        equal=1;greater=0
        for i in range(255,-1,-1):
            bit=bits[i]
            if (target>>i)&1:equal=r.node("and",equal,bit)
            else:
                violation=r.node("and",equal,bit)
                # Existing greater and a new first-difference violation are disjoint.
                greater=r.node("xor",greater,violation)
                equal=r.node("and",equal,r.node("not",bit))
        feasible=r.node("not",greater)
        c.finish_stage()
        constraint_result=None
        if solve_constraints:
            if representation!="dag":raise ValueError("CNF conversion requires a Boolean DAG")
            from ..solver.constraints import dag_to_cnf,solve_cnf
            cnf_started=perf_counter();clauses=dag_to_cnf(r,feasible)
            answer=solve_cnf(clauses,max_nodes=10000,max_seconds=.1)
            constraint_result={"status":answer.status,"visited":answer.visited,"clauses":len(clauses),"conversion_and_solver_seconds":perf_counter()-cnf_started}
        actual=[]
        solutions=[]
        for n in range(count):
            variables={str(rank):bool((n>>bit)&1) for rank,bit in enumerate(order)}
            words=[sum(int(r.evaluate(bit,variables))<<i for i,bit in enumerate(word)) for word in second]
            actual.append(b"".join(w.to_bytes(4,"big") for w in words))
            if r.evaluate(feasible,variables):solutions.append(base+n)
        if actual!=expected:raise AssertionError("Symbolic full SHA-256d parity failed")
        expected_solutions=[base+i for i,d in enumerate(expected) if meets_target(d,target)]
        if solutions!=expected_solutions:raise AssertionError("Symbolic target constraint lost or invented a solution")
        elapsed=perf_counter()-began
        return {**trace,"status":"full_sha256d_parity_passed","completed_rounds":c.round,"nodes":len(r.nodes),"total_seconds":elapsed,"speedup_including_construction":baseline/elapsed,"phase_node_growth":c.phase_growth,"variable_order":order,
                "target_constraint_verified":True,"exact_solutions":solutions,"rejected_candidates":count-len(solutions),"constraint_result":constraint_result,
                "cryptanalytic_discovery":False,"extrapolation_allowed":False}
    except RepresentationCollapsed as e:
        return {**trace,"status":"economic_budget_collapsed" if isinstance(e,EconomicCollapse) else "resource_budget_collapsed","at_round":c.round,"nodes":len(r.nodes),"total_seconds":perf_counter()-began,"reason":str(e),
                "economic_Rc":c.round if isinstance(e,EconomicCollapse) else None,"failure_phase":c.phase,
                "phase_node_growth":c.phase_growth,"variable_order":order,"cryptanalytic_discovery":False}
