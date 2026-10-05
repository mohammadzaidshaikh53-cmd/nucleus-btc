"""Topological word graph with structural CSE and deterministic interchange."""
import json
from hashlib import sha256
from .nodes import Node,MASK,COMMUTATIVE,ARITY,execute

class Graph:
    def __init__(self):self.nodes=[];self.unique={};self.outputs=[]
    def node(self,op,*args,value=None):
        if op not in ARITY and op!="ADD32":raise ValueError("Unknown IR opcode")
        if op=="ADD32":
            if not 2<=len(args)<=8:raise ValueError("ADD32 requires 2..8 operands")
        elif len(args)!=ARITY[op]:raise ValueError("Wrong IR arity")
        if any(not isinstance(i,int) or not 0<=i<len(self.nodes) for i in args):raise ValueError("Non-topological IR edge")
        if op=="INPUT" and (not isinstance(value,str) or not value.isidentifier()):raise ValueError("Invalid input name")
        if op=="CONST32" and (not isinstance(value,int) or not 0<=value<=MASK):raise ValueError("Invalid uint32 constant")
        if op in ("ROTR","SHR","SHL") and (not isinstance(value,int) or not 0<=value<32):raise ValueError("Invalid shift")
        if op not in ("INPUT","CONST32","ROTR","SHR","SHL") and value is not None:raise ValueError("Unexpected opcode metadata")
        if op in COMMUTATIVE:args=tuple(sorted(args))
        if args and all(self.nodes[i].op=="CONST32" for i in args):
            value32=execute(Node(op,args,value),[n.value if n.op=="CONST32" else 0 for n in self.nodes],{})
            return self.node("CONST32",value=value32)
        if op in ("XOR","AND","OR") and args[0]==args[1]:
            return self.node("CONST32",value=0) if op=="XOR" else args[0]
        if op in ("ROTR","SHR","SHL") and value==0:return args[0]
        if op=="NOT" and self.nodes[args[0]].op=="NOT":return self.nodes[args[0]].args[0]
        if op=="ROTR" and self.nodes[args[0]].op=="ROTR":
            child=self.nodes[args[0]];return self.node("ROTR",child.args[0],value=(child.value+value)%32)
        item=Node(op,tuple(args),value)
        if item not in self.unique:self.unique[item]=len(self.nodes);self.nodes.append(item)
        return self.unique[item]
    def input(self,name):return self.node("INPUT",value=name)
    def const(self,value):return self.node("CONST32",value=value&MASK)
    def validate(self):
        rebuilt=Graph()
        for index,n in enumerate(self.nodes):
            if any(i>=index or i<0 for i in n.args):raise ValueError("Invalid topological graph")
            # Construction checks arity and all scalar metadata; no executable expressions.
            rebuilt.node(n.op,*n.args,value=n.value)
            if len(rebuilt.nodes)!=index+1:raise ValueError("Noncanonical or duplicate IR node")
        if not self.outputs or any(not isinstance(i,int) or not 0<=i<len(self.nodes) for i in self.outputs):raise ValueError("Invalid outputs")
        return True
    def evaluate(self,inputs):
        values=[]
        for n in self.nodes:values.append(execute(n,values,inputs))
        return tuple(values[i] for i in self.outputs)
    def serialize(self):
        return json.dumps({"schema":1,"nodes":[[n.op,list(n.args),n.value] for n in self.nodes],"outputs":self.outputs},sort_keys=True,separators=(",",":"))
    @classmethod
    def deserialize(cls,text):
        data=json.loads(text)
        if data.get("schema")!=1 or len(data.get("nodes",[]))>100000:raise ValueError("Unsupported/bounded IR")
        graph=cls()
        for index,(op,args,value) in enumerate(data["nodes"]):
            ident=graph.node(op,*args,value=value)
            if ident!=index:raise ValueError("Noncanonical serialized graph")
        graph.outputs=data["outputs"];graph.validate();return graph
    @property
    def fingerprint(self):return sha256(self.serialize().encode()).hexdigest()
    def live_nodes(self):
        live=set();pending=list(self.outputs)
        while pending:
            index=pending.pop()
            if index not in live:live.add(index);pending.extend(self.nodes[index].args)
        return live
