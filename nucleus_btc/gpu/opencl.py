"""Dependency-free OpenCL 1.2 driver binding with explicit resource ownership."""
import ctypes as c
import ctypes.util
import sys
from dataclasses import dataclass,asdict
from pathlib import Path
from struct import pack,unpack
from time import perf_counter
from .backend import BackendUnavailable,ResultOverflow,ScanResult,validate_range,MAX_BATCH
from ..oracle.sha256 import header_midstate
from ..bitcoin.target import UINT256_MAX

P=c.c_void_p;U=c.c_uint32;S=c.c_size_t;Q=c.c_uint64;I=c.c_int32

class OpenCLError(RuntimeError):pass

def check(rc,operation):
    if rc:raise OpenCLError(f"{operation}: OpenCL status {rc}")

class API:
    def __init__(self):
        path="OpenCL.dll" if sys.platform=="win32" else ctypes.util.find_library("OpenCL")
        if not path:raise BackendUnavailable("OpenCL loader absent")
        try:self.lib=(c.WinDLL if sys.platform=="win32" else c.CDLL)(path)
        except OSError as e:raise BackendUnavailable(str(e)) from e
        signatures={
            "clGetPlatformIDs":(I,[U,c.POINTER(P),c.POINTER(U)]),
            "clGetDeviceIDs":(I,[P,Q,U,c.POINTER(P),c.POINTER(U)]),
            "clGetDeviceInfo":(I,[P,U,S,P,c.POINTER(S)]),
            "clCreateContext":(P,[P,U,c.POINTER(P),P,P,c.POINTER(I)]),
            "clCreateCommandQueue":(P,[P,P,Q,c.POINTER(I)]),
            "clCreateProgramWithSource":(P,[P,U,c.POINTER(c.c_char_p),c.POINTER(S),c.POINTER(I)]),
            "clBuildProgram":(I,[P,U,c.POINTER(P),c.c_char_p,P,P]),
            "clGetProgramBuildInfo":(I,[P,P,U,S,P,c.POINTER(S)]),
            "clCreateKernel":(P,[P,c.c_char_p,c.POINTER(I)]),
            "clCreateBuffer":(P,[P,Q,S,P,c.POINTER(I)]),
            "clSetKernelArg":(I,[P,U,S,P]),
            "clEnqueueNDRangeKernel":(I,[P,P,U,c.POINTER(S),c.POINTER(S),c.POINTER(S),U,c.POINTER(P),c.POINTER(P)]),
            "clEnqueueReadBuffer":(I,[P,P,U,S,S,P,U,c.POINTER(P),c.POINTER(P)]),
            "clFinish":(I,[P]),
            "clGetEventProfilingInfo":(I,[P,U,S,P,c.POINTER(S)]),
        }
        for n,(ret,args) in signatures.items():
            f=getattr(self.lib,n);f.restype=ret;f.argtypes=args;setattr(self,n,f)
        for kind in ("MemObject","Kernel","Program","CommandQueue","Context","Event"):
            n="clRelease"+kind;f=getattr(self.lib,n);f.restype=I;f.argtypes=[P];setattr(self,n,f)
    def info(self,device,field):
        n=S();check(self.clGetDeviceInfo(device,field,0,None,c.byref(n)),"device info length")
        out=c.create_string_buffer(n.value);check(self.clGetDeviceInfo(device,field,n.value,out,None),"device info")
        return out.raw

@dataclass
class Device:
    handle:int
    name:str
    vendor:str
    driver:str
    memory_bytes:int
    compute_units:int
    unified_memory:bool
    max_work_group:int
    vendor_id:int|None=None
    pci_address:str|None=None
    uuid:str|None=None

def devices(api=None):
    api=api or API();n=U();rc=api.clGetPlatformIDs(0,None,c.byref(n))
    if rc==-1001:return []
    check(rc,"platform count");platforms=(P*n.value)();check(api.clGetPlatformIDs(n,platforms,None),"platforms")
    found=[];seen=set()
    for platform in platforms:
        count=U();rc=api.clGetDeviceIDs(platform,4,0,None,c.byref(count))
        if rc==-1:continue
        check(rc,"GPU device count");ds=(P*count.value)();check(api.clGetDeviceIDs(platform,4,count,ds,None),"GPU devices")
        for d in ds:
            if d in seen:continue
            seen.add(d)
            text=lambda field:api.info(d,field).rstrip(b"\x00").decode("utf-8","replace")
            integer=lambda field:int.from_bytes(api.info(d,field),sys.byteorder)
            if not integer(0x1026):continue # This host binding requires little-endian GPU words.
            pci=None;uuid=None;extensions=text(0x1030).split()
            if "cl_khr_pci_bus_info" in extensions:
                try:
                    domain,bus,slot,function=unpack("<4I",api.info(d,0x410F));pci=f"{domain:04x}:{bus:02x}:{slot:02x}.{function}"
                except (OpenCLError,ValueError):pass
            if "cl_khr_device_uuid" in extensions:
                try:uuid=api.info(d,0x106A).hex()
                except OpenCLError:pass
            found.append(Device(d,text(0x102B),text(0x102C),text(0x102D),integer(0x101F),integer(0x1002),bool(integer(0x1035)),integer(0x1004),integer(0x1001),pci,uuid))
    # Some drivers expose the same board in multiple platforms; default favors discrete VRAM.
    return sorted(found,key=lambda d:(d.unified_memory,-d.memory_bytes,d.name))

class OpenCLBackend:
    name="opencl"
    def __init__(self,device_index=0,full_unroll=False,alt_boolean=False,local_size=64,ir_spec=None,ir_hash=None):
        self.api=API();ds=devices(self.api)
        if not 0<=device_index<len(ds):raise BackendUnavailable(f"No OpenCL GPU at index {device_index}")
        self.device=ds[device_index];self.context=None;self.queue=None;self.program=None;self.kernels={}
        self.local_size=local_size
        if local_size not in (32,64,128,256) or local_size>self.device.max_work_group:raise ValueError("Unsupported local workgroup size")
        self.config={"device_index":device_index,"full_unroll":bool(full_unroll),"alt_boolean":bool(alt_boolean),"local_size":local_size}
        err=I();d=P(self.device.handle)
        self._prepared={}
        try:
            self.context=self.api.clCreateContext(None,1,c.byref(d),None,None,c.byref(err));check(err.value,"context")
            self.queue=self.api.clCreateCommandQueue(self.context,d,2,c.byref(err));check(err.value,"profiling queue")
            source=(Path(__file__).with_name("exact.cl")).read_bytes()
            if ir_spec is not None:
                from ..ir.sha import compression_graph
                from ..ir.lower_opencl import kernel_source
                graph=compression_graph(ir_spec)
                if ir_hash is not None and ir_hash!=graph.fingerprint:raise ValueError("Stored champion IR hash differs from reconstructed graph")
                source=kernel_source(graph,source.decode()).encode()
                self.config.update(ir_spec=ir_spec,ir_hash=graph.fingerprint)
            from hashlib import sha256
            self.source_sha256=sha256(source).hexdigest()
            sources=(c.c_char_p*1)(source);lengths=(S*1)(len(source))
            self.program=self.api.clCreateProgramWithSource(self.context,1,sources,lengths,c.byref(err));check(err.value,"program")
            options=f"-cl-std=CL1.2 -DFULL_UNROLL={int(full_unroll)} -DALT_BOOLEAN={int(alt_boolean)}".encode()
            self.build_options=options.decode();build_started=perf_counter()
            rc=self.api.clBuildProgram(self.program,1,c.byref(d),options,None,None)
            self.compilation_seconds=perf_counter()-build_started
            if rc:
                n=S();self.api.clGetProgramBuildInfo(self.program,d,0x1183,0,None,c.byref(n));log=c.create_string_buffer(n.value)
                self.api.clGetProgramBuildInfo(self.program,d,0x1183,n.value,log,None)
                raise OpenCLError(f"Kernel build failed ({rc}): {log.value.decode('utf-8','replace')}")
            for name in ("hash_headers","hash_nonces","scan_nonces"):
                k=self.api.clCreateKernel(self.program,name.encode(),c.byref(err));check(err.value,"kernel "+name);self.kernels[name]=k
        except Exception:self.close();raise

    def _buffer(self,size,data=None):
        err=I();host=c.create_string_buffer(data) if data is not None else None
        flags=4|32 if data is not None else 1
        b=self.api.clCreateBuffer(self.context,flags,size,host,c.byref(err));check(err.value,"buffer")
        return b
    def _run(self,name,args,count):
        kernel=self.kernels[name]
        for i,(kind,value) in enumerate(args):
            obj=P(value) if kind=="buffer" else U(value)
            check(self.api.clSetKernelArg(kernel,i,c.sizeof(obj),c.byref(obj)),"kernel argument")
        global_size=S(((count+self.local_size-1)//self.local_size)*self.local_size);local=S(self.local_size);event=P()
        check(self.api.clEnqueueNDRangeKernel(self.queue,kernel,1,None,c.byref(global_size),c.byref(local),0,None,c.byref(event)),"enqueue "+name)
        try:
            check(self.api.clFinish(self.queue),"finish")
            begin=Q();end=Q()
            check(self.api.clGetEventProfilingInfo(event,0x1282,8,c.byref(begin),None),"event start")
            check(self.api.clGetEventProfilingInfo(event,0x1283,8,c.byref(end),None),"event end")
            return (end.value-begin.value)/1e9
        finally:self.api.clReleaseEvent(event)
    def _read(self,buffer,size):
        out=c.create_string_buffer(size);check(self.api.clEnqueueReadBuffer(self.queue,buffer,1,0,size,out,0,None,None),"read")
        return out.raw
    def _job(self,header):
        key=header[:76]
        if key not in self._prepared:
            if len(self._prepared)>=16:self._prepared.clear()
            self._prepared[key]=(pack("<8I",*header_midstate(header)),pack("<3I",*unpack(">3I",header[64:76])))
        return self._prepared[key]
    def hash_headers(self,headers):
        if not headers or len(headers)>MAX_BATCH or any(len(h)!=80 for h in headers):raise ValueError("Expected bounded 80-byte header batch")
        buffers=[]
        try:
            buffers.append(self._buffer(80*len(headers),b"".join(headers)));buffers.append(self._buffer(32*len(headers)))
            self._run("hash_headers",[("buffer",buffers[0]),("uint",len(headers)),("buffer",buffers[1])],len(headers))
            raw=self._read(buffers[1],32*len(headers));return [raw[i:i+32] for i in range(0,len(raw),32)]
        finally:
            for b in buffers:self.api.clReleaseMemObject(b)
    def hash_nonces(self,header,start,count):
        validate_range(header,start,count);mid,tail=self._job(header);buffers=[]
        try:
            buffers.append(self._buffer(32,mid));buffers.append(self._buffer(12,tail));buffers.append(self._buffer(32*count))
            self._run("hash_nonces",[("buffer",buffers[0]),("buffer",buffers[1]),("uint",start),("uint",count),("buffer",buffers[2])],count)
            raw=self._read(buffers[2],32*count);return [raw[i:i+32] for i in range(0,len(raw),32)]
        finally:
            for b in buffers:self.api.clReleaseMemObject(b)
    def scan(self,header,start,count,target,capacity=4096):
        validate_range(header,start,count)
        if not 0<target<=UINT256_MAX or not 0<capacity<=MAX_BATCH:raise ValueError("Invalid target/capacity")
        begun=perf_counter();mid,tail=self._job(header);buffers=[]
        try:
            buffers.append(self._buffer(32,mid));buffers.append(self._buffer(12,tail));buffers.append(self._buffer(32,target.to_bytes(32,"little")))
            buffers.append(self._buffer(4*capacity))
            zero=U(0)
            err=I()
            counter=self.api.clCreateBuffer(self.context,1|32,4,c.byref(zero),c.byref(err));check(err.value,"counter")
            buffers.append(counter)
            args=[("buffer",buffers[0]),("buffer",buffers[1]),("uint",start),("uint",count),("buffer",buffers[2]),("buffer",buffers[3]),("uint",capacity),("buffer",buffers[4])]
            seconds=self._run("scan_nonces",args,count);found=int.from_bytes(self._read(buffers[4],4),"little")
            if found>capacity:raise ResultOverflow(f"{found} solutions exceed buffer; retry a smaller batch")
            raw=self._read(buffers[3],4*found) if found else b""
            return ScanResult(sorted(unpack(f"<{found}I",raw)) if found else [],count,perf_counter()-begun,seconds)
        finally:
            for b in buffers:
                if b:self.api.clReleaseMemObject(b)
    def close(self):
        if not hasattr(self,"api"):return
        for k in getattr(self,"kernels",{}).values():self.api.clReleaseKernel(k)
        self.kernels={}
        for field,release in (("program","clReleaseProgram"),("queue","clReleaseCommandQueue"),("context","clReleaseContext")):
            obj=getattr(self,field,None)
            if obj:getattr(self.api,release)(obj);setattr(self,field,None)
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
