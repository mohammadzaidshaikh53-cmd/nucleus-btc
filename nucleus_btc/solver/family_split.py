"""Overflow retries split the same exact workspace without dropping solutions."""
from dataclasses import dataclass
from time import perf_counter
from ..gpu.backend import ResultOverflow,ScanResult,validate_range

def scan_with_split(backend,header,start,count,target,capacity=4096):
    validate_range(header,start,count);begun=perf_counter();pending=[(start,count)];found=[];kernel_seconds=0.;retried=0
    while pending:
        offset,size=pending.pop()
        try:result=backend.scan(header,offset,size,target,capacity)
        except ResultOverflow:
            if size<=1:raise
            retried+=1;half=size//2
            pending.extend([(offset+half,size-half),(offset,half)])
        else:
            found.extend(result.nonces);kernel_seconds+=result.kernel_seconds or 0.
    return {"result":ScanResult(sorted(found),count,perf_counter()-begun,kernel_seconds or None),"overflow_retries":retried,
            "retry_kernel_time_included_in_wall_time":True}
