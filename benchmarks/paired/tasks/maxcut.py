"""Pinned Stanford Gset source preparation for the paired Max-Cut task.

Only URLs, hashes and original adapter code are committed. Downloaded graph and
upstream source bytes remain in an explicitly supplied external cache.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

try:
    from .maxcut_runtime import TASK_ID, LIMITS, evaluate, confirm, main, parse_graph
except ImportError:
    from maxcut_runtime import TASK_ID, LIMITS, evaluate, confirm, main, parse_graph


SOURCE_BASE = "https://web.stanford.edu/~yyye/yyye/Gset/"
DEVELOPMENT = ("G1", "G6", "G11")
CONFIRMATION = ("G2", "G7", "G12")
GRAPH_HASHES = {
    "G1": "73bf704d8ffc55ba42260ab4cb659e3dcb6e729be70404d2cf476ba4e46d1665",
    "G2": "732d57480a0151e81253a08535da539ff579f77dbc8673d2b58f4b051f6ccdac",
    "G6": "e3dd8b29205280f1ad5806849321cdff6f11324c75cb95647d5783f3e47a1103",
    "G7": "62a49edc162b2548ea4a58f2b65a6398f9a54a24ea448f3939f1526326200329",
    "G11": "c2a760d2926db4fefd23b25c098dcd6311f711b355dbd1cc689fa25660c73174",
    "G12": "a8628108d95d74b90a342fabe97faaa566dabfb3f64382a93548b3bdf131f8e3",
}
LICENSE_NOTE = ("No explicit dataset redistribution license was located in the inspected Stanford Gset directory, "
                "author page or rudy.c snapshot on 2026-11-10. Public download is not treated as a redistribution grant. "
                "Keep original downloaded bytes in the local cache, outside the repository.")


def fetch_sources(cache: Path) -> dict:
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    for name, expected in GRAPH_HASHES.items():
        if (cache / name).exists() and hashlib.sha256((cache / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Cached Gset hash mismatch: {name}; preserve/inspect the cache before retrying")
    urls = {name: SOURCE_BASE + name for name in GRAPH_HASHES}
    urls.update({"index.html": SOURCE_BASE, "author.html": "https://web.stanford.edu/~yyye/",
                 "rudy.c": SOURCE_BASE + "rudy.c"})
    sources = {}
    for name, url in urls.items():
        path = cache / name
        if not path.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "competition-paired-evaluation/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
            actual = hashlib.sha256(raw).hexdigest()
            if name in GRAPH_HASHES and actual != GRAPH_HASHES[name]:
                raise ValueError(f"Downloaded Gset hash mismatch: {name}; upstream bytes differ from the task pin")
            path.write_bytes(raw)
        raw = path.read_bytes()
        source = {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        if name in GRAPH_HASHES:
            n, edges = parse_graph(raw)
            source.update(vertices=n, edges=len(edges), weights=sorted({w for _, _, w in edges}))
        sources[name] = source
    manifest = {"schema_version": 1, "task_id": TASK_ID, "checked_utc": datetime.now(timezone.utc).isoformat(),
                "sources": sources, "license_note": LICENSE_NOTE}
    (cache / "sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def prepare(cache: Path, output: Path) -> dict:
    cache, output = Path(cache).resolve(), Path(output).resolve()
    manifest = fetch_sources(cache)
    output.mkdir(parents=True, exist_ok=False)
    for stage, name, graph_ids in [("development", "public", DEVELOPMENT), ("confirmation", "private", CONFIRMATION)]:
        directory = output / name
        (directory / "graphs").mkdir(parents=True)
        if name == "private":
            directory.chmod(0o700)
        graphs = []
        for graph_id in graph_ids:
            relative = f"graphs/{graph_id}.txt"
            shutil.copyfile(cache / graph_id, directory / relative)
            graphs.append({"id": graph_id, "file": relative, **manifest["sources"][graph_id]})
        protocol = {"schema_version": 1, "task_id": TASK_ID, "stage": stage, "graphs": graphs}
        (directory / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    here = Path(__file__).resolve().parent
    public = output / "public"
    shutil.copyfile(here / "maxcut_runtime.py", public / "task.py")
    shutil.copyfile(here / "maxcut_baseline.py", public / "candidate.py")
    (public / "TASK.md").write_text(f'''# Weighted Max-Cut on a fixed public Gset subset

Improve the provided executable `candidate.py`. It implements a credible eight-start randomized one-vertex local search; improving it may require escaping single-flip local optima, a better construction, or more efficient search. Do not hard-code graph answers or read other graph/result files from candidate code.

Return a single UTF-8 Python file exposing `solve(n, edges, seed)`. The evaluator calls it once per graph with `n` vertices and a list of `(u, v, weight)` tuples. Endpoints are zero-based, undirected, and appear once; weights are signed integers. Return exactly `n` integer/bool labels in {{0,1}}. Either side may be empty. Use Python's standard library only and derive randomness from the supplied seed. Candidate code must not start subprocesses, access the network, read other files, or use external precomputed solutions.

The raw cut is the sum of each edge's signed weight when its endpoints have different labels. Negative crossing edges reduce the cut. The local objective is the **sum of raw cuts across every fixed development graph**, maximized; it is not a Gset leaderboard score or a claim of optimality. All graphs receive the same solver interface and limits. Reports retain every graph's raw cut and the sum of positive edge weights as a simple upper bound, not a known optimum.

Development files are {', '.join(DEVELOPMENT)}, all 800 vertices; exact files and SHA256 pins are in `protocol.json`. Use the existing development protocol throughout. Each graph gets a deterministic seed derived from the run seed and graph ID. Repeating a seed measures the same implementation; it is not a new algorithm. A separate fixed set is withheld by the experiment controller for post-freeze evaluation. This is posterior evaluation on a **public benchmark**; withholding local files cannot establish that the instances have never been seen before.

Run a local evaluation with a fresh output directory:

```sh
python task.py evaluate --public . --candidate candidate.py --output run-001 --seed 17
```

Per graph: {LIMITS['wall_seconds_per_graph']} seconds wall time including Python startup/import and serialization; {LIMITS['cpu_seconds_per_process']} seconds CPU per process; {LIMITS['address_space_bytes_per_process']} bytes address space per process; {LIMITS['file_bytes_per_process']} bytes per output file. Linux/POSIX is required. Timeout, resource termination, exception, malformed result or invalid partition stops the run, sets `valid=false` and leaves the aggregate objective null. A valid zero/negative cut remains a valid low score. Logs and partial successful cases remain for diagnosis. No automatic retries or lucky-seed selection are performed.

The evaluator snapshots source, recomputes cuts independently, and records complete coverage and source/evaluator/config/workload identities. Its process limits are not a security sandbox or proof of compliance with external-file/network rules; the controller uses a common trusted evaluator for both paired arms. Do not edit `task.py`, `protocol.json` or graph files. Freeze the selected source before requesting confirmation and do not revise it from confirmation feedback.

Original source directory: {SOURCE_BASE}

{LICENSE_NOTE}
''')
    (output / "sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"task_id": TASK_ID, "public": str(public), "private": str(output / "private"),
            "sources": str(output / "sources.json"), "baseline": str(public / "candidate.py")}


if __name__ == "__main__":
    raise SystemExit(main())
