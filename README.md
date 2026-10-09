# Competition Agent Skill

一个轻量的竞赛求解流程：给定题目、规则和本地材料，由 Codex 读题、检索资料、制作 baseline，再通过真实评测结果迭代优化。

当前仓库记录了两轮源码研究后的首版设计；可调用 skill 和 runner 尚未实现。

## 最小版本

采用 **一个 Codex skill + 薄型本地 runner + 比赛评测适配器**：

- **Skill**：指导 Codex 理解任务、定向检索、建立 baseline、提出可检验假设并分析反馈。
- **薄型 runner**：复用比赛已有命令，隔离每轮候选目录，记录源码/配置 hash、日志、退出状态和评测 JSON；不实现搜索算法或通用沙箱平台。
- **比赛适配器**：声明编译、短测、完整评测、规则检查和提交打包命令；评分口径仍由每道题的确定性 evaluator 决定。

先聚焦算法与代码优化类题目，用一个 Codex agent 顺序完成有预算上限的闭环。复用现有 benchmark；没有可靠评测器时，先建立并验证评测器，不进入自动优化。确认至少两个任务都需要后，再考虑独立运行、断点恢复或并行候选。

## 工作流程

1. **读题**：生成任务卡，提取目标、接口、评分规则、资源限制和提交要求，记录尚未明确的信息。
2. **建立评测器**：优先复用官方工具；自行实现时用样例核对，区分本地指标与官方分数。
3. **检索与 baseline**：定向寻找相关算法、论文和开源实现，记录来源，得到正确且有实测结果的初始方案。
4. **迭代优化**：每轮提出一个明确假设，生成候选代码，运行评测，分析改进与退步，保留最好版本。
5. **结束与交付**：达到轮数、时间或费用预算后，输出最好方案、实验对比和符合规则的提交包。

## 关键约定

- 从真实执行结果读取指标；缺少官方评分参数时，不虚构完整官方分数。
- 优化期间保持评测口径一致；评测器变化后，重新评测需要比较的版本。
- 保留独立验证场景，用于检查最终候选的泛化表现。
- 每次实验记录父版本、假设、代码快照、配置、指标、耗时、状态和失败原因。
- 最好版本与最新版本分别保存，失败实验不覆盖已验证的方案。
- 输出提交包；正式提交按用户授权和比赛配额处理。

## 源码研究结论

- 从 AIDE 借鉴父子候选记录、先产生 baseline 和一次只提出一个可检验改进的做法。
- 从 ShinkaEvolve 借鉴窄范围可变代码区、非 Python 评测适配和结构化正确性结果。
- 将 AIDE 式搜索选择与 Shinka 式评测/检查能力组合成一个轻量闭环；第一版不引入外部进化框架或多 agent 群组。
- Meta 的 LLM Speedrunner 是更贴近算法优化的参照：阶段化假设、实现、执行、分析，版本化工作区记录候选历史。其完整实验框架与 GPU/Slurm 配置不纳入 MVP。
- MLEvolve 的停滞检测、跨分支经验值得后续验证；其 MCGS、多 agent、embedding memory 和 Kaggle 数据栈不作为首版依赖。
- FDE-Bench 的离子束均匀性 case 是“优化/均匀性”表述上的近邻，但实际任务是预测曲线；只参考任务澄清和 evaluator 设计。case 数据和实现没有开放再分发许可，不复制进本仓库。
- 评分器以程序输出为准；测试失败、耗时和多项指标都作为单独证据。模型的解释用于选择下一项实验，不直接决定候选分数。
- 每轮保留可运行的最好版本，并用固定测试集配对比较；达到已配置预算即停止。

完整的源码依据、竞品取舍和首版接口草案见 [`docs/research.md`](docs/research.md)。

## 第一个验证案例

计划使用华为云固定时隙均匀调度算法题验证流程，覆盖 C++ 函数接口、在线增删操作、均匀性与稳定性权衡、运行时间，以及禁止乘除、取余和浮点运算的限制。

现有比赛材料与解法留在原工作区，本仓库先维护通用流程和设计。评测适配器接入后，再决定需要纳入哪些案例文件。

## 参考项目

| 项目 | 参考重点 |
| --- | --- |
| [LLM Speedrunner](https://github.com/facebookresearch/llm-speedrunner) | 算法/代码优化实验循环、版本化工作区；最贴近本项目目标。 |
| [AIDE](https://github.com/WecoAI/aideml) | 候选代码搜索树，以及生成、修复和改进之间的选择。 |
| [AutoKaggle](https://github.com/multimodal-art-projection/AutoKaggle) | 读题、规划、开发、评审和总结的竞赛流程。 |
| [MLEvolve](https://github.com/InternScience/MLEvolve) | Kaggle 与数学优化上的进化搜索；借鉴停滞识别与多分支保留，不搬完整框架。 |
| [ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve) | 程序演化，以及已有的 Codex / Claude skill 组织方式。 |
| [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) | 初始程序与自定义评测器驱动的代码优化。 |
| [MLE-bench](https://github.com/openai/mle-bench) | 参赛 agent 的评估方法与比赛评测适配。 |
| [FDE-Bench](https://github.com/baidubce/FM-Agent/tree/main/FDE-Bench) | 端到端交付与 evaluator 设计；case 006 是曲线预测任务，不是时隙调度。 |
| [AI Scientist v2](https://github.com/SakanaAI/AI-Scientist-v2) | 研究型树搜索和代码隔离风险提示；仅作概念参考。 |

## 下一步

实现可调用的 `SKILL.md` 和最小 trial runner；接入当前算法题已有的 benchmark 命令，跑通 baseline、候选比较、独立复核和打包验证。首个案例验证前，不把它扩展成通用 Kaggle 平台。
