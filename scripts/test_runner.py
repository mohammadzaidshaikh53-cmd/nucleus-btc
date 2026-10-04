"""Run real unittest cases and persist a machine-readable verification record."""
import argparse
import json
import os
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--require-gpu",action="store_true")
    parser.add_argument("--require-native",action="store_true")
    parser.add_argument("--output",default=str(ROOT/"results"/"test-suite.json"))
    args=parser.parse_args()
    if args.require_gpu:os.environ["NUCLEUS_REQUIRE_OPENCL"]="1"
    if args.require_native:os.environ["NUCLEUS_REQUIRE_NATIVE"]="1"
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={"timestamp_utc":datetime.now(timezone.utc).isoformat(),"run":result.testsRun,
            "passed":result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
            "skipped":[{"test":test.id(),"reason":reason} for test,reason in result.skipped],
            "failures":[{"test":test.id(),"details":details} for test,details in result.failures],
            "errors":[{"test":test.id(),"details":details} for test,details in result.errors],"successful":result.wasSuccessful()}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return 0 if result.wasSuccessful() else 1

if __name__=="__main__":raise SystemExit(main())
