"""Offline SV2 framing and standard-channel state, checked against the spec.

Not a live SV2 transport: authenticated encrypted handshake is still required.
No plaintext connection is offered as a substitute.
"""
from dataclasses import dataclass
from struct import pack,unpack
from ..bitcoin.block_header import BlockHeader
from ..bitcoin.target import UINT256_MAX,compact_to_target

@dataclass(frozen=True)
class Frame:
    extension_type:int
    message_type:int
    payload:bytes
    def encode(self):
        if not 0<=self.extension_type<=0xFFFF or not 0<=self.message_type<=255 or len(self.payload)>0xFFFFFF:raise ValueError("SV2 frame out of range")
        if self.extension_type&0x8000 and len(self.payload)<4:raise ValueError("Channel frame needs channel id")
        return pack("<HB",self.extension_type,self.message_type)+len(self.payload).to_bytes(3,"little")+self.payload
    @classmethod
    def decode(cls,data):
        if len(data)<6:raise ValueError("Truncated SV2 header")
        extension,kind=unpack("<HB",data[:3]);length=int.from_bytes(data[3:6],"little")
        if len(data)!=length+6:raise ValueError("SV2 frame length mismatch")
        result=cls(extension,kind,data[6:]);result.encode();return result

class FrameDecoder:
    def __init__(self,max_payload=1<<20):self.buffer=bytearray();self.max_payload=max_payload
    def feed(self,data):
        self.buffer.extend(data);frames=[]
        while len(self.buffer)>=6:
            length=int.from_bytes(self.buffer[3:6],"little")
            if length>self.max_payload:raise ValueError("SV2 payload exceeds configured bound")
            if len(self.buffer)<length+6:break
            frames.append(Frame.decode(bytes(self.buffer[:length+6])));del self.buffer[:length+6]
        return frames

@dataclass(frozen=True)
class SubmitSharesStandard:
    channel_id:int
    sequence_number:int
    job_id:int
    nonce:int
    ntime:int
    version:int
    def encode(self):return pack("<6I",self.channel_id,self.sequence_number,self.job_id,self.nonce,self.ntime,self.version)
    @classmethod
    def decode(cls,data):
        if len(data)!=24:raise ValueError("Standard share must contain six uint32 fields")
        return cls(*unpack("<6I",data))

@dataclass(frozen=True)
class StandardJob:
    job_id:int
    version:int
    merkle_root:bytes
    ntime_start:int|None
    target:int|None = None

class StandardChannel:
    def __init__(self,channel_id,target):
        if not 0<=channel_id<=0xFFFFFFFF:raise ValueError("Invalid channel id")
        self.channel_id=channel_id;self.jobs={};self.active=None;self.previous=None;self.sequence=0;self.set_target(target)
    def set_target(self,target):
        if not 0<target<=UINT256_MAX:raise ValueError("Invalid channel target")
        self.target=target
    def new_job(self,job:StandardJob):
        from dataclasses import replace
        if not 0<=job.job_id<=0xFFFFFFFF or not 0<=job.version<=0xFFFFFFFF or len(job.merkle_root)!=32:raise ValueError("Invalid standard job")
        if job.job_id in self.jobs:raise ValueError("Duplicate live job id")
        if len(self.jobs)>=128:raise ValueError("Channel job budget exceeded; upstream must retire jobs")
        if job.ntime_start is not None:
            if self.previous is None:raise ValueError("Active job requires SetNewPrevHash state")
            if job.ntime_start<self.previous[1]:raise ValueError("Job ntime_start below last activation")
            job=replace(job,target=self.target);self.active=job.job_id
        self.jobs[job.job_id]=job
    def activate(self,job_id,prev_hash,ntime_start,bits):
        from dataclasses import replace
        if len(prev_hash)!=32 or not 0<=ntime_start<=0xFFFFFFFF:raise ValueError("Invalid previous hash activation")
        compact_to_target(bits)
        job=self.jobs.get(job_id)
        if job is None or job.ntime_start is not None:raise ValueError("Activation needs a matching future job")
        active=replace(job,ntime_start=ntime_start,target=self.target)
        self.jobs={job_id:active};self.active=job_id;self.previous=(prev_hash,ntime_start,bits)
    def work(self):
        if self.active is None or self.previous is None:raise ValueError("No activated standard job")
        job=self.jobs[self.active];prev,_,bits=self.previous
        return BlockHeader(job.version,prev,job.merkle_root,job.ntime_start,bits,0),job.target
    def submission(self,nonce,ntime,version):
        h,target=self.work();job=self.jobs[self.active]
        if ntime<job.ntime_start:raise ValueError("Submission before job ntime_start")
        # Conservative: this codec submits only the supplied version, not unnegotiated rolling.
        if version!=h.version:raise ValueError("Version rolling not enabled in offline codec")
        candidate=BlockHeader(version,h.previous_hash,h.merkle_root,ntime,h.bits,nonce)
        from ..bitcoin.target import meets_target
        if not meets_target(candidate.digest(),target):raise ValueError("Share fails CPU validation")
        result=SubmitSharesStandard(self.channel_id,self.sequence,self.active,nonce,ntime,version)
        self.sequence=(self.sequence+1)&0xFFFFFFFF;return result
