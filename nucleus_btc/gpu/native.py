import ctypes as c
import sys
from pathlib import Path
from time import perf_counter
from .backend import BackendUnavailable,ResultOverflow,ScanResult,validate_range,MAX_BATCH
from ..bitcoin.target import UINT256_MAX

class NativeBackend:
    def __init__(self,reuse=True):
        self.reuse=reuse;self.name="native" if reuse else "native-full"
        root=Path(__file__).resolve().parents[2]
        filename="nucleus_core.dll" if sys.platform=="win32" else "libnucleus_core.so"
        choices=[root/"build"/filename,root/"build"/"Release"/filename]
        lib=next((p for p in choices if p.is_file()),None)
        if not lib: raise BackendUnavailable("Native library absent; run scripts/build-native.ps1 or build with CMake")
        self.api=c.CDLL(str(lib))
        self.api.nb_hash_headers.argtypes=[c.c_void_p,c.c_uint64,c.c_void_p]
        self.api.nb_hash_nonces.argtypes=[c.c_void_p,c.c_uint32,c.c_uint64,c.c_void_p,c.c_int]
        self.api.nb_scan_nonces.argtypes=[c.c_void_p,c.c_uint32,c.c_uint64,c.c_void_p,c.c_void_p,c.c_uint32,c.POINTER(c.c_uint64),c.c_int]
        for n in ("nb_hash_headers","nb_hash_nonces","nb_scan_nonces"):getattr(self.api,n).restype=c.c_int
    def hash_headers(self,headers):
        if not headers or len(headers)>MAX_BATCH or any(len(h)!=80 for h in headers):raise ValueError("Expected bounded nonempty 80-byte header batch")
        data=c.create_string_buffer(b"".join(headers));out=c.create_string_buffer(32*len(headers))
        if self.api.nb_hash_headers(data,len(headers),out):raise RuntimeError("Native hashing failed")
        raw=out.raw
        return [raw[i:i+32] for i in range(0,len(raw),32)]
    def hash_nonces(self,header,start,count):
        validate_range(header,start,count);out=c.create_string_buffer(32*count)
        if self.api.nb_hash_nonces(c.create_string_buffer(header),start,count,out,int(self.reuse)):raise RuntimeError("Native nonce hashing failed")
        raw=out.raw
        return [raw[i:i+32] for i in range(0,len(raw),32)]
    def scan(self,header,start,count,target,capacity=4096):
        validate_range(header,start,count)
        if not 0<target<=UINT256_MAX or not 0<capacity<=MAX_BATCH:raise ValueError("Invalid target/capacity")
        begun=perf_counter();out=(c.c_uint32*capacity)();found=c.c_uint64()
        target_buffer=c.create_string_buffer(target.to_bytes(32,"little"))
        rc=self.api.nb_scan_nonces(c.create_string_buffer(header),start,count,target_buffer,out,capacity,c.byref(found),int(self.reuse))
        if rc:raise RuntimeError("Native scan failed")
        if found.value>capacity:raise ResultOverflow(f"{found.value} solutions exceed buffer; retry smaller batch")
        return ScanResult(list(out[:found.value]),count,perf_counter()-begun)
    def close(self):pass
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
