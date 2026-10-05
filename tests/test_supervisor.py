import tempfile
import unittest
from pathlib import Path
from nucleus_btc.nucleus.supervisor import Supervisor
from nucleus_btc.nucleus.memory import KnowledgeStore
from nucleus_btc.nucleus.persistence import ProcessLock,atomic_json

class SupervisorTests(unittest.TestCase):
    def test_resume_and_compressed_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            attempts=[]
            def worker(experiment):
                attempts.append(experiment["id"])
                if len(attempts)<=2:raise OSError("transient compiler environment")
                return {"status":"exactness_passed"}
            report=Supervisor(directory,runner=worker).run(2)
            self.assertEqual(attempts[:3],[attempts[0]]*3)
            self.assertEqual(report["total_completed"],2)
            # JSON is an exported view; durable SQLite state is authoritative.
            Path(directory,"checkpoint.json").write_text("interrupted JSON")
            next_report=Supervisor(directory,runner=lambda _:{"status":"exactness_passed"}).run(1)
            self.assertEqual(next_report["total_completed"],3)
            self.assertLess(next_report["storage_bytes"],1<<20)
    def test_crash_intent_and_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            def crash(_):raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):Supervisor(directory,runner=crash).run(1)
            with KnowledgeStore(Path(directory)/"state.sqlite") as store:
                pending=store.get_state("supervisor")["pending"];self.assertEqual(pending["attempts"],1)
            seen=[]
            def recover(experiment):seen.append(experiment);return {"status":"exactness_passed"}
            Supervisor(directory,runner=recover).run(1)
            self.assertEqual(seen[0]["id"],pending["id"]);self.assertEqual(seen[0]["attempts"],2)
    def test_correctness_failure_not_retried_and_next_species_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def worker(experiment):
                calls.append(experiment["kind"])
                if len(calls)==1:raise AssertionError("bit mismatch")
                return {"status":"exactness_passed"}
            report=Supervisor(directory,runner=worker).run(2)
            self.assertNotEqual(calls[0],calls[1]);self.assertEqual(report["history"][0]["attempts"],1)
    def test_exclusive_writer_and_atomic_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"owner.lock"
            with ProcessLock(path):
                with self.assertRaises(RuntimeError):
                    with ProcessLock(path):pass
            with ProcessLock(path):pass
            target=Path(directory)/"state.json";atomic_json(target,{"x":1})
            self.assertIn('"x": 1',target.read_text())
    def test_champion_compare_and_swap(self):
        with tempfile.TemporaryDirectory() as directory,KnowledgeStore(Path(directory)/"store.sqlite") as store:
            store.set_state("champion",{"config":{"version":1}})
            with self.assertRaises(RuntimeError):store.promote({"version":2},{"geometric_speedup":2.},{"version":0})
            self.assertEqual(store.get_state("champion")["config"],{"version":1})
    def test_unverified_proposal_rejected_without_halting(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Supervisor(directory,runner=lambda _:{"status":"promotion_qualified"}).run(2)
            self.assertEqual(report["total_completed"],2)
            self.assertFalse(report["production_champion_modified"])
            self.assertTrue(all(r["status"]=="failed" for r in report["history"]))
