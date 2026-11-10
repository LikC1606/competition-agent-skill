# 2026-11-10 重构实施与验证

基线提交：`80331a1`。按 [重构方案](refactor-plan-2026-11-10.md)实施；代码改动保留在当前工作树，未提交 commit，未安装到全局技能目录。以下逐项记录工程交付与实际证据，工作流提分效果另列。

## 已实施

| 阶段 | 实现 | 关键兼容约束 |
| --- | --- | --- |
| P0a | `review_opportunities` 共用规则，`decide`/`brief` 不再被失败、无分数、未解决或独立构造后继误关闭机会 | 保留不同入口的展示窗口、旧手工 advisory 记录 |
| P0b | `timeslot_workloads` 定义固定预期集合，producer/reader 分别验证完整性；新结果 schema 3 | 完整 schema 2 short/full 可读；旧缺行记录明确拒绝 |
| P0c | `timeslot_rules` 使用 Clang AST；`rules`/`package` 分开；不可用时非零退出并标明覆盖范围 | 打包仅证明字节一致，规则子集通过不代表全部规则或正确性通过 |
| P1a | `ResultEvidence` 统一解码/声明冲突/用途；`prediction_core` 收拢评分与比较、解除 CLI 依赖环 | candidate JSONL schema 1、原字段/CLI 入口保留；evaluator identity 包括抽出的核心 |
| P1b | `EvidenceSnapshot`/`BriefQuery` 负责查询与文件核验；trials 直接调用证据 Interface | 旧查询 facade 保留；纯回放和本次文件核验职责仍分开 |
| P1c | SKILL 主循环和路由精简；`campaign_prompt` 按 mode/实际证据加载；`campaign_handoff` 选择完整卡片 | 身份/路径/封存报告不截成无效字符串；成功交付后才计曝光 |
| P1d | `campaign_state`、`TurnLifecycle`、`CodexInvocation`、实际指令 package 快照 | campaign schema 2、旧在途封存请求、恢复/接收顺序保留；工作流来源不进入候选比较身份 |
| P2a | `tabular_training` 实际拟合、OOF、group/time、稳定 recipe、冻结模型与最终 CSV | 旧 score-only 工具仍独立可用；新 adapter 限于数值表格标量回归/二分类 |
| P2b | 混合档案先测量；显式 evidence bundle/path resolver 支持原身份迁移 | 不重写原 JSONL、绝对路径或 seal；未导出引用明确报缺失 |

性能方面未引入数据库、跨轮缓存或通用工作流框架。已测混合档案、学习记录、测量计划、长反馈和大 case-profile；准备/接收段另在混合档案上实测。10,000 条历史及每种压力场景的全链路矩阵未覆盖，不能外推容量承诺。

## 真实训练与技能前向

新增 [`examples/tabular_training_pilot.py`](../examples/tabular_training_pilot.py) 在 sklearn 内置的原始 Diabetes 特征上实际训练三折基线和树模型。预处理只在训练折内拟合，开发预测覆盖声明的全部 OOF 行；选择发生在独立确认前。

| 项目 | 结果 |
| --- | --- |
| 线性基线 OOF RMSE | 54.6126149709249 |
| 树模型 OOF RMSE | 56.69207389768578 |
| 开发选择 | 保留基线，挑战者未改善 |
| 冻结基线的独立确认 RMSE | 57.218155324952875 |
| 最终 CSV | 89 行，ID/顺序/列格式与 sample 一致 |

这是固定的本地集成演示。它验证真实训练、选择、冻结和交付，没有证明新工作流比旧版更会寻找解法。当前 adapter 保存训练行、模型字节和候选源码；任意候选 Python 并未沙箱隔离，上游特征泄漏、过往确认集曝光和比赛数据许可仍需具体任务核查。

独立 agent 又按精简后的技能完成一个分组合成回归任务：144 个开发样本、48 个组、三折；baseline OOF RMSE **2.5271673535**，唯一二次特征候选 **0.6699609412**。只依据开发结果选候选，冻结后才读取确认标签；12 个新组、36 个样本的确认 RMSE 为 **0.7032232813**，最终 CSV 顺序与 sample 一致。共六次 fold fit、六个主要 CLI 操作，首次均成功，实测 CLI wall time 合计 2.20 s；这不包含 agent 思考时间。

没有运行 baseline 确认分数，因此不能据此声称确认集相对提升。前向执行使用执行前的完整工具快照，保留实际版本；该快照早于后来补充的 `recipe.json` 辅助产物及证据搬迁路由，后两者由最终合并测试覆盖。报告和产物在 [持久证据目录](/home/lzh/workspace/competition-agent-validation/refactor-20261110/forward-task/REPORT.md)。

## 验证记录

最终合并回归 **591 项全部通过，无跳过，196.097 s**；进程 wall time 196.32 s，峰值 RSS 182,312 KiB。命令与 [原始输出](/home/lzh/workspace/competition-agent-validation/refactor-20261110/final-tests.log) 一并保留：

```sh
PYTHONDONTWRITEBYTECODE=1 \
CLANGXX=/tmp/timeslot-clang18/usr/lib/llvm-18/bin/clang++ \
/tmp/competition-skill-refactor-20261110/ml-env/bin/python -m unittest discover \
  -s skills/competition-optimize/tests -q
```

本次使用可选 ML 隔离环境，使实际训练测试也参与整套回归，依赖固定在 `scripts/requirements-tabular.txt`。运行了 skill quick_validate、40 个 Python 源文件语法检查、五份入口/引用文档的本地链接检查及 `git diff --check`。隔离安装副本与源字节一致，五个公开 CLI 的 `--help` 在不含 ML 包的系统解释器下通过。

从 `80331a1` 独立提取旧 scripts，在相同 100 / 1,000 条原始档案及相同 artifact 路径上，与新版 `EvidenceSnapshot` 直调比较 brief、observed brief、全量 trace、最近 trace、trials，**10 组输出精确一致**，没有删字段或路径归一化。另有定向回归覆盖批准修正的 P0 行为差异。

恢复测试包含 manager/worker/verifier 中断接管、避免重复启动、CLI 失败后合法结果仍接收、旧 schema-v2 请求、来源快照被修改时阻断。新增 bundle 的九项测试覆盖搬迁后删除原目录、篡改、未导出引用、review/learning 原 seal、原路径后来成为 symlink 等行为。以上均为本地受控进程，不是跨日实际服务可靠性证明。

全套回归显式使用临时提取的真实 Clang：`CLANGXX=/tmp/timeslot-clang18/usr/lib/llvm-18/bin/clang++`。没有此依赖时静态 AST 集成测试会明确 skip，实际 `rules` CLI 则失败并说明不可用，不伪报通过。测试中的 C++ harness 是本地受控 fixture，不是官方比赛成绩。

档案基准初次测量（固定混合内容，单机局部结果）：

| 记录数 | 构建 | parse 中位数 | brief 中位数 | recent trace | trials |
| --- | --- | --- | --- | --- | --- |
| 100 | 0.645 s | 14.5 ms | 10.8 ms | 3.25 ms | 2.72 ms |
| 1,000 | 19.703 s | 143.9 ms | 73.9 ms | 3.43 ms | 14.02 ms |

构建与查询是不同操作，不能用此表声称完整 campaign 提速。原始测量与独立差分分别见 [benchmark JSON](/home/lzh/workspace/competition-agent-validation/refactor-20261110/archive-query-benchmark.json) 和 [差分 JSON](/home/lzh/workspace/competition-agent-validation/refactor-20261110/archive-query-differential.json)。1,000 条原始档案及引用文件另通过新 export/resolver 导出为持久 bundle，实际查询得到原 anchor 和最近八条 trace。

压力历史补测均使用合法录入/封存/回放，三次样本；学习/计划场景实际执行本地确定性程序，profile 数据为合成 fixture：

| 场景 | 记录规模 | parse 中位 | brief 中位 |
| --- | --- | --- | --- |
| Learning-heavy | 100 / 1,000 | 27.6 / 362.9 ms | 22.2 / 113.0 ms |
| Plan-heavy | 100 / 1,000 | 49.0 / 2,861.0 ms | 7.3 / 50.6 ms |
| 长反馈 | 100 / 1,000 | 22.0 / 235.1 ms | 21.1 / 192.7 ms |
| 大 case-profile | 100 个候选 × 每个 10,000 cases | 22.6 ms | 无追踪 1.522 s；带追踪 13.943 s |

除特指无追踪外，包含 tracemalloc 和读取计数开销；大 profile 的纯 wall 三次为 1.508 / 1.522 / 1.525 s。Plan-heavy 的压力成本主要在构建和全量语义回放，不能把 brief 时间当作完整读取成本。当前证据支持保留这些已量测开销，尚不足以确定新增跨轮缓存的实际收益，因此不引入索引/数据库。详细 I/O、峰值分配和样本见 [压力基准](/home/lzh/workspace/competition-agent-validation/refactor-20261110/archive-profile-benchmark.json)；四类原始 fixture 均已导出并核验为可迁移 bundle，大 profile 的 bundle 查询也实际通过。

同一 mixed fixture 的准备/接收路径，三次中位数如下。准备段覆盖 confirmed→Policy.prepare→prepare_handoff→confirmed 退出校验；不含 workflow 快照、prompt、持久化和 CLI。接收段验证实际追加的一个候选，运行程序与追加本身在计时范围外。

| 事件数 | 准备时间 | 准备读取 bytes / 次数 | 接收时间 | 接收读取 bytes / 次数 |
| --- | --- | --- | --- | --- |
| 100 | 34.56 ms | 478,068 / 23 | 34.36 ms | 635,756 / 7 |
| 1,000 | 262.25 ms | 4,615,858 / 25 | 340.91 ms | 6,152,831 / 9 |

原 fixture 的 1,406 个文件前后 hash 不变。Python 峰值内存、全部样本及逻辑读取定义见 [路径 benchmark](/home/lzh/workspace/competition-agent-validation/refactor-20261110/campaign-path-benchmark.json)。这些计时包括 tracemalloc/读取统计开销，不代表完整轮次性能。

同一空 context、相同路径的提示字节对照（UTF-8，不是 token）：

| mode | 原版 | 新版 | 减少 |
| --- | --- | --- | --- |
| work | 9,944 | 2,231 | 77.56% |
| repair | 11,079 | 2,657 | 76.02% |
| rethink | 10,339 | 2,471 | 76.10% |
| measure | 10,992 | 2,559 | 76.72% |

SKILL.md 从 24,546 降至 11,804 字节，减少 51.91%。必要身份、路径和封存报告完整性由行为测试核验，不能由字节减少推断模型成本或策略质量改善。

## 文档、安装与证据边界

README 已改为能力表、最短使用路径、无人值守入口和文档导航。早期研究/MVP 中的额度规则已标注历史范围。两份历史文档涉及的旧绝对路径在当前机器不存在，原文保留并注明不可重验；没有修改旧证据身份或补造原始文件。

提供了复制安装和字节对照方法，但没有自动安装。当前未提交工作树不等于基线提交的内容；应以实际文件 hashes/差异追溯本轮实现。新工作流快照冻结实际指令和支持脚本，旧在途请求的实时引用不可能凭 hash 复原旧内容，恢复记录明确披露该边界。

方案中的旧/新版本、独立题目、至少三次匹配运行的成对效果实验尚未执行。也没有真实平台提交、付费持续 campaign 或跨日可靠性新证据。本轮不把测试数量、提示字节下降或一次合成任务成功表述为比赛提分结论。
