"""Independent wire fixtures and encrypted local pool, never real mining claims."""
import hashlib
import os
import socket
import struct
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from nucleus_btc.protocol import sv2_wire as w
from nucleus_btc.protocol.stratum_v2 import Frame
from nucleus_btc.protocol.stratum_v1 import ProtocolError
from nucleus_btc.protocol.sv2_transport import NoiseProcess,NoiseTransport,MAX_PLAIN,ROOT,authority_key
from nucleus_btc.protocol.sv2_client import SV2Client,ReconnectRequested,VERSION_MASK,mine_session,run_miner
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.bitcoin.target import UINT256_MAX
from nucleus_btc.gpu.backend import HashlibBackend

def frame(kind,data):return Frame(0x8000 if kind in w.CHANNEL_TYPES else 0,kind,data)
def u32(*values):return struct.pack("<"+"I"*len(values),*values)
def dbl(data):return hashlib.sha256(hashlib.sha256(data).digest()).digest()

class OfflineTransport:
    def __init__(self):self.sent=[];self.queue=[];self.closed=False
    def send_frame(self,value):self.sent.append(value)
    def recv_frame(self,timeout=0):return self.queue.pop(0) if self.queue else None
    def close(self):self.closed=True

def ready(extended=False,flags=0):
    transport=OfflineTransport();client=SV2Client(transport,"test-worker",extended=extended,timeout=.01)
    client.process(frame(w.SETUP_OK,struct.pack("<HI",2,flags)))
    payload=u32(1,7)+UINT256_MAX.to_bytes(32,"little")
    if extended:payload+=struct.pack("<H",4)
    client.process(frame(w.OPEN_EXTENDED_OK if extended else w.OPEN_STANDARD_OK,payload+b"\x02\xaa\xbb"+u32(9)))
    if extended:
        payload=u32(7,10)+b"\x00"+u32(GENESIS.version)+b"\x01\x00"+w.blob(b"prefix",65535,2)+w.blob(b"suffix",65535,2)
    else:payload=u32(7,10)+b"\x00"+u32(GENESIS.version)+GENESIS.merkle_root
    client.process(frame(w.NEW_EXTENDED if extended else w.NEW_STANDARD,payload))
    client.process(frame(w.PREV_HASH,u32(7,10)+GENESIS.previous_hash+u32(GENESIS.timestamp,GENESIS.bits)))
    return client

class SV2StateTests(unittest.TestCase):
    def test_rolling_target_epochs_stale_extranonce_and_update(self):
        for extended in (False,True):
            client=ready(extended);header,target=client.channel.work();generation=client.generation
            rolled=type(header)(header.version^(VERSION_MASK&-VERSION_MASK),header.previous_hash,header.merkle_root,header.timestamp,header.bits,0)
            self.assertTrue(client.submit(rolled,target,10,generation,1))
            with self.assertRaisesRegex(ProtocolError,"Duplicate"):client.submit(rolled,target,10,generation,1)
            client.process(frame(w.TARGET,u32(7)+(1).to_bytes(32,"little")))
            self.assertEqual(client.channel.work()[1],UINT256_MAX)
            client.update_channel(100.);self.assertEqual(client.transport.sent[-1].message_type,w.UPDATE)
            client.process(frame(w.EXTRANONCE,u32(9)+b"\x01\xcc")) # Group prefix must be ignored.
            self.assertEqual(client.channel.active,10)
            client.process(frame(w.EXTRANONCE,u32(7)+b"\x01\xcc"))
            self.assertIsNone(client.channel.active)
            self.assertFalse(client.submit(header,target,10,generation,2))
            client.close();self.assertTrue(client.transport.closed)
        fixed=ready(flags=1);header,target=fixed.channel.work()
        with self.assertRaisesRegex(ProtocolError,"rolling"):
            fixed.submit(type(header)(header.version^0x2000,header.previous_hash,header.merkle_root,header.timestamp,header.bits,0),target,10,fixed.generation,0)
    def test_out_of_order_rejects_and_aggregate_ack_evidence(self):
        client=ready();header,target=client.channel.work()
        for nonce in range(4):client.submit(header,target,10,client.generation,nonce)
        client.process(frame(w.SUBMIT_OK,u32(7,3,1)+struct.pack("<Q",1)))
        client.process(frame(w.SUBMIT_ERROR,u32(7,1)+w.text("invalid-job-id")))
        client.process(frame(w.SUBMIT_OK,u32(7,2,2)+struct.pack("<Q",2)))
        self.assertEqual(client.stats["accepted"],3);self.assertEqual(client.stats["rejected"],1)
        self.assertEqual(client.pending,{})
        self.assertEqual({e["nonce"] for e in client.evidence},{0,2,3})
        for evidence in client.evidence:self.assertEqual(dbl(bytes.fromhex(evidence["header"])).hex(),evidence["digest"])
        with self.assertRaises(ProtocolError):client.process(frame(w.SUBMIT_OK,u32(7,2,2)+struct.pack("<Q",2)))
    def test_delayed_reject_does_not_attribute_wrong_header(self):
        client=ready();header,target=client.channel.work()
        for nonce in range(3):client.submit(header,target,10,client.generation,nonce)
        client.process(frame(w.SUBMIT_OK,u32(7,2,2)+struct.pack("<Q",2)))
        self.assertEqual(client.stats["accepted"],2);self.assertEqual(client.evidence,[])
        client.process(frame(w.SUBMIT_ERROR,u32(7,0)+w.text("stale-share")))
        self.assertEqual({e["nonce"] for e in client.evidence},{1,2})
    def test_malformed_duplicate_reconnect_and_bounds(self):
        client=ready();header,target=client.channel.work()
        with self.assertRaises(ProtocolError):client.process(Frame(0,w.TARGET,u32(7)+bytes(32)))
        with self.assertRaises(ProtocolError):client.process(frame(w.TARGET,u32(7)+bytes(32)))
        with self.assertRaises(ProtocolError):client.process(frame(w.NEW_STANDARD,u32(7,10)+b"\x00"+u32(1)+bytes(32)))
        with self.assertRaises(ProtocolError):client.process(frame(w.SETUP_OK,struct.pack("<HI",2,0)))
        with self.assertRaises(ReconnectRequested):client.process(frame(w.RECONNECT,w.text("localhost")+struct.pack("<H",34254)))
        client.pending={i:{} for i in range(128)}
        with self.assertRaisesRegex(ProtocolError,"timeout"):client.submit(header,target,10,client.generation,1)
        with self.assertRaises(ProtocolError):w.Reader(b"\x02").option()
        with self.assertRaises(ValueError):authority_key("invalid0key")
    def test_reconnect_statistics_and_fresh_client(self):
        backend=HashlibBackend();clients=[]
        class Transport(OfflineTransport):
            def __init__(self,*args,**kwargs):super().__init__()
            def handshake(self,key):pass
        def session(client,backend,seconds,batch):
            clients.append(client)
            if len(clients)==1:
                client.stats.update(submitted=1,accepted=1);client.examined=12
                client.evidence=[{"fixture":True}];raise ReconnectRequested("localhost",34254)
            self.assertFalse(client.pending);self.assertIsNone(client.channel)
            return {"protocol":"stratum-v2","submitted":2,"accepted":2,"rejected":0,"stale_discarded":0,"examined":24,"accepted_evidence":[],"btc_balance":None}
        with patch("nucleus_btc.protocol.sv2_client.get_backend",return_value=backend),patch("nucleus_btc.protocol.sv2_client.verify_backend"),patch("nucleus_btc.protocol.sv2_client.socket.create_connection"),patch("nucleus_btc.protocol.sv2_client.NoiseTransport",Transport),patch("nucleus_btc.protocol.sv2_client.mine_session",session):
            result=run_miner({"pool_url":"stratum2+tcp://localhost:34254","worker":"fixture","authority_pubkey":"01"*32},seconds=1)
        self.assertEqual(result["accepted"],3);self.assertEqual(result["examined"],36);self.assertEqual(len(clients),2)

class EncryptedSV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suffix=".exe" if os.name=="nt" else ""
        cls.fixture=ROOT/"build"/"sv2-fixture"/"debug"/("nucleus-sv2-noise"+suffix)
        if not cls.fixture.is_file():
            if os.environ.get("NUCLEUS_REQUIRE_SV2")=="1":raise RuntimeError("Required SV2 fixture helper missing")
            raise unittest.SkipTest("Build locked Rust SV2 helper and fixtures to run encrypted integration")
    def test_production_helper_cannot_create_fixture_authority(self):
        helper=NoiseProcess(timeout=2)
        try:
            with self.assertRaisesRegex(ProtocolError,"unknown operation"):helper.request("fixture-init",b"")
            self.assertTrue(helper.closed);self.assertFalse(helper.reader.is_alive())
        finally:helper.close()
    def connected(self):
        left,right=socket.socketpair();server_codec=NoiseProcess(self.fixture,timeout=2)
        public=server_codec.request("fixture-init",b"");transport=NoiseTransport(left,timeout=2)
        def handshake():
            try:
                first=b""
                while len(first)<64:first+=right.recv(64-len(first))
                reply=server_codec.request("fixture-handshake",first);right.sendall(reply[:13]);right.sendall(reply[13:])
            except Exception as error:self.server_errors.append(error)
        self.server_errors=[];thread=threading.Thread(target=handshake,daemon=True);thread.start();transport.handshake(public);thread.join(2)
        return transport,NoiseTransport(right,server_codec,timeout=2)
    def test_fragmented_multichunk_ciphertext_and_tamper(self):
        client,server=self.connected();server.authenticated=True
        try:
            original=Frame(0,0x70,b"x"*70000);raw=original.encode()
            encrypted=server.codec.request("encrypt",raw[:6])+b"".join(server.codec.request("encrypt",raw[i:i+MAX_PLAIN]) for i in range(6,len(raw),MAX_PLAIN))
            server.socket.sendall(encrypted[:9]);self.assertIsNone(client.recv_frame(.1))
            server.socket.sendall(encrypted[9:]);result=None;deadline=time.monotonic()+2
            while result is None and time.monotonic()<deadline:result=client.recv_frame(.1)
            self.assertEqual(result,original)
            bad=bytearray(server.codec.request("encrypt",Frame(0,0x70,b"").encode()));bad[0]^=1;server.socket.sendall(bad)
            with self.assertRaises(ProtocolError):client.recv_frame(.2)
            self.assertTrue(client.closed)
        finally:client.close();server.close()
    def test_authenticated_standard_and_extended_mock_pool(self):
        for extended in (False,True):
            with self.subTest(extended=extended):
                client_transport,server=self.connected();server.authenticated=True;seen=set();errors=[]
                prefix=b"\x01\x00\x00\x00prefix";suffix=b"suffix";channel_prefix=b"\xaa\xbb";job_id=10
                def send(kind,payload):server.send_frame(frame(kind,payload))
                def serve():
                    try:
                        while True:
                            message=server.recv_frame(.2)
                            if message is None:continue
                            kind=message.message_type;p=message.payload
                            if kind==w.SETUP:
                                self.assertEqual(struct.unpack("<BHHI",p[:9]),(0,2,2,0 if extended else 1));send(w.SETUP_OK,struct.pack("<HI",2,0))
                            elif kind in (w.OPEN_STANDARD,w.OPEN_EXTENDED):
                                self.assertEqual(kind,w.OPEN_EXTENDED if extended else w.OPEN_STANDARD)
                                reply=u32(1,7)+UINT256_MAX.to_bytes(32,"little")+(struct.pack("<H",4) if extended else b"")+b"\x02"+channel_prefix+u32(9)
                                send(w.OPEN_EXTENDED_OK if extended else w.OPEN_STANDARD_OK,reply)
                                if extended:send(w.NEW_EXTENDED,u32(7,job_id)+b"\x00"+u32(GENESIS.version)+b"\x01\x00"+w.blob(prefix,65535,2)+w.blob(suffix,65535,2))
                                else:send(w.NEW_STANDARD,u32(7,job_id)+b"\x00"+u32(GENESIS.version)+GENESIS.merkle_root)
                                send(w.PREV_HASH,u32(7,job_id)+GENESIS.previous_hash+u32(GENESIS.timestamp,GENESIS.bits))
                            elif kind in (w.SUBMIT_STANDARD,w.SUBMIT_EXTENDED):
                                cid,seq,jid,nonce,ntime,version=struct.unpack("<6I",p[:24]);self.assertEqual((cid,jid),(7,job_id))
                                if extended:
                                    self.assertEqual(p[24],4);self.assertEqual(len(p),29);root=dbl(prefix+channel_prefix+p[25:]+suffix)
                                else:root=GENESIS.merkle_root
                                header=struct.pack("<I",version)+GENESIS.previous_hash+root+struct.pack("<III",ntime,GENESIS.bits,nonce)
                                self.assertNotIn(header,seen);seen.add(header);self.assertLessEqual(int.from_bytes(dbl(header),"little"),UINT256_MAX)
                                send(w.SUBMIT_OK,u32(7,seq,1)+struct.pack("<Q",1))
                            elif kind==w.CLOSE:break
                            else:raise AssertionError("Unexpected encrypted wire message")
                    except Exception as error:errors.append(error)
                    finally:server.close()
                thread=threading.Thread(target=serve,daemon=True);thread.start();client=SV2Client(client_transport,"local-fixture",extended=extended,timeout=2)
                try:
                    result=mine_session(client,HashlibBackend(),seconds=.12,batch_size=4)
                    self.assertGreater(result["accepted"],0);self.assertEqual(result["accepted"],len(seen));self.assertEqual(result["unacknowledged"],0)
                    self.assertEqual(result["btc_balance"],None)
                finally:client.close();thread.join(3)
                self.assertFalse(thread.is_alive())
                if errors:raise errors[0]

if __name__=="__main__":unittest.main()
