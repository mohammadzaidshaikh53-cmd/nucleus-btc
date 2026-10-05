import unittest
from nucleus_btc.protocol.stratum_v2 import StandardChannel,StandardJob,version_for_index,valid_version_generator
from nucleus_btc.protocol.sv2_client import VERSION_MASK
from nucleus_btc.protocol.sv2_family import channel_family
from nucleus_btc.bitcoin.block_header import GENESIS

class SV2FamilyTests(unittest.TestCase):
    def test_24_bit_workspace_and_conceptual_family(self):
        self.assertEqual(VERSION_MASK.bit_count(),24)
        for index in (0,1,255,65535,(1<<24)-1):
            v=version_for_index(0x20000000,index,VERSION_MASK)
            self.assertEqual((v^0x20000000)&~VERSION_MASK,0)
        channel=StandardChannel(1,(1<<256)-1)
        channel.new_job(StandardJob(1,GENESIS.version,GENESIS.merkle_root,None,version_rolling_allowed=True,version_mask=VERSION_MASK))
        channel.activate(1,GENESIS.previous_hash,GENESIS.timestamp,GENESIS.bits)
        class Client:extended=False;flags=0
        client=Client();client.channel=channel
        family=channel_family(client);self.assertEqual(family.width,56)
        with self.assertRaises(ValueError):family.construct()
        small=channel_family(client,nonce_bits=(5,17),version_bits=(5,28))
        self.assertEqual(len({small.candidate(i).serialize() for i in range(16)}),16)
        channel.submission(0,GENESIS.timestamp,GENESIS.version^1<<5)
        with self.assertRaises(ValueError):channel.submission(0,GENESIS.timestamp,GENESIS.version^1<<4)
        client.flags=1
        with self.assertRaises(ValueError):channel_family(client,version_bits=(5,))
        self.assertEqual(len(set(valid_version_generator(1,(1<<5)|(1<<28)))),4)

    def test_nonce_exhaustion_rolls_permitted_version_without_duplicates(self):
        from types import SimpleNamespace
        from nucleus_btc.protocol.sv2_client import mine_session
        from nucleus_btc.gpu.backend import ScanResult
        channel=StandardChannel(1,1);channel.new_job(StandardJob(1,GENESIS.version,GENESIS.merkle_root,None))
        channel.activate(1,GENESIS.previous_hash,GENESIS.timestamp,GENESIS.bits)
        client=SimpleNamespace(channel=channel,flags=0,extended=False,ready=True,generation=0,examined=0,
                               pending={},ack_batches=[],evidence=[],timeout=.01,
                               stats={'submitted':0,'accepted':0,'rejected':0,'stale_discarded':0},handshake=lambda:None)
        client.pump=lambda seconds:False
        versions=[]
        class Backend:
            def scan(self,raw,start,count,target):
                versions.append(int.from_bytes(raw[:4],'little'))
                if len(versions)==513:client.ready=False
                return ScanResult([],count,0)
        result=mine_session(client,Backend(),seconds=1,batch_size=1<<24)
        self.assertEqual(versions[0],GENESIS.version)
        self.assertEqual(versions[256],GENESIS.version^(1<<5))
        self.assertEqual(versions[512],GENESIS.version^(1<<6))
        self.assertEqual(result['examined'],513*(1<<24))

    def test_extended_derived_merkle_cache_is_outer_workspace(self):
        from types import SimpleNamespace
        from nucleus_btc.protocol.sv2_client import ExtendedChannel,ExtendedJob
        channel=ExtendedChannel(1,(1<<256)-1,b'prefix',4)
        channel.new_job(ExtendedJob(1,GENESIS.version,None,False,(bytes(32),),b'fixture',b'end'))
        channel.activate(1,GENESIS.previous_hash,GENESIS.timestamp,GENESIS.bits)
        client=SimpleNamespace(channel=channel,extended=True,flags=0)
        family=channel_family(client,nonce_bits=(5,17),extranonce_bits=(0,9))
        headers,_=family.construct()
        self.assertEqual(len(set(headers)),16)
        self.assertEqual(family._derive_root.cache_info().misses,4)
        self.assertEqual(family._derive_root.cache_info().hits,12)
        with self.assertRaises(ValueError):channel_family(client,nonce_bits=(5,),version_bits=(5,))
