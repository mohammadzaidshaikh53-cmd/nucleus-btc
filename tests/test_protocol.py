import json
import socket
import threading
import unittest
from decimal import Decimal
from nucleus_btc.protocol.stratum_v1 import JsonLineDecoder,MiningJob,StratumClient,ProtocolError,word_swap,mine_session
from nucleus_btc.protocol.stratum_v2 import Frame,FrameDecoder,SubmitSharesStandard,StandardChannel,StandardJob
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.bitcoin.coinbase import build_coinbase
from nucleus_btc.bitcoin.target import UINT256_MAX
from nucleus_btc.gpu.backend import HashlibBackend

def notify(job_id="fixture",clean=True):
    # Coinbase prefix already contains scriptSig length accounting for 2 extranonce bytes.
    cb=build_coinbase(800000,b"\x00\x00",b"\x51",312500000)
    position=cb.index(b"\x03\x00\x35\x0c")+4
    return [job_id,word_swap(bytes(range(32))).hex(),cb[:position].hex(),cb[position+2:].hex(),[],"20000000","1d00ffff","65000000",clean]

class ProtocolTests(unittest.TestCase):
    def test_line_decoder(self):
        d=JsonLineDecoder(max_line=32)
        self.assertEqual(d.feed(b'{"id":'),[])
        self.assertEqual(d.feed(b'1}\n'),[{"id":1}])
        with self.assertRaises(ProtocolError):d.feed(bytes(33))
        with self.assertRaises(ProtocolError):JsonLineDecoder().feed(b'[]\n')
    def test_header_and_stale_job(self):
        params=notify();job=MiningJob.from_notify(params,UINT256_MAX,b"",2,1);h=job.header(b"\x00\x00")
        self.assertEqual(h.previous_hash,bytes(range(32)))
        self.assertEqual(h.serialize()[:4],b"\x00\x00\x00\x20")
        self.assertEqual(job.submission("worker",b"\x00\x00",0x12345678)[-1],"12345678")
        left,right=socket.socketpair()
        try:
            client=StratumClient(left,"worker");client.authorized=True;client.extranonce2_size=2
            client.process({"method":"mining.notify","params":params});old=client.latest
            client.process({"method":"mining.set_difficulty","params":[2]})
            self.assertEqual(client.latest.target,old.target)
            client.process({"method":"mining.notify","params":notify("new",True)})
            self.assertFalse(client.submit(old,b"\x00\x00",0))
            self.assertEqual(client.stats["stale_discarded"],1)
        finally:left.close();right.close()
    def test_mock_pool_session(self):
        left,right=socket.socketpair();errors=[];seen=set();accepted=[]
        def server():
            try:
                reader=right.makefile("rb")
                while True:
                    line=reader.readline()
                    if not line:break
                    obj=json.loads(line);method=obj["method"];ident=obj["id"]
                    if method=="mining.subscribe":
                        # Reply and job in the same packet exercise receive ordering.
                        messages=[{"id":ident,"result":[[],"",2],"error":None},
                                  {"method":"mining.set_difficulty","params":[Decimal("0.0000000001")]},
                                  {"method":"mining.notify","params":notify()}]
                        encoded=[]
                        for message in messages:
                            if message.get("method")=="mining.set_difficulty":encoded.append('{"method":"mining.set_difficulty","params":[0.0000000001]}')
                            else:encoded.append(json.dumps(message))
                        right.sendall(("\n".join(encoded)+"\n").encode())
                    elif method=="mining.authorize":right.sendall((json.dumps({"id":ident,"result":True,"error":None})+"\n").encode())
                    elif method=="mining.submit":
                        worker,job_id,extranonce,ntime,nonce=obj["params"]
                        key=(job_id,extranonce,nonce)
                        if key in seen:raise AssertionError("Duplicate search/share")
                        seen.add(key)
                        job=MiningJob.from_notify(notify(),UINT256_MAX,b"",2,1)
                        self.assertEqual(job.submission(worker,bytes.fromhex(extranonce),int(nonce,16)),obj["params"])
                        accepted.append(key);right.sendall((json.dumps({"id":ident,"result":True,"error":None})+"\n").encode())
            except Exception as e:errors.append(e)
            finally:right.close()
        thread=threading.Thread(target=server,daemon=True);thread.start()
        try:
            client=StratumClient(left,"offline-worker",timeout=2)
            result=mine_session(client,HashlibBackend(),seconds=.08,batch_size=8)
            self.assertGreater(result["accepted"],0);self.assertEqual(result["rejected"],0);self.assertEqual(result["unacknowledged"],0)
            self.assertEqual(result["accepted"],len(accepted))
        finally:left.close();thread.join(timeout=2)
        if errors:raise errors[0]
    def test_sv2_codec_and_target_epochs(self):
        share=SubmitSharesStandard(1,2,3,4,5,6)
        self.assertEqual(SubmitSharesStandard.decode(share.encode()),share)
        self.assertEqual(share.encode()[:8],b"\x01\x00\x00\x00\x02\x00\x00\x00")
        frame=Frame(0x8000,0x1A,share.encode());raw=frame.encode();d=FrameDecoder()
        self.assertEqual(d.feed(raw[:7]),[]);self.assertEqual(d.feed(raw[7:]),[frame])
        with self.assertRaises(ValueError):Frame.decode(raw[:-1])
        channel=StandardChannel(1,UINT256_MAX)
        with self.assertRaises(ValueError):channel.work()
        channel.new_job(StandardJob(10,GENESIS.version,GENESIS.merkle_root,None))
        channel.activate(10,GENESIS.previous_hash,GENESIS.timestamp,GENESIS.bits)
        channel.set_target(1)
        # Existing active job retains its target; new jobs receive updated target.
        self.assertEqual(channel.work()[1],UINT256_MAX)
        submitted=channel.submission(GENESIS.nonce,GENESIS.timestamp,GENESIS.version)
        self.assertEqual(submitted.job_id,10)
        channel.new_job(StandardJob(11,GENESIS.version,GENESIS.merkle_root,GENESIS.timestamp))
        self.assertEqual(channel.work()[1],1)
        with self.assertRaises(ValueError):channel.submission(GENESIS.nonce,GENESIS.timestamp,GENESIS.version)

if __name__=="__main__":unittest.main()
