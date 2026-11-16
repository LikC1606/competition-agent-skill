# Competition Agent Skill

用于比赛解法的持续改进：从规则和强方案推导机制，实际修改代码或训练流水线，用匹配的评测比较，再把反馈接到下一项实现。技能入口是 [`competition-optimize`](skills/competition-optimize/SKILL.md)。

本轮按 [2026-11-10 重构方案](docs/refactor-plan-2026-11-10.md)实施，变更和验证见 [实施记录](docs/refactor-implementation-2026-11-10.md)。代码测试和集成演示不等于真实比赛提分；跨任务、多次运行的效果对照仍需独立实验。

## 当前能力

| 能力 | 已实现的范围 | 使用入口 |
| --- | --- | --- |
| 策略与迭代 | 读题、理解强方案、提出机制、实际实现与评测、复核反馈和后继 | [技能入口](skills/competition-optimize/SKILL.md)、[策略设计](skills/competition-optimize/references/strategy-design.md) |
| 候选证据 | 提案/结果关联、未决机会、诊断、条件经验、互补案例、资源权衡、配对复测 | [迭代档案](skills/competition-optimize/references/iteration-trace.md) |
| 无人值守 | 每轮按需上下文、完整证据卡、指令快照、进程恢复、档案接收与检查点 | [启动与恢复](skills/competition-optimize/references/unattended-campaign.md) |
| 固定时隙 C++ | 固定 workload 完整性、Clang AST 已声明规则子集、ZIP 字节核验 | [timeslot adapter](skills/competition-optimize/references/fixed-timeslot.md) |
| 预测文件 | 无权标量回归/二分类 CSV 评分、比较、错误分析和已有预测组合诊断 | [预测工具](skills/competition-optimize/references/data-model.md) |
| 数值表格训练 | 实际 fold 训练、OOF、group/time 检查、冻结模型、独立确认和提交 CSV | [训练 adapter](skills/competition-optimize/references/tabular-training.md) |
| LLM 与 Agent 方法指南 | 数据合成与蒸馏、后训练、推理预算、轨迹重放和职责分离；执行需题目 adapter | [专项指南](skills/competition-optimize/references/llm-agent-competitions.md) |
| 其它题型 | 共用档案与驱动；仍需对应的题目评测器 | [Adapter 合同](skills/competition-optimize/references/adapter-contract.md) |

不设置默认总轮数、总时间或费用上限；遵守比赛约束、实际资源和用户当前限制。默认实施有依据的机制改动，专门参数搜索需要明确请求。确认集不参与开发决策；正式提交/上传需要明确授权。

## 最短使用路径

将题目、当前实现、评测命令和已有结果放在比赛工作区，然后向 agent 描述目标与当前限制：

> 使用本仓库的 competition-optimize，继续改进这份解法。先恢复未完成试验，按现有开发协议运行真实候选，再据结果执行下一项改动。我补充的想法是……

如仅研究方案思路，明确说“只分析，不改代码”。如果当前没有可信评测器，先用已知正反例建立它。工具详情按题型和当前决策加载，不需要每轮读完整历史。

仓库脚本可直接运行，无须安装 skill。普通脚本使用 Python 3.10+；本次验证使用 `/usr/bin/python3` 3.12。数值训练需要独立的[可选依赖环境](skills/competition-optimize/references/tabular-training.md#setup-and-candidate-interface)。C++ 执行需要比赛 harness 和编译器，静态规则检查另需 Clang。

真实训练的本地集成示例：

```sh
/absolute/path/to/tabular-env/bin/python examples/tabular_training_pilot.py \
  --output-dir /absolute/path/to/new-pilot-directory
```

## 无人值守启动

先建立可运行 adapter 和开发 baseline。以下动作会持续调用已配置的 Codex；仅在用户请求无人值守执行时运行：

```sh
/usr/bin/python3 skills/competition-optimize/scripts/autonomous_campaign.py start \
  --workspace /absolute/path/to/contest \
  --task-file /absolute/path/to/contest/continuing-task.md \
  --campaign /absolute/path/to/contest/agent-runs/campaign-01 \
  --archive /absolute/path/to/contest/agent-runs/campaign-01/candidates.jsonl \
  --background
```

用 `status` 查看状态，`stop` 在本轮后停止，`stop --now` 取消当前执行，`resume --background` 对账后恢复；均指定同一 `--campaign`。模型 receipt 是检查点，完成须由配置的 verifier 证实。主机重启需恢复进程。具体参数、旧请求兼容和来源信息见[运行说明](skills/competition-optimize/references/unattended-campaign.md)。

## 本地安装与更新

本次重构不自动安装或改变全局配置。如需要本地发现，可在确认目标尚不存在后，将技能目录复制到 `~/.codex/skills/competition-optimize`。先选择并记录明确的仓库版本；更新前核对安装内容和当前运行任务。运行中的旧封存请求保留原引用，新轮次使用指令快照。

```sh
# 在仓库根目录执行；目标已存在时停止，避免覆盖本地修改。
test ! -e "$HOME/.codex/skills/competition-optimize" && \
  cp -a skills/competition-optimize "$HOME/.codex/skills/competition-optimize"
diff -qr skills/competition-optimize "$HOME/.codex/skills/competition-optimize"
git rev-parse HEAD
```

`git rev-parse` 只标识提交，不能代表未提交工作树。未提交版本另保留文件 hashes/差异；不要把当前改动宣称为基线提交的原始内容。更新方法和运行证据以已核对的文件为准。

## 文档与证据

- [本轮方案](docs/refactor-plan-2026-11-10.md)、[源码和一手资料依据](docs/refactor-evidence-2026-11-10.md)、[实施与验证](docs/refactor-implementation-2026-11-10.md)。
- 当前模块设计：[候选证据](docs/candidate-evidence.md)、[档案恢复](docs/campaign-archive.md)、[纯策略](docs/campaign-policy.md)。
- 历史设计和经验：[MVP](docs/mvp-plan.md)、[实际使用复盘](docs/execution-first-revision.md)、[源码研究](docs/source-study-20261022.md)。旧默认额度不适用于当前技能。
- 历史验证：[无人值守与恢复](docs/unattended-campaign-validation.md)、[工具效率](docs/efficiency.md)、[表格 pilot](docs/tabular-pilot.md)、[路线 pilot](docs/route-search-pilot.md)。当前不可访问的历史原始路径保留并标明复核边界，不补造数据。
