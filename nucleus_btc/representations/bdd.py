"""Reduced ordered BDD with a hard node budget. Fixed ordering is explicit."""
from .bool_dag import RepresentationCollapsed

class BDD:
    def __init__(self,max_nodes=20000):
        if max_nodes<2:raise ValueError("Need two terminal nodes")
        self.max_nodes=max_nodes;self.nodes=[None,None];self.unique={};self.cache={}
    def make(self,var,low,high):
        if low==high:return low
        key=(var,low,high)
        if key not in self.unique:
            if len(self.nodes)>=self.max_nodes:raise RepresentationCollapsed("BDD node budget exceeded")
            self.unique[key]=len(self.nodes);self.nodes.append(key)
        return self.unique[key]
    def variable(self,var):return self.make(var,0,1)
    def apply(self,op,a,b):
        if op not in ("and","xor"):raise ValueError("Unknown BDD operation")
        a,b=sorted((a,b));key=(op,a,b)
        if key in self.cache:return self.cache[key]
        if a<2 and b<2:return (a&b) if op=="and" else (a^b)
        if op=="and" and a==0:return 0
        if op=="and" and a==1:return b
        if op=="xor" and a==0:return b
        if a==b:return a if op=="and" else 0
        va=self.nodes[a][0] if a>=2 else 1<<30;vb=self.nodes[b][0] if b>=2 else 1<<30;v=min(va,vb)
        _,al,ah=self.nodes[a] if va==v else (v,a,a)
        _,bl,bh=self.nodes[b] if vb==v else (v,b,b)
        result=self.make(v,self.apply(op,al,bl),self.apply(op,ah,bh))
        self.cache[key]=result
        if len(self.cache)>self.max_nodes*8:self.cache.clear()
        return result
    def node(self,op,*args):
        if op=="var":return self.variable(int(args[0]))
        if op=="not":return self.apply("xor",1,args[0])
        return self.apply(op,*args)
    def evaluate(self,index,variables):
        while index>=2:
            var,lo,hi=self.nodes[index];index=hi if variables[str(var)] else lo
        return bool(index)
