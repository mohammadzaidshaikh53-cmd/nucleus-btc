"""Durable atomic JSON and an OS-owned lock released automatically on crash."""
import json
import os
import tempfile
from pathlib import Path

def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    encoded=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
    fd,name=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
        if os.name!="nt":
            directory=os.open(path.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
    finally:
        if os.path.exists(name):os.unlink(name)

class ProcessLock:
    def __init__(self,path):self.path=Path(path);self.stream=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=open(self.path,"a+b")
        if self.stream.seek(0,2)==0:self.stream.write(b"0");self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.stream.close();self.stream=None
            raise RuntimeError("Another supervisor owns this checkpoint") from None
        return self
    def __exit__(self,*args):
        if self.stream:
            self.stream.seek(0)
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
            self.stream.close();self.stream=None
