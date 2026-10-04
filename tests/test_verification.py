import unittest
from nucleus_btc.gpu.backend import HashlibBackend
from nucleus_btc.verify.parity import verify_backend
from nucleus_btc.solver.family_split import scan_with_split
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.bitcoin.target import UINT256_MAX

class VerificationTests(unittest.TestCase):
    def test_intentionally_wrong_challenger_is_rejected(self):
        class Wrong(HashlibBackend):
            def hash_headers(self,headers):
                out=super().hash_headers(headers);out[0]=bytes(32);return out
        with self.assertRaises(AssertionError):verify_backend(Wrong(),samples=16)
    def test_overflow_split_preserves_every_solution(self):
        split=scan_with_split(HashlibBackend(),GENESIS.serialize(),0,17,UINT256_MAX,capacity=2)
        self.assertGreater(split["overflow_retries"],0)
        self.assertEqual(split["result"].nonces,list(range(17)))
        self.assertEqual(split["result"].examined,17)

if __name__=="__main__":unittest.main()
