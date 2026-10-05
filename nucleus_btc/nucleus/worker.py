"""Isolated, finite built-in research workers. No wallet or pool config access."""
import json
import subprocess
import sys
from pathlib import Path
from .persistence import atomic_json
from .memory import KnowledgeStore
from ..benchmark import heldout_headers,benchmark
from ..gpu.backend import get_backend,BackendUnavailable
from ..gpu.opencl import OpenCLError

ROOT=Path(__file__).resolve().parents[2]

def backend():
    try:
        with KnowledgeStore(ROOT/"results"/"knowledge.sqlite") as store:config=store.get_state("champion",{}).get("config",{})
        return get_backend("opencl",**config)
    except (BackendUnavailable,OpenCLError):
        try:return get_backend("native")
        except BackendUnavailable:return get_backend("hashlib")

def execute(experiment):
    kind=experiment["kind"];generation=experiment.get("generation",0);header=heldout_headers(510019+generation,1)[0]
    if kind in ("family-ir","carry-factor","conditional","program","differential","mitm","cone","egraph"):
        from ..family_ir.experiments import worker_experiment
        return worker_experiment(kind,generation)
    if kind=="planes-scaling":
        if experiment["carry"].startswith("hybrid-"):
            from ..representations.symbolic import symbolic_experiment
            return symbolic_experiment(experiment["nonce_bits"],20000,experiment["carry"],header=bytes.fromhex(experiment["header"]),target=1,switch_round=2)
        from ..representations.plane_sha import plane_family
        return plane_family(bytes.fromhex(experiment["header"]),0,experiment["nonce_bits"],carry=experiment["carry"])
    if kind=="generated":
        from .generated import evaluate
        with KnowledgeStore(ROOT/"results"/"knowledge.sqlite") as store:config=store.get_state("champion",{}).get("config",{"full_unroll":True,"alt_boolean":True,"local_size":64})
        return evaluate(16+generation,config)
    if kind=="family":
        from ..solver.adaptive import solve_family,SplitPolicy
        with backend() as engine:return solve_family(engine,header,0,1<<min(16,8+generation),1,SplitPolicy(**experiment.get("split_policy",{})))
    if kind=="carry":
        from ..representations.plane_sha import plane_family
        return plane_family(header,0,6+generation%5,carry=("ripple","prefix","carry-select","carry-save")[generation%4])
    if kind=="representation":
        from ..representations.symbolic import symbolic_experiment
        species=("anf","bdd","dag","hybrid-dag","hybrid-bdd")[generation%5]
        return symbolic_experiment(2+generation%5,20000,species,header=header)
    if kind=="sat":
        if generation%2:
            from ..solver.smt import smt_family
            return smt_family(header,nonce_bits=2+generation%5)
        from ..representations.symbolic import symbolic_experiment
        return symbolic_experiment(1,500000,"dag",header=header,solve_constraints=True)
    if kind=="structural":
        from ..solver.structural import search_structures
        with backend() as engine:return search_structures(engine,number=8)
    if kind=="benchmark":
        with backend() as engine:return {"status":"measured","measurement":benchmark(engine,count=1<<20,repeats=3,seconds=.05)}
    if kind=="regression":
        import tempfile
        with tempfile.TemporaryDirectory(prefix="regression-",dir=ROOT/"results"/"evolution") as temporary:
            result_path=Path(temporary)/"tests.json"
            result=subprocess.run([sys.executable,"scripts/test_runner.py","--output",str(result_path)],cwd=ROOT,capture_output=True,timeout=120)
            if result.returncode:raise AssertionError("Exactness regression failed: "+result.stderr.decode("utf-8","replace")[-2048:])
            return {"status":"exactness_passed",**json.loads(result_path.read_text())}
    raise ValueError("Unregistered experiment kind")

def main():
    try:
        experiment=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        result=execute(experiment);atomic_json(sys.argv[2],result);return 0
    except Exception as error:
        print(f"{type(error).__name__}: {error}",file=sys.stderr);return 1

if __name__=="__main__":raise SystemExit(main())
