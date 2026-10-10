# Competition Adapter Contract

An adapter makes one competition family or task reproducibly evaluable. Keep the competition-specific objective and execution details in the adapter; keep experiment selection and score-directed decisions in the shared skill.

## Required Information

Before search, the adapter or sealed task contract must identify:

- Candidate artifacts (source, configuration, predictions, model weights, or other required files) and exact build/train/run/package commands.
- Hard validity rules, resource limits, and failure categories.
- The official metric, whether it is maximized or minimized, its formula, per-case aggregation, thresholds, and parameters. Mark every unavailable term explicitly.
- Development and validation workloads, data splits, seeds, and repetition policy.
- Which measurements are score inputs and which are diagnostics only, and which measured costs count toward the experiment budget.

Identify the origin and scope of constraints: competition rules, explicit user limits, or provisional agent policies/defaults. A convenient acceptance threshold, speed-only search scope or exact-incumbent-output check is not a task requirement merely because the agent recorded it in a contract. Preserve evaluation identity, but do not restrict permissible solution changes to simplify comparison.

If the official score cannot be computed, return its value as unavailable. Do not silently replace it with a convenient proxy. Preserve individual score components so the optimizer can compare tradeoffs without inventing weights.

## Verify the Executable Meaning

Compare official rules, scorer source where available, and actual output on reference candidates. Check maximize/minimize transformations, units, mean/median/percentile or relative-score aggregation, case weights, timeout treatment, and validity coverage. A field called `correct` or `accepted` may mean only one case passed or a positive score was returned; record individual outcomes and enforce the contract's required checks before promotion.

For relative or rank-based objectives whose reference changes, preserve raw measurements and the reference version. Freeze that reference for comparisons or recompute all compared candidates under the same reference. Do not present a local reference ranking as the unknown official ranking. Smoke-test the scoring boundary as well as candidate execution, including missing cases, non-finite metrics, and timeout/failed outputs.

## Result Record

Each invocation should produce an immutable machine-readable result with information equivalent to:

```json
{
  "schema_version": 1,
  "status": "success",
  "valid": true,
  "candidate_hash": "...",
  "evaluator_hash": "...",
  "score_model_hash": "...",
  "score": {
    "kind": "official_metric",
    "origin": "local",
    "direction": "maximize",
    "value": 0.0,
    "aggregation": "officially specified aggregation",
    "components": {}
  },
  "evaluation": {
    "stage": "validation",
    "config_hash": "...",
    "split_hash": "...",
    "seeds": [],
    "repetitions": 1,
    "runtime_environment": {}
  },
  "artifacts": [],
  "error": null
}
```

`status` describes whether evaluation executed; `valid` describes whether the candidate passed the hard rules checked at that stage. Check task feasibility/invariants, not output identity with the incumbent, unless unique output, user requirements or an intentionally equivalent optimization calls for it. Preserve individual check outcomes and expected/completed case counts so an inexpensive stage cannot imply all rules passed. Partial or failed evaluations cannot promote a candidate. Numeric score inputs must be finite; missing values need an explicit reason or officially specified failure treatment.

When using the candidate archive, declare what `candidate_hash` identifies with `candidate_scope`: `prediction_csv` for the bundled prediction interface, `generated_artifact` for other produced outputs or weights, and a source scope such as `program_source` for directly evaluated code. Snapshot the complete executable recipe separately for produced artifacts, passed as `--configuration` to the archive. Include intended candidate arguments and feature/data dependencies; record measurement seeds under the declared repetition protocol. Produced bytes identify an execution artifact, while the recipe identifies the implementation. Source candidates use source plus configuration. The archive does not infer artifact meaning from extensions, recompute missing recipes or certify their provenance; other task-specific scopes keep their declared source/configuration identity until adapted.

`score.kind` is `official_metric` (the specified formula), `proxy`, or `unknown`; `score.origin` is `local` or `platform`. A local evaluation using the official metric is still a local estimate, not a leaderboard result. `score.direction` is `maximize` or `minimize`. A proxy must name its formula and assumptions. An unknown score has a null value and explicit missing terms. For tasks with multiple test cases, report per-case scores and use the official aggregation rather than an unweighted average chosen by the adapter author.

An adapter may use different field names during an initial pilot, but it must preserve these distinctions and hashes. A shared runner should normalize adapters only after more than one real adapter demonstrates a stable common contract.

## Comparability

Candidate comparisons require the same score-model version, evaluator and fixture hashes, workload/split, evaluation fidelity, seed protocol, and relevant measurement environment. Hash evaluation configuration separately from candidate configuration: candidate hyperparameters may differ, but comparisons must use the same evaluation protocol. For noisy workloads, preserve repetitions and compare matched cases. Report feasibility failures separately from low scores; invalid candidates are never promoted.

When estimating uncertainty, record which variation is modeled: sampling independent rows/groups, training/execution seeds, or new scenarios. A paired resampling interval conditional on fixed predictions does not measure training randomness or distribution shift. Define independent units, compute limits, practical improvement thresholds, and the confirmation protocol before interpreting comparisons; uncertainty diagnostics do not change the official objective.

## Family-Specific Checks

- **Algorithm/code:** compile and interface checks, property or differential tests, boundary cases, resource limits, and workload-level quality/time metrics.
- **Data/model:** train/validation/test provenance, leakage checks, fixed folds, prediction artifacts, and metric computation from predictions. Keep the final test split untouched and do not use public leaderboard feedback as a substitute for local validation.
- **Stochastic simulation:** fixed seed sets, repeated runs where needed, confidence or dispersion measures, and explicit feasibility gates.
- **Optimization/control:** exact constraint checks, objective components, solver status, and repeatable instance sets.

These are adapter requirements, not assumptions that every family is already implemented in this repository.
