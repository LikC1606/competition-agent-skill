# Connect Feedback to Executed Changes

Use this when repeated trials are managed by `candidate_archive.py`. It links an agent-authored proposal to verified parent code and development feedback, then to a new adapter result. Existing equivalent ledger links are sufficient; do not migrate old trials or reconstruct proposals after seeing their results.

## Retrieve Evidence for the Next Implementation

```powershell
python <skill-dir>/scripts/candidate_archive.py brief `
  --archive <run>/candidate-archive.jsonl
```

Use this read-only view before opening more logs. It supplies one shared comparison identity, the best measured development representative, recent distinct implementations on the active route, best/latest versions of alternative routes, unresolved feedback, recent failure evidence and code/result paths. Candidate cards are included once even when several decisions reference them. Read the relevant function or pipeline at those paths, compare the mechanism with the retained failures, and choose a concrete next implementation. A successful retrieval does not complete an optimization request.

The default anchor is the latest development record. Use `--anchor <candidate-id>` to select the comparison and route for a different parent; this is not a historical cutoff. A failed latest experiment still retains the previous valid best under the same comparison. Early failures can lack metric/evaluator metadata and therefore anchor a different comparison; the unattended driver's separate recovery packet supplies verified diagnostics and a development reference without comparing their scores. `best_development` is a retrieval representative, not an incumbent promotion or a frozen finalist. Unknown scalar objectives keep their components and have no best-score ranking. Costs remain visible for the agent's investment decision.

The unattended driver also checks whether new complete contracts remain isolated with only one measured implementation. Its `comparison_recovery` can point to an earlier isolated target even when the latest record is a healthy smoke run. Retrieve the cited snapshots and establish a common legal development contract before comparing reference and candidate. A genuine new result from archived code may supply the missing comparison with `--reuse-reason`; it remains a measurement of that implementation and does not fulfill a code-change proposal. Cross-contract cards carry identities and pointers without scores or original feedback.

Scored candidate cards share the exact evaluator, workload/split, score model, evaluation configuration, stage, environment and objective metadata. Pending proposals can also cite development references under another contract: these receive separate identity/pointer cards without scores or original feedback. Confirmation records do not change this view, including selection, ordering and counts. Score ordering uses the first valid comparable observation of each **implementation identity**, so stochastic output changes and renamed routes cannot create a new best implementation. Repeated measurements stay visible as measurements; use the task's uncertainty/aggregation procedure when they matter rather than promoting the luckiest observation.

For `prediction_csv` results with a complete training-code/recipe directory, implementation identity uses that directory; prediction bytes retain a separate artifact fingerprint. An adapter can declare `candidate_scope: generated_artifact` for other produced outputs or weights, with its executable recipe likewise saved as `--configuration`. For evaluated algorithm source, identity includes source and supplied configuration, so changing the source while retaining settings is a real implementation change. The tool uses declared artifact scope, without guessing from a filename. Changing output scope labels alone does not create a new recipe.

Cards expose `implementation` and earlier same-comparison `reused_implementation_from` IDs. Routes report measurements and distinct artifact fingerprints separately from distinct implementations. Output-only records retain their scores but have a null implementation count and a diagnostic route review; reconcile the actual executed recipe before proposing a code change. These identities assume a complete snapshot: capture intended candidate arguments, feature/data choices and dependency identities in the recipe, while storing declared measurement seeds and run logs separately. Hash equality does not prove that provenance is complete. Earlier costs remain binding, as do user limits that still apply.

New disk events store fixed-size `reuse_links` summaries (first ID, previous ID and count) for artifact and implementation reuse. Existing events remain byte-for-byte intact. `record` still returns complete reuse lists; `brief` reconstructs the displayed lists from actual history, while `read_records` leaves compact events unexpanded. Use the upgraded `brief` with compact events. This removes quadratic repeated-ID storage; a record call still scans history and its complete CLI output can grow with that history.

The active route is always shown; alternatives are ordered by their measured representatives in the declared direction. Separately, `review_frontier` retrieves open opportunities from the complete matched development history, including older candidates on the same route and routes outside the score list. An opportunity requires a valid scored execution, a code/recipe snapshot, a promising/unresolved status and explicit feedback. Its representative is the first valid scored execution of that implementation; `feedback_candidate_id` can point to a later measurement that first declared the opportunity. Renaming a route or repeating an implementation does not create another opportunity or replace its representative with a lucky score.

Frontier entries show distinct executed successor implementations, measured successor counts and the latest successor's verified card. Only a measured changed child after the implementation's first opportunity declaration, with a prediction status other than `unresolved`, advances the old opportunity. Failed, partial, unscored and explicitly unresolved children preserve it; an older child cannot close a newly declared opportunity. Repeated declarations cannot revive an opportunity already advanced by a real successor. Legacy measured children without a prediction status retain their previous closing behavior. These links track implementation progress, not proof that feedback was correct or the whole method was exhausted.

Frontier retrieval orders never-exposed implementations first, then least recently exposed ones; archive declaration order breaks ties. The unattended driver supplies successful-checkpoint exposure turns, separately for each comparison contract. Direct `brief` calls are read-only and do not advance exposure, so repeated standalone calls keep archive order. This retrieval order does not select the next parent: inspect objective headroom, unresolved mechanisms, prior children, maturity and cost.

Defaults display four routes, four recent distinct active-route candidates, four matching pending details and two frontier opportunities. `--routes`, `--recent` and `--frontier` change retrieval size only; `--frontier 0` disables the extra selection. They are not candidate budgets or method settings. Older best representatives are retained even outside the recent window. Each displayed route includes its latest failure/rejection; use the archive's referenced records for an older relevant mechanism. Omission counts make the retrieval scope explicit.

Pending work belongs to its **first parent's complete comparison**. List that parent first when proposing a repair or transfer; other development parents and feedback may come from different contracts. The brief keeps their verified implementation, source/recipe paths and result identities in `pending_references`, with `requires_revalidation: true`; their objectives and original feedback stay out of the active score evidence. A repaired successor may acquire a complete scoring contract that the failed parent lacked. Confirmation references remain forbidden.

Standalone `brief` retains all pending IDs and the latest matching details; `matched_pending_proposals` and `pending_summary` identify the active subset and omissions. The unattended packet includes only IDs assigned to the active comparison, then rotates details by successful exposure. It starts with never-exposed work, then the least recently exposed, breaking ties by archive order. Exposure does not fulfill or stop a proposal. Inspect existing artifacts before executing still-useful work or record an explicit stop reason; unchanged code and old results cannot fulfill it.

Use `trace --archive <path> --proposal-id <ID>` to recover one original proposal outside either retrieval window, including its full `code_targets`, validation, stop condition, input hash when recorded, and current outcome. This checks only the selected proposal's evidence, returns an explicit error for an unknown ID, and leaves the archive unchanged. `trace` is an audit view and may show its development references' original contracts and scores; do not treat cross-contract scores as active ranking evidence. A missing original input hash remains null rather than being reconstructed. Reconcile unarchived processes/outputs separately; exact retrieval does not prove that a partial implementation ran.

The command checks displayed result and snapshot bytes once per candidate and checks shown pending code targets. It does not rehash unselected history or alter the archive. Missing identity fields are labeled `not_recorded`; legacy evidence does not gain verification merely by appearing in a brief. Adapter validity keeps its checked scope, and score recomputation, training provenance, unchecked hard rules and causal interpretation still require their existing evidence. Reference raw results when detailed errors or components are needed; there is no need to write another summary document.

## Record One Actionable Proposal

Read the relevant parent code and matched feedback. Choose the next implementation using the [task/code/history proposal guidance](score-search.md#propose-from-task-structure-code-and-history), with applicable resource constraints and the nearest credible alternative in mind. Save one compact JSON proposal and link it from the decision card; do not also write a separate report or duplicate the proposal fields in other notes. For example, an algorithm candidate might use:

```json
{
  "proposal_id": "complete-neighborhood",
  "parent_ids": ["cand-03"],
  "feedback_from": ["cand-03", "cand-05"],
  "route": "block-neighborhood",
  "code_targets": ["D:/competition/run/cand-03/solution.cpp"],
  "basis": "Matched results show the pair-swap search stalls with a remaining block-assignment gap; the prior cache change did not alter that limitation.",
  "change": "Implement the complete block reassignment neighborhood and its constraint-preserving decoder.",
  "expected_observation": "Valid block changes escape the stalled state and improve the full development objective within the legal runtime.",
  "validation": "Use the unchanged evaluator/workloads; check constraints, score components and total runtime against parent and incumbent.",
  "stop_condition": "Stop on user request, an applicable hard/resource constraint, an observed unresolved blocker or verified task completion. An exhausted route triggers strategy review."
}
```

Replace the example path and hypothesis with this task's verified snapshot and evidence. `parent_ids` are the implementations being changed or combined; `feedback_from` are the relevant development results, which may differ from the parent. `basis` explains why the change follows from task facts, sources or observations. For a new task-derived route, the baseline can supply comparison context in `feedback_from`; put the independent derivation and component dependencies in `basis` without inventing a measured bottleneck. No extra schema or prior successful trial is required. The script checks identities and links, not whether the diagnosis is scientifically correct.

For a user-inspired proposal, include the short original idea or its message/note reference and the interpreted mechanism in `basis`; this text is retained in both `brief` pending details and `trace`. Keep `feedback_from` bound to actual development candidate IDs, including a baseline when needed, rather than inventing a result ID for a user message. Extra arbitrary proposal fields are not retained by the helper. After execution, connect the measured outcome back to the tested idea in `--feedback`. Follow [user-idea handling](score-search.md#turn-user-ideas-into-experiments) when deciding priority or handling new input.

For modeling, the parent record should include predictions as `--source` and a compact immutable training-code/recipe directory as `--configuration`; `code_targets` names a file inside that directory. Evaluated predictions are outputs, not code targets. For an algorithm, the target can name the archived source or an applicable configuration file. The proposal command verifies parent artifact/result bytes and binds the targets to the executable snapshots. Unrelated files, changed parent bytes, missing produced-output recipes, unknown IDs and confirmation feedback are rejected.

```powershell
python <skill-dir>/scripts/candidate_archive.py propose `
  --archive <run>/candidate-archive.jsonl --proposal <run>/proposal-07.json
```

The proposal is now `pending`. Create an isolated candidate directory, implement the change, check duplicates, and execute the adapter now. Copy the needed parent components or build a standalone replacement behind the same interface; preserve the parent snapshot. The tool does not run embedded commands, generate a method or impose/renew a budget. A missing code snapshot should be reconciled from the actual executed artifacts, rather than manufactured for the record.

## Attach the Measured Outcome

After evaluation, explain the actual observation and whether the prediction was supported, contradicted or unresolved. Attach the proposal when recording the candidate:

```powershell
python <skill-dir>/scripts/candidate_archive.py record `
  --archive <run>/candidate-archive.jsonl --candidate-id cand-07 `
  --parent cand-03 --proposal-id complete-neighborhood `
  --source <run>/cand-07/solution.cpp --result <run>/cand-07/result.json `
  --route block-neighborhood --mechanism "complete block reassignment" `
  --status promising --prediction-status supported `
  --feedback "Valid block moves escaped the stalled state; runtime cost and the full score determine further investment."
```

Use the measured outcome, not the example's `promising`/`supported` labels. Failed implementations use `rejected` or `unresolved`, keep the failure, and do not establish method quality. The successor must match the proposal's parents and route, change the evaluated artifacts, supply a new completed adapter result and include feedback/prediction status. Produced outputs require a changed executable recipe: fresh predictions from any unchanged parent cannot fulfill a code-change or combination proposal. Algorithm source may change while its ordinary configuration stays fixed. Necessary unchanged measurement remains an ordinary record; an exact artifact repeat uses `--reuse-reason`. The archive automatically links different output bytes from the same complete recipe as repeated implementation measurements.

Different fingerprints alone do not prove a substantive algorithm change. The agent still reviews the code difference, hard rules, maturity, cost and full-objective comparison; do not edit comments or rename artifacts to satisfy the check. Adapter validity keeps its declared scope. Unknown total score and partial-rule coverage remain limitations even when an implementation ran.

When a proposed action cannot be run, preserve it as pending or close it with a concrete stop:

```powershell
python <skill-dir>/scripts/candidate_archive.py stop `
  --archive <run>/candidate-archive.jsonl --proposal-id complete-neighborhood `
  --reason "The required input data is unavailable after checking the declared source; preserve this proposal until the blocker is resolved."
```

One proposal has one outcome. A repair or revised mechanism gets its own proposal, citing the previous development result. An interrupted process or partial adapter write stays pending until reconciled; do not mark it evaluated merely because a command was launched.

## Resume and Deliver the Actual Chain

```powershell
python <skill-dir>/scripts/candidate_archive.py trace `
  --archive <run>/candidate-archive.jsonl --recent 8
```

`trace` shows feedback -> proposed code change -> evaluated successor or stop. It verifies the displayed result and artifact identities once per candidate, reports prediction status and costs, and computes signed gain against parents only when valid scalar development results share the comparison identity. Missing/unknown scores and incomparable or invalid outcomes return no gain; they are not promoted. Positive gain is developmental evidence, not independent confirmation or proof of causation.

The default returns the last eight proposals and **all pending IDs**, so older unfinished work remains visible without loading every historical result into context. Use `--all` for a full audit. A proposal without a linked successor stays pending even if other candidates were evaluated. Legacy trials remain in the archive; absence of a prospective link does not mean they were never run.

Legacy records need no rewrite. Known prediction scope and existing recipe hashes supply their implementation identity when available; older linked outcomes retain their original acceptance scope. The evidence view labels an unavailable recipe, and prospective code-change proposals require the actual executed snapshot. A legacy output link alone does not establish that its source code changed.

On resumption, reconcile pending artifacts/processes before retrying. At delivery, include the compact actual chain, then follow the existing freeze/confirmation rules. A successful trace is evidence of linked execution, not grounds to stop while a useful feasible successor remains. Retrieval window sizes never limit the number of optimization iterations.
