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
        for count, move, limit in itertools.product([6, 12, 25], ["two_opt", "relocate"], [0, 7, 3000]):
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
