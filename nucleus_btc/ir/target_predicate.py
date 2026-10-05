"""Exact concrete-job SHA256d predicate; the root is inclusive Bitcoin <= target.

Graph specializes fixed workspace bits, folds constants/CSE, and removes every
node unreachable from the comparator. No finite-family truth tables are used.
"""
from struct import pack
from time import perf_counter

from .graph import Graph
from .nodes import execute, MASK
from .sha import compression_graph
from ..oracle.sha256 import IV


class PredicateBudget(MemoryError):
    pass


class BoundedGraph(Graph):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit

    def node(self, *args, **kwargs):
        result = super().node(*args, **kwargs)
        if len(self.nodes) > self.limit:
            raise PredicateBudget('Exact predicate graph exceeded node budget; retain workspace')
        return result


def compact(graph):
    live = graph.live_nodes()
    result, mapping = Graph(), {}
    for i, node in enumerate(graph.nodes):
        if i in live:
            mapping[i] = result.node(node.op, *(mapping[j] for j in node.args), value=node.value)
    result.outputs = [mapping[i] for i in graph.outputs]
    result.validate()
    return result, mapping


class TargetPredicate:
    def __init__(self, workspace, target, max_nodes=100000):
        if not 0 < target < 1 << 256 or not 128 <= max_nodes <= 100000:
            raise ValueError('Invalid target/predicate node budget')
        start = perf_counter()
        self.workspace, self.target = workspace, target
        self.trace = []
        self.always_true = target == (1 << 256)-1
        self.graph = BoundedGraph(max_nodes)
        g = self.graph
        self.setup_headers = 0
        if self.always_true:
            g.outputs = [g.const(1)]
            self.predicate_graph = g
            self.raw_nodes = 1
            self.compile_seconds = perf_counter()-start
            return
        template_trace = []
        template = compression_graph(observer=lambda r, s, w: template_trace.append((r, s, w)))
        def compression(state, words, label):
            inputs = {**{f's{i}': x for i, x in enumerate(state)}, **{f'w{i}': x for i, x in enumerate(words)}}
            mapping = []
            for n in template.nodes:
                mapping.append(inputs[n.value] if n.op == 'INPUT' else g.node(n.op, *(mapping[i] for i in n.args), value=n.value))
            for r, s, w in template_trace:
                self.trace.append({'compression': label, 'round': r, 'state': tuple(mapping[i] for i in s), 'W': mapping[w]})
            return [mapping[i] for i in template.outputs]
        def word_bytes(word, little=False):
            shifts = (0, 8, 16, 24) if little else (24, 16, 8, 0)
            return [g.node('AND', g.node('SHR', word, value=s), g.const(255)) for s in shifts]
        def to_words(data):
            return [g.node('OR', g.node('OR', g.node('SHL', data[i], value=24), g.node('SHL', data[i+1], value=16)),
                                  g.node('OR', g.node('SHL', data[i+2], value=8), data[i+3])) for i in range(0, len(data), 4)]
        def sha(data, label):
            length = len(data)
            if length > 1 << 20:
                raise PredicateBudget('Template byte budget exceeded; no work discarded')
            data = data+[g.const(128)]+[g.const(0)]*((55-length) % 64)+[g.const(x) for x in pack('>Q', length*8)]
            state = [g.const(x) for x in IV]
            for offset in range(0, len(data), 64):
                state = compression(state, to_words(data[offset:offset+64]), label+'/'+str(offset//64))
            return [b for word in state for b in word_bytes(word)]
        def double_sha(data, label):
            return sha(sha(data, label+'/first'), label+'/second')
        base = workspace.family.candidate(workspace.global_index(0))
        self.setup_headers = 1
        masks = workspace.masks()
        data = [g.const(x) for x in base.serialize()]
        for kind, offset, value in (('nonce', 76, base.nonce), ('version', 0, base.version), ('ntime', 68, base.timestamp)):
            if masks.get(kind):
                word = g.node('XOR', g.const(value), g.node('AND', g.input(kind), g.const(masks[kind])))
                data[offset:offset+4] = word_bytes(word, True)
        if masks.get('merkle_tail'):
            word = g.node('XOR', g.const(int.from_bytes(base.merkle_root[-4:], 'little')),
                          g.node('AND', g.input('merkle_tail'), g.const(masks['merkle_tail'])))
            data[64:68] = word_bytes(word, True)
        if any(d.kind.value == 'extranonce' for d in workspace.family.dimensions):
            f = workspace.family
            extra = int.from_bytes(f.extranonce, 'little')
            for i, value in workspace.fixed:
                kind, bit = f.variables[i]
                if kind == 'extranonce' and value:
                    extra ^= 1 << bit
            cb = [g.const(x) for x in f.coinbase_prefix]
            for offset in range(0, len(f.extranonce), 4):
                mask = (masks.get('extranonce', 0) >> (8*offset)) & MASK
                word = g.const((extra >> (8*offset)) & MASK)
                if mask:
                    word = g.node('XOR', word, g.node('AND', g.input('extranonce_'+str(offset//4)), g.const(mask)))
                cb.extend(word_bytes(word, True)[:min(4, len(f.extranonce)-offset)])
            cb.extend(g.const(x) for x in f.coinbase_suffix)
            # Match the existing HeaderFamily's explicit witness-txid boundary.
            concrete_cb = f.coinbase_prefix+extra.to_bytes(len(f.extranonce), 'little')+f.coinbase_suffix
            if len(concrete_cb) >= 6 and concrete_cb[4:6] == b'\x00\x01':
                raise ValueError('Witness coinbase requires an explicit txid-stripped template')
            root = double_sha(cb, 'coinbase')
            for j, sibling in enumerate(f.merkle_branch):
                root = double_sha(root+[g.const(x) for x in sibling], 'merkle/'+str(j))
            data[36:68] = root
        digest = double_sha(data, 'header')
        self.digest_nodes = tuple(to_words(digest))
        g.outputs = list(self.digest_nodes)
        self.raw_nodes = len(g.nodes)
        self.graph, mapping = compact(g)
        self.digest_nodes = tuple(self.graph.outputs)
        self.trace = [{**t, 'state': tuple(mapping.get(i) for i in t['state']), 'W': mapping.get(t['W'])} for t in self.trace]
        # Separate Boolean-root view, using only existing exact word operators.
        # The digest view remains available to the independent interval checker.
        # Slice backward from the inclusive comparator, rather than declaring
        # digest outputs to be the mining observable. Worst-case equality needs
        # every digest bit, so this does not imply cheap full-SHA evaluation.
        boolean = Graph.deserialize(self.graph.serialize())
        equal, less = boolean.const(1), boolean.const(0)
        for position in range(255, -1, -1):
            word, byte, bit = position//32, (position%32)//8, position%8
            raw_bit = (3-byte)*8+bit
            value = boolean.node('AND', boolean.node('SHR', self.digest_nodes[word], value=raw_bit), boolean.const(1))
            inverse = boolean.node('XOR', value, boolean.const(1))
            if (target >> position) & 1:
                less = boolean.node('OR', less, boolean.node('AND', equal, inverse))
                equal = boolean.node('AND', equal, value)
            else:
                equal = boolean.node('AND', equal, inverse)
        boolean.outputs = [boolean.node('OR', less, equal)]
        self.predicate_graph, _ = compact(boolean)
        self.compile_seconds = perf_counter()-start

    def evaluate(self, index):
        if self.always_true:
            if not 0 <= index < self.workspace.count:
                raise ValueError('Assignment outside workspace')
            return True
        return bool(self.predicate_graph.evaluate(self.workspace.inputs(index))[0])

    @property
    def fingerprint(self):
        from hashlib import sha256
        return sha256((self.workspace.fingerprint+str(self.target)+self.predicate_graph.fingerprint).encode()).hexdigest()

    def metadata(self):
        return {'conceptual_K': self.workspace.count, 'K_materialized': False,
                'nodes': len(self.graph.nodes), 'raw_nodes': self.raw_nodes,
                'dead_nodes_removed': self.raw_nodes-len(self.graph.nodes),
                'graph_bytes': len(self.graph.serialize()), 'compile_seconds': self.compile_seconds,
                'predicate_nodes': len(self.predicate_graph.nodes), 'predicate_bytes': len(self.predicate_graph.serialize()),
                'predicate_root_outputs': 1, 'storage_includes_digest_view': True,
                'setup_headers': self.setup_headers, 'root': 'exact inclusive little-endian uint256 comparator',
                'comparator_words': 0 if self.always_true else 8,
                'predicate_fingerprint': self.fingerprint, 'cost_grows_with_K': False}
