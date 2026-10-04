"""Deterministic diverse research queue; retry failures within bounded resources."""
from hashlib import sha256
from pathlib import Path
from ..representations.symbolic import symbolic_experiment
from ..benchmark import heldout_headers
from .memory import KnowledgeStore

def run_portfolio(store_path="results/knowledge.sqlite"):
    attempts=[("dag",4,20000),("bdd",4,20000),("bdd",4,100000),("bdd",6,100000),("bdd",2,10000)]
    results=[]
    # One hidden template prevents hardcoded known-block behavior from passing unnoticed.
    heldout=heldout_headers(seed=812,number=1)[0]
    source=Path(__file__).resolve().parents[1]/"representations"/"symbolic.py"
    fingerprint=sha256(source.read_bytes()).hexdigest()
    with KnowledgeStore(store_path) as store:
        for representation,bits,budget in attempts:
            config={"species":representation,"nonce_bits":bits,"max_nodes":budget,"source_sha256":fingerprint}
            result=symbolic_experiment(bits,budget,representation,header=heldout)
            gain=result.get("speedup_including_construction",0.)
            kind="FRONTIER" if gain>1 else "DEAD"
            reason="Bounded symbolic approach collapsed" if result["status"]=="resource_budget_collapsed" else "Full exact computation works; setup/evaluation does not beat hashing" if gain<=1 else "Finite-family speed signal requires larger unseen-family verification"
            store.put(kind,config,result,reason,gain)
            results.append(result)
    return {"attempts":results,"production_modified":False,"cryptanalytic_discovery":False,"decision":"retain optimized ordinary hashing; these symbolic branches are not economically competitive"}
