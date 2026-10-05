"""Bounded Phase-II runner. Outputs are append-only evidence, never promotions."""
import argparse
import csv
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nucleus_btc.benchmark import heldout_headers
from nucleus_btc.bitcoin.block_header import BlockHeader
from nucleus_btc.family_ir import Dimension, DimensionKind as D, HeaderFamily

def fixture(bits,seed=710203,positions=None):
    h=BlockHeader.parse(heldout_headers(seed,1)[0]).with_nonce(0)
    positions=tuple(range(bits)) if positions is None else tuple(positions)
    return HeaderFamily(h,(Dimension(D.NONCE32,positions,0xffffffff),))

def save(path,result):
    path=Path(path)
    if path.exists(): raise FileExistsError("Historical result path already exists")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)

def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=('profile','scaling','probes','cones','gpu','supervisor'))
    p.add_argument('--output',required=True);p.add_argument('--bits',type=int,default=6)
    p.add_argument('--block',type=int,choices=(4,8,16),default=8);a=p.parse_args()
    if a.kind=='profile':
        from nucleus_btc.family_ir.profile import dependency_profile
        result=dependency_profile(fixture(a.bits),a.block)
        csv_path=Path(a.output).with_suffix('.csv')
        if csv_path.exists(): raise FileExistsError(csv_path)
        with csv_path.open('x',newline='',encoding='utf-8') as stream:
            fields=('round','word','K','unique','sharing_ratio','Nnodes','Nresidual','binary_affine_rank')
            writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(result['rows'])
    else:
        from nucleus_btc.family_ir.experiments import run
        result=run(a.kind)
    save(a.output,result)
    print(json.dumps({"output":a.output,"status":result.get('status','measured'),"rows":len(result.get('rows',[]))}))

if __name__=='__main__': main()
