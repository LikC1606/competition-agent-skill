# Resume and Choose the Next Action

Use this when continuing a run, recovering an interrupted trial, or deciding whether more research or diagnostics would help. The contract, append-only ledger, and immutable artifacts are the evidence; `next-action.md` is a replaceable summary. It neither grants extra budget nor establishes candidate validity.

## Recover Only What Changed

Read the sealed contract and the compact card first. Check the contract bytes against the card's hash and the ledger prefix against its checkpoint (byte length and SHA-256); these checks can read bytes without loading all events into model context. If both match, read only appended complete events and the evidence needed for the current decision. Verify the dependencies and validity scope of results you intend to reuse. A hash confirms identity, not training provenance or unchecked hard rules.

[`inspect_run_resume.py`](../scripts/inspect_run_resume.py) performs the byte/syntax checks for any adapter's JSON-object events. For the first inspection, omit `--checkpoint`; it reads from the start and can save a new checkpoint file:

```powershell
python <skill-dir>/scripts/inspect_run_resume.py `
  --contract <run>/task-contract.json --ledger <run>/trials.jsonl `
  --max-events 20 --save-checkpoint <run>/checkpoint-001.json
```

Reconcile the returned events and referenced evidence before linking that checkpoint from `next-action.md`. On the next inspection, use it and save to another new file:

```powershell
python <skill-dir>/scripts/inspect_run_resume.py `
  --contract <run>/task-contract.json --ledger <run>/trials.jsonl `
  --checkpoint <run>/checkpoint-001.json `
  --max-events 20 --save-checkpoint <run>/checkpoint-002.json
```

With `has_more: true`, continue reading pages before deciding from the card. A saved checkpoint covers only returned events and intervening blank lines, so later events are not silently skipped. Complete event lines must end in a newline (UTF-8, LF or CRLF); a missing final newline, malformed object, duplicate JSON key, or non-finite number blocks inspection, including malformed events beyond the output page. Contract changes, prefix rewrites, truncation, and wrong checkpoint paths also return code 2 without saving a new checkpoint. Reconcile the defect before rebuilding; omitting a bad checkpoint does not make stale evidence current.

The tool reports checkpoint/JSONL integrity only. It does not infer trial budget, validate candidate artifacts, promote candidates, run commands contained in events, or alter the ledger/card. A new checkpoint is a proposed anchor; saving it does not mean the returned evidence has been reconciled. Source appends during inspection remain for the next page. Existing checkpoint files are never overwritten. Legacy cards with manual byte/hash fields can be checked manually once, then replaced with a file produced by this tool.

If the card is missing, its prefix differs, or the contract changed, rebuild relevant state from the ledger and artifacts. Contract changes invalidate dependent conclusions; they do not erase spent trials. No new event does not prove that an unfinished evaluation failed: inspect its process and output directory before retrying. A successful result missing a completed event can be reconciled only after verifying its completeness, dependencies, and hard checks, then appending the recovered outcome. A truncated final event or partial result remains unresolved; do not invent a completion or overwrite old evidence. Resolve a ledger write failure before appending more events; preserve damaged bytes and record the repair.

For reused prediction CSV scores, [comparison with `--truth`](data-model.md#compare-local-scores) can audit recorded scores against frozen truth and snapshots once before relying on them. The ledger inspector's `ready` status does not perform this check. Reuse a passed audit only while its recorded dependencies match; preserve unaffected artifacts and redo the specific invalidated work.

Reconcile trials/time/compute, the confirmation/packaging reserve, incumbent scope, alternatives, unfinished work and frozen shortlist. Establish the origin and scope of a recorded limit: an explicit user cap, a skill default or an agent estimate. Preserve consumed work and never reset a user cap. Missing records do not establish extra allowance under an explicit limit; reconcile the gap conservatively.

After a completed default work round, a new user request to continue permits another bounded round under `SKILL.md` when no explicit user cap prevents it. Preserve the same task history and cumulative costs; record the new round and default limits prospectively, without rewriting old contracts or treating historical counts as a lifetime default cap. An old skill default is not itself a user-imposed limit. Actual user caps and explicit extensions remain binding at their stated scope. Never renew a round without a user request. If confirmation feedback guides new search, it becomes development evidence and fresh confirmation is needed.

## Route the Current Decision

Choose the first applicable condition; this is routing within the current run, not a sequence to replay every turn.

| Current state | Next useful action | Exit condition |
| --- | --- | --- |
| An unfinished trial may already have evidence | Reconcile its artifacts/process and actual cost | Record verified completion, interruption, or failure before another trial |
| Hard rules, score meaning, or comparison dependencies are unresolved | Resolve the specific contract/measurement defect | A trustworthy comparison path or an explicit provisional limitation |
| No credible action fits outside the reserve | Freeze/confirm the shortlist, or deliver if confirmation is done | Apply the sealed delivery rule; preserve remaining uncertainty |
| No valid credible baseline exists | Establish one affordable reference | Validity, objective, and measured cost for subsequent comparisons |
| Ranking or mechanism uncertainty prevents choosing a trial | Run a targeted diagnostic or matched repetition | A stated result changes promotion or identifies a testable mechanism |
| An affordable falsifiable mechanism is ready | Compare its route with the strongest affordable alternative, then execute the chosen test | Reject, advance to matched full fidelity, or identify missing evidence |
| Missing knowledge prevents a viable mechanism | Search for that specific gap | A source-backed test with prerequisites, or retire the route |

Resolve a rules/scoring defect within the authorized budget even when search is exhausted; do not report an invalid comparison as confirmed. An infrastructure failure warrants a bounded repair when useful, not a fresh algorithm conclusion. Repair variants consume trial slots; rerunning unchanged candidates consumes time/compute under the sealed protocol.

Before execution, ask: which observation changes the next decision, which evidence can be reused, and does implementation + execution + analysis + possible full-fidelity follow-up fit outside the reserve? Use measured costs where available and label estimates. No plausible decision change means defer that action. Full-fidelity promotion, provenance checks, and confirmation remain necessary even when intermediate work is cached.

For score-seeking runs, recover the current [route comparison](score-search.md#compare-routes-before-choosing-variants) as well as the incumbent. Recover each relevant route's tested maturity/resource setting and unresolved mechanism: promotion rank alone does not determine investment. Use [failure and maturity evidence](score-search.md#decide-whether-to-repair-deepen-or-retire) to compare a lagging route's bounded rescue with the leader's next refinement. A ready parameter variant is one option, not an automatic reason to defer a credible structural alternative. When recent gains are negligible, revisit the route's representation or mechanism. Preserve the route map across continuation; rebuild only when task conditions or new evidence change it.

Keep rejected hypotheses with their mechanism, prerequisites, and rejection evidence. Recover the applicable [comparison lessons](score-search.md#learn-from-evaluated-pairs), including contradicted predictions and local improvements that did not beat the incumbent. They should identify the next test or constraint, not replace artifact checks. Reopen a rejected hypothesis when a dependency, implementation diagnosis, or new source changes that evidence. A new filename or another request to continue is not new evidence. After a failure, revise the hypothesis or switch route; do not regenerate the same configuration through repeated broad searches.

After a trial is reconciled, apply [the feedback loop](score-search.md#close-the-feedback-loop) and return to the next useful action in the same round. A completed evaluation is a loop boundary, not an automatic delivery boundary. When resuming, recover the last feedback and whether its successor was actually implemented; a pending suggestion is not a completed iteration.

## Compact Decision Card

Refresh `<run>/next-action.md` after a decision or before a handoff, not after every tool call. Keep only facts needed for the next action and link to details; it is disposable and never replaces ledger events. The checkpoint covers complete JSONL events through the recorded byte offset. Later events must be reconciled before acting. Do not checkpoint a partial final line.

Use the fields relevant to the task; this is a copyable example, not a required adapter schema:

```markdown
# Next action

Contract: task-contract.json; SHA-256: <contract hash>
Ledger checkpoint: <checkpoint file, or verified byte length + prefix SHA-256>; last event: <trial/event/time>
Incumbent: <ID>; scope: <development/provisional/confirmed>; evidence: <result and checks>
Alternatives: <IDs and the uncertainty worth preserving>
Routes: <current/alternative routes; tested maturity/resource setting; unresolved mechanism; research.md section>
Budget: <limit origin/scope; round consumed / limits; cumulative costs; explicit cap remaining>; reserved: <confirmation + packaging>
Unfinished: <trial ID and output/process, or none>
Frozen shortlist: <path/hash, or not yet frozen>

Next action: <one action and parent IDs>
Feedback source: <trial/result path; measured comparison vs parent/best; validity and cost; prediction status>
Change scope and route choice: <method/pipeline replacement, mechanism refinement, tuning, or combination; why this route now>
Implementation target and prediction: <specific code/pipeline change; what the next result should test>
Prior outcome and investment: <promotion status; defect/cap/plateau evidence; why repair/deepen/retire/defer>
Applicable lesson: <research.md evidence; supported/contradicted/unresolved prediction; prerequisites still satisfied>
Evidence to reuse / invalidate: <paths, dependency hashes, affected descendants>
Execution: <command or implementation target, stage/fidelity, resource cap, total cost estimate>
If rejected / promising: <next branch, including full-fidelity cost when needed>
```

An old run needs no migration: rebuild a card only when resuming it. A tiny completed run may have nothing unresolved beyond delivery; do not create a new hypothesis queue just to fill the template. Source details stay in `research.md`, candidate history in `trials.jsonl`, and final selection in the frozen shortlist and delivery evidence. Record only aggregate confirmation outcomes needed for the delivery rule, never tuning suggestions extracted from confirmation errors.
