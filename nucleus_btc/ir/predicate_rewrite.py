"""Bounded nonenumerating equivalence layer with independently checkable rules.

This is intentionally local equality saturation, not a full-SHA SAT search.
Library identities have declared universal uint32 preconditions. UNKNOWN from
an optional solver never adds a rule to this registry.
"""
import json
from hashlib import sha256
from time import perf_counter

from .graph import Graph
from .target_predicate import compact

RULES = {
    'xor-absorb': {'statement': 'x^(x&y)=x&~y', 'preconditions': 'uint32 words; bit-local operators', 'proof': 'exhaustive two-bit identity; independent bit positions'},
    'ch-xor': {'statement': '(x&y)^(~x&z) = z^(x&(y^z))', 'preconditions': 'uint32 words', 'proof': 'exhaustive one-bit identity; independent bit positions'},
    'maj-or': {'statement': '(x&y)^(x&z)^(y&z) = (x&y)|(z&(x|y))', 'preconditions': 'uint32 words', 'proof': 'exhaustive one-bit identity; independent bit positions'},
    'add-complement': {'statement': 'x+~x = 0xffffffff mod 2^32', 'preconditions': 'uint32 modular arithmetic', 'proof': 'per-bit complement gives one with no carry; induction over 32 bits'},
    'add-reassociate': {'statement': '(x+y)+z = x+(y+z) mod 2^32', 'preconditions': 'uint32 modular arithmetic', 'proof': 'associativity of the quotient ring Z/(2^32)'},
    'rotate-compose': {'statement': 'rotr(rotr(x,a),b)=rotr(x,(a+b)%32)', 'preconditions': 'uint32; counts 0..31', 'proof': 'composition of cyclic bit-index permutations'},
    'carry-save': {'statement': 'x+y+z=(x^y^z)+((xy|xz|yz)<<1) mod 2^32', 'preconditions': 'uint32; final carry resolved', 'proof': 'exhaustive three-bit sum followed by positional summation modulo 2^32'},
}


def rule_fingerprint(rule):
    if rule not in RULES:
        raise ValueError('Unproved rewrite rule')
    return sha256(json.dumps(RULES[rule], sort_keys=True).encode()).hexdigest()


def verify_rule(rule, fingerprint):
    """No discovery engine call; fixed trusted schemas plus independent truth checks."""
    if rule not in RULES or fingerprint != rule_fingerprint(rule):
        return False
    if rule in ('ch-xor', 'maj-or', 'carry-save', 'xor-absorb'):
        for x in range(2):
            for y in range(2):
                for z in range(2):
                    if rule == 'xor-absorb':
                        if (x^(x & y)) != (x & (1-y)): return False
                    elif rule == 'ch-xor':
                        if ((x & y)^((1-x) & z)) != (z^(x & (y^z))): return False
                    elif rule == 'maj-or':
                        if ((x & y)^(x & z)^(y & z)) != ((x & y)|(z & (x | y))): return False
                    elif x+y+z != (x^y^z)+2*((x & y)|(x & z)|(y & z)): return False
    return True


def saturate(graph, max_nodes=20000, seconds=.25, prefer='precision', lemmas=(), lemma_source=None):
    if prefer not in ('precision', 'opencl') or not 0 < seconds <= 5 or not 1 <= max_nodes <= 100000:
        raise ValueError('Invalid equality-saturation budget')
    start = perf_counter()
    output, mapping, proofs = Graph(), [], []
    # Learned bit-local identities may be instantiated by syntactic matching.
    # Finite-domain proofs cannot authorize an unrestricted symbolic rewrite.
    from ..verify.lemmas import verify_lemma
    patterns = []
    for record in list(lemmas)[:16]:
        if record.get('source') == lemma_source and record.get('checker') == 'lemma/v1' and record.get('proof', {}).get('type') == 'bit-local-universal' and verify_lemma(record):
            patterns.append((Graph.deserialize(record['statement']), record['fingerprint']))
    def learned(node_id):
        for pattern, identity in patterns:
            bindings = {}
            def match(p, actual):
                n, a = pattern.nodes[p], output.nodes[actual]
                if n.op == 'INPUT':
                    if n.value in bindings: return bindings[n.value] == actual
                    bindings[n.value] = actual; return True
                return n.op == a.op and n.value == a.value and len(n.args) == len(a.args) and all(match(x, y) for x, y in zip(n.args, a.args))
            if match(pattern.outputs[0], node_id):
                cache = {}
                def instantiate(p):
                    if p in cache: return cache[p]
                    n = pattern.nodes[p]
                    result = bindings[n.value] if n.op == 'INPUT' else output.node(n.op, *(instantiate(j) for j in n.args), value=n.value)
                    cache[p] = result; return result
                # RHS variables must have appeared in the matched LHS.
                rhs_inputs = {n.value for n in pattern.nodes if n.op == 'INPUT'}
                if not rhs_inputs <= set(bindings): continue
                replacement = instantiate(pattern.outputs[1])
                proofs.append({'rule': 'learned-bit-local-universal', 'proof_identity': identity})
                return replacement
        return node_id
    bounded = False
    for node in graph.nodes:
        if len(output.nodes) >= max_nodes or perf_counter()-start > seconds:
            bounded = True
            break
        args = [mapping[i] for i in node.args]
        op = node.op
        if op == 'ADD32':
            remaining = list(args)
            pair = None
            for x in remaining:
                for y in remaining:
                    if output.nodes[y].op == 'NOT' and output.nodes[y].args == (x,):
                        pair = x, y
                        break
                if pair: break
            if pair:
                for x in pair: remaining.remove(x)
                remaining.append(output.const(0xffffffff))
                result = remaining[0] if len(remaining) == 1 else output.node('ADD32', *remaining)
                proofs.append({'rule': 'add-complement', 'proof_identity': rule_fingerprint('add-complement')})
            else:
                result = output.node(op, *args, value=node.value)
        elif op == 'XOR' and prefer == 'opencl' and all(output.nodes[x].op == 'AND' for x in args):
            left, right = (output.nodes[x].args for x in args)
            found = None
            for e, f in (left, left[::-1]):
                for ne, g in (right, right[::-1]):
                    if output.nodes[ne].op == 'NOT' and output.nodes[ne].args == (e,):
                        found = e, f, g
            if found:
                e, f, g = found
                result = output.node('XOR', g, output.node('AND', e, output.node('XOR', f, g)))
                proofs.append({'rule': 'ch-xor', 'proof_identity': rule_fingerprint('ch-xor')})
            else:
                result = output.node(op, *args, value=node.value)
        else:
            result = output.node(op, *args, value=node.value)
        mapping.append(learned(result))
        if len(output.nodes) > max_nodes or perf_counter()-start > seconds:
            bounded = True
            break
    if bounded:
        return graph, {'status': 'UNKNOWN', 'reason': 'rewrite_budget', 'seconds': perf_counter()-start,
                       'input_nodes': len(graph.nodes), 'output_nodes': len(graph.nodes), 'proofs': [], 'retained_original': True}
    output.outputs = [mapping[i] for i in graph.outputs]
    output, _ = compact(output)
    if not all(p['rule'] == 'learned-bit-local-universal' and any(p['proof_identity'] == ident for _, ident in patterns) or verify_rule(p['rule'], p['proof_identity']) for p in proofs):
        raise AssertionError('Unverified rewrite entered predicate')
    return output, {'status': 'EXACT', 'seconds': perf_counter()-start, 'input_nodes': len(graph.nodes),
                    'output_nodes': len(output.nodes), 'proofs': proofs,
                    'analyses': {'precision': 'complement-carry elimination', 'opencl': 'Boolean selection form'},
                    'candidate_count_materialized': 0}
