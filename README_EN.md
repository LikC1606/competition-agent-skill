<!-- README_SYNC: source=4e47943d568303dfb95221ba1a40e000ff053ba6; updated=2026-11-23 -->
<p align="center"><a href="./README.md" lang="zh-CN">简体中文</a> · English</p>

# Competition Agent Skill

Improve an existing contest solution by turning a concrete capability gap into an implemented candidate, then measuring it on a comparable local evaluation. The [competition-optimize Skill](./skills/competition-optimize/SKILL.md) records each trial and uses the measured evidence to decide what to investigate or implement next.

<a href="https://github.com/LikC1606/competition-agent-skill"><img alt="GitHub stars" src="https://img.shields.io/github/stars/LikC1606/competition-agent-skill"></a>
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
<img alt="Codex Skill" src="https://img.shields.io/badge/skill-Codex-4c566a">
<a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-2f855a"></a>

[Star this repository](https://github.com/LikC1606/competition-agent-skill) to keep this auditable contest iteration workflow handy.

## Start from the contest workspace

Put the rules, current implementation, evaluation command, and prior results in the workspace, then ask the agent to use the Skill. For example:

> Use competition-optimize to continue improving this solution. Reconcile unfinished trials, compare an implemented candidate under the current development protocol, and explain how the result changes the next step.

Ask for analysis only if you want to understand a strong entry. For optimization, first check that the local evaluation matches the rules, represents the target workload, and can distinguish the candidate from its controls. Keep confirmation data separate from development decisions. Diagnose disagreements between local and public leaderboard results before acting on them. Submissions, uploads, and unattended runs require their own authorization.

## Run an offline example

Ordinary scripts need Python 3.10 or later. If `python3` launches a container, use an interpreter with access to your contest workspace. The example below replays four **synthetic cached answer sets** to illustrate voting and stopping diagnostics. It writes `trace.json` and `report.json` without a model, network access, or numeric packages. Cached replay does not establish leaderboard gains or measured wall-clock savings.

```sh
demo_root=$(mktemp -d "${TMPDIR:-/tmp}/competition-demo.XXXXXXXX")
python3 examples/inference_vote_replay.py --output-dir "$demo_root/replay"
```

For the full tabular training path, prepare the [numeric environment](./skills/competition-optimize/references/tabular-training.md#setup-and-candidate-interface) and run the fitting example:

```sh
/absolute/path/to/tabular-env/bin/python examples/tabular_training_pilot.py \
  --output-dir /absolute/path/to/new-pilot-directory
```

## Pick a tool based on the gap

| What you need | Entry points |
| --- | --- |
| Read strong entries and identify a transferable mechanism | [Competition research](./skills/competition-optimize/references/competition-research.md) · [Read-only Kaggle sources](./skills/competition-optimize/references/kaggle-sources.md) |
| Check scoring, splits, and comparability | [Local evaluation](./skills/competition-optimize/references/local-evaluation.md) · [Task adapter](./skills/competition-optimize/references/adapter-contract.md) |
| Compare candidates, preserve failures, and resume trials | [Decision routing](./skills/competition-optimize/references/decision-loop.md) · [Iteration archive](./skills/competition-optimize/references/iteration-trace.md) |
| Score prediction files or fit a model | [CSV scoring and diagnostics](./skills/competition-optimize/references/data-model.md) · [Tabular training](./skills/competition-optimize/references/tabular-training.md) |
| Validate fixed-timeslot C++ runs | [Timeslot adapter](./skills/competition-optimize/references/fixed-timeslot.md); use the contest harness and Clang for static rule checks |
| Inspect answer selection or inference for LLM contests | [LLM competitions](./skills/competition-optimize/references/llm-agent-competitions.md) · [Vote replay](./skills/competition-optimize/references/inference-vote-replay.md); actual inference needs a task-specific adapter |

The default is to implement a mechanism with a concrete rationale. Request dedicated tuning explicitly. Keep development evaluation, independent confirmation, and submission artifacts distinct. See the [competition workflow](./docs/competition-workflow-design.md) for the overall design.

## Run an authorized unattended campaign

Prepare a working task adapter and development baseline, and check the workspace, archive, and resource limits. Run this only for a task that calls for unattended execution: it starts a background process that repeatedly invokes the configured Codex client.

```sh
python3 skills/competition-optimize/scripts/autonomous_campaign.py start \
  --workspace /absolute/path/to/contest \
  --task-file /absolute/path/to/contest/continuing-task.md \
  --campaign /absolute/path/to/contest/agent-runs/campaign-01 \
  --archive /absolute/path/to/contest/agent-runs/campaign-01/candidates.jsonl \
  --background
```

Use the same `--campaign` with `status`, `stop` after the current round, `stop --now` to cancel the current invocation, or `resume --background` after reconciling state. Agent receipts are checkpoints; completion depends on the configured verifier. Follow the [campaign and recovery guide](./skills/competition-optimize/references/unattended-campaign.md) after a restart, and set time, cost, and resource limits as the task requires.

## Install into a local Codex client

The scripts work directly in the checkout. To make the Skill discoverable, run this from the repository root; compare and reconcile existing local edits before replacing an installation.

```sh
skill_dir="${CODEX_HOME:-$HOME/.codex}/skills/competition-optimize"
mkdir -p "$(dirname "$skill_dir")"
test ! -e "$skill_dir" && test ! -L "$skill_dir" && cp -a skills/competition-optimize "$skill_dir"
diff -qr skills/competition-optimize "$skill_dir"
git rev-parse HEAD
```

## Records and license

The [implementation record](./docs/competition-improvement-implementation-2026-11-16.md) and [refactor verification](./docs/refactor-implementation-2026-11-10.md) index tests and integrated examples. The [competition strategy research](./docs/competition-skills-agents-research-report-2026-11-16.md) traces outside methods and their scope. The [tabular pilot](./docs/tabular-pilot.md) and [campaign verification](./docs/unattended-campaign-validation.md) document historical runs. These results verify specific tools and workflows; leaderboard gains must be measured on the target task.

Licensed under the [MIT License](./LICENSE). [Open an issue](https://github.com/LikC1606/competition-agent-skill/issues) for reproducible problems, and [star the repository](https://github.com/LikC1606/competition-agent-skill) to bookmark it.
