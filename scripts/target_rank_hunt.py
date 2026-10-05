"""Search valid header dimensions for a full-SHA target-word parity invariant.

Changed mechanism after the generic boundary hull saturates: vary the family
alignment, and score its exact final target-word projection, not reduced-round
activity or timing noise. Construction and hunt costs are explicit.
"""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nucleus_btc.benchmark import heldout_headers
from nucleus_btc.bitcoin.block_header import BlockHeader
from nucleus_btc.family_ir import Dimension, DimensionKind as D, HeaderFamily
from nucleus_btc.family_ir.middle_cut import (
    MASK, IV, affine_basis, affine_target_cut, pack_words, trace_family,
)


def specifications():
    nonce_sets = {tuple(range(start, start+6)) for start in range(27)}
    nonce_sets |= {tuple(range(offset, 32, 5))[:6] for offset in range(5)}
    rng = random.Random(202610054)
    nonce_sets |= {tuple(sorted(rng.sample(range(32), 6))) for _ in range(16)}
    specs = [('nonce', (Dimension(D.NONCE32, bits, MASK),)) for bits in sorted(nonce_sets) if len(bits) == 6]
    for first in (5, 13, 21, 27):
        for bits in ((0, 1, 2, 3), (5, 11, 17, 31)):
            specs.append(('nonce-version', (Dimension(D.NONCE32, bits, MASK),
                Dimension(D.VERSION_ROLL_BITS, (first, first+1), 0x1fffffe0,
                          'diagnostic within SV2 version mask; no live job permission asserted'))))
    return specs


def run(seeds):
    begun = perf_counter()
    rows = []
    for seed in seeds:
        header = BlockHeader.parse(heldout_headers(seed, 1)[0]).with_nonce(0)
        for name, dimensions in specifications():
            started = perf_counter()
            family = HeaderFamily(header, dimensions)
            headers, traces, timing = trace_family(family, (60,))
            vectors = [pack_words(trace[60]) for trace in traces]
            values = [trace[60][4] for trace in traces]
            _, basis = affine_basis(values)
            result = affine_target_cut(vectors, 1)
            audit_started = perf_counter()
            for raw, value in zip(headers, values):
                digest = hashlib.sha256(hashlib.sha256(raw).digest()).digest()
                high = int.from_bytes(((value+IV[7]) & MASK).to_bytes(4, 'big'), 'little')
                if high != int.from_bytes(digest[-4:], 'little'):
                    raise AssertionError('Target-word projection mismatches independent full SHA256d')
                if result['status'] == 'UNSAT' and high == 0:
                    raise AssertionError('False target-prefix rejection')
            audit = perf_counter()-audit_started
            rows.append({'seed': seed, 'family_kind': name, 'variables': family.variables,
                         'K': family.count, 'e_projection_rank': len(basis),
                         'status': result['status'], 'prefix_construction': timing,
                         'proof_seconds': result['total_seconds'], 'audit_seconds': audit,
                         'total_seconds': perf_counter()-started,
                         'verified_prefix_rejection': result['status'] == 'UNSAT',
                         'full_sha256d_prefix_audited': len(headers)})
        print(json.dumps({'seed': seed, 'completed_families': len(rows),
                          'minimum_rank': min(r['e_projection_rank'] for r in rows)}), flush=True)
    found = [r for r in rows if r['e_projection_rank'] < 32]
    elapsed = perf_counter()-begun
    return {'schema': 1, 'status': 'STRUCTURAL CANDIDATE NEEDS COST PROOF' if found else 'DEAD',
            'mechanism': 'full target-word affine parity after nonce/version subspace alignment',
            'hypothesis': 'chosen header-variable subspaces preserve a useful full-SHA target-word affine constraint at K=64',
            'seeds': seeds, 'rows': rows, 'family_count': len(rows), 'subspaces_per_fixture': len(specifications()),
            'nonuniversal_projection_count': len(found), 'hunt_seconds': elapsed,
            'P_find_nonuniversal_projection': len(found)/len(rows),
            'certified_saved_work_seconds': 0., 'net_benefit_seconds': -elapsed,
            'certified_mining_speedup': False, 'pruning_authorized': False,
            'actual_live_pool_job': False, 'target_achieved': False,
            'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                              ('nucleus_btc/family_ir/middle_cut.py', 'scripts/target_rank_hunt.py')},
            'failure_cause': 'all tested target-word projections span 32 bits' if not found else 'no cheaper nonenumerating construction proved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Historical evidence cannot be overwritten')
    result = run((202610055, 202610056, 202610057))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'source_sha256')}), flush=True)
