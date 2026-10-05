import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from .bitcoin.block_header import BlockHeader,GENESIS
from .bitcoin.target import compact_to_target,meets_target
from .gpu.backend import get_backend,BackendUnavailable,ResultOverflow

ROOT=Path(__file__).resolve().parents[1]

def dump(value,path=None):
    encoded=json.dumps(value,indent=2,allow_nan=False)
    if path:
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists():
            from time import time_ns
            p=p.with_name(p.stem+"-"+str(time_ns())+p.suffix);print(f"Preserved previous result; saving {p}",file=sys.stderr)
        with p.open("x",encoding="utf-8") as stream:stream.write(encoded+"\n")
    print(encoded)

def header_value(text):
    return GENESIS if text is None else BlockHeader.parse(bytes.fromhex(text))

def main(argv=None):
    parser=argparse.ArgumentParser(description="Nucleus-BTC exact PoW research toolkit")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("doctor",help="Discover local compilers and GPU drivers")
    h=sub.add_parser("hash");h.add_argument("header",nargs="?")
    v=sub.add_parser("verify");v.add_argument("--backend",default="opencl",choices=["hashlib","native","native-full","opencl","hip"]);v.add_argument("--samples",type=int,default=4096);v.add_argument("--output")
    for name in ["benchmark","scaling"]:
        b=sub.add_parser(name);b.add_argument("--backend",default="opencl",choices=["hashlib","native","native-full","opencl"]);b.add_argument("--output");b.add_argument("--champion",action="store_true");b.add_argument("--repeats",type=int,default=5)
        if name=="benchmark":
            b.add_argument("--count",type=int,default=1<<20);b.add_argument("--seconds",type=float,default=.2);b.add_argument("--watts",type=float)
    o=sub.add_parser("optimize");o.add_argument("--store",default=str(ROOT/"results"/"knowledge.sqlite"));o.add_argument("--count",type=int,default=1<<20);o.add_argument("--seconds",type=float,default=.12);o.add_argument("--output")
    o.add_argument("--candidates",type=int,default=16)
    e=sub.add_parser("evolve");e.add_argument("--steps",type=int,default=16);e.add_argument("--seconds",type=float,default=3600);e.add_argument("--forever",action="store_true");e.add_argument("--directory",default=str(ROOT/"results"/"evolution"));e.add_argument("--output")
    f=sub.add_parser("family");f.add_argument("--count",type=int,default=65536);f.add_argument("--backend",default="native",choices=["native","opencl","hashlib"]);f.add_argument("--output")
    pl=sub.add_parser("planes");pl.add_argument("--nonce-bits",type=int,default=8);pl.add_argument("--output")
    c=sub.add_parser("confirm");c.add_argument("--store",default=str(ROOT/"results"/"knowledge.sqlite"));c.add_argument("--count",type=int,default=1<<22);c.add_argument("--seconds",type=float,default=.5);c.add_argument("--output")
    s=sub.add_parser("scan");s.add_argument("--backend",default="opencl",choices=["hashlib","native","native-full","opencl"]);s.add_argument("--header");s.add_argument("--start",type=int);s.add_argument("--count",type=int,default=1024);s.add_argument("--target",help="Full 256-bit target in conventional big-endian hex");s.add_argument("--capacity",type=int,default=4096);s.add_argument("--champion",action="store_true");s.add_argument("--output")
    sub.add_parser("status")
    p=sub.add_parser("portfolio");p.add_argument("--output");p.add_argument("--store",default=str(ROOT/"results"/"knowledge.sqlite"))
    r=sub.add_parser("research");r.add_argument("--nonce-bits",type=int,default=4);r.add_argument("--max-nodes",type=int,default=20000);r.add_argument("--representation",choices=["dag","bdd","anf","hybrid-dag","hybrid-bdd"],default="dag");r.add_argument("--output")
    sm=sub.add_parser("smt");sm.add_argument("--nonce-bits",type=int,default=4);sm.add_argument("--timeout-ms",type=int,default=250);sm.add_argument("--templates",action="store_true");sm.add_argument("--output")
    rs=sub.add_parser("representation-scaling");rs.add_argument("--repeats",type=int,default=3);rs.add_argument("--hybrids",action="store_true");rs.add_argument("--output")
    m=sub.add_parser("mine");m.add_argument("--config",required=True);m.add_argument("--seconds",type=float,default=60);m.add_argument("--output")
    args=parser.parse_args(argv)
    try:
        if args.command=="doctor":
            import shutil
            from .gpu.opencl import devices
            ds=[];error=None
            try:
                ds=[{k:v for k,v in asdict(d).items() if k!="handle"} for d in devices()]
            except Exception as e:error=str(e)
            native=any((ROOT/"build"/n).is_file() for n in ["nucleus_core.dll","libnucleus_core.so"])
            dump({"python":sys.version.split()[0],"native_library_built":native,"opencl_devices":ds,"opencl_error":error,"hipcc":shutil.which("hipcc"),"pool_configured":(ROOT/"config"/"local.json").exists()});return 0
        if args.command=="hash":
            h=header_value(args.header);dump({"header":h.serialize().hex(),"raw_sha256d":h.digest().hex(),"bitcoin_display_hash":h.display_hash(),"meets_encoded_target":h.has_valid_pow()});return 0
        if args.command=="status":
            from .nucleus.memory import KnowledgeStore
            with KnowledgeStore(ROOT/"results"/"knowledge.sqlite") as store:dump({"champion":store.get_state("champion"),"records":store.records(),"live_pool_result":"not established by offline measurements"})
            return 0
        if args.command=="optimize":
            from .nucleus.champion import optimize
            dump(optimize(args.store,args.count,args.seconds,progress=lambda msg:print(msg,file=sys.stderr),number=args.candidates),args.output);return 0
        if args.command=="evolve":
            from .nucleus.supervisor import Supervisor
            dump(Supervisor(args.directory).run(args.steps,args.seconds,args.forever),args.output);return 0
        if args.command=="family":
            from .solver.adaptive import solve_family
            with get_backend(args.backend) as engine:dump(solve_family(engine,GENESIS.serialize(),0,args.count,compact_to_target(GENESIS.bits)),args.output)
            return 0
        if args.command=="planes":
            from .representations.plane_sha import plane_family
            dump(plane_family(GENESIS.serialize(),0,args.nonce_bits),args.output);return 0
        if args.command=="confirm":
            from .nucleus.champion import confirm_champion
            dump(confirm_champion(args.store,args.count,args.seconds),args.output);return 0
        if args.command=="research":
            from .representations.symbolic import symbolic_experiment
            dump(symbolic_experiment(args.nonce_bits,args.max_nodes,args.representation),args.output);return 0
        if args.command=="smt":
            from .solver.smt import smt_family,prove_templates
            dump(prove_templates() if args.templates else smt_family(GENESIS.serialize(),nonce_bits=args.nonce_bits,timeout_ms=args.timeout_ms),args.output);return 0
        if args.command=="representation-scaling":
            from .solver.scaling import representation_scaling
            options={"representations":("hybrid-dag","hybrid-bdd")} if args.hybrids else {}
            dump(representation_scaling(repeats=args.repeats,progress=lambda m:print(m,file=sys.stderr),**options),args.output);return 0
        if args.command=="portfolio":
            from .nucleus.experiment_selector import run_portfolio
            dump(run_portfolio(args.store),args.output);return 0
        if args.command=="mine":
            config=json.loads(Path(args.config).read_text(encoding="utf-8"))
            if config.get("pool_url","").startswith("stratum2+tcp:"):
                from .protocol.sv2_client import run_miner
            else:
                from .protocol.stratum_v1 import run_miner
            dump(run_miner(config,args.seconds),args.output);return 0
        kwargs={}
        if getattr(args,"champion",False) and args.backend=="opencl":
            from .nucleus.memory import KnowledgeStore
            with KnowledgeStore(ROOT/"results"/"knowledge.sqlite") as store:kwargs=store.get_state("champion",{}).get("config",{})
        with get_backend(args.backend,**kwargs) as backend:
            if args.command=="verify":
                from .verify.parity import verify_backend
                dump(verify_backend(backend,args.samples),args.output)
            elif args.command=="benchmark":
                from .benchmark import benchmark
                dump(benchmark(backend,args.count,args.repeats,args.seconds,args.watts),args.output)
            elif args.command=="scaling":
                from .benchmark import family_scaling
                dump(family_scaling(backend,repeats=args.repeats),args.output)
            elif args.command=="scan":
                h=header_value(args.header);start=max(0,h.nonce-args.count//2) if args.start is None else args.start
                target=compact_to_target(h.bits) if args.target is None else int(args.target,16)
                result=backend.scan(h.serialize(),start,args.count,target,args.capacity)
                solutions=[]
                for n in result.nonces:
                    candidate=h.with_nonce(n)
                    if not meets_target(candidate.digest(),target):raise AssertionError("CPU rejected GPU solution")
                    solutions.append({"nonce":n,"hash":candidate.display_hash(),"header":candidate.serialize().hex()})
                dump({**asdict(result),"verified_solutions":solutions,"source":"historical genesis fixture" if args.header is None else "supplied header","live_pool_accepted":False},args.output)
        return 0
    except (ValueError,RuntimeError,OSError,AssertionError) as e:
        print(f"ERROR: {type(e).__name__}: {e}",file=sys.stderr);return 1

if __name__=="__main__":raise SystemExit(main())
