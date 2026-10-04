"""Small bounded exact SAT engine. UNKNOWN is never a pruning certificate."""
from dataclasses import dataclass
from time import monotonic

@dataclass
class SATResult:
    status:str
    assignment:dict[int,bool]|None
    visited:int

def dag_to_cnf(dag,root):
    """Tseitin constraints for the complete DAG and root=true. IDs are 1-based."""
    if not 0<=root<len(dag.nodes):raise ValueError("Root outside DAG")
    clauses=[]
    for i,node in enumerate(dag.nodes):
        z=i+1;op,*args=node
        if op=="const":clauses.append((z if args[0] else -z,))
        elif op=="var":continue
        elif op=="not":
            a=args[0]+1;clauses.extend(((z,a),(-z,-a)))
        else:
            a,b=(n+1 for n in args)
            if op=="and":clauses.extend(((-z,a),(-z,b),(z,-a,-b)))
            elif op=="xor":clauses.extend(((-a,-b,-z),(a,b,-z),(a,-b,z),(-a,b,z)))
            else:raise ValueError("Unsupported CNF operation")
    clauses.append((root+1,));return clauses

def solve_cnf(clauses,max_nodes=10000,max_seconds=1.):
    if max_nodes<=0 or max_seconds<=0:raise ValueError("Invalid SAT budget")
    clauses=tuple(tuple(clause) for clause in clauses)
    if any(any(not isinstance(lit,int) or lit==0 for lit in clause) for clause in clauses):raise ValueError("CNF literals are nonzero signed variable IDs")
    deadline=monotonic()+max_seconds;visited=0;stack=[(clauses,{})]
    while stack:
        visited+=1
        if visited>max_nodes or monotonic()>deadline:return SATResult("UNKNOWN",None,visited-1)
        remaining,assignment=stack.pop();contradiction=False
        while True:
            if monotonic()>deadline:return SATResult("UNKNOWN",None,visited)
            if any(len(clause)==0 for clause in remaining):contradiction=True;break
            units=[clause[0] for clause in remaining if len(clause)==1]
            if not units:break
            unit=units[0];var=abs(unit);value=unit>0
            if var in assignment and assignment[var]!=value:contradiction=True;break
            assignment[var]=value
            remaining=tuple(tuple(lit for lit in clause if lit!=-unit) for clause in remaining if unit not in clause)
        if contradiction:continue
        if not remaining:return SATResult("SAT",assignment,visited)
        # Shortest clause heuristic; exhaustive branches, no learned probabilistic pruning.
        chosen=min(remaining,key=len)[0]
        stack.append((remaining+((-chosen,),),dict(assignment)))
        stack.append((remaining+((chosen,),),dict(assignment)))
    return SATResult("UNSAT",None,visited)
