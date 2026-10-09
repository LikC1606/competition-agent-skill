# MVP 实施方案

## 目标

验证一个 Codex skill 能否在一类算法优化竞赛中完成可审计的闭环：读题、定向检索、建立 baseline、提出有限实验、根据真实评测结果继续或停止，最后复核并打包。

首个案例用华为云固定时隙调度题。第一版不需要让 agent 找到比现有 v8 更好的算法；先证明它能可靠比较候选、发现失败、不覆盖最好版本、产出可信记录。

## 架构选择

- `SKILL.md` 是流程控制器，由一个 Codex agent 执行。
- 比赛 adapter 负责编译、测试、评分和打包，返回确定性的 JSON。
- 先不实现通用 runner。Skill 可以用每轮独立目录和 adapter 结果文件完成小规模 pilot；只有出现重复的快照、超时或记账错误后，才把机械操作抽成 Python runner。
- 代码生成与候选执行分开。候选不能改 evaluator、fixtures 或打包规则；这些文件的 hash 属于评测契约。

## 首案接入发现

目前的 harness 有很好的算法覆盖，但还没有适合作为 agent 工具调用的稳定接口：

- `tests/run_v4_benchmarks.py` 和 `tests/run_v7_short.py` 通过硬编码 variant 名称找到源码。每加一个候选都要改 registry，容易把 evaluator 改动和算法改动混在一起。
- 编译器路径硬编码为本机 MinGW 路径。
- benchmark CSV/JSON 写回共享 `tests/`；如果重复 label，会覆盖旧结果。
- `tests/package_submission.py` 只支持 v3、v4、v5、v7，不接受任意候选路径。
- `tests/v8_validation.cpp` 等内部验证会直接 include 指定版本源码；它们不是可直接套用于任意候选的公共接口测试。
- 工作区含大量历史二进制和试验结果，不能把整个目录复制进每个 trial 或提交到 skill 仓库。

因此，adapter 应有一个窄接口，示意如下：

```text
python adapters/current_timeslot/evaluate.py \
  --candidate <source.cpp> \
  --stage smoke|short|full|package \
  --output-dir <unique-run-directory>
```

比赛目录通过本机配置或环境变量传入，不把用户的源代码、二进制和试验结果复制到 skill 仓库。编译器从配置或 `CXX` 环境变量读取；适配器直接使用既有的公共 API benchmark，但将可执行文件、原始 CSV、汇总 JSON、日志和 ZIP 都写到调用方给定的独立目录。stdout 返回一份结果 JSON；非零退出、超时、编译失败和正确性失败都必须明确区分。`full` 保留逐 workload 指标，质量项和耗时分开，不能声称包含未知的官方速度分。`evaluator_hash` 覆盖 adapter、其调用的测试源、规则扫描逻辑和配置，而不是只 hash 外层 Python 文件。

## 实施顺序

1. **固定 adapter 契约**：确认输入只需候选源码路径和测试阶段，输出包含 `candidate_hash`、`evaluator_hash`、`correct`、逐场景 `metrics`、`artifacts` 和 `error`。评测命令不依赖候选的命名。
2. **接入既有 harness**：支持 smoke、短序列、完整 benchmark 和 package 四个阶段。输出不写回共享 `tests/`；不复制历史 `tmp/`、exe 或旧 CSV。
3. **验证 adapter**：跑现有 v7/v8 源码作为正例，用编译错误和计数错误样例作为负例。正例的质量指标应与已有报告一致；耗时允许按固定测量误差范围浮动。重复跑同一输入不得覆盖前一次 artifact。
4. **写 `SKILL.md`**：规定 task contract、定向 research 记录格式、baseline gate、一次一个假设、评测分层、promotion 规则、预算停止和 final verify。Skill 只读取 adapter JSON 中的分数，不从自由文本猜分。
5. **做一次受限 pilot**：单 agent、顺序运行、最多三条独立假设路线；保留 incumbent 与 runner-up。至少覆盖一个通过硬门槛的候选、一个执行/正确性失败候选和一个有效但无提升的候选，观察流程是否能正确晋升/拒绝及保留证据。
6. **按证据决定 runner**：如果候选快照、超时终止、hash 对账或 JSONL 记录必须重复手工处理，再实现只做这些工作的薄 runner。否则保留简单 skill + adapter。
7. **第二题再谈通用化**：先在第二个同类算法题上验证 adapter 协议；只有跨任务的命令、结果和状态模型稳定后才抽象公共包。Kaggle 数据竞赛作为另一种 adapter 家族，不纳入首版。

## 验收条件

- 从 baseline 到 candidate 的每次比较都有相同的 evaluator/fixture/config hash，候选源码有独立 hash。
- 编译失败、timeout、违反规则和低分有效解能被 evaluator 区分；失败 candidate 永远不能覆盖 incumbent。
- 已知 candidate 复测可重现质量指标；计时按配对 workload、固定 seeds 和重复协议比较。
- 每轮的源码、配置、原始输出和结果 JSON 都在独立 run 目录，旧结果不会被覆盖。
- 打包 ZIP 中的源文件字节与获选候选完全一致，并重新打开 ZIP 验证文件名和内容。
- 交付摘要区分本地指标与官方分数，并列出尚未验证的规则/阈值。

## 暂不做

不做 multi-agent、并行搜索、数据库、经验向量库、自动提交、官方分数猜测、通用 hidden-test 服务或安全容器平台。首个 skill pilot 也不需要把比赛源代码、历史二进制和个人结果数据复制进 GitHub 仓库。
