"""Retry a failed GPU range on independently verified CPU, without losing work."""
from ..gpu.backend import get_backend,BackendUnavailable
from ..gpu.opencl import OpenCLError
from ..verify.parity import verify_backend

class RecoveringBackend:
    def __init__(self,engine,reasons):self.engine=engine;self.reasons=reasons
    @property
    def name(self):return self.engine.name
    def scan(self,*args,**kwargs):
        try:return self.engine.scan(*args,**kwargs)
        except OpenCLError:
            self.engine.close();self.reasons.append({"backend":"opencl","status":"runtime_failure","action":"same range retried on verified CPU"})
            for name in ("native","hashlib"):
                try:replacement=get_backend(name)
                except BackendUnavailable:continue
                try:verify_backend(replacement,256)
                except Exception:replacement.close();raise
                self.engine=replacement;return self.engine.scan(*args,**kwargs)
            raise BackendUnavailable("No verified CPU fallback for failed GPU range")
    def close(self):self.engine.close()
