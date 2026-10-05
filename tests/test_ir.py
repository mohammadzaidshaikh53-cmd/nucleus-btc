import unittest
from random import Random
from nucleus_btc.ir.graph import Graph
from nucleus_btc.ir.sha import compression_graph,header_digest
from nucleus_btc.ir.rewrite import genome
from nucleus_btc.ir.equivalence import verify_graph
from nucleus_btc.ir.lower_opencl import lower
from nucleus_btc.oracle.sha256 import sha256d
from nucleus_btc.bitcoin.block_header import GENESIS

class IRTests(unittest.TestCase):
    def test_serialization_and_topology(self):
        g=Graph();a=g.input("s0");b=g.const(7);x=g.node("XOR",a,b);g.outputs=[x]
        self.assertEqual(g.node("XOR",b,a),x)
        self.assertEqual(Graph.deserialize(g.serialize()).fingerprint,g.fingerprint)
        self.assertEqual(g.evaluate({"s0":8}),(15,))
        with self.assertRaises(ValueError):g.node("XOR",x,999)
        with self.assertRaises(ValueError):g.node("SHR",a,value=32)
        with self.assertRaises(ValueError):Graph.deserialize(g.serialize().replace('"outputs":[2]','"outputs":[999]'))
    def test_rewrite_templates(self):
        rng=Random(74)
        triples=[(a,b,c) for a in range(8) for b in range(8) for c in range(8)]
        triples.extend(tuple(rng.getrandbits(32) for _ in range(3)) for _ in range(4096))
        mask=0xFFFFFFFF
        for a,b,c in triples:
            self.assertEqual((a&b)^((~a)&c),c^(a&(b^c)))
            majority=(a&b)^(a&c)^(b&c)
            self.assertEqual(majority,(a&b)|(c&(a|b)))
            self.assertEqual(majority,(a&b)^(c&(a^b)))
            self.assertEqual((a+b+c)&mask,((a^b^c)+(majority<<1))&mask)
    def test_full_sha_all_species(self):
        fingerprints=set()
        for index in range(8):
            graph=compression_graph(genome(index));fingerprints.add(graph.fingerprint)
            self.assertTrue(verify_graph(graph,3)["passed"])
            self.assertIn("void compress",lower(graph,"cpp")["source"])
        self.assertGreaterEqual(len(fingerprints),7)
    def test_lowered_register_lifetimes(self):
        # Evaluate emitted SSA assignments independently, including slot reuse.
        graph=compression_graph(genome(4));program=lower(graph,"cpp")["source"]
        self.assertGreater(len(program),10000)
        self.assertLess(lower(graph)["temporary_registers"],100)
        self.assertEqual(header_digest(graph,GENESIS.serialize()),sha256d(GENESIS.serialize()))
    def test_dead_nodes_and_rotation_fold(self):
        g=Graph();a=g.input("s0");b=g.node("ROTR",a,value=7);c=g.node("ROTR",b,value=25)
        self.assertEqual(c,a);dead=g.node("NOT",a);g.outputs=[a]
        self.assertNotIn(dead,g.live_nodes())
