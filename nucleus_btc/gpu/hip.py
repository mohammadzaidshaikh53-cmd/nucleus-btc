import ctypes as c
import sys
from pathlib import Path
from .backend import BackendUnavailable,MAX_BATCH

class HIPBackend:
    name="hip"
    def __init__(self):
        root=Path(__file__).resolve().parents[2]
        filename="nucleus_hip.dll" if sys.platform=="win32" else "libnucleus_hip.so"
        paths=[root/"build"/filename,root/"build"/"Release"/filename]
        path=next((p for p in paths if p.is_file()),None)
        if path is None:raise BackendUnavailable("HIP backend needs SDK and CMake -DNUCLEUS_ENABLE_HIP=ON; OpenCL is the working fallback")
        self.api=c.CDLL(str(path));self.api.nb_hip_hash_headers.argtypes=[c.c_void_p,c.c_uint64,c.c_void_p];self.api.nb_hip_hash_headers.restype=c.c_int
    def hash_headers(self,headers):
        if not headers or len(headers)>MAX_BATCH or any(len(h)!=80 for h in headers):raise ValueError("Expected 80-byte header batch")
        data=c.create_string_buffer(b"".join(headers));out=c.create_string_buffer(32*len(headers))
        rc=self.api.nb_hip_hash_headers(data,len(headers),out)
        if rc:raise RuntimeError(f"HIP error: {rc}")
        raw=out.raw
        return [raw[i:i+32] for i in range(0,len(raw),32)]
    def close(self):pass
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
