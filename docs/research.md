# 竞赛优化 Skill 源码研究

## 结论

首版做成一个 **Codex skill + 本地实验执行器 + 比赛专用 evaluator**。Skill 管理读题、检索、实验假设和结果解释；Python 执行器负责隔离候选、运行固定命令、记账和保存 incumbent；evaluator 负责比赛指标、正确性门槛和规则审计。

首版用单个 Codex agent 做有限轮次的顺序优化，不包一层多 agent 群组，也不依赖 AIDE / ShinkaEvolve / OpenEvolve 的完整运行框架。将上游项目中的实验模式抽取成小接口，能降低部署和调试成本，也能直接适配当前比赛已有的 benchmark、C++ 编译方式和静态约束检查。

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

## 首版文件与运行契约

建议先实现下列接口；具体目录名可在代码实现时小幅调整：

```text
.agents/skills/competition-optimize/SKILL.md
src/competition_runner.py
adapters/current_timeslot/evaluate.py
adapters/current_timeslot/README.md
runs/<run-id>/contract.json
runs/<run-id>/trials.jsonl
runs/<run-id>/candidates/<trial-id>/
```

每条 trial 至少存：`trial_id`、`parent_id`、单一 `hypothesis`、候选源码 hash、evaluator/fixture hash、seed/suite、启动命令、exit code、timeout、`correct`、逐场景 metrics、elapsed time、artifact 路径和 promote/reject 原因。原始日志/完整源码放在 trial 目录，JSONL 保持可扫描。

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

候选只在以下情况晋升：硬门槛全过；与父版本使用相同 evaluator hash、fixtures、seeds 和环境；短序列与完整集都有数据；按已知评分项的本地比较不被误称为完整官方排名；超预算或失败候选不覆盖 incumbent。

## 尚未验证的内容

本次做了浅克隆源码并阅读上述文件，未安装或运行 AIDE、ShinkaEvolve、OpenEvolve 或 AutoKaggle，也未测量它们在本题上的收益。结论是针对本项目首版的架构选择，不是上游系统之间的性能排名。若要复用代码而非借鉴接口/流程，应单独审核对应版本的 license 和依赖。
