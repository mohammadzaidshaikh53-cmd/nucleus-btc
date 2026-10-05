import json
import socket
import ssl
import unittest
from unittest.mock import patch,Mock
from urllib.parse import urlparse
from test_protocol import notify
from nucleus_btc.protocol.stratum_v1 import StratumClient,ProtocolError,ReconnectRequested,connect_pool,run_miner
from nucleus_btc.bitcoin.target import UINT256_MAX
from nucleus_btc.gpu.backend import HashlibBackend

class V1RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.left,self.right=socket.socketpair();self.client=StratumClient(self.left,"local-worker",timeout=.02)
        self.client.authorized=True;self.client.target=UINT256_MAX;self.client.extranonce2_size=2
        self.client.process({"method":"mining.notify","params":notify()})
    def tearDown(self):self.client.close();self.right.close()
    def test_out_of_order_rejection_duplicate_and_evidence(self):
        job=self.client.latest
        for nonce in (0,1,2):self.client.submit(job,b"\x00\x00",nonce)
        ids=list(self.client.pending)
        self.client.process({"id":ids[2],"result":True,"error":None})
        self.client.process({"id":ids[0],"result":False,"error":[21,"stale",None]})
        self.client.process({"id":ids[1],"result":True,"error":None})
        self.client.process({"id":ids[1],"result":True,"error":None})
        self.assertEqual(self.client.stats["accepted"],2);self.assertEqual(self.client.stats["rejected"],1)
        self.assertEqual({e["nonce"] for e in self.client.accepted_evidence},{1,2})
        with self.assertRaisesRegex(ProtocolError,"Duplicate"):self.client.submit(job,b"\x00\x00",1)
    def test_extranonce_and_malformed_messages_invalidate_work(self):
        old=self.client.latest
        self.client.process({"method":"mining.set_extranonce","params":["abcd",4]})
        self.assertFalse(self.client.submit(old,b"\x00\x00",0));self.assertIsNone(self.client.latest)
        for message in ({"method":"mining.set_difficulty","params":{}},{"method":"mining.set_extranonce","params":["",True]},{"id":True,"result":True}):
            with self.subTest(message=message),self.assertRaises(ProtocolError):self.client.process(message)
        with self.assertRaises(ReconnectRequested):self.client.process({"method":"client.reconnect","params":["malicious.invalid",1]})
        self.client.pending[99]="mining.submit"
        with self.assertRaises(ProtocolError):self.client.process({"id":99,"result":"true","error":None})
    def test_tls_certificate_failure_closes_socket(self):
        sock=Mock();context=Mock();context.wrap_socket.side_effect=ssl.SSLCertVerificationError("fixture certificate rejected")
        with patch("nucleus_btc.protocol.stratum_v1.socket.create_connection",return_value=sock),patch("nucleus_btc.protocol.stratum_v1.ssl.create_default_context",return_value=context):
            with self.assertRaises(ssl.SSLCertVerificationError):connect_pool(urlparse("stratum+ssl://localhost:443"))
        sock.close.assert_called_once();context.wrap_socket.assert_called_once_with(sock,server_hostname="localhost")
    def test_finite_retries_and_secret_free_results(self):
        backend=HashlibBackend()
        with patch("nucleus_btc.protocol.stratum_v1.get_backend",return_value=backend),patch("nucleus_btc.protocol.stratum_v1.verify_backend"),patch("nucleus_btc.protocol.stratum_v1.connect_pool",side_effect=OSError("password-should-not-appear")) as connect,patch("nucleus_btc.protocol.stratum_v1.sleep"):
            result=run_miner({"pool_url":"stratum+tcp://localhost:1","worker":"fixture","password":"private-password"},seconds=2)
        self.assertEqual(connect.call_count,3);self.assertEqual(result["accepted"],0)
        self.assertNotIn("password",json.dumps(result));self.assertEqual(result["status"],"bounded_reconnect_exhausted")
    def test_failed_gpu_range_retried_exactly_on_cpu(self):
        from nucleus_btc.protocol.recovering_backend import RecoveringBackend
        from nucleus_btc.gpu.opencl import OpenCLError
        from nucleus_btc.bitcoin.block_header import GENESIS
        engine=Mock();engine.name="opencl";engine.scan.side_effect=OpenCLError("fixture GPU fault");reasons=[]
        backend=RecoveringBackend(engine,reasons);reference=HashlibBackend()
        with patch("nucleus_btc.protocol.recovering_backend.get_backend",return_value=reference):
            result=backend.scan(GENESIS.serialize(),0,16,UINT256_MAX,16)
        self.assertEqual(result.nonces,list(range(16)));self.assertEqual(result.examined,16)
        engine.close.assert_called_once();self.assertEqual(backend.name,"hashlib");self.assertEqual(len(reasons),1);backend.close()

if __name__=="__main__":unittest.main()
