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
