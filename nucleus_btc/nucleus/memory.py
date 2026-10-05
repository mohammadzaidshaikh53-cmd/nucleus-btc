"""SQLite knowledge store with bounded records; raw traces do not accumulate."""
import json
import sqlite3
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

CLASSES=("PROVEN","DEAD","FRONTIER")

class KnowledgeStore:
    def __init__(self,path="results/knowledge.sqlite",max_records=128):
        if max_records<3:raise ValueError("Need capacity for all three classes")
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.max_records=max_records;self.db=sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA max_page_count=8192") # 32 MiB with SQLite's default 4096-byte pages.
        self.db.execute("PRAGMA wal_autocheckpoint=64")
        self.db.execute("PRAGMA journal_size_limit=262144")
        self.db.execute("CREATE TABLE IF NOT EXISTS knowledge (id TEXT PRIMARY KEY, class TEXT NOT NULL, created TEXT NOT NULL, utility REAL NOT NULL, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.commit()
    def put(self,kind,config,metrics,reason,utility=0.):
        if kind not in CLASSES:raise ValueError("Unknown knowledge class")
        key=sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        payload=json.dumps({"config":config,"metrics":metrics,"reason":reason},sort_keys=True,allow_nan=False)
        if len(payload.encode())>65536:raise ValueError("Record too large; distill measurements first")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO knowledge VALUES (?,?,?,?,?)",(key,kind,datetime.now(timezone.utc).isoformat(),utility,payload))
        self.consolidate()
        return key
    def consolidate(self):
        # Each class has a bounded budget; current champion is protected.
        champion=self.get_state("champion",{}).get("record_id","")
        budget=max(1,self.max_records//3)
        with self.db:
            for kind in CLASSES:
                records=self.db.execute("SELECT id FROM knowledge WHERE class=? ORDER BY utility DESC,created DESC",(kind,)).fetchall()
                champion_in_class=any(r[0]==champion for r in records)
                keep={champion} if champion_in_class else set()
                if kind=="FRONTIER":
                    diverse={}
                    for (key,) in records:
                        row=self.db.execute("SELECT payload FROM knowledge WHERE id=?",(key,)).fetchone()
                        species=json.loads(row[0])["config"].get("species")
                        if species and species not in diverse:diverse[species]=key
                    for key in list(diverse.values())[:max(0,budget-len(keep))]:keep.add(key)
                for (key,) in records:
                    if len(keep)>=budget:break
                    keep.add(key)
                for (key,) in records:
                    if key not in keep:self.db.execute("DELETE FROM knowledge WHERE id=?",(key,))
    def set_state(self,key,value):
        if not self.db.execute("SELECT 1 FROM state WHERE key=?",(key,)).fetchone() and self.db.execute("SELECT COUNT(*) FROM state").fetchone()[0]>=64:raise ValueError("State key budget exceeded")
        encoded=json.dumps(value,allow_nan=False,sort_keys=True)
        if len(encoded)>65536:raise ValueError("State value too large")
        with self.db:self.db.execute("INSERT OR REPLACE INTO state VALUES (?,?)",(key,encoded))
    def get_state(self,key,default=None):
        row=self.db.execute("SELECT value FROM state WHERE key=?",(key,)).fetchone()
        return json.loads(row[0]) if row else default
    def promote(self,config,metrics,expected_config,experiment_id=None):
        """Atomically protect a verified record and switch champion, with CAS guard."""
        key=sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        payload=json.dumps({"config":config,"metrics":metrics,"reason":"Exact holdout and confidence-qualified generated improvement"},sort_keys=True,allow_nan=False)
        if len(payload.encode())>65536:raise ValueError("Promotion record too large")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current=self.get_state("champion",{}).get("config",expected_config)
            if current!=expected_config:raise RuntimeError("Champion changed during experiment; no promotion")
            self.db.execute("INSERT OR REPLACE INTO knowledge VALUES (?,?,?,?,?)",(key,"PROVEN",datetime.now(timezone.utc).isoformat(),metrics["geometric_speedup"],payload))
            value=json.dumps({"config":config,"record_id":key,"scope":"exact throughput champion; energy and live acceptance unmeasured"},sort_keys=True)
            self.db.execute("INSERT OR REPLACE INTO state VALUES (?,?)",("champion",value))
            if experiment_id is not None:
                self.db.execute("INSERT OR REPLACE INTO state VALUES (?,?)",("promotion_receipt",json.dumps({"experiment_id":experiment_id,"record_id":key})))
            self.db.commit()
        except BaseException:self.db.rollback();raise
        self.consolidate();return key
    def set_states(self,values):
        existing={r[0] for r in self.db.execute("SELECT key FROM state")}
        if len(existing|set(values))>64:raise ValueError("State key budget exceeded")
        encoded={k:json.dumps(v,allow_nan=False,sort_keys=True) for k,v in values.items()}
        if any(len(v.encode())>65536 for v in encoded.values()):raise ValueError("Checkpoint too large")
        with self.db:
            self.db.executemany("INSERT OR REPLACE INTO state VALUES (?,?)",encoded.items())
    def records(self):
        return [{"id":key,"class":kind,"created":created,"utility":utility,**json.loads(payload)} for key,kind,created,utility,payload in self.db.execute("SELECT * FROM knowledge ORDER BY created")]
    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
