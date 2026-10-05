"""Bounded exact Boolean DAG with canonical node sharing and measurable collapse."""
class RepresentationCollapsed(RuntimeError):pass

class BooleanDAG:
    def __init__(self,max_nodes=4096):
        if max_nodes<2:raise ValueError("Need two constant nodes")
        self.max_nodes=max_nodes;self.nodes=[("const",0),("const",1)];self.lookup={node:i for i,node in enumerate(self.nodes)}
    def node(self,op,*args):
        if op not in ("var","not","and","xor"):raise ValueError("Unsupported Boolean operation")
        if op=="var":
            if len(args)!=1 or not isinstance(args[0],str):raise ValueError("Variable needs name")
        else:
            if len(args)!=(1 if op=="not" else 2) or any(not isinstance(i,int) or not 0<=i<len(self.nodes) for i in args):raise ValueError("Invalid node operands")
        if op in ("and","xor"):
            a,b=sorted(args);args=(a,b)
            if a==b:return a if op=="and" else 0
            if op=="and" and a==0:return 0
            if op=="and" and a==1:return b
            if op=="xor" and a==0:return b
            if op=="xor" and a==1:return self.node("not",b)
        if op=="not" and args[0]<2:return 1-args[0]
        if op=="not" and self.nodes[args[0]][0]=="not":return self.nodes[args[0]][1]
        key=(op,*args)
        if key not in self.lookup:
            if len(self.nodes)>=self.max_nodes:raise RepresentationCollapsed("DAG node budget exceeded")
            self.lookup[key]=len(self.nodes);self.nodes.append(key)
        return self.lookup[key]
    def evaluate(self,index,variables):
        return self.evaluate_many([index],variables)[0]
    def evaluate_many(self,indexes,variables):
        values=[]
        for node in self.nodes[:max(indexes)+1]:
            op,*args=node
            if op=="const":value=bool(args[0])
            elif op=="var":value=bool(variables[args[0]])
            elif op=="not":value=not values[args[0]]
            elif op=="and":value=values[args[0]] and values[args[1]]
            else:value=values[args[0]] != values[args[1]]
            values.append(value)
        return [values[index] for index in indexes]
