#!/usr/bin/env python3
"""Compare parameter-only search with route exploration on generated Euclidean tours.

This is a scripted integration example, not an autonomous-agent benchmark. Both
arms have six development candidate slots; their actual compute costs differ.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import pathlib
import platform
import random
import time


REPOSITORY = pathlib.Path(__file__).resolve().parents[1]
MOVE_LIMIT = 50000


def save(path: pathlib.Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def distances(points: list[list[float]]) -> list[list[float]]:
    return [[math.hypot(x - u, y - v) for u, v in points] for x, y in points]


def tour_length(matrix: list[list[float]], route: list[int]) -> float:
    if (len(route) != len(matrix) or any(type(vertex) is not int for vertex in route)
            or set(route) != set(range(len(matrix)))):
        raise ValueError("A tour must visit every vertex exactly once")
    return math.fsum(matrix[a][b] for a, b in zip(route, route[1:] + route[:1]))


def nearest(matrix: list[list[float]], start: int) -> list[int]:
    remaining = set(range(len(matrix))) - {start}
    route = [start]
    while remaining:
        vertex = min(remaining, key=lambda value: (matrix[route[-1]][value], value))
        route.append(vertex)
        remaining.remove(vertex)
    return route


def farthest_insertion(matrix: list[list[float]]) -> list[int]:
    route, remaining = [0], set(range(1, len(matrix)))
    closest = [row[0] for row in matrix]
    while remaining:
        vertex = min(remaining, key=lambda value: (-closest[value], value))
        edge = min(range(len(route)), key=lambda i: (
            matrix[route[i]][vertex] + matrix[vertex][route[(i + 1) % len(route)]]
            - matrix[route[i]][route[(i + 1) % len(route)]], i))
        route.insert(edge + 1, vertex)
        remaining.remove(vertex)
        for value in remaining:
            closest[value] = min(closest[value], matrix[value][vertex])
    return route


def mst_preorder(matrix: list[list[float]]) -> list[int]:
    count = len(matrix)
    costs, parents, remaining = [math.inf] * count, [-1] * count, set(range(count))
    costs[0] = 0
    children = [[] for _ in matrix]
    while remaining:
        vertex = min(remaining, key=lambda value: (costs[value], value))
        remaining.remove(vertex)
        if parents[vertex] >= 0:
            children[parents[vertex]].append(vertex)
        for value in remaining:
            if matrix[vertex][value] < costs[value]:
                costs[value], parents[value] = matrix[vertex][value], vertex
    route, stack = [], [0]
    while stack:
        vertex = stack.pop()
        route.append(vertex)
        stack.extend(reversed(sorted(children[vertex])))
    return route


def improve(route: list[int], matrix: list[list[float]], move: str,
            limit: int) -> tuple[list[int], dict[str, int]]:
    route, checks, accepted = list(route), 0, 0
    count = len(route)
    while checks < limit:
        changed = False
        for i, j in itertools.product(range(count), repeat=2):
            if move == "two_opt":
                if j < i + 2 or (i == 0 and j == count - 1):
                    continue
                a, b, c, d = route[i], route[(i + 1) % count], route[j], route[(j + 1) % count]
                delta = matrix[a][c] + matrix[b][d] - matrix[a][b] - matrix[c][d]
            elif move == "relocate":
                if j in {i, (i - 1) % count}:
                    continue
                before, vertex, after = route[(i - 1) % count], route[i], route[(i + 1) % count]
                a, b = route[j], route[(j + 1) % count]
                delta = (matrix[before][after] + matrix[a][vertex] + matrix[vertex][b]
                         - matrix[before][vertex] - matrix[vertex][after] - matrix[a][b])
            else:
                raise ValueError("Unknown neighborhood")
            checks += 1
            if delta < -1e-12:
                if move == "two_opt":
                    route[i + 1:j + 1] = reversed(route[i + 1:j + 1])
                else:
                    vertex = route.pop(i)
                    route.insert(j + 1 if j < i else j, vertex)
                accepted += 1
                changed = True
                break
            if checks == limit:
                break
        if not changed:
            break
    return route, {"checks": checks, "accepted": accepted}


def solve(points: list[list[float]], recipe: dict) -> tuple[list[int], dict]:
    started = time.perf_counter()
    matrix = distances(points)
    constructor = recipe["constructor"]
    if constructor == "nearest":
        route = nearest(matrix, recipe["start"])
    elif constructor == "farthest_insertion":
        route = farthest_insertion(matrix)
    elif constructor == "mst_preorder":
        route = mst_preorder(matrix)
    else:
        raise ValueError("Unknown constructor")
    work = []
    for move in recipe["moves"]:
        route, receipt = improve(route, matrix, move, MOVE_LIMIT)
        work.append({"move": move, **receipt})
    score = tour_length(matrix, route)
    if sum(row["checks"] for row in work) > 3 * MOVE_LIMIT:
        raise ValueError("Candidate exceeded the declared move-check cap")
    return route, {"length": score, "seconds": time.perf_counter() - started, "work": work}


def fixtures(sizes: list[int], repetitions: int, seed_start: int, stage: str) -> list[dict]:
    cases = []
    for regime, size, repeat in itertools.product(["uniform", "clusters", "elongated"], sizes, range(repetitions)):
        seed = seed_start + len(cases)
        rng = random.Random(seed)
        points = []
        for _ in range(size):
            if regime == "clusters":
                center = rng.choice([(0.2, 0.2), (0.2, 0.8), (0.8, 0.2), (0.8, 0.8)])
                points.append([rng.gauss(center[0], 0.06), rng.gauss(center[1], 0.06)])
            else:
                points.append([rng.random() * (3 if regime == "elongated" else 1),
                               rng.random() * (0.3 if regime == "elongated" else 1)])
        cases.append({"id": f"{stage}-{regime}-{size}-{repeat}", "regime": regime, "seed": seed, "points": points})
    return cases


def run(output: pathlib.Path, sizes: list[int], confirmation_sizes: list[int], repetitions: int) -> dict:
    if (min(sizes + confirmation_sizes) < 6 or max(sizes + confirmation_sizes) > 500
            or len(set(sizes)) != len(sizes) or len(set(confirmation_sizes)) != len(confirmation_sizes)
            or not 1 <= repetitions <= 5):
        raise ValueError("Use distinct sizes between 6 and 500, with 1-5 repetitions per regime")
    output = output.resolve()
    if output == REPOSITORY or REPOSITORY in output.parents:
        raise ValueError("Keep generated fixtures and receipts outside the repository")
    output.mkdir(exist_ok=False)
    source = pathlib.Path(__file__).read_bytes()
    (output / "pilot-source.py").write_bytes(source)
    contract = {"metric": "mean_closed_tour_length", "direction": "minimize", "score_kind": "synthetic_proxy",
                "validity": "one closed permutation of every input vertex", "seed_development": 4100,
                "seed_confirmation": 9100, "sizes_development": sizes, "sizes_confirmation": confirmation_sizes,
                "repetitions_per_regime": repetitions, "slots_per_arm": 6, "shared_baseline_counts_in_both_arms": True,
                "max_distinct_development_recipes": 11, "max_move_checks_per_case": 3 * MOVE_LIMIT,
                "confirmation": "Freeze baseline and each arm's development winner before generating confirmation. "
                                "Deliver an arm's challenger only when it improves both phases, otherwise baseline.",
                "source_hash": hashlib.sha256(source).hexdigest(), "python": platform.python_version(),
                "limits": "Candidate counts and hard work caps match; actual compute, implementation effort, "
                          "and runtime differ. This is not an old/new skill or autonomous-agent experiment."}
    save(output / "task-contract.json", contract)
    development = fixtures(sizes, repetitions, 4100, "development")
    save(output / "development.json", development)
    results, recipes, arms = {}, {}, {"parameter_only": [], "route_search": []}

    def event(**fields: object) -> None:
        with (output / "trials.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(fields, allow_nan=False) + "\n")

    def evaluate(name: str, recipe: dict, cases: list[dict], stage: str) -> dict:
        directory = output / f"{stage}-{name}"
        directory.mkdir()
        save(directory / "recipe.json", recipe)
        started = time.perf_counter()
        rows = []
        for case in cases:
            route, receipt = solve(case["points"], recipe)
            # Independent scoring from coordinates, rather than the search's delta updates.
            direct = math.fsum(math.dist(case["points"][a], case["points"][b])
                               for a, b in zip(route, route[1:] + route[:1]))
            if not math.isclose(direct, receipt["length"], abs_tol=1e-10, rel_tol=1e-12):
                raise ValueError("Independent tour score mismatch")
            rows.append({"id": case["id"], "regime": case["regime"], "route": route, **receipt})
        result = {"candidate": name, "stage": stage, "recipe_hash": digest(recipe),
                  "data_hash": digest(cases), "candidate_hash": digest({"source": contract["source_hash"], "recipe": recipe}),
                  "valid": True, "score": math.fsum(row["length"] for row in rows) / len(rows),
                  "seconds": time.perf_counter() - started, "cases": rows}
        save(directory / "result.json", result)
        event(event="completed", candidate=name, stage=stage, score=result["score"],
              seconds=result["seconds"], result=str(directory / "result.json"), recipe_hash=digest(recipe))
        return result

    def trial(name: str, recipe: dict, arm: str, scope: str, parent: str | None,
              hypothesis: str, deferred: str) -> None:
        if len(arms[arm]) >= contract["slots_per_arm"] or len(results) >= 11:
            raise ValueError("Development trial budget exhausted")
        event(event="planned", candidate=name, arm=arm, route=recipe["constructor"], change_scope=scope,
              parent=parent, hypothesis=hypothesis, alternative_deferred=deferred,
              rejection_test="Full development mean length must improve or justify its route's next mechanism")
        recipes[name] = recipe
        results[name] = evaluate(name, recipe, development, "development")
        arms[arm].append(name)

    base = {"constructor": "nearest", "start": 0, "moves": []}
    trial("baseline", base, "parameter_only", "baseline", None, "Cheap valid geometric reference", "None")
    arms["route_search"].append("baseline")  # One cached evaluation, one slot in each arm.
    for start in range(1, 6):
        trial(f"nearest-start-{start}", {**base, "start": start}, "parameter_only", "parameter_refinement", "baseline",
              "A different fixed starting vertex may improve greedy construction",
              "Structural routes deliberately excluded by this illustrative arm")
    for constructor in ["farthest_insertion", "mst_preorder"]:
        trial(constructor, {"constructor": constructor, "start": 0, "moves": []}, "route_search", "route_prototype",
              "baseline", "Global construction may avoid greedy short-edge traps",
              "Nearby nearest-neighbor starts defer to testing a different construction mechanism")
    parent = min(arms["route_search"], key=lambda name: (results[name]["score"], name))
    selected_constructor = recipes[parent]["constructor"]
    for name, moves, mechanism in [
        ("two-opt", ["two_opt"], "Replace a fixed construction by edge-exchange local optimization"),
        ("relocate", ["two_opt", "relocate"], "Vertex relocation can escape an edge-exchange local minimum"),
        ("alternate", ["two_opt", "relocate", "two_opt"], "Edge exchange after relocation may unlock further gains"),
    ]:
        trial(name, {"constructor": selected_constructor, "start": 0, "moves": moves}, "route_search",
              "mechanism_replacement" if name == "two-opt" else "pipeline_combination", parent, mechanism,
              "Start-vertex tuning defers to a new neighborhood under the same objective and hard cap")
        parent = name
    winners = {arm: min(names, key=lambda name: (results[name]["score"], name)) for arm, names in arms.items()}
    finalists = sorted({"baseline", *winners.values()})
    shortlist = {"winners": winners, "finalists": {name: digest(recipes[name]) for name in finalists},
                 "delivery_rule": contract["confirmation"], "development_data_hash": digest(development)}
    save(output / "shortlist.json", shortlist)
    event(event="shortlist_frozen", shortlist_hash=digest(shortlist))
    # No confirmation coordinates or scores are generated before the freeze.
    confirmation = fixtures(confirmation_sizes, repetitions, 9100, "confirmation")
    save(output / "confirmation.json", confirmation)
    confirmed = {}
    for name in finalists:
        if digest(recipes[name]) != shortlist["finalists"][name]:
            raise ValueError("Frozen recipe changed")
        confirmed[name] = evaluate(name, recipes[name], confirmation, "confirmation")
    summary = {"arms": {}, "distinct_development_recipes": len(results),
               "development_cases": len(development), "confirmation_cases": len(confirmation),
               "limits": contract["limits"]}
    for arm, names in arms.items():
        winner = winners[arm]
        improves = (results[winner]["score"] < results["baseline"]["score"]
                    and confirmed[winner]["score"] < confirmed["baseline"]["score"])
        summary["arms"][arm] = {
            "trials": names, "development_winner": winner, "selected": winner if improves else "baseline",
            "development_scores": {name: results[name]["score"] for name in names},
            "confirmation_baseline": confirmed["baseline"]["score"], "confirmation_winner": confirmed[winner]["score"],
            "confirmation_improvement_fraction": 1 - confirmed[winner]["score"] / confirmed["baseline"]["score"],
            "development_evaluation_seconds": math.fsum(results[name]["seconds"] for name in names),
        }
    save(output / "summary.json", summary)
    if source != pathlib.Path(__file__).read_bytes():
        raise ValueError("Pilot implementation changed during execution")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    parser.add_argument("--sizes", nargs="+", type=int, default=[60, 100, 160])
    parser.add_argument("--confirmation-sizes", nargs="+", type=int, default=[80, 140])
    parser.add_argument("--cases-per-regime", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.sizes, args.confirmation_sizes, args.cases_per_regime), indent=2))


if __name__ == "__main__":
    main()
