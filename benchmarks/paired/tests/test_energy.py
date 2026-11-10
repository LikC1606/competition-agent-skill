from __future__ import annotations

import csv
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("paired_energy", Path(__file__).resolve().parents[1] / "tasks/energy.py")
energy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(energy)
ML = importlib.util.find_spec("sklearn") is not None


class EnergyTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.cache = cls.root / "cache"
        cls.cache.mkdir()
        cls.raw_rows = []
        start = datetime(2016, 1, 11, 17)
        for index in range(19735):
            cls.raw_rows.append({"date": str(start + timedelta(minutes=10 * index)), "Appliances": 50 + index % 144,
                                 "lights": index % 30, **{name: 20 + index / 10000 for name in energy.SENSORS}})
        with (cls.cache / "energydata_complete.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(cls.raw_rows[0]))
            writer.writeheader(); writer.writerows(cls.raw_rows)
        with mock.patch.object(energy, "fetch_sources", return_value={"cache": str(cls.cache), "fixture": "synthetic chronological test rows"}):
            cls.prepared = energy.prepare(cls.cache, cls.root / "prepared")
        cls.public, cls.private = Path(cls.prepared["public"]), Path(cls.prepared["private"])
        cls.protocol = json.loads((cls.public / "protocol.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.root))

    def rows(self, path):
        with path.open() as stream:
            return list(csv.DictReader(stream))

    def test_public_private_chronology_and_complete_oof(self):
        public = self.rows(self.public / "training.csv")
        private = self.rows(self.private / "features.csv")
        by_id = {row["id"]: row for row in public}
        self.assertEqual((len(public), len(private)), (13434, 3853))
        self.assertLess(max(row["id"] for row in public), "2016-04-15")
        self.assertGreaterEqual(min(row["id"] for row in private), "2016-05-01")
        self.assertNotIn("target", private[0])
        self.assertFalse(set(by_id) & {row["id"] for row in private})
        covered = []
        for fold in self.protocol["folds"]:
            self.assertFalse(set(fold["train_ids"]) & set(fold["validation_ids"]))
            latest = max(int(by_id[key]["label_available_time"]) for key in fold["train_ids"])
            earliest = min(int(by_id[key]["prediction_time"]) for key in fold["validation_ids"])
            self.assertGreaterEqual(earliest - latest, 86400)
            covered.extend(fold["validation_ids"])
        self.assertEqual(covered, self.protocol["expected_oof_ids"])
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(len(covered), 8640)

    def test_features_use_only_past_values_and_available_calendar(self):
        first = self.rows(self.public / "training.csv")[0]
        self.assertEqual(float(first["appliances_lag1"]), self.raw_rows[143]["Appliances"])
        self.assertEqual(float(first["appliances_lag144"]), self.raw_rows[0]["Appliances"])
        self.assertAlmostEqual(float(first["appliances_mean6"]), sum(row["Appliances"] for row in self.raw_rows[138:144]) / 6)
        self.assertEqual(float(first["T1_lag1"]), self.raw_rows[143]["T1"])
        self.assertEqual(float(first["target"]), self.raw_rows[144]["Appliances"])
        self.assertFalse({"target", "Appliances", "lights", "T_out", "rv1", "rv2"} & set(energy.FEATURES))
        self.assertEqual(int(first["label_available_time"]) - int(first["prediction_time"]), 600)

    def test_public_bundle_contains_complete_common_adapter_without_raw_holdout(self):
        manifest = energy._verify(self.public, "energy_public")
        for name in energy.CORE_FILES:
            self.assertIn("adapter_core/" + name, manifest["files"])
        self.assertNotIn("energydata_complete.csv", manifest["files"])
        self.assertNotIn("features.csv", manifest["files"])
        self.assertNotIn("truth.csv", manifest["files"])
        self.assertNotIn(str(self.private), (self.public / "TASK.md").read_text())

    def test_edited_protocol_is_rejected_before_training(self):
        copied = self.work / "public"
        shutil.copytree(self.public, copied)
        (copied / "protocol.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Changed task input"):
            energy.evaluate(copied, copied / "candidate.py", self.work / "run", 11)
        self.assertFalse((self.work / "run").exists())

    @unittest.skipUnless(ML, "Run with the isolated ML interpreter")
    def test_future_training_row_is_rejected_even_with_consistent_input_manifest(self):
        copied = self.work / "public"
        shutil.copytree(self.public, copied)
        spec = json.loads((copied / "protocol.json").read_text())
        spec["folds"][0]["train_ids"].append(spec["folds"][0]["validation_ids"][0])
        (copied / "protocol.json").write_text(json.dumps(spec))
        manifest = json.loads((copied / "manifest.json").read_text())
        (copied / "manifest.json").unlink()
        energy._seal(copied, {key: value for key, value in manifest.items() if key not in {"schema_version", "files", "seal"}})
        with self.assertRaisesRegex(ValueError, "overlap"):
            energy.evaluate(copied, copied / "candidate.py", self.work / "run", 11)
        self.assertFalse((self.work / "run" / "result.json").exists())

    @unittest.skipUnless(ML, "Run with the isolated ML interpreter")
    def test_actual_training_stable_recipe_archive_contract_and_seed_binding(self):
        first, second = self.work / "first", self.work / "second"
        a = energy.evaluate(self.public, self.public / "candidate.py", first, 11)
        b = energy.evaluate(self.public, self.public / "candidate.py", second, 19)
        self.assertEqual((first / "recipe.json").read_bytes(), (second / "recipe.json").read_bytes())
        fit = json.loads((first / "fit.json").read_text())
        self.assertEqual(len(fit["folds"]), 3)
        self.assertTrue(all((first / row["model"]).is_file() for row in fit["folds"]))
        result = json.loads(Path(a["archive"]["result"]).read_text())
        self.assertEqual(result["candidate_hash"], energy.digest(Path(a["archive"]["source"]).read_bytes()))
        self.assertEqual(result["candidate_scope"], "prediction_csv")
        self.assertEqual(result["evaluation"]["completed_cases"], 8640)
        self.assertEqual(result["evaluation"]["seeds"], [11])
        self.assertEqual(a["score"], b["score"])
        with self.assertRaisesRegex(ValueError, "seed differ"):
            energy.confirm(self.public, self.private, first, self.work / "wrong-seed", 19)

    @unittest.skipUnless(ML, "Run with the isolated ML interpreter")
    def test_confirmation_uses_relocated_frozen_models_without_fitting(self):
        candidate = self.work / "guard.py"
        candidate.write_text('''import os
from sklearn.dummy import DummyRegressor
class Guard(DummyRegressor):
    def fit(self, X, y, **kwargs):
        if os.environ.get("ENERGY_FORBID_FIT") == "1":
            raise RuntimeError("confirmation attempted fitting")
        return super().fit(X, y, **kwargs)
def build_model(seed, task):
    return Guard()
''')
        run, moved = self.work / "run", self.work / "moved"
        energy.evaluate(self.public, candidate, run, 11)
        shutil.copytree(run, moved)
        shutil.rmtree(run)
        before = {str(p.relative_to(moved)): energy.digest(p.read_bytes()) for p in moved.rglob("*") if p.is_file()}
        with mock.patch.dict(os.environ, {"ENERGY_FORBID_FIT": "1"}):
            result = energy.confirm(self.public, self.private, moved, self.work / "confirmation", 11)
        after = {str(p.relative_to(moved)): energy.digest(p.read_bytes()) for p in moved.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(result["row_count"], 3853)
        scored = json.loads(Path(result["result"]).read_text())
        self.assertEqual(scored["stage"], "confirmation")
        self.assertEqual(scored["training_provenance"]["kind"], "frozen_model_inference")
        model = next((moved / "frozen/models").glob("*.joblib"))
        model.write_bytes(model.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "Artifact changed"):
            energy.confirm(self.public, self.private, moved, self.work / "tampered", 11)

    @unittest.skipUnless(ML, "Run with the isolated ML interpreter")
    def test_nonfinite_predictions_fail_without_success_receipt(self):
        candidate = self.work / "invalid.py"
        candidate.write_text('''import numpy as np
from sklearn.dummy import DummyRegressor
class Invalid(DummyRegressor):
    def predict(self, X):
        return np.full(len(X), np.nan)
def build_model(seed, task):
    return Invalid()
''')
        with self.assertRaisesRegex(ValueError, "finite scalar"):
            energy.evaluate(self.public, candidate, self.work / "invalid", 11)
        self.assertFalse((self.work / "invalid/result.json").exists())
        self.assertFalse((self.work / "invalid/frozen").exists())


if __name__ == "__main__":
    unittest.main()
