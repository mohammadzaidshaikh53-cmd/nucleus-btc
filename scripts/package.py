"""Create a portable source/results archive; retain only useful native build outputs."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import json

ROOT=Path(__file__).resolve().parents[1]

def include(path):
    rel=path.relative_to(ROOT)
    if any(p in ("__pycache__",".git",".venv") or p.endswith(".egg-info") for p in rel.parts):return False
    if path.suffix in (".pyc",".pyo") or path.name.endswith(("-wal","-shm")):return False
    if rel.parts[0]=="build":return path.name in ("nucleus_core.dll","nucleus-native.exe","libnucleus_core.so")
    if rel==Path("config/local.json"):return False # Explicit local credentials never enter the archive.
    return True

def main():
    output=ROOT.parent/"Nucleus-BTC.zip"
    files=sorted(p for p in ROOT.rglob("*") if p.is_file() and include(p))
    with ZipFile(output,"w",compression=ZIP_DEFLATED) as archive:
        for path in files:archive.write(path,Path(ROOT.name)/path.relative_to(ROOT))
    with ZipFile(output) as archive:
        bad=archive.testzip()
        if bad:raise RuntimeError(f"Archive verification failed: {bad}")
        count=len(archive.namelist())
    manifest={"archive":output.name,"files":count,"bytes":output.stat().st_size,"sha256":sha256(output.read_bytes()).hexdigest(),"credentials_included":False}
    (ROOT.parent/"Nucleus-BTC-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2))

if __name__=="__main__":main()
