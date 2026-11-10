# 长周期驱动验证（2026-10-22）

> 历史证据可访问性（2026-11-10）：本文引用的 `/home/lzh/competition-agent-validation/` 原始路径在当前环境不可访问。以下数字保留为历史记录，不视为本轮重新验证；原始链接不重写。当前验证见 [本轮实施记录](refactor-implementation-2026-11-10.md)。

本轮验证的是持续执行、检查点交接、故障恢复、共同基准恢复、同口径收益信号、旧分支检索与跨上下文证据。实现入口为 [autonomous_campaign.py](../skills/competition-optimize/scripts/autonomous_campaign.py)，进程原语在 [campaign_runtime.py](../skills/competition-optimize/scripts/campaign_runtime.py)，搜索信号与交接包在 [campaign_search.py](../skills/competition-optimize/scripts/campaign_search.py)，已完成试验召回在 [campaign_trials.py](../skills/competition-optimize/scripts/campaign_trials.py)。启动及恢复命令见[使用说明](../skills/competition-optimize/references/unattended-campaign.md)。

## 候选规则与文件核验直接依赖（2026-10-23）

按四步顺序提取 `candidate_evidence` 的纯身份、观测与比较规则，分离 `evidence_files` 的当前文件核验，再移除 `measurement_plans` 和 `scoped_learning` 的整模块参数。两个消费者直接导入具体规则，文件读取视图使用 `EvidenceReads | None`；档案、交接和试验检索的调用一并迁移。原档案导出直接引用同一实现，CLI、JSONL schema 1、campaign schema 2 和旧 sealed turn 不需要迁移。[候选证据说明](candidate-evidence.md)记录了依赖方向和 interface。

迁出的 19 个类和函数与原定义逐一比对一致；测量和经验模块全部 26 个定义在去除整模块调用、明确读取类型后保持原逻辑。已有文件读取和观测测试改为使用新入口，新增两个独立解释器消费场景：真实测量计划在源码/result 已删除后仍能查询归档状态，显式核验当前文件则失败；经验修订链可独立校验、检索和确认交付。两个场景均不加载 `candidate_archive`。

最终完整回归 `/usr/bin/python3 -m unittest discover -s skills/competition-optimize/tests -p 'test_*.py' -q`：**520/520 通过，180.442 秒**。19 个变更 Python 文件编译、Skill 的 `quick_validate` 和 `git diff --check` 通过。首次完整回归发现文件读取测试的模块别名与局部集合重名；修复后该文件 9 项通过，再重跑得到上述完整结果。验证范围为本地 Interface、档案和长期驱动流程，本轮未新增官方提分或端到端提速证据。

## 档案读取、核验与接收收口（2026-10-23）

按 `codebase-design` 的四步设计顺序，先从 `read_records` 抽取纯字节入口 `parse_records(raw, source)`，共用已有索引和顺序验证，删除前缀回放的临时文件。随后新增 [CampaignArchive](campaign-archive.md)，用 `verified`、`confirmed` 和 `receive` 集中全量核验、交接前后检查及轮末接收。Driver 接入后删除原四个档案 helper，直接使用接收结果中的新增事件、计数变化与 evidence；锁、CLI 输出身份、receipt、campaign events 和最终 state 保存仍在 Driver。

核验范围保持明确：历史回放不读源码/result，启动与无在途轮次恢复核验全量文件，轮末接收只核验新增 candidate，handoff 按需复核引用。坏尾部整段保全、写 journal 后才截断；已确认前缀损坏直接报错。合法追加与 CLI 成功独立，旧 JSONL、schema-v2 及 sealed turn 恢复不需要迁移。

新增 20 项公开档案 Interface 测试，使用真实临时目录覆盖全量与新增核验范围、合法和零追加、重复接收、前缀篡改/截短/消失、含合法事件的整个坏尾部隔离、result/source/metadata 损坏、隔离副本不完整、journal 写入前后及已截断恢复、token/hash/JSON journal 损坏拒绝。将 Driver 中对应的隔离副本恢复用例迁至该 Interface，保留跨 start/resume、receipt 和进程的流程保证。字节回放另覆盖无文件依赖、物理行号和残缺尾部；原混合历史、错误优先级及旧 digest 语义继续验证。

固定脚本与测试后完整回归 `/usr/bin/python3 -m unittest discover -s skills/competition-optimize/tests -p 'test_*.py' -q`：**518/518 通过，182.871 秒**。变更脚本和测试的 `py_compile`、Skill 的 `quick_validate` 与 `git diff --check` 通过。验证覆盖本地档案与长期驱动流程；本次未量测整体提速或新增比赛提分。

## 每轮决策、交付确认与证据视图收口（2026-10-23）

按设计顺序集中四项职责：新增纯 `CampaignPolicy.prepare/accept`，统一工作选择、上下文刷新、成功后的 review/曝光确认与空转处理；`prepare_handoff` 同时返回有界交接包和实际交付意图；`CampaignEvidence` 为同一档案前缀共享比较投影、计数、信号和交接核验读取。Driver 保留归档核验、进程、请求封存与原持久化顺序。完整 Interface 及恢复约定见[维护说明](campaign-policy.md)。

同时修复一个恢复边角：健康固定计划已经写入合法判断、但 CLI 随后失败时，旧 `measure` 不再被下一轮继承。合法判断仍接收，失败轮次不确认交付。schema-v2、JSONL 和命令行格式保持兼容；旧 in-flight 请求继续使用原封存内容。

新增 8 项 Policy Interface 检查，使用真实归档记录覆盖输入不变性、测量与上下文轮换独立、确认旧 checkpoint 后再处理本轮新合同、失败交付、计划关闭后恢复、旧 sealed 字段兼容和决议的时间/比较范围。另新增一项纯信号无文件读取且共用比较投影检查，以及一个实际执行配对程序、判断落盘后 CLI 中断、start/resume 回到 work 的集成场景。

最终固定版本完整回归 `/usr/bin/python3 -m unittest discover -s skills/competition-optimize/tests -p 'test_*.py' -q`：**497/497 通过，179.721 秒**。变更脚本和测试的 `py_compile`、Skill 的 `quick_validate` 与 `git diff --check` 通过。首次全套在协作测试文件定稿前启动，加载了旧夹具版本而出现两项失败；最终文件单独 8 项通过后，固定文件重跑得到上述完整结果。

## 工作调度和上下文轮换分开处理（2026-10-23）

修复固定复测计划绕过会话轮换的问题。公开 `measure-plan → start → resume` 反例中，3 run、6 slot 的真实执行配置 `session_checkpoints=2`，却连续 6 轮沿用同一会话，`session_turns=6`，首轮也没有 initial/fresh 标记。原因是计划分支提前命中，使同一 `elif` 链末尾的轮换和会话恢复判断无法执行。现在先选择本轮动作，再补充上下文轮换或恢复；已有执行、比较和策略重审的具体原因保持优先。计划、已完成槽位和下一步规则跨新上下文保留。

同时统一准备与消费阶段的动作优先级：真实失败始终进入 repair，健康时先继续已有固定计划，再处理比较缺口和候选停滞。失败 diagnostic 与普通候选停滞同时出现时，策略重审不再覆盖修复，也不提前消耗策略检查点；实测恢复健康后，该重审仍然到期。另一个真实执行回归先复现了“计划与停滞同时到期，每轮都被清除 session”的问题，修正后计划只在配置的轮次换上下文，完成判断后再进行策略重审。

新增 8 项受控 CLI 回归，覆盖跨 start/resume 的 6 槽位计划及最终判断、第 1/3/5/7 轮使用新会话、关闭周期轮换、丢失 session 后恢复、轮换时发生 429 后只统计成功检查点，以及归档已有/当轮新增失败 diagnostic 的调度。另保留连续没有执行产出时的新上下文请求：`session_checkpoints=0` 的 5 轮空转仍保持 repair，在第 1/3/5 轮使用新会话，且不伪造新执行或消耗策略/执行观察检查点。测试实际执行源码并核对归档槽位，没有新增默认轮次、候选或时间限制。验证范围是调度和上下文生命周期，不代表比赛提分或跨日运行证明。

最终完整回归 `/usr/bin/python3 -m unittest discover -s skills/competition-optimize/tests -p 'test_*.py' -q`：**487/487 通过，176.125 秒**；变更脚本和测试的 `py_compile`、`git diff --check` 通过。

## 无法完成的固定复测计划可以中止并继续优化（2026-10-23）

修复一个实际复现的长跑循环：固定源码在计划指定 seed 必然失败，另一个修改后的程序即使成功执行，也不能填入原实现的槽位；此前驱动会继续在旧计划的 `measure → repair` 之间切换。新增 `measure-stop --archive PATH --plan-id ID --reason TEXT --next-action TEXT`，以追加事件记录明确的中止原因和可执行后续方案。`measure-status` 保留未完成槽位、全部成功及失败尝试和 `stopped_unresolved` 状态；中止事件绑定固定协议及全部尝试的证据摘要，写入和后续交接均复核引用的源码/result 原字节。

中止后的计划不再调度，不能继续填槽、补写胜负结论或为同一冲突重建计划。交接的 `measurement_stop` 携带原因、下一步、尝试数、剩余槽位和比较条件；当前口径优先，否则只带最近历史线索。本轮新增且匹配当前 comparison 的 stop 才能更新 `next_action`，历史事件不会覆盖新 receipt。停止计划不清除最后一次执行失败，修复后的实现仍需独立实测才会恢复健康；首次观测排名不变，也没有新增自动重试次数上限。

新增 6 项归档回归和 3 项受控 CLI 回归。真实程序在 seed 13 抛出 `RuntimeError` 后，公开 start/resume 实际经历 `measure → measure → repair → repair → work`：先冻结计划、执行失败、中止旧计划，再实测新程序恢复优化。另覆盖 stop 已写但 invocation 中断后的恢复、跨口径 stop 不覆盖当前动作、无新事件不回放旧 stop、关闭后拒写及未进入 brief 的失败尝试字节被修改时拒绝交接。验证范围是计划生命周期和驱动恢复，不代表比赛分数提高或跨日运行可靠性。

完整回归命令 `/usr/bin/python3 -m unittest discover -s skills/competition-optimize/tests -p 'test_*.py' -q`：**479/479 通过，159.193 秒**；相关脚本与测试的 `py_compile`、Skill 的 `quick_validate` 和 `git diff --check` 通过。

## 复测结论在后续轮次保持正确范围（2026-10-23）

修复长期驱动的两个状态错误：无新增档案事件的轮次不再用 `records[-0:]` 重新找到历史 `measurement_decision`，因此不会覆盖 Agent 当轮 receipt 提供的 `next_action`；交接优先带出当前完整 comparison 的最近判断，只有没有当前口径判断时才回退到全局最近判断。交接在携带判断前重新核验配对结果和源码快照字节，即使配对卡片因有界检索未进入 `development_brief` 也会发现篡改。新增回归覆盖无事件续跑、跨口径判断选择、结果文件篡改和源码篡改。

仅本轮新增且与当前 comparison 一致的判断才可更新 `next_action`；跨口径判断保留作历史线索。独立只读构造验证了 A 计划结案而 B 已活跃时，B 的 receipt 后续动作不被 A 覆盖。完整回归 **470/470 通过，150.293 秒**，相关脚本 `py_compile` 与 `git diff --check` 通过。验证范围是续跑状态与证据交接，不代表新增比赛提分或跨日运行证据。

## 实测质量与资源取舍检索（2026-10-23）

此前即使 adapter 明确测得两个版本的候选运行成本，brief/交接仍主要保留 scalar best 与近期路线；一个较快但略低分的真实实现可能离开自动上下文。本轮参考 AI Telco Engineer 真实计时→前沿→下一次方案生成链，实现显式 resource_profile 和同协议质量/成本取舍视图。只比较完整口径相同的真实、有效、普通开发运行；端点的质量与成本来自同一观测，保留最快和最高质量两个源码版本，原 scalar best/晋级/停止规则不变。字段及端点规则属本地推导，[来源与边界](source-study-20261022.md#质量与实测资源的取舍进入下一次构造2026-10-23)分开说明。完整原始结果、前向和验证见[本轮报告](/home/lzh/competition-agent-validation/quality-cost-frontier-20261023/REPORT.md)。

固定 12 例 8×8 分配任务由 adapter 显式测量预热后的 solve-only 批次中位数。greedy 实测收益 3301、0.037767 毫秒；exhaustive 实测收益 3622、188.4939725 毫秒。公开 record→handoff 的 14,202 字节包同时显示两端，附真实源码/result 身份，scalar best 仍是 exhaustive。独立后继读包后先记录前瞻提案，实施 bitmask DP 并经未改 adapter 实测收益 **3622**、**0.954477 毫秒**，12 例逐例匹配穷举；120 个小矩阵另与独立穷举一致。这个固定本地 proxy 案例验证取舍线索进入真实构造及评测；不能归因于检索策略，也非华为正式分数或跨设备延迟。

专项新增 8 项回归，全套 **455/455 通过，138.590 秒**；quick_validate、py_compile 和 git diff --check 通过。没有安装或执行第三方框架、调用付费 provider、正式提交或推送；未设置默认运行配额。同实现首次实测 profile 只作确定性代表，不是重复测量降噪；缺 profile 或协议不一致时不能推断成本。[完整证据与命令](/home/lzh/competition-agent-validation/quality-cost-frontier-20261023/REPORT.md)保留结果与限制。

## 当前结论与历史经验轮转（2026-10-23）

借鉴 LoongFlow 的非最优候选实际进入 planner、RD-Agent 按当前轨迹与其他经验分槽消费的思路，修复 scoped_learning 始终取相关/最新两条导致较早当前结论长期不可见的问题。campaign 至多保留一条近期相关 head，其余位置按未成功交付优先、最久未交付其次轮转；仍最多两条。曝光按完整 comparison 和 candidate_id 持久化，只有完整报告交付且 receipt 成功才推进，失败、prepare、截断不消费；resume 保留顺序，修订新 head 重新进入候选，standalone 默认排序保持原行为。两槽政策与成功交付记账是本地推导，[来源调用链及迁移边界](source-study-20261022.md#当前经验与历史结论分别保留2026-10-23)区分其与上游机制。

固定区间调度任务实际执行五个程序后，旧检索重复显示 end-tie-late、profit-first，遗漏 density-first 的当前经验。受控 CLI 前两轮输出标志夹具错误已保留，修正后 resume：第 3 轮成功交付原两条，第 4 轮轮转至 density-first，失败轮次未消费曝光。独立 Agent 读取该实际交接包，前瞻提案引用 learning_from=[density-first]，实现兼容前缀动态规划并实际测得 **896→938（+42，4.6875%）**，10 例逐例无回退，335 个小实例与独立穷举相符。它验证取回经验进入实际构造，不证明轮转的因果提分、华为官方成绩或长期模型自主运行。

新增 12 项检索/受控 CLI 集成测试，全套 **447/447 通过，142.709 秒**；测试期间 47 个脚本与测试 hash 不变。quick_validate、py_compile、git diff --check 通过。原档案九条前缀和 31 个 raw/历史文件保持原字节，仅追加实际提案及后继，无 pending；最终交接包 40,834 字节，修订旧经验后仍完整交付。[完整报告、源码研究和原始结果](/home/lzh/competition-agent-validation/learning-rotation-20261023/REPORT.md)保留初期失败、恢复与证据边界。本轮未执行第三方 Agent、调用付费 provider、正式提交或推送，未增加默认搜索配额或停止条件。

## 单次交接的证据读取复用（2026-10-23）

借鉴 Aira Dojo 的任务文本显式传递、LLM Speedrunner 的结果索引消费，将 brief、trace、trial、恢复和条件经验核验中的摘要读取复用到单次操作。EvidenceReads 每次操作新建，完整核对路径及stat身份；目录每次重新枚举，内容消费者仍重读bytes。回归发现同尺寸连续写入可能保留mtime/ctime，已改为近期文件始终重读，无生产等待；仅复用稳定文件的摘要。[来源与迁移范围](source-study-20261022.md#单次交接中的证据读取复用2026-10-23)保留不照搬的长寿命缓存和可变summary问题。

真实历史交接的read_bytes调用 **65→10**，逻辑读取 **61,569→9,164字节**；brief、完整trace及43,849字节handoff与冻结旧版完全一致。额外路径/stat核对让该小文件样本 **2.866→3.665毫秒**，约慢0.8毫秒。共享recipe I/O放大夹具中，1 MiB为 **18.583→6.117毫秒（3.04×）**，16 MiB为 **250.442→14.776毫秒（16.95×）**，后者87→11次读取、453,040,651→16,786,380逻辑字节。夹具不代表新算法执行；这些是本机七次预热后计时的中位数，不是官方分数或整个campaign提速。

新增8项行为回归覆盖近期同stat篡改、同size改写/还原、rename/symlink、目录增删、跨操作新鲜性、共享输出与错误兼容。最终完整回归 **435/435通过，137.194秒**，测试期间45个脚本/测试hash不变；quick_validate、py_compile、git diff --check通过。原实际档案与21份历史protected文件hash保持不变。[完整报告、脚本和原始结果](/home/lzh/competition-agent-validation/evidence-read-reuse-20261023/REPORT.md)保留初期与最终数据的区别。未执行第三方Agent、调用付费provider、正式提交或推送。

## 条件经验跨窗口影响实际构造（2026-10-23）

从 ReEvo 的累计反思→mutation→评测，以及 ShinkaEvolve 的 outcome→推荐更新→后续生成→评测，迁移可选的条件经验修订与显式使用连接。`record --learning` 附在实际测得的 prospective 后继；同完整 comparison 的同 key 更新必须 `revises` 当前 head 并保留证据。`brief.scoped_learning` 交付当前结论，下一提案用 `learning_from` 说明依据，连接经 pending、实际 successor、trace 和有界 trial 包保留。证据身份不认证自然语言语义，不增加 provider、试验配额或停止规则。[使用方式](../skills/competition-optimize/references/iteration-trace.md#carry-conditional-learning-into-the-next-construction)与[源码研究](source-study-20261022.md#条件经验的修订与实际消费)给出边界。

用固定单资源带收益区间调度任务，实际执行 earliest-finish、profit-first、density-first、start-first 四个程序，总收益依次 693、896、894、704。前两种收益启发式的逐例互有胜负促成同 key 修订。重新启动公开 API 读取后，原始 trial_history 只显示 start-first 与 profit-first，而 density-first 的当前修订仍由 scoped_learning 返回；没有把最近窗口当作全部经验。

独立 Agent 仅接收任务、当前 skill、档案与其原始证据，先 fresh brief/trace 及源码检查，再构造带原下标回溯的兼容前缀动态规划。prospective 提案 `learning_from=["density-first"]` 解释该证据如何使其转向完整兼容集合；实际 adapter 收益 **938**，比旧最好 896 增加 **42（4.6875%）**，10 个开发例逐例无回退并达到独立穷举最优，另通过 126 个边界/随机例。实际结果再次显式修订旧结论。此例说明经验真的进入后续实现与测量，不证明自动框架对所有任务的因果收益或长期比赛成绩。

最终交接包 43,849 字节，小于 48 KiB；新 trial 的原学习报告和引用完整交付，trace 为 evaluated_valid，无 pending。原档案前缀、raw 输入和所有历史源码/result hash 保持不变。最终全套 **427/427 通过**，134.118 秒，测试期间 44 个脚本与测试文件 hash 不变；quick_validate、py_compile、git diff --check 通过。聚焦回归另覆盖 stale/foreign/confirmation/manual/failed/output-only 拒绝、旧报告独立证据核验、改字节及报告截断/篡改、相关优先与最多两项检索。[真实命令、程序、原始结果和证据](/home/lzh/competition-agent-validation/scoped-learning-20261023/REPORT.md)保存在隔离目录。没有执行第三方 Agent 仓库、安装依赖、调用付费 provider、正式提交或推送。

## 档案回放提速（2026-10-23）

借鉴 FunSearch、OpenEvolve 的增量注册/查询索引，将 read_records 已有的 candidate map 传入提案/后继验证，并维护此前 result digest 集合。保留逐事件校验顺序、仅接受先前有效事件的关系、旧异常类型与消息；不改磁盘格式、不增加持久缓存或数据库。每次读都重新解析当前字节，standalone validator 及旧非字符串摘要仍保留原行为。[来源与范围](source-study-20261022.md#长期档案单次回放复用索引)说明哪些机制来自源码、哪些由本地实现和测量证明。

对同一冻结输入各先预热一次、再读三次取中位数：512 组 proposal/successor 为 **0.0651→0.0311 秒（2.10×）**；2,048 组为 **0.8238→0.1525 秒（5.40×）**；8,192 组、16,385 个事件、36,986,630 字节为 **12.9927→0.7561 秒（17.18×）**。按先旧后新顺序运行、未隔离 CPU；独立 profiler 进程曾与大档案测量重叠，数字是本机观察值，不是无噪声端到端速度结论。剖析显示 2,048 组原本 4,096 次 candidate_index 重建，新版为零；它验证热点来源，不替代非剖析计时。

规模 fixture 从实际公开 API 的有效事件复制，使用固定宽度 parent/reference 与不同实现/结果身份；未新增算法执行或分数。三个样本的解析结果逐字段一致。两份真实历史档案也一致，真实独立构造档案的 brief、完整 trace 和 18,423 字节 handoff 完全相同，trial 仍完整交付。全部被引用的历史源码、结果和原档案 hash 保持不变。性能范围仅为解析及回放校验；record、brief 与其他历史处理仍有各自扫描。

新增六项行为测试覆盖旧/新 construction、pending/stopped、错误优先级、全部历史结果重用、旧摘要等价、跨读取新鲜性及 standalone 兼容。冻结旧源码的九场景差分全部一致。全套 **420/420 通过**，129.555 秒，测试期间 42 个脚本与测试文件 hash 不变；skill quick_validate、py_compile、git diff --check 通过。精确命令记录在[本轮证据](/home/lzh/competition-agent-validation/archive-replay-20261023/REPORT.md)。

## 独立构造与比较控制分开（2026-10-23）

借鉴 LLM4AD Next 的 I1 空父集执行链、Comind 的可选 codebase，新增 `construction_mode=independent` 和合法空 `code_targets`，保留父版作为验证过的比较控制。先前 API 不限制新代码的形式，但独立构造仍需伪填一个不继承的父文件目标；本轮修复这个声明与交接缺口。模式经 proposal、candidate、brief、trace 与 trial_history 保留，缺失/篡改独立模式不算完整交付；独立结果不会计作控制父版的 refinement 后继或关闭其机会。新源码/recipe 快照和真实新结果仍必要。默认 refinement、完整 comparison、确认隔离与停止规则保持原有含义。[源码研究](source-study-20261022.md#比较控制不等于源码继承)与[使用合同](../skills/competition-optimize/references/iteration-trace.md#declare-an-independent-construction)说明迁移边界。

真实旧/新 API 回放使用同一固定带收益区间调度任务和实际 earliest-finish 对照，开发总收益 693。旧快照拒绝独立空目标提案且档案字节不变；新实现成功归档为 pending，trace/brief/有界交接保持模式且可记成功交付，canonical 交接包 13,051 字节。原 baseline 前缀相同，未改分数来制造差异。

不继承主线推导和预期答案的独立 Agent，使用新 skill、公开档案、原始任务和固定 adapter，自主推导按结束时间排序、二分兼容前缀与最优收益递推，独立实现带重建的动态规划。一次完整开发评测 **693→938（+245，+35.35%）**，10 例全合法且全部改善。227 个合成实例通过独立穷举核对，10 个固定实例另用冲突图递归求解核验。公开 record/trace/brief 完成真实后继链；这些检查验证该任务实现，不证明模式造成收益、通用最优性或跨任务效果。[独立原始产物](/home/lzh/competition-agent-validation/fresh-construction-20261023/independent-use/)保留实际命令和结果。

全套 **414/414 通过**，131.233 秒；新增六项行为检查覆盖独立/旧版兼容、frontier、完整代码/recipe、跨契约和有界交接。审查发现的仅输出无 recipe、只有源码 hash 没有快照两处新独立后继接收缺口已修复，未改旧 refinement 接收范围。测试期间 33 个脚本/skill/reference 文件 hash 不变；skill quick_validate、py_compile、git diff --check 通过。[本轮完整记录](/home/lzh/competition-agent-validation/fresh-construction-20261023/REPORT.md)保留来源、回放和限制。模式不隐藏历史、不证明原创；本轮没有真实比赛成绩或长期运行的新证据。

## 实际实现复核指导后继（2026-10-23）

沿 Telco 的执行反馈链，新增可选 source-bound `implementation_review`，将 fidelity、实际机制、缺失组件和后继源码/recipe hash 与原 proposal 关联。`brief`、精确 `trace` 和匹配契约的 `trial_history` 带回下一轮；driver 提示先核对源码，再决定补齐、修复或换路线。跨契约卡不带原复核解释，截断/篡改 review 不计完整 trial 交付。旧档案不改字节；分数、valid、排名、停滞与停止条件独立。该字段是 Agent 的源码判断，不是语义证明。[来源研究](source-study-20261022.md#区分方案未实现与机制实测失败)和[输入合同](../skills/competition-optimize/references/iteration-trace.md#review-the-actual-implementation)保留具体边界。

真实回放使用改动前六脚本快照与当前实现，固定任务、adapter、数据、真实源码/result 完全相同。density 总利润 1075；后继 direct exchange 为 1097，虽然改善却缺少提案要求的逐构造回填与零删除分支。旧版只回传原预测与结果，新版明确保存 `fidelity=partial` 与缺失组件，真实成绩和最好版本不变；canonical 交接包 17,113 字节，review 完整可核验。两个真实候选只执行一次，新版重用已保存的真实结果，旧档案前缀保留。

不继承主线推导或预期答案的独立 Agent，使用新 skill、公开 brief/trace、原始任务及历史源码，自主选定并实施完整 seeded refill。前瞻 proposal、真实评测和 review 归档成功，缺失组件补全后 `fidelity=yes`，固定开发集 **1097→1097，10 例全平且合法**，因此保留较简单的父版。255 个合成正确性检查通过，其中两个相对父版改善；这些不替代固定开发集结果。一次完整 adapter 耗时 0.012839 秒，命令 wall 0.037465 秒。原 archive/raw 和引用历史源码/result 八文件 hash 未变，本地档案仅追加一项 proposal 与 candidate。[独立报告](/home/lzh/competition-agent-validation/next-mechanism-20261023/independent-use/REPORT.md)保存精确命令、源码与结果。

全套 **408/408 通过**，129.554 秒；skill quick_validate、py_compile 和 git diff --check 通过，测试期间 33 个脚本/skill/reference 的 hash 不变。[完整证据](/home/lzh/competition-agent-validation/next-mechanism-20261023/REPORT.md)保留旧/新回放、六个新增行为测试、独立使用和失败后处理记录。本轮证明复核信息可指导实际机制补全，没有开发集提分、官方成绩、跨任务因果效果或长期运行的新证明。

<a id="最新逐实例互补证据接入构造2026-10-23"></a>

## 逐实例互补证据接入构造（2026-10-23）

加入可选 case profile、普通候选互补检索与预测损失输出后，全套 **402/402 通过**，127.890 秒；skill quick_validate、变更脚本 py_compile 与 git diff --check 通过。测试期间七个相关脚本 hash 未变。[本轮证据](/home/lzh/competition-agent-validation/complementarity-study-20261023/)保留前后源码、来源正文、真实执行、检索对照及原始测试输出。来源机制和迁移边界见[源码研究](source-study-20261022.md#逐-case-胜例进入下一次构造)。

固定背包开发 adapter 的七个普通构造真实执行一次：density 总利润 1075，profit 为 1036，却在 case 2、3、8、9 胜过 density。旧 brief 已没有 profit；复用原七份执行结果建立新档案后，`complementary_evidence` 找回其 4 胜、3 负、3 平，并给出具体胜负值及源码/result 身份。第二槽 input 补充不同的 case 6 胜例；实际最好仍为 density 的 1075。检索对照没有新增程序执行，也没有把逐 case 最佳值当收益。实际交接包 **17,944 字节**。

完整 comparison 与 profile metric/direction/精确 case IDs 隔离；每个实现使用首个有效 profile，普通已执行开发快照才能供选亲。诊断、确认、失败、手工分数、仅输出与缺源码不成为互补父代；旧 metadata 即使原 result 含 profile 也不自动升级、不改字节。预测端显式 `--case-profile` 输出平方误差、绝对误差或同 epsilon 的 log loss，原聚合分数和配置不变；AUC 不支持该分解。检索窗口不限制实验，也不决定组合、晋升或停止。

一个不继承主线研究与预期答案的独立 Agent，仅获新 skill、原始任务/adapter/输入和真实历史，在隔离副本中完成一次前瞻提案、实现、执行与归档。它读取 profit/input 胜例和源码后，依据整数容量规模选择精确 capacity DP，而非只组合原贪心；proposal 以 density 为 parent，以 density/profit/input 为反馈来源。实际总利润 **1075→1127（+4.84%）**，相对 density 为 6 胜、4 平、0 负；127 个合成实例通过独立穷举核对。固定 adapter 计时 0.0120 秒，完整命令 wall 0.0363 秒，峰值 RSS 16 MiB。代码只读 stdin，不使用验证 ID 或历史胜者表；原 raw 和历史档案前缀保留。过程与结果见[独立工作区](/home/lzh/competition-agent-validation/complementarity-study-20261023/independent-use/work/)。这是一次真实策略转换的可用性验证，没有旧版 Agent 对照，也不证明官方提分、跨任务收益或长期自主能力。

## 诊断反馈接到实际后继（2026-10-23）

加入显式 diagnostic 角色后，全套 **392/392 通过**，130.216 秒；skill quick_validate、五个核心文件 py_compile 与 git diff --check 通过。测试期间五核心源码 hash 未变。[本轮证据摘要](/home/lzh/competition-agent-validation/search-continuation-20261022/summary.json)保留前后源码、固定来源正文、原始测试输出和独立使用产物。借鉴的职责分工见[源码研究](source-study-20261022.md#诊断试验指导构造而不参与候选排名)。

原公开 API 的五次真实基线/消融执行中，四项有意削弱的诊断也触发候选停滞。新行为区分诊断与候选：同样四个有效低分消融不制造候选停滞，源码/result/反馈进入封存上下文；真实失败诊断进入 repair，之后四个普通退步候选仍触发策略重审。诊断不能占据 best/runner_up、关闭普通 frontier 或贡献 comparison 单例；跨合同只交接核验身份/重验指针，确认仍被隔离。仅诊断新增不自动调用完成验证器，普通候选与显式 complete 保持原触发。prospective 诊断保留原预期和观测，可被普通后继引用，但诊断双方不产生候选 gain。

独立 Agent 只收到新版 skill、原始任务/基线及固定 adapter/data，自行完成两项消融和一项机制改进。隔离背包任务基线 **624**，去单件兜底 **624**，去密度排序 **436**；随后保留排序与兜底，增加可行获利交换/回填，实际后继 **627（+3）**。三项提案均在实施前通过公开 API 记录，最后四项真实 adapter 记录、原诊断反馈和后继完整归档，pending 为空。246 项额外合成检查中仍有 13 项非全局最优；极短单次耗时只作成本记录。

[独立使用报告](/home/lzh/competition-agent-validation/search-continuation-20261022/independent-use/work/report.md)、[精确命令](/home/lzh/competition-agent-validation/search-continuation-20261022/independent-use/work/commands.jsonl)和[实际轨迹](/home/lzh/competition-agent-validation/search-continuation-20261022/independent-use/work/trace-final.json)保留完整依据，raw 文件 hash 未变。本次确认了诊断可影响实际构造和真实产物，没有启动跨日 campaign 或外部 provider，也不将小任务开发利润当作华为官方提分。没有增加默认轮次/时间/候选额度或第三方运行依赖。

## 将已测机制带回下一次构造

新增 `trial_history` 后，仓库全套 **379/379 通过**，121.683 秒；skill quick_validate、五个核心文件 py_compile 与 git diff --check 通过。[本轮证据摘要](/home/lzh/competition-agent-validation/next-decision-study-20261022/summary.json)关联修复前已提交源码、原 API 反例、来源链、最终源码及原始测试输出。实际迁移和来源边界见[源码研究](source-study-20261022.md#已完成试验影响下一次构造)。

修复前的公开 API 反例显示：完成提案退出 pending 后，原 `change` 和 `expected_observation` 未进入自动包；更多后继又遮蔽整个旧 trial，最好父代仍在。精确 trace 一直能够恢复完整链。本轮没有将此检索缺口描述为已发生的模型自主重复，也没有增加相似机制黑名单。

新增 8 项 helper 行为检查与 3 项 driver 集成检查。使用公开 propose/record 和真实子进程，核对原假设、预期、实际结果及 source/result hash 进入封存 prompt；相关槽固定、历史槽跨 start/resume 轮转。连续 429、坏 receipt、prepare 和重建封存包不消费曝光；旧 state 和缺新字段的 in-flight 保持兼容。必要指针遭裁剪时原检索摘要不匹配，即使 64 项 omission 索引已经归并也不能记曝光；普通说明文字可缩短并按 ID 回取。失败/缺分数不产生虚构 gain，pending/stopped/手工分数/仅输出/缺快照不增加已测机制，确认不影响召回或计数。跨合同 outcome 的原反馈、预测状态和结构化分数被排除。

独立前向完成 **8 次受控 CLI、42 次真实背包程序执行**。旧 one-for-one 试验离开普通近期卡片后，仍从封存 `trial_history` 恢复原改动、预期及失败反馈；受控 CLI 检查原源码后实施 two-for-one，局部目标 30→50，下一轮历史槽继续推进。另一场景在 `thread.started` 后构造 429，再返回缺 evidence 的坏收据，前两次均不消费；从缺新字段的旧 state 恢复后，第三轮成功才记曝光。跨合同后继只交接核验身份与源码/result 指针，实际在当前合同重测后才得到 50；异口径 5000 与确认 50000 均未进入当前排名。

[前向报告](/home/lzh/competition-agent-validation/next-decision-study-20261022/forward/report.md)和[原始清单](/home/lzh/competition-agent-validation/next-decision-study-20261022/forward/evidence-manifest.json)保留实际命令、source/result 和 sealed request/context/prompt。五个核心源码前后 hash 与最终快照一致，最大 context **27,693 字节**，无残留自有进程；主线另逐字节核对 47 个封存文件与 42 个结果文件。第三场景的 fixture 因漏填复测 reuse 声明被正确拒绝，保留原字节补记后续跑，前两场景没有重跑。受控 CLI 验证数据流和恢复，不证明真实模型自主发现策略、官方提分或跨日可靠性。

## 评测口径缺少共同对照

新增共同基准诊断与 `measure` 恢复后，仓库全套 **368/368 通过**，115.906 秒；skill quick_validate、核心四文件 py_compile 与 git diff --check 通过。[本轮证据摘要](/home/lzh/competition-agent-validation/comparison-continuity-20261022/summary.json)保留修复前后源码、完整测试输出、独立前向和来源证据。实际迁移与未照搬的部分见[源码研究](source-study-20261022.md#评测口径缺少共同对照)。

修复前的公开 API 探针执行了 55 次真实程序，复现每项新代码更换配置后只剩自身基线：实现计数正常，执行健康正常，收益判断也只有一个观测。稳定 smoke 夹在 full 漂移中还能清零简单的全局连续计数。按原字节保存的[前置证据](/home/lzh/competition-agent-validation/comparison-continuity-20261022/before-study/copy-manifest.json)包含 120 个文件，保留原绝对路径；新的待补对照统计能识别该路径，正常两套固定口径各自建立对照后则不触发。

新增行为验证覆盖当前仍未配对的完整口径、首次 `(comparison, implementation)` 去重、旧代码跨合同真实补测、确认与失败隔离、repair 优先、旧状态升级与 start/resume 调整窗口。429 和不合法 receipt 不提交检查点；成功交接只提交 prepare 的观测数，本轮新观测仍供下一轮判断。独立审查还复现巨量环境元数据耗尽截断索引后，长 ID/真实长 result 路径误算完整的问题；新增 `retrieval_sha256` 在裁剪后按必要指针重算，完整 compact 卡可交接，截断或改动指针不可消费诊断。

独立前向完成 **11 次受控 CLI、40 次真实背包程序执行**。四个孤立 full 合同中穿插健康 smoke 后，第五轮 fresh `measure` 仍取回真实 full target；在同合同重测参考和候选后，孤立合同从四个减至三个，下一轮继续执行精确算法，真实局部目标 30→50。smoke 的 500 保留在自己的合同中。另一场景首次 `thread.started` 后主动构造 429，resume 再次 fresh 并保留相同证据；成功调用又产生四个新单例时，检查点先提交封存的 6，下一次仍触发重审并提交 11。正常双合同、alias 与确认分数 5000 不造成误触发或污染 full 排名。

四个核心文件在前向前后 hash 一致，[前向摘要](/home/lzh/competition-agent-validation/comparison-continuity-20261022/forward/summary.json)和[证据清单](/home/lzh/competition-agent-validation/comparison-continuity-20261022/forward/evidence-manifest.json)保留真实 source/result 与 sealed request/context/prompt。程序和 CLI 决策均受控，未请求真实模型或外部 provider；该背包数值不代表华为官方成绩，也不能证明模型自主策略质量或跨日可靠性。窗口 4 是工程触发默认值，补共同基准仍由 agent 在任务允许的 development adapter 下执行。

## 未完成提案恢复与失败重审

补充 pending 工作检索、精确提案回取和成功后提交 review 后，仓库全套 **353/353 通过**，100.262 秒；skill quick_validate、核心四文件 py_compile 与 git diff --check 通过。[本轮证据目录](/home/lzh/competition-agent-validation/pending-recovery-20261022/)保存全套输出、冻结源码与 hash，以及修复前的公开 API 反例副本。副本逐文件核对字节，保留原始绝对路径与原目录，未重写身份。源码依据与设计边界见[迁移记录](source-study-20261022.md#未完成提案接回真实执行)。

修复前，七项同口径 pending 中最老三项从实际自动包消失；缺分数的失败父代引用旧有效开发反馈的合法 repair 提案，也不能匹配任一上下文。另用真实程序失败种子触发 fresh repair 后，让 CLI 在 `thread.started` 后遇到 429，原驱动提前提交检查点，第二轮实际 resume 失败会话。策略 review 对照未复现跳过，现为统一提交语义一并改为成功后记账，不把它描述为同样已发生的故障。

新增集成用公共 propose 和真实父代程序，在两轮含 resume 中得到 pending 详情 `[p0,p1,p2,p3] → [p4,p5,p6,p0]`；当前口径全部七项 ID 保留。非零退出、无效 receipt、prepare 与重新物化原包都不提交 pending 曝光。execution 和 objective review 两个场景的第一次调用均在发出 session 后失败，第二轮仍 fresh 且保留原 review 原因，成功后才提交检查点。旧状态和旧 in-flight 缺新字段仍可消费；必要代码目标或引用卡的身份被裁剪时不记曝光，普通解释文本裁剪仍能带完整原证据指针。

独立前向完成 **7 次受控 CLI、11 次真实程序执行**，覆盖三条完整流程：七项积压提案跨 start/resume 轮转，按 ID 取回旧 p0 并真正改代码/运行，局部背包值 50→100，仅 p0 关闭、其余六项仍 pending；无分数的真实失败父代保留跨口径 repair 提案，后继经固定 adapter 重验恢复完整评分合同，异口径参考没有分数或原反馈，确认父代被 API 拒绝；一项有效和三项真实失败后，两轮均开启 fresh execution_stagnation，首轮受控 CLI 的 thread.started→429/exit1 不提交，公开 resume 后首次成功才提交 review 与曝光。曝光之后但执行之前，提案仍为 pending，验证没有把检索记账冒充工作完成。

该前向交接包为 **7,619–14,135 字节**；原 accepted archive 前缀、固定 adapter/数据与四个核心源码 hash 均保持一致，无残留自有进程。[前向报告](/home/lzh/competition-agent-validation/pending-recovery-20261022/forward/report.md)和[总证据摘要](/home/lzh/competition-agent-validation/pending-recovery-20261022/summary.json)保留命令、原始目标、程序/result 和核验记录。受控 CLI 只证明编排与证据传递，429 为主动构造且未请求外部 provider；背包数值不是官方成绩，也不能据此证明真实模型策略质量或跨日运行可靠性。

## 旧分支检索与成功交接轮转

新增 `review_frontier` 后，仓库全套 **332/332 通过**，94.636 秒；skill quick_validate、四个核心文件的 py_compile 与 git diff --check 通过。[本轮证据目录](/home/lzh/competition-agent-validation/branch-retrieval-20261022/)保留全套原始输出、最终源码快照及 hash。源码借鉴、实现选择与不移植的部分见[研究记录](source-study-20261022.md#旧分支与高分参考分开检索)。

新增覆盖对应三个实际遗漏：低分机会被高分路线截断挡住，同路线较早机会被最新一项覆盖，以及失败子代错误关闭父代。检索现从所有同口径真实开发实现选择机会，按首次有效分数代表去重，另外引用首次反馈声明；后于声明的真实可用且非 unresolved 子代才能推进机会。确认/其他口径、手工分数、仅输出和缺快照的实现不会制造机会，换名和幸运复测不增加代表或后继数量。

驱动集成使用真实执行的五个旧分支和独立最高分方案，在三轮成功交接及显式 resume 中得到 `[0,1] → [2,3] → [4,0]`，历史最好值保持 1000。非零退出和不合法 receipt 不记曝光，恢复后仍交接原机会；prepare 不改曝光，缺文件可按封存字节恢复，缺新增字段的旧状态可读取。机会、反馈或后继卡缺失/身份被截断时，不计相应曝光；普通反馈文本或 reuse 历史被标记截断仍可保留完整身份。曝光是成功传递证据的记账，不证明模型采纳或方案质量。

独立前向另用固定背包 adapter、真实程序、公开 start/resume 和读取实际封存包的受控 CLI，完成 **13 次 CLI、34 次候选程序执行**。三个低分旧机会即使不在高分路线列表中也能轮转；同实现一次刻意设置的高分复测为 100，代表仍取首次 50，独立历史最好值保持 99。失败、缺分数和显式 unresolved 子代保留父机会，真实有效的 supported 后继推进机会。退出码 7 与坏 receipt 不记曝光；实际 SIGKILL manager 后，resume 接管原 worker 和同一 request/context，只提交一次曝光。旧状态、确认/异口径隔离与所有引用卡的源码/result 字节身份也经独立核对。

该前向的交接包为 **13,991–17,737 字节**，均低于 48 KiB；最终四个核心 hash 与仓库及冻结快照一致，无残留自有进程。[完整报告](/home/lzh/competition-agent-validation/branch-retrieval-20261022/forward/report.md)保留命令、状态、原程序与结果。初次运行的并列曝光预期写错已在独立说明中记录，修正 fixture 后换目录重跑，没有改主代码或覆盖原字节。受控 CLI 只证明编排与证据行为，背包值不是华为官方成绩；一次本地进程崩溃也不能证明跨日或真实 provider 可靠性。

## 执行失败恢复与持久化增长

补充失败分流、恢复证据和紧凑 reuse 链接后，仓库全套 **315/315 通过**，91.353 秒；skill quick_validate、py_compile 和 git diff --check 通过。[证据摘要](/home/lzh/competition-agent-validation/execution-recovery-20261022/summary.json)保留最终源码 hash、全套输出和初次失败记录。新增覆盖包含跨失败口径的连续诊断、同结果去重、低分但有效结果结束失败串、真实 error 身份、确认隔离、旧状态恢复和旧/新磁盘格式混读。

独立前向用实际 skill、固定 adapter、真实背包程序和读取 prompt/context 的确定性 CLI，完成 **12 次 CLI、14 次程序执行、69 项行为断言**。三个真实失败跨 start/resume 保留，fresh repair 取回开发祖先后执行 DP，开发值 45→50；成功但缺分数的候选用同源码补测，随后恢复正常优化。高分和失败的确认记录均未指导下一轮。会话、usage 和已接受档案前缀保留，所有任务进程已清理。

独立边界补充构造 148,279 字节嵌套运行环境元数据，最终交接包为 **3,123 字节**，目标、参考父代、真实错误/phase、结果指针与 hash、实现指纹和 comparison hash 均保留。该反例对应初次单元检查发现的 448,050 字节超限，现已修复；原结果和档案不改。[前向完整报告](/home/lzh/competition-agent-validation/execution-recovery-20261022/forward/report.md)说明流程、范围与局限。以上证明执行恢复和证据传递，不证明模型自主发现策略、官方涨分或跨日稳定性；本轮没有新增后台崩溃注入结论。

持久化复算使用旧/新 writer 的真实 record API，各在两种记录形状写入 512 条，共 2,048 次记录调用，结果为：

| 记录形状 | 原档案 | 紧凑档案 |
| --- | ---: | ---: |
| 相同 artifacts，512 条 | 3,947,012 字节 | 1,145,616 字节 |
| 同 pipeline、不同输出，512 条 | 2,631,938 字节 | 1,262,472 字节 |

新档案在 64/128/256/512 条时随记录数近似线性增长；旧/新 brief 除档案路径外完全一致，旧前缀字节与身份保留。该复算是合成 adapter 元数据，未执行 solver，也未测量整个 campaign；单次 record 仍扫描历史并完整返回 reuse 数组。[完整存储报告](/home/lzh/competition-agent-validation/execution-recovery-20261022/archive-growth/report.md)保留唯一对照差异、源码快照、全部档案和输出。持久副本逐文件核对原字节，保留原始绝对路径；原目录仍在，不重写证据身份。

## 本轮搜索与上下文机制

新增机制后的定向验证 **69/69 通过**（41 项驱动行为、28 项搜索与交接，73.388 秒），仓库全套 **290/290 通过**（79.790 秒）。检索历史复制的后续优化，又对受影响的 archive、brief、实现身份、反馈链和 campaign_search 共 **105 项**复核通过（5.258 秒）。skill quick_validate 和 git diff --check 通过。

- 真实执行的十个不同源码持续退步，即使始终标为 promising 并更换路线名称，也只保留第一项历史最好结果，分别在第 6、10 轮转入策略重审。新会话直接收到第 1 项的代码/result 身份；重审之间需要新的有效实现窗口，campaign 持续到显式验证上限。
- 持续进步时按配置每 2 个成功检查点轮换，保留六项实现和全部 usage；默认第 9 次调用轮换不依赖 token usage，0 可关闭周期轮换。resume 可调整策略参数，不清零历史。
- 最大化/最小化、完整 comparison 的九类变化、低于历史最好值的回升、重复实现的幸运高分、仅输出、仅声明分数、失败后首个有效执行均有隔离检查。确认数据不会改变搜索信号和开发证据包；其他口径 pending 不进入当前任务列表。
- 跨路线 best、失败与未解决机会、父子方向正确的实测差值均保留；长 Unicode ID 和大段反馈仍受 48 KiB 限制，原档案不变。证据包被修改会阻塞接纳；准备后尚未建文件、manager 崩溃及成功后未消费等恢复路径保持原包与计数。

这些是受控程序和 CLI 替身对运行机制的验证，不是模型自主发现高分方法的对照。默认 4/8 两个阈值没有经过真实比赛寻优；实现及源码依据见[迁移记录](source-study-20261022.md#长期驱动器中的实际迁移)。

## 新机制的独立前向验证

独立探针 **6/6 场景通过**，共 39 次本地 CLI 替身调用、38 次真实背包候选程序执行。程序在真实容量约束实例上计分，替身读取实际 skill、prompt、context 和档案后按确定性策略选择实现。

轨迹为 71→67→59→74：连续退步后，重审取回较早的 seed-main（71），执行 DP 得到 74。已归档但尚未返回收据时杀 manager，没有重跑同一程序；complete 收据仍继续到探针声明的轮次上限。其余场景验证复测/无效/跨口径与确认隔离、长反馈、周期轮换后 resume 改策略、manager/worker 双杀、context 丢失后的原字节重建和 429 后继续。

逐次核对 request/context/prompt 身份、session、源码/result 和 usage；driver/runtime/search/archive 四文件 hash 在验证前后相同，全部正式和初期 fixture 进程已清理。最初探针的 proposal 输入格式与一个提示大小写断言曾被修正，原失败记录保留；没有因此修改 driver。

可查看[完整前向报告](/home/lzh/competition-agent-validation/search-memory-20261022/forward/report.md)及[本轮证据摘要](/home/lzh/competition-agent-validation/search-memory-20261022/summary.json)。原始记录另在 `/tmp/competition-strategy-forward-0oexaz9v`；持久副本保留原字节和绝对路径，不改写档案身份。这验证编排和证据接续，不能证明真实模型自主发现 DP、官方提分或跨日可靠性。

## 长期检索中的复测历史复制

自动交接每轮都使用 brief，因此同时去掉了为未展示候选复制复测历史的开销。只为最终展示卡保留它之前的同实现观测，返回内容不变。独立复核固定源码快照，仅移除这一条件恢复旧函数，用一份真实执行的 source/result 构造 2,000、4,000、8,000 条同实现记录；三档完整 canonical JSON 逐字一致。

8,000 条记录、两张展示卡的函数调用结果为：

| 对照 | 旧实现 | 当前实现 |
| --- | --- | --- |
| 三次调用的中位数 | 0.362 秒 | 0.160 秒 |
| tracemalloc 增量分配峰值 | 245.24 MiB | 0.54 MiB |

本 fixture 调用时间约为旧版的 1/2.26；旧复制量随同实现记录数呈平方增长，当前随记录和实际展示卡数增长。计时与分配不包含档案读取、输入构造和 JSON 序列化；内存 fixture 没有构造可选的已有 reused_from/reused_implementation_from 输入数组，因此不能当作整个档案或完整 campaign 的内存/提速比例。[完整复核报告](/home/lzh/competition-agent-validation/search-memory-20261022/brief-performance/report.md)含精确源码 hash、唯一 diff、输出 hash 和逐次计时；原始目录为 `/tmp/competition-brief-reuse-review-20261022-i21n85se`。

## 最初驱动版本的自动化回归

在 Linux、系统 Python 3 上执行：

~~~sh
/usr/bin/python3 -m unittest discover -s skills/competition-optimize/tests -p 'test_autonomous_campaign.py' -v
/usr/bin/python3 -m unittest discover -s skills/competition-optimize/tests -p 'test_*.py' -q
~~~

框架测试 **34/34 通过**，耗时 54.610 秒；仓库全套 **255/255 通过**，耗时 60.801 秒，全套包含这 34 项。测试使用隔离临时工作区及受控假 CLI，候选程序实际执行，再生成带源码身份的开发结果。

主要覆盖：

- 开放式 campaign 连续 12 次收到 complete 仍继续；blocked 声明、空下一步、重复测量均不能冒充任务完成或新实现。
- 连续四次临时失败后继续；认证失败与丢失会话分别阻塞和重建上下文。
- manager 崩溃接管原 worker；worker/CLI 被杀、PID 标记丢失、清空环境及关闭继承 FD 的子进程不会造成下一轮实验重叠。
- 后台 resume 不会因旧的 terminal 状态提前结束守护；manager 随后被杀仍能重启。
- 档案已确认前缀保持不变；损坏后缀先完整隔离，隔离写入中断后仍保存全部字节再对账。
- 同一工作区/档案不能同时由两个 campaign 写入；显式额度可以延长或移除，保留累计历史。
- 固定完成验证器的身份和结果必须匹配；manager 崩溃后接管同一次验证，立即停止及超时回收其子进程；manager 与验证器 worker 同时被杀后，这两种回收路径仍生效。

## 独立故障复验

独立审查使用新的临时工作区、受控 CLI 和自行设计的进程故障；未调用真实模型。初审发现并修复了旧实验子进程残留、后台 resume 误读旧状态、隔离副本写入中断后三处问题。

复验 **6/6 通过**：PTY 断线后继续、四次临时失败重试、manager 自动重启、stop/resume、立即停止、原 worker/CLI 双杀后的孤儿清理、启动竞态及隔离文件恢复均包含在组合场景中。隔离尾部保留 53/53 字节，SHA-256 与原始尾部一致；清理后核查的 41 个进程身份均无存活残留。

本机证据目录为 `/tmp/competition-forward-recheck-py2uv7dj`，含 `report.json`、`cleanup.json` 和可复跑探针。临时目录可能被系统清理，仓库内的回归用例保留了这些故障机制。

完成验证器另做了一组独立复验，**6/6 通过**，覆盖验证执行中/退出落盘后 manager 崩溃、立即停止、超时，以及 manager 与验证器 worker 双杀后的停止和超时。初测发现的恢复死锁与取消原因误报已修复。每个场景均只执行一次实验和一次验证，候选 hash 匹配，usage 无重复累加；忽略 TERM 的子进程也已回收。最终核查 42 个进程身份，无存活残留，两个驱动源码的 hash 在验证前后相同。证据目录为 `/tmp/competition-completion-recheck-p13eg2xi`，含报告、探针与清理记录。

## 真实 Codex CLI 检查点交接

通过已认证的 Codex CLI、默认 workspace-write 沙箱，在隔离合成任务中运行后台 campaign；任务为精确平方和计算，已有可信 baseline 和开发 adapter。验证显式设置 max-turns=2、每次调用 watchdog=600 秒。

| 调用 | 行为 | 实际结果 |
| --- | --- | --- |
| 第一轮 | 新建 session，实现闭式计算并评测归档 | exit 0、turn.completed、continue 收据，下一步指定批量 I/O |
| 第二轮 | 使用第一轮明确的 session ID 执行 exec resume，实现批量 I/O 并评测归档 | exit 0、turn.completed、continue 收据 |
| 驱动器 | 接纳两个不同源码实现及其结果，记录 usage | baseline 加两个后继；按显式两轮上限结束，无未对账调用 |

两个调用分别耗时约 84.48 秒和 63.46 秒。逐轮复核了请求 token、真实退出记录、原始输出 hash、terminal 事件及 receipt；档案工具复核了 baseline 和两个后继的源码/结果身份。两个 successor 均通过任务的七个正确性用例，未将单次计时作为稳健加速结论。

本机完整证据位于 `/home/lzh/competition-agent-validation/checkpoint-20261022`，摘要为该目录的 `verification-summary.json`。初次真实探针曾因一次调用持续迭代、不返回检查点而触发 watchdog；随后明确“一次归档实测步骤后返回，由外层继续”，才完成上述正常续接。真实 CLI 验证之后新增的完成验证器恢复使用受控故障用例覆盖。

## 比较证据投影与复测冲突（2026-10-23）

档案只读投影现在按完整比较条件和实现身份分组，同一次准备复用在目标进展、比较连续性及交接排名中。A 的首次/复测为 100/10/10、B 为 60/60/60 的回归用例验证：代表排名仍为 A，`repeat_conflict` 指向 A 的真实复测，完整身份卡交付后触发一次 `measure`；未成功的交接不消耗复核检查点。不同比较条件下的低分复测不产生冲突。此信号不替代题目预先固定的重复测量或最终确认规则。

在本机 `/usr/bin/python3` 下对内存中 8,000 条合成开发记录（6,000 个实现，2,000 次复测）各测 5 次中位数：构建一次投影供进展、连续性和冲突查询共用耗时 0.0892 秒；这三个查询各自重新构建投影耗时 0.2420 秒，约 2.71 倍差异。两条路径的结果完全一致。这只比较内存投影复用，不包括档案解析、证据文件校验、Agent 调用或比赛训练耗时，不能外推为整轮 campaign 的加速比。

## 配对复测计划（2026-10-23）

同契约复测逆转现在可先用 `measure-plan` 追加计划事件，固定比较条件、两份实现及冲突见证、run/seed 身份、重复次数和任务专属判断规则。后续 `record` 只接受在计划之后归档、元数据和代码身份都匹配的真实结果；失败/无效尝试不关闭槽位，同一成功槽位不能靠重复记录刷新。`measure-status` 显示每一对的原始成绩与剩余槽位；全部配对完成后，`measure-decide` 记录依据预定规则作出的判断及其结果证据哈希，仍不自动改动首次观测排名。

判断完成后，下一轮交接包的 `measurement_decision` 直接带出结论、预定规则和配对证据哈希，并用 `comparison_matches_active` 标明当前比较条件是否相同；条件变化时结论保留作历史线索，不直接用于新条件。受控 CLI 的下一轮请求及归档接口回归均检查了该交付路径，首次观测排名保持原规则。

受控测试覆盖计划先于归档结果、错 seed/次数/run/比较条件/实现被拒、档案重放发现协议被改写、无计划的成功回合不消耗冲突检查点、中断后计划交接、跨轮配对完成、跨比较条件保留计划、证据绑定的判断及判断后下一轮交接。`/usr/bin/python3` 的 468 项全套测试通过；`git diff --check` 和相关脚本的 `py_compile` 通过。这证明控制流程与归档校验，不证明实际运行发生在计划之后、task adapter 真正使用了声明的随机种子，也不证明比赛分数提高。

## 证据边界

已验证受控条件下的续跑和真实 CLI 的两次交接，尚未做跨日、主机重启或真实比赛长跑。后台 supervisor 能恢复 manager；主机或 supervisor 结束后需 resume，或由系统服务恢复。远程训练/调度任务需由 adapter 单独对账。

机制不会承诺比赛提分。它将持续推进和停止判断交给外层驱动，策略质量、评分契约、候选有效性及最终确认仍需任务本身的证据。
