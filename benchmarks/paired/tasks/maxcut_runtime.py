#!/usr/bin/env python3
"""Standalone, stdlib-only evaluator for a fixed weighted Max-Cut workload.

The public copy contains no confirmation instance selection or graph data.
Candidate execution has per-process limits; it is not a security sandbox.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
from typing import Any


TASK_ID = "gset-maxcut-paired-v1"
LIMITS = {"wall_seconds_per_graph": 3, "cpu_seconds_per_process": 3,
          "address_space_bytes_per_process": 256 * 1024 * 1024,
          "file_bytes_per_process": 1024 * 1024}
SCORE_MODEL = {"metric": "fixed_graph_raw_cut_sum", "direction": "maximize", "kind": "proxy",
               "origin": "local", "aggregation": "sum of raw weighted cuts over all fixed graphs; not a platform ranking"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def object_hash(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def parse_graph(raw: bytes) -> tuple[int, list[tuple[int, int, int]]]:
    lines = [line.split() for line in raw.decode("utf-8").splitlines() if line.strip()]
    if not lines or len(lines[0]) != 2:
        raise ValueError("Graph must start with vertex and edge counts")
    n, count = map(int, lines[0])
    if n <= 0 or count < 0 or len(lines) != count + 1:
        raise ValueError("Graph vertex/edge counts do not match the file")
    edges, seen = [], set()
    for fields in lines[1:]:
        if len(fields) != 3:
            raise ValueError("Every edge requires two endpoints and an integer weight")
        u, v, weight = map(int, fields)
        if not 1 <= u <= n or not 1 <= v <= n or u == v:
            raise ValueError("Invalid graph endpoint or self-loop")
        key = min(u, v), max(u, v)
        if key in seen:
            raise ValueError("Duplicate undirected edge")
        seen.add(key)
        edges.append((u - 1, v - 1, weight))
    return n, edges


def cut_value(n: int, edges: list[tuple[int, int, int]], partition: Any) -> int:
    if (not isinstance(partition, list) or len(partition) != n or
            any(type(side) not in (int, bool) or side not in (0, 1) for side in partition)):
        raise ValueError(f"Expected exactly {n} binary integer/bool partition labels")
    return sum(weight for u, v, weight in edges if partition[u] != partition[v])


def configuration() -> dict[str, Any]:
    return {"task_id": TASK_ID, "interface": "solve(n, edges, seed); zero-based undirected edges",
            "limits": LIMITS, "score_model": SCORE_MODEL,
            "seed_protocol": "first 8 SHA256 bytes of decimal run seed, colon, graph ID; big-endian integer",
            "runtime_environment": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                                    "system": platform.system(), "machine": platform.machine()},
            "failure_policy": "stop on first failed graph; incomplete or invalid runs have null objective"}


def evaluator_hash() -> str:
    return object_hash({"runtime_sha256": digest(Path(__file__).read_bytes()), "configuration": configuration()})


def load_workload(directory: Path, stage: str, seed: int) -> tuple[list[dict[str, Any]], str]:
    directory = directory.resolve()
    protocol = json.loads((directory / "protocol.json").read_text())
    if (protocol.get("schema_version") != 1 or protocol.get("task_id") != TASK_ID or
            protocol.get("stage") != stage or not isinstance(protocol.get("graphs"), list) or not protocol["graphs"]):
        raise ValueError("Invalid task protocol or stage")
    graphs, seen = [], set()
    for graph in protocol["graphs"]:
        name = graph["id"]
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("Missing or duplicate graph ID")
        seen.add(name)
        path = (directory / graph["file"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Graph path must remain inside its dataset directory")
        raw = path.read_bytes()
        if digest(raw) != graph["sha256"]:
            raise ValueError(f"Graph hash mismatch: {name}")
        n, edges = parse_graph(raw)
        case_seed = int.from_bytes(hashlib.sha256(f"{seed}:{name}".encode()).digest()[:8], "big")
        graphs.append({"id": name, "sha256": digest(raw), "n": n, "edges": edges, "seed": case_seed})
    workload = {"task_id": TASK_ID, "stage": stage, "run_seed": seed,
                "cases": [{k: graph[k] for k in ("id", "sha256", "seed")} for graph in graphs]}
    return graphs, object_hash(workload)


class CaseFailure(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def run_case(candidate: Path, graph: dict[str, Any], directory: Path) -> dict[str, Any]:
    directory.mkdir()
    payload = {key: graph[key] for key in ("n", "edges", "seed")}
    (directory / "input.json").write_text(json.dumps(payload, separators=(",", ":")))
    started = time.perf_counter()
    with (directory / "input.json").open("rb") as stdin, (directory / "stdout.json").open("wb") as stdout, \
            (directory / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "_worker", str(candidate)],
                                   cwd=directory, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True,
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"})
        try:
            process.wait(timeout=LIMITS["wall_seconds_per_graph"])
        except subprocess.TimeoutExpired as exc:
            raise CaseFailure("timeout", f"Graph exceeded {LIMITS['wall_seconds_per_graph']} seconds wall time") from exc
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    elapsed = time.perf_counter() - started
    if process.returncode != 0:
        raise CaseFailure("candidate_execution_failed", f"Worker exited {process.returncode}; inspect case stderr")
    try:
        answer = json.loads((directory / "stdout.json").read_text())
        partition = answer["partition"]
        value = cut_value(graph["n"], graph["edges"], partition)
    except (ValueError, KeyError, TypeError) as exc:
        raise CaseFailure("invalid_partition", str(exc)) from exc
    (directory / "partition.json").write_text(json.dumps(partition) + "\n")
    return {"id": graph["id"], "n": graph["n"], "m": len(graph["edges"]), "graph_sha256": graph["sha256"],
            "seed": graph["seed"], "cut": value, "positive_weight_upper_bound": sum(max(0, w) for _, _, w in graph["edges"]),
            "wall_seconds_including_worker": elapsed, "solve_seconds": answer["solve_seconds"]}


def _evaluate(dataset: Path, candidate: Path, out: Path, seed: int, stage: str,
              *, public: Path | None = None, frozen_run: Path | None = None) -> dict[str, Any]:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    config = configuration()
    result: dict[str, Any] = {
        "schema_version": 1, "status": "failed", "valid": False, "stage": stage,
        "candidate_scope": "program_source", "candidate_hash": None,
        "evaluator_hash": evaluator_hash(), "score_model_hash": object_hash(SCORE_MODEL), "workload_hash": None,
        "score": {**SCORE_MODEL, "value": None, "components": {}},
        "evaluation": {"stage": stage, "config_hash": object_hash(config), "configuration": config,
                       "expected_cases": 0, "completed_cases": 0, "seeds": [seed], "repetitions": 1,
                       "runtime_environment": config["runtime_environment"]},
        "validity_scope": "complete_partition_validation_and_exact_raw_cut_recomputation",
        "unchecked_rules": ["candidate_external_side_effects_not_security_sandboxed", "prior_exposure_to_public_benchmark",
                            "proof_of_optimality", "aggregate_child_process_resource_usage"],
        "cases": [], "error": None,
        "archive": {"source": str(out / "candidate.py"), "configuration": None, "result": str(out / "result.json")},
    }
    try:
        if os.name != "posix":
            raise CaseFailure("unsupported_platform", "This evaluator requires POSIX resource limits and process groups")
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        source = candidate.read_bytes()
        source.decode("utf-8")
        result["candidate_hash"] = digest(source)
        (out / "candidate.py").write_bytes(source)
        dev_graphs = []
        if frozen_run is not None:
            frozen_bytes = (frozen_run / "result.json").read_bytes()
            frozen = json.loads(frozen_bytes)
            if (frozen.get("status") != "success" or frozen.get("valid") is not True or
                    frozen.get("candidate_hash") != digest(source) or frozen.get("evaluator_hash") != result["evaluator_hash"] or
                    frozen.get("evaluation", {}).get("config_hash") != object_hash(config) or frozen.get("stage") != "development"):
                raise CaseFailure("invalid_frozen_run", "Frozen development source/result identity or validity mismatch")
            previous_seeds = frozen["evaluation"].get("seeds", [])
            if len(previous_seeds) != 1:
                raise CaseFailure("invalid_frozen_run", "Frozen run lacks its measurement seed")
            dev_graphs, dev_hash = load_workload(public, "development", previous_seeds[0])
            if (frozen.get("workload_hash") != dev_hash or
                    frozen["evaluation"].get("completed_cases") != len(dev_graphs) or
                    frozen["evaluation"].get("expected_cases") != len(dev_graphs)):
                raise CaseFailure("invalid_frozen_run", "Frozen run lacks complete matching development evidence")
            result["frozen_from"] = {"result_sha256": digest(frozen_bytes), "candidate_hash": digest(source)}
        graphs, result["workload_hash"] = load_workload(dataset, stage, seed)
        if dev_graphs and ({g["id"] for g in graphs} & {g["id"] for g in dev_graphs} or
                           {g["sha256"] for g in graphs} & {g["sha256"] for g in dev_graphs}):
            raise CaseFailure("invalid_confirmation_workload", "Confirmation must use distinct graph IDs and bytes")
        result["evaluation"]["expected_cases"] = len(graphs)
        for index, graph in enumerate(graphs):
            result["cases"].append(run_case(out / "candidate.py", graph, out / f"case-{index}"))
            result["evaluation"]["completed_cases"] = len(result["cases"])
        if digest((out / "candidate.py").read_bytes()) != result["candidate_hash"] or evaluator_hash() != result["evaluator_hash"]:
            raise CaseFailure("execution_identity_changed", "Candidate or evaluator bytes changed during execution")
        result["score"]["components"] = {case["id"]: case["cut"] for case in result["cases"]}
        result["score"]["value"] = sum(case["cut"] for case in result["cases"])
        result.update(status="success", valid=True)
    except (CaseFailure, OSError, ValueError, KeyError, TypeError) as exc:
        result["error"] = {"type": exc.kind if isinstance(exc, CaseFailure) else "invalid_evaluation_input", "message": str(exc)}
    result["elapsed_seconds"] = time.perf_counter() - started
    result["artifacts"] = [str(path.relative_to(out)) for path in sorted(out.rglob("*")) if path.is_file()] + ["result.json"]
    (out / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def evaluate(public: Path, candidate: Path, out: Path, seed: int) -> dict[str, Any]:
    return _evaluate(Path(public), Path(candidate), Path(out), seed, "development")


def confirm(public: Path, private: Path, frozen_run: Path, out: Path, seed: int) -> dict[str, Any]:
    frozen_run = Path(frozen_run)
    return _evaluate(Path(private), frozen_run / "candidate.py", Path(out), seed, "confirmation",
                     public=Path(public), frozen_run=frozen_run)


def worker(candidate: str) -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (LIMITS["cpu_seconds_per_process"], LIMITS["cpu_seconds_per_process"] + 1))
    resource.setrlimit(resource.RLIMIT_AS, (LIMITS["address_space_bytes_per_process"],) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMITS["file_bytes_per_process"],) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    data = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        spec = importlib.util.spec_from_file_location("maxcut_candidate", candidate)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        started = time.perf_counter()
        partition = module.solve(data["n"], [tuple(edge) for edge in data["edges"]], data["seed"])
        elapsed = time.perf_counter() - started
    json.dump({"partition": partition, "solve_seconds": elapsed}, sys.stdout, allow_nan=False)


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "_worker":
        worker(sys.argv[2])
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("evaluate", "confirm"):
        sub = commands.add_parser(name)
        sub.add_argument("--public", required=True, type=Path)
        sub.add_argument("--output", required=True, type=Path)
        sub.add_argument("--seed", required=True, type=int)
        if name == "evaluate":
            sub.add_argument("--candidate", required=True, type=Path)
        else:
            sub.add_argument("--private", required=True, type=Path)
            sub.add_argument("--frozen-run", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = (evaluate(args.public, args.candidate, args.output, args.seed) if args.command == "evaluate"
                  else confirm(args.public, args.private, args.frozen_run, args.output, args.seed))
    except OSError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 2
    print(json.dumps({"status": result["status"], "valid": result["valid"], "score": result["score"],
                      "archive": result["archive"], "error": result["error"]}, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
