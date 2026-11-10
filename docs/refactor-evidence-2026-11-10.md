# 重构方案的代码、验证与资料证据

对应[改造方案](refactor-plan-2026-11-10.md)。日期：2026-11-10；代码基线 `80331a1`。E 为直接代码/执行/原文证据，I 为设计推断，未复验的效果明确保留为未知。

## 1. 审查范围与研究问题

| 研究方向 | 必答问题 | 本轮证据与边界 |
| --- | --- | --- |
| N1 代码责任 | 哪些规则分散、调用顺序复杂或语义不同？哪些现有深 Module 应保留？ | 阅读运行、档案、证据、两类 adapter 与相关测试；三个定向行为探针；没有把代码长度当缺陷 |
| N2 比赛工作流 | 参赛者如何设计验证、根据失败改方法、组合和最终选择？ | 两份独立一手复盘，核对官方任务/指标及固定版本源码；未复现参赛成绩 |
| N3 自动优化机制 | 搜索、消融、执行、反馈与上下文如何连接？ | MLE-STAR 正文、AIDE 源码、Shinka setup/inspect；未运行第三方 agent |
| N4 迁移与效果 | 如何保留恢复/比较语义，并判断新工作流是否更好？ | 本地测试基线，MLE-bench/ALE-Bench 的评价协议；尚无改造后的效果数据 |

本地审查分为三条独立代码线：

- 运行：`autonomous_campaign`、`campaign_runtime`、`campaign_policy`、`campaign_search`、`campaign_archive`。
- 档案与证据：`candidate_archive`、`candidate_evidence`、`evidence_files`、`campaign_trials`、`measurement_plans`、`scoped_learning`、profiles/reviews。
- 题型：prediction 的评分、比较、批量、bootstrap、错误分析、blend、split audit；timeslot 的编译/执行/打包/比较；resume/screening 及 tabular pilot。

深读以公共行为、调用链和测试为依据；不是形式验证，也未执行真实比赛数据或付费 Codex campaign。

## 2. 本次执行的验证

### 2.1 隔离测试基线

在仓库根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover \
  -s skills/competition-optimize/tests -p 'test_*.py' -q
```

实际结果：

```text
Ran 520 tests in 182.780s
OK
```

进程退出码 0；外部计时 182.86 秒。这是 skill 测试目录的运行结果，未运行第三方系统、作者模型或真实比赛评测。

执行前检查了隔离方式：`test_autonomous_campaign.py:339–366` 使用 TemporaryDirectory 与显式 fake-codex；恢复使用同一临时 state；清理只处理本次身份关联的进程。timeslot 测试采用内存 CSV。测试会创建自己的本地子进程，但未发现真实 provider 或生产访问。

另对 57 个 Python 文件做了 AST 语法解析，无语法错误；SKILL.md 引用的本地文件均存在。未重写或格式化源码。

### 2.2 三个定向探针

| 探针 | 输入与实际观察 | 结论范围 |
| --- | --- | --- |
| 未决机会 | baseline=10；父版=9 且 unresolved；新后继执行失败、无分数；随后无关正常候选=8。`decide` 返回 explore 和空机会列表；`brief` 仍返回该父版 | 建议规则分歧；不等同于官方计分或晋升错误 |
| full 完整性 | 两个手工 schema-2 结果，同 evaluator/环境、同一个有效 workload row、都声明 full；`load_result` + `compare` 返回 success、workload_count=1 | 正常 runner 的 full 为 2 sizes × 5 seeds × 9 scenarios=90。缺口在持久结果消费，不能据此说正常 runner 漏跑 |
| C++ 扫描 | 调用 `audit_and_package`：`int f(int current) { return 2 * current; }` 放行；`int f(int* p) { return *p; }` 被拒 | 变量名白名单不能区分乘法与指针。未编译这些片段，也未作官方合规判定 |

定位：[两个机会规则](../skills/competition-optimize/scripts/candidate_archive.py#L896)与[另一条路径](../skills/competition-optimize/scripts/candidate_archive.py#L1017)；[reader 完整性](../skills/competition-optimize/scripts/compare_timeslot_results.py#L23)；[双方配对](../skills/competition-optimize/scripts/compare_timeslot_results.py#L110)；[full 定义](../skills/competition-optimize/scripts/evaluate_current_timeslot.py#L24)；[规则扫描](../skills/competition-optimize/scripts/evaluate_current_timeslot.py#L209)。

未决机会探针可在基线仓库根目录用下列代码复现；全部文件来自已有测试的临时夹具：

```python
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path("skills/competition-optimize/tests").resolve()))
from test_optimization_brief import OptimizationBriefTests, archive

case = OptimizationBriefTests()
case.setUp()
try:
    case.record("baseline", 10, status="incumbent")
    case.record("open-parent", 9, status="unresolved", feedback="Mechanism remains untested")
    case.record("failed-child", None, status="rejected", valid=False,
                parent="open-parent", feedback="Execution failed",
                score_fields={"kind": "official_metric"})
    case.record("healthy-unrelated", 8, status="rejected", feedback="No gain")
    args = archive.parser().parse_args([
        "decide", "--archive", str(case.path), "--recent", "4", "--min-stagnant", "3"])
    decision = archive.route_decision(args)
    brief = case.brief("--recent", "4")
    print(decision["action"], decision["unresolved_candidates"])
    print([x["candidate_id"] for x in brief["review_frontier"]["selection"]])
finally:
    case.doCleanups()
```

基线输出为 `explore []` 和 `['open-parent']`。修复后的预期应由共同机会规则明确规定，不要求所有建议文本完全相同。

### 2.3 上下文与档案观察

纯调用 `prompt_for_turn`，空 context 的 UTF-8 字节为 work 9,944、repair 11,079、rethink 10,339、measure 10,992；SKILL.md 为 24,546 字节。未调用模型。不能把这些数字当作实际 token、费用或质量改善。

静态发现 learning 验证反复扫描已有候选：`candidate_archive.py:88–90` → `scoped_learning.validate` → `active`。N 个候选、L 个经验记录时，这部分可产生 O(N×L) 累计访问；未测出它占整个 campaign 的比例，因此方案要求先 profiling。

## 3. 重要代码依据

| 主题 | 代码位置 | 审查结论 |
| --- | --- | --- |
| 封存/恢复/接收 | `autonomous_campaign.py:441–478,481–587,599–673` | caller 仍协调很多时序；移动责任时保留封存先于启动、合法追加独立接收等语义 |
| 深 Module 已存在 | `campaign_archive.py:104–186`；`campaign_policy.py:85–194` | 方案以深化现有 Interface 为主，不能把已有实现描述为从零缺失 |
| 结果已归一化 | `candidate_archive.py:193–260,737–781` | 已兼容 correct/valid、嵌套 evaluation、不同 score 命名与 partial；应集中这套规则 |
| 查询耦合 | `candidate_archive.py:1044–1299`；`campaign_trials.py:69–71,116,123` | argparse、核验与查询策略交织，跨 Module 使用私有 helper |
| 包裁剪/交付 | `campaign_search.py:409–430,434–598,602–759` | 通用截断与反向核对身份耦合；按 mode 先选完整卡片可减少调用知识 |
| 指令升级 | `autonomous_campaign.py:215–219,772–790` | prompt 引用实时 skill；workflow provenance 还需版本化内容，不能仅存 hash |
| prediction 依赖环 | `prediction_evidence.py:11–12`；`compare_prediction_results.py:121–126` | 局部 import 绕过环；适合把共同核验/比较放入实际核心 Interface |
| ML 已有起点 | `examples/tabular_pilot.py:215–233,279–314` | 实际 fit、回执、冻结短名单、模型 hash 和确认预测可提取；目前仍是预设 pilot |
| 证据搬运 | `candidate_archive.py:202,795–796`；`scoped_learning.py:44–50` | 部分绝对路径已进入证据身份；机械替换路径会破坏 seal 含义 |

这些路径均以 `skills/competition-optimize/scripts/` 为基准，除显式写出的 examples。行号固定对应审查基线。

## 4. 外部一手资料

所有下列材料均实际读取正文或固定版本源码。已有仓库研究文档仅用于发现线索，未直接沿用其中结论。以下编号供方案查阅，不代表来源按效果排名。

### R1：MLE-STAR

[论文 v3 正文](https://arxiv.org/html/2506.15692v3)，实际解析回退到同版本 PDF；相关内容为 §3.1–3.4、PDF 第 5–7 页。

**E：** 方法先构造和评价候选，用执行过的消融结果选择要深入的代码块，再实施后继；另检查生成流水线中的数据使用和泄漏风险。**I：** 本项目可以让已有 diagnostic 结果直接影响代码目标，按需要激活对应流程。**边界：** 论文中的 checker 含模型判断，不能把“审查通过”当作实际拟合来源证明；预设循环数和多 agent 配置不直接迁入。本轮未复现论文成绩。

### R2：AIDE

[固定源码 agent.py](https://raw.githubusercontent.com/WecoAI/aideml/ad73d227af481bea3de06f884f41b2993dd6453a/aide/agent.py)，commit `ad73d227af481bea3de06f884f41b2993dd6453a`，主要读取 161–192、369–439 行。

**E：** search_policy 在 draft/debug/improve 之间选择；执行后保存代码、输出与解释。该版本以 LLM 反馈中的 metric 构造节点指标。**I：** 借鉴执行状态驱动动作选择，保留本项目确定性 adapter 计分。**边界：** 不把 greedy、debug 概率或深度上限当作普遍最优策略。

### R3：ShinkaEvolve

[setup skill](https://raw.githubusercontent.com/SakanaAI/ShinkaEvolve/8adc053a2ce4511ad2ac310e004c530a73fb974a/skills/shinka-setup/SKILL.md)、[inspect skill](https://raw.githubusercontent.com/SakanaAI/ShinkaEvolve/8adc053a2ce4511ad2ac310e004c530a73fb974a/skills/shinka-inspect/SKILL.md)，commit `8adc053a2ce4511ad2ac310e004c530a73fb974a`。

**E：** setup 先建立候选接口与 evaluator 并 smoke test；inspect 将排名、反馈、代码打包。**I：** 任务接入与日常续跑可以有不同指令负担。**边界：** inspect 在没有正确结果时有明确标注的 fallback；本项目不能把这种展示 fallback 当作可晋升结果。未安装或运行该系统。

### R4：ICFP 2025 Team Unagi

[官方任务 PDF](https://icfpcontest2025.github.io/specs/task.pdf)、[Takuya Akiba / Team Unagi 作者复盘](https://sakana.ai/icfp-2025/)、[固定 evaluator](https://raw.githubusercontent.com/icfpc-unagi/icfpc2025/23439908ed97bdff72c0d95803e9a875b22c9436/evo/exp2/evaluate.py)，commit `23439908ed97bdff72c0d95803e9a875b22c9436`。官方规则定位 PDF 第 4 页；evaluator 231–304 行。

**E：** 官方对正确迷宫图按 expedition 次数排序，总榜采用 Borda。团队先做 SAT 整体解法，再优化编码，后继加入中间连接变量。所读局部 evaluator 实际优化负 p25 时间，非 AC 或内部目标未达成时记超时惩罚；`correct` 只需至少一次 AC。

**I：** 学习完整表示替换，并把正式目标、局部 fitness、逐例有效性分开记录。**边界：** 未复现速度或整个比赛提交；团队排名不能归因于这一个机制，并发参数不变成本项目默认值。

### R5：SIIM-ISIC 2020 Ian Pan

官方对象通过 [CompetitionService](https://www.kaggle.com/api/i/competitions.CompetitionService/GetCompetition?competitionName=siim-isic-melanoma-classification) 确认；Evaluation/Data/Rules 通过 [PageService](https://www.kaggle.com/api/i/competitions.PageService/ListPages?competitionId=20270&competitionName=siim-isic-melanoma-classification) 成功读取。作者复盘通过 [Kaggle 原讨论 API](https://www.kaggle.com/api/v1/discussions/175324/get) 获取，响应绑定作者 Ian Pan、该比赛和 2020-08-18 日期。

代码核对：[README](https://raw.githubusercontent.com/i-pan/kaggle-melanoma/caaec0d7e9cafc7b405eb86e7fdf00107d89e1d9/README.md)、[患者分组切分](https://raw.githubusercontent.com/i-pan/kaggle-melanoma/caaec0d7e9cafc7b405eb86e7fdf00107d89e1d9/src/etl/1_create_cv_splits.py)、[最终文件入口](https://raw.githubusercontent.com/i-pan/kaggle-melanoma/caaec0d7e9cafc7b405eb86e7fdf00107d89e1d9/src/eval/generate_sub.py)，commit `caaec0d7e9cafc7b405eb86e7fdf00107d89e1d9`。

**E：** 官方指标为 ROC-AUC，提交两列 `image_name,target`。作者报告单折不稳定，因此每项实验看五折；切分代码先按患者形成折，再映射回图像。复盘保留了增强无效、过拟合和最终选择不确定的记录；事后 private LB 最好的单体没有被选中。

**I：** 验证稳定性和数据单位应先落实，模型/训练信号改动共享同一协议；单体与组合都保留，并冻结最终选择规则。**边界：** 本次未取最终官方榜单独立核验作者自述名次，未复训或证明伪标签无泄漏，不把某种增强在这题无效泛化为禁用。

公开代码还提供一个交付教训：所读 `generate_sub.py:42` 引用未定义的 `df_list`，末段没有构造官方两列。这是固定公开版本的静态缺口，未执行该脚本；不能推成比赛实际提交有同样问题。获奖仓库的标题与 README 不能替代最终文件核验。

### R6：ALE-Bench

[固定 README](https://raw.githubusercontent.com/SakanaAI/ALE-Bench/3da9b12fb5d112dabb3af693d1a42031c95142bc/README.md)，commit `3da9b12fb5d112dabb3af693d1a42031c95142bc`，129–194 行。

**E：** 示例使用 public_eval 做迭代和选择，最后才调用 private_eval，并读取资源消耗；明确禁止优化期间使用 private seeds 等信息。**I：** 工作流对照应冻结交付选择、保留独立确认与成本。**边界：** 这是评测结构来源，不代表本项目已经完成 ALE-Bench 测试。

### R7：MLE-bench

[固定 README](https://raw.githubusercontent.com/openai/mle-bench/507f92e1138bb6e40dac5c6ee7a6758e6424bf97/README.md)，commit `507f92e1138bb6e40dac5c6ee7a6758e6424bf97`，69–84、132–141 行。

**E：** 推荐重复 agent 运行、报告分布与资源；数据从公开训练集重新切出测试集，不能当原比赛隐藏 private test。**I：** 为本项目设置匹配的多次工作流对照，报告各任务的失败与收益。**边界：** 不把其机器配置、24 小时或至少三次运行变成普通 campaign 的硬默认；方案中的次数仅为具体评估设计。

## 5. 外部证据怎样改变方案

| 原始决策问题 | 证据后的选择 | 未被证据支持的扩张 |
| --- | --- | --- |
| 继续加更多通用指导是否足够？ | 优先把消融/失败/参考机制接到真实代码目标与后继结果；按需交付相关材料 | 没有证据支持“提示更长就更会比赛” |
| 是否换成完整进化框架？ | 现有 Policy/Archive 已承担具体责任；先修规则与真实 Interface | 未建立迁入种群、向量库或多 agent 搜索的收益依据 |
| 下一种通用能力是什么？ | 从已有 tabular pilot 提取一条有真实 fitting/OOF/交付证据的 ML adapter | 不承诺一次支持多分类、所有自定义指标和所有平台 |
| 怎么证明改造有用？ | 行为兼容、过程效率与独立确认分开测，旧案例只作回归 | 测试数量、短 prompt、局部时间或作者名次都不能单独证明提分 |

两份独立参赛经历的共同点是：验证协议决定比较是否有意义，完整机制可以改变可达解空间，最终选择本身也会出错。它们的差异同样保留：算法局部加速需要回到官方目标，ML 的分组/训练信号与分布问题需要任务专属证据。

## 6. 保存位置与限制

本轮中间审查、原始测试输出、复现脚本和网页快照保存在本机 `/tmp/competition-skill-refactor-20261110/`；它是临时研究工作区，不是长期归档承诺。项目内这两份文档保存结论、版本、命令和原始来源链接，避免要求未来读者只依赖临时目录。

研究采用 Deep Search：四个问题方向均已给出证据或明确限制。普通网页检索出现验证码、超时及摘要匹配差，随后转为已定位的一手正文、官方 API 和固定源码；没有把搜索摘要当证据。未执行上游安装命令或第三方程序。

本轮尚未得到：改造后性能/提分结果、真实长周期运行的新证据、旧原始实验产物恢复情况，以及完整跨题型能力验证。方案已将这些分别安排为后续验收或限制，不将未知项记为成功。
