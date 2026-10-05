"""Exact round-boundary DAG/BDD -> live bit-plane conversion with bounded memory."""
from time import perf_counter
from .bool_dag import BooleanDAG,RepresentationCollapsed
from .bdd import BDD

class Hybrid:
    def __init__(self,count,max_nodes=20000,switch_round=8,growth_fraction=.5,kind="dag",max_bytes=64<<20):
        self.symbolic=BooleanDAG(max_nodes) if kind=="dag" else BDD(max_nodes)
        self.count=count;self.mask=(1<<count)-1;self.kind=kind;self.switch_round=switch_round
        self.threshold=int(max_nodes*growth_fraction);self.max_bytes=max_bytes;self.values=None;self.cache={};self.next_id=0
        self.transitions=[];self.peak_estimated_bytes=0;self.lane_bytes=(count+7)//8
    @property
    def nodes(self):return self.symbolic.nodes if self.values is None else self.values
    def variable(self,rank):
        run=1<<rank;return (self.mask//((1<<run)+1))<<run
    def boundary(self,round_number,live):
        live=set(live)|{0,1}
        if self.values is not None:
            self.values={i:self.values[i] for i in live};self.cache.clear();return
        if round_number<self.switch_round and len(self.symbolic.nodes)<self.threshold:return
        estimate=len(self.symbolic.nodes)*(self.lane_bytes+48)
        if estimate>self.max_bytes:raise RepresentationCollapsed("Hybrid conversion memory bound exceeded; use smaller subfamilies")
        t=perf_counter();values=[0,self.mask]
        for node in self.symbolic.nodes[2:]:
            if self.kind=="dag":
                op,*args=node
                if op=="var":value=self.variable(int(args[0]))
                elif op=="not":value=values[args[0]]^self.mask
                elif op=="and":value=values[args[0]]&values[args[1]]
                else:value=values[args[0]]^values[args[1]]
            else:
                rank,low,high=node;p=self.variable(rank);value=values[low]^((values[low]^values[high])&p)
            values.append(value)
        self.next_id=len(values);self.values={i:values[i] for i in live}
        self.peak_estimated_bytes=max(self.peak_estimated_bytes,estimate)
        self.transitions.append({"from":self.kind,"to":"bit-planes","round":round_number,"symbolic_nodes":len(values),"live_nodes":len(live),"conversion_seconds":perf_counter()-t})
        self.symbolic=None
    def node(self,op,*args):
        if self.values is None:return self.symbolic.node(op,*args)
        key=(op,*args)
        if key in self.cache:return self.cache[key]
        if op=="not":value=self.values[args[0]]^self.mask
        elif op=="and":value=self.values[args[0]]&self.values[args[1]]
        elif op=="xor":value=self.values[args[0]]^self.values[args[1]]
        elif op=="var":value=self.variable(int(args[0]))
        else:raise ValueError("Invalid hybrid primitive")
        if value in (0,self.mask):return int(value==self.mask)
        estimated=(len(self.values)+1)*(self.lane_bytes+48)
        if estimated>self.max_bytes:raise RepresentationCollapsed("Hybrid live plane memory bound exceeded")
        ident=self.next_id;self.next_id+=1;self.values[ident]=value;self.cache[key]=ident
        self.peak_estimated_bytes=max(self.peak_estimated_bytes,estimated);return ident
    def evaluate(self,index,variables):
        if self.values is None:return self.symbolic.evaluate(index,variables)
        lane=sum(int(value)<<int(rank) for rank,value in variables.items())
        return bool((self.values[index]>>lane)&1)
