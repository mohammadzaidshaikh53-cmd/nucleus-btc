"""Build locked SV2 reference transport; synthetic server is optional and separate."""
import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--cargo",default="cargo");parser.add_argument("--fixtures",action="store_true");args=parser.parse_args()
    manifest=str(ROOT/"native"/"sv2-noise"/"Cargo.toml")
    for command in ([args.cargo,"test","--locked","--manifest-path",manifest],[args.cargo,"build","--release","--locked","--manifest-path",manifest]):subprocess.run(command,cwd=ROOT,check=True)
    suffix=".exe" if os.name=="nt" else "";name="nucleus-sv2-noise"+suffix
    (ROOT/"build").mkdir(exist_ok=True);shutil.copy2(ROOT/"native"/"sv2-noise"/"target"/"release"/name,ROOT/"build"/name)
    if args.fixtures:subprocess.run([args.cargo,"build","--locked","--features","fixtures","--target-dir",str(ROOT/"build"/"sv2-fixture"),"--manifest-path",manifest],cwd=ROOT,check=True)
if __name__=="__main__":main()
