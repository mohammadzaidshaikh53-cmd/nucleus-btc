import hashlib
import random
import unittest
from dataclasses import replace
from nucleus_btc.oracle.sha256 import sha256,sha256d,header_midstate,finish_header
from nucleus_btc.bitcoin.block_header import BlockHeader,GENESIS,GENESIS_HASH
from nucleus_btc.bitcoin.target import compact_to_target,target_to_compact,meets_target,MAINNET_POW_LIMIT,UINT256_MAX,difficulty_target,DIFFICULTY_ONE
from nucleus_btc.bitcoin.merkle import merkle_root,apply_coinbase_branch
from nucleus_btc.bitcoin.coinbase import compact_size,build_coinbase,height_push
from nucleus_btc.bitcoin.work_family import WorkFamily

class OracleTests(unittest.TestCase):
    def test_fips_and_padding(self):
        self.assertEqual(sha256(b"abc").hex(),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        rng=random.Random(70)
        for size in [0,1,55,56,63,64,65,80,119,120,128,257,1024]:
            data=rng.randbytes(size)
            self.assertEqual(sha256(data),hashlib.sha256(data).digest())
    def test_genesis_and_midstate(self):
        raw=GENESIS.serialize()
        self.assertEqual(len(raw),80)
        self.assertEqual(BlockHeader.parse(raw),GENESIS)
        self.assertEqual(sha256d(raw)[::-1].hex(),GENESIS_HASH)
        self.assertTrue(GENESIS.has_valid_pow())
        mid=header_midstate(raw)
        for nonce in [0,1,GENESIS.nonce,0xFFFFFFFF]:
            header=GENESIS.with_nonce(nonce).serialize()
            self.assertEqual(finish_header(mid,header[64:]),sha256d(header))
    def test_malformed_header(self):
        for data in [bytes(79),bytes(81)]:
            with self.assertRaises(ValueError):BlockHeader.parse(data)
        with self.assertRaises(ValueError):replace(GENESIS,nonce=1<<32)

class BitcoinTests(unittest.TestCase):
    def test_targets_and_equality(self):
        target=compact_to_target(0x1D00FFFF,MAINNET_POW_LIMIT)
        self.assertEqual(target_to_compact(target),0x1D00FFFF)
        self.assertTrue(meets_target(target.to_bytes(32,"little"),target))
        self.assertFalse(meets_target((target+1).to_bytes(32,"little"),target))
        for bits in [0,0x1D80FFFF,0x23000001,0x22000100,0x21010000,0x01000001]:
            with self.assertRaises(ValueError):compact_to_target(bits)
        # Compact encoding truncates low bytes; canonical decode never exceeds original.
        for target in [1,0x80,0x1234,MAINNET_POW_LIMIT,UINT256_MAX]:
            decoded=compact_to_target(target_to_compact(target))
            self.assertLessEqual(decoded,target)
            self.assertEqual(target_to_compact(decoded),target_to_compact(target))
    def test_difficulty_precision_and_extreme_exponents(self):
        self.assertEqual(difficulty_target(1),DIFFICULTY_ONE)
        self.assertEqual(difficulty_target(2),DIFFICULTY_ONE//2)
        self.assertEqual(difficulty_target("1e-99999"),UINT256_MAX)
        self.assertEqual(difficulty_target("1e99999"),1)
        for value in ["NaN","Infinity","0","-1"]:
            with self.assertRaises(ValueError):difficulty_target(value)
    def test_merkle_mutation(self):
        a=bytes([1])*32;b=bytes([2])*32;c=bytes([3])*32
        odd,mutated=merkle_root([a,b,c]);even,bad=merkle_root([a,b,c,c])
        self.assertEqual(odd,even);self.assertFalse(mutated);self.assertTrue(bad)
        self.assertEqual(merkle_root([]),(bytes(32),False))
    def test_coinbase(self):
        self.assertEqual(compact_size(253),b"\xfd\xfd\x00")
        self.assertEqual(height_push(1),b"\x51")
        cb=build_coinbase(800000,b"nucleus",b"\x51",312500000)
        self.assertEqual(apply_coinbase_branch(cb,[]),hashlib.sha256(hashlib.sha256(cb).digest()).digest())
        with self.assertRaises(ValueError):build_coinbase(1,bytes(101),b"\x51",1)
    def test_family_boundaries(self):
        family=WorkFamily(GENESIS,0xFFFFFFFF,1,version_mask=2,min_time=GENESIS.timestamp,max_time=GENESIS.timestamp+1)
        self.assertEqual(len(list(family.headers())),1)
        self.assertEqual(family.roll(version=3).header.version,3)
        with self.assertRaises(ValueError):family.roll(version=5)
        with self.assertRaises(ValueError):family.roll(timestamp=GENESIS.timestamp+2)
        with self.assertRaises(ValueError):WorkFamily(GENESIS,0xFFFFFFFF,2)

if __name__=="__main__":unittest.main()
