# Campaign 档案接收

2026-11-10 更新：Driver 通过 [`TurnLifecycle`](../skills/competition-optimize/scripts/turn_lifecycle.py) 统一安排 prepare/accept 的顺序，通过 `CodexInvocation` 解释 CLI 结果；`CampaignArchive` 仍独立接收合法追加，不依赖 receipt 成功。档案与 schema 兼容规则不变，详见 [本轮验证](refactor-implementation-2026-11-10.md)。

[campaign_archive.py](../skills/competition-optimize/scripts/campaign_archive.py)
将 Driver 对已确认前缀的读取、文件核验和轮末接收集中为 `CampaignArchive`。
调用方继续持有现有资源锁，并先核验 worker 退出、token 和输出摘要。

## Interface

`verified(expected=None)` 在新建任务、无在途轮次的恢复和完成核验时使用。
它回放完整档案，核验所有 candidate 的 result、artifact 和已记录 metadata，
返回 `ArchiveHead(snapshot, evidence)`。指定 `expected` 时整个文件必须匹配。

`verified_prefix(expected)` 用于有在途请求时核对显式主评测锚点。只回放并核验已确认
前缀及其 candidate 文件，允许未接收的尾部继续追加；该尾部仍由 `receive` 处理。
新锚点必须来自已确认记录，不改变或重新生成原封存请求。

`confirmed(expected)` 是准备交接包的只读作用域。进入和正常退出时检查完整档案
仍等于原快照，作用域内返回 `CampaignEvidence`，只回放记录及其历史关系。
handoff 仍按需核验引用的文件。作用域内只构造复制的状态、计划和材料；退出成功
后 Driver 才保存 turn intent。这不是文件事务，也不提供回滚。

`receive(before, token=..., directory=...)` 在本轮 worker 退出后使用。
它验证封存前缀、回放历史，只核验新增 candidate 的文件，返回 `ReceivedArchive`：
`snapshot`、`evidence`、`appended_events`、`delta`、`quarantined` 和可选的
`quarantine_event`。没有新事件时 `appended_events` 为空。

返回的 evidence 借用 records，调用方不修改这些记录。module 不跨操作缓存文件
核验结果，不接收 receipt，不修改 campaign state，也不写 campaign events。

## 坏尾部与恢复

已确认前缀消失、截短、内容变化或历史关系无效时，报错并保留档案。
未确认尾部任何位置无效时，整个尾部一起隔离；其中的合法子前缀也不接收。
先完整保存原始尾部并核对摘要，再写 repair journal，最后截断并 fsync 原档案。

恢复沿用旧 sealed turn 的 `archive_before`、`token` 和原 journal 格式：

- journal 尚未写入、隔离副本不完整时，先重新保全完整尾部。
- journal 已写但未截断时，核对 token 和隔离证据后继续处理尾部。
- 已截断而 campaign state 尚未保存时，再次接收仍返回 `quarantined=True`。
- journal 或隔离证据损坏时直接报错，不继续截断。

合法追加即使来自失败的 CLI 调用也可进入证据。Driver 随后独立解析 receipt，
让 Policy 决定是否确认 review 和曝光。隔离事件由 Driver 写入，usage、outcome
event、完成核验和最终 state 保存继续沿用原顺序。

## 共享回放与验证

[candidate_archive.parse_records(raw, source)](../skills/competition-optimize/scripts/candidate_archive.py)
是纯字节回放入口。`read_records(path)` 和已确认前缀共用同一实现，不再为了回放
前缀创建临时文件。回放保留现有索引、物理行号、错误优先级和旧记录接受范围，
不会访问源码或结果文件。CLI 新建记录的额外规则仍由原命令负责。

共享身份与比较规则由 `candidate_evidence` 提供，当前文件核验由 `evidence_files`
提供；测量计划与条件经验直接依赖它们，不再通过参数接收整个档案 module。
`candidate_archive` 继续导出原名称，具体 interface 见[候选证据说明](candidate-evidence.md)。

档案 JSONL schema 1、campaign schema 2、CLI 和旧在途请求不变。测试通过真实
临时目录跨上述 interface 检查文件核验范围、整段隔离和恢复；Driver 流程测试保留
失败 receipt、旧请求恢复、进程与持久化的跨职责保证。当前仍完整回放历史并核对
前缀摘要；这次提取不承诺轮末复杂度只随新增事件增长。
