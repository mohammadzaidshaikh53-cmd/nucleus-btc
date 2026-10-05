"""Finite standard/extended SV2 mining lifecycle over authenticated transport."""
from dataclasses import dataclass,replace
from struct import pack
from time import monotonic,time
from datetime import datetime,timezone
from urllib.parse import urlparse
import socket
from . import sv2_wire as w
from .stratum_v1 import ProtocolError
from .stratum_v2 import Frame,StandardChannel,StandardJob,SubmitSharesStandard
from .sv2_transport import NoiseTransport,authority_key
from ..bitcoin.block_header import BlockHeader
from ..bitcoin.merkle import apply_coinbase_branch
from ..bitcoin.target import UINT256_MAX,meets_target
from ..oracle.sha256 import sha256d
from ..gpu.backend import get_backend,BackendUnavailable,ResultOverflow
from ..verify.parity import verify_backend

VERSION_MASK=0x1FFFE000

class ReconnectRequested(ProtocolError):
    def __init__(self,host,port):super().__init__("Authenticated upstream requested reconnect");self.host=host;self.port=port

@dataclass(frozen=True)
class ExtendedJob:
    job_id:int
    version:int
    ntime_start:int|None
    rolling:bool
    branch:tuple[bytes,...]
    prefix:bytes
    suffix:bytes
    target:int|None=None

class ExtendedChannel(StandardChannel):
    def __init__(self,channel_id,target,prefix,size):
        super().__init__(channel_id,target)
        if not 1<=size<=32 or len(prefix)>32:raise ProtocolError("Invalid extended extranonce workspace")
        self.prefix=prefix;self.size=size;self.extranonce=bytes(size)
    def new_job(self,job):
        if job.job_id in self.jobs or len(self.jobs)>=128:raise ProtocolError("Duplicate/bounded extended job id")
        if job.ntime_start is not None:
            if self.previous is None or job.ntime_start<self.previous[1]:raise ProtocolError("Extended job before activation time")
            job=replace(job,target=self.target);self.active=job.job_id
        self.jobs[job.job_id]=job
    def work(self):
        if self.active is None or self.previous is None:raise ProtocolError("No active extended job")
        job=self.jobs[self.active];previous,_,bits=self.previous
        coinbase=job.prefix+self.prefix+self.extranonce+job.suffix
        if len(coinbase)>=6 and coinbase[4:6]==b"\x00\x01":raise ProtocolError("Witness coinbase requires txid stripping")
        root=apply_coinbase_branch(coinbase,list(job.branch))
        return BlockHeader(job.version,previous,root,job.ntime_start,bits,0),job.target

class SV2Client:
    def __init__(self,transport,worker,host="localhost",port=34254,extended=False,timeout=10,nominal_hashrate=0.):
        self.transport=transport;self.worker=worker;self.host=host;self.port=port;self.extended=extended;self.timeout=timeout
        self.nominal_hashrate=nominal_hashrate;self.channel=None;self.group=None;self.flags=0;self.ready=False
        self.pending={};self.sequence=0;self.generation=0;self.evidence=[];self.examined=0;self.setup_received=False
        self.submission_keys={};self.ack_batches=[];self.last_ack=-1
        self.stats={"submitted":0,"accepted":0,"rejected":0,"stale_discarded":0,"unknown_messages":0}
    def send(self,kind,payload):self.transport.send_frame(Frame(0x8000 if kind in w.CHANNEL_TYPES else 0,kind,payload))
    def pump(self,timeout=0):
        frame=self.transport.recv_frame(timeout)
        if frame is None:return False
        self.process(frame);return True
    def process(self,frame):
        try:self._process(frame)
        except (ValueError,OverflowError) as error:raise ProtocolError("Invalid SV2 channel data") from error
    def _process(self,frame):
        if frame.extension_type&0x7FFF:self.stats["unknown_messages"]+=1;return
        kind=frame.message_type;r=w.Reader(frame.payload)
        if bool(frame.extension_type&0x8000)!=(kind in w.CHANNEL_TYPES):raise ProtocolError("Incorrect SV2 channel flag")
        if kind==w.SETUP_OK:
            if self.setup_received:raise ProtocolError("Duplicate SV2 setup response")
            self.setup_received=True
            version=r.integer(2);self.flags=r.integer();r.finish()
            if version!=2 or not self.extended and self.flags&2:raise ProtocolError("Incompatible SV2 setup negotiation")
            self.send(w.OPEN_EXTENDED if self.extended else w.OPEN_STANDARD,w.open_channel(self.worker,self.nominal_hashrate,UINT256_MAX,self.extended))
        elif kind in (w.SETUP_ERROR,w.OPEN_ERROR):
            r.integer();r.text();r.finish();raise ProtocolError("SV2 setup/channel rejected")
        elif kind in (w.OPEN_STANDARD_OK,w.OPEN_EXTENDED_OK):
            if self.channel is not None or kind!=(w.OPEN_EXTENDED_OK if self.extended else w.OPEN_STANDARD_OK):raise ProtocolError("Unexpected channel response")
            if r.integer()!=1:raise ProtocolError("Unknown channel request id")
            channel_id=r.integer();target=r.integer(32)
            size=r.integer(2) if self.extended else 0;prefix=r.bytes(32);self.group=r.integer();r.finish()
            if self.group==channel_id:raise ProtocolError("SV2 group and channel ids must differ")
            if self.extended and size<4:raise ProtocolError("Server did not satisfy requested extranonce size")
            self.channel=ExtendedChannel(channel_id,target,prefix,size) if self.extended else StandardChannel(channel_id,target)
            self.ready=True
        elif kind==w.RECONNECT:
            host=r.text();port=r.integer(2);r.finish();raise ReconnectRequested(host or self.host,port or self.port)
        elif kind==w.ENDPOINT_CHANGED:
            r.integer();r.finish() # No extensions negotiated; core mining state is unchanged.
        elif kind==w.GROUP:
            group=r.integer();count=r.integer(2)
            if count>4096:raise ProtocolError("Group channel memory bound exceeded")
            channels=[r.integer() for _ in range(count)];r.finish()
            if self.channel and self.channel.channel_id in channels:self.group=group
        elif kind in w.CHANNEL_TYPES:
            if self.channel is None:raise ProtocolError("Channel message before channel opening")
            channel_id=r.integer()
            if channel_id not in (self.channel.channel_id,self.group):raise ProtocolError("Unknown SV2 channel id")
            if channel_id==self.group and kind not in (w.NEW_EXTENDED,w.PREV_HASH,w.TARGET):
                if kind==w.EXTRANONCE:return # The specification requires ignoring this on group channels.
                raise ProtocolError("Message not applicable to an SV2 group")
            if kind==w.NEW_STANDARD:
                if self.extended:raise ProtocolError("Standard job on extended channel")
                job=StandardJob(r.integer(),0,b"",r.option());version=r.integer();root=r.take(32);r.finish()
                self.channel.new_job(replace(job,version=version,merkle_root=root))
            elif kind==w.NEW_EXTENDED:
                if not self.extended:raise ProtocolError("Extended jobs violate REQUIRES_STANDARD_JOBS")
                ident=r.integer();ntime=r.option();version=r.integer();rolling=r.integer(1)
                if rolling not in (0,1) or rolling and self.flags&1:raise ProtocolError("Invalid version rolling declaration")
                count=r.integer(1);branch=tuple(r.take(32) for _ in range(count))
                prefix=r.bytes(65535,2);suffix=r.bytes(65535,2);r.finish()
                self.channel.new_job(ExtendedJob(ident,version,ntime,bool(rolling),branch,prefix,suffix))
            elif kind==w.PREV_HASH:
                ident=r.integer();previous=r.take(32);ntime=r.integer();bits=r.integer();r.finish()
                self.channel.activate(ident,previous,ntime,bits);self.generation+=1
            elif kind==w.TARGET:
                self.channel.set_target(r.integer(32));r.finish()
            elif kind==w.EXTRANONCE:
                prefix=r.bytes(32);r.finish()
                if self.extended:self.channel.prefix=prefix
                self.channel.jobs.clear();self.channel.active=None;self.generation+=1
            elif kind==w.SUBMIT_ERROR:
                sequence=r.integer();code=r.text();r.finish()
                if sequence not in self.pending:raise ProtocolError("Unknown share rejection sequence")
                if any(b["last"]==sequence for b in self.ack_batches):raise ProtocolError("SV2 rejection contradicts acknowledged last sequence")
                self.pending.pop(sequence);self.stats["rejected"]+=1
                self.resolve_ack_batches()
            elif kind==w.SUBMIT_OK:
                last=r.integer();count=r.integer();shares_sum=r.integer(8);r.finish()
                eligible=[last] if count==1 else [seq for seq in self.pending if seq<=last]
                if not count or last not in self.pending or any(b["last"]==last for b in self.ack_batches) or len(eligible)<count or self.stats["accepted"]+count>self.stats["submitted"]-self.stats["rejected"]:raise ProtocolError("Invalid or duplicate SV2 acknowledgement")
                self.ack_batches.append({"sequences":eligible,"count":count,"last":last,"sum":shares_sum})
                self.last_ack=last;self.stats["accepted"]+=count
                self.resolve_ack_batches() # Delayed rejects must identify accepted headers before evidence is attributed.
            elif kind==w.CLOSE:
                r.text();r.finish();self.ready=False;self.channel.jobs.clear();self.channel.active=None;self.generation+=1
            elif kind==w.UPDATE_ERROR:r.text();r.finish();raise ProtocolError("SV2 channel update rejected")
            else:self.stats["unknown_messages"]+=1
        else:self.stats["unknown_messages"]+=1
    def resolve_ack_batches(self):
        remaining=[]
        for batch in self.ack_batches:
            accepted=[seq for seq in batch["sequences"] if seq in self.pending]
            if len(accepted)<batch["count"]:raise ProtocolError("SV2 rejection conflicts with prior success")
            if len(accepted)>batch["count"]:remaining.append(batch);continue
            for sequence in accepted:
                evidence=self.pending.pop(sequence)
                evidence.update(timestamp_utc=datetime.now(timezone.utc).isoformat(),pool_response={"last_sequence_number":batch["last"],"accepted_count":batch["count"],"new_shares_sum":batch["sum"]})
                self.evidence=(self.evidence+[evidence])[-128:]
        self.ack_batches=remaining
    def update_channel(self,hashrate,max_target=UINT256_MAX):
        if not self.ready or not 0<=hashrate<3.4e38 or not 0<max_target<=UINT256_MAX:raise ProtocolError("Invalid channel update")
        self.send(w.UPDATE,pack("<If",self.channel.channel_id,hashrate)+max_target.to_bytes(32,"little"))
    def handshake(self):
        self.send(w.SETUP,w.setup(self.host,self.port,self.extended));deadline=monotonic()+self.timeout
        while not self.ready:
            if monotonic()>deadline:raise ProtocolError("SV2 channel setup timed out")
            self.pump(min(.1,max(0,deadline-monotonic())))
    def submit(self,header,target,job_id,generation,nonce):
        if not self.ready:raise ProtocolError("SV2 channel unavailable")
        deadline=monotonic()+self.timeout
        while len(self.pending)>=128:
            if monotonic()>deadline:raise ProtocolError("SV2 acknowledgement timeout")
            self.pump(.05)
        if generation!=self.generation or self.channel.active!=job_id:
            self.stats["stale_discarded"]+=1;return False
        current,active_target=self.channel.work();job=self.channel.jobs[job_id]
        rolling=not self.flags&1 and (not self.extended or job.rolling)
        if header.previous_hash!=current.previous_hash or header.merkle_root!=current.merkle_root or header.bits!=current.bits or target!=active_target or header.timestamp<current.timestamp:
            self.stats["stale_discarded"]+=1;return False
        if header.version!=current.version and (not rolling or (header.version^current.version)&~VERSION_MASK):raise ProtocolError("Unnegotiated version rolling")
        candidate=header.with_nonce(nonce);digest=sha256d(candidate.serialize())
        if not meets_target(digest,target):raise ProtocolError("SV2 share failed independent oracle")
        key=candidate.serialize()
        if key in self.submission_keys:raise ProtocolError("Duplicate SV2 share suppressed")
        if self.sequence>0xFFFFFFFF:raise ProtocolError("SV2 sequence space exhausted; reopen channel")
        sequence=self.sequence;payload=SubmitSharesStandard(self.channel.channel_id,sequence,job_id,nonce,header.timestamp,header.version).encode()
        if self.extended:payload+=w.blob(self.channel.extranonce,32)
        self.send(w.SUBMIT_EXTENDED if self.extended else w.SUBMIT_STANDARD,payload)
        self.pending[sequence]={"job_id":job_id,"nonce":nonce,"header":candidate.serialize().hex(),"digest":digest.hex(),"target":f"{target:064x}"}
        self.submission_keys[key]=None
        if len(self.submission_keys)>4096:self.submission_keys.pop(next(iter(self.submission_keys)))
        self.sequence+=1;self.stats["submitted"]+=1;return True
    def close(self):
        if self.ready:
            try:self.send(w.CLOSE,pack("<I",self.channel.channel_id)+w.text("shutdown"))
            except (OSError,ProtocolError):pass
        self.ready=False;self.transport.close()

def mine_session(client,backend,seconds=60,batch_size=1<<20):
    if not 0<seconds<=86400 or not 1<=batch_size<=1<<24:raise ValueError("Finite SV2 session budget required")
    started=monotonic();client.handshake();previous=None;nonce=0;examined=0;extranonce=0;version_counter=0
    while monotonic()-started<seconds:
        for _ in range(32):
            if not client.pump(0):break
        if not client.ready:break
        if client.channel.active is None:client.pump(.05);continue
        header,target=client.channel.work();identity=(header.serialize()[:76],client.channel.active,client.generation)
        if identity!=previous:previous=identity;nonce=0;extranonce=0;version_counter=0
        if nonce==1<<32:
            if client.extended:
                extranonce+=1
                if extranonce>=1<<(8*client.channel.size):raise ProtocolError("Extended extranonce exhausted")
                client.channel.extranonce=extranonce.to_bytes(client.channel.size,"little");header,target=client.channel.work()
                previous=(header.serialize()[:76],client.channel.active,client.generation);nonce=0
            elif not client.flags&1 and version_counter<65535:version_counter+=1;nonce=0
            else:client.pump(.05);continue # Await a distinct valid job after permitted workspace exhaustion.
        if version_counter:
            version_bits=(((header.version&VERSION_MASK)>>13)+version_counter)&0xFFFF
            header=replace(header,version=(header.version&~VERSION_MASK)|(version_bits<<13))
        count=min(batch_size,(1<<32)-nonce);job_id=client.channel.active;generation=client.generation
        try:scan=backend.scan(header.serialize(),nonce,count,target)
        except ResultOverflow:
            if batch_size==1:raise
            batch_size=max(1,batch_size//2);continue
        examined+=scan.examined
        client.examined=examined
        for _ in range(32):
            if not client.pump(0):break
        for found in scan.nonces:client.submit(header,target,job_id,generation,found)
        nonce+=count
    deadline=monotonic()+min(2,client.timeout)
    while client.pending and monotonic()<deadline:client.pump(.05)
    return {"protocol":"stratum-v2","examined":examined,"seconds":monotonic()-started,**client.stats,
            "unacknowledged":len(client.pending),"unresolved_ack_batches":len(client.ack_batches),"accepted_evidence":client.evidence,"btc_balance":None}

def run_miner(config,seconds=60):
    if not 0<seconds<=86400:raise ValueError("Finite SV2 session required")
    uri=urlparse(config.get("pool_url",""));worker=config.get("worker","")
    if uri.scheme!="stratum2+tcp" or not uri.hostname or not uri.port or not worker or uri.username or uri.password:raise ValueError("Actual stratum2+tcp pool URL and worker required")
    key=bytes.fromhex(config["authority_pubkey"]) if config.get("authority_pubkey") else authority_key(uri.path.lstrip("/"))
    if len(key)!=32:raise ValueError("Pinned SV2 authority key required")
    chosen=config.get("backend","opencl");backend=None;fallbacks=[]
    if chosen not in ("opencl","native","native-full","hashlib"):raise ValueError("Invalid SV2 scan backend")
    for name in dict.fromkeys([chosen,"native","hashlib"]):
        try:backend=get_backend(name,**(config.get("gpu",{}) if name=="opencl" else {}))
        except BackendUnavailable:fallbacks.append({"backend":name,"status":"unavailable"});continue
        try:verify_backend(backend,4096)
        except Exception:backend.close();raise
        break
    if backend is None:raise BackendUnavailable("All SV2 scan backends unavailable")
    from .recovering_backend import RecoveringBackend
    backend=RecoveringBackend(backend,fallbacks)
    client=None;started=monotonic();totals={"submitted":0,"accepted":0,"rejected":0,"stale_discarded":0,"examined":0};evidence=[]
    try:
        host=uri.hostname;port=uri.port;attempts=[]
        for attempt in range(3):
            remaining=seconds-(monotonic()-started)
            if remaining<=0:break
            sock=None;transport=None
            try:
                timeout=min(10,remaining)
                sock=socket.create_connection((host,port),timeout=timeout)
                transport=NoiseTransport(sock,timeout=timeout);transport.handshake(key)
                client=SV2Client(transport,worker,host,port,config.get("extended",False),timeout=timeout,nominal_hashrate=config.get("nominal_hashrate",0.))
                result=mine_session(client,backend,remaining,config.get("batch_size",1<<20))
                return {**result,**{k:totals[k]+result[k] for k in totals},"accepted_evidence":(evidence+result["accepted_evidence"])[-128:],"backend":backend.name,"fallback_reasons":fallbacks,"reconnects":attempt,"attempts":attempts}
            except ReconnectRequested as error:
                host=error.host;port=error.port;attempts.append({"status":"authenticated_reconnect","previous_session_work_discarded":True})
            except (OSError,ProtocolError):
                attempts.append({"status":"network_or_protocol_failure","previous_session_work_discarded":True})
            finally:
                if client:
                    for k in totals:totals[k]+=client.examined if k=="examined" else client.stats[k]
                    evidence=(evidence+client.evidence)[-128:];client.close();client=None
                elif transport:transport.close()
                elif sock:sock.close()
        return {"protocol":"stratum-v2","status":"bounded_reconnect_exhausted",**totals,"accepted_evidence":evidence,"backend":backend.name,"fallback_reasons":fallbacks,"attempts":attempts,"btc_balance":None}
    finally:
        if client:client.close()
        backend.close()
