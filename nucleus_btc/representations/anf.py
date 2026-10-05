"""Exact GF(2) algebraic normal forms with hard monomial/node bounds."""
from .bool_dag import RepresentationCollapsed

class ANF:
    def __init__(self,max_nodes=20000,max_terms=64):
        self.max_nodes=max_nodes;self.max_terms=max_terms
        self.nodes=[frozenset(),frozenset({0})];self.unique={v:i for i,v in enumerate(self.nodes)};self.total_terms=1
    def intern(self,terms):
        terms=frozenset(terms)
        if terms in self.unique:return self.unique[terms]
        if len(terms)>self.max_terms or len(self.nodes)>=self.max_nodes or self.total_terms+len(terms)>self.max_nodes*8:
            raise RepresentationCollapsed("ANF monomial/node budget exceeded")
        ident=len(self.nodes);self.nodes.append(terms);self.unique[terms]=ident;self.total_terms+=len(terms);return ident
    def node(self,op,*args):
        if op=="var":return self.intern({1<<int(args[0])})
        if op=="not":return self.intern(self.nodes[args[0]]^{0})
        left,right=(self.nodes[i] for i in args)
        if op=="xor":return self.intern(left^right)
        if op!="and":raise ValueError("Unsupported ANF operation")
        result=set()
        for a in left:
            for b in right:
                term=a|b
                if term in result:result.remove(term)
                else:result.add(term)
        return self.intern(result)
    def evaluate(self,index,variables):
        assignment=sum(int(value)<<int(name) for name,value in variables.items())
        return bool(sum((term&assignment)==term for term in self.nodes[index])%2)
