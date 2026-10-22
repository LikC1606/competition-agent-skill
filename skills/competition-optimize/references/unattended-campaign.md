# Run an Unattended Optimization Campaign

Use this when the user asks for continued optimization beyond one conversation turn. [autonomous_campaign.py](../scripts/autonomous_campaign.py) supplies a durable outer loop around Codex CLI. The skill and agent choose strategies; the task adapter produces scores; the driver decides whether to launch another invocation.

## Start in the background

Prepare a contest workspace containing rules, current source, a credible baseline and a runnable development adapter. Put the continuing objective and applicable constraints in a task file. Keep evaluated source/recipe snapshots and results immutable. Existing candidate records must use [candidate_archive.py](../scripts/candidate_archive.py)'s format; the driver verifies their identities before starting.

Linux, Python 3.10+ and an authenticated Codex CLI are required. Use the actual interpreter path if the environment wraps python3. Replace the example paths:

~~~sh
/usr/bin/python3 /path/to/competition-agent-skill/skills/competition-optimize/scripts/autonomous_campaign.py start \
  --workspace /path/to/contest \
  --task-file /path/to/contest/continuing-task.md \
  --campaign /path/to/contest/agent-runs/campaign-01 \
  --archive /path/to/contest/agent-runs/campaign-01/candidates.jsonl \
  --background
~~~

The campaign directory must not exist before start. The command returns after a detached supervisor becomes ready. It continues after the launching terminal closes and restarts a crashed manager. Omit --background to run in the foreground. The default agent sandbox is workspace-write; campaign/archive paths are added as writable directories. The driver uses the saved CLI authentication and does not use approval-bypass flags.

There is **no default campaign duration, candidate or turn cap**. Optional --max-turns, --max-tokens and --max-wall-seconds are explicit user limits. Token limits use the CLI's reported input plus output tokens and are checked between invocations, so one invocation can overshoot. Wall time starts at campaign creation and includes pauses/backoff. An optional --turn-timeout-seconds cancels one stuck invocation and proceeds through recovery; it is not a default campaign budget. Retry delays default to 5 seconds, increasing to 300 seconds; --retry-base-seconds and --retry-max-seconds configure them.

## Continuation and stopping

In default open-ended mode, **an agent cannot complete or block the campaign by declaration**. Its structured receipt describes what happened and proposes the next action. complete, blocked or an empty next action triggers a fresh-context strategy review. A plateau, a short candidate list or “no credible follow-up” is a reason to revisit the representation and implement another route.

Progress is derived from the archive, rather than receipt prose. The driver validates candidate schema/lineage, result bytes, source/recipe snapshots and implementation identity. Search notes and proposals are not executed candidates. Repeated measurements, random prediction bytes and renamed routes cannot reset the count of turns without a new executed implementation. After two such turns the driver alternates fresh strategy review with an execution-focused continuation and applies backoff. This ensures continuation and exposes stagnation; it cannot guarantee that the model will discover a useful algorithm or improve a contest score.

New implementations and objective improvement are separate signals. Under the latest development record's complete comparison contract, the driver replays first valid scored executions against their historical running best. By default, four distinct, valid implementations without a new best request a fresh-context strategy review. A recovery that still scores below the historical best, a route rename, or a promising/unresolved label cannot reset that signal. The first observation is a baseline, not an improvement or a failed attempt. Repeated measurements cannot supply a lucky new best. Invalid/unknown results, confirmation data, unsnapshotted implementations and manually declared scores absent from the adapter result do not count as comparable objective observations.

--stagnation-window N configures this review trigger. It requests another look at the strategy; it is not evidence that a route is exhausted, a candidate allowance, or a stopping rule. A successful review handoff consumes the current signal, so another objective-triggered review requires N new comparable implementations since that review. Review checkpoints are kept by complete comparison identity, including when switching away and back. Candidate promotion still follows the task's validation/repetition protocol.

Execution health is a separate signal: the latest failed/invalid/partial execution, or a successful run without a usable objective, enters `repair` immediately. The next invocation receives verified result errors/phases, log references, source identities and the nearest scored development ancestor when available; otherwise it may refer to an earlier development observation. A reference from another contract must be revalidated. Repair the responsible candidate, data or environment, or recover missing measurement evidence, while preserving the fixed evaluator. An unscored run does not disprove its method.

By default, three executions without a usable observation request a fresh repair review; --failure-review-window N changes this trigger at start/resume. Another execution-triggered review needs N new attempts since the preceding review. A later usable scored execution clears the failure streak even when its score is low; objective progress is judged separately. New result files from unchanged code can represent repair measurements, while reusing the same implementation/result path/hash cannot add another attempt. Confirmation, manual records and output-only/unsnapshotted artifacts do not drive this signal. This chronological health signal spans comparison changes because early failures can lack metric/evaluator metadata; it compares no scores and cannot terminate a campaign.

Comparison continuity separately tracks complete development contracts that still contain only one distinct, valid, scored implementation. It deduplicates first `(comparison, implementation)` observations, so aliases and lucky same-code repeats cannot create a reference. Measuring a different archived implementation under the same contract resolves the gap even without new code. Smoke/full switching is legitimate; when both receive references they leave no pending gap. Successful smoke runs do not erase unresolved full contracts. Confirmation, invalid executions, manual scores and output-only artifacts do not contribute.

By default, four newly observed contracts still lacking references since the last successful measurement-review handoff request a fresh `measure` context. --comparison-review-window N configures this threshold at start/resume. The window counts outstanding new gaps, with healthy evaluations allowed between them; it is not a consecutive-failure count. `comparison_recovery` identifies the actual isolated target, a different measured development ancestor or earlier reference, changed comparison fields and up to four recent isolated examples with omitted counts. Cross-contract cards contain verified identities and source/result pointers without objective values or feedback. Inspect the fixed task and intentional fidelity changes, then evaluate reference and candidate under an existing legal common development contract and record genuine results with a reuse reason as appropriate. Preserve the evaluator and compare only exact matching contracts. Execution repair takes priority; this evidence request neither rejects an algorithm nor stops fidelity exploration.

Objective, execution and comparison review checkpoints are prepared as durable `turn.review_checkpoints` intent, then committed only after a successful terminal event, exit zero and a valid receipt. An interrupted or rate-limited fresh review therefore does not mark its diagnosis as delivered; the next invocation still requests the due fresh review. Comparison review additionally requires intact target/reference retrieval pointers in the bounded packet. Its checkpoint retains the **pre-turn** distinct-observation count, so contracts first observed during that invocation remain eligible for the next review. A successful handoff does not resolve an isolated contract; only another measured implementation does. Older in-flight requests keep their original accounting behavior.

Independently, --session-checkpoints N starts a fresh context after N successful checkpoint batches (default 8); 0 disables periodic rotation. Rotation preserves the current work mode, next action, accepted archive, cumulative usage and campaign limits. Failed invocations do not count as successful checkpoints. The driver uses checkpoint counts rather than guessing context size from cumulative input tokens. These thresholds are engineering defaults, with no claim that these values optimize contest performance.

Before **every** invocation, including resume, the driver retrieves a development evidence packet and injects it directly into the prompt. turns/NNNNNN/context.json contains the archive prefix hash/size, task hash, objective progress, execution health/recovery, comparison continuity/recovery, best versions across selected routes, recent failures, unresolved feedback, parent-relative observed gains and relevant pending proposals. Score representatives share a complete comparison contract; cross-contract recovery cards supply identities for revalidation. Code/recipe and result identities accompany the displayed candidates. The latest candidate need not be the next parent or the isolated measurement target. Free-text feedback remains an interpretation tied to those candidates and that comparison; it is not a general causal rule. Confirmation feedback and pending proposals from other comparisons stay out of the active packet.

`review_frontier` retrieves up to two explicit open opportunities independently of the high-score routes, across all matched development implementations. Each retains its first valid scored representative, the feedback declaration and distinct executed/measured successor counts. Failed, unscored or explicitly unresolved children leave the opportunity open; only a measured changed child after its first declaration advances it. Route aliases and lucky repeated scores cannot create more opportunities. Inspect the branch and its attempted successors before choosing another implementation; this list is a retrieval aid, not a mandatory parent or a value estimate.

The driver rotates never-exposed and least recently exposed opportunities using `frontier_exposures` in state.json, keyed by complete comparison and implementation fingerprint. Exposure is committed only after the invocation has a successful terminal event, exit zero and an accepted receipt. Preparing or recovering a sealed request does not consume exposure; an interrupted handoff remains eligible. The candidate, feedback and latest-successor cards must retain their verified identities in the bounded packet. Exposure means evidence was handed off successfully, not that the model understood or acted on it. Existing states default to an empty exposure map; older in-flight requests finish unchanged.

Unfinished proposals use a separate `pending_proposal_exposures` map keyed by first-parent comparison and proposal ID. The packet retains the matching IDs and rotates up to four full details, with available/omitted counts. Its code targets and required reference identities must survive bounding before exposure can commit. Cross-contract development references are shown in `pending_references` with hashes and source/result pointers, without scores or original feedback; revalidate them under the intended evaluator. Foreign-only proposals and confirmation do not become active work. The prompt directs the agent to reconcile these proposals, execute a useful one or record a reason to stop it; exposure itself never closes work. `trace --proposal-id ID` retrieves full original targets when a detail or path was omitted. Old states default to an empty exposure map without changing archive bytes.

The packet is at most 48 KiB of UTF-8 JSON. Bounded fields and omitted routes/details are marked; the full archive and immutable artifacts remain available through brief/trace. Oversized nested metadata falls back to verified diagnostic pointers and contract hashes. Truncated IDs and paths are retrieval hints, not complete executable paths. Static task instructions precede changing evidence. No extra summarization model, embedding service or database is required.

Temporary CLI/network/receipt failures retry with a persisted retry_at and reconciliation instructions; three failures do not terminate the campaign. An unusable saved session is discarded. Observed authentication/configuration failures, unavailable host dependencies, changed control files or modified confirmed archive history block execution with evidence in the logs. Agent-reported missing ideas/dependencies alone do not establish these failures.

The campaign stops for a user stop request, an explicit resource limit, an observed host/evidence blocker, or a configured completion verifier. This driver does not perform official submissions.

## Observe, stop and resume

~~~sh
/usr/bin/python3 /path/to/scripts/autonomous_campaign.py status --campaign /path/to/campaign-01
/usr/bin/python3 /path/to/scripts/autonomous_campaign.py stop --campaign /path/to/campaign-01
/usr/bin/python3 /path/to/scripts/autonomous_campaign.py stop --campaign /path/to/campaign-01 --now
/usr/bin/python3 /path/to/scripts/autonomous_campaign.py resume --campaign /path/to/campaign-01 --background
~~~

status reports actual manager/supervisor process identity and liveness, active worker/agent heartbeat, accepted progress, reported usage, retry time, last result and next action. It also exposes the current comparison's best candidate/value, implementations since best, numbers of frontier implementations and pending proposals exposed, successful checkpoints in the current context, refresh count/reason and configured review/rotation thresholds. state.json is durable intent; a running status with dead processes is not itself proof that work is currently executing.

The normal stop finishes the current invocation. --now cancels the active local invocation and its owned children, including during a hung call. Both preserve accepted candidates. After inspecting an observed blocker or a stopped campaign, resume reconciles the same in-flight request before starting a successor. A running campaign rejects another manager/supervisor. Separate campaigns cannot simultaneously own the same canonical workspace or archive; use separate checkouts for independent searches.

Extend a previous limit with --max-turns N, --max-tokens N or --max-wall-seconds N on resume. --clear-max-turns, --clear-max-tokens and --clear-max-wall-seconds remove the corresponding limit. Cumulative records and usage remain. Limits cannot be rewritten by a second runner while the manager is active.

The same start/resume commands accept --stagnation-window and --session-checkpoints. For example, resume --campaign /path/to/campaign-01 --session-checkpoints 6 --stagnation-window 5 --background adjusts continuation policy without clearing history. Existing schema-v2 campaigns remain readable; an older in-flight request finishes with its original prompt, and automatic evidence packets begin with the next prepared invocation. Successful-checkpoint accounting starts when these fields become available.

## Optional task completion verifier

For a task with a concrete, externally checkable completion condition, configure --completion-check /path/to/check_goal.py at start. Without it, the driver never infers task completion from a score or a model's judgment.

The driver calls the fixed Python file using the same interpreter:

~~~sh
/usr/bin/python3 /path/to/check_goal.py --workspace /path/to/contest --archive /path/to/candidates.jsonl
~~~

The verifier must exit zero and write exactly this JSON shape to stdout:

~~~json
{"complete": false, "reason": "Declared target has not been reached", "evidence": ["/path/to/evidence.json"]}
~~~

It must judge the actual task contract, validity and metric identity without changing the workspace, archive or accepted artifacts. A true result requires a nonempty reason, existing evidence paths and an accepted executed implementation. The driver rechecks archived artifacts before accepting completion. Declare additional judge/rule/data dependencies with repeated --check-dependency PATH. The verifier and these dependencies are hashed at creation and checked before use; changing them blocks completion. Undeclared dependencies are not protected. --completion-timeout-seconds defaults to 60 seconds and is adjustable for a larger judge.

Verifier jobs use the same durable worker, inherited resource locks and process recovery as agent invocations. Their request, raw stdout (events.jsonl), stderr and exit marker live under turns/NNNNNN/completion/. Recovery handles a pending verifier before reconciling the original agent turn, including when both manager and verifier worker died. A manager restart adopts the existing check instead of launching another. Immediate stop and verifier timeout reclaim its owned children before another invocation can run. A failed verifier cannot certify completion.

This is a local workflow integrity check, not an isolation boundary against hostile code running as the same OS user. Use an isolated contest workspace for untrusted submissions; do not expose production credentials to candidate programs.

## Crash recovery and evidence

Each turn has a durable request token, prompt, launch intent, process markers, CLI events/stderr, final receipt and exit.json under turns/NNNNNN/. The worker owns an execution lock and passes the turn/resource locks to Codex. A manager crash adopts that invocation; a worker crash cannot launch a second Codex for the same launch intent. If the original exit status was lost, the outcome is marked interrupted even when a receipt exists. Acceptance requires the matching durable exit record, exit zero, unchanged output hashes, a successful turn.completed event and a valid receipt.

The prepared request seals the exact context packet and its SHA-256 before a process starts. Missing files can be materialized from that durable intent; recovery does not silently regenerate the packet from a later archive state. A changed packet, request or prompt blocks acceptance. Context counters and review checkpoints are saved with the in-flight request, so adopting a turn does not count another rotation or repeat its review.

Confirmed archive bytes are immutable. A malformed or torn **unconfirmed append** is copied into a hashed quarantine file and journaled before it is removed from the active archive. The confirmed prefix is retained; the next agent must recover artifacts from that evidence rather than blindly rerun. This is explicit suffix reconciliation, not permission to rewrite accepted history. Previously accepted artifacts are checked on startup and before task completion; new artifacts are checked when accepted.

The manager and supervisor publish heartbeats every two seconds. events.jsonl records transitions with stable outcome IDs; consumers should deduplicate event_id if a manager crashes between appending an event and saving state. state.json remains the accepted accounting state. Raw per-turn CLI events are retained for inspection; token totals cover reported terminal usage rather than a monetary billing guarantee.

The detached supervisor survives a terminal disconnect and restarts its manager. A host reboot or termination of the supervisor itself still requires resume, or an OS service manager configured to restart it. The driver supervises local process groups/owned descendants; adapters must reconcile remote jobs and schedulers separately. It does not provision compute, infer missing official score terms or make a proxy score an official result.

The CLI integration follows [OpenAI's non-interactive mode documentation](https://developers.openai.com/codex/noninteractive): structured JSON events, output schemas and explicit session IDs. Persistent lineage and measured feedback follow the [source-study patterns](source-patterns.md); third-party results are not performance guarantees for this implementation.
