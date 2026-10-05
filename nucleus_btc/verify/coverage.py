"""Independent structural coverage proof for a symbolic binary refinement tree."""
from ..family_ir.symbolic import SymbolicFamily
from .certificates import check_certificate


def check_coverage(tree, root, target, verify_rejections=True):
    if tree.get('workspace') != root.fingerprint or tree.get('target') != str(target):
        raise ValueError('Wrong refinement tree scope')
    nodes = tree['nodes']
    if not 1 <= len(nodes) <= 4095: raise ValueError('Refinement tree node budget')
    seen, leaves = set(), []
    def visit(ident, expected):
        if ident in seen or ident not in nodes: raise ValueError('Cycle/missing refinement node')
        seen.add(ident); node = nodes[ident]
        if tuple(map(tuple, node['fixed'])) != expected.fixed or node['scope'] != expected.fingerprint:
            raise ValueError('Refinement node has wrong fixed-variable scope')
        children = node.get('children', [])
        if children:
            variable = node['split_variable']
            if variable not in expected.free or len(children) != 2 or len(set(children)) != 2:
                raise ValueError('Split does not partition one legal parent variable')
            for value, child in enumerate(children):
                child_workspace = SymbolicFamily(expected.family, expected.fixed+((variable, value),))
                visit(child, child_workspace)
        else:
            if node['status'] not in ('PENDING', 'UNKNOWN', 'ALL_PASS', 'REJECTED', 'FALLBACK'):
                raise ValueError('Unclassified leaf would lose work')
            if node['status'] == 'REJECTED' and verify_rejections and not check_certificate(node['certificate'], expected, target)['valid']:
                raise ValueError('Rejected leaf lacks an independently valid certificate')
            leaves.append((expected, node['status']))
    visit('root', root)
    if len(seen) != len(nodes): raise ValueError('Unreachable nodes in refinement tree')
    if sum(w.count for w, _ in leaves) != root.count: raise ValueError('Gap in symbolic coverage')
    return {'valid': True, 'leaves': len(leaves), 'covered': root.count,
            'rejected': sum(w.count for w, s in leaves if s == 'REJECTED'),
            'retained': sum(w.count for w, s in leaves if s != 'REJECTED'),
            'proof': 'recursive legal fixed-bit binary partitions; no candidate enumeration'}
