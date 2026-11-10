# MVP 实施方案

> 历史设计说明：本文保留早期方案与局部试验设置。候选次数、默认预算等旧设计不构成当前运行限制；现行规则以 [SKILL.md](../skills/competition-optimize/SKILL.md) 和 [重构方案](refactor-plan-2026-11-10.md) 为准。

> 这是早期实施计划。用户在 2026-10-22 明确要求长周期无人值守优化，现已增加[可恢复的 campaign driver](../skills/competition-optimize/references/unattended-campaign.md)；下文“暂不做 runner”仅记录当时的范围，不再代表当前能力边界。

## 目标

建立一个以改善官方比赛指标为目标、可跨竞赛题型复用的 Codex skill 核心：固定指标方向和评分契约，按题型选择 evaluator adapter，建立 baseline，再用预算内的实测实验改进候选。

首个端到端 adapter 使用华为云固定时隙调度题。数据建模已接入预测 CSV 的标准指标评测与比较层，并完成两个公开小数据集的受限训练 pilot。通用比赛数据准备、防泄漏与跨任务提分仍需独立验证。每个新任务需要自己的评分、数据切分、硬约束和评测契约。

## 架构选择

- `SKILL.md` 是题型无关的流程控制器，由一个 Codex agent 执行。
- 比赛 adapter 负责候选接口、硬约束、评测和计分口径；缺少完整参数时报告分项和缺口，返回可追溯的结构化结果。
- 先不实现通用 runner。Skill 可以用每轮独立目录和 adapter 结果文件完成小规模 pilot；只有出现重复的快照、超时或记账错误后，才把机械操作抽成 Python runner。
- 代码生成与候选执行分开。候选不能改 evaluator、fixtures 或打包规则；这些文件的 hash 属于评测契约。

## Skill 本身

首版是一份可单独安装的 `competition-optimize` skill，不拆成 Reader、Planner、Coder、Reviewer 等多个角色，也不依赖本机已有的其他竞赛 skills。Skill 统一管理规则、评分、预算和候选决策；不同任务族的研究方法和验证方式由 adapter 补充。官方分数可计算时按官方分数晋升；参数缺失时报告分项和 Pareto 候选。

Skill 的描述面向“有明确比赛目标，且能建立可重复评测闭环”的竞赛优化请求。当前有算法/代码 adapter 和标准预测 CSV 评测层；Kaggle/数据建模仍需额外的泄漏与资源检查。Skill 正文要求实际实现、执行和按结果迭代，保留比赛/用户硬约束与停止条件；通用 adapter 契约及题目专属命令放在 references 中。代理筛选政策需说明依据，不能替代实际目标。

仓库中把 installable skill 放在 `skills/competition-optimize/`，题目 adapter 作为该 skill 的 supporting script/resources；文档留在仓库 `docs/`。安装后的试验输出写在用户指定的比赛工作区，不写入已安装的 skill 目录。先保留平台默认的隐式发现，同时允许显式 `$competition-optimize` 调用；不添加更改调用策略的 UI 配置，除非真实使用暴露需要。

Skill 在 Codex 对话中提供工作流指引和工具选择，由用户发起，状态写入 run 目录以便恢复。没有 skill 自设的时间、计算、候选或轮次上限；agent 按反馈持续执行有价值的后继，记录累计消耗。比赛硬规则、实际资源条件和用户当前明确的限制仍然有效；用户取消限制后无需重新开轮。若后续需要无人值守的长任务或可靠断点恢复，再把执行循环抽到独立 runner。

## 首案接入发现

目前的 harness 有很好的算法覆盖，但还没有适合作为 agent 工具调用的稳定接口：

- `tests/run_v4_benchmarks.py` 和 `tests/run_v7_short.py` 通过硬编码 variant 名称找到源码。每加一个候选都要改 registry，容易把 evaluator 改动和算法改动混在一起。
- 编译器路径硬编码为本机 MinGW 路径。
- benchmark CSV/JSON 写回共享 `tests/`；如果重复 label，会覆盖旧结果。
- `tests/package_submission.py` 仍通过版本名选择源码，且将 ZIP 和解压验证目录写回比赛根目录；它不接受任意候选路径。
- `tests/v8_validation.cpp` 等内部验证会直接 include 指定版本源码；它们不是可直接套用于任意候选的公共接口测试。
- 工作区含大量历史二进制和试验结果，不能把整个目录复制进每个 trial 或提交到 skill 仓库。

当前算法 adapter 按下列窄接口实施：

```text
python skills/competition-optimize/scripts/evaluate_current_timeslot.py \
  --candidate <source.cpp> \
  --stage smoke|short|full|package \
  --output-dir <unique-run-directory>
```

比赛目录通过 `--competition-root` 或 `COMPETITION_ROOT` 传入，不把用户的源代码、二进制和试验结果复制进 skill 仓库。编译阶段从 `--compiler` 或 `CXX` 环境变量读取；adapter 复用既有公共 API benchmark，将不可变候选快照、可执行文件、原始 CSV、日志和 ZIP 都写到调用方给定的独立目录。stdout 给紧凑 JSON 摘要，`result.json` 保存逐 workload 结果；超时、编译失败、正确性失败、规则失败和基础设施错误都有明确分类。`full` 保留逐 workload 指标，质量代理指标与耗时分开，不能声称包含官方速度分。结果包含运行平台标识，避免跨机器直接比较耗时；`evaluator_hash` 覆盖 adapter、其调用的测试源、接口头文件、官方打包扫描脚本、阶段配置和运行平台标识，而不是只 hash 外层 Python 文件。

## 实施顺序

1. **固定 adapter 契约**：已完成。输入候选源码路径、阶段和新输出目录；输出含 `candidate_hash`、`evaluator_hash`、`correct`、逐场景 `metrics`、`artifacts` 和 `error`。
2. **接入既有 harness**：已完成 smoke、短序列、完整 benchmark 和 package 四阶段。输出不写回共享 `tests/`，也不复制历史 `tmp`、exe 或旧 CSV。
3. **验证 adapter**：已完成。v7/v8 smoke 与 package 正例通过；v8 short/full 通过，full 的 90 行质量指标与已有 release 报告逐项一致；编译失败、规则失败和错误计数候选都得到不同的失败分类。
4. **写通用 `SKILL.md`、搜索策略和 adapter 契约**：已更新。用有边界的侦察读取当前实现与相关成功/失败实验，提出具体代码/流水线优化并实施；反馈接到后继实现，默认不做参数搜索。候选档案保存指纹、父版本、路线和失败机制，连续弱结果触发基于证据的路线切换。候选先过接口、硬规则、评测身份、产物和目标口径质量门，再进入昂贵评测。按需检索缺失机制与题型指南，核对评分实现及有效性字段的实际含义。预算留出独立确认，参数缺失时报告暂定代理，候选有效性与分数分开。
5. **做受限算法类 pilot**：单 agent、顺序运行、保留 incumbent 与 runner-up；观察硬门槛、分数比较和证据记录能否正确决定晋升。
6. **接入第二种题型验证泛化**：已新增标准预测 CSV 工具，支持四种回归/二分类指标，记录样本与 split/metric/configuration hash，并区分格式有效性和未检查的训练规则。成对 bootstrap 可按独立样本或完整组估计固定预测的抽样波动，保存抽样记录、区间、实际计算量和实用提升阈值；无效 AUC 抽样与证据不足明确报告，不自动决定晋升。错误诊断工具定位开发集逐样本损失和分组退步；AUC 不伪造逐样本损失，单类分组明确返回不可计算。加权集成工具保存父预测和冻结配方，并复用于确认集或测试集。预测与 truth 校验由小型共享模块复用。合成测试之外，已完成 [Diabetes 与 Breast Cancer 受限 pilot](tabular-pilot.md)：可信线性基线、两个树模型与一次条件组合，训练行内预处理、冻结短名单、确认及独立 sklearn 计分核对。观测收益不确定，且发生排名反转，已据此加强验证与交付规则；该脚本不是通用 runner，也不是完整 agent 效果评估。分组/时间任务与跨任务自主提分对照仍待验证。
7. **按证据决定 runner**：候选档案的机械记录、精确重复拦截和提案到实测后继的关联检查已由 `scripts/candidate_archive.py` 提供；只有快照、超时、hash 对账或多 adapter 记账仍出现重复错误时，才继续扩展 runner。搜索和候选生成仍由受预算约束的 skill 流程负责，提案与记录不能替代执行。

## 验收条件

- 从 baseline 到 candidate 的每次比较都有相同的 evaluator/fixture/config hash，候选源码有独立 hash。
- 编译失败、timeout、违反规则和低分有效解能被 evaluator 区分；失败 candidate 永远不能覆盖 incumbent。
- 已知 candidate 复测可重现质量指标；计时按配对 workload、固定 seeds 和重复协议比较。
- 每轮的源码、配置、原始输出和结果 JSON 都在独立 run 目录，旧结果不会被覆盖。
- 打包 ZIP 中的源文件字节与获选候选完全一致，并重新打开 ZIP 验证文件名和内容。
- 交付摘要区分本地指标与官方分数，并列出尚未验证的规则/阈值。

## 暂不做

当前不做 multi-agent、并行搜索、数据库、经验向量库、自动提交、官方分数猜测、通用 hidden-test 服务或安全容器平台。也不把已有算法 adapter 和预测评测层描述成已经支持所有比赛流程。
