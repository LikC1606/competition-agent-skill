from __future__ import annotations

import importlib
import itertools
import json
import math
import pathlib
import random
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
pilot = importlib.import_module("algorithm_route_pilot")


class AlgorithmRoutePilotTests(unittest.TestCase):
    def test_tour_validity_and_score_agree_with_direct_geometry(self) -> None:
        points = [[0, 0], [1, 0], [1, 1], [0, 1]]
        matrix = pilot.distances(points)
        self.assertEqual(pilot.tour_length(matrix, [0, 1, 2, 3]), 4)
        for route in [[0, 1, 2], [0, 1, 1, 3], [0, 1, 2, 4], [False, 1, 2, 3]]:
            with self.subTest(route=route), self.assertRaises(ValueError):
                pilot.tour_length(matrix, route)

    def test_edge_exchange_removes_crossing_and_reaches_exact_square_optimum(self) -> None:
        matrix = pilot.distances([[0, 0], [1, 0], [1, 1], [0, 1]])
        initial = [0, 2, 1, 3]
        route, work = pilot.improve(initial, matrix, "two_opt", 100)
        optimum = min(pilot.tour_length(matrix, list(order)) for order in itertools.permutations(range(4)))
        self.assertEqual(pilot.tour_length(matrix, route), optimum)
        self.assertEqual(optimum, 4)
        self.assertGreater(work["accepted"], 0)
        self.assertEqual(initial, [0, 2, 1, 3])

    def test_both_neighborhoods_preserve_cycles_reduce_actual_score_and_respect_caps(self) -> None:
        rng = random.Random(23)
        for count, move, limit in itertools.product([6, 12, 25], ["two_opt", "two_opt_rotate", "relocate"], [0, 7, 3000]):
            points = [[rng.random(), rng.random()] for _ in range(count)]
            matrix, initial = pilot.distances(points), list(range(count))
            rng.shuffle(initial)
            before = list(initial)
            route, work = pilot.improve(initial, matrix, move, limit)
            with self.subTest(count=count, move=move, limit=limit):
                self.assertEqual(initial, before)
                self.assertEqual(sorted(route), list(range(count)))
                self.assertLessEqual(work["checks"], limit)
                self.assertLessEqual(work["accepted"], work["checks"])
                self.assertLessEqual(pilot.tour_length(matrix, route), pilot.tour_length(matrix, before) + 1e-10)

    def test_constructors_and_composite_recipes_are_deterministic_complete_solutions(self) -> None:
        points = [[0, 0], [1, 0], [1, 1], [0, 1], [0.1, 0.3], [0.9, 0.7]]
        for constructor in ["nearest", "farthest_insertion", "mst_preorder"]:
            recipe = {"constructor": constructor, "start": 0, "moves": ["two_opt", "relocate", "two_opt"]}
            first, work = pilot.solve(points, recipe)
            second, _ = pilot.solve(points, recipe)
            with self.subTest(constructor=constructor):
                self.assertEqual(first, second)
                self.assertEqual(sorted(first), list(range(len(points))))
                direct = math.fsum(math.dist(points[a], points[b]) for a, b in zip(first, first[1:] + first[:1]))
                self.assertAlmostEqual(work["length"], direct)
                self.assertLessEqual(sum(row["checks"] for row in work["work"]), 3 * pilot.MOVE_LIMIT)

    def test_progress_receipts_score_actual_tours_and_distinguish_cap_from_local_stop(self) -> None:
        points = [[0, 0], [1, 0], [1, 1], [0, 1]]
        matrix = pilot.distances(points)
        crossed = [0, 2, 1, 3]
        capped, cap_work = pilot.improve(crossed, matrix, "two_opt", 1, trace=True)
        complete, complete_work = pilot.improve(crossed, matrix, "two_opt", 10, trace=True)
        self.assertEqual(cap_work["stop_reason"], "work_cap")
        self.assertEqual(cap_work["last_accepted_check"], 1)
        self.assertEqual(complete_work["stop_reason"], "neighborhood_exhausted")
        self.assertEqual(capped, complete)
        self.assertAlmostEqual(pilot.tour_length(matrix, complete), 4)
        for work in (cap_work, complete_work):
            trace = work["progress"]
            self.assertEqual(trace[0]["checks"], 0)
            self.assertEqual(trace[-1]["checks"], work["checks"])
            self.assertEqual(trace[-1]["accepted"], work["accepted"])
            for checkpoint in trace:
                tour = checkpoint["route"]
                direct = math.fsum(math.dist(points[a], points[b]) for a, b in zip(tour, tour[1:] + tour[:1]))
                self.assertAlmostEqual(checkpoint["length"], direct)
            self.assertTrue(all(a["checks"] < b["checks"] and a["length"] >= b["length"] - 1e-12
                                for a, b in zip(trace, trace[1:])))

    def test_flat_capped_search_is_not_reported_as_converged(self) -> None:
        matrix = pilot.distances([[0, 0], [1, 0], [1, 1], [0, 1]])
        for limit, reason in [(0, "work_cap"), (1, "work_cap"), (10, "neighborhood_exhausted")]:
            route, work = pilot.improve([0, 1, 2, 3], matrix, "two_opt", limit, trace=True)
            self.assertEqual(work["accepted"], 0)
            self.assertIsNone(work["last_accepted_check"])
            self.assertEqual(work["stop_reason"], reason)
            self.assertEqual(route, [0, 1, 2, 3])

    def test_work_can_be_reallocated_without_exceeding_the_total_recipe_cap(self) -> None:
        points = [[0, 0], [1, 0], [1, 1], [0, 1]]
        recipe = {"constructor": "nearest", "start": 0, "moves": ["two_opt"],
                  "move_limits": [3 * pilot.MOVE_LIMIT], "trace": True}
        route, receipt = pilot.solve(points, recipe)
        self.assertAlmostEqual(receipt["length"], 4)
        self.assertEqual(sorted(route), [0, 1, 2, 3])
        for invalid in [[], [-1], [True], [3 * pilot.MOVE_LIMIT + 1]]:
            with self.subTest(limits=invalid), self.assertRaises(ValueError):
                pilot.solve(points, {**recipe, "move_limits": invalid})

    def test_rotating_search_covers_the_entire_neighborhood_before_claiming_exhaustion(self) -> None:
        rng = random.Random(7321)
        for _ in range(8):
            points = [[rng.random(), rng.random()] for _ in range(9)]
            matrix = pilot.distances(points)
            initial = list(range(len(points)))
            rng.shuffle(initial)
            route, work = pilot.improve(initial, matrix, "two_opt_rotate", 10000, trace=True)
            again, _ = pilot.improve(initial, matrix, "two_opt_rotate", 10000, trace=True)
            self.assertEqual(route, again)
            self.assertEqual(work["stop_reason"], "neighborhood_exhausted")
            final = pilot.tour_length(matrix, route)
            for left in range(len(route) - 2):
                for right in range(left + 2, len(route)):
                    if left == 0 and right == len(route) - 1:
                        continue
                    neighbor = route[:left + 1] + list(reversed(route[left + 1:right + 1])) + route[right + 1:]
                    self.assertGreaterEqual(pilot.tour_length(matrix, neighbor), final - 1e-10)

    def test_feedback_spends_the_third_trial_only_after_the_declared_development_trigger(self) -> None:
        for cap, sizes in [(0, [6]), (pilot.MOVE_LIMIT, [160])]:
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as temporary, mock.patch.object(pilot, "MOVE_LIMIT", cap):
                output = pathlib.Path(temporary) / "pilot"
                summary = pilot.run(output, sizes, [8], 1, "feedback_search")
                contract = json.loads((output / "task-contract.json").read_text())
                control = json.loads((output / "development-restart-control/result.json").read_text())
                triggered = any(row["work"][0]["stop_reason"] == "work_cap"
                                and (row["work"][0]["last_accepted_check"] or 0) > .75 * 3 * cap
                                for row in control["cases"])
                self.assertEqual(triggered, cap > 0)  # These fixtures exercise both branches.
                self.assertEqual(summary["rescue_triggered"], triggered)
                self.assertEqual(summary["distinct_development_recipes"], 3 if triggered else 2)
                self.assertEqual(contract["slots_per_arm"], 3)
                ledger = [json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()]
                decision = next(i for i, event in enumerate(ledger) if event["event"] == "feedback_decision")
                frozen = next(i for i, event in enumerate(ledger) if event["event"] == "shortlist_frozen")
                if triggered:
                    planned = next(i for i, event in enumerate(ledger)
                                   if event["event"] == "planned" and event["candidate"] == "rotating-search")
                    self.assertLess(decision, planned)
                    self.assertLess(planned, frozen)
                    changed = json.loads((output / "development-rotating-search/recipe.json").read_text())
                    original = json.loads((output / "development-restart-control/recipe.json").read_text())
                    self.assertEqual({**original, "moves": ["two_opt_rotate"]}, changed)
                    lesson = json.loads((output / "development-lesson.json").read_text())
                    changed_score = json.loads((output / "development-rotating-search/result.json").read_text())["score"]
                    base_score = json.loads((output / "development-baseline/result.json").read_text())["score"]
                    self.assertEqual(lesson["incumbent_improved"], changed_score < base_score)
                    self.assertAlmostEqual(lesson["observation"]["improvement"], control["score"] - changed_score)
                else:
                    self.assertFalse((output / "development-rotating-search").exists())
                    self.assertFalse((output / "development-lesson.json").exists())
                shortlist = json.loads((output / "shortlist.json").read_text())
                confirmed = {event["candidate"] for event in ledger if event.get("stage") == "confirmation"}
                self.assertEqual(confirmed, set(shortlist["finalists"]))
                self.assertTrue(all(i > frozen for i, event in enumerate(ledger) if event.get("stage") == "confirmation"))

    def test_investment_study_counts_shared_trials_and_confirms_only_frozen_pipelines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "pilot"
            summary = pilot.run(output, [6], [8], 1, "route_investment")
            self.assertEqual(summary["distinct_development_recipes"], 8)
            for arm in summary["arms"].values():
                self.assertEqual(len(arm["trials"]), 6)
            shared = set.intersection(*(set(arm["trials"]) for arm in summary["arms"].values()))
            self.assertEqual(len(shared), 4)
            complete_arm = summary["arms"]["mature_routes"]
            pipelines = [json.loads((output / f"development-{name}/recipe.json").read_text())
                         for name in complete_arm["trials"] if name not in {"baseline", "farthest_insertion", "mst_preorder"}]
            self.assertEqual({recipe["constructor"] for recipe in pipelines},
                             {"nearest", "farthest_insertion", "mst_preorder"})
            self.assertTrue(all(recipe["move_limits"] == [3 * pilot.MOVE_LIMIT] for recipe in pipelines))
            ledger = [json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()]
            self.assertEqual(sum(event["event"] == "planned" for event in ledger), 8)
            frozen = next(i for i, event in enumerate(ledger) if event["event"] == "shortlist_frozen")
            self.assertTrue(all(i > frozen for i, event in enumerate(ledger) if event.get("stage") == "confirmation"))
            shortlist = json.loads((output / "shortlist.json").read_text())
            confirmed = {event["candidate"] for event in ledger if event.get("stage") == "confirmation"}
            self.assertEqual(confirmed, set(shortlist["finalists"]))
            for candidate, expected_hash in shortlist["finalists"].items():
                recipe = json.loads((output / f"confirmation-{candidate}/recipe.json").read_text())
                self.assertEqual(pilot.digest(recipe), expected_hash)

    def test_fixtures_reproduce_and_stages_have_distinct_seeds_and_ids(self) -> None:
        development = pilot.fixtures([6], 1, 4100, "development")
        confirmation = pilot.fixtures([6], 1, 9100, "confirmation")
        self.assertEqual(development, pilot.fixtures([6], 1, 4100, "development"))
        self.assertEqual({case["regime"] for case in development}, {"uniform", "clusters", "elongated"})
        self.assertTrue({case["id"] for case in development}.isdisjoint(case["id"] for case in confirmation))
        self.assertTrue({case["seed"] for case in development}.isdisjoint(case["seed"] for case in confirmation))

    def test_end_to_end_budget_freeze_recipe_reuse_and_overwrite_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "pilot"
            summary = pilot.run(output, [6], [8], 1)
            self.assertEqual(summary["distinct_development_recipes"], 11)
            for arm in summary["arms"].values():
                self.assertEqual(len(arm["trials"]), 6)
            ledger = [json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()]
            frozen = next(i for i, event in enumerate(ledger) if event["event"] == "shortlist_frozen")
            self.assertEqual(sum(event["event"] == "planned" for event in ledger), 11)
            self.assertTrue(all(i > frozen for i, event in enumerate(ledger)
                                if event.get("stage") == "confirmation"))
            shortlist = json.loads((output / "shortlist.json").read_text())
            for candidate, expected_hash in shortlist["finalists"].items():
                dev = json.loads((output / f"development-{candidate}/recipe.json").read_text())
                confirmed = json.loads((output / f"confirmation-{candidate}/recipe.json").read_text())
                self.assertEqual(dev, confirmed)
                self.assertEqual(pilot.digest(confirmed), expected_hash)
            original = (output / "summary.json").read_bytes()
            with self.assertRaises(FileExistsError):
                pilot.run(output, [6], [8], 1)
            self.assertEqual((output / "summary.json").read_bytes(), original)

    def test_invalid_sizes_and_repository_output_are_rejected_before_creating_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for sizes, confirm, repetitions in [([5], [8], 1), ([6, 6], [8], 1), ([6], [501], 1), ([6], [8], 6)]:
                output = pathlib.Path(temporary) / "invalid"
                with self.assertRaises(ValueError):
                    pilot.run(output, sizes, confirm, repetitions)
                self.assertFalse(output.exists())
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            pilot.run(pilot.REPOSITORY / "forbidden-pilot-output", [6], [8], 1)


if __name__ == "__main__":
    unittest.main()
