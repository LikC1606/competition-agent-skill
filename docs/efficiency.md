# 流程与评测效率

2026-10-10 的改动覆盖入口上下文、实验选择、任务恢复、批量评分和预测抽样评测。计分 evaluator 未改动，因此既有预测评测仍可通过原 hash 契约复用；抽样 estimator 的源码 hash 随实现更新。

## 少做重复工作

`SKILL.md` 从 943 个空白分隔词精简到 651 个，约减少 31%。保留任务契约、评分核验、预算、候选证据、独立确认和交付要求；按题型与当前动作读取详细参考，避免每轮加载所有工具说明。

新增的决策原则是先做便宜的有效分数比较，再按当前问题使用误差切片、profile、bootstrap 或训练重复。明显被否定的候选保留拒绝证据；排名接近、误差互补或机制不明确时再做相应诊断。以各阶段实测成本安排预算，并复用仍满足依赖条件的 baseline、来源和中间产物。

例如，只改集成权重可复用成员预测；只修正评分公式可复用未变的模型与预测，但重算评测；改 split 或训练特征需要重做依赖该变化的拟合和预测。固定预测 bootstrap 的缓存不允许跨模型、split 或配置盲目复用，也不会把旧开发证据变成独立确认。

规则见 [实验效率](../skills/competition-optimize/references/score-search.md#avoid-work-that-cannot-change-the-next-decision) 和 [预测缓存依赖](../skills/competition-optimize/references/data-model.md#establish-training-and-validation-evidence)。这些流程调整尚未单独测量完整 agent 的时间或提分效果。

## 从当前状态继续实验

主入口改为“新建/恢复 → 决策循环 → 确认/交付”，新建任务的评分核验不再表现为每次继续都要重做的固定阶段。`next-action.md` 保存契约 hash、账本完整事件的字节检查点及前缀 hash、当前候选、已耗预算、未完成实验和一个下一步动作；详细来源、日志和结果仍在原文件。恢复时核验检查点后只补读新增事件，检查点过期或缺失则从证据重建。卡片可重写，历史事件与评测产物保持不可变。

[恢复路由](../skills/competition-optimize/references/decision-loop.md) 先处理未完成实验与口径缺陷，再决定执行、诊断、定向搜索或冻结确认。执行前把实现、执行、分析和可能的完整评测成本一起与剩余预算比较。已准备好可证伪假设时停止泛搜；没有新证据时不重复已被否定的配置。默认候选额度按完整 run 计算，继续对话不会重置额度；显式单列 baseline 的已有契约仍按原预算执行。

复用两个真实 pilot 的历史记录，按不同断点做人工流程回放及产物核对，未训练模型、未改原记录：

- **评测已完成但 completed 事件未写入**：核验实际预测、模型/配置、训练行、split 和 evaluator hash，先补齐已发生的结果；原试验占用保留，无需重新拟合。
- **开发阶段已完成三个 challenger**：两题均剩余 0 个 challenger，沿用冻结 shortlist 的确认协议；不因继续任务增加第四个变体。
- **确认结果与开发资格冲突**：Breast Cancer 的 blend 确认指标更好，但开发阶段不符合已声明的晋升条件，因此仍按冻结规则保留 baseline；Diabetes 仍选择 blend，改善的不确定性单独保留。
- **卡片或事件不完整**：核对新增事件后缀，检测契约/账本前缀变化和截断 JSONL 事件，避免将过期摘要或半条事件当作完成证据。

本次检查脚本、两份示例卡片及 `review.json` 留在 `D:\华为云\tmp\workflow-review-20261010`。这是历史产物支持的人工流程审查，不是独立 agent 运行；尚未测量决策卡对完整流程的提分、耗时或上下文使用的净收益。

恢复核验现已抽成标准库工具 [`inspect_run_resume.py`](../skills/competition-optimize/scripts/inspect_run_resume.py)，可处理任意 adapter 的 JSON 对象事件；不依赖事件字段来推断预算或选择候选。它核验契约、旧日志前缀和新增事件语法，按页返回事件；新检查点仅覆盖已返回页，须核对证据后再引用到决策卡。遇到契约/前缀变化、截断、重复 JSON key、非有限数字或不完整事件时明确返回失败。并发追加保留到下页，原日志/卡片不会被修改。

新增 9 个测试覆盖中文/CRLF 字节位置、分页无丢失、空白行、追加、契约/前缀变化、截断和异常 JSON、并发改写、CLI 及拒绝覆盖；完整测试为 101 项通过。另用该 CLI 分页读取两题各 25 条真实历史事件，每页 3 条、各 9 页；所有事件与原记录逐项一致，各检查点 hash 一致，原契约和日志字节未变，模型拟合次数为 0。核对脚本、分页回执和 `audit.json` 位于 `D:\华为云\tmp\resume-inspector-20261010`。这验证了恢复工具，不证明 agent 的实验决策或提分效果。

## 抽样评测实测

profile 显示旧实现每次 bootstrap draw 都重建标签/预测数组，重复检查输入、计算 log loss 和排序 AUC。新实现先验证固定输入，缓存逐行损失/残差，并预先排序 AUC；抽样时使用整数行重复次数计算原 pooled AUC，保留 ties。回归仍使用每次 draw 自己的缩放，避免未抽到极端行时小残差下溢。

使用 [`examples/benchmark_prediction_uncertainty.py`](../examples/benchmark_prediction_uncertainty.py)，对照改动前 commit `5d7dd78` 的脚本。固定 1000 行、1000 次抽样，分别测试 row 和大小不等的完整 group；四种指标各重复计时 3 次并交替运行顺序，以下为中位数。本机 Python `3.14.7`，Windows 11。

| 指标 | 抽样单位 | 原耗时（秒） | 新耗时（秒） | 原耗时 / 新耗时 |
| --- | --- | ---: | ---: | ---: |
| RMSE | row | 1.470 | 0.763 | 1.93 |
| MAE | row | 1.358 | 0.675 | 2.01 |
| Binary LogLoss | row | 2.003 | 0.580 | 3.45 |
| ROC-AUC | row | 1.872 | 0.695 | 2.70 |
| RMSE | group | 1.133 | 0.476 | 2.38 |
| MAE | group | 0.997 | 0.339 | 2.94 |
| Binary LogLoss | group | 1.650 | 0.223 | 7.40 |
| ROC-AUC | group | 1.499 | 0.351 | 4.27 |

八项对照的逐次 score、case count、状态、改善量和实际 row draws 完全相同。测试另覆盖极端回归数值、零残差、概率边界、AUC tie/单类抽样、大小不等的 group、输入异常与预算超限。

复用上轮 [Diabetes 和 Breast Cancer pilot](tabular-pilot.md) 的确认预测进行 CLI 验证，两项 `bootstrap.csv` 与原文件逐字节相同，区间及预算消耗相同，没有重训模型。完整测试为 83 项通过，skill validator 通过。

性能数字只覆盖进程内 bootstrap，包括输入验证与预计算；不含 Python 启动、CSV 读取、模型训练或 agent 推理。大任务的实际收益取决于耗时构成，不能把 7.40 的单项比例当作整个比赛流程的提速。

## 批量评分与比较

新增 [`evaluate_prediction_batch.py`](../skills/competition-optimize/scripts/evaluate_prediction_batch.py)，将已生成且共享同一评测契约的预测文件放到一个进程内顺序评测，并复用已核验的基线评测结果。每个候选仍有独立预测快照、标准 `result.json` 和错误记录，原评分器及其 hash 未改动。批次保存公共 truth 快照，失败候选不阻断后续有效候选，失败 baseline 不产生比较；没有自动训练或晋升。

[`benchmark_prediction_batch.py`](../examples/benchmark_prediction_batch.py) 对照逐候选启动评测 CLI、再启动比较 CLI 的旧路径。固定合成 CSV，三次交替顺序计时，包含 Python 启动、读取、计分、hash 核验和产物写入；以下为中位数。

| 输入规模 | 原进程数 → 新进程数 | 原耗时（秒） | 新耗时（秒） | 原耗时 / 新耗时 |
| --- | ---: | ---: | ---: | ---: |
| 1000 行、4 个候选 | 7 → 1 | 0.930 | 0.186 | 5.01 |
| 10000 行、12 个候选 | 23 → 1 | 3.381 | 0.755 | 4.48 |

逐候选分数、候选/evaluator/score-model hashes、评测契约、检查范围和比较结果相同。路径元数据指向各自的新目录，因此整份 JSON 不应逐字节相同。批量路径保留原评分器的逐文件解析和验证，实测收益来自减少进程启动及重复基线读取；该比例只覆盖 CSV 评测/比较，不包含模型训练或完整 agent 工作。

另复用了真实数据 pilot 的两题开发集各 4 份预测、确认集各 2 份预测，共 12 份，分数、hash 和评测契约与既有记录一致，模型拟合次数为 0。新增 9 个测试覆盖四种指标、前导零 ID、可选比较、部分失败、无效 baseline、冻结 truth、列/裁剪参数、确认阶段、名称/数量限制及拒绝覆盖；全套 92 个测试及 skill 结构校验通过。

用法见 [批量入口](../skills/competition-optimize/references/data-model.md#batch-ready-candidates)。仅对已经准备好的兼容文件批量处理；有用反馈应及时获取，不能为了凑批次延迟下一次决策。每个配置仍单独记 trial，正式确认只处理冻结的 shortlist。

性能复现：`python examples/benchmark_prediction_batch.py --output-dir <仓库外的新目录>`。本次计时与源码 hashes 在 `D:\华为云\tmp\batch-efficiency-20261010\benchmark.json`，真实预测复测及摘要在 `D:\华为云\tmp\batch-real-predictions-20261010\audit.json`。

## 复现与证据

先创建仓库外的新目录，保存来自自己仓库的可信旧脚本，再执行对照：

```powershell
New-Item -ItemType Directory -Path 'D:\华为云\tmp\efficiency-reproduction'
git show 5d7dd78:skills/competition-optimize/scripts/compare_prediction_uncertainty.py |
  Set-Content -Encoding utf8 -LiteralPath 'D:\华为云\tmp\efficiency-reproduction\before.py'
python examples/benchmark_prediction_uncertainty.py `
  --reference 'D:\华为云\tmp\efficiency-reproduction\before.py' `
  --output 'D:\华为云\tmp\efficiency-reproduction\benchmark.json'
```

脚本导入 reference 作为 Python 代码，仅使用可信的旧版本。输出须为新文件；结果保存各次计时、环境、seed、输入规模、源码 hash、抽样结果 hash 和一致性检查，性能断言不写入单元测试以避免机器负载造成误报。

本次证据保留在 `D:\华为云\tmp\efficiency-pilot-20261010`：原实现快照、profile、对照 `benchmark.json`、两项真实预测的重测产物及 `real-prediction-check.json`。仓库只提交代码、测试和汇总。
