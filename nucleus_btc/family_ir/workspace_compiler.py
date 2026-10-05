"""Cost-directed hierarchy over existing permitted workspaces; no nonce luck."""
from dataclasses import dataclass
from .symbolic import SymbolicFamily
from ..protocol.sv2_family import channel_family


@dataclass(frozen=True)
class WorkspacePlan:
    workspace: SymbolicFamily
    outer: tuple
    inner: tuple
    permissions: str

    def report(self):
        return {'scope': self.workspace.fingerprint, **self.workspace.cost_record(),
                'outer': self.outer, 'inner': self.inner, 'permissions': self.permissions,
                'selection_basis': 'midstate/derived-Merkle invalidation and reasoning cost; no probability prediction',
                'production_pruning_allowed': False}


def compile_family(family):
    if any(d.kind.value in ('custom', 'merkle_tail') for d in family.dimensions):
        raise ValueError('Compiler does not invent transaction or arbitrary Merkle workspaces')
    outer = tuple(i for i, (kind, _) in enumerate(family.variables) if kind in ('version', 'extranonce'))
    inner = tuple(i for i in range(family.width) if i not in outer)
    return WorkspacePlan(SymbolicFamily(family), outer, inner, 'explicit local fixture; no live permission assertion')


def compile_channel(client, **bounds):
    # The established protocol adapter checks rolling flags, VERSION_MASK,
    # nTime range and Extended extranonce allocation. No wire writes occur.
    from dataclasses import replace
    return replace(compile_family(channel_family(client, **bounds)), permissions='actual negotiated channel constraints')
