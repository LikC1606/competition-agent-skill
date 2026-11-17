"""Durable launch, fit accounting and proposal evidence for the tabular adapter.

This records calls made by the adapter, not fits hidden inside arbitrary Python.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from prediction_core import byte_hash, object_hash, load_result, scorer_fingerprint


def append_event(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), **event},
                                allow_nan=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def proposal_binding(archive: Path | None, proposal_id: str | None, *, allow_closed: bool = False) -> dict:
    if (archive is None) != (proposal_id is None):
        raise ValueError("Provide both --archive and --proposal-id")
    if archive is None:
        return {"status": "unregistered"}
    # Imported lazily: archive recording also verifies these receipts.
    from candidate_archive import parse_records
    archive = archive.expanduser().resolve(strict=True)
    raw = archive.read_bytes()
    records = parse_records(raw, str(archive))
    proposal = next((row for row in records if row["event"] == "proposal"
                     and row["proposal_id"] == proposal_id), None)
    if proposal is None:
        raise ValueError("Record the proposal before training")
    if not allow_closed and any(row["event"] in {"candidate", "proposal_stop"} and row.get("proposal_id") == proposal_id
                                for row in records):
        raise ValueError("Training proposal is already closed")
    return {"status": "bound", "proposal_id": proposal_id, "proposal_sha256": object_hash(proposal),
            "archive": str(archive), "prefix_bytes": len(raw), "prefix_sha256": byte_hash(raw)}


def fit_cost(root: Path) -> dict:
    """Include failed attempts and unknown completions without inventing durations."""
    launch = json.loads((root / "execution.json").read_text())
    events = []
    raw = (root / "fit-events.jsonl").read_bytes()
    # A killed append can leave a partial tail; completed newline records survive.
    for line in raw.splitlines(keepends=True):
        if line.endswith(b"\n"):
            events.append(json.loads(line))
    starts = {row["fold_id"] for row in events if row["event"] == "fit_started"}
    done = [row for row in events if row["event"] == "fit_completed"]
    failed = [row for row in events if row["event"] == "fit_failed"]
    ended = {row["fold_id"] for row in done + failed}
    complete = next((row for row in events if row["event"] == "run_completed"), None)
    return {"execution_id": launch["execution_id"], "fit_calls": len(starts),
            "completed_fit_calls": len(done), "failed_fit_calls": len(failed),
            "unresolved_fit_calls": len(starts - ended),
            "fit_seconds_recorded": sum(row["fit_seconds"] for row in done + failed),
            "workflow_seconds": complete["elapsed_seconds"] if complete else None,
            "journal_complete": not raw or raw.endswith(b"\n"),
            "scope": "adapter estimator.fit calls; nested fits and agent/research time are excluded"}


def execution_descriptor(root: Path) -> dict:
    binding = json.loads((root / "execution.json").read_text())["proposal"]
    return {"kind": "tabular_training_v1",
            "execution_sha256": byte_hash((root / "execution.json").read_bytes()),
            "journal_sha256": byte_hash((root / "fit-events.jsonl").read_bytes()),
            "proposal_at_launch": {key: binding[key] for key in ["status", "proposal_id", "proposal_sha256"]
                                   if key in binding},
            "cost": fit_cost(root)}


def cost_report(roots: list[Path]) -> dict:
    runs = [{"path": str(root), **fit_cost(root)} for root in roots]
    unique = {}
    for row in runs:
        identifier = row["execution_id"]
        cost = {key: value for key, value in row.items() if key != "path"}
        if identifier in unique and unique[identifier] != cost:
            raise ValueError("Copies of the same execution have inconsistent cost journals")
        unique[identifier] = cost
    costs = list(unique.values())
    return {"runs": runs, "unique_executions": len(costs),
            **{key: sum(cost[key] for cost in costs) for key in
               ["fit_calls", "completed_fit_calls", "failed_fit_calls", "unresolved_fit_calls", "fit_seconds_recorded"]},
            "completed_workflow_seconds": sum(cost["workflow_seconds"] for cost in costs
                                               if cost["workflow_seconds"] is not None),
            "unfinished_workflows": sum(cost["workflow_seconds"] is None for cost in costs),
            "scope": "unique adapter executions, including failed attempts; excludes agent/research and nested fits"}


def verify_manifest(root: Path, kind: str) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("seal") != object_hash({k: v for k, v in manifest.items() if k != "seal"}):
        raise ValueError("Invalid training manifest")
    if manifest.get("kind") != kind:
        raise ValueError("Unexpected training manifest kind: " + str(manifest.get("kind")))
    for name, expected in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or byte_hash(path.read_bytes()) != expected:
            raise ValueError("Training artifact changed: " + name)
    return manifest


def verify_training_source(result_path: Path, descriptor: dict) -> tuple[Path, dict]:
    """Verify the original fitting receipt without importing the fitted model."""
    if descriptor.get("kind") != "tabular_training_v1":
        raise ValueError("Unknown training execution kind")
    root = result_path.resolve().parent.parent
    manifest = verify_manifest(root, "tabular_training")
    if manifest["files"].get("evaluation/result.json") != byte_hash(result_path.read_bytes()):
        raise ValueError("Result is outside its training manifest")
    if execution_descriptor(root) != descriptor:
        raise ValueError("Training execution or fit cost changed")
    launch = json.loads((root / "execution.json").read_text())
    for name, expected in launch["inputs"].items():
        if byte_hash((root / name).read_bytes()) != expected:
            raise ValueError("Training input differs from launch: " + name)
    return root, launch


def verify_rescored_source(result_path: Path, descriptor: dict) -> tuple[Path, dict]:
    """Bind a zero-fit rescore to the exact original predictions and fitting receipt."""
    output = result_path.resolve().parent.parent
    manifest = verify_manifest(output, "tabular_rescore")
    if manifest["files"].get("evaluation/result.json") != byte_hash(result_path.read_bytes()):
        raise ValueError("Result is outside its rescore manifest")
    lineage = descriptor["rescore"]
    source = Path(lineage["source_run"]).resolve(strict=True)
    if byte_hash((source / "manifest.json").read_bytes()) != lineage["source_manifest_sha256"]:
        raise ValueError("Original training manifest changed since rescoring")
    original_path = source / "evaluation/result.json"
    original = load_result(original_path)
    if byte_hash(original_path.read_bytes()) != lineage["source_result_sha256"]:
        raise ValueError("Original training result changed since rescoring")
    expected = {**original["training_execution"], "rescore": lineage}
    if descriptor != expected or "rescore" in original["training_execution"]:
        raise ValueError("Rescore changed the originating training receipt")
    root, launch = verify_training_source(original_path, original["training_execution"])
    result = load_result(result_path)
    if (result["candidate_hash"] != original["candidate_hash"] or
            result["evaluation"]["configuration"] != original["evaluation"]["configuration"] or
            result["score_model_hash"] != original["score_model_hash"]):
        raise ValueError("Rescore must use the original OOF predictions and scoring inputs")
    reference = json.loads((output / "reference-result.json").read_text())
    backend = reference["evaluation"].get("runtime_environment", {}).get("metric_backend")
    scorer_hash = scorer_fingerprint(output / "scorer", backend)
    if (result["evaluator_hash"] != scorer_hash or scorer_hash != reference["evaluator_hash"] or
            result["evaluation"] != reference["evaluation"] or
            result["score_model_hash"] != reference["score_model_hash"]):
        raise ValueError("Rescore differs from the pinned reference contract")
    return root, launch


def verify_execution(result_path: Path, descriptor: dict, *, archive: Path,
                     proposal_id: str | None, configuration: Path | None) -> dict:
    """Check a managed result before archive append. Legacy results have no descriptor."""
    root, launch = (verify_rescored_source(result_path, descriptor) if "rescore" in descriptor else
                    verify_training_source(result_path, descriptor))
    if configuration is None or configuration.read_bytes() != (root / "recipe.json").read_bytes():
        raise ValueError("Managed training results require --configuration RUN/recipe.json")
    binding = launch["proposal"]
    if proposal_id is not None:
        if binding.get("status") != "bound" or binding.get("proposal_id") != proposal_id:
            raise ValueError("Proposal was not bound before training; late registration cannot complete it")
        raw = archive.read_bytes()
        prefix = raw[:binding["prefix_bytes"]]
        if len(prefix) != binding["prefix_bytes"] or byte_hash(prefix) != binding["prefix_sha256"]:
            raise ValueError("Proposal archive prefix changed since training launch")
        from candidate_archive import parse_records
        rows = parse_records(prefix, str(archive))
        proposal = next((row for row in rows if row["event"] == "proposal"
                         and row["proposal_id"] == proposal_id), None)
        if proposal is None or object_hash(proposal) != binding["proposal_sha256"]:
            raise ValueError("Proposal differs from training launch")
    elif binding.get("status") == "bound":
        raise ValueError("Record this managed result with its bound --proposal-id")
    return descriptor["cost"]
