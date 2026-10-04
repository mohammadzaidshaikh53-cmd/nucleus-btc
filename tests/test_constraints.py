import itertools
import random
import unittest
from nucleus_btc.representations.bool_dag import BooleanDAG
from nucleus_btc.solver.constraints import solve_cnf,dag_to_cnf

class ConstraintTests(unittest.TestCase):
    def test_sat_unsat_unknown(self):
        self.assertEqual(solve_cnf([(1,),(-1,)]).status,"UNSAT")
        self.assertEqual(solve_cnf([(1,2),(-1,2)]).status,"SAT")
        self.assertEqual(solve_cnf([(1,2),(3,4)],max_nodes=1).status,"UNKNOWN")
    def test_tseitin_truth_table(self):
        for op in ["and","xor"]:
            dag=BooleanDAG();a=dag.node("var","a");b=dag.node("var","b");root=dag.node(op,a,b)
            for av,bv in itertools.product([False,True],repeat=2):
                clauses=dag_to_cnf(dag,root)+[(a+1 if av else -(a+1),),(b+1 if bv else -(b+1),)]
                expected=av and bv if op=="and" else av!=bv
                self.assertEqual(solve_cnf(clauses).status,"SAT" if expected else "UNSAT")
        dag=BooleanDAG();a=dag.node("var","a");root=dag.node("not",a)
        self.assertEqual(solve_cnf(dag_to_cnf(dag,root)+[(a+1,)]).status,"UNSAT")
    def test_dpll_against_exhaustive_small_formulas(self):
        rng=random.Random(923)
        for _ in range(100):
            clauses=[tuple(rng.choice([-1,1])*rng.randrange(1,5) for _ in range(rng.randrange(1,4))) for _ in range(rng.randrange(1,12))]
            brute=any(all(any(values[abs(lit)-1]==(lit>0) for lit in clause) for clause in clauses) for values in itertools.product([False,True],repeat=4))
            self.assertEqual(solve_cnf(clauses).status,"SAT" if brute else "UNSAT")

if __name__=="__main__":unittest.main()
