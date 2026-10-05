"""Bounded, exact necessary relations at second-SHA round boundaries.

Two overapproximations are deliberately distinct: independent known bits and a
joint affine hull of (cut state, first digest). Both contain every actual family
member. Neither SAT nor UNKNOWN authorizes deleting a candidate. The affine
hull's enumeration cost is measured, never hidden as free preprocessing.
"""
from dataclasses import dataclass
from hashlib import sha256
from struct import pack, unpack
from time import perf_counter

from ..oracle.sha256 import IV, K, MASK, compress, rotr


def schedule(words):
    w = list(words)
    if len(w) != 16:
        raise ValueError('A schedule needs sixteen uint32 words')
    for t in range(16, 64):
        x, y = w[t-15], w[t-2]
        w.append((w[t-16] + (rotr(x, 7)^rotr(x, 18)^(x >> 3)) +
                  w[t-7] + (rotr(y, 17)^rotr(y, 19)^(y >> 10))) & MASK)
    return tuple(w)


def step(s, w, t):
    a, b, c, d, e, f, g, h = s
    t1 = (h + (rotr(e, 6)^rotr(e, 11)^rotr(e, 25)) +
          ((e & f)^((~e) & g)) + K[t] + w) & MASK
    t2 = ((rotr(a, 2)^rotr(a, 13)^rotr(a, 22)) +
          ((a & b)^(a & c)^(b & c))) & MASK
    return ((t1+t2)&MASK, a, b, c, (d+t1)&MASK, e, f, g)


def inverse_step(s, w, t):
    """The round is a permutation of state when its schedule word is fixed."""
    aa, a, b, c, ee, e, f, g = s
    t2 = ((rotr(a, 2)^rotr(a, 13)^rotr(a, 22)) +
          ((a & b)^(a & c)^(b & c))) & MASK
    t1 = (aa-t2) & MASK
    d = (ee-t1) & MASK
    h = (t1-(rotr(e, 6)^rotr(e, 11)^rotr(e, 25))-
         ((e & f)^((~e) & g))-K[t]-w) & MASK
    return (a, b, c, d, e, f, g, h)


def trace_header(header, cuts=(31, 47, 55, 59, 60), midstate=None):
    """Construct the real boundary and first digest; no full second SHA here."""
    if len(header) != 80 or not cuts or any(not 0 <= c <= 60 for c in cuts):
        raise ValueError('Invalid header or cut')
    mid = compress(IV, header[:64]) if midstate is None else midstate
    first = compress(mid, header[64:]+b'\x80'+bytes(39)+pack('>Q', 640))
    words = schedule(first+(0x80000000,)+(0,)*6+(256,))
    s = IV
    result = {}
    for t in range(max(cuts)+1):
        s = step(s, words[t], t)
        if t in cuts:
            result[t] = s+first
    return result


def trace_family(family, cuts):
    begun = perf_counter()
    headers, construction = family.construct()
    cache, traces = {}, []
    for header in headers:
        prefix = header[:64]
        if prefix not in cache:
            cache[prefix] = compress(IV, prefix)
        traces.append(trace_header(header, cuts, cache[prefix]))
    return headers, traces, {'total_seconds': perf_counter()-begun,
                            'header_construction_seconds': construction,
                            'unique_midstates': len(cache)}


def pack_words(words):
    return sum(x << (32*j) for j, x in enumerate(words))


def unpack_words(value, count=16):
    return tuple((value >> (32*j)) & MASK for j in range(count))


def affine_basis(values):
    """Exact GF(2) affine superset, with cross-word correlations preserved."""
    values = tuple(values)
    if not values:
        raise ValueError('Empty family')
    base = values[0]
    pivots = {}
    for value in values[1:]:
        residual = value ^ base
        while residual:
            bit = residual.bit_length()-1
            if bit not in pivots:
                pivots[bit] = residual
                break
            residual ^= pivots[bit]
    return base, tuple(pivots[k] for k in sorted(pivots, reverse=True))


def affine_contains(value, base, basis):
    residual = value ^ base
    for vector in basis:
        bit = vector.bit_length()-1
        if residual & (1 << bit):
            residual ^= vector
    return residual == 0


def affine_target_cut(vectors, target):
    """Solver-free exact elimination at the cut after second-SHA round 60.

    If target's high word is zero, every solution needs e60 == -IV7 mod 2**32.
    GF(2) elimination either supplies a joint-boundary witness or a parity
    separator proving this necessary value is outside the affine superset.
    This proves a projection property, not a full target solution.
    """
    if not 0 < target < 1 << 256:
        raise ValueError('Invalid target')
    vectors = tuple(vectors)
    if not vectors or len(vectors) > 4096 or any(not 0 <= x < 1 << 512 for x in vectors):
        raise ValueError('Invalid boundary family')
    started = perf_counter()
    report = {'method': 'GF2 target-word elimination', 'K': len(vectors), 'cut': 60,
              'pruning_authorized': False, 'pruned': 0, 'retained': len(vectors)}
    if target >> 224:
        return {**report, 'status': 'UNKNOWN', 'reason': 'requires_zero_target_high_word',
                'total_seconds': perf_counter()-started}
    base, basis = affine_basis(vectors)
    base_e = (base >> 128) & MASK
    wanted = (-IV[7]) & MASK
    delta = wanted ^ base_e
    projected = tuple((v >> 128) & MASK for v in basis)
    rows = {}
    contradiction = None
    for bit in range(32):
        coefficients = sum(((v >> bit) & 1) << j for j, v in enumerate(projected))
        rhs, certificate = (delta >> bit) & 1, 1 << bit
        while coefficients:
            pivot = coefficients.bit_length()-1
            if pivot not in rows:
                rows[pivot] = (coefficients, rhs, certificate)
                break
            old, old_rhs, old_certificate = rows[pivot]
            coefficients ^= old
            rhs ^= old_rhs
            certificate ^= old_certificate
        if not coefficients and rhs:
            contradiction = certificate
            break
    report['joint_rank'] = len(basis)
    report['target_e_word'] = wanted
    if contradiction is not None:
        # Validate the certificate directly against original vectors, using no
        # Gaussian elimination. Prefix construction still needs exactness gates.
        parity = (base_e & contradiction).bit_count() & 1
        if (wanted & contradiction).bit_count() & 1 == parity or any(
            ((((v >> 128) & MASK) & contradiction).bit_count() & 1) != parity for v in vectors):
            raise AssertionError('Independent parity-separator verification failed')
        return {**report, 'status': 'UNSAT', 'separator_mask': contradiction,
                'family_parity': parity, 'separator_independently_verified': True,
                'total_seconds': perf_counter()-started}
    assignment = 0
    for pivot in sorted(rows):
        coefficients, rhs, _ = rows[pivot]
        assignment |= (rhs ^ ((coefficients & assignment).bit_count() & 1)) << pivot
    witness = base
    for j, vector in enumerate(basis):
        if assignment & (1 << j):
            witness ^= vector
    if (witness >> 128) & MASK != wanted:
        raise AssertionError('Affine membership witness failed')
    return {**report, 'status': 'SAT', 'e_projection_rank': len(rows),
            'actual_family_boundary': witness in set(vectors),
            'is_verified_full_target_solution': False,
            'witness_sha256': sha256(witness.to_bytes(64, 'little')).hexdigest(),
            'total_seconds': perf_counter()-started}


@dataclass(frozen=True)
class KnownWord:
    """Sound 32-bit cube. Unknown bits are independent, never presumed zero."""
    value: int
    known: int = MASK

    def __post_init__(self):
        object.__setattr__(self, 'known', self.known & MASK)
        object.__setattr__(self, 'value', self.value & self.known & MASK)

    def __xor__(self, other):
        return KnownWord(self.value ^ other.value, self.known & other.known)

    def __and__(self, other):
        zero = (self.known & ~self.value) | (other.known & ~other.value)
        one = self.value & other.value
        return KnownWord(one, zero | one)

    def __invert__(self):
        return KnownWord(~self.value, self.known)

    def rotate(self, n):
        return KnownWord(rotr(self.value, n), rotr(self.known, n))

    def shift(self, n):
        return KnownWord(self.value >> n, (self.known >> n) | (MASK << (32-n)))

    def contains(self, value):
        return value & self.known == self.value


def cube_sum(*words):
    """Bit-local carry reachable sets; forgetting correlations only adds values."""
    value = known = 0
    carries = {0}
    for bit in range(32):
        totals = carries
        for word in words:
            choices = {(word.value >> bit) & 1} if word.known & (1 << bit) else {0, 1}
            totals = {a+b for a in totals for b in choices}
        outputs = {x & 1 for x in totals}
        if len(outputs) == 1:
            known |= 1 << bit
            value |= next(iter(outputs)) << bit
        carries = {x >> 1 for x in totals}
    return KnownWord(value, known)


def cube_compress(initial, block, cuts=()):
    w = list(block)
    for t in range(16, 64):
        x, y = w[t-15], w[t-2]
        w.append(cube_sum(w[t-16], x.rotate(7)^x.rotate(18)^x.shift(3),
                          w[t-7], y.rotate(17)^y.rotate(19)^y.shift(10)))
    s = tuple(initial)
    trace = {}
    first_free = None
    for t in range(64):
        a, b, c, d, e, f, g, h = s
        t1 = cube_sum(h, e.rotate(6)^e.rotate(11)^e.rotate(25),
                      (e & f)^((~e) & g), KnownWord(K[t]), w[t])
        t2 = cube_sum(a.rotate(2)^a.rotate(13)^a.rotate(22),
                      (a & b)^(a & c)^(b & c))
        s = (cube_sum(t1, t2), a, b, c, cube_sum(d, t1), e, f, g)
        if first_free is None and not any(x.known for x in s):
            first_free = t
        if t in cuts:
            trace[t] = s
    return tuple(cube_sum(x, y) for x, y in zip(initial, s)), trace, first_free


def abstract_family(family, cuts=(31, 47, 55, 59, 60)):
    """O(width+rounds) necessary cubes, without enumerating 2**width headers.

    Only direct XOR header dimensions are accepted. Derived Merkle/extranonce
    transformations cannot be safely bounded from singleton flips this way.
    """
    if any(d.kind.value not in ('nonce', 'version', 'ntime') for d in family.dimensions):
        raise ValueError('Cube construction requires direct XOR header dimensions')
    begun = perf_counter()
    base = family.candidate(0).serialize()
    varied = bytearray(80)
    for bit in range(family.width):
        changed = family.candidate(1 << bit).serialize()
        for i, (x, y) in enumerate(zip(base, changed)):
            varied[i] |= x ^ y
    padded = base+b'\x80'+bytes(39)+pack('>Q', 640)
    masks = bytes(varied)+bytes(48)
    state = tuple(KnownWord(x) for x in IV)
    free = []
    for offset in (0, 64):
        block = tuple(KnownWord(v, ~m) for v, m in zip(
            unpack('>16I', padded[offset:offset+64]), unpack('>16I', masks[offset:offset+64])))
        state, _, first_free = cube_compress(state, block)
        free.append(first_free)
    first = state
    _, trace, first_free = cube_compress(tuple(KnownWord(x) for x in IV),
        first+(KnownWord(0x80000000),)+(KnownWord(0),)*6+(KnownWord(256),), cuts)
    return {'first': first, 'cuts': trace, 'first_free_rounds': free+[first_free],
            'seconds': perf_counter()-begun, 'headers_constructed': family.width+1}


def free_cut_witness(first_digest, cut, desired_high=0):
    """Construct a SAT witness for an unconstrained cut, with real schedule.

    This is NOT an actual header preimage: the cut-to-header relation has been
    relaxed. The witness demonstrates why that relaxation cannot reject work.
    """
    if not 0 <= cut <= 60 or len(first_digest) != 8 or not 0 <= desired_high <= MASK:
        raise ValueError('Invalid cut witness request')
    w = schedule(tuple(first_digest)+(0x80000000,)+(0,)*6+(256,))
    final_h = (int.from_bytes(desired_high.to_bytes(4, 'little'), 'big')-IV[7]) & MASK
    final = (0,)*7+(final_h,)
    s = final
    for t in range(63, cut, -1):
        s = inverse_step(s, w[t], t)
    boundary = s
    for t in range(cut+1, 64):
        s = step(s, w[t], t)
    if s != final:
        raise AssertionError('Inverse-round certificate failed forward replay')
    return boundary


def signed_add(solver, words, reference, name):
    """Exact modular add expressed as a signed delta from a concrete reference.

    sum(x)-sum(b) = (y-y_b) + 2**32 * (carry-carry_b).
    Widening to 35 bits and bounding carry prevents modular aliases for <=5
    uint32 operands. The base constants cancel, leaving exact integer addition.
    """
    import z3
    if not 1 <= len(words) <= 5 or len(reference) != len(words):
        raise ValueError('Signed cone supports one through five operands')
    if any(not 0 <= x <= MASK for x in reference):
        raise ValueError('Reference operands must be uint32')
    total = sum(reference)
    result = z3.BitVec(name, 32)
    carry = z3.BitVec(name+'_carry', 3)
    solver.add(z3.ULE(carry, len(words)-1))
    left = sum(z3.ZeroExt(3, x) for x in words)-total
    right = z3.ZeroExt(3, result)-(total & MASK)+((z3.ZeroExt(32, carry)-(total >> 32)) << 32)
    solver.add(left == right)
    return result


def boundary_query(vectors, cut, target, mode='affine', encoding='signed-carry',
                   timeout_ms=300, rank_budget=64):
    """A bounded suffix cone, with the entire exact second-SHA schedule.

    Word-cube mode drops cross-word correlation; affine mode retains its joint
    GF(2) hull. SAT is only feasibility in this superset. This function NEVER
    authorizes pruning: independent checks of the actual family are separate.
    """
    if not 0 <= cut <= 60 or not 0 < target < 1 << 256 or not 1 <= timeout_ms <= 5000:
        raise ValueError('Invalid suffix query')
    if mode not in ('affine', 'cube') or encoding not in ('signed-carry', 'bitvector'):
        raise ValueError('Unknown projection or encoding')
    vectors = tuple(vectors)
    if not vectors or len(vectors) > 4096 or any(not 0 <= v < 1 << 512 for v in vectors):
        raise ValueError('Invalid bounded boundary vectors')
    start = perf_counter()
    base, basis = affine_basis(vectors)
    report = {'cut': cut, 'mode': mode, 'encoding': encoding, 'K': len(vectors),
              'joint_rank': len(basis), 'affine_superset_log2_size': len(basis),
              'pruning_authorized': False, 'retained': len(vectors), 'pruned': 0}
    if mode == 'affine' and len(basis) > rank_budget:
        return {**report, 'status': 'UNKNOWN', 'reason': 'joint_rank_budget',
                'total_seconds': perf_counter()-start}
    try:
        import z3
    except ImportError:
        return {**report, 'status': 'UNKNOWN', 'reason': 'solver_unavailable',
                'total_seconds': perf_counter()-start}
    solver = z3.Solver()
    solver.set(timeout=timeout_ms, rlimit=300000)
    cv = lambda x: z3.BitVecVal(x, 32)
    if mode == 'affine':
        coefficients = [z3.Bool('alpha_'+str(i)) for i in range(len(basis))]
        words = [cv(x) for x in unpack_words(base)]
        for coefficient, vector in zip(coefficients, basis):
            for j, word in enumerate(unpack_words(vector)):
                if word:
                    words[j] = words[j] ^ z3.If(coefficient, cv(word), cv(0))
    else:
        variable = 0
        for vector in vectors:
            variable |= vector ^ base
        words = [z3.BitVec('boundary_'+str(i), 32) for i in range(16)]
        for j, word in enumerate(words):
            known = (~(variable >> (j*32))) & MASK
            solver.add((word & known) == ((base >> (j*32)) & known))
    serial = 0
    def add(operands):
        nonlocal serial
        serial += 1
        if encoding == 'bitvector':
            return sum(operands)
        # Zero is an admissible reference, not an approximation to operands.
        return signed_add(solver, operands, [0]*len(operands), 'add_'+str(serial))
    w = words[8:]+[cv(0x80000000)]+[cv(0)]*6+[cv(256)]
    for t in range(16, 61):
        x, y = w[t-15], w[t-2]
        w.append(add([w[t-16], z3.RotateRight(x, 7)^z3.RotateRight(x, 18)^z3.LShR(x, 3),
                      w[t-7], z3.RotateRight(y, 17)^z3.RotateRight(y, 19)^z3.LShR(y, 10)]))
    s = words[:8]
    for t in range(cut+1, 61):
        a, b, c, d, e, f, g, h = s
        t1 = add([h, z3.RotateRight(e, 6)^z3.RotateRight(e, 11)^z3.RotateRight(e, 25),
                  (e & f)^((~e) & g), cv(K[t]), w[t]])
        t2 = add([z3.RotateRight(a, 2)^z3.RotateRight(a, 13)^z3.RotateRight(a, 22),
                  (a & b)^(a & c)^(b & c)])
        s = [add([t1, t2]), a, b, c, add([d, t1]), e, f, g]
    h7 = add([s[4], cv(IV[7])])
    high = z3.Concat(*[z3.Extract(i+7, i, h7) for i in (0, 8, 16, 24)])
    solver.add(z3.ULE(high, target >> 224))
    construction = perf_counter()-start
    query_start = perf_counter()
    answer = solver.check()
    query_time = perf_counter()-query_start
    witness = None
    if answer == z3.sat:
        model = solver.model()
        values = tuple(model.eval(w, model_completion=True).as_long() for w in words)
        concrete = values[:8]
        full_w = schedule(values[8:]+(0x80000000,)+(0,)*6+(256,))
        for t in range(cut+1, 61):
            concrete = step(concrete, full_w[t], t)
        actual_high = int.from_bytes(((concrete[4]+IV[7]) & MASK).to_bytes(4, 'big'), 'little')
        if actual_high > target >> 224:
            raise AssertionError('SAT witness does not satisfy the integer suffix')
        packed = pack_words(values)
        if mode == 'affine' and not affine_contains(packed, base, basis):
            raise AssertionError('SAT witness outside the necessary affine hull')
        witness = {'high_word': actual_high, 'actual_family_boundary': packed in set(vectors),
                   'is_verified_full_target_solution': False}
    return {**report, 'status': str(answer).upper(), 'solver': z3.get_version_string(),
            'construction_seconds': construction, 'query_seconds': query_time,
            'total_seconds': perf_counter()-start, 'addition_cones': serial,
            'reason': solver.reason_unknown() if answer == z3.unknown else None,
            'witness': witness, 'prefix_constraint_only': True}


def audit_prefix_unsat(headers, target):
    """Independent exhaustive reproduction; its full-hash cost MUST be charged."""
    begun = perf_counter()
    for raw in headers:
        digest = sha256(sha256(raw).digest()).digest()
        if int.from_bytes(digest[-4:], 'little') <= target >> 224:
            raise AssertionError('UNSAT contradicts independent target-prefix evaluation')
    return {'independent_cases': len(headers), 'audit_seconds': perf_counter()-begun,
            'certificate': 'exhaustive hashlib SHA256d necessary-prefix reproduction',
            'all_costs_include_full_hash_audit': True}
