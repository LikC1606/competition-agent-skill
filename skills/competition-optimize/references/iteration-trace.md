# Connect Feedback to Executed Changes

Use this when repeated trials are managed by `candidate_archive.py`. It links an agent-authored proposal to verified parent code and development feedback, then to a new adapter result. Existing equivalent ledger links are sufficient; do not migrate old trials or reconstruct proposals after seeing their results.

## Record One Actionable Proposal

Read the relevant parent code and matched feedback first. Choose the next implementation using the [proposal guidance](score-search.md#propose-from-code-and-history), with remaining budget and the nearest credible alternative in mind. Save one compact JSON proposal and link it from the decision card; do not also write a separate report or duplicate the proposal fields in other notes. For example, an algorithm candidate might use:

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
  "stop_condition": "Stop for reserve, an implementation defect without a useful repair, or no supported follow-up."
}
```

Replace the example path and hypothesis with this task's verified snapshot and evidence. `parent_ids` are the implementations being changed or combined; `feedback_from` are the development results that justify the choice, which may differ from the parent. `basis` records the agent's diagnosis and why this change follows from those observations. The script checks identities and links, not whether the diagnosis is scientifically correct.

For modeling, the parent record should include predictions as `--source` and a compact immutable training-code/recipe directory as `--configuration`; `code_targets` names a file inside that directory. For a source-only algorithm, it names the archived source. The proposal command verifies parent artifact/result bytes and binds the targets to parent snapshots. Unrelated files, changed parent bytes, unknown IDs and confirmation feedback are rejected.

```powershell
python <skill-dir>/scripts/candidate_archive.py propose `
  --archive <run>/candidate-archive.jsonl --proposal <run>/proposal-07.json
```

The proposal is now `pending`. Copy the parent into a new candidate directory, implement the change, check duplicates, and execute the adapter in the same work round. Preserve the parent snapshot. The tool does not run embedded commands, generate a method or grant a new budget. A missing code snapshot should be reconciled from the actual executed artifacts, rather than manufactured for the record.

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

Use the measured outcome, not the example's `promising`/`supported` labels. Failed implementations use `rejected` or `unresolved`, keep the failure, and do not establish method quality. The successor must match the proposal's parents and route, change the evaluated artifacts, supply a new completed adapter result and include feedback/prediction status. A parent with a separate pipeline snapshot requires changed code/recipe, so fresh predictions from unchanged training do not masquerade as an implementation change. Necessary unchanged measurement remains an ordinary record with `--reuse-reason`, rather than fulfilling a code-change proposal.

Different fingerprints alone do not prove a substantive algorithm change. The agent still reviews the code difference, hard rules, maturity, cost and full-objective comparison; do not edit comments or rename artifacts to satisfy the check. Adapter validity keeps its declared scope. Unknown total score and partial-rule coverage remain limitations even when an implementation ran.

When a proposed action cannot be run, preserve it as pending or close it with a concrete stop:

```powershell
python <skill-dir>/scripts/candidate_archive.py stop `
  --archive <run>/candidate-archive.jsonl --proposal-id complete-neighborhood `
  --reason "Only the confirmation reserve remains; this implementation cannot fit."
```

One proposal has one outcome. A repair or revised mechanism gets its own proposal, citing the previous development result. An interrupted process or partial adapter write stays pending until reconciled; do not mark it evaluated merely because a command was launched.

## Resume and Deliver the Actual Chain

```powershell
python <skill-dir>/scripts/candidate_archive.py trace `
  --archive <run>/candidate-archive.jsonl --recent 8
```

`trace` shows feedback -> proposed code change -> evaluated successor or stop. It verifies the displayed result and artifact identities once per candidate, reports prediction status and costs, and computes signed gain against parents only when valid scalar development results share the comparison identity. Missing/unknown scores and incomparable or invalid outcomes return no gain; they are not promoted. Positive gain is developmental evidence, not independent confirmation or proof of causation.

The default returns the last eight proposals and **all pending IDs**, so older unfinished work remains visible without loading every historical result into context. Use `--all` for a full audit. A proposal without a linked successor stays pending even if other candidates were evaluated. Legacy trials remain in the archive; absence of a prospective link does not mean they were never run.

On resumption, reconcile pending artifacts/processes before retrying. At delivery, include the compact actual chain, then follow the existing freeze/confirmation rules. A successful trace is evidence of linked execution, not grounds to end a round that still has a useful affordable successor.
