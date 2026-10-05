"""Two causal follow-ups after sparse nonlinear expansion widens to TOP.

Opaque carry/Boolean atoms preserve exact XOR lineage without expanding high
degree polynomials. Backward demand propagates only exact inverse operations
with explicit preconditions. These facts are conditional on target feasibility,
and are not advertised as family rejection or solved headers.
"""
from collections import Counter
from time import perf_counter
from .domains import ZERO, ONE, KnownBits
from ..ir.nodes import MASK


def xor(*expressions, limit=32):
    if any(x is None for x in expressions): return None
    result = frozenset()
    for expression in expressions: result ^= expression
    return result if len(result) <= limit else None


def lineage(graph, support_limit=32):
    if not 1 <= support_limit <= 128: raise ValueError('Invalid parity support budget')
    started = perf_counter(); values = []; counts = Counter()
    zero, one = frozenset(), frozenset((('constant',),))
    def atom(i, bit, role='boolean'): return frozenset(((role, i, bit),))
    def band(a, b, i, bit):
        if a == zero or b == zero: return zero
        if a == one: return b
        if b == one or a == b: return a
        if xor(a, b, limit=support_limit) == one: return zero
        counts['opaque_nonlinear_atoms'] += 1
        return atom(i, bit)
    for i, n in enumerate(graph.nodes):
        a = [values[j] for j in n.args]; op = n.op
        if op == 'CONST32': p = tuple(one if n.value & (1 << b) else zero for b in range(32))
        elif op == 'INPUT': p = tuple(atom(n.value, b, 'input') for b in range(32))
        elif op == 'NOT': p = tuple(xor(x, one, limit=support_limit) for x in a[0])
        elif op in ('ROTR', 'SHR', 'SHL'):
            shift = n.value
            p = tuple(a[0][(b+shift) % 32] if op == 'ROTR' else a[0][b+shift] if op == 'SHR' and b+shift < 32 else a[0][b-shift] if op == 'SHL' and b >= shift else zero for b in range(32))
        elif op == 'ADD32':
            current = a[0]
            for operand_index, operand in enumerate(a[1:]):
                result, carry = [], zero
                for bit, (x, y) in enumerate(zip(current, operand)):
                    result.append(xor(x, y, carry, limit=support_limit))
                    # Known/complementary Boolean operands permit exact carry
                    # elimination; otherwise introduce an existential exact
                    # majority atom. It is not an omitted carry assumption.
                    if x == y and x is not None: carry = x
                    elif x == zero: carry = band(y, carry, (i, operand_index), bit)
                    elif y == zero: carry = band(x, carry, (i, operand_index), bit)
                    elif xor(x, y, limit=support_limit) == one: pass
                    else:
                        carry = atom((i, operand_index), bit, 'majority-carry')
                        counts['opaque_carry_atoms'] += 1
                current = tuple(result)
            p = current
        else:
            result = []
            for bit in range(32):
                x, y = a[0][bit], a[1][bit]
                if op == 'XOR': value = xor(x, y, limit=support_limit)
                elif op == 'AND': value = band(x, y, i, bit)
                elif op == 'OR': value = xor(x, y, band(x, y, i, bit), limit=support_limit)
                elif op == 'MUX':
                    z = a[2][bit]
                    if x == zero: value = z
                    elif x == one: value = y
                    elif y == z and y is not None: value = y
                    else: value = atom(i, bit, 'select')
                else: raise ValueError('Unsupported lineage operation')
                result.append(value)
            p = tuple(result)
        counts['support_widenings'] += sum(x is None for x in p)
        values.append(p)
    output_known = []
    for node in graph.outputs:
        value = known = 0
        for b, expression in enumerate(values[node]):
            if expression in (zero, one):
                known |= 1 << b; value |= int(expression == one) << b
        output_known.append(KnownBits(value, known))
    return {'values': values, 'output_known': output_known, 'counts': dict(counts),
            'seconds': perf_counter()-started, 'candidate_count_materialized': 0,
            'contract': 'affine equations in inputs and existential exact Boolean/carry atoms; support overflow widens to TOP'}


def backward_demand(predicate, analysis, max_steps=256):
    if not 1 <= max_steps <= 4096: raise ValueError('Invalid inverse-transfer budget')
    started = perf_counter()
    if predicate.always_true or predicate.target >> 224 or analysis.get('values') is None:
        return {'status': 'UNKNOWN', 'reason': 'zero-high-word precondition unavailable', 'steps': [], 'seconds': perf_counter()-started}
    nodes, values = predicate.graph.nodes, analysis['values']
    pending = [(predicate.graph.outputs[7], 0)]
    demands, steps, losses = {}, [], []
    contradiction = False
    while pending and len(steps) < max_steps:
        node_id, wanted = pending.pop()
        if node_id in demands:
            if demands[node_id] != wanted: contradiction = True
            continue
        demands[node_id] = wanted
        known = values[node_id].known
        if not known.contains(wanted): contradiction = True
        n = nodes[node_id]
        if n.op == 'CONST32':
            continue
        if n.op in ('NOT', 'ROTR'):
            actual = (~wanted) & MASK if n.op == 'NOT' else ((wanted << n.value)|(wanted >> ((32-n.value) % 32))) & MASK if n.value else wanted
            pending.append((n.args[0], actual))
            steps.append({'rule': 'inverse-'+n.op.lower(), 'output': node_id, 'input': n.args[0], 'value': actual})
        elif n.op in ('ADD32', 'XOR'):
            unknown = [j for j in n.args if values[j].known.known != MASK]
            if len(unknown) == 1:
                constants = [values[j].known.value for j in n.args if j != unknown[0]]
                if n.op == 'ADD32': actual = (wanted-sum(constants)) & MASK
                else:
                    actual = wanted
                    for c in constants: actual ^= c
                pending.append((unknown[0], actual))
                steps.append({'rule': 'inverse-'+n.op.lower()+'-one-unknown', 'output': node_id, 'input': unknown[0], 'value': actual})
            else:
                losses.append({'node': node_id, 'operation': n.op, 'unknown_operands': len(unknown),
                               'reason': 'joint nonlinear/schedule/carry relation required; independent inverse is universal'})
        else:
            losses.append({'node': node_id, 'operation': n.op, 'reason': 'inverse transformer not proved; retain all possibilities'})
    return {'status': 'UNSAT_CANDIDATE' if contradiction else 'UNKNOWN', 'steps': steps,
            'conditional_known_bits': len(demands)*32, 'losses': losses,
            'budget_widened': bool(pending), 'seconds': perf_counter()-started,
            'pruning_authorized': False, 'candidate_count_materialized': 0}
