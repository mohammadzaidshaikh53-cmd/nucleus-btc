import hashlib
import os
import random
import unittest
from nucleus_btc.bitcoin.block_header import GENESIS
from nucleus_btc.bitcoin.target import compact_to_target,UINT256_MAX,meets_target
from nucleus_btc.gpu.backend import get_backend,BackendUnavailable,ResultOverflow

class BackendTests(unittest.TestCase):
    def check_backend(self,name,**kwargs):
        try:backend=get_backend(name,**kwargs)
        except BackendUnavailable as e:
            if os.environ.get("NUCLEUS_REQUIRE_"+name.upper()):raise
            self.skipTest(str(e))
        with backend:
            rng=random.Random(1841)
            headers=[GENESIS.serialize(),bytes(80),bytes([255])*80]+[rng.randbytes(80) for _ in range(253)]
            expected=[hashlib.sha256(hashlib.sha256(h).digest()).digest() for h in headers]
            self.assertEqual(backend.hash_headers(headers),expected)
            if not hasattr(backend,"scan"):return
            for start,count in [(0,65),(0xFFFFFFF0,16),(GENESIS.nonce-8,17)]:
                h=GENESIS.serialize()
                truth=get_backend("hashlib").hash_nonces(h,start,count)
                self.assertEqual(backend.hash_nonces(h,start,count),truth)
                # High targets test false negatives, atomics, capacity and word comparison.
                for target in [1,compact_to_target(GENESIS.bits),UINT256_MAX//4,UINT256_MAX]:
                    expected_n=[start+i for i,d in enumerate(truth) if meets_target(d,target)]
                    self.assertEqual(sorted(backend.scan(h,start,count,target,capacity=count).nonces),expected_n)
            target=compact_to_target(GENESIS.bits)
            self.assertIn(GENESIS.nonce,backend.scan(GENESIS.serialize(),GENESIS.nonce-4,8,target).nonces)
            with self.assertRaises(ResultOverflow):backend.scan(GENESIS.serialize(),0,16,UINT256_MAX,capacity=1)
            with self.assertRaises(ValueError):backend.hash_nonces(GENESIS.serialize(),0xFFFFFFFF,2)
    def test_hashlib(self):self.check_backend("hashlib")
    def test_native(self):self.check_backend("native")
    def test_native_full(self):self.check_backend("native-full")
    def test_opencl(self):self.check_backend("opencl")
    def test_opencl_algebra_unroll(self):self.check_backend("opencl",full_unroll=True,alt_boolean=True,local_size=128)
    def test_hip_if_installed(self):self.check_backend("hip")
    def test_changed_jobs_and_inclusive_comparison(self):
        from nucleus_btc.verify.parity import verify_backend
        try:backend=get_backend("opencl",full_unroll=True,alt_boolean=True)
        except BackendUnavailable as e:self.skipTest(str(e))
        with backend:
            report=verify_backend(backend,samples=2048)
            self.assertEqual(report["scan_cases"],20)

if __name__=="__main__":unittest.main()
