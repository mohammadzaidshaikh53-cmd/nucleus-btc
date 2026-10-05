"""Bounded Stratum V1 compatibility client alongside authenticated SV2.

No network connections happen on import. Pool settings are supplied explicitly.
"""
import json
import select
import socket
import ssl
from collections import deque,OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic,sleep
from datetime import datetime,timezone
from urllib.parse import urlparse
from ..bitcoin.block_header import BlockHeader
from ..bitcoin.merkle import apply_coinbase_branch
from ..bitcoin.target import difficulty_target,meets_target,compact_to_target
from ..gpu.backend import get_backend,BackendUnavailable,ResultOverflow
from ..verify.parity import verify_backend

class ProtocolError(RuntimeError):pass
class ReconnectRequested(ProtocolError):pass

class JsonLineDecoder:
    def __init__(self,max_line=1<<20):self.buffer=bytearray();self.max_line=max_line
    def feed(self,data):
        self.buffer.extend(data);out=[]
        while b"\n" in self.buffer:
            index=self.buffer.index(10)
            if index>self.max_line:raise ProtocolError("Stratum line exceeds memory bound")
            line=bytes(self.buffer[:index]);del self.buffer[:index+1]
            if line.strip():
                try:obj=json.loads(line,parse_float=Decimal)
                except (ValueError,UnicodeError) as e:raise ProtocolError("Malformed Stratum JSON") from e
                if not isinstance(obj,dict):raise ProtocolError("Stratum message must be an object")
                out.append(obj)
        if len(self.buffer)>self.max_line:raise ProtocolError("Incomplete line exceeds memory bound")
        return out

def decode_hex(value,size=None):
    if not isinstance(value,str) or len(value)%2:raise ProtocolError("Expected even-length hexadecimal string")
    try:raw=bytes.fromhex(value)
    except ValueError as e:raise ProtocolError("Malformed hex") from e
    if size is not None and len(raw)!=size:raise ProtocolError("Unexpected field length")
    return raw

def word_swap(raw):
    if len(raw)%4:raise ProtocolError("Word swap requires 4-byte words")
    return b"".join(raw[i:i+4][::-1] for i in range(0,len(raw),4))

@dataclass(frozen=True)
class MiningJob:
    job_id:str
    previous:bytes
    coinbase_prefix:bytes
    coinbase_suffix:bytes
    branch:tuple[bytes,...]
    version:int
    bits:int
    timestamp:int
    clean:bool
    target:int
    extranonce1:bytes
    extranonce2_size:int
    generation:int
    @classmethod
    def from_notify(cls,params,target,extranonce1,size,generation):
        if not isinstance(params,list) or len(params)!=9:raise ProtocolError("mining.notify needs 9 fields")
        job_id,prev,prefix,suffix,branch,version,bits,ntime,clean=params
        if not isinstance(job_id,str) or len(job_id)>256 or not isinstance(clean,bool) or not isinstance(branch,list) or len(branch)>64:raise ProtocolError("Invalid job metadata")
        if not 1<=size<=32:raise ProtocolError("Extranonce2 size must be 1..32 bytes")
        previous=word_swap(decode_hex(prev,32))
        ver=int.from_bytes(decode_hex(version,4),"big");nbits=int.from_bytes(decode_hex(bits,4),"big");timestamp=int.from_bytes(decode_hex(ntime,4),"big")
        compact_to_target(nbits)
        return cls(job_id,previous,decode_hex(prefix),decode_hex(suffix),tuple(decode_hex(x,32) for x in branch),ver,nbits,timestamp,clean,target,extranonce1,size,generation)
    def header(self,extranonce2):
        if len(extranonce2)!=self.extranonce2_size:raise ProtocolError("Incorrect extranonce2 length")
        coinbase=self.coinbase_prefix+self.extranonce1+extranonce2+self.coinbase_suffix
        # V1 pools provide a stripped coinbase for txid hashing; reject witness marker/flag.
        if len(coinbase)>=6 and coinbase[4:6]==b"\x00\x01":raise ProtocolError("Witness-serialized coinbase requires stripping; this adapter expects pool-provided non-witness parts")
        return BlockHeader(self.version,self.previous,apply_coinbase_branch(coinbase,list(self.branch)),self.timestamp,self.bits,0)
    def submission(self,worker,extranonce2,nonce):
        h=self.header(extranonce2).with_nonce(nonce)
        if not meets_target(h.digest(),self.target):raise ProtocolError("Share failed independent CPU validation")
        return [worker,self.job_id,extranonce2.hex(),f"{h.timestamp:08x}",f"{nonce:08x}"]

class StratumClient:
    def __init__(self,sock,worker,password="x",timeout=15):
        self.socket=sock;self.worker=worker;self.password=password;self.timeout=timeout
        self.decoder=JsonLineDecoder();self.next_id=1;self.responses={};self.pending={};self.jobs={};self.latest=None
        self.target=difficulty_target(1);self.extranonce1=b"";self.extranonce2_size=0;self.generation=0;self.authorized=False
        self.stats={"submitted":0,"accepted":0,"rejected":0,"stale_discarded":0,"unknown_notifications":0}
        self.share_evidence={};self.accepted_evidence=[];self.examined=0;self.submission_keys={}
    def send(self,method,params):
        if len(self.pending)>=128:raise ProtocolError("Too many unacknowledged requests")
        ident=self.next_id;self.next_id+=1
        self.socket.sendall((json.dumps({"id":ident,"method":method,"params":params},separators=(",",":"))+"\n").encode())
        self.pending[ident]=method;return ident
    def process(self,obj):
        try:self._process(obj)
        except (ValueError,TypeError,ArithmeticError) as error:raise ProtocolError("Invalid Stratum notification data") from error
    def _process(self,obj):
        method=obj.get("method")
        if method:
            params=obj.get("params",[])
            if not isinstance(method,str) or not isinstance(params,list):raise ProtocolError("Invalid Stratum notification")
            if method=="mining.set_difficulty":
                if len(params)!=1:raise ProtocolError("Invalid difficulty notification")
                self.target=difficulty_target(params[0]) # Applies to subsequent jobs, not existing jobs.
            elif method=="mining.set_extranonce":
                if len(params)!=2 or type(params[1]) is not int or not 1<=params[1]<=32:raise ProtocolError("Invalid extranonce update")
                self.extranonce1=decode_hex(params[0]);self.extranonce2_size=params[1];self.generation+=1;self.jobs.clear();self.latest=None
            elif method=="mining.notify":
                clean=params[-1] if isinstance(params,list) and params else False
                if clean:self.generation+=1;self.jobs.clear()
                job=MiningJob.from_notify(params,self.target,self.extranonce1,self.extranonce2_size,self.generation)
                if len(self.jobs)>=64:self.jobs.pop(next(iter(self.jobs)))
                self.jobs[job.job_id]=job;self.latest=job
            elif method=="client.reconnect":raise ReconnectRequested("Pool requested reconnect using the configured endpoint")
            else:self.stats["unknown_notifications"]+=1
            return
        ident=obj.get("id")
        if ident is not None and (not isinstance(ident,int) or isinstance(ident,bool)):raise ProtocolError("Malformed Stratum response id")
        if ident not in self.pending:return
        request=self.pending.pop(ident)
        if request=="mining.submit":
            if not isinstance(obj.get("result"),bool) and obj.get("error") is None:raise ProtocolError("Malformed share acknowledgement")
            accepted=obj.get("result") is True and obj.get("error") is None
            self.stats["accepted" if accepted else "rejected"]+=1
            evidence=self.share_evidence.pop(ident,None)
            if accepted and evidence:
                evidence.update(timestamp_utc=datetime.now(timezone.utc).isoformat(),pool_response={"id":ident,"result":True,"error":None})
                self.accepted_evidence=(self.accepted_evidence+[evidence])[-32:]
        else:
            # A subscribe reply and first notify may arrive in the same recv.
            # Install workspace parameters before processing later messages in that recv.
            if request=="mining.subscribe" and obj.get("error") is None:
                result=obj.get("result")
                if not isinstance(result,list) or len(result)!=3 or type(result[2]) is not int or not 1<=result[2]<=32:raise ProtocolError("Invalid subscription result")
                self.extranonce1=decode_hex(result[1]);self.extranonce2_size=result[2]
            if len(self.responses)>=128:raise ProtocolError("Response memory bound exceeded")
            self.responses[ident]=obj
    def pump(self,timeout=0):
        # SSLSocket may have decrypted bytes pending even when select is not readable.
        pending=getattr(self.socket,"pending",lambda:0)()
        if not pending and not select.select([self.socket],[],[],timeout)[0]:return False
        data=self.socket.recv(65536)
        if not data:raise ProtocolError("Pool disconnected")
        for obj in self.decoder.feed(data):self.process(obj)
        return True
    def request(self,method,params):
        ident=self.send(method,params);deadline=monotonic()+self.timeout
        while ident not in self.responses:
            remaining=deadline-monotonic()
            if remaining<=0:raise ProtocolError(f"{method} timed out")
            self.pump(min(remaining,.2))
        obj=self.responses.pop(ident)
        if obj.get("error") is not None:raise ProtocolError(f"{method} rejected by pool")
        return obj.get("result")
    def handshake(self):
        result=self.request("mining.subscribe",["Nucleus-BTC/0.1.0"])
        if not isinstance(result,list) or len(result)!=3 or not isinstance(result[2],int) or not 1<=result[2]<=32:raise ProtocolError("Invalid subscription result")
        self.extranonce1=decode_hex(result[1]);self.extranonce2_size=result[2]
        if self.request("mining.authorize",[self.worker,self.password]) is not True:raise ProtocolError("Worker authorization denied")
        self.authorized=True
    def submit(self,job,extranonce2,nonce):
        if not self.authorized:raise ProtocolError("Cannot submit before authorization")
        if self.jobs.get(job.job_id)!=job or job.generation!=self.generation:
            self.stats["stale_discarded"]+=1;return False
        # Fast scanners can fill the request window before the pool thread responds.
        # Wait for acknowledgements without increasing the bounded pending queue.
        deadline=monotonic()+self.timeout
        while len(self.pending)>=128:
            remaining=deadline-monotonic()
            if remaining<=0:raise ProtocolError("Share acknowledgement timed out while waiting for request capacity")
            self.pump(min(remaining,.2))
        # Waiting can also deliver a replacement job, making this candidate stale.
        if self.jobs.get(job.job_id)!=job or job.generation!=self.generation:
            self.stats["stale_discarded"]+=1;return False
        params=job.submission(self.worker,extranonce2,nonce)
        candidate=job.header(extranonce2).with_nonce(nonce)
        from ..oracle.sha256 import sha256d
        digest=sha256d(candidate.serialize())
        if not meets_target(digest,job.target):raise ProtocolError("Share failed immutable oracle")
        key=candidate.serialize()
        if key in self.submission_keys:raise ProtocolError("Duplicate V1 share suppressed")
        ident=self.send("mining.submit",params)
        self.share_evidence[ident]={"job_id":job.job_id,"nonce":nonce,"header":candidate.serialize().hex(),"digest":digest.hex(),"target":f"{job.target:064x}"}
        self.submission_keys[key]=None
        if len(self.submission_keys)>4096:self.submission_keys.pop(next(iter(self.submission_keys)))
        self.stats["submitted"]+=1;return True
    def close(self):self.socket.close()

def mine_session(client,backend,seconds=60,batch_size=1<<20):
    if not 0<seconds<=86400 or not 1<=batch_size<=1<<24:raise ValueError("Invalid session budget")
    started=monotonic();job=None;nonce=0;extranonce_number=0;hashes=0;cursors=OrderedDict();identity=None
    client.handshake()
    while monotonic()-started<seconds:
        # Drain a bounded amount of pending traffic; avoid starving mining on chatty upstreams.
        for _ in range(32):
            if not client.pump(0):break
        if client.latest is None:
            client.pump(min(.1,max(0,seconds-(monotonic()-started))));continue
        if client.latest!=job:
            job=client.latest;identity=job.header(bytes(job.extranonce2_size)).serialize()[:76]
            nonce,extranonce_number=cursors.get(identity,(0,0));cursors[identity]=(nonce,extranonce_number);cursors.move_to_end(identity)
            if len(cursors)>64:cursors.popitem(last=False)
        if nonce>=1<<32:
            extranonce_number+=1;nonce=0
        if extranonce_number>=1<<(8*job.extranonce2_size):raise ProtocolError("Extranonce workspace exhausted; await a new pool job")
        extranonce2=extranonce_number.to_bytes(job.extranonce2_size,"little")
        header=job.header(extranonce2);count=min(batch_size,(1<<32)-nonce)
        try:scan=backend.scan(header.serialize(),nonce,count,job.target)
        except ResultOverflow:
            if batch_size==1:raise
            batch_size=max(1,batch_size//2);continue # Retry the same range; never drop candidates.
        hashes+=scan.examined
        client.examined=hashes
        for _ in range(32):
            if not client.pump(0):break
        for found in scan.nonces:client.submit(job,extranonce2,found)
        nonce+=count
        cursors[identity]=(nonce,extranonce_number)
    # Resolve outstanding share acknowledgements briefly; unacknowledged shares never count as accepted.
    deadline=monotonic()+min(2,client.timeout)
    while any(method=="mining.submit" for method in client.pending.values()) and monotonic()<deadline:client.pump(.05)
    elapsed=monotonic()-started
    return {"protocol":"stratum-v1","examined":hashes,"seconds":elapsed,"hashes_per_second":hashes/elapsed,**client.stats,
            "unacknowledged":sum(method=="mining.submit" for method in client.pending.values()),"accepted_evidence":client.accepted_evidence,"btc_balance":None}

def connect_pool(parsed,timeout=10):
    sock=socket.create_connection((parsed.hostname,parsed.port),timeout=timeout)
    try:
        return ssl.create_default_context().wrap_socket(sock,server_hostname=parsed.hostname) if parsed.scheme=="stratum+ssl" else sock
    except Exception:sock.close();raise

def run_miner(config,seconds=60):
    if not 0<seconds<=86400:raise ValueError("Live session must have a finite 0..86400 second budget")
    url=config.get("pool_url","");worker=config.get("worker","")
    if not url or not worker or "REPLACE" in url or "REPLACE" in worker:raise ValueError("Configure an actual Bitcoin pool URL and worker before live mining")
    parsed=urlparse(url)
    if parsed.scheme not in ("stratum+tcp","stratum+ssl") or not parsed.hostname or not parsed.port:raise ValueError("Expected stratum+tcp://host:port or stratum+ssl://host:port")
    if parsed.username or parsed.password:raise ValueError("Put credentials in worker/password fields, not the URL")
    chosen=config.get("backend","opencl");backend=None;failures=[]
    if chosen not in ("opencl","native","native-full","hashlib"):raise ValueError("Live scan requires OpenCL, native or hashlib backend")
    for name in dict.fromkeys([chosen,"native","hashlib"]):
        try:backend=get_backend(name,**(config.get("gpu",{}) if name=="opencl" else {}))
        except BackendUnavailable as e:failures.append(str(e))
        else:
            try:verify_backend(backend,256)
            except Exception:backend.close();raise
            break
    if backend is None:raise BackendUnavailable("; ".join(failures))
    from .recovering_backend import RecoveringBackend
    backend=RecoveringBackend(backend,failures)
    sock=None;client=None;started=monotonic();sessions=[];totals={"submitted":0,"accepted":0,"rejected":0,"stale_discarded":0,"examined":0};evidence=[]
    try:
        for attempt in range(3):
            try:
                remaining=seconds-(monotonic()-started)
                if remaining<=0:break
                timeout=min(10,remaining);sock=connect_pool(parsed,timeout);client=StratumClient(sock,worker,config.get("password","x"),timeout=timeout)
                result=mine_session(client,backend,remaining,config.get("batch_size",1<<20))
                for key in totals:totals[key]+=result[key]
                evidence=(evidence+result["accepted_evidence"])[-32:]
                sessions.append({"attempt":attempt+1,"status":"completed","examined":result["examined"],"unacknowledged":result["unacknowledged"]})
                return {**result,**totals,"accepted_evidence":evidence,"backend":backend.name,"fallback_reasons":failures,"sessions":sessions}
            except (OSError,ProtocolError) as error:
                if client:
                    for key in totals:totals[key]+=client.examined if key=="examined" else client.stats[key]
                    evidence=(evidence+client.accepted_evidence)[-32:]
                # Server-provided error strings and credential-bearing configuration are not logged.
                sessions.append({"attempt":attempt+1,"status":"failed","failure_type":type(error).__name__,"old_job_state_discarded":True})
                if attempt<2:sleep(min(.5*(attempt+1),max(0,seconds-(monotonic()-started))))
            finally:
                if client:client.close();client=None;sock=None
                elif sock:sock.close();sock=None
        return {"protocol":"stratum-v1","status":"bounded_reconnect_exhausted",**totals,"accepted_evidence":evidence,
                "backend":backend.name,"fallback_reasons":failures,"sessions":sessions,"btc_balance":None}
    finally:
        if client:client.close()
        elif sock:sock.close()
        backend.close()
