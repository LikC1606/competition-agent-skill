"""Exercise real local fitting and delivery when optional ML dependencies exist."""
import copy
import contextlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import tabular_training as adapter
from prediction_core import compare, load_result
from training_execution import append_event, cost_report, fit_cost, proposal_binding
import candidate_archive
from campaign_archive import CampaignArchive

ML_AVAILABLE = all(importlib.util.find_spec(name) for name in ["sklearn", "numpy", "joblib", "threadpoolctl"])


class SplitContractTests(unittest.TestCase):
    def test_saved_oof_screen_checks_training_and_validation_membership_and_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def saved_oof(name, folds, *, first_target=1, freeze=False):
                run = root / name
                run.mkdir()
                oof = run / "oof.csv"
                adapter.save_csv(oof, ["Id", "prediction"], [("a", 1), ("b", 2), ("c", 3), ("d", 4)])
                adapter.save_csv(run / "truth.csv", ["Id", "target"],
                                 [("a", first_target), ("b", 2), ("c", 3), ("d", 4)])
                protocol = {"id_column": "Id", "task": "regression"}
                adapter.write_json(run / "protocol.json", protocol)
                adapter.write_json(run / "fit.json", {"folds": [
                    {"fold_id": key, "train_ids": list(train), "validation_ids": list(validation)}
                    for key, train, validation in folds]})
                model = run / "fold-0.joblib"
                model.write_bytes(b"model bytes are outside this preflight")
                adapter.seal(run, {"kind": "tabular_training", "protocol_hash": adapter.object_hash(protocol)})
                if freeze:
                    copy = root / "frozen"
                    adapter.freeze(run, copy, "Fixture decision")
                    (copy / model.name).unlink()
                    return copy / oof.name
                model.unlink()
                return oof

            folds = [("0", "cd", "ab"), ("1", "ab", "cd")]
            reference = saved_oof("reference", folds)
            reordered = saved_oof("reordered", [("last", "ba", "dc"), ("first", "dc", "ba")])
            other_validation = saved_oof("other-validation", [("0", "bd", "ac"), ("1", "ac", "bd")])
            other_training = saved_oof("other-training", [("0", "c", "ab"), ("1", "ab", "cd")])
            other_truth = saved_oof("other-truth", folds, first_target=0)
            frozen = saved_oof("original", folds, freeze=True)
            missing = saved_oof("missing-fit", folds)
            missing.with_name("fit.json").unlink()
            changed = saved_oof("tampered-oof", folds)
            changed.write_text("Id,prediction\na,9\nb,2\nc,3\nd,4\n", encoding="utf-8")

            cmd = [sys.executable, "-B", str(SCRIPTS / "prediction_evidence.py")]
            report = subprocess.run(cmd + ["--reference", str(reference), *map(str, [
                reordered, other_validation, other_training, other_truth, frozen, missing, changed])],
                capture_output=True, text=True, check=True)
            candidates = {Path(row["oof"]).parent.name: row for row in json.loads(report.stdout)["candidates"]}
            self.assertEqual({name: row["status"] for name, row in candidates.items()}, {
                "reordered": "matched", "other-validation": "different_folds",
                "other-training": "different_folds", "other-truth": "different_truth", "frozen": "matched",
                "missing-fit": "unverified", "tampered-oof": "unverified"})
            self.assertIn("different OOF predictions", candidates["tampered-oof"]["reason"])

            invalid_reference = subprocess.run(cmd + ["--reference", str(changed), str(reference)],
                                               capture_output=True, text=True)
            self.assertEqual(invalid_reference.returncode, 2)
            self.assertFalse(invalid_reference.stdout)

    def test_group_overlap_rejected(self):
        with self.assertRaisesRegex(adapter.TrainingFailure, "groups overlap"):
            adapter.check_boundary({"split": {"kind": "group", "group_column": "group"}},
                                   {"a": {"group": "same"}}, {"b": {"group": "same"}})

    def test_time_availability_and_gap(self):
        spec = {"split": {"kind": "time", "time_column": "time", "time_format": "number",
                          "available_time_column": "available", "minimum_time_gap": "2"}}
        earlier = {"a": {"time": "1", "available": "5"}}
        for next_time in ["4", "5", "6"]:
            with self.subTest(next_time=next_time), self.assertRaises(adapter.TrainingFailure):
                adapter.check_boundary(spec, earlier, {"b": {"time": next_time}})
        adapter.check_boundary(spec, earlier, {"b": {"time": "7"}})

    def test_plan_cost_counts_actual_folds_across_partitions_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ids = [str(i) for i in range(10)]
            paths = []
            for number in range(5):
                folds = []
                for index in range(5):
                    validation = [key for key in ids if (int(key) + number * (int(key) % 2)) % 5 == index]
                    folds.append({"id": str(index), "seed": index,
                                  "train_ids": [key for key in ids if key not in validation],
                                  "validation_ids": validation})
                path = root / f"partition-{number}.json"
                adapter.write_json(path, {"schema_version": 1, "task_id": "cost-fixture", "task": "regression",
                                          "metric": "rmse", "features": ["x"], "split": {"kind": "iid"},
                                          "expected_oof_ids": ids, "folds": folds})
                paths.append(path)
            cmd = [sys.executable, "-B", str(SCRIPTS / "tabular_training.py"), "plan-cost"]
            for path in paths:
                cmd += ["--protocol", str(path)]
            mismatch = subprocess.run(cmd + ["--expected-fit-calls", "15"], capture_output=True, text=True)
            self.assertEqual(mismatch.returncode, 2)
            self.assertIn("supplied protocols require 25", json.loads(mismatch.stderr)["error"]["message"])
            ok = subprocess.run(cmd + ["--expected-fit-calls", "25"], capture_output=True, text=True, check=True)
            result = json.loads(ok.stdout)
            self.assertEqual(result["fit_calls"], 25)
            self.assertEqual([row["fit_calls"] for row in result["requests"]], [5] * 5)

            with patch.object(adapter, "runtime", side_effect=AssertionError("no runtime before cost check")):
                with self.assertRaisesRegex(adapter.TrainingFailure, "require 5"):
                    adapter.train(root / "unused-data.csv", paths[0], root / "unused-candidate.py", root / "run",
                                  expected_fit_calls=3)
            self.assertFalse((root / "run").exists())


@unittest.skipUnless(ML_AVAILABLE, "Optional dependencies: scripts/requirements-tabular.txt")
class TabularTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data.csv"
        adapter.save_csv(self.data, ["id", "x", "target", "group", "time"],
                         [(str(i), i, i * 3 + 2, str(i // 2), i) for i in range(12)])
        self.spec = {"schema_version": 1, "task_id": "local-regression", "task": "regression",
                     "metric": "rmse", "features": ["x"], "split": {"kind": "group", "group_column": "group"},
                     "expected_oof_ids": [str(i) for i in range(12)], "folds": [
                         {"id": str(j), "seed": 100 + j,
                          "train_ids": [str(i) for i in range(12) if i // 2 % 3 != j],
                          "validation_ids": [str(i) for i in range(12) if i // 2 % 3 == j]} for j in range(3)]}
        self.protocol = self.root / "protocol.json"
        self.protocol.write_text(json.dumps(self.spec))
        self.candidate = self.root / "candidate.py"
        self.candidate.write_text("from sklearn.pipeline import make_pipeline\n"
                                  "from sklearn.preprocessing import StandardScaler\n"
                                  "from sklearn.linear_model import LinearRegression\n"
                                  "def build_model(seed, task):\n"
                                  "    return make_pipeline(StandardScaler(), LinearRegression())\n")

    def train(self, name="run"):
        output = self.root / name
        adapter.train(self.data, self.protocol, self.candidate, output)
        return output

    def frozen(self):
        run = self.train()
        frozen = self.root / "frozen"
        adapter.freeze(run, frozen, "Deliver only if the frozen candidate passes the independent confirmation rule")
        return frozen

    def holdout(self):
        data, truth = self.root / "confirmation.csv", self.root / "confirmation-truth.csv"
        adapter.save_csv(data, ["id", "x", "group"], [("h2", 15, "new-1"), ("h1", 14, "new-2")])
        adapter.save_csv(truth, ["id", "target"], [("h1", 44), ("h2", 47)])
        return data, truth

    def test_actual_pipeline_fits_only_fold_rows_and_oof_is_recomputed(self):
        import joblib
        run = self.train()
        report = adapter.read_json(run / "fit.json")
        for fold in report["folds"]:
            model = joblib.load(run / fold["model"])
            ids = list(map(int, fold["train_ids"]))
            self.assertEqual(model[0].n_samples_seen_, len(ids))
            self.assertAlmostEqual(model[0].mean_[0], sum(ids) / len(ids))
        values = adapter.read_json(run / "evaluation/result.json")
        self.assertEqual(values["evaluation"]["completed_cases"], 12)
        self.assertLess(values["score"]["value"], 1e-12)
        self.assertEqual(values["evaluation"]["stage"], "development")
        self.assertEqual(len(adapter.csv_rows(run / "oof.csv", ["id", "prediction"])[1]), 12)

    def test_repeated_fit_preserves_recipe_identity(self):
        first = self.train("first")
        second = self.train("repeat")
        self.assertEqual((first / "recipe.json").read_bytes(), (second / "recipe.json").read_bytes())
        receipt = adapter.read_json(first / "recipe.json")
        self.assertIn("candidate_source", receipt)
        self.assertNotIn("fit_seconds", receipt)

    def test_recompose_uses_the_added_members_saved_fit_and_scores_new_oof(self):
        import numpy as np

        control = self.train("control")
        self.spec["features"] = ["group", "x"]
        self.protocol.write_text(json.dumps(self.spec))
        self.candidate.write_text("""import numpy as np

class LocalMember:
    def fit(self, X, y):
        self.train_prediction_ = y - 3 * X[:, 1]
        return self
    def predict(self, X):
        return X[:, 0] + 3 * X[:, 1]

def build_model(seed, task):
    return LocalMember()
""")
        member = self.train("extra-member")
        composition = self.root / "composition.py"
        composition.write_text("""import numpy as np

def predict_fold(control, member, x_fit, x_score, member_x_fit, member_x_score, *, include_member):
    centre = control.predict(x_score)
    scale = np.mean(member.train_prediction_)
    return centre + include_member * np.clip(member.predict(member_x_score) - centre, -scale, scale) / 4
""")
        output = self.root / "recomposed"
        received = subprocess.run([sys.executable, "-B", str(SCRIPTS / "tabular_training.py"), "recompose",
                                   "--control", str(control), "--member", str(member),
                                   "--composition", str(composition), "--output-dir", str(output)],
                                  capture_output=True, text=True, check=True)
        report = json.loads(received.stdout)
        self.assertEqual(report["new_fit_calls"], 0)
        self.assertEqual(report["inputs"]["control"]["originating_cost"], fit_cost(control))
        self.assertEqual(report["inputs"]["member"]["originating_cost"]["completed_fit_calls"], 3)
        self.assertTrue(all(row["control_max_abs_error"] == 0 for row in report["folds"]))
        _, rows = adapter.csv_rows(output / "oof.csv", ["id", "prediction"])
        expected = [3 * i + 2 + np.clip(i // 2 - 2, -2, 2) / 4 for i in range(12)]
        np.testing.assert_allclose([float(rows[str(i)]["prediction"]) for i in range(12)], expected, rtol=0, atol=1e-14)
        baseline = load_result(control / "evaluation/result.json")
        combined = load_result(output / "evaluation/result.json")
        compare(baseline, combined, 0)
        self.assertNotEqual(combined["candidate_hash"], baseline["candidate_hash"])
        self.assertNotIn("training_execution", combined)
        self.assertGreater(combined["score"]["value"], baseline["score"]["value"])
        self.assertEqual(adapter.verified_manifest(output, "tabular_recomposition")["seal"], report["seal"])

        composition.write_text("def predict_fold(control, member, x_fit, x_score, *_, include_member):\n"
                               "    return control.predict(x_score) + 1\n")
        invalid = self.root / "wrong-control"
        with self.assertRaisesRegex(adapter.TrainingFailure, "Control reproduction failed on fold"):
            adapter.recompose(control, member, composition, invalid)
        self.assertFalse(invalid.exists())

    def test_recompose_reuses_members_inside_one_saved_control(self):
        self.candidate.write_text("""import numpy as np

class TwoMembers:
    def fit(self, X, y):
        self.offset_ = float(np.mean(y - 3 * X[:, 0]))
        return self
    def members(self, X):
        trend = 3 * X[:, 0]
        return trend, trend + 2 * self.offset_
    def predict(self, X):
        a, b = self.members(X)
        return 0.5 * a + 0.5 * b

def build_model(seed, task):
    return TwoMembers()
""")
        control = self.train("control")
        composition = self.root / "composition.py"
        composition.write_text("""def predict_fold(control, member, x_fit, x_score, member_x_fit, member_x_score, *, include_member):
    assert member is member_x_fit is member_x_score is None
    a, b = control.members(x_score)
    weight_b = 0.25 if include_member else 0.5
    return (1 - weight_b) * a + weight_b * b
""")
        output = self.root / "recomposed"
        received = subprocess.run([sys.executable, "-B", str(SCRIPTS / "tabular_training.py"), "recompose",
                                   "--control", str(control), "--composition", str(composition),
                                   "--output-dir", str(output)], capture_output=True, text=True, check=True)
        report = json.loads(received.stdout)
        self.assertEqual(report["new_fit_calls"], 0)
        self.assertEqual(set(report["inputs"]), {"control"})
        self.assertTrue(all(row["control_max_abs_error"] == 0 for row in report["folds"]))
        result = load_result(output / "evaluation/result.json")
        compare(load_result(control / "evaluation/result.json"), result, 0)
        self.assertEqual(result["score"]["value"], 1.0)
        self.assertNotIn("training_execution", result)

    def test_recompose_refuses_mismatched_folds_before_importing_composition(self):
        control = self.train("control")
        self.spec["folds"][0]["seed"] += 1
        self.protocol.write_text(json.dumps(self.spec))
        mismatched = self.train("mismatched")
        never_import = self.root / "must-not-open.py"
        output = self.root / "recomposed"
        with self.assertRaisesRegex(adapter.TrainingFailure, "including fold IDs, row order and seeds"):
            adapter.recompose(control, mismatched, never_import, output)
        self.assertFalse(output.exists())

    def test_identical_request_reuses_completed_fit_in_new_or_existing_directory(self):
        from sklearn.linear_model import LinearRegression
        original = LinearRegression.fit
        with patch.object(LinearRegression, "fit", autospec=True, side_effect=original) as fits:
            first = self.train("first")
            first_result = (first / "evaluation/result.json").read_bytes()
            report = adapter.train(self.data, self.protocol, self.candidate, self.root / "relocated")
            same = adapter.train(self.data, self.protocol, self.candidate, first)
        self.assertEqual(fits.call_count, 3)
        self.assertEqual(report["new_fit_calls"], 0)
        self.assertEqual(same["new_fit_calls"], 0)
        self.assertEqual(first_result, (self.root / "relocated/evaluation/result.json").read_bytes())
        adapter.verified_manifest(self.root / "relocated", "tabular_training")
        self.assertEqual(fit_cost(first)["fit_calls"], 3)
        totals = cost_report([first, self.root / "relocated"])
        self.assertEqual(totals["fit_calls"], 3)
        self.assertEqual(totals["unique_executions"], 1)

    def test_changed_seed_and_explicit_repeat_are_new_measurements(self):
        first = self.train()
        self.spec["folds"][0]["seed"] += 1
        self.protocol.write_text(json.dumps(self.spec))
        changed = self.train("changed-seed")
        repeated = self.root / "intentional-repeat"
        result = adapter.train(self.data, self.protocol, self.candidate, repeated,
                               retry_reason="Independent planned measurement")
        self.assertEqual(result["new_fit_calls"], 3)
        self.assertNotEqual(adapter.read_json(first / "execution.json")["identity_hash"],
                            adapter.read_json(changed / "execution.json")["identity_hash"])
        self.assertNotEqual(fit_cost(changed)["execution_id"], fit_cost(repeated)["execution_id"])

    def test_failed_fit_is_counted_and_automatic_retry_is_refused(self):
        self.candidate.write_text("class Broken:\n"
                                  "    def fit(self, x, y): raise RuntimeError('actual fit failure')\n"
                                  "def build_model(seed, task): return Broken()\n")
        with self.assertRaisesRegex(RuntimeError, "actual fit failure"):
            self.train("failed")
        cost = fit_cost(self.root / "failed")
        self.assertEqual((cost["fit_calls"], cost["failed_fit_calls"], cost["unresolved_fit_calls"]), (1, 1, 0))
        self.assertGreaterEqual(cost["fit_seconds_recorded"], 0)
        with self.assertRaisesRegex(adapter.TrainingFailure, "incomplete execution"):
            self.train("unintended-retry")
        self.assertFalse((self.root / "unintended-retry").exists())

    def test_killed_fit_remains_unknown_and_journal_tail_does_not_hide_started_fit(self):
        root = self.root / "killed"
        root.mkdir()
        adapter.write_json(root / "execution.json", {"execution_id": "interrupted"})
        append_event(root / "fit-events.jsonl", {"event": "fit_started", "fold_id": "0"})
        with (root / "fit-events.jsonl").open("ab") as stream:
            stream.write(b'{"partial":')
        cost = fit_cost(root)
        self.assertEqual(cost["unresolved_fit_calls"], 1)
        self.assertFalse(cost["journal_complete"])
        self.assertIsNone(cost["workflow_seconds"])

    def archive_run(self, run, candidate_id, *extra):
        args = candidate_archive.parser().parse_args([
            "record", "--archive", str(self.root / "archive.jsonl"), "--candidate-id", candidate_id,
            "--result", str(run / "evaluation/result.json"), "--configuration", str(run / "recipe.json"),
            "--route", "numeric", "--mechanism", "different estimator", "--status", "promising",
            "--feedback", "The measured residuals support the next comparison",
            "--prediction-status", "supported", *extra])
        return candidate_archive.record_candidate(args)

    def make_proposal(self, baseline):
        archive = self.root / "archive.jsonl"
        value = {"proposal_id": "change", "parent_ids": ["baseline"], "feedback_from": ["baseline"],
                 "route": "numeric", "basis": "Development residuals", "change": "Use a dummy mean model",
                 "expected_observation": "Nonlinear residuals remain", "validation": "Same frozen folds",
                 "stop_condition": "One matched observation", "code_targets": [str(baseline / "recipe.json")]}
        source = self.root / "proposal.json"
        source.write_text(json.dumps(value))
        candidate_archive.propose_candidate(candidate_archive.parser().parse_args([
            "propose", "--archive", str(archive), "--proposal", str(source)]))
        return archive

    def test_launch_binds_proposal_and_archive_records_measured_cost(self):
        baseline = self.train("baseline")
        self.archive_run(baseline, "baseline")
        archive = self.make_proposal(baseline)
        self.candidate.write_text("from sklearn.dummy import DummyRegressor\n"
                                  "def build_model(seed, task): return DummyRegressor()\n")
        successor = self.root / "successor"
        adapter.train(self.data, self.protocol, self.candidate, successor, archive=archive, proposal_id="change")
        result = self.archive_run(successor, "successor", "--parent", "baseline", "--proposal-id", "change")
        self.assertEqual(result["cost"]["training_execution"]["completed_fit_calls"], 3)
        self.assertEqual(len(candidate_archive.read_records(archive)), 3)
        with self.assertRaisesRegex(ValueError, "already closed"):
            proposal_binding(archive, "change")
        copied = adapter.train(self.data, self.protocol, self.candidate, self.root / "after-archive",
                               archive=archive, proposal_id="change")
        self.assertEqual(copied["new_fit_calls"], 0)

    def test_managed_paired_measurement_binds_protocol_and_seals_result(self):
        challenger = self.train("challenger")
        challenger_entry = self.archive_run(challenger, "challenger")
        source = self.root / "baseline.py"
        source.write_text("from sklearn.dummy import DummyRegressor\n"
                          "def build_model(seed, task): return DummyRegressor()\n")
        baseline = self.root / "baseline"
        adapter.train(self.data, self.protocol, source, baseline)
        leader = self.archive_run(baseline, "baseline")
        archive = self.root / "archive.jsonl"
        protocol = adapter.plan_cost([self.protocol], 3)["requests"][0]
        plan = self.root / "plan.json"
        adapter.write_json(plan, {"plan_id": "adoption", "comparison": leader["comparison"],
                                  "leader_candidate": "baseline", "challenger_candidate": "challenger",
                                  "runs": [{"run_id": "fixed", "seeds": [], "repetitions": 1,
                                            "leader_result": "baseline", "protocol_sha256": protocol["protocol_sha256"]}],
                                  "decision_rule": {"requirements": [{"statistic": "mean_improvement",
                                                                        "operator": ">", "threshold": 1}]}})
        plan_entry = candidate_archive.record_measurement_plan(candidate_archive.parser().parse_args([
            "measure-plan", "--archive", str(archive), "--plan", str(plan)]))
        planned = self.root / "paired"
        kwargs = {"measurement_archive": archive, "measurement_plan_id": "adoption", "measurement_run_id": "fixed",
                  "expected_fit_calls": 3}
        wrong_protocol = self.root / "not-frozen.json"
        wrong_protocol.write_bytes(self.protocol.read_bytes() + b"\n")
        with self.assertRaisesRegex(adapter.TrainingFailure, "exact protocol bytes"):
            adapter.train(self.data, wrong_protocol, self.candidate, planned, **kwargs)
        with self.assertRaisesRegex(adapter.TrainingFailure, "unfilled side"):
            adapter.train(self.data, self.protocol, source, planned, **kwargs)
        self.assertFalse(planned.exists())

        fitted = adapter.train(self.data, self.protocol, self.candidate, planned, **kwargs)
        self.assertEqual(fitted["new_fit_calls"], 3)
        paired = self.archive_run(planned, "measured-challenger", "--reuse-reason", "Frozen paired measurement")
        self.assertEqual(paired["result"]["measurement_run_id"], "fixed")
        self.assertEqual(paired["cost"]["training_execution"]["completed_fit_calls"], 3)
        view = candidate_archive.measurement_plans.status(plan_entry, candidate_archive.read_records(archive))
        self.assertEqual(view["rule_result"]["state"], "passed")
        decision = self.root / "decision.json"
        adapter.write_json(decision, {"plan_id": "adoption", "outcome": "qualified", "conclusion": "Passed the frozen margin",
                                      "reason": "Matched RMSE improved by more than one", "next_action": "Retain the evidence"})
        candidate_archive.record_measurement_decision(candidate_archive.parser().parse_args([
            "measure-decide", "--archive", str(archive), "--decision", str(decision)]))
        candidate_archive.measurement_plans.validate_selection(challenger_entry, candidate_archive.read_records(archive))

    def test_managed_costs_are_automatic_and_manual_override_gives_recovery(self):
        run = self.train()
        with self.assertRaisesRegex(candidate_archive.ArchiveFailure, "omit training_execution"):
            self.archive_run(run, "manual", "--cost", '{"training_execution":{"fit_calls":0}}')
        record = self.archive_run(run, "automatic")
        self.assertEqual(record["cost"]["training_execution"], adapter.execution_descriptor(run)["cost"])
        self.assertEqual(len(candidate_archive.read_records(self.root / "archive.jsonl")), 1)

    def test_late_proposal_cannot_bind_previously_executed_run(self):
        baseline = self.train("baseline")
        self.archive_run(baseline, "baseline")
        self.candidate.write_text("from sklearn.dummy import DummyRegressor\n"
                                  "def build_model(seed, task): return DummyRegressor()\n")
        successor = self.train("executed-before-proposal")
        archive = self.make_proposal(baseline)
        with self.assertRaisesRegex(candidate_archive.ArchiveFailure, "not bound before training"):
            self.archive_run(successor, "too-late", "--parent", "baseline", "--proposal-id", "change")
        with self.assertRaisesRegex(adapter.TrainingFailure, "different proposal provenance"):
            adapter.train(self.data, self.protocol, self.candidate, self.root / "late-binding-copy",
                          archive=archive, proposal_id="change")
        self.assertEqual(len(candidate_archive.read_records(archive)), 2)

    def test_unknown_proposal_fails_before_output_or_fit(self):
        archive = self.root / "empty.jsonl"
        archive.touch()
        with self.assertRaisesRegex(ValueError, "before training"):
            adapter.train(self.data, self.protocol, self.candidate, self.root / "invalid",
                          archive=archive, proposal_id="missing")
        self.assertFalse((self.root / "invalid").exists())

    def test_archive_detects_modified_fit_cost_receipt(self):
        baseline = self.train("baseline")
        append_event(baseline / "fit-events.jsonl", {"event": "fit_started", "fold_id": "fake"})
        with self.assertRaisesRegex(candidate_archive.ArchiveFailure, "Training artifact changed"):
            self.archive_run(baseline, "baseline")

    def saved_scoring_reference(self, run):
        scorer = self.root / "saved-scorer"
        scorer.mkdir()
        for name in ["evaluate_predictions.py", "prediction_core.py"]:
            raw = (SCRIPTS / name).read_bytes()
            if name == "prediction_core.py":
                raw += b"\n# Saved evaluator version retained for this contract.\n"
            (scorer / name).write_bytes(raw)
        result = adapter.read_json(run / "evaluation/result.json")
        config = result["evaluation"]["configuration"]
        reference = self.root / "reference"
        command = [sys.executable, "-B", str(scorer / "evaluate_predictions.py"),
                   "--truth", str(run / "truth.csv"), "--predictions", str(run / "oof.csv"),
                   "--stage", "development", "--split-id", config["split_id"],
                   "--metric", config["score_model"]["metric"],
                   "--id-column", config["id_column"], "--target-column", config["target_column"],
                   "--prediction-column", config["prediction_column"],
                   "--output-dir", str(reference)]
        subprocess.run(command, capture_output=True, text=True, check=True)
        return scorer / "evaluate_predictions.py", reference / "result.json"

    def test_rescore_cli_uses_saved_contract_nondefault_columns_and_zero_fits(self):
        self.data.unlink()
        adapter.save_csv(self.data, ["PassengerId", "x", "SalePriceLog", "group", "time"],
                         [(str(i), i, i * 3 + 2, str(i // 2), i) for i in range(12)])
        self.spec.update(id_column="PassengerId", target_column="SalePriceLog", prediction_column="Answer")
        self.protocol.write_text(json.dumps(self.spec))
        self.candidate.write_text("import os\n"
                                  "if os.environ.get('FORBID_REIMPORT'): raise RuntimeError('candidate imported')\n"
                                  "from sklearn.linear_model import LinearRegression\n"
                                  "def build_model(seed, task): return LinearRegression()\n")
        run = self.train()
        before = adapter.artifact_hashes(run)
        evaluator, reference = self.saved_scoring_reference(run)
        output = self.root / "rescored"
        result = subprocess.run([
            sys.executable, "-B", str(SCRIPTS / "tabular_training.py"), "rescore",
            "--run", str(run), "--evaluator", str(evaluator), "--reference-result", str(reference),
            "--output-dir", str(output)], capture_output=True, text=True,
            env={**os.environ, "FORBID_REIMPORT": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        measured = load_result(output / "evaluation/result.json")
        original = load_result(run / "evaluation/result.json")
        self.assertEqual(receipt["new_fit_calls"], 0)
        self.assertEqual(receipt["originating_cost"]["fit_calls"], 3)
        self.assertEqual(before, adapter.artifact_hashes(run))
        self.assertNotEqual(original["evaluator_hash"], measured["evaluator_hash"])
        self.assertEqual(measured["evaluator_hash"], load_result(reference)["evaluator_hash"])
        self.assertEqual(measured["candidate_hash"], original["candidate_hash"])
        self.assertEqual(measured["score"]["value"], original["score"]["value"])
        self.assertEqual(measured["evaluation"], original["evaluation"])
        with self.assertRaises(FileExistsError):
            adapter.rescore(run, evaluator, reference, output)

    def test_rescored_bound_proposal_keeps_verified_cost_and_replays(self):
        baseline = self.train("baseline")
        self.archive_run(baseline, "baseline")
        archive = self.make_proposal(baseline)
        self.candidate.write_text("from sklearn.dummy import DummyRegressor\n"
                                  "def build_model(seed, task): return DummyRegressor()\n")
        successor = self.root / "successor"
        adapter.train(self.data, self.protocol, self.candidate, successor, archive=archive, proposal_id="change")
        evaluator, reference = self.saved_scoring_reference(baseline)
        output = self.root / "rescored"
        with patch.object(adapter, "runtime", side_effect=AssertionError("no fitting runtime in rescore")):
            receipt = adapter.rescore(successor, evaluator, reference, output)
        args = candidate_archive.parser().parse_args([
            "record", "--archive", str(archive), "--candidate-id", "rescored",
            "--source", str(successor / "oof.csv"), "--result", receipt["result"],
            "--configuration", str(successor / "recipe.json"), "--parent", "baseline",
            "--proposal-id", "change", "--prediction-status", "contradicted",
            "--route", "numeric", "--mechanism", "dummy control", "--status", "rejected",
            "--feedback", "Dummy predictions have larger residuals on the pinned contract"])
        record = candidate_archive.record_candidate(args)
        original = load_result(successor / "evaluation/result.json")["training_execution"]
        self.assertEqual(record["cost"]["training_execution"], original["cost"])
        self.assertEqual(record["result"]["training_execution"]["proposal_at_launch"], original["proposal_at_launch"])
        self.assertEqual(len(CampaignArchive(archive).verified().evidence.records), 3)

    def test_rescore_cannot_bind_a_late_proposal(self):
        baseline = self.train("baseline")
        self.archive_run(baseline, "baseline")
        self.candidate.write_text("from sklearn.dummy import DummyRegressor\n"
                                  "def build_model(seed, task): return DummyRegressor()\n")
        successor = self.train("before-proposal")
        archive = self.make_proposal(baseline)
        evaluator, reference = self.saved_scoring_reference(baseline)
        output = self.root / "rescored"
        receipt = adapter.rescore(successor, evaluator, reference, output)
        args = candidate_archive.parser().parse_args([
            "record", "--archive", str(archive), "--candidate-id", "late",
            "--result", receipt["result"], "--configuration", str(successor / "recipe.json"),
            "--parent", "baseline", "--proposal-id", "change", "--prediction-status", "contradicted",
            "--route", "numeric", "--mechanism", "dummy control", "--status", "rejected"])
        with self.assertRaisesRegex(candidate_archive.ArchiveFailure, "not bound before training"):
            candidate_archive.record_candidate(args)
        self.assertEqual(len(candidate_archive.read_records(archive)), 2)

    def test_rescore_rejects_wrong_evaluator_or_changed_reference_inputs_before_writing(self):
        run = self.train()
        evaluator, reference = self.saved_scoring_reference(run)
        output = self.root / "rejected"
        with self.assertRaisesRegex(adapter.TrainingFailure, "reference evaluator hash"):
            adapter.rescore(run, SCRIPTS / "evaluate_predictions.py", reference, output)
        with patch.object(adapter, "metric_backend", return_value={"scikit-learn": "different-version"}):
            with self.assertRaisesRegex(adapter.TrainingFailure, "reference numeric dependency versions"):
                adapter.rescore(run, evaluator, reference, output)
        self.assertFalse(output.exists())
        value = adapter.read_json(reference)
        value["evaluation"]["configuration"]["split_id"] = "different-split"
        value["evaluation"]["split_id"] = "different-split"
        value["evaluation"]["config_hash"] = adapter.object_hash(value["evaluation"]["configuration"])
        reference.write_text(json.dumps(value))
        with self.assertRaisesRegex(adapter.TrainingFailure, "Reference scoring inputs differ"):
            adapter.rescore(run, evaluator, reference, output)
        self.assertFalse(output.exists())

    def test_rescore_preserves_probability_metric_and_rejects_confirmation_reference(self):
        self.data.unlink()
        adapter.save_csv(self.data, ["id", "x", "target", "group", "time"],
                         [(str(i), i, i % 2, str(i // 2), i) for i in range(12)])
        self.spec.update(task="binary", metric="binary_log_loss")
        self.protocol.write_text(json.dumps(self.spec))
        self.candidate.write_text("from sklearn.dummy import DummyClassifier\n"
                                  "def build_model(seed, task): return DummyClassifier(strategy='prior')\n")
        run = self.train()
        evaluator, reference = self.saved_scoring_reference(run)
        receipt = adapter.rescore(run, evaluator, reference, self.root / "rescored")
        self.assertEqual(receipt["new_fit_calls"], 0)
        self.assertEqual(load_result(Path(receipt["result"]))["score"], load_result(reference)["score"])
        value = adapter.read_json(reference)
        value["evaluation"]["configuration"]["stage"] = "confirmation"
        value["evaluation"]["stage"] = "confirmation"
        value["evaluation"]["config_hash"] = adapter.object_hash(value["evaluation"]["configuration"])
        reference.write_text(json.dumps(value))
        with self.assertRaisesRegex(adapter.TrainingFailure, "development training results"):
            adapter.rescore(run, evaluator, reference, self.root / "confirmation-rejected")
        self.assertFalse((self.root / "confirmation-rejected").exists())

    def test_rescore_checks_original_training_bytes_and_linked_cost(self):
        run = self.train()
        evaluator, reference = self.saved_scoring_reference(run)
        output = self.root / "rescored"
        receipt = adapter.rescore(run, evaluator, reference, output)
        result_path = output / "evaluation/result.json"
        result = adapter.read_json(result_path)
        from training_execution import verify_execution
        verify = lambda: verify_execution(result_path, adapter.read_json(result_path)["training_execution"],
                                          archive=self.root / "archive.jsonl", proposal_id=None,
                                          configuration=run / "recipe.json")
        verify()
        result["training_execution"]["cost"]["fit_calls"] = 0
        result_path.write_text(json.dumps(result))
        (output / "manifest.json").unlink()
        adapter.seal(output, {"kind": "tabular_rescore", "new_fit_calls": 0})
        with self.assertRaisesRegex(ValueError, "originating training receipt"):
            verify()
        result["training_execution"]["cost"]["fit_calls"] = receipt["originating_cost"]["fit_calls"]
        result_path.write_text(json.dumps(result))
        (output / "manifest.json").unlink()
        adapter.seal(output, {"kind": "tabular_rescore", "new_fit_calls": 0})
        with (run / "fit-events.jsonl").open("ab") as stream:
            stream.write(b"\n")
        with self.assertRaisesRegex(ValueError, "Training artifact changed"):
            verify()

    def test_new_group_relation_rejects_row_cv_before_fitting(self):
        self.spec["relations"] = [{"column": "group", "inference": "new_groups",
                                  "rationale": "Future entities are absent from training"}]
        self.spec["split"] = {"kind": "iid"}
        for index, fold in enumerate(self.spec["folds"]):
            fold["train_ids"] = [str(i) for i in range(12) if i % 3 != index]
            fold["validation_ids"] = [str(i) for i in range(12) if i % 3 == index]
        self.protocol.write_text(json.dumps(self.spec))
        inference, _ = self.holdout()
        with self.assertRaisesRegex(adapter.TrainingFailure, "new groups"):
            adapter.train(self.data, self.protocol, self.candidate, self.root / "bad-row-cv",
                          inference_data=inference)
        self.assertFalse((self.root / "bad-row-cv").exists())
        self.spec["folds"] = [{"id": str(j), "seed": 100 + j,
                               "train_ids": [str(i) for i in range(12) if i // 2 % 3 != j],
                               "validation_ids": [str(i) for i in range(12) if i // 2 % 3 == j]} for j in range(3)]
        self.protocol.write_text(json.dumps(self.spec))
        adapter.train(self.data, self.protocol, self.candidate, self.root / "valid-groups", inference_data=inference)
        launch = adapter.read_json(self.root / "valid-groups/execution.json")
        self.assertEqual(launch["relations"][0]["validation_known_row_fractions"], [0, 0, 0])

    def test_binary_accuracy_averages_probability_before_fixed_decision(self):
        self.data.write_text("id,x,target,group\n" + "".join(
            f"{i},{i},{i % 2},{i // 2}\n" for i in range(12)))
        self.spec.update(task="binary", metric="accuracy")
        self.protocol.write_text(json.dumps(self.spec))
        self.candidate.write_text("import numpy as np\nclass Constant:\n"
                                  "    def __init__(self, seed): self.p = {100: 0.9, 101: 0.4, 102: 0.4}[seed]\n"
                                  "    def fit(self, x, y): self.classes_ = np.array([0, 1]); return self\n"
                                  "    def predict_proba(self, x): return np.tile([1-self.p, self.p], (len(x), 1))\n"
                                  "def build_model(seed, task): return Constant(seed)\n")
        run = self.train()
        self.assertEqual(adapter.read_json(run / "evaluation/result.json")["score"]["value"], 0.5)
        frozen = self.root / "frozen"
        adapter.freeze(run, frozen, "Use frozen probability mean with threshold 0.5")
        data, _ = self.holdout()
        sample = self.root / "sample.csv"
        adapter.save_csv(sample, ["id", "prediction"], [("h1", 0), ("h2", 0)])
        output = self.root / "final"
        adapter.deliver(frozen, data, output, sample_submission=sample)
        _, rows = adapter.csv_rows(output / "submission.csv", ["id", "prediction"])
        self.assertTrue(all(float(row["prediction"]) == 1 for row in rows.values()))
        sample.write_text("id,prediction\nh2,False\nh1,True\n")
        adapter.deliver(frozen, data, self.root / "boolean-final", sample_submission=sample)
        _, rows = adapter.csv_rows(self.root / "boolean-final/submission.csv", ["id", "prediction"])
        self.assertEqual(list(rows), ["h2", "h1"])
        self.assertTrue(all(row["prediction"] == "True" for row in rows.values()))

    def test_real_changed_model_has_comparable_oof(self):
        first = self.train("baseline")
        self.candidate.write_text("from sklearn.dummy import DummyRegressor\n"
                                  "def build_model(seed, task): return DummyRegressor()\n")
        second = self.train("changed")
        a = load_result(first / "evaluation/result.json")
        b = load_result(second / "evaluation/result.json")
        result = compare(a, b, 0.0)
        self.assertIn("score", result["baseline"])
        self.assertGreater(b["score"]["value"], a["score"]["value"])
        self.assertNotEqual(adapter.read_json(first / "manifest.json")["files"]["candidate.py"],
                            adapter.read_json(second / "manifest.json")["files"]["candidate.py"])

    def test_frozen_copy_survives_source_changes_and_confirmation_scores(self):
        frozen = self.frozen()
        self.candidate.write_text("raise RuntimeError('live source must not load')\n")
        (self.root / "run/models/fold-0.joblib").write_bytes(b"changed live run")
        data, truth = self.holdout()
        report = adapter.deliver(frozen, data, self.root / "confirmed", truth=truth)
        self.assertLess(report["score"]["value"], 1e-12)
        result = adapter.read_json(self.root / "confirmed/evaluation/result.json")
        self.assertEqual(result["evaluation"]["stage"], "confirmation")

    def test_submission_order_schema_and_portable_frozen_model(self):
        import shutil
        frozen = self.frozen()
        moved = self.root / "moved"
        shutil.move(frozen, moved)
        data, _ = self.holdout()
        sample = self.root / "sample.csv"
        adapter.save_csv(sample, ["id", "prediction"], [("h1", 0), ("h2", 0)])
        adapter.deliver(moved, data, self.root / "final", sample_submission=sample)
        header, rows = adapter.csv_rows(self.root / "final/submission.csv", ["id", "prediction"])
        self.assertEqual(header, ["id", "prediction"])
        self.assertEqual(list(rows), ["h1", "h2"])
        self.assertAlmostEqual(float(rows["h1"]["prediction"]), 44)

    def custom_model_run(self, name, offset, class_name="CustomRegressor", import_guard=""):
        self.candidate.write_text(
            "import numpy as np\n"
            "from sklearn.base import BaseEstimator, RegressorMixin\n"
            "from sklearn.pipeline import make_pipeline\n"
            "from sklearn.preprocessing import FunctionTransformer\n"
            f"OFFSET = {offset}\n"
            "def transform(x): return x + OFFSET\n"
            f"class {class_name}(RegressorMixin, BaseEstimator):\n"
            "    def fit(self, x, y): self.fitted_ = True; return self\n"
            "    def predict(self, x): return x[:, 0] + OFFSET\n"
            f"def build_model(seed, task): return make_pipeline(FunctionTransformer(transform), {class_name}())\n"
            + import_guard)
        return self.train(name)

    def test_saved_runs_isolate_same_named_custom_classes_functions_and_globals(self):
        import numpy as np

        first = self.custom_model_run("first", 1)
        second = self.custom_model_run("second", 100)
        sentinel = types.ModuleType("competition_candidate")
        with patch.dict(sys.modules, {"competition_candidate": sentinel}):
            left, right = adapter.SavedTabularRun(first), adapter.SavedTabularRun(second)
            a = left.load_model("0")
            b = right.load_model("0")
            self.assertIs(sys.modules["competition_candidate"], sentinel)
            for _ in range(2):
                self.assertEqual(a.predict(np.array([[14.0]])).tolist(), [16])
                self.assertEqual(b.predict(np.array([[14.0]])).tolist(), [214])
                self.assertEqual(a[:-1].transform(np.array([[14.0]])).tolist(), [[15]])
                self.assertEqual(b[:-1].transform(np.array([[14.0]])).tolist(), [[114]])
            self.assertEqual(left.load_model("1").predict(np.array([[14.0]])).tolist(), [16])
            self.assertIs(sys.modules["competition_candidate"], sentinel)

    def test_saved_runs_load_different_custom_classes_without_manual_module_registration(self):
        import numpy as np

        first = self.custom_model_run("first", 1, "FirstRegressor")
        second = self.custom_model_run("second", 2, "SecondRegressor")
        with patch.dict(sys.modules):
            sys.modules.pop("competition_candidate", None)
            left, right = adapter.SavedTabularRun(first), adapter.SavedTabularRun(second)
            a, b = left.load_model("0"), right.load_model("0")
            self.assertNotIn("competition_candidate", sys.modules)
            self.assertEqual(a.predict(np.array([[14.0]])).tolist(), [16])
            self.assertEqual(b.predict(np.array([[14.0]])).tolist(), [18])

    def test_saved_model_reading_does_not_fit_or_rewrite_source_artifacts(self):
        import numpy as np
        from sklearn.pipeline import Pipeline

        run = self.custom_model_run("custom", 3)
        before = {str(path): path.read_bytes() for path in run.rglob("*") if path.is_file()}
        with patch.object(Pipeline, "fit", side_effect=AssertionError("Saved analysis must not fit")):
            saved = adapter.SavedTabularRun(run)
            self.assertEqual(saved.load_model("0").predict(np.array([[14.0]])).tolist(), [20])
        self.assertEqual(before, {str(path): path.read_bytes() for path in run.rglob("*") if path.is_file()})

    def test_saved_loader_rechecks_source_and_model_after_open_before_execution(self):
        run = self.custom_model_run("custom", 1)
        saved = adapter.SavedTabularRun(run)
        for name in ["candidate.py", saved.fit["folds"][0]["model"]]:
            path = run / name
            original = path.read_bytes()
            path.write_bytes(original + b"\nchanged")
            with self.subTest(name=name), patch("joblib.load", side_effect=AssertionError("Must reject before load")):
                with self.assertRaisesRegex(adapter.TrainingFailure, "Artifact changed"):
                    saved.load_model("0")
            path.write_bytes(original)

    def test_saved_loader_restores_alias_when_unpickling_fails(self):
        run = self.custom_model_run("custom", 1)
        sentinel = types.ModuleType("competition_candidate")
        with patch.dict(sys.modules, {"competition_candidate": sentinel}):
            saved = adapter.SavedTabularRun(run)
            with patch("joblib.load", side_effect=RuntimeError("broken pickle")):
                with self.assertRaisesRegex(RuntimeError, "broken pickle"):
                    saved.load_model("0")
            self.assertIs(sys.modules["competition_candidate"], sentinel)

    def test_saved_loader_cleans_up_failed_candidate_import(self):
        guard = ("if __name__.startswith('competition_saved_'):\n"
                 "    raise RuntimeError('candidate import failed')\n")
        run = self.custom_model_run("custom", 1, import_guard=guard)
        sentinel = types.ModuleType("competition_candidate")
        modules_before = set(sys.modules)
        with patch.dict(sys.modules, {"competition_candidate": sentinel}):
            saved = adapter.SavedTabularRun(run)
            with self.assertRaisesRegex(RuntimeError, "candidate import failed"):
                saved.load_model("0")
            self.assertIs(sys.modules["competition_candidate"], sentinel)
            self.assertFalse({name for name in set(sys.modules) - modules_before
                              if name.startswith("competition_saved_")})

    def test_saved_loader_rejects_wrong_environment_and_unknown_fold(self):
        run = self.custom_model_run("custom", 1)
        with patch.object(adapter, "environment", return_value={"python": "incompatible"}):
            with self.assertRaisesRegex(adapter.TrainingFailure, "recorded.*environment"):
                adapter.SavedTabularRun(run)
        saved = adapter.SavedTabularRun(run)
        with patch("joblib.load", side_effect=AssertionError("Unknown fold must not load")):
            with self.assertRaisesRegex(adapter.TrainingFailure, "Unknown saved fold"):
                saved.load_model("missing")

    def test_submission_inverse_follows_fold_average_and_confirmation_keeps_target_scale(self):
        import shutil
        from sklearn.dummy import DummyRegressor

        self.candidate.write_text("from sklearn.dummy import DummyRegressor\n"
                                  "def build_model(seed, task):\n"
                                  "    return DummyRegressor(strategy='constant', constant=seed-99)\n")
        run = self.train()
        original_manifest = (run / "manifest.json").read_bytes()
        data, _ = self.holdout()
        adapter.save_csv(self.root / "log-truth.csv", ["id", "target"], [("h1", 2), ("h2", 2)])
        sample = self.root / "sample.csv"
        adapter.save_csv(sample, ["id", "SalePrice"], [("h1", 0), ("h2", 0)])
        with patch.object(DummyRegressor, "fit", side_effect=AssertionError("Delivery must not fit")):
            for transform in ["exp", "expm1"]:
                with self.subTest(transform=transform):
                    frozen = self.root / ("frozen-" + transform)
                    frozen_report = adapter.freeze(run, frozen, "Fixed delivery rule",
                                                   submission_column="SalePrice", inverse_transform=transform)
                    moved = self.root / ("moved-" + transform)
                    shutil.move(frozen, moved)
                    output = self.root / ("final-" + transform)
                    report = adapter.deliver(moved, data, output, sample_submission=sample)
                    header, rows = adapter.csv_rows(output / "submission.csv", ["id", "SalePrice"])
                    self.assertEqual(header, ["id", "SalePrice"])
                    self.assertEqual(list(rows), ["h1", "h2"])
                    self.assertAlmostEqual(float(rows["h1"]["SalePrice"]), getattr(math, transform)(2))
                    _, raw_rows = adapter.csv_rows(output / "predictions.csv", ["id", "prediction"])
                    self.assertEqual(float(raw_rows["h1"]["prediction"]), 2)
                    self.assertEqual(report["submission"], frozen_report["submission"])
                    self.assertEqual(Path(report["submission_path"]), output / "submission.csv")
                    self.assertEqual(report["submission_hash"], adapter.byte_hash((output / "submission.csv").read_bytes()))
                    self.assertEqual(report["prediction_hash"], report["submission_hash"])
                    self.assertEqual(report["raw_prediction_hash"], adapter.byte_hash((output / "predictions.csv").read_bytes()))
                    self.assertNotEqual(report["raw_prediction_hash"], report["submission_hash"])
                    confirmed = self.root / ("confirmed-" + transform)
                    confirmation = adapter.deliver(moved, data, confirmed, truth=self.root / "log-truth.csv")
                    self.assertEqual(confirmation["score"]["value"], 0)
                    result = load_result(confirmed / "evaluation/result.json")
                    self.assertEqual(result["candidate_hash"], confirmation["raw_prediction_hash"])
                    self.assertIsNone(confirmation["submission_path"])
        self.assertEqual((run / "manifest.json").read_bytes(), original_manifest)

    def test_submission_identity_rename_through_cli(self):
        run = self.train()
        frozen, output = self.root / "frozen", self.root / "final"
        data, _ = self.holdout()
        sample = self.root / "sample.csv"
        adapter.save_csv(sample, ["id", "SalePrice"], [("h1", 0), ("h2", 0)])
        for arguments in [
                ["freeze", "--run", str(run), "--decision-rule", "fixed", "--submission-column", "SalePrice",
                 "--inverse-transform", "identity", "--output-dir", str(frozen)],
                ["predict", "--frozen", str(frozen), "--data", str(data), "--sample-submission", str(sample),
                 "--output-dir", str(output)]]:
            with patch.object(sys, "argv", ["tabular_training.py", *arguments]), contextlib.redirect_stdout(io.StringIO()) as stream:
                self.assertEqual(adapter.main(), 0)
            self.assertIn(json.loads(stream.getvalue())["status"], {"frozen", "success"})
        _, rows = adapter.csv_rows(output / "submission.csv", ["id", "SalePrice"])
        self.assertAlmostEqual(float(rows["h1"]["SalePrice"]), 44)

    def test_legacy_frozen_manifest_preserves_identity_delivery(self):
        frozen = self.frozen()
        manifest = adapter.read_json(frozen / "manifest.json")
        del manifest["submission"]
        del manifest["seal"]
        manifest["seal"] = adapter.object_hash(manifest)
        (frozen / "manifest.json").write_text(json.dumps(manifest))
        data, _ = self.holdout()
        sample = self.root / "sample.csv"
        adapter.save_csv(sample, ["id", "prediction"], [("h1", 0), ("h2", 0)])
        output = self.root / "final"
        report = adapter.deliver(frozen, data, output, sample_submission=sample)
        _, rows = adapter.csv_rows(output / "submission.csv", ["id", "prediction"])
        self.assertAlmostEqual(float(rows["h1"]["prediction"]), 44)
        self.assertEqual(report["submission"]["inverse_transform"], "identity")

    def test_submission_contract_tampering_rejected_before_model_load(self):
        frozen = self.frozen()
        manifest = adapter.read_json(frozen / "manifest.json")
        manifest["submission"]["inverse_transform"] = "exp"
        (frozen / "manifest.json").write_text(json.dumps(manifest))
        data, _ = self.holdout()
        with patch("joblib.load", side_effect=AssertionError("Must reject before model load")):
            with self.assertRaisesRegex(adapter.TrainingFailure, "seal"):
                adapter.deliver(frozen, data, self.root / "failed")
        self.assertFalse((self.root / "failed").exists())

    def test_invalid_submission_contract_rejected_before_freeze(self):
        run = self.train()
        for kwargs in [{"submission_column": " "}, {"submission_column": "id"}, {"inverse_transform": "log"}]:
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(adapter.TrainingFailure, "Submission"):
                adapter.freeze(run, self.root / "invalid-freeze", "fixed", **kwargs)
        self.assertFalse((self.root / "invalid-freeze").exists())

    def test_binary_submission_cannot_inverse_transform_probabilities(self):
        self.data.write_text("id,x,target,group\n" + "".join(
            f"{i},{i},{i % 2},{i // 2}\n" for i in range(12)))
        self.spec.update(task="binary", metric="binary_log_loss")
        self.protocol.write_text(json.dumps(self.spec))
        self.candidate.write_text("from sklearn.dummy import DummyClassifier\n"
                                  "def build_model(seed, task): return DummyClassifier(strategy='prior')\n")
        run = self.train()
        with self.assertRaisesRegex(adapter.TrainingFailure, "only to regression"):
            adapter.freeze(run, self.root / "invalid-freeze", "fixed", inverse_transform="exp")
        self.assertFalse((self.root / "invalid-freeze").exists())

    def test_submission_transform_rejects_overflow_and_underflow_without_output(self):
        from sklearn.dummy import DummyRegressor

        self.candidate.write_text("from sklearn.dummy import DummyRegressor\n"
                                  "def build_model(seed, task): return DummyRegressor(strategy='constant', constant=1000)\n")
        run = self.train()
        frozen = self.root / "frozen"
        adapter.freeze(run, frozen, "fixed", submission_column="SalePrice", inverse_transform="exp")
        data, _ = self.holdout()
        sample = self.root / "sample.csv"
        adapter.save_csv(sample, ["id", "SalePrice"], [("h1", 0), ("h2", 0)])
        for value in [1000, -1000]:
            with self.subTest(value=value), patch.object(DummyRegressor, "predict", return_value=[value, value]):
                with self.assertRaisesRegex(adapter.TrainingFailure, "inverse transform"):
                    adapter.deliver(frozen, data, self.root / "failed", sample_submission=sample)
                self.assertFalse((self.root / "failed").exists())

    def test_official_sample_mismatch_fails_before_model_load(self):
        run = self.train()
        frozen = self.root / "frozen"
        adapter.freeze(run, frozen, "fixed", submission_column="SalePrice", inverse_transform="exp")
        data, _ = self.holdout()
        sample = self.root / "sample.csv"
        for text in ["id,prediction\nh1,0\nh2,0\n", "id,SalePrice\nh1,0\nmissing,0\n",
                     "id,SalePrice\nh1,0\nh1,0\n"]:
            sample.write_text(text)
            with self.subTest(text=text), patch("joblib.load", side_effect=AssertionError("Must reject before model load")):
                with self.assertRaises(adapter.TrainingFailure):
                    adapter.deliver(frozen, data, self.root / "failed", sample_submission=sample)
        self.assertFalse((self.root / "failed").exists())

    def test_model_tamper_rejected_before_loading(self):
        frozen = self.frozen()
        (frozen / "models/fold-0.joblib").write_bytes(b"not trusted")
        data, truth = self.holdout()
        with self.assertRaisesRegex(adapter.TrainingFailure, "Artifact changed"):
            adapter.deliver(frozen, data, self.root / "failed", truth=truth)
        self.assertFalse((self.root / "failed").exists())

    def test_confirmation_cannot_reuse_development_groups(self):
        frozen = self.frozen()
        data, truth = self.holdout()
        data.write_text("id,x,group\nh1,14,0\nh2,15,new\n")
        with self.assertRaisesRegex(adapter.TrainingFailure, "groups overlap"):
            adapter.deliver(frozen, data, self.root / "failed", truth=truth)

    def test_sample_submission_rejects_wrong_ids_or_columns(self):
        frozen = self.frozen()
        data, _ = self.holdout()
        sample = self.root / "sample.csv"
        for text in ["id,prediction\nh1,0\nmissing,0\n", "prediction,id\n0,h1\n0,h2\n"]:
            sample.write_text(text)
            with self.subTest(text=text), self.assertRaisesRegex(adapter.TrainingFailure, "Sample submission"):
                adapter.deliver(frozen, data, self.root / "failed", sample_submission=sample)
        self.assertFalse((self.root / "failed").exists())

    def test_only_completed_training_runs_can_be_frozen(self):
        run = self.train()
        (run / "oof.csv").write_text("id,prediction\nwrong,0\n")
        with self.assertRaisesRegex(adapter.TrainingFailure, "Artifact changed"):
            adapter.freeze(run, self.root / "invalid-freeze", "fixed rule")
        self.assertFalse((self.root / "invalid-freeze").exists())

    def test_missing_oof_rows_and_duplicate_validation_rejected_before_fit(self):
        for mode in ["missing", "duplicate"]:
            spec = copy.deepcopy(self.spec)
            if mode == "missing":
                spec["expected_oof_ids"].pop()
            else:
                spec["folds"].append({**spec["folds"][0], "id": "duplicate"})
            self.protocol.write_text(json.dumps(spec))
            with self.subTest(mode=mode), self.assertRaises(adapter.TrainingFailure):
                self.train(mode)
            self.assertFalse((self.root / mode).exists())

    def test_time_oof_allows_declared_warmup_and_rejects_future_training(self):
        spec = copy.deepcopy(self.spec)
        spec["split"] = {"kind": "time", "time_column": "time", "time_format": "number"}
        spec["folds"] = [{"id": "future", "seed": 1, "train_ids": [str(i) for i in range(8)],
                          "validation_ids": [str(i) for i in range(8, 12)]}]
        spec["expected_oof_ids"] = spec["folds"][0]["validation_ids"]
        self.protocol.write_text(json.dumps(spec))
        run = self.train()
        self.assertEqual(adapter.read_json(run / "evaluation/result.json")["evaluation"]["completed_cases"], 4)
        spec["folds"][0]["train_ids"], spec["folds"][0]["validation_ids"] = (
            spec["folds"][0]["validation_ids"], spec["folds"][0]["train_ids"])
        spec["expected_oof_ids"] = spec["folds"][0]["validation_ids"]
        self.protocol.write_text(json.dumps(spec))
        with self.assertRaisesRegex(adapter.TrainingFailure, "Evaluation precedes"):
            self.train("bad")

    def test_binary_real_fit(self):
        self.data.write_text("id,x,target,group\n" + "".join(
            f"{i},{i},{i % 2},{i // 2}\n" for i in range(12)))
        self.spec.update(task="binary", metric="binary_log_loss")
        self.protocol.write_text(json.dumps(self.spec))
        self.candidate.write_text("from sklearn.linear_model import LogisticRegression\n"
                                  "def build_model(seed, task): return LogisticRegression(random_state=seed)\n")
        run = self.train()
        result = adapter.read_json(run / "evaluation/result.json")
        self.assertTrue(result["valid"])
        self.assertGreater(result["score"]["value"], 0)

    def test_cli_failure_is_nonzero_and_no_success_manifest(self):
        self.candidate.write_text("def build_model(seed, task): raise RuntimeError('broken candidate')\n")
        output = self.root / "failed"
        process = subprocess.run([sys.executable, str(SCRIPTS / "tabular_training.py"), "train", "--data", str(self.data),
                                  "--protocol", str(self.protocol), "--candidate", str(self.candidate),
                                  "--output-dir", str(output)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertIn("broken candidate", process.stderr)
        self.assertFalse((output / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
