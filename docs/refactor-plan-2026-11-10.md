# Competition Optimize 重构与工作流改造方案

审查日期：2026-11-10。代码基线：`80331a1`。状态：已获授权实施，当前进展与验证见 [实施记录](refactor-implementation-2026-11-10.md)。下述审查统计保留原始基线；方案编写阶段未修改实现或启动比赛 campaign。

## 1. 建议与目标

建议采用**保留现有证据与恢复机制的渐进重构**：先修正已复现的比较和检查问题，再统一结果与证据查询 Interface，减少每轮无关上下文，最后补齐一条真实的机器学习训练—验证—交付流程。

现有项目已具备有价值的工程基础：26 个脚本约 8,312 行、31 个测试文件、13 份参考文档。本次完整运行 520 项测试，全部通过，测试耗时 182.780 秒；另外的定向探针复现了三个现有测试没有覆盖的问题。测试通过说明当前已编码行为稳定，不能替代比赛效果验证。详细方法与来源见[审查证据](refactor-evidence-2026-11-10.md)。

改造目标按顺序是：

1. 同一组实验事实在不同入口得到一致的资格判断与比较结果。
2. 调用方只需要理解少量稳定 Interface，不必掌握内部投影、核验和状态落盘顺序。
3. 每轮交给 agent 的信息直接服务当前决策，保留策略推导和跨路线探索能力。
4. 至少让一种 ML 任务从真实训练、OOF 到冻结交付可复现，明确其它题型的能力边界。
5. 用独立任务上的结果与成本判断工作流是否改善；性能优化先找到实际开销。

本方案按现有产品约定设计：保留单 agent 顺序优化、无 skill 自设总轮数/成本上限、专门调参需明确请求、确认数据不参与开发决策、正式提交需明确授权。公平对照实验可以预先约定有限预算；该预算不变成日常 campaign 的默认限制。

## 2. 当前结构与值得保留的部分

```mermaid
flowchart LR
  T[题目、当前实现、任务协议] --> D[autonomous_campaign 驱动]
  D --> P[CampaignPolicy 选择本轮工作]
  P --> E[CampaignEvidence 与 handoff]
  E --> C[Codex 调用与本地执行]
  C --> A[adapter 结果与候选档案]
  A --> V[CampaignArchive 核验与接收]
  V --> P
  D --> R[campaign_runtime 进程恢复]
```

| 现有 Module | 已解决的责任 | 重构原则 |
| --- | --- | --- |
| `CampaignArchive` | 已确认前缀、追加接收、损坏尾部隔离；档案接收独立于 CLI receipt 成功 | 保留一个持久化事实源，不另建第二套账本 |
| `CampaignPolicy` | 纯决策；修复、测量、策略重审与上下文轮换；成功交接后才确认曝光 | 保留纯计算 Interface，逐步减少调用方必须提供的内部字段 |
| `CampaignEvidence` / `ComparisonEvidence` | 同一档案视图中的比较投影与复用 | 在现有实现上深化查询，不再叠一个平行“智能记忆层” |
| `EvidenceReads` | 单次操作内共享文件核验，跨操作重新检查 | 保留核验时效，避免未经需要的跨轮缓存 |
| `measurement_plans` | 固定配对测量计划、中断续测、停止未完成计划 | 保留计划身份和配对规则，复测不能制造新实现 |
| `campaign_runtime` | 封存启动意图、锁、进程身份、worker 接管、退出证据 | 这些机制已有具体故障场景；重构不能退化成简单 subprocess 循环 |

代码定位：[档案接收](../skills/competition-optimize/scripts/campaign_archive.py#L104)、[策略决策](../skills/competition-optimize/scripts/campaign_policy.py#L45)、[证据视图](../skills/competition-optimize/scripts/campaign_search.py#L30)、[纯比较证据](../skills/competition-optimize/scripts/candidate_evidence.py#L196)、[进程执行](../skills/competition-optimize/scripts/campaign_runtime.py#L231)。

## 3. 代码审查结论与优先级

下文 **E** 表示本次已读源码或实际探针直接支持；**I** 表示据此提出的设计判断；**待测** 表示尚无效果或性能实测。优先级针对本项目改造，不是安全严重性评级。

| 优先级 | 发现与影响 | 证据 | 建议 |
| --- | --- | --- | --- |
| P0 | `decide` 与 `brief` 对失败后继是否关闭未决机会有分歧，可能让 agent 错过仍值得修复的分支 | **E**：同一临时历史中，`decide` 返回 `explore`、无未决机会；`brief.review_frontier` 保留 `open-parent`。前者只看 changed child，后者要求有效观测等条件 | 共用“机会仍开放”的纯规则；保留各入口不同的展示窗口 |
| P0 | timeslot 比较器只检查双方用例集合相等，未检查是否覆盖声明的完整工作负载 | **E**：两份各只有 1 个 case、都声明 `full` 的手工结果被接受；正常 full 配置应有 90 个 case。这是持久结果消费缺口，不是声称正常 runner 只跑 1 例 | 从封存协议核对 expected case IDs，分别验证双方完整性后再配对 |
| P0 | C++ 规则扫描按 `*` 后的变量名白名单判断，既可能放过乘法，也可能误拒合法指针 | **E**：`2 * current` 放行；`int* p` / `*p` 被拒。文档已要求人工审查，扫描本身不能证明全部规则通过 | 独立规则检查与打包；优先复用任务的权威检查器，缺少时明确覆盖范围；需要语法区分的规则用语法级检查 |
| P1 | 结果语义分散在 adapter、`result_metadata`、CLI flags、记录组装和核验路径；两种 stage 的含义不同 | **E**：已有 normalizer，不能当成缺失重建。prediction stage 是 development/confirmation，timeslot 是 smoke/short/full/package | 收拢现有 `ResultEvidence` Interface，分别表达用途、保真度和操作 |
| P1 | `optimization_brief` 暴露 argparse、投影、核验视图与多组曝光状态；`campaign_trials` 通过档案 CLI Module 调私有函数 | **E/I**：调用方承担过多内部知识 | 深化单次档案查询 Interface，CLI 只做输入输出适配 |
| P1 | 每轮提示无条件解释大量可选能力，证据包先大范围组装再通用递归截断 | **E**：空 context 的 work prompt 为 9,944 UTF-8 字节，repair 为 11,079；SKILL.md 为 24,546 字节。这里测的是字节，不是 token | 稳定核心＋当前模式说明＋实际存在的证据；整张卡选择后再缩短描述 |
| P1 | 轮次封存、CLI 协议、恢复、用量和状态持久化在 driver 中交织 | **E/I**：新增一个状态字段需要理解多处初始化、恢复、消费与展示路径 | 在 driver 内集中轮次状态转换；单独封装真实 Codex invocation seam |
| P1 | prediction 工具尚未覆盖实际训练、OOF 血缘及最终模型/提交身份 | **E**：`UNCHECKED_RULES` 明示缺口；tabular pilot 已有可复用训练回执 | 从一条真实任务流程提取 ML adapter，不先承诺支持所有 Kaggle 类型 |
| P2 | learning-heavy 档案存在重复前缀扫描；历史证据依赖绝对路径 | **E/I**：有静态复杂度依据和失效文档路径；整体性能收益**待测** | 先量测，再维护必要投影；证据搬运使用显式映射与内容核验 |

关键源码：[机会判断 A](../skills/competition-optimize/scripts/candidate_archive.py#L896)、[机会判断 B](../skills/competition-optimize/scripts/candidate_archive.py#L1017)、[timeslot reader](../skills/competition-optimize/scripts/compare_timeslot_results.py#L23)、[配对检查](../skills/competition-optimize/scripts/compare_timeslot_results.py#L97)、[规则扫描](../skills/competition-optimize/scripts/evaluate_current_timeslot.py#L203)、[现有 normalizer](../skills/competition-optimize/scripts/candidate_archive.py#L193)、[brief Interface](../skills/competition-optimize/scripts/candidate_archive.py#L1044)、[提示生成](../skills/competition-optimize/scripts/autonomous_campaign.py#L331)。

## 4. 从比赛与自动优化资料中采用什么

资料详见[一手来源与适用边界](refactor-evidence-2026-11-10.md#4-外部一手资料)。这里讨论具体机制的迁移，不以论文成绩或参赛名次推断本项目必然提分。

| 材料 | 可借鉴的具体机制 | 对本项目的落点与边界 |
| --- | --- | --- |
| MLE-STAR，论文 §3.1–3.4 | 检索适用方法，执行候选；用消融结果选定要改的代码块；检查数据使用与预处理 | 让已有 `diagnostic` 结果直接产生下一项代码目标；只在诊断能改变选择时运行，不把每轮消融变成强制仪式 |
| AIDE，固定版本 `agent.py` | draft/debug/improve 由执行状态驱动；失败代码和实际输出进入修复 | 保留现有 repair 优先级；评分继续由 adapter 产生。该版本从 LLM 日志解释中提取 metric 的方式不迁入 |
| ShinkaEvolve，setup/inspect skills | 搜索前建立稳定候选—evaluator 接口并 smoke test；把实测结果、反馈和代码一起交接 | 将任务接入与续跑分开；普通续跑复用已核验协议。不照搬其批次暂停习惯或完整进化框架 |
| ICFP 2025 Team Unagi 作者复盘及 evaluator | 先有整体 SAT 解法，再改变中间变量与编码；局部运行时间和官方探测次数/排名是不同目标 | 提案可以替换完整表示；同时记录正式目标、代理指标和逐例合法性。不能拿至少一例 AC 当全例通过 |
| SIIM-ISIC 2020 Ian Pan 原始复盘及切分代码 | 单折不稳定后比较五折；按患者划分；改变训练信号；记录无效增强和最终选择失误 | 补实际 fitting/OOF 血缘；保留单体、组合和冻结选择规则。具体模型、伪标签和外部数据许可不能直接泛化 |
| ALE-Bench / MLE-bench | 开发反馈与最终独立评价分开；重复 agent 运行并报告资源；明确重切分和评测边界 | 增加工作流版本和成对效果评估；小型 pilot 的成功不表述为跨任务能力已验证 |

现有 skill 已写入不少上述思想。此次改造的新增价值应体现在：规则一致、关键动作有可调用接口、证据能进入下一次决策，以及实际任务对照；不能把新增说明段落计为能力提升。

## 5. 目标工作流

### 5.1 接入任务：产出一个可执行协议

将目前散落的题目说明、adapter 参数和人工约定收成精简的 `TaskSpec`。先利用现有合同和事实，避免要求用户填写大量新模板。只保留会影响执行或判断的字段：

- 任务身份、候选入口、允许修改的内容、实际比赛规则与可用数据。
- 目标及方向、聚合方式、未知分项；质量指标与资源测量各自的含义。
- 数据/实例集合、统计单位、开发协议、确认协议；ML 的 folds 和预处理拟合范围。
- 构建/训练/预测/评测/打包命令，以及 task adapter 实际具备的能力。
- 当前适用的硬约束、用户限制和停止条件；不存在的限制留空。

接入完成条件是：可信 baseline 可以运行、已知正反例能验证 evaluator、结果完整性有检查。资料缺失可以阻止依赖它的执行，但不阻止独立准备工作。

### 5.2 普通一轮：少量输入，一项可执行决策

```text
读取本轮所需证据 → 选择父版/独立构造/诊断/修复/测量
→ 提出一个完整机制 → 实际实现 → 任务 adapter 执行
→ 接收结果与成本 → 判断晋升和后续投入 → 执行下一轮
```

默认输入包含任务约束、选中父版的源码位置、相关已完成试验和当前具体问题。只有存在对应事实时，才加入固定测量计划、互补案例、资源权衡、条件经验或实施复核。用户中途想法进入下一次决策，保留原意和试验优先级。

提案复用现有字段：依据与父版、实际改动及必要耦合部分、预期观察与验证方法。实现与测量仍分开；诊断失败不等于方法失效，低分但互补的候选仍可以保留。普通续跑不重复阅读所有规则、旧日志和高级用法。

### 5.3 按题型保留不同的完整闭环

| 算法/程序路径 | ML 路径 |
| --- | --- |
| 可行构造 → 表示/邻域/编码假设 → 正确性与规则检查 → 匹配实例和资源条件比较 → 冻结源码/打包 | 统计单位与划分 → baseline → 实际 fold 训练和预测 → OOF/错误分析 → 特征、模型或训练信号改进 → 冻结模型或组合 → 独立确认/最终产物 |
| 同时看逐例质量、有效率、不同规模与真实运行限制下的质量 | 同时看官方聚合、fold/时间/组退步、拟合来源与训练/推理成本 |
| 减少单次操作耗时不自动等于最终分数提升 | 固定预测 bootstrap 不自动覆盖训练随机性，也不证明没有泄漏 |

结束时冻结交付选择，验证最终字节与候选身份。C++ ZIP 与预测 CSV 各有自己的格式核验；平台反馈以原始回执保存。正式提交继续使用独立、显式授权的动作。

## 6. 目标 Module 与 Interface

下面是责任划分，不要求一次迁目录或把所有字典改成类。先在现有文件内收拢行为，再根据真实调用决定物理文件边界。

| Module / Interface | 隐藏的复杂性 | 调用方必须知道的内容 |
| --- | --- | --- |
| `ResultEvidence.read(raw, artifacts, protocol)` | 旧结果格式、字段映射、有效性覆盖、比较身份和来源等级 | 返回可用观测、比较条件、未核验项；未知分数仍未知 |
| `EvidenceSnapshot`，深化已有证据视图 | 档案前缀投影、机会开放规则、提案/经验检索、按需文件核验 | `brief(query)`、`trace(id)` 等实际查询，不传内部索引或私有 helper |
| `Handoff.prepare(mode, evidence, task)` | 当前模式的完整必需卡片、可选卡片选择、提示与交付资格 | 封存后的提示/证据及可确认的交付意图 |
| `TurnLifecycle`，深化现有 driver | prepare/恢复/观察/接收的时序、记账及 durable state 转换 | 准备本轮、观察执行、接收结果；进程原语继续由 runtime 管理 |
| `CodexInvocation` | CLI 参数、事件、receipt、session 与错误分类 | 明确的执行结果；测试用已有假 CLI 替换 |
| 具体 `TaskAdapter` | 题型对应的构建或训练、评测和产物核验 | `evaluate(candidate, protocol, output_dir)`；支持时提供 `finalize(...)` |

重要约束：

1. **结果合同分开表达用途和保真度。** 建议保留 `purpose=development/confirmation`；timeslot 的 fidelity 示例为 smoke/short/full，ML 则由具体协议表达 folds、样本范围或训练资源，不能共用固定阶段枚举；package 是操作。旧记录从已有 role/任务协议恢复用途，不能把旧 `full` 默认为 development。
2. **质量与资源只在证据允许时分开复用。** 先保留现有严格比较，只有具体 adapter 明确证明质量可跨环境复用时才拆合同；时间不能随之被视为可比。
3. **保持旧读入与落盘兼容。** 第一阶段保持 candidate JSONL schema 1、campaign schema 2 和旧封存轮次；新字段有明确版本语义，不批改旧 JSONL。
4. **状态仍有一个权威来源。** `TurnLifecycle` 不复制 Policy/Archive 的状态，也不另引入工作流数据库。
5. **prediction 先解除真实依赖环。** `prediction_evidence → compare_prediction_results → prediction_evidence` 的核心计分/核验逻辑收进共同 Interface，现有 CLI 入口继续可用。
6. **用 `workflow_provenance` 记录指令版本。** 保存 skill hash、runner revision、实际 CLI/model 标识（不可得时记 unknown），但不自动将它们并入 candidate comparison key，避免仅换工作流就失去同一 evaluator 下的候选可比性。当前 sealed prompt 仍引用实时 SKILL 路径，只有 hash 不足以冻结正文；后续采用版本化安装或指令快照，保留旧在途请求的原引用。迁移在安全检查点生效；无法还原旧指令内容时明确披露，不能宣称完全按原指令恢复。

## 7. 分阶段交付

| 阶段 | 具体改动与范围 | 进入下一阶段前的验收 | 回退方式 |
| --- | --- | --- | --- |
| P0a：统一机会规则 | `route_decision` 与 `brief` 共用纯规则；补失败/缺分数/未决/独立构造/别名用例 | 两入口在相同历史中共享机会资格；各自窗口行为仍明确 | 回退代码即可，档案格式不变 |
| P0b：工作负载完整性 | timeslot reader/adapter 共享封存 workload 定义，检查 missing/extra/duplicate | 双方共同漏 case 也被拒；合法 short/full 保持可用；旧缺证据记录明确标识 | 保留旧 reader 的只读兼容路径，不能继续冒充完整测量 |
| P0c：规则检查范围 | 分离检查与 ZIP；修复乘法/解引用识别，保留未覆盖规则标记 | 两个探针及字符串/注释/指针形式等相关例子有明确结果；包字节核对保持 | 不改变正式比赛规则；可回退实现并保留覆盖说明 |
| P1a：结果与预测核心 | 将现有 normalizer 收进 `ResultEvidence`；prediction CLI 调用共同核心 | 两种真实 schema、manual/executed、partial/failed、确认/开发、源码/产物身份保持语义 | 旧命令和字段的兼容 reader 保留 |
| P1b：证据查询 | 深化 `ComparisonEvidence/CampaignEvidence`；移除跨 CLI Module 私有调用 | CLI/driver 核心事实一致；无文件回放、当前文件篡改与首次错误语义不变 | 旧查询 facade 暂留，差分输出后切换 |
| P1c：上下文与入口 | 核心 SKILL 精简为主循环和路由；按 mode/事实生成提示；完整卡片选择 | 活跃功能仍可发现、必要身份不被截断、未交付不计曝光、旧封存请求不变 | 新旧渲染器可固定选择，按工作流版本比较 |
| P1d：轮次与调用 | 集中 schema-v2 state codec/状态转换；收口 CodexInvocation | 中断接管不重复启动；合法追加即便 CLI 失败仍保留；completion verifier 恢复不变 | 不迁移运行中档案，保留旧状态读入 |
| P2a：一条真实 ML 闭环 | 从 `tabular_pilot` 提取训练回执、fold/OOF 协议、冻结模型/组合与最终 CSV 核验 | baseline→实际改动→可比 OOF→冻结确认→可复算产物；有相关组/时间用例 | 新 adapter 独立接入，现有 score-only 工具保留 |
| P2b：按测量优化与归档 | 测混合长档案；必要时增量维护 learning heads/plan 投影；显式 evidence bundle/resolver | 相同历史结果一致，I/O/时间/内存有实测；移动后按旧身份和内容核验，原始字节不改 | 优化可撤回；导出包不修改原档案 |

P0 的三个改动分别提交，避免把无关行为修正混成一个大 diff。P1 的结构迁移与提示策略改变也分别验证。优先交付到 P1c，再根据真实使用决定 P1d/P2 的投入顺序；不能为重排文件拖延已确认的行为修复。

## 8. 怎样验证确实变好

### 8.1 工程与兼容性

- 以本次 520 项通过结果为基线；将三个探针改成公开行为测试。不要为了维持数量保留绑定内部函数调用次数的测试。
- 保存代表性旧格式夹具：prediction、timeslot、混合 candidate JSONL、带未完成测量计划的 campaign、旧 sealed turn。
- 核对失败路径：写入后 CLI 失败、request 已封存但 worker 未起、worker 已起但 manager 消失、退出已写但状态未消费、坏尾部隔离中断。
- 新旧查询对同一混合历史做差分比较；只有预先列明的缺陷修正允许变化。内部重构不能改变确认隔离、身份或未决机会语义。
- CLI smoke 使用临时目录和假 CLI；真实 CLI 协议验证单独记账，不把它藏在常规单测中。

### 8.2 工作流质量：预先约定的成对实验

用旧版 `80331a1` 和各阶段固定版本比较。固定同一模型/CLI 配置、题目、初始实现、数据划分、硬件与可用资料；每个任务重复 agent 运行，初始方案采用至少 3 个匹配 seed/独立运行。实验资源由实际评测计划约定，报告超时和失败，不能挑最好一次。

任务分两层：工程小任务用于快速暴露回归；独立任务用于判断优化能力。第一批建议包含一个组合优化/程序任务、一个含 group 或 time 结构的 ML 任务；是否扩到更多任务取决于实际投入。小批结果只支持相应任务上的结论。已用于改造的旧背包/调度案例只作开发回归，不作为新的独立提分证据。

| 维度 | 记录内容 | 判断方式 |
| --- | --- | --- |
| 有效交付 | 完整评测、合法输出、可复现最终文件比例；失败原因 | 不能因少检查或忽略失败提高“成功率” |
| 真实目标 | 预先冻结规则下的独立确认分数，相对 baseline 的同口径差值 | 跨任务先各自报告，不直接平均不同量纲原始分数 |
| 过程效率 | 首个可用候选时间、总墙钟、模型用量/费用、实际评测成本、有效实现数 | 分开模型耗时与本地执行；未知费用不填 0 |
| 决策有效性 | 诊断是否接到实际后继、失败恢复、重复已否定机制、遗漏待办 | 根据源码与结果追踪，不能仅评分 agent 自述 |
| 上下文 | prompt/证据字节、实际 token、必要事实是否完整到达 | 缩短字节不是自动改善；须与行为及结果一起比较 |

先比较“仅修正确性＋结构迁移”，再比较“按需上下文”，最后比较“新增 ML 闭环”。不要把这些变化合在一起声称某一机制提分。保留持平与退步结果；收益不明确时保持可逆选择。

### 8.3 性能与长跑

档案 benchmark 至少区分普通 candidate、learning-heavy、plan-heavy、长 feedback 和大 case-profile；记录 parse、brief、prepare、receive 的时间、读取字节和峰值内存。可以用 100/1,000/10,000 条的固定内容梯度检查增长，但规模是测量设置，不是新系统容量承诺。只有开销影响实际轮次效率时才做索引或缓存。

长跑验收继续使用现有故障注入，再单独做真实持续运行检查。当前历史短跑、假 CLI 和本次单测不能证明跨日可靠性；此次方案没有新增这项结论。

## 9. 文档、安装和证据交付

将 README 改成能力表、最短使用路径和证据入口；详细历史迁入已有 docs 导航。旧计划中默认额度等与现行规则不同的表述标明历史范围，避免被当作当前操作指引。

本次未在 `~/.codex/skills`、`~/.agents/skills` 找到该 skill 的安装项。后续在明确安装路径时提供一种可核验的安装/更新方法并记录版本；本次不安装。历史验证文档的 33 个原始绝对路径当前不可访问，先定位原始产物再修链接，找不到就标记不可复核，不补造证据。

新 run 的可迁移性通过显式 artifact 引用与导出封套解决：保留旧路径、内容 hash 和映射，核验新位置的字节；不搜索全盘猜文件，不直接替换已参与 seal 的旧路径。开发结果、确认结果与平台回执保持来源差异。

## 10. 本轮不建议优先投入的方向

没有现有瓶颈或调用需求支持时，暂不引入数据库/向量记忆、通用 DAG、provider 插件系统、岛屿种群或多 agent 搜索。它们会改变运行成本、调度和比较方法，需要单独证据。

也不把重构变成全面增加防御或大类树：当前锁、核验、隔离、恢复已有实际责任，应保留；新增抽象必须隐藏调用方当前确实承担的复杂性。自动平台提交、通用全题型支持、全量机器学习数据平台不列入这一轮的完成条件。

推荐先实施 **P0a–P0c → P1a/P1b → P1c**，形成第一份可评估版本。其完成标准是：已确认问题修正、核心规则一致、兼容性验证通过、每轮上下文与实际行为可测，而不是文件数增加或说明更长。
