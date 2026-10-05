from dataclasses import asdict,replace
from hashlib import sha256
from math import log,exp
from random import Random
from statistics import median
from time import perf_counter
import platform
from datetime import datetime,timezone

def metadata(backend):
    device=getattr(backend,"device",None)
    fields={k:v for k,v in asdict(device).items() if k!="handle"} if device is not None else None
    identifier=sha256(str(sorted(fields.items())).encode()).hexdigest() if fields else None
    return {"timestamp_utc":datetime.now(timezone.utc).isoformat(),"python":platform.python_version(),
            "os":platform.platform(),"cpu":platform.processor(),"device":fields,"device_fingerprint":identifier,
            "physical_pci_id":None,"source_sha256":getattr(backend,"source_sha256",None),
            "build_options":getattr(backend,"build_options",None),"compilation_seconds":getattr(backend,"compilation_seconds",None),
            "gpu_clock_mhz":None,"gpu_temperature_c":None,"power_watts":None,"joules_per_terahash":None,
            "sensors":"not available; no TDP inference"}
from .bitcoin.block_header import GENESIS

def heldout_headers(seed=491,number=5):
    """Deterministic serialized header fixtures; NOT live pool jobs."""
    rng=Random(seed)
    return [replace(GENESIS,version=0x20000000|(i<<13),merkle_root=rng.randbytes(32),timestamp=GENESIS.timestamp+i).serialize() for i in range(number)]

def measure_window(backend,header,count,seconds=0.2):
    if not 0.01<=seconds<=60:raise ValueError("Measurement window must be 0.01..60 seconds")
    started=perf_counter();trials=0;kernel_seconds=0.;examined=0
    # Keep the nonce space unique in each timing window and roll a fixture when exhausted.
    start=0;current=header
    while perf_counter()-started<seconds or not trials:
        if start+count>1<<32:
            current=current[:36]+sha256(current[36:68]).digest()+current[68:];start=0
        result=backend.scan(current,start,count,1)
        examined+=result.examined;kernel_seconds+=result.kernel_seconds or 0.;trials+=1;start+=count
    wall=perf_counter()-started
    return {"hashes":examined,"seconds":wall,"hashes_per_second":examined/wall,"iterations":trials,
            "batch_size":count,"fixture_sha256":sha256(header).hexdigest(),"host_and_queue_seconds":max(0,wall-kernel_seconds) if kernel_seconds else None,
            "kernel_seconds":kernel_seconds or None,"kernel_hashes_per_second":examined/kernel_seconds if kernel_seconds else None}

def benchmark(backend,count=1<<20,repeats=5,seconds=0.2,watts=None):
    if not 3<=repeats<=31:raise ValueError("Need 3..31 repeats")
    if watts is not None and watts<=0:raise ValueError("Power must be positive")
    jobs=heldout_headers(number=repeats)
    warmup_seconds=min(2.,seconds*3)
    measure_window(backend,jobs[0],count,warmup_seconds)
    samples=[measure_window(backend,h,count,seconds) for h in jobs]
    hps=median(s["hashes_per_second"] for s in samples)
    return {"schema":2,"metadata":metadata(backend),"batch_size":count,"backend":backend.name,"config":getattr(backend,"config",{}),"device":getattr(getattr(backend,"device",None),"name",platform.processor()),
            "work_source":"held-out serialized header fixtures, no pool acceptance", "hashes_per_second":hps,"gh_per_second":hps/1e9,
            "steady_state_end_to_end":True,"startup_compilation_excluded":True,"warmup_seconds":warmup_seconds,"power_watts":watts,
            "power_source":"user-provided whole-system measurement" if watts is not None else "unmeasured",
            "joules_per_terahash":watts*1e12/hps if watts is not None else None,"samples":samples}

def paired_confidence(ratios,seed=79,resamples=2000):
    if len(ratios)<5 or any(r<=0 for r in ratios):raise ValueError("Need at least five positive paired ratios")
    rng=Random(seed);logs=[log(r) for r in ratios];values=[]
    for _ in range(resamples):values.append(exp(sum(rng.choice(logs) for _ in logs)/len(logs)))
    values.sort()
    return {"geometric_speedup":exp(sum(logs)/len(logs)),"ci95_low":values[int(resamples*.025)],"ci95_high":values[int(resamples*.975)],"pairs":len(ratios),"method":"paired bootstrap; timing noise only, not all systematic effects"}

def family_scaling(backend,powers=(8,10,12,14,16,18,20,22,23,24),repeats=5):
    """Fit large-batch scan costs, plus materialized digest costs for comparison."""
    from time import perf_counter
    if repeats<3 or len(powers)<3 or any(not 1<=p<=24 for p in powers):raise ValueError("Need 3 repeats and at least 3 bounded batch sizes")
    rows=[];header=heldout_headers(number=1)[0]
    for p in powers:
        count=1<<p;backend.scan(header,0,count,1)
        costs=[]
        for r in range(repeats):
            t=perf_counter();backend.scan(header,r*count,count,1);costs.append(perf_counter()-t)
        rows.append({"count":count,"median_seconds":median(costs),"seconds_per_candidate":median(costs)/count,"samples":costs})
    # Fixed launch/transfer overhead can make a linear GPU kernel appear sublinear.
    xs=[log(r["count"]) for r in rows[-3:]];ys=[log(r["median_seconds"]) for r in rows[-3:]]
    xm=sum(xs)/len(xs);ym=sum(ys)/len(ys)
    denominator=sum((x-xm)**2 for x in xs)
    alpha=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/denominator if denominator else None
    return {"backend":backend.name,"rows":rows,"observed_alpha_largest_three":alpha,
            "algorithmic_complexity":"linear independent SHA-256d with shared standard midstate",
            "evidence_of_cryptanalytic_sublinear_work":False,
            "caution":"Launch overhead, occupancy and batching affect observed alpha. A slope below 1 here is not a cryptanalytic discovery."}
