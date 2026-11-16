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
