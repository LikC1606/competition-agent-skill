# Competition Adapter Contract

An adapter makes one competition family or task reproducibly evaluable. Keep the competition-specific objective and execution details in the adapter; keep experiment selection and score-directed decisions in the shared skill.

## Required Information

Before search, the adapter or sealed task contract must identify:

- Candidate artifacts (source, configuration, predictions, model weights, or other required files) and exact build/train/run/package commands.
- Hard validity rules, resource limits, and failure categories.
- The official metric, whether it is maximized or minimized, its formula, per-case aggregation, thresholds, and parameters. Mark every unavailable term explicitly.
- Development and validation workloads, data splits, seeds, and repetition policy.
- Which measurements are score inputs and which are diagnostics only; record measured costs and any currently applicable resource constraints. No numeric optimization budget is required when none applies.

Identify the origin and scope of constraints: competition rules, actual resource availability, currently applicable user limits, or provisional agent policies. Do not impose default optimization time/cost/trial/round caps; a later user removal/change supersedes earlier optimization limits prospectively without changing prior results. A convenient acceptance threshold, speed-only search scope or exact-incumbent-output check is not a task requirement merely because the agent recorded it in a contract. Preserve evaluation identity, but do not restrict permissible solution changes to simplify comparison.

If the official score cannot be computed, return its value as unavailable. Do not silently replace it with a convenient proxy. Preserve individual score components so the optimizer can compare tradeoffs without inventing weights.

## Verify the Executable Meaning

When organizers publish runnable tools, try their generator and scorer before implementing replacements. If a build trips on a read-only dependency cache, try a cache inside the workspace and bound the build to the checkpoint's remaining time. Check the official web or prebuilt version before replacing the scorer. A published WebAssembly visualizer may expose its generator and scorer to an installed JavaScript runtime. Reuse the published module through its actual interface and save the version and hashes. AHC041's [official visualizer](https://img.atcoder.jp/ahc041/m0Bwp9WL.html?lang=en) uses `gen` and `vis`, so its own scoring code can run without building Rust. If the official tool cannot run within the task's environment or budget, keep fallback measurements provisional until a reference comparison establishes what is equivalent.

Compare official rules, scorer source where available, and actual output on reference candidates. Check maximize/minimize transformations, units, mean/median/percentile or relative-score aggregation, case weights, timeout treatment, and validity coverage. A field called `correct` or `accepted` may mean only one case passed or a positive score was returned; record individual outcomes and enforce the contract's required checks before promotion.

Identify the scorer's actual validity signal. For example, the AHC027 local visualizer exits normally for a route that misses a square, prints an error and then prints `Score = 0`. For a minimization task this can reverse rankings if the adapter reads only the final number. Check the complete response on valid, illegal and missing output. An interactive visualizer can treat an empty answer as its initial display state. Check missing or empty output explicitly when the task requires an answer. If the task accepts successive answers, exercise both a valid sequence and a malformed earlier block followed by a valid last block to check the official parser and the scoring selection. Gate aggregation on validity and complete case coverage.

When the metric penalizes unfinished work, include a legal partial output in the boundary check. A local adapter must preserve the official distinction between a penalty and an invalid output.

For relative or rank-based objectives whose reference changes, preserve raw measurements and the reference version. Freeze that reference for comparisons or recompute all compared candidates under the same reference. Do not present a local reference ranking as the unknown official ranking. Smoke-test the scoring boundary as well as candidate execution, including missing cases, non-finite metrics, and timeout/failed outputs.

Establish [local evaluation quality](local-evaluation.md) separately from identity and execution checks: the workload must represent decision-relevant test conditions, respect independent groups and information availability, and expose the mechanisms being compared. Preserve unknown distribution assumptions. A stable evaluator hash does not certify any of these properties; a public leaderboard correlation alone cannot validate them.

### Live Interaction and Saved Output

When a judge answers during execution, route the full instance to the organizer's live tester. Verify in the tester source or with a probe what initial fields and replies actually reach the candidate. Keep hidden state in the judge and run each policy live when its queries or actions can differ. A standalone visualizer can replay saved output and score the final answer. It establishes only the checks that its replay implements.

Use one accepted interaction and one that breaks a consequential protocol rule, such as exceeding the query limit. Check which errors the tester signals in text and which it signals through its exit status. A zero score can also be legal. Apply the shared deadline to every live run and exercise timeout or early termination when either could produce an incomplete result. If a prior result used a different launcher or deadline, remeasure the pair with one runner before comparing quality and time. Save the versioned tool, build/run recipe, fixed inputs, stdout and judge diagnostics where the next checkpoint can reuse them. Record each case's query/action count, validity, score and elapsed time. Report what the local timer includes.

When a deadline determines eligibility, preserve the actual launched command or effective timeout with the case result. Record the time limit used by any separate timeout probe so a deliberately short probe can be distinguished from the scored runs.

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
    "metric": "objective_name",
    "direction": "maximize",
    "value": 0.0,
    "aggregation": "officially specified aggregation",
    "components": {}
  },
  "evaluation": {
    "stage": "development",
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

For a frozen repeatability plan, add `evaluation.measurement_plan_id` and `evaluation.measurement_run_id` to each actual result, alongside exactly matching `evaluation.seeds` and `evaluation.repetitions`. Keep those run-specific fields outside the implementation recipe. The archive checks them against a pre-existing `measurement_plan` event and the complete comparison before accepting the record. This binding proves the recorded plan/result order and declared metadata match; the task adapter still owns actual seed use, aggregation and scoring correctness.

`score.kind` is `official_metric` (the specified formula), `proxy`, or `unknown`; `score.origin` is `local` or `platform`. A local evaluation using the official metric is still a local estimate, not a leaderboard result. `score.direction` is `maximize` or `minimize`. A proxy must name its formula and assumptions. An unknown score has a null value and explicit missing terms. For tasks with multiple test cases, report per-case scores and use the official aggregation rather than an unweighted average chosen by the adapter author.

An adapter may use different field names during an initial pilot, but it must preserve these distinctions and hashes. A shared runner should normalize adapters only after more than one real adapter demonstrates a stable common contract.

Before scoring a matched control and challenger, fix the evaluator hash, score model hash, evaluation stage and input workload identity. Emit the shared identity from the adapter into both result files (`evaluation.split_hash` carries the workload). A hash passed only to the control's `record` command is absent from its result file. If present, `evaluation.config_hash` and `evaluation.runtime_environment` are also part of the comparison. Generate these from one evaluation configuration. Keep solver settings, dependencies and their recipe hash in `--configuration`. Keep setup failure notes in the result's diagnostics so differing phrasing cannot split an otherwise unchanged environment. Preserve any real differences when they affect the declared comparison. With `candidate_archive.py brief --archive ARCHIVE --anchor CONTROL_ID`, verify that both implementations appear under the control's comparison before making a paired claim. If the results use different contracts, identify the change and replay saved outputs when that can repair the comparison. Preserve prior results and archive the eligible replay separately.

For a deterministic judge, the score model describes the scoring rule. Save the metric, direction, judge version, case acceptance and aggregation in the shared scoring configuration and hash its bytes for `score_model_hash`. Use the same file for every matched run. The evaluator hash identifies the executed scorer, while the workload hash identifies the inputs. For an old result with no emitted score model identifier, reconstruct the description only when the saved evaluator or launcher and measurement evidence establish those details. Cite them and label the identifier as reconstructed.

In a new task, archive the verified control when its shared comparison is ready. A subsequent checkpoint can continue a source search or implement a supported proposal from that control. Keep small mechanism checks separate from the scored development panel. Record the proposal before starting the matched evaluation on that panel.

## Optional Case Profile

An adapter may provide aligned development outcomes for finding useful construction references:

```json
"case_profile": {
  "metric": "per-case-profit",
  "direction": "maximize",
  "cases": {"case-0": 97, "case-1": 78}
}
```

Use stable nonempty string case IDs and finite numeric values, with an explicit metric and `maximize` or `minimize` direction. The profile can differ from the aggregate metric: squared errors, for example, accompany an RMSE score. It does not replace the score, evaluation contract, case-completion checks or validity evidence. The archive retains a compact descriptor and hashes; complete case values stay in the immutable result. Complementary retrieval additionally requires the same complete comparison and matching profile metric, direction and exact IDs. It uses ordinary executed development candidates only. These values guide the next construction, not promotion or a hypothetical combined score. See [retrieval semantics](iteration-trace.md#retrieve-complementary-case-evidence).

## Optional Measured Resource Profile

An adapter that actually measures candidate latency, memory, energy or another consumed resource may opt in to resource tradeoff retrieval:

    "resource_profile": {
      "metric": "latency",
      "unit": "seconds",
      "scope": "candidate_inference",
      "protocol_sha256": "<SHA-256 of the fixed measurement protocol>",
      "value": 0.012
    }

All five fields are required and no others are accepted. Metric, unit and scope are nonempty strings of at most 128 characters; protocol_sha256 is a lowercase SHA-256; value is a finite nonnegative number. This interface always minimizes consumed resource; throughput or another higher-is-better quantity is not a direct input. Preserve measurement code, workload, warmup/repetition/aggregation policy, environment and inclusions/exclusions in the hashed protocol and raw result. The hash identifies a declaration, not proof that the measurement is valid.

The archive never infers this profile from elapsed_seconds, score components or an arbitrary --cost object. Evaluation elapsed time can include compilation, validation and orchestration; it is not automatically training, inference or algorithm latency. No profile means unknown in this view. Profiles are comparable only when metric, unit, scope, protocol hash and the complete ordinary development comparison match exactly; no implicit unit conversion occurs. Quality and resource must come from the same actual successful observation. The optional view leaves the scalar score and promotion protocol intact. See [retrieval semantics](iteration-trace.md#retrieve-measured-resource-tradeoffs).

## Comparability

Candidate comparisons require the same score-model version, evaluator and fixture hashes, workload/split, evaluation fidelity, seed protocol, and relevant measurement environment. Hash evaluation configuration separately from candidate configuration: candidate hyperparameters may differ, but comparisons must use the same evaluation protocol. For noisy workloads, preserve repetitions and compare matched cases. Report feasibility failures separately from low scores; invalid candidates are never promoted.

When estimating uncertainty, record which variation is modeled: sampling independent rows/groups, training/execution seeds, or new scenarios. A paired resampling interval conditional on fixed predictions does not measure training randomness or distribution shift. Define independent units, compute limits, practical improvement thresholds, and the confirmation protocol before interpreting comparisons; uncertainty diagnostics do not change the official objective.

## Family-Specific Checks

- **Algorithm/code:** compile and interface checks, property or differential tests, boundary cases, resource limits, and workload-level quality/time metrics.
- **Data/model:** train/validation/test provenance, leakage checks, fixed folds, prediction artifacts, and metric computation from predictions. Keep the final test split untouched and do not use public leaderboard feedback as a substitute for local validation.
- **Stochastic simulation:** fixed seed sets, repeated runs where needed, confidence or dispersion measures, and explicit feasibility gates.
- **Optimization/control:** exact constraint checks, objective components, solver status, and repeatable instance sets.

These are adapter requirements, not assumptions that every family is already implemented in this repository.
