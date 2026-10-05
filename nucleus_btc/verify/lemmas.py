"""Independent finite Boolean/declared-domain lemma proof and reuse checks."""
import itertools
import json
from hashlib import sha256
from ..ir.graph import Graph
from ..ir.predicate_rewrite import rule_fingerprint, verify_rule


def fingerprint(statement, preconditions):
    return sha256(json.dumps({'statement': statement, 'preconditions': preconditions}, sort_keys=True).encode()).hexdigest()


def verify_lemma(record):
    proof = record.get('proof', {})
    statement = record.get('statement')
    preconditions = record.get('preconditions')
    if record.get('fingerprint') != fingerprint(statement, preconditions): return False
    kind = proof.get('type')
    if kind == 'canonical-uint32-rule':
        return statement == proof.get('rule') and preconditions == 'canonical rule preconditions' and verify_rule(statement, proof.get('identity'))
    if kind not in ('bit-local-universal', 'finite-domain'): return False
    try:
        graph = Graph.deserialize(statement)
        names = sorted({n.value for n in graph.nodes if n.op == 'INPUT'})
        if len(graph.nodes) > 128 or len(names) > 8 or len(graph.outputs) != 2: return False
        if kind == 'bit-local-universal':
            if preconditions != 'all uint32 inputs; bit-local operators only': return False
            if any(n.op not in ('INPUT', 'CONST32', 'XOR', 'AND', 'OR', 'NOT', 'MUX') or n.op == 'CONST32' and n.value not in (0, 0xffffffff) for n in graph.nodes): return False
            domains = [(0, 0xffffffff)]*len(names)
        else:
            if not isinstance(preconditions, dict) or set(preconditions) != set(names): return False
            domains = [preconditions[n] for n in names]
            if any(not values or any(not isinstance(x, int) or not 0 <= x <= 0xffffffff for x in values) for values in domains): return False
        cases = 1
        for domain in domains: cases *= len(domain)
        if cases > 256 or proof.get('cases') != cases: return False
        for assignment in itertools.product(*domains):
            a, b = graph.evaluate(dict(zip(names, assignment)))
            if a != b: return False
        return True
    except (ValueError, TypeError, KeyError): return False


def applicable(record, inputs, source, checker='lemma/v1'):
    if record.get('source') != source or record.get('checker') != checker or not verify_lemma(record): return False
    if record['proof']['type'] == 'finite-domain':
        return set(inputs) == set(record['preconditions']) and all(inputs[n] in allowed for n, allowed in record['preconditions'].items())
    return all(isinstance(x, int) and 0 <= x <= 0xffffffff for x in inputs.values())
