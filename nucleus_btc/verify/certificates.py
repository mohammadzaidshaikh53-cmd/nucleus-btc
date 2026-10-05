"""Independent typed rejection checker: no discovery/domain/refinement imports.

Large-workspace proofs replay simple, conservative known-bit transfers over the
canonical exact predicate. The optional finite type declares and charges every
enumerated header, and is rejected outside <=256 candidates. Other proof types
are accepted only through explicit, independently checked transfer schemas.
"""
import json
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from ..ir.target_predicate import TargetPredicate
from ..ir.predicate_rewrite import verify_rule, rule_fingerprint

MASK = 0xffffffff
CHECKER_VERSION = 'target-certificate/v1'
ROOT = Path(__file__).resolve().parents[2]


def source_fingerprint():
    digest = sha256()
    for name in ('nucleus_btc/verify/certificates.py', 'nucleus_btc/ir/target_predicate.py',
                 'nucleus_btc/family_ir/symbolic.py', 'nucleus_btc/ir/graph.py'):
        digest.update(name.encode()); digest.update((ROOT/name).read_bytes())
    return digest.hexdigest()


def _replay(graph):
    """Independent tuple-mask implementation; never trusts producer bounds."""
    values = []
    def inv(x): return ((~x[0]) & x[1] & MASK, x[1])
    def band(x, y):
        ones = x[0] & y[0]
        zeros = (x[1] & ~x[0]) | (y[1] & ~y[0])
        return ones, (ones | zeros) & MASK
    def bxor(x, y):
        mask = x[1] & y[1]
        return (x[0]^y[0]) & mask, mask
    for n in graph.nodes:
        a = [values[i] for i in n.args]
        op = n.op
        if op == 'INPUT': result = (0, 0)
        elif op == 'CONST32': result = (n.value, MASK)
        elif op == 'NOT': result = inv(a[0])
        elif op == 'AND': result = band(*a)
        elif op == 'XOR': result = bxor(*a)
        elif op == 'OR': result = inv(band(inv(a[0]), inv(a[1])))
        elif op == 'MUX': result = bxor(band(a[0], a[1]), band(inv(a[0]), a[2]))
        elif op == 'ROTR':
            shift = n.value
            result = tuple(((v >> shift) | (v << ((32-shift) % 32))) & MASK for v in a[0]) if shift else a[0]
        elif op == 'SHR':
            shift = n.value
            result = (a[0][0] >> shift, ((a[0][1] >> shift) | (MASK << (32-shift))) & MASK) if shift else a[0]
        elif op == 'SHL':
            shift = n.value
            result = ((a[0][0] << shift) & MASK, ((a[0][1] << shift) | ((1 << shift)-1)) & MASK)
        elif op == 'ADD32':
            lo = hi = 0
            value = known = 0
            for bit in range(32):
                # An interval of carry values is an overapproximation to the
                # producer's exact finite carry set, hence independently safe.
                low_sum = lo+sum(((v >> bit) & 1) if k & (1 << bit) else 0 for v, k in a)
                high_sum = hi+sum(((v >> bit) & 1) if k & (1 << bit) else 1 for v, k in a)
                if low_sum == high_sum:
                    known |= 1 << bit
                    value |= (low_sum & 1) << bit
                lo, hi = low_sum >> 1, high_sum >> 1
            result = value, known
        else: raise ValueError('Unsupported certificate opcode')
        values.append(result)
    return [values[i] for i in graph.outputs]


def make_certificate(workspace, target, predicate, analysis, kind='interval'):
    if analysis['status'] != 'UNSAT' or kind not in ('interval', 'congruence', 'parity'):
        raise ValueError('Only a declared contradiction may emit a certificate')
    certificate = {'schema': 1, 'type': kind, 'workspace': workspace.fingerprint, 'target': str(target),
            'predicate': predicate.fingerprint, 'source': source_fingerprint(), 'checker': CHECKER_VERSION,
            'byte_order': 'raw-digest-little-endian', 'inclusive': True,
            'rule': 'known-mask-carry-envelope/v1', 'lower': str(analysis['bounds'][0]),
            'proof_identities': [{'rule': r, 'fingerprint': rule_fingerprint(r)} for r in ('add-reassociate', 'rotate-compose')]}
    if kind in ('parity', 'congruence'):
        word = analysis['values'][predicate.graph.outputs[7]].known
        value = int.from_bytes(word.value.to_bytes(4, 'big'), 'little')
        known = int.from_bytes(word.known.to_bytes(4, 'big'), 'little')
        if target >> 224:
            raise ValueError('Projected contradiction needs a zero target high word')
        if kind == 'parity':
            one = value & known
            if not one: raise ValueError('No known odd parity separator')
            certificate.update(separator_mask=one & -one, separator_parity=1)
        else:
            bits = 0
            while bits < 32 and known & (1 << bits): bits += 1
            residue = value & ((1 << bits)-1)
            if not residue: raise ValueError('No nonzero low congruence')
            certificate.update(residue_bits=bits, residue=residue)
    return certificate


def check_certificate(certificate, workspace, target):
    start = perf_counter()
    result = {'valid': False, 'check_seconds': 0., 'enumerated_candidates': 0, 'checker': CHECKER_VERSION}
    try:
        if len(json.dumps(certificate)) > 16384:
            raise ValueError('Certificate size budget')
        if certificate.get('schema') != 1 or certificate.get('checker') != CHECKER_VERSION or certificate.get('workspace') != workspace.fingerprint or certificate.get('target') != str(target):
            raise ValueError('Wrong certificate scope or target')
        if certificate.get('source') != source_fingerprint() or certificate.get('byte_order') != 'raw-digest-little-endian' or certificate.get('inclusive') is not True:
            raise ValueError('Source/endianness/precondition mismatch')
        if certificate.get('type') == 'finite-exact':
            if workspace.count > 256 or certificate.get('count') != workspace.count:
                raise ValueError('Finite proof scope violation')
            for i in range(workspace.count):
                raw = workspace.header(i)
                if int.from_bytes(sha256(sha256(raw).digest()).digest(), 'little') <= target:
                    raise ValueError('Finite certificate lost a valid candidate')
            result['enumerated_candidates'] = workspace.count
        else:
            if certificate.get('type') not in ('interval', 'congruence', 'parity') or certificate.get('rule') != 'known-mask-carry-envelope/v1':
                raise ValueError('Unsupported proof schema')
            identities = certificate.get('proof_identities')
            expected = [{'rule': r, 'fingerprint': rule_fingerprint(r)} for r in ('add-reassociate', 'rotate-compose')]
            if identities != expected or not all(verify_rule(p['rule'], p['fingerprint']) for p in identities):
                raise ValueError('Rule proof identity mismatch')
            predicate = TargetPredicate(workspace, target)
            if predicate.fingerprint != certificate.get('predicate') or predicate.always_true:
                raise ValueError('Wrong predicate binding')
            outputs = _replay(predicate.graph)
            lower = sum(int.from_bytes(value.to_bytes(4, 'big'), 'little') << (32*j) for j, (value, _) in enumerate(outputs))
            if lower != int(certificate['lower']) or lower <= target:
                raise ValueError('No independently reproduced target contradiction')
            # These types use the declared same conservative transfer proof.
            # Parity/residue facts are projected known-mask contradictions; an
            # arbitrary learned cross-word lemma is deliberately unsupported.
            if certificate['type'] in ('parity', 'congruence') and target >> 224:
                raise ValueError('Projected zero-prefix precondition required')
            if certificate['type'] in ('parity', 'congruence'):
                value, known = outputs[7]
                value = int.from_bytes(value.to_bytes(4, 'big'), 'little')
                known = int.from_bytes(known.to_bytes(4, 'big'), 'little')
                if certificate['type'] == 'parity':
                    mask = certificate.get('separator_mask', 0)
                    if not 0 < mask <= MASK or mask & ~known or certificate.get('separator_parity') != 1 or (value & mask).bit_count() % 2 != 1:
                        raise ValueError('Invalid independent parity separator')
                else:
                    bits = certificate.get('residue_bits', 0)
                    residue = certificate.get('residue', 0)
                    if not 1 <= bits <= 32 or known & ((1 << bits)-1) != (1 << bits)-1 or residue != value % (1 << bits) or not residue:
                        raise ValueError('Invalid independent congruence contradiction')
        result['valid'] = True
    except (ValueError, KeyError, TypeError, MemoryError, OverflowError) as error:
        result['reason'] = str(error)
    result['check_seconds'] = perf_counter()-start
    return result
