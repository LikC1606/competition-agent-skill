# 五个方向改进：实施记录

2026-11-16，实施[改进方案](competition-improvement-plan-2026-11-16.md)的 A—C 阶段。工作在 `research-competition-skills-agents` 分支进行，原代码基线为 `fde9ea880d2de2602d64ca10e730212ceb785303`。

## 已实现的增量

新增标准库只读工具 [kaggle_sources.py](../skills/competition-optimize/scripts/kaggle_sources.py)，通过 `discover` 和 `read` 取得并保存研究来源。具体用法见[工具指南](../skills/competition-optimize/references/kaggle-sources.md)。

| 责任 | 实现行为 |
| --- | --- |
| 精确比赛与发现关系 | 解析比赛及其真实 forum ID，在该论坛搜索并显式翻页；榜单通过 team ID 关联 writeup；搜索结果保留无排名身份，已知其他比赛链接排除并报告 |
| 正文与评论 | 读取 topic/writeup，保存完整返回内容；保留 `is_partial` 占位及层级，分别统计已取得正文与未取得正文的节点；上游完整性保持未知 |
| 历史 notebook | 通过 kernel 范围的版本列表绑定版本号和 session ID，取指定源码；不能验证所求版本即失败，不静默回退 latest |
| 保存和复用 | 每次新请求生成快照，保留原始响应字节、请求/错误、可读正文、来源 JSON 和 hash；成功缓存可换显示范围而不重发请求 |
| 刷新与错误 | 刷新保留历史；失败/部分刷新不覆盖成功缓存；工具错误、坏 JSON 和不支持的必要响应结构不会冒充空结果；可用 `--direct` 为本次命令选择直连 |
| 连接恢复 | 对临时传输故障有限重试，逐次保存 HTTP 状态、未收完的原始字节与 hash；请求 gzip 减少传输量，可显式调整当前连接的 TCP MSS |
| 与当前研究衔接 | 原文定位、快照与适用条件进入任务 `research.md` 和现有 proposal `basis`，不增加候选或另一套提案字段 |

请求信息不记录授权头。读取器优先使用环境变量 `KAGGLE_API_TOKEN`，其次读取 `KAGGLE_CONFIG_DIR/access_token`；未设置目录时使用 `~/.kaggle/access_token`，没有 token 才匿名读取。工具只访问固定 Kaggle 主机，使用现有凭据，不执行下载的源码，不发起登录、参赛、训练或提交。

## 五个方向如何进入现有指南

- [资料研究](../skills/competition-optimize/references/competition-research.md)：按需读取入口、原始资料与解释的区别、来源支持的提案案例。
- [本地评测](../skills/competition-optimize/references/local-evaluation.md)：未来新实体与延迟标签的边界推导，评测修复后哪些产物失效、哪些可复用；公榜与本地冲突和确认污染的处置。
- [机制推导](../skills/competition-optimize/references/strategy-design.md)：JSSP 就绪状态带来的真实选择变化，与所有候选共享偏置被抵消的反例。
- [实际反馈链](../skills/competition-optimize/references/iteration-trace.md)：依据实际执行区分未实现、无效运行、有效退步与改善，接入既有 review、learning 和 `learning_from`。

案例明确是假设和手算，不包含虚构实测。现有表格训练、候选比较、条件经验、campaign 策略与恢复代码保持原有实现；主 skill 只增加按需入口，无需向每轮交接塞入全部工具说明。

## 当前在线接入边界

修复后，匿名直连已取得 topic `429948` 的主帖，共 1,494 个字符，读取状态为 `ok`。首次响应保留 963 个评论/回复节点，其中 3 个带正文、960 个是未取得正文的部分节点；本地 `--full` 命中同一缓存，范围标记保持不变。

用实际占位 ID `3438699` 指定 `--starting-comment-id` 后，该评论及其嵌套回复取得正文，返回正文数由 3 变为 5，未取得正文的节点由 960 变为 958。每次范围请求分别留存快照；这些数量不证明全部历史已读完，也没有建立自动遍历全部评论的规则。

最初的 HTTP 404 来自配置代理的路径：同一首页通过 `127.0.0.1:27900` 返回 134 字节的 404，直连返回真实首页与 HTTP 200，MCP `tools/list` 直连也成功。读取器新增 `--direct`，只改变当前命令的 opener，默认仍使用环境代理；请求记录保留实际连接模式。未修改全局代理设置。

直连还揭示了解析缺陷：Kaggle 返回 `is_partial=true` 的无正文评论占位，原代码会因其中一项缺正文而拒绝整帖。修复后保留主帖、可用评论及占位树，用 `body_available` 与覆盖统计表达缺口；未带部分标记却缺少必要正文的异常仍报错。这种成功返回的有限范围可以缓存，`status=ok` 不意味着全部节点的正文已取得。

真实接入材料保存在 `/data/lzh/workspace/outputs/competition-skill-implementation/20261116/`：

- [代理/直连对照](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/failure-diagnosis-network.json)。
- [修复后的真实读取结果](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/reader-direct-fixed-result.json)与[缓存展开](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/reader-direct-cache-result.json)。
- [指定评论展开结果](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/reader-direct-range-result.json)。
- 首轮失败原文及[历史接口核查笔记](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/kaggle-interface-notes.md)，保留作排查证据。

## 主要链路线上验证

用户要求补齐线上验证后，先以匿名、直连方式检查真实对象；收到登录凭据后，再验证 API token 认证及读取器自动加载。原始字节、请求记录和快照保存在上述输出目录的 `online-validation/` 下，[总汇总](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/online-validation/verification-summary.json)记录可复核结果。

| 能力 | 实际结果 |
| --- | --- |
| 精确比赛与范围搜索 | CMI 比赛 ID `102335`、forum ID `7865241`；查询 validation，两页分别 20/12 条，32 个 ID 无重叠，返回 URL 均属该赛；不可能词查询返回有效空对象 |
| 榜单关联 | 33 份 writeup 的 team ID、private rank、score、URL 与原始榜单逐一匹配；第一名 team `13896582`，分数 `0.886193` |
| 方案帖与评论 | 第一名 writeup `18466`、topic `603611`，取得 6,273 个字符正文；19 个评论节点中 6 个有正文，13 个为占位 |
| 评论范围 | Titanic topic `6240`，`--page-size 1` 返回 1 份正文和 42 个占位；`--page-size 64` 取得全部 43 个返回节点的正文 |
| notebook 版本 | `alexisbcook/titanic-tutorial`：latest v22，历史 v1；v1 的版本号和 URL 两种读取源码 hash 相同，且与 v22 不同，取得 nbformat 4 源码且未执行 |
| 错误版本 | 请求不存在的 v23、v1 搭配 latest session 均返回失败，只请求 view/list，未下载源码或回退 latest |
| 缓存展示 | 搜索结果从本地展示 5 条扩为 20 条，命中同一快照，无新增请求；原始 33 条榜单关联保持可见 |
| 无凭据错误 | 最初未配置凭据时，需认证的 MCP 榜单请求返回 `isError=true`、`Unauthenticated`，被识别为失败；保留为匿名负对照 |
| API token 认证 | Titanic 的 `get_competition_leaderboard` 成功；凭据保存为 `~/.kaggle/access_token`，权限 `0600`；清除进程内环境 token 后，读取器自动加载文件并取得 HTTP 200 |

本轮还修复了一个离线测试未发现的接入缺陷：`search_content` 实测忽略 `competitionIds` 过滤，返回跨比赛资料；当前发现入口改用已验证的 `GetCompetition.forumId → list_forum_topics`。新增 `--search-page` 对应真实论坛页码；`discover --page-size` 仅控制本地展示，完整返回仍保存到快照，扩大展示可复用缓存。缺少 forum ID 时报告该搜索不可用，保留已取得的榜单资料。

notebook v1 的 `version.id=11553429` 与 `run.id/scriptVersionId=20063545` 不同；v22 的 session ID 为 `99170538`。真实响应确认了这些身份的区别，详见[版本验证报告](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/online-validation/notebook/notebook-online-verification.md)。

本次登录通过 API token 完成。[登录验证](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/kaggle-login/login-verification.json)与[读取器自动加载验证](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/kaggle-login/reader-integration-verification.json)仅保留脱敏结果。此前 headless OAuth 的授权码交换因远端断开失败，没有保存 OAuth 凭据；API token 成功不代表该 OAuth 路径通过。

版本列表在 `pageSize=2` 时没有返回 `nextPageToken`，因此 token 翻页仍未能在线验证。评论案例取得全部返回节点的正文，也不据此建立所有帖子通用的历史穷尽或自动游标规则。

## 登录后的端到端复测

随后通过实际 CLI 再测比赛发现、第一名 writeup 及历史 notebook，均清除进程内 `KAGGLE_API_TOKEN` 和 `KAGGLE_CONFIG_DIR`，由读取器自动加载标准凭据文件。CMI 比赛元信息与第一名 writeup 正文成功返回；正文为 6,273 个字符，与此前匿名快照完全一致。其余请求发生网络超时：发现结果为 `error`，writeup 保留正文并标记评论读取 `partial`，notebook 为 `error`，没有把失败当作空结果或完整读取。

含后续评论连接对照在内，共记录 10 次读取请求，2 次 HTTP 200、8 次网络失败，未观察到认证拒绝。独立连接检查中，代理首页和 MCP 均返回 404；默认直连 TLS 握手超时，TLS 1.2 首页曾返回 200，但同一评论接口的默认 TLS 与 TLS 1.2 均超时，因此没有将 TLS 1.2 作为已验证修复写入工具。

此前认证榜单及匿名主要链路通过的证据保留；该次带凭据的完整组合验证受网络阻塞，未全部通过。[该次结果与逐项快照](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/online-validation/authenticated/verification-summary.json)单独记录。已核对该次响应字节与记录 hash；扫描 387 个项目及输出文件，未发现凭据内容进入这些文件。后续修复与通过结果见下一节。

## 网络修复与最终验收

用户要求解决失败后，对同一请求的多次实际结果进行核查：认证请求可以成功，但 TLS 握手与正文传输会间歇性超时；大榜单未压缩时为 1,887,719 字节。只增加重试或只降低 TCP MSS 均未稳定恢复完整流程。现已在读取器实现 gzip 请求/解码、有限传输重试、部分响应留存，以及只影响当前客户端连接的 `--tcp-mss` 选项。没有改变系统网络、代理选择器或 TLS 证书验证。

默认增加最多两次传输重试，等待 1 秒、2 秒；`--retries N` 可调整，`0` 可关闭。HTTP 状态错误、工具/JSON 错误及证书验证失败不自动重试。HTTP 200 后发生正文中断时，保留已收到的字节、HTTP 状态和 `response_complete=false`；耗尽重试仍返回失败，不写成功缓存。快照的响应文件和 hash 对应原始压缩字节，`decoded_bytes` 另记解压后的大小。

最终三条真实 CLI 均自动使用标准凭据文件，以 `--direct --tcp-mss 800 --timeout 20 --retries 2` 验收通过：

| 链路 | 最终结果 |
| --- | --- |
| 比赛发现 | CMI 的 33 个 private 榜单/writeup 关系与此前快照逐一相同；论坛查询返回 20 条，URL 均属该比赛；榜单完整响应从 1,887,719 字节压缩至 418,710 字节 |
| 方案帖及评论 | writeup `18466` 的 6,273 字符正文与此前一致；取得全部 19 个返回评论节点的正文，没有未加载占位；上游历史完整性仍不据此推定 |
| 指定历史 notebook | kernel `5660537` 的 v1、session `20063545`，源码 hash 与此前历史版本完全一致；nbformat 4，仅下载未执行 |

三条最终验收命令共 17 次请求尝试，其中 10 次收到完整响应、7 次传输失败后按既定次数重试恢复；这些数量不包含此前诊断。原始字节、完整与中断响应、版本、来源 hash 及失败历史均已核对。[最终验收汇总](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/network-repair/verification-summary.json)保存逐项结果；早先失败记录继续保留。扫描本次项目和输出中的 501 个文件，未发现凭据内容进入这些文件。

这些结果确认了当前可用的恢复路径；尚未定位到具体网络设备，不能将全部故障确定归因于 MTU。版本列表 token 翻页仍受此前服务响应限制，本轮没有扩大训练或竞赛提分实验。

## 验证与交付

新增行为测试使用固定响应和可丢弃的本地目录，禁止真实网络请求，并隔离真实凭据目录。修复后 36 项测试全部通过，覆盖来源归属、榜单关联、原始字节留存、正文与回复范围、缓存/失败刷新、工具错误、历史版本绑定、部分评论与嵌套占位、直连选择、论坛空结果与格式错误、搜索分页、本地展开复用缓存、凭据文件加载与环境优先级，以及 token 不进入快照。连接恢复测试覆盖重试恢复和耗尽、HTTP/证书错误不重试、不完整响应拒绝、部分字节留存、gzip 解码与原始 hash、TCP MSS 设置和 TLS 验证保留。

在 `skills/competition-optimize/` 下执行：

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover \
  -s tests -p test_kaggle_sources.py -v
```

凭据自动加载接入后，`quick_validate.py` 检查通过（`Skill is valid!`）。本地 Markdown 链接、章节锚点与空白检查结果见线上验证总汇总；线上验证覆盖范围与限制见上表及原始快照。

本轮没有安装全局 skill，没有启动上游 agent、比赛训练或提交，也没有承诺提分效果。非表格和远程训练 adapter 仍由下一场真实任务决定。

## 后续补充：实施前判断与反馈边界

用户确认以陌生比赛的自主完整流程作为成熟度目标，并要求补充评审发现的三个缺口。本次接入 `SKILL.md`、相应参考指南和 `campaign_prompt.py` 的每轮提示，复用现有 `basis`、任务笔记与后继反馈：

| 缺口 | 补充行为 |
| --- | --- |
| 保存了来源，但具体主张可能误引 | 回到保存版本的具体段落、cell 或函数；区分作者陈述、源码行为和 agent 推导。误引修正追加到现有记录，保留密封历史 |
| 有机制名称，但理论理由可能不成立 | 实施前化简决策规则，检查实际流水线与表达能力；说明正则化、预处理或优化造成的真实差异。线性和差特征不自动增加线性表达能力，也不自动意味着拟合结果相同 |
| 固定 OOF 被反复用于选择，却被当成独立证据 | 恢复并维护已用于选择的反馈边界；重切已用开发数据不能恢复独立性。无独立确认时保持开发范围的结论，按决策需要使用已有逐折/分组产物 |

详细指导分别位于[逐项来源依据](../skills/competition-optimize/references/competition-research.md#ground-decision-changing-claims)、[实施前等价性检查](../skills/competition-optimize/references/strategy-design.md#check-equivalence-before-execution)和[反馈使用边界](../skills/competition-optimize/references/local-evaluation.md#track-feedback-already-used-for-selection)。这些语义判断由 agent 执行；档案 hash 检查继续只证明相应字节与关联身份，不保证解释正确。不新增强制表单、自动语义判定器或默认追加训练。

软件侧通过 10 项现有检查：提示渲染 4 项、工作流快照 4 项、真实 driver 调用假 agent 的密封/恢复集成 2 项；另通过 skill 结构检查与本地链接/章节锚点检查。未新增仅匹配文案的测试。

另用 DeepSeek 对已知失败案例做隔离判断检查：输入为真实提案、固定 notebook 全文、父实现和字段说明，加上一份明确标记的构造交接建议；没有新增训练、读取确认数据或提交比赛。CLI 会话完成资料读取，但在 240 秒窗口内未交出产物；一次性非流式请求在约 100 秒后返回 HTTP 502；流式请求取得响应，但 3,500 个输出 token 均用于推理，以 `response.incomplete` 结束，没有最终答案。请求和返回的模型 alias 均为 `deepseek-flash`，未据此推断底层版本。这三次均未形成完整行为结果，不能记为通过，也不能据此声称跨比赛自主能力已验证。

[本次验证汇总](/data/lzh/workspace/outputs/competition-skill-implementation/20261116/autonomy-checks-20261116T130738Z/validation-summary.json)保留软件结果、各次未完成原因与输入身份。失败记录继续保留；本次交付仅将软件检查记为通过。新规则进入仓库主入口、参考指南和提示生成代码；已经密封的历史提案、回合 prompt 与运行快照不改写。运行器在后继检查点重新封存资源，已加载的 Python 模块随 manager 生命周期更新；本次没有重启正在运行的比赛 campaign。

## 后续实施：训练信息流、结论边界与停滞研究

用户要求推进下一步后，检查实际最佳实现发现：`EncodedLinearDesign`、`KernelNumericTreeDesign` 继承的默认 `fit_transform` 调用了 `fit().transform()`，绕过内部 `TargetEncoder.fit_transform` 的交叉拟合；`cv=5` 本身没有提供所声称的训练行隔离。sklearn [官方 API](https://scikit-learn.org/1.7/modules/generated/sklearn.preprocessing.TargetEncoder.html) 和[示例](https://scikit-learn.org/1.7/auto_examples/preprocessing/plot_target_encoder_cross_val.html)明确区分两条路径。

通过明确绑定的 `deepseek-flash` 完成两处封装修复；只在原 1,168 行、三折协议下训练一个新候选，复用历史父候选，未扫描参数或 seed。小型行为检查覆盖真实封装和下游 Pipeline：改变一个内部验证折的标签，该折训练编码不变；旧实现负对照会变化；训练编码与全量推理编码不同，未见类别回退到训练目标均值，序列化往返推理一致。

| 固定开发比较 | 父候选 | 修复版 |
| --- | --- | --- |
| pooled log-RMSE | 0.12479917634103173 | 0.12463355713294218 |
| 三折 log-RMSE | 0.125056 / 0.122076 / 0.127211 | 0.125143 / 0.121594 / 0.127100 |

修复版三个未修改树模型分支的 OOF 预测逐值一致；修复版三折合计拟合约 45.31 秒，模型约 227.59 MB。受影响分支并非各自都改善，不能把集成总收益等同于每个分支的收益。行重采样区间跨零，仅描述当前已拟合 OOF 的条件不确定性，不证明零效应，不校正反复开发选择，也不覆盖重新拟合变异。结果仍是开发证据，没有新的独立确认。

旧外层 OOF 不因训练行编码缺陷自动作废：外层验证标签仍未进入 fit；需要撤回的是“这些封装已经提供内部交叉编码”的实现结论。本次检查也不等于已将 `LassoCV` 等内部模型选择完整改造成逐分割重拟合预处理。历史源码、分数、提案、密封请求保持原样，后继记录补充这些边界。

通用 skill 同步补充三点：在[表格训练指南](../skills/competition-optimize/references/tabular-training.md#verify-supervised-preprocessing-information-flow)检查实际传给下游的训练特征；在[条件学习](../skills/competition-optimize/references/iteration-trace.md#carry-conditional-learning-into-the-next-construction)区分观测与因果推断；在[停滞恢复](../skills/competition-optimize/references/plateau-recovery.md)要求用能回答具体缺口的原始资料改变决策。单个失败不能证明整个方法族耗尽、误差不可约，库函数签名也不提供竞赛强度证据。这些指导接入主入口与后继回合提示。

软件检查通过既有的 10 项提示、快照及 driver 密封/恢复检查，以及 skill 结构、链接与空白检查。实际修复、负对照、训练与比较见[DeepSeek 修复报告](/data/lzh/workspace/outputs/competition-house-prices-test/continuous-20261116T122318Z/maintenance/encoding-repair-20261116T152502Z/REPORT.md)。修复产物由下一次受运行器管理的回合对账接纳，避免从维护进程外部追加档案；原有未完成 residual 提案保留部分文件，并显式说明停止或重建依据。

本次已重启同一个 DeepSeek campaign。第 24 回合实际核对密封源码、数据/折字节、OOF 分数与已存模型后接纳修复版，没有重新训练；更新了 current-best、进度与冻结交付，停止了旧 residual 提案，并在修复版上另建后继提案。隔离导出材料受维护请求影响误标为 `independent`，实际继承父源码，接纳回合以 `refinement` 和父 recipe 目标如实登记，并保留原报告及更正说明。

运行器接受第 24 回合后已进入第 25 回合；新冻结包与本地 skill 对应文件一致，实际提示包含新增规则。此前档案前缀和受保护任务/快照字节保持原样。[本轮软件与修复核验](/data/lzh/workspace/outputs/competition-house-prices-test/continuous-20261116T122318Z/maintenance/encoding-repair-20261116T152502Z/maintenance-validation.json)及[恢复接纳核验](/data/lzh/workspace/outputs/competition-house-prices-test/continuous-20261116T122318Z/maintenance/encoding-repair-20261116T152502Z/resume-verification.json)保留具体证据。尚未验证换到陌生比赛后的自主完整流程，也不能将本次小幅开发收益当作这些通用指导的整体效果。

## 后续实施：回执可靠性与低成本继续

第 26、29、31、32 回合进程与终止事件正常，最终消息包含前置说明和完整 JSON，但运行器只接受纯 JSON。现在调用适配器允许这种单个终止回执，保留严格五字段 schema；不修补残缺 JSON，不接受多对象或尾随材料，也不放宽进程、输出 hash、受保护文件与档案边界。原始消息和历史失败状态不改写，四例只读回放全部通过。

20 项软件测试通过：5 项回执行为、7 项 driver 集成、4 项提示和 4 项快照检查；另通过 skill 结构检查，空证据提示保持 3,856 字节。真实回执格式的集成用例只启动三回合并接纳三个实现，没有格式导致的重试。非零退出、无成功终止事件、错误 schema、档案/上下文篡改继续被拒绝。

现有指南和每轮提示还补充：诊断前检查已有 fold/member 预测与模型，复用相同依赖的产物，记录诊断、中断和重测成本；停止定期重复检查未变化交付。RBF 本已有非线性交互能力；误差相关性、邻居标签离散和一次重切分排序都不能推出方法穷尽或不存在可用信号。这些指导不能自动阻止任意代码重训，后续必须从实际行为检查效果。

维护取消了第 37 回合正在执行的三模型额外五折计划，保留四个已生成的 fold 模型，没有完整评分或新候选；205.20 秒后清理完成，没有存活子进程。原 campaign 随后通过受支持 resume 重启，第 38 回合已加载新冻结模块和指南、读取维护交接并成功接纳一次真实后继实验，随后进入第 39 回合。该自训练方案分数 0.126025 比原最佳 0.123039 差，如实归档而未晋升。194 个原受保护文件与原档案前缀保持原样。[本次维护报告](/data/lzh/workspace/outputs/competition-house-prices-test/continuous-20261116T122318Z/maintenance/autonomy-repair-20261116T173024Z/REPORT.md)链接回放、激活与接纳证据。

另启动 Spaceship Titanic 的独立 URL 输入验收，要求 DeepSeek 自行查资料、定评测、完成基线到机制比较和本地 CSV。只提供通用基础设施与低成本任务范围，不预先给算法或切分。官方数据接口实际要求先接受比赛规则，因此首次在训练前暂停，216.66 秒，没有候选或分数；用户回复“已接受，继续 Spaceship Titanic”后恢复并取得官方 train/test/sample。访问失败后的本地 benchmark/公开镜像搜索不能替代官方数据访问证据。[测试状态与失败证据](/data/lzh/workspace/outputs/competition-spaceship-titanic-test/url-only-20261116T174208Z/probe-status.json)保留原始拒绝信息。

第二场第 2 回合现已完成：DeepSeek 自主发现 train/test 乘客组零重叠，纠正最初的随机行五折，按组隔离重测四个候选。舱位位置方案 accuracy 0.810652，基线 0.806511，提升 0.4141 个百分点、多答对 36 / 8,693 条；4,277 行本地 CSV 通过 sample 顺序和布尔标签检查，未提交线上。独立只读核验复算全部 pooled 分数、档案/源码身份和组隔离覆盖均相符。它证明了单个陌生任务的主链路完成，不提供独立确认或整体成熟度结论。

本次也暴露实际不足：40 次拟合合计保存的模型流程时间 19.724 秒，其中 10 次仅因输出目录调整重复；代理回合时间 747.12 秒。正式提案在训练后登记，原 LOO 测试忽略了全局 prior 的自依赖，部分来源定位和成本表述不准确。现有参考指南补入拟合前的信息可用性检查、prior/实际编码输出检查，以及路径调整优先搬移并重新绑定已有产物。没有实现任意 Python 训练的自动缓存、统一完整计费或事前提案强制机制。[第二场独立审查](/data/lzh/workspace/outputs/competition-spaceship-titanic-test/url-only-20261116T174208Z/INDEPENDENT_REVIEW.md)保留完整证据边界与后续重点。

## 2026-11-17：把实测缺口落实到可执行接口

针对上述四个具体缺口，在隔离工作树中完成并通过全量软件检查：

- `accuracy` 已进入统一 scorer、batch、误差分析、不确定性比较和数值表格训练；它只接受硬 0/1 决策。表格适配器先平均折概率，再按封存的 `decision_threshold` 决策，并按官方 sample 的布尔格式交付。用 Spaceship Titanic 已保存的 OOF 预测复算，基线 `0.8065109858506845`、舱位方案 `0.8106522489359255`，与独立核验相符，未重新训练。
- 表格训练支持 `--archive ARCHIVE --proposal-id ID`。在导入候选前验证开放 proposal，保存 proposal 哈希和档案前缀；归档时核对输入、recipe、seal、执行日志和成本。训练后补 proposal 会被拒绝；没有该证据的历史结果仍可读，但不声称事前登记。
- 相同源码、数据、protocol、seed、推理元数据、依赖、适配器和评分器请求会复用已封存完成运行，返回 `new_fit_calls: 0`，复制目录共享原 `execution_id`。只改变输出目录不再造成重复拟合；显式 `--retry-reason` 才能产生同一实现的新测量。
- 每个 fold 在 `fit-events.jsonl` 记录开始、完成或失败。进程中断留下 `unresolved_fit_calls`，不填零成本；`cost --run` 按唯一执行 ID 汇总，归档自动挂载适配器级成本。它不假装覆盖任意候选内部嵌套拟合、代理推理时间或货币账单。
- protocol 可声明关系列及 `new_groups`/`known_groups`/`mixed` 推理前提，配合 `--inference-data` 在拟合前报告或拒绝验证/推理组重叠。它检查已声明边界，不能替代任务分析或发现遗漏的关系。

验证结果：训练适配器 25 项、预测工具 110 项、全量 skill 测试 667 项（33 项按环境跳过）均通过；skill 结构校验和 Python 编译也通过。运行中的 House Prices campaign 没有重启或切换评分身份；这些改动尚未激活到它的已加载进程。

## 2026-11-17：用户要求重启后的激活与兼容修复

用户随后明确要求重启。第 97 回合在 checkpoint 停止请求后仍未退出，维护通过受支持的即时停止取消本次调用；exit=-15，存活子进程为空。已产生的诊断和 proposal/stop 保留，运行器接纳其有效档案后缀；没有代替代理重新训练或修改比赛结果。

启动新 manager 时发现：17 条记录由旧常驻 reader 省略了结果文件中的 `training_execution` 元数据，新版完整字段比较因此误报。修复只按历史记录当时保存的可选字段投影比较；结果文件 hash、源码/recipe hash 和已记录字段继续严格检查，不回填事前提案或成本声明。23 项档案测试、9 项结果接口测试、25 项训练测试通过，317 条真实事件完整回放通过。

同一个 DeepSeek campaign 已恢复到第 98 回合，manager/supervisor/worker/agent 均存活。新冻结包 `ac1bdc5d66ebdcc89b9f18d5ac73d36ad4cbf587c7f03cd1ce296fbaf19ba08a` 的 64 个文件与已安装 skill 一致，原 387 个受保护文件及原档案前缀保持原样。第 98 回合已实际读取本次恢复交接；主评分契约、确认隔离、DeepSeek provider 和原资源限制保留。这里验证了重启与加载，尚未形成该回合的新比赛收益。[重启核验](/data/lzh/workspace/outputs/competition-house-prices-test/continuous-20261116T122318Z/maintenance/skill-restart-20261117T023921Z/restart-verification.json)保留进程、快照和完整性结果。

## 2026-11-17：修复重启暴露的恢复与状态反馈问题

上次重启还暴露两条恢复缺陷：首次初始化失败后，旧停止请求残留在 `blocked` 状态，一次显式恢复又立即停止；后台启动只等 supervisor 写心跳，可能提前返回旧 manager 的状态。针对这两条已发生的路径，本轮更新 `autonomous_campaign.py`、skill 主入口及无人值守指南：

- 显式恢复只消费该命令开始时已有的停止请求，且在任务与档案验证通过后才消费。请求带独立 ID，写入和消费共享短文件锁，保留启动期间新发出的停止请求；自动崩溃接管不消费待处理停止请求。
- supervisor 发布当前 manager 的 generation。后台启动核对该代 manager 的实际状态；五秒内未就绪时明确返回 `starting`，继续通过 `status` 查看同一次启动；初始化失败返回具体 `blocked` 原因及非零退出码。`starting` 期间也支持停止。
- skill 要求区分启动受理、当前 manager 已就绪和代理实际执行，避免根据旧状态再次启动。历史密封请求、档案和评分契约保持原样。

新增 7 项行为回归，覆盖前后台一次恢复、慢启动、启动失败、初始化期间停止、新停止请求保留及崩溃接管。全量套件 677 项中 644 项通过、33 项因可选表格依赖缺失跳过，用时约 203 秒。结构、修改文件语法、本地链接和 diff 空白检查均通过。第一次全量运行被测试清理逻辑终止：新失败心跳引用进程内测试 PID，旧清理误向自身发出 SIGTERM；已修复该测试夹具后重新完成全量验证，不把中断运行计为通过。

真实开发档案的 317 条事件完整回放通过，回放前后字节 hash 一致。[验证目录](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/recovery-verification)保存完整测试日志、检查结果及回放记录。本轮没有新增比赛训练或 provider 调用，也没有再次重启正在运行的 DeepSeek campaign；恢复代码已在仓库中验证，尚未加载到该常驻 manager。以上结论限于恢复行为和软件验证，不代表新的比赛提分结果。

## 2026-11-17：重评复用原训练证据

第 98 回合的实际产物暴露另一条缺口：训练结果记录了事前 proposal 和 3 次拟合，手工改用旧评分器后，归档结果却丢失 `training_execution`，成本只剩人工填写；第一次重评还因默认 ID 列名错误失败。原始训练回执及两个评分结果均保留，未修改历史结论。

新增 `tabular_training.py rescore`，从封存训练结果继承预测、标签、列名、metric 和 split；调用哈希匹配参考结果的历史评分器副本，单独保存新结果。它只需标准库，不导入候选代码、不反序列化模型、不重新拟合；模型文件只参与原 manifest 的字节校验。评分器身份、输入契约或开发阶段不匹配时拒绝，不能手工改 hash 伪装成可比较结果。新结果关联原训练 seal、回执及成本，归档时继续检查事前 proposal、原始文件、评分器和配置；无事前绑定的训练不能借重评补成已登记实验。skill 主入口和表格指南已加入使用路径。

隔离验证直接复用第 98 回合保存的 1,168 行 OOF，原评分器 `f59d9dad…` 得到 `0.1227142629304321`，与历史结果完全一致；新增拟合 0 次，原 3 次拟合及 proposal 身份均通过核验。最初误选了不匹配的历史副本，工具在写输出前明确拒绝，换成实际匹配的副本后完成。319 条真实档案回放通过，档案字节不变，未向比赛档案追加重复候选。[真实产物核验](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/ck98-rescore-checks.json)记录对比与成本。

新增 6 项行为测试，覆盖无候选导入、非默认列名、前置提案与成本保留、拒绝事后提案、错误评分器/切分、篡改原回执及分类概率指标/确认阶段边界。103 项相关测试通过（包含表格适配器 31 项）、skill 结构和 diff 检查通过；测试中的拟合仅使用可丢弃的小型合成数据。本轮没有新增比赛训练、provider 调用、提交或重启。实际比赛采用新入口的效果仍待后续回合观察，不据此声称提分。

用户随后要求使用新入口。维护在原 campaign 的维护目录实际调用 `rescore`，成功复用第 98 回合的预测，分数 `0.1227142629304321`、原 3 次拟合成本及事前 proposal 均经核验，新增拟合为 0。原候选没有重复归档。第 99 回合收到检查点停止请求后仍继续运行，因此通过受支持即时停止切换；exit=-15、无存活子进程，有效档案后缀已接纳。原 517 个受保护文件及档案前缀不变。

同一 `deepseek-flash` 任务已恢复到第 100 回合，64 个冻结文件与当前仓库一致；代理实际读取了新入口交接、执行了 `rescore --help`，并读取了已完成的真实重评结果。模型、资源限制和主评分身份未变。接入与可用性已有证据，下一次新候选是否按该入口完成归档仍需实际观察。[激活核验](/data/lzh/workspace/outputs/competition-house-prices-test/continuous-20261116T122318Z/maintenance/rescore-activation-20261117T031558Z/activation-verification.json)保存进程、快照、读取与完整性证据。

## 2026-11-17：冻结提交格式与目标逆变换

第 100 回合的真实交付暴露出自动化缺口：代理先猜错输出目录，再将 `Id,prediction` 误当作 `Id,SalePrice` 读取；工具输出仍是对数价格，只能另写脚本取指数和改列名。原 `delivery.json` 仅记录内部预测文件的 hash，未覆盖最终手工转换的 CSV。历史文件和代理选择结论保留，本轮仅修复通用交付流程。

`tabular_training.py freeze` 新增 `--submission-column` 和 `--inverse-transform identity|exp|expm1`，把提交列名和目标逆变换绑定在冻结 manifest 中；默认行为及无此字段的历史冻结产物继续使用原列名和尺度。`predict` 在原目标空间平均 fold 输出后执行一次逆变换，按正式 sample 的 ID 和顺序直接生成 `submission.csv`；拒绝列名/ID 不符、非有限输出和指数下溢。分类仅允许 identity，保留 accuracy 的布尔输出。评测尺度的 `predictions.csv` 单独保存，`confirm` 继续使用该文件评分。

返回值和 `delivery.json` 现在提供原始预测、最终提交各自的绝对路径和 hash、冻结映射及 sample hash；代理可直接使用返回路径，最终转换后的文件也进入交付回执。skill 主入口与表格指南增加对应入口、尺度选择依据和旧产物兼容说明。逆变换须依据实际模型输出语义声明，工具不根据预测范围猜测；未扩展至任意自定义变换或多列输出。

新增 8 项行为测试，覆盖 fold 平均后再还原、`exp`/`expm1`、原尺度确认评分、CLI 改列名、历史冻结兼容、篡改拒绝、分类边界、错误 sample 与溢出/下溢。表格适配器 39 项、档案集成 23 项全部通过，skill 结构、语法、本地引用和 diff 检查通过。

隔离验证复用已保存的 drop-forest fold 模型和正式 sample，直接生成 1,459 行 `Id,SalePrice`，新增训练 0 次。原始预测 hash 与第 100 回合完全一致；与原手工转换 CSV 的最大相对差异为 `2.22e-16`（浮点末位），最终文件 hash 与回执一致。37 个原训练、冻结和交付文件及原档案前缀保持原样。没有读取确认输入、提交比赛或替换当前交付选择，也没有重启 DeepSeek；新工具已通过真实保存模型的验证，不能据此宣称常驻代理已采用或比赛提分。[验证目录](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/submission-verification)保存测试、脚本、隔离产物及完整核验。

## 2026-11-17：隔离保存模型的候选代码，收紧误差归因

第 101 回合的成员诊断曾因未注册 `competition_candidate` 无法加载保存模型；第 102 回合同时读取父子候选时，又把该模块名绑定到后一个候选，导致父模型的自定义类找不到。若两份代码恰好存在同名类，直接反序列化还可能静默引用错误实现。这是通用读取问题，不应通过重新训练解决。

`tabular_training.py` 新增只读 Python 接口 `SavedTabularRun`，接收封存训练目录或冻结目录，验证 manifest 与记录环境，按 `fold_id` 读取模型。每次加载前重新核验源文件和所选模型字节；每个 reader 使用独立的候选代码命名空间，仅在反序列化时临时映射历史模块名，成功或失败后均恢复调用者原映射。既有 `predict`/`confirm` 已使用同一入口。接口用于单线程分析和预测，不承担训练、模型重存储、未封存依赖恢复或跨协议可比性判断。

技能入口和表格指南加入读取示例，要求按保存的原始特征顺序进入完整 pipeline；成员级检查若绕过前置步骤，应使用相应的已拟合变换，避免重做派生特征或因形状错误重复拟合。只需预测时继续直接复用已有 OOF/预测文件。

真实记录还反复将少数样本主导误差解释为标签噪声和不存在特征规则。局部评测指南因此补充：重复切分同一批观测能说明敏感性，不能独立证明标签错误、不可约误差或所有特征机制均无效；保留贡献分解，原因作为假设，单个规则失败只支持该规则的结论。本轮未改写历史记录或替代理调整比赛机制。

新增 7 项行为回归，覆盖同名类/函数/全局变量隔离、不同自定义类共存、读取不拟合或改写产物、打开后篡改检测、导入/反序列化失败后的模块恢复、环境与 fold 检查。46 项表格适配器测试全部通过，skill 结构、语法、相对链接及 diff 空白检查通过。

隔离验证先用真实保存模型复现原 `AttributeError`，再同时读取 drop-forest 与第 102 回合候选的各 3 个 fold，分别重放 1,168 行 OOF；两份输出均与各自原 OOF 逐字节一致，新增训练 0 次，35 个原文件及原档案前缀不变。首次核验因复现夹具清理整个模块表，移除了 sklearn 扩展模块别名而中断；已改为仅恢复候选别名后完成核验，首次中断不计为通过。本轮未读确认输入、改变当前选择或重启任务；接口已在仓库验证，常驻代理是否采用仍需后续轨迹证实。[验证目录](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/saved-model-verification)保存测试日志、复现脚本、原样重放 OOF 和核验结果。

## 2026-11-17：修复 JSON 代码块导致的虚假中断

第 104、105 回合均以 exit=0 和 `turn.completed` 正常结束，候选/诊断产物已保留，但模型将最终回执包在 Markdown 的 JSON 代码块中。旧解析器容许前置说明，却把闭合代码块当作 JSON 后的多余内容，两次报 `Extra data`，触发下一轮的恢复核对；第 105 回合明确将第 104 回合成果再次核对为已完成。问题是回执格式，不是比赛实验失败。

`codex_invocation.py` 现在接受一个完整终末 JSON 代码块（无语言标签或 `json`，反引号/波浪号），核对闭合字符和长度后解析；保留原始消息，继续验证相同的精确字段 schema。多个对象、残缺代码块、末尾解释文字以及进程失败、缺少成功终止事件或档案隔离仍不被接受。技能入口、回合提示和无人值守指南同时要求最终返回一个原始 JSON，减少 provider 包装差异。没有改写历史退出记录、回执或已接受的档案。

新增 3 项解析测试及 1 项两轮运行器集成测试；连同既有解析、提示及进程/终止/认证检查共 16 项通过。集成测试实际执行可丢弃的假 agent，确认两个回执均被接受、执行次数为 2、不中断或恢复、不重复执行，原始包装和退出记录的输出 hash 保持匹配。测试未调用模型服务。

只读重放第 103—105 回合原始记录，历史解析器对 104/105 重现原报错，新解析器均得到 `continue`；103 的普通 JSON 结果不变。durable token、原始输出 hash、usage 均保持一致，非零退出和档案隔离仍明确拒绝。结构、语法、相对链接和 diff 检查通过。新增训练和 provider 调用均为 0；本轮没有重启常驻 runner、回填历史成功状态或调整比赛选择，尚不能声称常驻进程已加载修复。[验证目录](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/receipt-fence-verification)保存相关测试、只读复现脚本和真实回执核验。

用户随后明确要求“加载”。维护请求检查点停止，第 114 回合正常完成（exit=0、无存活子进程），361 条档案事件完整回放；计划中的即时取消在调用前已失去必要性，命令被运行器拒绝，没有执行强制终止。保留回合成果后，从当前仓库启动新的 supervisor/manager generation，同一 `deepseek-flash` campaign 已进入第 115 回合，manager、supervisor、worker、agent 和 CLI `turn.started` 均已核验。

当前冻结包 `befcfb0e02568e5c82cddaee25c91731521270d13d6a1b37ee87d1cd9f543900` 的 64 个文件与仓库一致，包含回执、保存模型读取与提交逆变换修复；该包在旧 manager 的后续回合已可见，此次重启使常驻 Python 模块也从当前代码重新加载。原 861 个受保护文件以及停止前后的档案前缀不变，模型、评测锚点、资源与轮换配置未改。维护没有新增比赛训练、额外 provider 验证调用或替代理选择模型；新 API 的实际采用仍由后续轨迹判断。工作区加入工具交接，未注入算法指导。[加载核验](/data/lzh/workspace/outputs/competition-house-prices-test/continuous-20261116T122318Z/maintenance/skill-load-20261117T055345Z/activation-verification.json)保存新进程、源码包、配置、历史回执重放与完整性证据。

## 2026-11-17：自主数学推导、保持机制探索与约束结论范围

用户明确要求“自己合成数学”“不要过早收敛，要提出新机制”“不要让结论超过证据”。本轮将这三条落实到 skill 主入口、策略设计、停滞恢复、条件学习及自动回合提示，保留已有提案字段和所有历史实验，不新增填表 schema、固定实验配额或基于措辞的语义判定器。

新机制从变量、目标、约束和可用信息出发，在原 `basis/change/expected_observation` 中给出假设、可检查推导、实际行为变化和区分性预测/反例。补充平方损失下修正项的精确展开，以及预测平均的方差恒等式；明确恒等式、条件性期望结论、模型假设和经验估计的不同范围。平均不超过成员平均损失，不代表胜过某个固定成员；高误差群体不能直接推出应降低训练权重。公式、预先声明常数或组合已有模块本身不算机制创新。

停滞恢复允许根据任务数学结构提出完整新机制，不把现有集成、截断或表示当成任务约束。低成本原型需要可证伪的机制依据，不要求先保证超过旧分折噪声带；探索、投入优先级与最终采用分别判断。一个实现失败不能封闭整个方法族，也不能因为某个残差模型失败就断言必须获得外部新数据。实际用户/资源边界继续适用，未授权参数或 seed 搜索的约束保留。

条件学习和旧回执都需核对实际实现、父模型、输入/评测与接入方式，再携带结论进入后续选择。组件比较存在其他变化时不作单因素归因；离散设置失败不证明连续局部最优；置信区间跨零不证明零效应；低预测性不证明信号不存在。按既有字段保留观察、条件、未证解释和下一步，把缺乏支持的概括收窄到受测实现；不改写封存历史，不生成方法黑名单。

4 项回合提示、4 项冻结工作流及 95 项假 agent 驱动集成测试全部通过，共 103 项；保持原空提示 4 KB 检查上限。数学示例通过 135 个精确分数展开/改善条件案例、9 个预测平均恒等式案例，并给出有限权重点不能证明局部最优、平均界不能界定固定最佳成员的反例。隔离封装核对 64 个文件，使用真实第 117 回合上下文渲染新提示，核对 54 条相对文件引用；skill 结构、语法及 diff 检查通过。新增比赛训练和额外 provider 调用均为 0；这些检查不证明数学创新能力或比赛提分。

只读运行核验显示第 118 回合已自动采用包 `3ae39eaa3b58a629fd70f7b47f7c7cc647a69431af3c3713bcd9316599f3935c`，与验证版本一致。常驻 manager 的回合提示函数仍为启动时加载版本，因此不能宣称新提示模块已热重载；新 `SKILL.md` 与参考文档已进入该回合指令包。本轮没有重启、取消在途实验或替代理选择具体比赛算法。指令包采用、代理实际使用推导、有效机制产生与泛化收益分别验收，后续行为尚待轨迹验证。

[验证目录](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/mathematical-reasoning-063436Z)保存原文件副本、本次增量 diff、测试日志、精确算术核验、隔离封装及运行观察。

## 2026-11-17：按当前问题主动使用 Codex 工具

用户要求尽量利用好 Codex 的工具能力。本轮增加 `references/codex-tools.md`，由 skill 主入口与资料研究指南直接路由；按当前缺少的证据选择原始资料检索/浏览、代码定位与补丁、精确算术或可用符号计算、已有模型和预测分析、图像查看、进程会话跟踪、独立工具并行及受授权的独立子任务。工具动作需对应问题并读取实际返回，再决定依赖步骤；输出截断、启动警告、工具缺失、请求失败和有效负实验分别解释。

后台当前是第三方 DeepSeek 驱动的 Codex CLI。父会话、CLI feature flag 和模型别名都不能证明某个后台调用具有浏览器、MCP 或子 agent 能力；按实际曝光的工具和返回判断。优先原生能力或现有 reader/SDK，失败时排查具体访问路径并选择已授权替代。模型与 provider 要求适用于子任务；不能确认路由时采用工具级并行。不会因一个访问失败而封闭研究方向，也不把获取工具解释为新增外部写权限。

独立搜索、读取、下载和无共享副作用的检查可以并行；依赖编辑、状态写入、不确定写入后的重试和受资源影响的正式计时保持顺序。代数/反例和保存产物分析优先使用现有环境，不为每个问题新增训练、工具框架或依赖。能力发现结果在环境适用期间复用，不要求每轮列全量工具、固定调用数量或额外资料配额。工具价值按获得证据、消除不确定性或节约执行成本衡量。

此次只修改 skill 文档和资料研究路由，没有改动可执行脚本、provider、模型、权限或正在执行的封存请求。4 项回合提示与 4 项冻结工作流测试通过；新参考文档进入 65 文件的隔离指令包，44 条相对文件引用、skill 结构和 diff 检查通过。维护新增比赛拟合和额外模型验证调用均为 0。

核验时真实任务仍在第 119 回合，使用此前数学推导更新包；新文档将由既有运行器在后续新检查点自动封装，旧回合请求保持原样，无须为此文档更新重启常驻模块。此处验收的是文档路由和封装，不代表后台已使用全部工具，也不证明研究质量或分数提升。[验证目录](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/codex-tool-use-070035Z)保留本次增量、环境观察、测试日志和指令包核验。

用户随后明确补充：能调用工具的地方，不要自己写。主入口与工具指南因此收紧为现成工具、仓库入口、CLI/SDK 和库接口覆盖的操作直接调用；用法不明先读 schema/help，调用失败先定位问题，不把失败自动解释为需要重写。仅在现有接口未覆盖的任务机制或最小集成处编写代码，并在原提案/笔记说明具体缺口。删除了“现成工具或小脚本”并列的表述，避免把自写脚本当作同等默认选项；保留自主算法开发及底层库复用。这次为文档规则补充，不修改可执行流程或在途请求，由后续检查点自动封装。

### 2026-11-17：移除已确认的重复实现

用户要求解决组件审查发现的重复后，将通用 RMSE、MAE、accuracy 和 AUC 计算改为调用 sklearn；log loss 使用 SciPy 稳定函数，并在汇总、逐行报告和误差分析中共用实现，以保留原显式 epsilon 语义。删除 bootstrap 中的第二套指标公式，保留成对/整组采样、缺失类别和工作量约束。评分、重评分及归档核验共用静态评测器身份函数；新版身份包含数值库版本，旧源码身份保持可读，归档读取不执行 scorer 或导入数值包。

技能入口与工具指南新增已有数值操作的直接调用表；保存模型与管线特征使用 `SavedTabularRun` 和 sklearn Pipeline 接口，成本由归档 `--result` 自动读取、由现有 `cost --run` 汇总。CLI 帮助和成本冲突反馈明确纠正手拼字段的调用。复用既有数值依赖清单，未新增框架；README 与评分/重评分指南同步说明依赖变化。历史脚本、封存结果和在途请求不回写。

两批 169+54=223 项测试通过；真实开发 OOF 经旧评测器在无 sklearn 的系统 Python 中零训练复算成功，新归档核验器也能在无数值包环境核验其成本。skill 校验、差异检查及隔离封装通过。运行状态回读显示 DeepSeek 第 123 轮已引用新版包 `fb36f4bf4b56b78d882edd3f96837feba947a72d77e07631eda6b2e0b5d39c29`；这证明请求采用新版，不等同于新行为验收或比赛收益。未重启 campaign。[变更与验证报告](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/deduplicate-mZM6AngC/REPORT.md)保留范围、初次失败、最终测试和兼容证据。

### 2026-11-17：修复后续审查确认的四项问题

共享指标入口支持列表、元组和一维 NumPy 数组，统一拒绝空输入、形状/长度错误及非有限数值。新增共享 `prepare_metric`，在 bootstrap 前缓存行损失、正确性和 AUC 分组，普通评分继续使用同一实现；回归每次抽样独立缩放，AUC 使用库的 ROC 积分。配对/整组采样、随机序列、缺类别记录和工作量约束保留，估计器身份补入实际参与计算的核心模块。数值库延迟导入，标准库档案读取不受影响。

新建和恢复的 Codex 命令通过原生环境配置启用 Bash `pipefail`，真实子进程测试确认失败生产者不会被 `head` 的成功状态掩盖，正常输出中的 Traceback 字样也不会被误判。主入口、每轮提示和参考文档明确调用现有保存模型读取接口，父模型与候选模型各自使用保存的上游变换；日志截断优先使用工具输出限制或保存日志。没有新增执行器、模型加载器或第二套评分器。

337 项相关测试通过，另在最终测试修改后复验 9 项调用测试；skill 结构与 diff 检查通过。1000 行、100 次抽样、3 次计时的小规模基准中，五项指标的逐行/整组 bootstrap 比修复前快 1.79–9.24 倍，最大数值差异为 `3.33e-16`；不代表训练提速或所有规模下的收益。现有 benchmark 补入明确维度、硬分类 accuracy 输入、数值容差和参考版本自己的 scorer，避免比较被当前依赖混用。

ck129 诊断在独立目录零拟合重放，加载 6 个模型，父模型和候选模型预测均与各自保存的开发 OOF 完全一致，历史诊断最大差异约 `2.78e-17`。没有发现此次分数受读取风险影响的证据，历史脚本、结果与归档保持原样。真实旧版重评分及成本在 `python -S` 下再次核验成功，无数值模块加载。

第 125 回合正常结束后，通过既有 stop/resume 恢复同一 campaign；第 126 回合使用 `deepseek-flash`，预算、数据边界及其他设置不变，实际封存请求包含新 pipefail 配置及模型读取提示。真实请求包与隔离验证包同为 `3f64cc6d7cfbc68017eaa65a9ccaed6d675d6879b6b9891594b1eaf9cbad6118`。此处证明实现与请求采用，不证明后续全面遵循或比赛收益。[完整报告与证据](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/fix-observed-kru_ds2g/REPORT.md)记录测试、性能、重放与激活核验。

### 2026-11-17：研究状态、证据数量与单回合交付

Kaggle 来源读取保留计数对应的实体、单位、总体范围及原始响应位置，避免把公榜条目数误当训练行数。普通回执可携带当前研究问题与独立解释修正；同合同、同 key 的撤回替换当前解释并保留历史回执指针。新回合使用随指令包冻结的 receipt schema，旧 schema、请求和记录保持原样。这些记录属于 agent interpretation，不增加已执行实现数，也不证明科学判断正确。

研究回合改为以完整 `next_action` 开头，宽问题留作背景；移除普通比赛初始化、立即实现及无关档案行动。单回合交付后由 driver 继续 campaign，失败恢复保留当前合同上的未决行动。没有新增默认回合、候选、训练配额或时限。行动和旧回执中的关键前提需要回到原始证据核对；现有 watchdog 只负责中断，不能强制生成有效回执。

最终全量 728 项工程测试通过、0 跳过，包含安装 Clang 后补齐的真实 AST 检查；skill 结构与 diff 检查通过。固定版本、全新隔离目录、相同合成原始材料的 `deepseek-flash` 回合在 106.51 秒交付有效回执，宽问题保持 open，没有新增比赛训练或 Kaggle 提交。300 秒与一回合限制仅用于隔离验收。

行为验收仍为部分通过：模型继续沿用原始记录未确认的“联合干预”说法，没有对此前提返回修正或撤回；还曾将临时回执写到工作区外。维护者核对该临时文件与最终回执一致后保存副本并清理，原始观测、快照及导入的历史回执未变。有效回执和工程测试不能替代推理正确性或写入范围验收，一次小样例也不能证明长期稳定性或比赛收益。

第 153 回合自然完成后，通过既有 stop/resume 在第 154 回合加载最终包 `771b990b432eef0691130d3efd249ea182ea48b5d942bb8c36bbd5692767495f`，与隔离验收版本一致。模型仍为 `deepseek-flash`，原配置、旧受保护文件身份及 accepted archive 前缀保持，未投递具体比赛研究指导。[本轮报告与分项证据](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/research-turn-scope-m41nuise/REPORT.md)保存原超时、初步与最终行为结果、源码增量及激活核验。


### 2026-11-17：复用原生会话分叉补交回执

第 155 回合正常退出却只返回“正在整理回执”，触发后续重复恢复。现对这种有成功终止事件、有保存会话且档案完整的漏交路径，在原检查点内执行一次原生 `codex exec fork`，沿用冻结 schema 和原模型，只交付已建立的观察、限制与下一步。实际 DeepSeek wrapper 在该步骤保留原生输出 schema；普通工具回合保持既有兼容路径。

交付步骤复用已有 worker、锁、截止时间、取消和崩溃接管。原始输出与补交分别保存；档案变化拒收，进程失败不能靠补交变成功，失败不递归补交。用量各计一次，工作仍从原会话继续。普通工作和策略复盘也改为开头传递完整 next_action，在一个检查点后交回结果。

737 项全量测试及最终 24 项定向检查通过、0 跳过（覆盖最终 738 个不同测试）。实际 DeepSeek 入口在隔离构造漏交场景中 6.079 秒交付有效回执，0 工具执行、0 训练、0 Kaggle 操作；这不证明长期失败率或比赛收益。第 161 回合自然结束后重载，第 162 回合已采用最终包，原配置与历史证据身份保留。[修复与验收报告](/data/lzh/workspace/outputs/competition-skill-implementation/20261117/receipt-delivery-u89nuqcm/REPORT.md)。
