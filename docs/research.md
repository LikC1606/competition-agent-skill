# 竞赛优化 Skill 源码研究

## 结论

三轮源码研究与首个案例 harness 审计后，首个可验证版本应是 **一个 Codex skill + 比赛专用 evaluator adapter**。先把题目评测做成接受任意候选路径、产出机器可读结果的稳定接口；不急着写通用 runner。若 pilot 表明快照、超时或记账容易出错，再加很小的 runner。评分实现仍属于确定性 evaluator，不交给模型从日志推断。

首版先只支持算法与代码优化类题目，用单个 Codex agent 做有限轮次的顺序优化，复用比赛已有 benchmark。没有可信、可重复的 evaluator 时，先构造并验证评测器，不开始自动搜索。不要实现 MCTS、memory service、数据库、并行 worker 或通用 Kaggle 数据管线；等多个真实任务证明它们必要后再加。分阶段实现与验收条件见 [`mvp-plan.md`](mvp-plan.md)。

## 上游实现观察

### AIDE：候选树与有方向的迭代

[AIDE 的搜索策略](https://github.com/WecoAI/aideml/blob/60b3978ddf65b71f86eb7c64506965048a1398cf/aide/agent.py#L162)先产生配置数量的初始 drafts，再按概率处理失败的叶子，其他时候从当前最好可用节点继续；[改进提示](https://github.com/WecoAI/aideml/blob/60b3978ddf65b71f86eb7c64506965048a1398cf/aide/agent.py#L308)明确要求一个具体、可单独验证的改动。每次执行后把新节点挂到 parent 下，[每步保存 journal](https://github.com/WecoAI/aideml/blob/60b3978ddf65b71f86eb7c64506965048a1398cf/aide/run.py#L135)。节点持有代码、计划、parent、执行输出和 metric：[journal schema](https://github.com/WecoAI/aideml/blob/60b3978ddf65b71f86eb7c64506965048a1398cf/aide/journal.py#L25)。

**采用：** 候选要有 parent ID；一次实验只验证一个假设；失败候选进入 debug 路径；当前最好版本不会被最新代码覆盖。

**不照搬：** AIDE 当前 search policy 主要 greedy 地反复改最好节点，可能让普通算法问题过早收敛。第一版应允许回到至少两个已验证的候选方向继续扩展，但先用线性 trial ledger 记录即可，不需要把每个候选都做成复杂搜索树。

**重要差异：** AIDE 在这份实现里让 feedback LLM 根据运行输出报告 metric 和是否有 bug：[metric 解析](https://github.com/WecoAI/aideml/blob/60b3978ddf65b71f86eb7c64506965048a1398cf/aide/agent.py#L397)。这适合总结日志，不应成为本项目的评分来源。候选排名必须来自确定性的 evaluator；LLM 只解释失败并建议下一项实验。

### ShinkaEvolve：跨语言 evaluator 契约与分段 skills

Shinka 的 [setup skill](https://github.com/SakanaAI/ShinkaEvolve/blob/8adc053a2ce4511ad2ac310e004c530a73fb974a/skills/shinka-setup/SKILL.md)要求新任务同时有初始程序和 evaluator，并先做 evaluator smoke test；[convert skill](https://github.com/SakanaAI/ShinkaEvolve/blob/8adc053a2ce4511ad2ac310e004c530a73fb974a/skills/shinka-convert/SKILL.md)可把已有代码库放进独立 sidecar snapshot、标出小的可演化区，再用 Python evaluator 启动非 Python 候选。Evaluator 分开写指标与 `correct`/`error`，检查结果可读；[inspect skill](https://github.com/SakanaAI/ShinkaEvolve/blob/8adc053a2ce4511ad2ac310e004c530a73fb974a/skills/shinka-inspect/SKILL.md)再把前几个好候选和反馈打包给下一轮。

Shinka 的 [run skill](https://github.com/SakanaAI/ShinkaEvolve/blob/8adc053a2ce4511ad2ac310e004c530a73fb974a/skills/shinka-run/SKILL.md)以一批 generations 为运行单位，默认批次间暂停并询问。这里需要保留明确预算和批次记录，但用户想要自动优化，所以首版可以在用户设定或默认上限内连续执行；预算耗尽、规则有歧义、需要正式提交或需要增加付费预算时再停下来。

**采用：** evaluator 是可替换的比赛适配器；任务快照与原工作区隔离；先 smoke 再花完整预算；指标与有效性分开记录；只把最小代码区域交给优化。

**不照搬：** Shinka 的数据库、island population、embedding 和异步并行都不是这个 MVP 的必要条件。先用 JSONL 和文件快照，确认迭代次数足以证明价值后，再决定是否升级。

### OpenEvolve：评测成本和失败分类

[OpenEvolve evaluator](https://github.com/algorithmicsuperintelligence/openevolve/blob/9196d8763300d1e46cc8b48cb0dc987966db3d48/openevolve/evaluator.py#L140)支持候选超时、异常结果、有限重试和分阶段评测；[EvaluationResult](https://github.com/algorithmicsuperintelligence/openevolve/blob/9196d8763300d1e46cc8b48cb0dc987966db3d48/openevolve/evaluation_result.py#L11)把用于排名的 metrics 和供检查的 artifacts 分开。

**采用：** 评测成本分层，先执行编译和短测试；运行错误、超时、无效指标分别分类；错误详情可作为 artifact 保存，而不混进主分数。

**不照搬：** 多岛、MAP-Elites、多目标搜索会扩大首版的状态空间。当前题的质量和运行时间虽有 tradeoff，但已有固定的官方权重，不需要为此实现通用 Pareto 引擎。

### AutoKaggle：阶段化流程，但角色数对本项目过多

[AutoKaggle 的 SOP](https://github.com/multimodal-art-projection/AutoKaggle/blob/2640d756499846eff6cab4a56b4fbaa8f84b3453/multi_agents/sop.py#L11)串联 Reader、Planner、Developer、Reviewer、Summarizer，并为流程阶段限制重试次数。Developer 有运行超时和 unit-test 路径；项目目标和数据入口主要针对 Kaggle 表格建模。

**采用：** 把读题、规划、开发、验证和总结作为清楚的阶段。

**不照搬：** 首版不分配五个 agent。当前工作主要是算法、C++ 和本地 harness；一个 agent 调工具并读取结构化评测结果，足以覆盖这些阶段，也避免多个角色重复读题和互相转述分数。

### Meta LLM Speedrunner：最接近的算法优化参照

[LLM Speedrunner](https://github.com/facebookresearch/llm-speedrunner/tree/ec3e4afd6dcf7c99f7b0be35898e40df6e1257c9)把实验循环拆为 ideation、实现、执行和分析。它把每次实验放在版本化 workspace 中，保留父版本、实验代码和结果，因此能从算法性能优化角度追溯候选，不只是自动训练 Kaggle 模型。可参考其 [BoN runner](https://github.com/facebookresearch/llm-speedrunner/blob/ec3e4afd6dcf7c99f7b0be35898e40df6e1257c9/core/runners/bon_science_runner.py)、[workspace](https://github.com/facebookresearch/llm-speedrunner/blob/ec3e4afd6dcf7c99f7b0be35898e40df6e1257c9/core/workspace.py) 和 [metrics extraction](https://github.com/facebookresearch/llm-speedrunner/blob/ec3e4afd6dcf7c99f7b0be35898e40df6e1257c9/core/runners/science_runner.py)。

这个系统的完整 scaffold 包含 Hydra、Slurm、GPU 任务环境和多种 agent class；其中 metrics 若无法从程序输出解析，还会回退让 assistant 从日志抽取。首版只借鉴阶段划分与版本历史，保留机器可判定的 evaluator 输出，也不需要把整个运行框架搬进来。该仓库声明 CC BY-NC 4.0，因此仅引用设计，不复制代码。

### MLEvolve：停滞时换方向，搜索栈仍然偏重

[MLEvolve](https://github.com/InternScience/MLEvolve/tree/9c5c8a3b23f0361708b59a401452dddc00f97189)以 Kaggle/MLE-bench 为主，也报告数学优化任务。源码中的 [node selection](https://github.com/InternScience/MLEvolve/blob/9c5c8a3b23f0361708b59a401452dddc00f97189/engine/node_selection.py)实现 UCT、随时间调整探索权重和跨 branch 的 Top-K 选择；[stagnation conditions](https://github.com/InternScience/MLEvolve/blob/9c5c8a3b23f0361708b59a401452dddc00f97189/engine/conditions.py)会在符合条件时触发 branch fusion。README 还描述了 BM25 + FAISS 经验记忆和多种规划/生成模式。

可借鉴的是识别停滞、保留多条路线和记录失败经验。首版把它简化为：先从 baseline 试最多三个独立假设，之后保留 incumbent 与 runner-up；同一路线连续两轮无提升时，切到另一条或回到 baseline。这里是本项目建议的简化策略，不是对 MLEvolve 策略的复刻。它使用 Apache-2.0，但本项目仍不需要依赖其实现。

### FM-Agent FDE-Bench：验收评测借鉴，邻近 case 不是同一题型

[FDE-Bench](https://github.com/baidubce/FM-Agent/tree/cd494b3e89660adeaf60743a99a5a470897d7637/FDE-Bench)将真实交付任务拆为输入需求、澄清信息、agent workspace 和提交后的评测。case 006 [ion beam uniformity optimization](https://github.com/baidubce/FM-Agent/tree/cd494b3e89660adeaf60743a99a5a470897d7637/FDE-Bench/case/006_ion_beam_uniformity_optimization)看起来与均匀性优化相近，但实际目标是用历史数据预测约 186 点的 `UniformityY` 曲线；这与本题在线时隙调度算法不同。它适合参考问题澄清、交付 schema 和硬约束/质量分离，不宜当作本题算法参考。

FDE-Bench README 要求把 `information.md`、`gt.json`、tests 和参考答案留在 agent workspace 之外，并明确指出 `_private` 只是约定名称，不会让公开仓库中的文件自动变成不可访问。这个边界很重要：若模型拥有文件系统工具，就必须靠工作区挂载/权限或外部评测服务隔离真值；仅把文件夹命名为 `_private`、或在 prompt 中禁止读取，都不构成访问控制。FDE-Bench case 代码与数据没有开放再分发许可，本仓库只引用其公开文档，不复制内容。

### AI Scientist v2：树搜索的安全提醒

[AI Scientist v2](https://github.com/SakanaAI/AI-Scientist-v2/tree/96bd51617cfdbb494a9fc283af00fe090edfae48)采用 best-first tree search，且 README 说明它的 tree search 基于 AIDE；它面向开放式研究而不是限定规则的竞赛。README 还提醒生成代码可能安装危险依赖、访问网络或启动额外进程，建议放在 Docker 等隔离环境执行。这里借鉴的是“模型生成代码需要运行边界”的风险认识，不引入其研究流程或受额外限制的代码。

## MVP 的具体运行模型

### 适用边界

先限定为算法/代码优化题：有清楚的输入输出或函数接口、能重复运行的本地测试、可以结构化读取的指标。Kaggle 式数据竞赛需要不同的数据切分、防泄漏、提交和 leaderboard adapter，暂不把两种任务硬塞进同一个通用 evaluator。遇到评分规则不清、关键限制未知或没有确定性评测命令时，Skill 记录缺口并停在评测器建立阶段。

### 闭环步骤

1. **Seal contract**：把题目目标、官方规则版本、允许的工具/网络、资源限制、评分方向、提交格式、试验预算、已知与未知项序列化并 hash。硬规则仍有歧义时先澄清，不花大预算搜索。
2. **Research**：按题型和可疑瓶颈定向检索论文、开源代码和竞赛讨论；输出短清单，记录 URL、版本/commit、可迁移的具体机制和 license。网页内容作为待验证证据，不把它直接当答案或把未许可代码拷进候选。
3. **Evaluator smoke test**：组合官方样例和本地 harness，检查指标方向、退出码、超时、错误输出和 JSON schema。至少用已知 baseline/故意失败用例验证 evaluator 真能分清有效与无效候选。
4. **Baseline**：先做最简单的正确解，记录同一 evaluator/fixture hash 下的全量 baseline；没有 baseline 就不能判断迭代是否有进步。
5. **Trial loop**：最多先从 baseline 分别试三个不同机制；每个 trial 只改一个可归因机制，生成独立候选快照。按编译/静态规则、短测、完整 benchmark 的成本顺序执行，保存结构化结果和失败原因。短测通过后才支付完整评测成本；涉及计时的指标应按固定协议重复运行，提升小于测量波动时视作平局并复测。
6. **Promote / stop**：先过硬正确性与规则门槛，再按比赛目标排序；保持 incumbent 与 runner-up。连续两轮无提升则切换到 runner-up 或提出不同机制。达到 trial、时间或费用预算即停止，并留出最终复测预算。
7. **Final verify**：用未参与调参的 seeds/scenarios 或独立参考实现复核最终候选，重新跑规则检查和提交打包。报告只写 evaluator 可追溯的数据，分清本地与官方分数。

### 可选 Runner 与隔离边界

如果 pilot 证明手工步骤容易出错，runner 只做可重复的机械工作：按 trial ID 建目录、复制指定候选源文件、运行 adapter 的固定命令、强制 timeout、保存 stdout/stderr、读取 evaluator JSON、计算源代码和配置 hash，并以追加方式写入 JSONL ledger。候选生成、研究和下一步策略仍由一个 Codex agent 完成。候选绝不编辑已 seal 的 evaluator；若 evaluator/fixture 有变化，hash 变化后必须重跑基线和待比较版本。

目录隔离方便追溯，但不等于安全 sandbox。LLM 生成的候选可以是任意程序；如需要保护机器或隐藏真值，应由 OS/container 限制 CPU、内存、时间、网络和文件系统，并让 evaluator/truth 位于候选进程不可读的独立身份或服务。无法提供访问控制时，只把公开本地 fixtures 称为 validation，不称为 hidden test，也不声称 evaluator 对该 agent 保密。

## 应用于当前华为云题目

任务材料定义了 `init` / `apply_add` / `apply_remove` / `grid` 接口，目标函数同时包含 uniformity、variance 和 speed，另有不允许乘法、除法、取余和浮点运算的提交限制。官方最终测试独立于赛中测试，且速度分数需要官方 reference times；本地无法从比赛说明推算出这两个阈值。

当前工作区已具备较好的 evaluator 起点：

- `tests/benchmark.cpp` 有九种 workload、计数不变量检查和 operation/init 计时。
- `tests/run_v4_benchmarks.py` 对每个候选使用相同 seeds、scenarios 和 `N=400/10000`，逐个构建运行，产出 CSV 与 JSON 汇总。
- `tests/run_v7_short.py` 另测 `N=100/400/10000` 与 `Q=1/10/100`，可以暴露长 workload 平均值盖住的短序列回退。
- `tests/v7_validation.cpp` 包含独立参考增量、循环链和 bitmap 一致性检查；`tests/package_submission.py` 还做静态规则扫描并重新打开 ZIP 核对文件。
- `tests/v5-notes.md` 明确把 `0.55*U + 0.35*V` 标为不含 speed 的本地质量指标。

因此，候选评价应分层报告，而不是把一个 local `combined_score` 冒充官方分：

1. **硬门槛：** 严格编译、接口、grid 长度和每种 ID 的计数、样例、算术限制、压力/状态不变量、ZIP 内容。任一失败都不能晋升。
2. **短 workload：** 统一 seed 比较 `Q=1/10/100`，拦截新策略在短序列中的回退。
3. **完整本地 benchmark：** 配对跑九种场景和不同规模，分别保留 `U`、`V`、运行时间及 initialization 时间；可以报告 `0.55*U + 0.35*V` 作为质量项，speed 单独列出。
4. **官方分数：** 只有在拿到官方 `tfast` 和 `tslow` 或平台反馈后，才能计算/声称完整 score；否则只报告本地数据。

本地 benchmark 脚本用浮点重算分数没问题，受限的是最终提交解法。源代码静态扫描可以做快速检查，但由于 `*` 也用于 C++ 解引用，不能只用一个不理解语法的正则当作最终合规证明；应保留严格审阅和独立编译验证。

## 可选 Runner 文件草案

若 pilot 需要 runner，再实现下列接口；具体目录名可在代码实现时小幅调整：

```text
skills/competition-optimize/SKILL.md
skills/competition-optimize/scripts/evaluate_current_timeslot.py
runs/<run-id>/contract.json
runs/<run-id>/trials.jsonl
runs/<run-id>/candidates/<trial-id>/
```

其中 skill 与 task adapter 是首个 pilot 的范围；`src/trial_runner.py` 仅在 pilot 证明有必要时再加入。

每条 trial 至少存：`trial_id`、`parent_id`、单一 `hypothesis`、候选源码 hash、evaluator/fixture/config hash、seed/suite、启动命令、exit code、timeout、`correct`、逐场景 metrics、elapsed time、artifact 路径和 promote/reject 原因。原始日志与候选快照放在 trial 目录，JSONL 保持可扫描。runner 先只消费比赛已有命令，不把通用评分公式写进核心。

Evaluator 对 runner 返回稳定结构，例如：

```json
{
  "correct": true,
  "metrics": {
    "uniformity": 0.0,
    "stability": 0.0,
    "operation_ms": 0.0,
    "initialization_ms": 0.0
  },
  "artifacts": [],
  "error": null
}
```

候选只在以下情况晋升：硬门槛全过；与父版本使用相同 evaluator hash、fixtures、seeds 和环境；短序列与完整集都有数据；按已知评分项的本地比较不被误称为完整官方排名；有证据表明提升超过测量波动。超预算或失败候选不覆盖 incumbent。

## 尚未验证的内容

本次对 AIDE、ShinkaEvolve、OpenEvolve、AutoKaggle、LLM Speedrunner、MLEvolve、FM-Agent/FDE-Bench 和 AI Scientist v2 做了浅克隆并阅读目标文件，未安装或运行这些系统，也未测量它们在本题上的收益。结论是针对本项目首版的架构选择，不是上游系统之间的性能排名。LLM Speedrunner 为 CC BY-NC 4.0，AI Scientist v2 有额外限制；FDE-Bench case 文件未指定开放再分发许可。当前建议只借鉴流程/接口概念，复用代码或数据前须单独审核对应版本的 license 与依赖。
