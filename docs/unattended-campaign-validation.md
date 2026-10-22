# 长周期驱动验证（2026-10-22）

本轮验证的是持续执行、检查点交接、故障恢复、共同基准恢复、同口径收益信号、旧分支检索与跨上下文证据。实现入口为 [autonomous_campaign.py](../skills/competition-optimize/scripts/autonomous_campaign.py)，进程原语在 [campaign_runtime.py](../skills/competition-optimize/scripts/campaign_runtime.py)，搜索信号与交接包在 [campaign_search.py](../skills/competition-optimize/scripts/campaign_search.py)。启动及恢复命令见[使用说明](../skills/competition-optimize/references/unattended-campaign.md)。

## 最新：评测口径缺少共同对照

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

## 证据边界

已验证受控条件下的续跑和真实 CLI 的两次交接，尚未做跨日、主机重启或真实比赛长跑。后台 supervisor 能恢复 manager；主机或 supervisor 结束后需 resume，或由系统服务恢复。远程训练/调度任务需由 adapter 单独对账。

机制不会承诺比赛提分。它将持续推进和停止判断交给外层驱动，策略质量、评分契约、候选有效性及最终确认仍需任务本身的证据。
