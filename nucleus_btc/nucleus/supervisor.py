"""Finite/resumable research with durable intent-before-execution checkpoints.

Only registered project experiments execute. Workers have a hard process timeout;
interrupted experiments resume with the SAME identity and bounded retry counter.
"""
import json
import os
import signal
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from time import monotonic
from .memory import KnowledgeStore
from .persistence import ProcessLock,atomic_json
from .selector import ExperimentSelector,RESEARCH

ROOT=Path(__file__).resolve().parents[2]
KINDS=RESEARCH+("regression","benchmark")

def classify(error):
    if isinstance(error,(AssertionError,)):return "D",False
    if isinstance(error,MemoryError):return "F",False
    if isinstance(error,(TimeoutError,subprocess.TimeoutExpired)):return "F",True
    if isinstance(error,ModuleNotFoundError):return "H",False
    if isinstance(error,OSError):return "B",True
    text=str(error).lower()
    if "timeouterror" in text:return "F",True
    if "oserror" in text:return "B",True
    if "unavailable" in text or "loader absent" in text:return "H",False
    if "mismatch" in text or "parity" in text:return "D",False
    if "build" in text:return "B",False
    if "opencl" in text:return "C",True
    return "A",False

def source_fingerprint():
    digest=sha256()
    paths=[]
    for folder in (ROOT/"nucleus_btc",ROOT/"native",ROOT/"tests",ROOT/"scripts"):
        paths.extend(p for p in folder.rglob("*") if p.suffix in (".py",".cl",".cpp",".h",".hpp",".cu",".rs",".toml",".lock") and "target" not in p.parts)
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode());digest.update(path.read_bytes())
    return digest.hexdigest()

class Supervisor:
    def __init__(self,directory="results/evolution",worker_timeout=180,max_records=192,runner=None):
        self.directory=Path(directory);self.worker_timeout=worker_timeout
        if not 1<=worker_timeout<=3600:raise ValueError("Worker timeout must be 1..3600 seconds")
        self.max_records=max_records;self.runner=runner or self._worker;self.stop=False
    def _worker(self,experiment):
        request=self.directory/"request.json";response=self.directory/"response.json"
        atomic_json(request,experiment)
        if response.exists():response.unlink()
        command=[sys.executable,"-m","nucleus_btc.nucleus.worker",str(request.resolve()),str(response.resolve())]
        environment={k.upper():v for k,v in os.environ.items()} if os.name=="nt" else dict(os.environ)
        result=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,timeout=getattr(self,"current_worker_timeout",self.worker_timeout))
        if result.returncode:
            # Worker diagnostics are intentionally limited and never contain pool config.
            message=result.stderr.decode("utf-8","replace")[-2048:]
            raise RuntimeError(f"worker {experiment['kind']} exited {result.returncode}: {message}")
        if not response.is_file() or response.stat().st_size>65536:raise RuntimeError("Missing or oversized worker result")
        return json.loads(response.read_text(encoding="utf-8"))
    def run(self,steps=16,seconds=3600,forever=False):
        if not 1<=steps<=100000 or not 0<seconds<=86400*30:raise ValueError("Invalid supervisor budget")
        self.directory.mkdir(parents=True,exist_ok=True);started=monotonic();completed=0
        fingerprint=source_fingerprint()
        with ProcessLock(self.directory/"owner.lock"),KnowledgeStore(self.directory/"state.sqlite",self.max_records) as store:
            state=store.get_state("supervisor",{"schema":1,"cursor":0,"pending":None,"completed":0,"history":[]})
            if state["pending"] and state["pending"].get("source_sha256")!=fingerprint:
                previous=state["pending"]
                store.put("DEAD",{"candidate_id":previous["id"]},{"failure_class":"A","previous_source_sha256":previous.get("source_sha256"),"new_source_sha256":fingerprint},"Source changed across restart; stale worker result invalidated")
                state["pending"]=None;store.set_state("supervisor",state)
            selector=ExperimentSelector(store.get_state("selector",{}));promotions=0
            previous_handlers={}
            if __import__('threading').current_thread() is __import__('threading').main_thread():
                for sig in (signal.SIGINT,signal.SIGTERM):
                    previous_handlers[sig]=signal.signal(sig,lambda *_:setattr(self,"stop",True))
            try:
                while not self.stop and (forever or completed<steps) and monotonic()-started<seconds:
                    if state["pending"] is None:
                        cursor=state["cursor"];kind=selector.select(cursor)
                        if kind=='frontier-complete':break
                        config={"kind":kind,"generation":selector.statistics.get(kind,{}).get("trials",0),"source_sha256":fingerprint}
                        if kind=="family":config["split_policy"]=store.get_state("split_policy",{})
                        ident=sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
                        state["pending"]={**config,"id":ident,"attempts":0}
                    experiment=state["pending"]
                    operation_started=monotonic()
                    if experiment.get("stage")=="result_ready":
                        result=store.get_state("worker_result")
                    elif experiment["attempts"]>=3:
                        result={"status":"failed","failure_class":"F","reason":"Three interrupted/failed attempts; fallback to next species"}
                    else:
                        experiment["attempts"]+=1
                        self.current_worker_timeout=max(.01,min(self.worker_timeout,seconds-(monotonic()-started)))
                        store.set_state("supervisor",state) # Durable execution intent BEFORE worker starts.
                        try:result=self.runner(dict(experiment))
                        except Exception as error:
                            category,retry=classify(error)
                            result={"status":"failed","failure_class":category,"reason":str(error)[:2048],
                                    "command":f"python -m nucleus_btc.nucleus.worker ({experiment['kind']})",
                                    "environment":{"python":sys.version.split()[0],"platform":sys.platform},
                                    "candidate_id":experiment["id"],"checkpoint":state["cursor"],"attempt":experiment["attempts"]}
                            store.put("DEAD",experiment,result,"Compressed recoverable failure")
                            if retry and experiment["attempts"]<3:
                                store.set_state("supervisor",state);continue
                    if not isinstance(result,dict):result={"status":"failed","failure_class":"A","reason":"Worker returned invalid result type"}
                    experiment["stage"]="result_ready"
                    store.set_states({"worker_result":result,"supervisor":state})
                    if result.get("status")=="promotion_qualified":
                        try:
                            holdout=result.get("fresh_holdout") or {}
                            gates=(result.get("interpreter_parity",{}).get("passed"),result.get("parity",{}).get("passed"),
                                   holdout.get("passed"),holdout.get("headers_tested",0)>=16384,result.get("metrics",{}).get("ci95_low",0)>1.02)
                            if not all(gates):raise AssertionError("Supervisor rejected incomplete production promotion gates")
                            with ProcessLock(str(ROOT/"results"/"knowledge.sqlite")+".optimizer.lock"),KnowledgeStore(ROOT/"results"/"knowledge.sqlite") as production:
                                if production.get_state("promotion_receipt",{}).get("experiment_id")!=experiment["id"]:
                                    production.promote(result["config"],{**result["metrics"],"holdout":holdout},result["compared_against"],experiment["id"])
                            promotions+=1
                        except Exception as error:
                            category,_=classify(error);result={"status":"failed","failure_class":category,"reason":str(error)[:2048]}
                    kind="DEAD" if result.get("status") in ("DEAD","failed","resource_budget_collapsed","economic_budget_collapsed","economically_dominated") else "FRONTIER"
                    # Worker validation does not itself authorize a production replacement.
                    store.put(kind,{"species":experiment["kind"],"candidate_id":experiment["id"]},result,
                              result.get("reason","Finite exact experiment; production champion retained"))
                    state["history"]=(state["history"]+[{"id":experiment["id"],"kind":experiment["kind"],"status":result.get("status"),"attempts":experiment["attempts"]}])[-32:]
                    state["completed"]+=1;state["cursor"]+=1;state["pending"]=None;completed+=1
                    selector.observe(experiment["kind"],result,monotonic()-operation_started)
                    checkpoint={"supervisor":state,"selector":selector.statistics}
                    if experiment["kind"]=="family" and result.get("policy"):checkpoint["split_policy"]=result["policy"]
                    store.set_states(checkpoint)
                    store.consolidate()
                    atomic_json(self.directory/"checkpoint.json",state)
                store.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                # Bounding rows alone does not reclaim SQLite's historical pages.
                store.db.execute("VACUUM")
                report={"schema":1,"status":"stopped" if self.stop else "checkpointed","completed_this_run":completed,
                        "total_completed":state["completed"],"next_kind":selector.select(state["cursor"]),
                        "pending":state["pending"],"history":state["history"],"source_sha256":fingerprint,
                        "storage_bytes":sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file()),
                        "production_champion_modified":promotions>0,"selector_estimates":{k:selector.estimates(k) for k in KINDS},"live_pool_acceptance":False}
                atomic_json(self.directory/"latest.json",report);return report
            finally:
                for sig,handler in previous_handlers.items():signal.signal(sig,handler)
