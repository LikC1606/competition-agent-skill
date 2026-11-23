<!-- README_SYNC: source=4e47943d568303dfb95221ba1a40e000ff053ba6; updated=2026-11-23 -->
<p align="center">简体中文 · <a href="./README_EN.md" lang="en">English</a></p>

# Competition Agent Skill

给已有比赛解法持续找改进方向，并用可比的本地评测检验。先定位限制当前效果的机制或证据缺口，再实现候选、留存记录，并依据评测结果决定下一步。技能入口是 [competition-optimize](./skills/competition-optimize/SKILL.md)。

<a href="https://github.com/LikC1606/competition-agent-skill"><img alt="GitHub stars" src="https://img.shields.io/github/stars/LikC1606/competition-agent-skill"></a>
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
<img alt="Codex Skill" src="https://img.shields.io/badge/skill-Codex-4c566a">
<a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-2f855a"></a>

欢迎[点 Star](https://github.com/LikC1606/competition-agent-skill) 收藏这套可审计的竞赛迭代工作流。

## 从现有工作区开始

把比赛规则、当前实现、评测命令和已有结果放在比赛工作区，让 Agent 读取上述 Skill。可以直接说：

> 用 competition-optimize 接着改进这份比赛解法。先对账未完成的实验，沿用现有开发协议，比对真实候选，并说明结果怎样影响下一项改动。

只需要理解强方案时，可以明确要求只分析。要做优化时，先检查本地评测是否覆盖规则、目标分布和必要的对照；开发结果用来选方向，独立确认集不参与开发决策。公榜和本地分歧时先诊断原因。提交、上传和无人值守运行分别需要对应授权。

## 运行一个离线例子

普通脚本需要 Python 3.10 或更新版本。若 `python3` 是容器包装命令，换成能访问比赛工作区的解释器。下例用四组**合成固定答案**演示投票和早停诊断，写出 `trace.json` 和 `report.json`，无需模型、网络或数值依赖。缓存回放不能证明比赛提分或实测耗时减少。

```sh
demo_root=$(mktemp -d "${TMPDIR:-/tmp}/competition-demo.XXXXXXXX")
python3 examples/inference_vote_replay.py --output-dir "$demo_root/replay"
```

要查看完整的表格训练路径，准备[数值环境](./skills/competition-optimize/references/tabular-training.md#setup-and-candidate-interface)，再运行这个实际拟合示例：

```sh
/absolute/path/to/tabular-env/bin/python examples/tabular_training_pilot.py \
  --output-dir /absolute/path/to/new-pilot-directory
```

## 按证据选择工具

| 现在要解决什么 | 入口 |
| --- | --- |
| 读强方案，确定可转用的机制 | [比赛资料](./skills/competition-optimize/references/competition-research.md) · [Kaggle 只读来源](./skills/competition-optimize/references/kaggle-sources.md) |
| 核对评分、验证切分和可比性 | [本地评测设计](./skills/competition-optimize/references/local-evaluation.md) · [题目 Adapter](./skills/competition-optimize/references/adapter-contract.md) |
| 比较候选、保存失败和恢复试验 | [决策路由](./skills/competition-optimize/references/decision-loop.md) · [迭代档案](./skills/competition-optimize/references/iteration-trace.md) |
| 处理预测文件或实际训练 | [CSV 评分/诊断](./skills/competition-optimize/references/data-model.md) · [表格训练](./skills/competition-optimize/references/tabular-training.md) |
| 核对固定时隙 C++ 合规性 | [时隙 Adapter](./skills/competition-optimize/references/fixed-timeslot.md)；需要比赛 harness，静态规则检查需 Clang |
| 检查 LLM 答案选择或推理策略 | [LLM 比赛](./skills/competition-optimize/references/llm-agent-competitions.md) · [投票回放](./skills/competition-optimize/references/inference-vote-replay.md)；真实推理需要题目专用 Adapter |

常规优化从有依据的机制改动开始；专门的参数搜索只在明确要求时进行。开发评测、独立确认及提交产物各自保留。方法总览见[比赛工作流设计](./docs/competition-workflow-design.md)。

## 已授权的无人值守运行

准备可执行的题目 Adapter 和开发 baseline，并确认工作区、归档位置与资源限制。以下命令会启动持续调用已配置 Codex 的后台进程，只有任务明确需要无人值守时运行：

```sh
python3 skills/competition-optimize/scripts/autonomous_campaign.py start \
  --workspace /absolute/path/to/contest \
  --task-file /absolute/path/to/contest/continuing-task.md \
  --campaign /absolute/path/to/contest/agent-runs/campaign-01 \
  --archive /absolute/path/to/contest/agent-runs/campaign-01/candidates.jsonl \
  --background
```

使用同一个 `--campaign` 查看 `status`、用 `stop` 停在本轮后、用 `stop --now` 取消本轮，或对账后 `resume --background`。模型回报是检查点，完成取决于配置的验证器。重启后按[运行与恢复说明](./skills/competition-optimize/references/unattended-campaign.md)恢复；按任务要求设置时长、费用和资源限制。

## 安装到本地 Codex

只运行脚本时无需安装 Skill。需要客户端发现时，在仓库根目录执行下列命令；已有目标须先比较版本并处理本地修改。

```sh
skill_dir="${CODEX_HOME:-$HOME/.codex}/skills/competition-optimize"
mkdir -p "$(dirname "$skill_dir")"
test ! -e "$skill_dir" && test ! -L "$skill_dir" && cp -a skills/competition-optimize "$skill_dir"
diff -qr skills/competition-optimize "$skill_dir"
git rev-parse HEAD
```

## 记录与许可

[实施记录](./docs/competition-improvement-implementation-2026-11-16.md)和[重构验证](./docs/refactor-implementation-2026-11-10.md)列出已运行的测试与集成示例。[竞赛策略研究](./docs/competition-skills-agents-research-report-2026-11-16.md)说明外部机制与采用边界；[表格 pilot](./docs/tabular-pilot.md)和[无人值守验证](./docs/unattended-campaign-validation.md)保存历史结果。上述证据验证工具与流程，实际排名收益仍要按题目评测。

本项目采用 [MIT 许可证](./LICENSE)。欢迎[提交 Issue](https://github.com/LikC1606/competition-agent-skill/issues)反馈可复现的问题，也可以[点 Star](https://github.com/LikC1606/competition-agent-skill)收藏。
