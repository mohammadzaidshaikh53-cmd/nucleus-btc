"""Append-only, bounded target-directed research; never promotes a miner."""
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from struct import pack, unpack
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nucleus_btc.benchmark import heldout_headers, metadata
from nucleus_btc.bitcoin.block_header import BlockHeader
from nucleus_btc.family_ir import Dimension, DimensionKind as D, HeaderFamily
from nucleus_btc.family_ir.middle_cut import (
    IV, MASK, abstract_family, affine_basis, audit_prefix_unsat, boundary_query,
    free_cut_witness, pack_words, schedule, step, trace_family,
)
from nucleus_btc.gpu.backend import get_backend


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)


def run(output, seeds, powers, timeout_ms):
    cuts = (31, 47, 55, 59, 60)
    sources = ('nucleus_btc/family_ir/middle_cut.py', 'scripts/middle_cut.py')
    report = {'schema': 1, 'objective': '20-30 TH/s equivalent exact valid Bitcoin work',
              'git_parent': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
              'seeds': seeds, 'powers': powers, 'cuts_after_second_sha_round_index': cuts,
              'timeout_ms_per_query': timeout_ms, 'target': '1',
              'work_source': 'synthetic serialized header fixtures, no live pool shares',
              'rows': [], 'abstract_rows': [], 'queries': [],
              'production_champion_changed': False, 'target_achieved': False}
    started = perf_counter()
    with get_backend('opencl', full_unroll=True, alt_boolean=True, local_size=64) as engine:
        report['metadata'] = metadata(engine)
        for seed in seeds:
            header = BlockHeader.parse(heldout_headers(seed, 1)[0]).with_nonce(0)
            # Large conceptual families cost width+1 header constructions here.
            for width in (8, 16, 24):
                family = HeaderFamily(header, (Dimension(D.NONCE32, tuple(range(width)), MASK),))
                abstract = abstract_family(family, cuts)
                first = unpack('>8I', hashlib.sha256(header.serialize()).digest())
                witnesses = []
                for cut in cuts:
                    if not any(x.known for x in abstract['cuts'][cut]):
                        boundary = free_cut_witness(first, cut)
                        if not all(x.contains(v) for x, v in zip(abstract['first'], first)):
                            raise AssertionError('Schedule witness outside digest abstraction')
                        witnesses.append({'cut': cut, 'all_state_words_free': True,
                                          'schedule_from_actual_first_digest': True,
                                          'inverse_witness_verified': True,
                                          'boundary_sha256': hashlib.sha256(pack('>8I', *boundary)).hexdigest(),
                                          'status': 'SAT_RELAXATION', 'pruned': 0})
                report['abstract_rows'].append({'seed': seed, 'width': width, 'K': family.count,
                    'first_free_rounds': abstract['first_free_rounds'], 'seconds': abstract['seconds'],
                    'headers_constructed': abstract['headers_constructed'],
                    'known_digest_bits': sum(x.known.bit_count() for x in abstract['first']),
                    'witnesses': witnesses})
            for power in powers:
                family = HeaderFamily(header, (Dimension(D.NONCE32, tuple(range(power)), MASK),))
                headers, traces, timing = trace_family(family, cuts)
                # Check cut/schedule semantics against a separate full SHA implementation.
                audit_start = perf_counter()
                for raw, traces_for_header in zip(headers, traces):
                    value = traces_for_header[60]
                    if pack('>8I', *value[8:]) != hashlib.sha256(raw).digest():
                        raise AssertionError('First digest trace mismatch')
                    w = schedule(value[8:]+(0x80000000,)+(0,)*6+(256,))
                    s = value[:8]
                    for t in range(61, 64):
                        s = step(s, w[t], t)
                    digest = pack('>8I', *((x+y)&MASK for x, y in zip(s, IV)))
                    if digest != hashlib.sha256(hashlib.sha256(raw).digest()).digest():
                        raise AssertionError('Full SHA256d cut audit mismatch')
                parity_seconds = perf_counter()-audit_start
                raw = header.serialize()
                engine.scan(raw, 0, family.count, 1)
                baseline = []
                for _ in range(5):
                    before = perf_counter()
                    engine.scan(raw, 0, family.count, 1)
                    baseline.append(perf_counter()-before)
                ordinary = median(baseline)
                for cut in cuts:
                    before = perf_counter()
                    vectors = [pack_words(t[cut]) for t in traces]
                    base, basis = affine_basis(vectors)
                    hull_seconds = perf_counter()-before
                    projected = [((v >> (4*32)) & MASK) for v in vectors]
                    _, e_basis = affine_basis(projected)
                    row = {'seed': seed, 'K': family.count, 'cut': cut, 'joint_rank': len(basis),
                           'joint_dimension': 512, 'e_word_rank': len(e_basis),
                           'affine_extra_log2_candidates': len(basis)-power,
                           'unique_boundaries': len(set(vectors)),
                           'prefix_to_round60_seconds': timing['total_seconds'],
                           'prefix_cost_scope': 'shared fixture preparation through cut 60 for all five probes; not separately timed per cut',
                           'hull_seconds': hull_seconds, 'parity_audit_seconds': parity_seconds,
                           'ordinary_gpu_seconds': ordinary, 'ordinary_gpu_samples': baseline,
                           'GPU_cost_scope': 'same finite contiguous family; includes launch, not sustained H/s',
                           'complete_joint_hull_is_universal': len(basis) == 512}
                    report['rows'].append(row)
                    # Bounded small-family solver experiments; large-K branch tests rank collapse.
                    if power in (2, 4, 6) and cut in (47, 59, 60):
                        for mode, encoding in (('cube', 'signed-carry'), ('affine', 'signed-carry'), ('affine', 'bitvector')):
                            result = boundary_query(vectors, cut, 1, mode, encoding, timeout_ms, rank_budget=64)
                            result.update(seed=seed)
                            proof_audit = 0.
                            if result['status'] == 'UNSAT':
                                verification = audit_prefix_unsat(headers, 1)
                                result['independent_verification'] = verification
                                proof_audit = verification['audit_seconds']
                                result['research_family_rejection_verified'] = True
                            cost = timing['total_seconds']+hull_seconds+result['total_seconds']+proof_audit
                            rho = 1. if result['status'] == 'UNSAT' else 0.
                            result['candidate_pipeline_seconds'] = cost+(1-rho)*ordinary
                            result['F_analysis'] = cost/ordinary
                            result['rho_verified'] = rho
                            result['effective_speedup'] = ordinary/result['candidate_pipeline_seconds']
                            result['useful_rho'] = rho if result['effective_speedup'] > 1 else 0.
                            result['cost_scope'] = 'prefix to round60 shared by lab; exact per-cut cost is a separate follow-up if rank and proof warrant it; independent rejection audit included'
                            report['queries'].append(result)
                print(json.dumps({'seed': seed, 'K': family.count, 'joint_ranks': [r['joint_rank'] for r in report['rows'][-len(cuts):]],
                                  'queries': len(report['queries'])}), flush=True)
    report['elapsed_seconds'] = perf_counter()-started
    report['query_status_counts'] = dict(Counter(q['status'] for q in report['queries']))
    report['best_effective_speedup'] = max((q['effective_speedup'] for q in report['queries']), default=0.)
    report['useful_rho'] = max((q['useful_rho'] for q in report['queries']), default=0.)
    report['status'] = 'NO LARGE ADVANTAGE FOUND'
    report['next_distinct_hypothesis'] = 'Nonlinear cross-word boundary invariants constructed without enumerating the family; require a falsifiable relation and independent proof before implementation.'
    save(output, report)
    print(json.dumps({'output': str(output), 'status': report['status'], 'query_status_counts': report['query_status_counts'],
                      'best_effective_speedup': report['best_effective_speedup']}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--seeds', type=int, nargs='+', default=[202610051, 202610052, 202610053])
    p.add_argument('--powers', type=int, nargs='+', default=[2, 4, 6, 8, 10])
    p.add_argument('--timeout-ms', type=int, default=300)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError('Historical evidence cannot be overwritten')
    if not 1 <= len(args.seeds) <= 3 or any(not 1 <= x <= 10 for x in args.powers) or not 1 <= len(args.powers) <= 5:
        raise ValueError('Bounded runner allows <=3 seeds and <=5 powers from 1..10')
    if not 1 <= args.timeout_ms <= 1000:
        raise ValueError('Bounded solver budget is 1..1000 milliseconds')
    run(args.output, args.seeds, args.powers, args.timeout_ms)
