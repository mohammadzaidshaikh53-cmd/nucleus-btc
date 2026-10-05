"""Nonenumerating, canonical subspaces of the existing Bitcoin HeaderFamily."""
import json
from dataclasses import dataclass, field
from hashlib import sha256


class AccidentalEnumeration(RuntimeError):
    pass


@dataclass(frozen=True)
class SymbolicFamily:
    family: object
    fixed: tuple = ()
    audit_counts: dict = field(default_factory=lambda: {'headers': 0}, compare=False, repr=False)

    def __post_init__(self):
        fixed = tuple(sorted(self.fixed))
        if len(dict(fixed)) != len(fixed) or any(not 0 <= i < self.family.width or v not in (0, 1) for i, v in fixed):
            raise ValueError('Invalid fixed workspace variables')
        object.__setattr__(self, 'fixed', fixed)

    @property
    def free(self):
        fixed = dict(self.fixed)
        return tuple(i for i in range(self.family.width) if i not in fixed)

    @property
    def count(self):
        return 1 << len(self.free)

    def scope(self):
        f = self.family
        return {'schema': 1, 'header': f.header.serialize().hex(), 'fixed': self.fixed,
                'dimensions': [{'kind': d.kind.value, 'bits': d.bits, 'mask': d.permitted_mask,
                                'source': d.protocol_source, 'standard': d.standard_allowed,
                                'extended': d.extended_allowed} for d in f.dimensions],
                'min_time': f.min_time, 'max_time': f.max_time,
                'coinbase_prefix': f.coinbase_prefix.hex(), 'coinbase_suffix': f.coinbase_suffix.hex(),
                'extranonce': f.extranonce.hex(), 'merkle_branch': [x.hex() for x in f.merkle_branch]}

    @property
    def fingerprint(self):
        return sha256(json.dumps(self.scope(), sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def global_index(self, index):
        if not 0 <= index < self.count:
            raise ValueError('Assignment outside symbolic workspace')
        value = sum(v << i for i, v in self.fixed)
        for j, i in enumerate(self.free):
            value |= ((index >> j) & 1) << i
        return value

    def header(self, index):
        """Explicit one-header reconstruction, counted as audit/fallback work."""
        self.audit_counts['headers'] += 1
        return self.family.candidate(self.global_index(index)).serialize()

    def masks(self):
        result = {}
        for i in self.free:
            kind, bit = self.family.variables[i]
            result[kind] = result.get(kind, 0) | (1 << bit)
        return result

    def inputs(self, index):
        assignment = self.global_index(index)
        result = {}
        for i in self.free:
            kind, bit = self.family.variables[i]
            key = kind if kind != 'extranonce' else 'extranonce_'+str(bit//32)
            result[key] = result.get(key, 0) | (((assignment >> i) & 1) << (bit % 32))
        return result

    def construct(self):
        raise AccidentalEnumeration('SymbolicFamily cannot construct K-sized arrays; use bounded audit explicitly')

    def __iter__(self):
        raise AccidentalEnumeration('Implicit candidate iteration is forbidden')

    def audit_headers(self, limit=256):
        if self.count > limit:
            raise AccidentalEnumeration('Exhaustive audit exceeds its explicit finite scope')
        return [self.header(i) for i in range(self.count)]

    def split(self, variables):
        variables = tuple(variables)
        if not 1 <= len(variables) <= 3 or len(set(variables)) != len(variables) or any(v not in self.free for v in variables):
            raise ValueError('Split must fix one to three distinct legal free variables')
        return tuple(SymbolicFamily(self.family, self.fixed+tuple((v, (assignment >> j) & 1) for j, v in enumerate(variables)))
                     for assignment in range(1 << len(variables)))

    def cost_record(self):
        return {'conceptual_K': self.count, 'K_materialized': False,
                'scope_bytes': len(json.dumps(self.scope())), 'workspace_variables': len(self.free),
                'explicit_audit_or_fallback_headers': self.audit_counts['headers'],
                'storage_complexity': 'O(template bytes + workspace variables), independent of K'}
