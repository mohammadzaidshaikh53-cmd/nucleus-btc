"""Sound nonenumerating reduced product over exact uint32 graph operations.

KnownBits is a cube; Congruence is an intersection of residue classes; sparse
ANF/parity expressions are exact equations in input bits until widened to TOP.
CarryEnvelope contains every possible unsigned carry. None means TOP, never a
discarded monomial. All narrowing follows an implied exact equation.
"""
from dataclasses import dataclass
from math import log2
from time import perf_counter

from .middle_cut import KnownWord as KnownBits, cube_sum
from ..ir.nodes import MASK, execute

ZERO = frozenset()
ONE = frozenset((frozenset(),))


@dataclass(frozen=True)
class DomainBudget:
    terms: int = 8
    degree: int = 2
    reduction_iterations: int = 4
    max_nodes: int = 20000

    def __post_init__(self):
        if not 1 <= self.terms <= 64 or not 1 <= self.degree <= 4 or not 1 <= self.reduction_iterations <= 8 or not 1 <= self.max_nodes <= 100000:
            raise ValueError('Invalid abstract domain budget')


def pxor(a, b):
    return None if a is None or b is None else a ^ b


def pmul(a, b, budget):
    if a == ZERO or b == ZERO:
        return ZERO
    if a is None or b is None:
        return None
    out = set()
    for x in a:
        for y in b:
            term = x | y
            if len(term) > budget.degree:
                return None
            if term in out:
                out.remove(term)
            else:
                out.add(term)
            if len(out) > budget.terms:
                return None
    return frozenset(out)


def bounded(poly, budget):
    return None if poly is not None and (len(poly) > budget.terms or any(len(x) > budget.degree for x in poly)) else poly


@dataclass(frozen=True)
class Congruence:
    bits: int = 0
    residue: int = 0
    odd: tuple = ()

    def __post_init__(self):
        if not 0 <= self.bits <= 32 or not 0 <= self.residue < 1 << self.bits:
            raise ValueError('Invalid power-of-two congruence')
        if any(m not in (3, 5) or not 0 <= r < m for m, r in self.odd) or len(dict(self.odd)) != len(self.odd):
            raise ValueError('Only bounded moduli 3 and 5 are supported')

    def contains(self, value):
        return value % (1 << self.bits) == self.residue and all(value % m == r for m, r in self.odd)


@dataclass(frozen=True)
class CarryEnvelope:
    low: int
    high: int
    operands: int

    def __post_init__(self):
        if not 0 <= self.low <= self.high <= self.operands-1:
            raise ValueError('Invalid exact unsigned carry envelope')


@dataclass
class AbstractWord:
    known: KnownBits
    congruence: Congruence
    polynomial: tuple
    parity: tuple
    carry: CarryEnvelope | None = None

    def contains(self, value):
        return self.known.contains(value) and self.congruence.contains(value)


def constant_word(value):
    p = tuple(ONE if value & (1 << b) else ZERO for b in range(32))
    return AbstractWord(KnownBits(value), Congruence(32, value, ((3, value % 3), (5, value % 5))), p, p)


def reduce_word(word, budget, counts):
    for iteration in range(budget.reduction_iterations):
        old = (word.known, word.congruence, word.polynomial, word.parity)
        value, known = word.known.value, word.known.known
        for bit, poly in enumerate(word.polynomial):
            if poly in (ZERO, ONE):
                wanted = int(poly == ONE)
                if known & (1 << bit) and ((value >> bit) & 1) != wanted:
                    raise AssertionError('Inconsistent sound abstract facts')
                if not known & (1 << bit):
                    counts['nonlinear_to_known'] = counts.get('nonlinear_to_known', 0)+1
                    known |= 1 << bit
                    value |= wanted << bit
        low_mask = (1 << word.congruence.bits)-1
        if (value ^ word.congruence.residue) & known & low_mask:
            raise AssertionError('Contradictory congruence/known-bits facts')
        added = low_mask & ~known
        if added:
            counts['congruence_to_known'] = counts.get('congruence_to_known', 0)+added.bit_count()
        value = (value & ~low_mask) | word.congruence.residue
        known |= low_mask
        word.known = KnownBits(value, known)
        bits = 0
        while bits < 32 and known & (1 << bits):
            bits += 1
        if bits > word.congruence.bits:
            counts['known_to_congruence'] = counts.get('known_to_congruence', 0)+bits-word.congruence.bits
            word.congruence = Congruence(bits, value & ((1 << bits)-1), word.congruence.odd)
        if known == MASK:
            word.congruence = Congruence(32, value, ((3, value % 3), (5, value % 5)))
        polynomial, parity = list(word.polynomial), list(word.parity)
        for b in range(32):
            if known & (1 << b):
                polynomial[b] = ONE if value & (1 << b) else ZERO
            p = polynomial[b]
            if p is not None and all(len(term) <= 1 for term in p):
                if parity[b] is None:
                    counts['nonlinear_to_parity'] = counts.get('nonlinear_to_parity', 0)+1
                parity[b] = p
            else:
                parity[b] = None
        word.polynomial, word.parity = tuple(polynomial), tuple(parity)
        counts['iterations'] = max(counts.get('iterations', 0), iteration+1)
        if old == (word.known, word.congruence, word.polynomial, word.parity):
            return word
    # The finite pass limit retains the last sound facts; absence of convergence
    # cannot manufacture BOTTOM or cause any rejection.
    counts['fixed_point_budget_hits'] = counts.get('fixed_point_budget_hits', 0)+1
    return word


def polynomial_transfer(node, args, budget):
    op = node.op
    p = [a.polynomial for a in args]
    if op == 'NOT':
        return tuple(pxor(x, ONE) for x in p[0])
    if op in ('ROTR', 'SHR', 'SHL'):
        n = node.value
        return tuple(p[0][(b+n) % 32] if op == 'ROTR' else
                     p[0][b+n] if op == 'SHR' and b+n < 32 else
                     p[0][b-n] if op == 'SHL' and b >= n else ZERO for b in range(32))
    if op == 'ADD32':
        current = p[0]
        for operand in p[1:]:
            carry, result = ZERO, []
            for a, b in zip(current, operand):
                pair = pxor(a, b)
                result.append(bounded(pxor(pair, carry), budget))
                carry = bounded(pxor(pmul(a, b, budget), pmul(carry, pair, budget)), budget)
            current = tuple(result)
        return current
    result = []
    for bit in range(32):
        a, b = p[0][bit], p[1][bit]
        if op == 'XOR':
            poly = pxor(a, b)
        elif op == 'AND':
            poly = pmul(a, b, budget)
        elif op == 'OR':
            poly = pxor(pxor(a, b), pmul(a, b, budget))
        elif op == 'MUX':
            c = p[2][bit]
            poly = pxor(pmul(a, b, budget), pmul(pxor(a, ONE), c, budget))
        else:
            raise ValueError('Unsupported polynomial transfer')
        result.append(bounded(poly, budget))
    return tuple(result)


def transfer(node, args, budget, counts, nonlinear=True):
    if node.op == 'CONST32':
        return constant_word(node.value)
    if node.op == 'INPUT':
        p = tuple(frozenset((frozenset(((node.value, bit),)),)) for bit in range(32)) if nonlinear else (None,)*32
        return AbstractWord(KnownBits(0, 0), Congruence(), p, p)
    kb = [a.known for a in args]
    op = node.op
    carry = None
    if op == 'ADD32':
        known = cube_sum(*kb)
        carry = CarryEnvelope(sum(x.value for x in kb) >> 32,
                              sum(x.value | (~x.known & MASK) for x in kb) >> 32, len(args))
    elif op == 'XOR': known = kb[0] ^ kb[1]
    elif op == 'AND': known = kb[0] & kb[1]
    elif op == 'OR': known = ~((~kb[0]) & (~kb[1]))
    elif op == 'NOT': known = ~kb[0]
    elif op == 'ROTR': known = kb[0].rotate(node.value)
    elif op == 'SHR': known = kb[0].shift(node.value) if node.value else kb[0]
    elif op == 'SHL': known = KnownBits(kb[0].value << node.value, (kb[0].known << node.value) | ((1 << node.value)-1))
    elif op == 'MUX': known = (kb[0] & kb[1]) ^ ((~kb[0]) & kb[2])
    else: raise ValueError('Unsupported domain operation')
    congruence = Congruence()
    if op == 'ADD32':
        bits = min(a.congruence.bits for a in args)
        odd = []
        if carry.low == carry.high:
            for modulus in (3, 5):
                if all(modulus in dict(a.congruence.odd) for a in args):
                    odd.append((modulus, (sum(dict(a.congruence.odd)[modulus] for a in args)-(1 << 32)*carry.low) % modulus))
        congruence = Congruence(bits, sum(a.congruence.residue for a in args) % (1 << bits), tuple(odd))
    polynomial = polynomial_transfer(node, args, budget) if nonlinear else (None,)*32
    counts['widened_bit_expressions'] = counts.get('widened_bit_expressions', 0)+sum(p is None for p in polynomial)
    word = AbstractWord(known, congruence, polynomial, (None,)*32, carry)
    return reduce_word(word, budget, counts)


@dataclass(frozen=True)
class TargetDomain:
    lower: int
    upper: int
    target: int

    @property
    def status(self):
        return 'UNSAT' if self.lower > self.target else 'ALL_PASS' if self.upper <= self.target else 'UNKNOWN'

    @property
    def information(self):
        return max(0., 256-log2(self.upper-self.lower+1))


def target_bounds(words, target):
    lower = upper = 0
    for j, word in enumerate(words):
        lo = int.from_bytes(word.known.value.to_bytes(4, 'big'), 'little')
        hi = int.from_bytes((word.known.value | (~word.known.known & MASK)).to_bytes(4, 'big'), 'little')
        lower |= lo << (32*j)
        upper |= hi << (32*j)
    return TargetDomain(lower, upper, target)


def analyze(predicate, budget=None, nonlinear=True):
    budget = budget or DomainBudget()
    started = perf_counter()
    counts, values = {}, []
    graph = predicate.graph
    if len(graph.nodes) > budget.max_nodes:
        return {'status': 'UNKNOWN', 'reason': 'abstract_node_budget', 'retained': predicate.workspace.count,
                'domain_seconds': perf_counter()-started, 'K_materialized': False, 'values': None,
                'counts': {}, 'round_precision': [], 'target_information': 0.}
    for node in graph.nodes:
        values.append(transfer(node, [values[i] for i in node.args], budget, counts, nonlinear))
    if predicate.always_true:
        bounds = TargetDomain(0, (1 << 256)-1, predicate.target)
    else:
        bounds = target_bounds([values[i] for i in graph.outputs], predicate.target)
    rounds = []
    for row in predicate.trace:
        known = sum(values[i].known.known.bit_count() for i in row['state'] if i is not None)
        nonlinear_bits = sum(p is not None for i in row['state'] if i is not None for p in values[i].polynomial)
        constants = row.get('constant_state', (None,)*8)
        folded_bits = 32*sum(i is None and c is not None for i, c in zip(row['state'], constants))
        untracked_bits = 32*sum(i is None and c is None for i, c in zip(row['state'], constants))
        rounds.append({'compression': row['compression'], 'round': row['round'],
                       'known_state_bits': known+folded_bits, 'retained_sparse_nonlinear_bits': nonlinear_bits+folded_bits,
                       'constant_folded_state_bits': folded_bits, 'untracked_dead_state_bits': untracked_bits})
    # Logical storage is explicit; process peak is measured by the runner.
    monomials = sum(len(p) for word in values for p in word.polynomial if p is not None)
    return {'status': bounds.status, 'bounds': (bounds.lower, bounds.upper),
            'target_information': bounds.information, 'counts': counts, 'round_precision': rounds,
            'values': values, 'abstract_nodes': len(values), 'monomial_count': monomials,
            'logical_representation_bytes_estimate': len(values)*96+monomials*32,
            'representation_byte_scope': 'logical estimate excludes Python object overhead',
            'domain_seconds': perf_counter()-started, 'K_materialized': False,
            'enumerated_candidates': 0, 'cost_grows_with_K': False}
