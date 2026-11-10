from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


TASKS = Path(__file__).resolve().parents[1] / "tasks"
sys.path.insert(0, str(TASKS))
task = importlib.import_module("maxcut")
runtime = importlib.import_module("maxcut_runtime")

POSITIVE = b"3 3\n1 2 2\n2 3 3\n1 3 5\n"
SIGNED = b"3 3\n1 2 1\n2 3 1\n1 3 -1\n"


def fixture(root: Path, stage: str = "development") -> Path:
    root.mkdir()
    (root / "graphs").mkdir()
    graphs = []
    for name, raw in [("positive", POSITIVE), ("signed", SIGNED)]:
        if stage == "confirmation":
            name = "confirmation-" + name
            raw = raw.replace(b"1 2 2", b"1 2 4").replace(b"1 2 1", b"1 2 3")
        path = root / "graphs" / (name + ".txt")
        path.write_bytes(raw)
        graphs.append({"id": name, "file": str(path.relative_to(root)),
                       "sha256": hashlib.sha256(raw).hexdigest()})
    (root / "protocol.json").write_text(json.dumps({"schema_version": 1, "task_id": runtime.TASK_ID,
                                                    "stage": stage, "graphs": graphs}))
    return root


class MaxCutTests(unittest.TestCase):
    def test_parser_and_signed_cut_are_exact(self) -> None:
        n, edges = runtime.parse_graph(SIGNED)
        self.assertEqual((n, len(edges)), (3, 3))
        self.assertEqual(runtime.cut_value(n, edges, [0, 1, 0]), 2)
        self.assertEqual(runtime.cut_value(n, edges, [0, 0, 1]), 0)
        self.assertEqual(runtime.cut_value(n, edges, [0, 0, 0]), 0)
        for invalid in [SIGNED.replace(b"3 3", b"3 4"), b"2 2\n1 2 1\n2 1 1\n",
                        b"2 1\n1 1 1\n", b"2 1\n1 3 1\n", b"2 1\n1 2 1.5\n"]:
            with self.subTest(raw=invalid), self.assertRaises(ValueError):
                runtime.parse_graph(invalid)

    def test_invalid_partition_is_not_a_low_score(self) -> None:
        n, edges = runtime.parse_graph(POSITIVE)
        for invalid in [[], [0, 1], [0, 1, 2], [0.0, 1, 0], "010", None]:
            with self.subTest(partition=invalid), self.assertRaises(ValueError):
                runtime.cut_value(n, edges, invalid)

    def test_baseline_handles_signed_graph_and_reaches_local_optimum(self) -> None:
        baseline = importlib.import_module("maxcut_baseline")
        for raw in [SIGNED, POSITIVE]:
            n, edges = runtime.parse_graph(raw)
            partition = baseline.solve(n, edges, 123)
            cut = runtime.cut_value(n, edges, partition)
            self.assertEqual(partition, baseline.solve(n, edges, 123))
            for index in range(n):
                changed = list(partition)
                changed[index] ^= 1
                self.assertLessEqual(runtime.cut_value(n, edges, changed), cut)
        self.assertEqual(runtime.cut_value(*runtime.parse_graph(SIGNED), baseline.solve(*runtime.parse_graph(SIGNED), 0)), 2)

    def test_evaluate_records_source_full_coverage_and_raw_cuts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = fixture(root / "public")
            candidate = root / "solution.py"
            candidate.write_text("def solve(n, edges, seed):\n    return [0, 1, 0]\n")
            result = task.evaluate(public, candidate, root / "run", 17)
            self.assertEqual(result["status"], "success")
            self.assertTrue(result["valid"])
            self.assertEqual(result["score"]["value"], 7)
            self.assertEqual([c["cut"] for c in result["cases"]], [5, 2])
            self.assertEqual(result["evaluation"]["completed_cases"], 2)
            self.assertEqual(result["candidate_scope"], "program_source")
            self.assertEqual(result["candidate_hash"], hashlib.sha256(candidate.read_bytes()).hexdigest())
            self.assertEqual(Path(result["archive"]["source"]).read_bytes(), candidate.read_bytes())
            self.assertEqual(Path(result["archive"]["result"]), (root / "run/result.json").resolve())
            self.assertIsNone(result["archive"]["configuration"])
            repeated = task.evaluate(public, candidate, root / "other", 17)
            self.assertEqual(result["workload_hash"], repeated["workload_hash"])
            self.assertEqual(result["evaluator_hash"], repeated["evaluator_hash"])

    def test_zero_cut_is_valid_but_invalid_or_broken_candidate_has_no_score(self) -> None:
        sources = [("return [0] * n", True), ("return []", False), ("raise RuntimeError('broken')", False)]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = fixture(root / "public")
            candidate = root / "solution.py"
            for index, (body, valid) in enumerate(sources):
                candidate.write_text(f"def solve(n, edges, seed):\n    {body}\n")
                result = task.evaluate(public, candidate, root / str(index), 0)
                self.assertEqual(result["valid"], valid)
                self.assertEqual(result["score"]["value"], 0 if valid else None)
                if not valid:
                    self.assertEqual(result["status"], "failed")
                    self.assertLess(result["evaluation"]["completed_cases"], result["evaluation"]["expected_cases"])

    def test_timeout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = fixture(root / "public")
            candidate = root / "solution.py"
            candidate.write_text("import time\ndef solve(n, edges, seed):\n    time.sleep(10)\n    return [0]*n\n")
            result = task.evaluate(public, candidate, root / "run", 0)
            self.assertFalse(result["valid"])
            self.assertIsNone(result["score"]["value"])
            self.assertEqual(result["error"]["type"], "timeout")

    def test_tampered_graph_fails_before_candidate_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = fixture(root / "public")
            (public / "graphs/positive.txt").write_bytes(SIGNED)
            candidate = root / "solution.py"
            candidate.write_text("def solve(n, edges, seed): return [0]*n\n")
            result = task.evaluate(public, candidate, root / "run", 0)
            self.assertFalse(result["valid"])
            self.assertIn("hash", result["error"]["message"].lower())

    def test_candidate_self_modification_invalidates_execution_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = fixture(root / "public")
            candidate = root / "solution.py"
            candidate.write_text("from pathlib import Path\ndef solve(n, edges, seed):\n"
                                 "    Path(__file__).write_text('def solve(n, edges, seed): return [0]*n\\n')\n"
                                 "    return [0]*n\n")
            result = task.evaluate(public, candidate, root / "run", 0)
            self.assertFalse(result["valid"])
            self.assertIsNone(result["score"]["value"])
            self.assertEqual(result["error"]["type"], "execution_identity_changed")

    def test_confirmation_uses_portable_frozen_source_and_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = fixture(root / "public")
            private = fixture(root / "private", "confirmation")
            candidate = root / "solution.py"
            candidate.write_text("def solve(n, edges, seed): return [0,1,0]\n")
            task.evaluate(public, candidate, root / "run", 0)
            shutil.copytree(root / "run", root / "frozen")
            shutil.rmtree(root / "run")
            candidate.unlink()
            result = task.confirm(public, private, root / "frozen", root / "confirmation", 0)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["evaluation"]["stage"], "confirmation")
            (root / "frozen/candidate.py").write_text("def solve(n, edges, seed): return [0]*n\n")
            rejected = task.confirm(public, private, root / "frozen", root / "rejected", 0)
            self.assertEqual(rejected["status"], "failed")
            self.assertIsNone(rejected["score"]["value"])

    def test_prepare_withholds_confirmation_files_and_exports_standalone_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            cache.mkdir()
            sources = {}
            for name in task.GRAPH_HASHES:
                (cache / name).write_bytes(SIGNED)
                sources[name] = {"url": task.SOURCE_BASE + name,
                                 "sha256": hashlib.sha256(SIGNED).hexdigest(), "bytes": len(SIGNED)}
            with patch.object(task, "fetch_sources", return_value={"sources": sources}):
                prepared = task.prepare(cache, root / "prepared")
            public = Path(prepared["public"])
            public_names = (public / "TASK.md").read_text() + (public / "task.py").read_text() + (public / "protocol.json").read_text()
            for name in task.CONFIRMATION:
                self.assertNotIn(task.SOURCE_BASE + name + '"', public_names)
                self.assertFalse((public / "graphs" / (name + ".txt")).exists())
            run = subprocess.run([sys.executable, str(public / "task.py"), "evaluate", "--public", str(public),
                                  "--candidate", str(public / "candidate.py"), "--output", str(root / "cli"),
                                  "--seed", "123"], capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(json.loads((root / "cli/result.json").read_text())["status"], "success")


if __name__ == "__main__":
    unittest.main()
