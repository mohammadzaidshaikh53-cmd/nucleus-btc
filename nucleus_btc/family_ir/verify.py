from ..oracle.sha256 import sha256d
from .state import evaluate_family

def verify_family(family, **kwargs):
    digests, metrics = evaluate_family(family, **kwargs)
    for i, digest in enumerate(digests):
        candidate = family.candidate(i)
        if digest != candidate.digest() or digest != sha256d(candidate.serialize()):
            raise AssertionError(f"Full SHA256d family mismatch at {i}")
    return {"passed":True,"exhaustive_headers":family.count,**metrics}
