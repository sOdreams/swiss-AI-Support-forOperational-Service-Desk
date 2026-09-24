# 给下一位开发者 / GPT 的 FAISS 接入说明

先阅读根目录 `AGENTS.md`，然后执行 `backend/README.md` 的 quick start。
本分支已实现召回，不需要重新写 FAISS wrapper 或把实验脚本复制进来。

## 当前已经实现什么

- 独立 Python package：`service_desk.retrieval`。
- 固定 MiniLM + 标题/描述/评论（SDC）+ 精确 FAISS cosine 检索。
- 默认 **Top-50 去重证据组**，每条有 **rank（1–50）**、score、document_id。
- 原始评论与各自作者、工单行号、service/team 一一关联；不是把聚合组的
  第一个作者当成整组作者。
- HTTP 检索接口、完整来源分页、前端证据展示/选择和 SQLite 反馈保存。
- 离线建索引、启动加载一次，反馈不会直接改索引。

## 下一步接 filter / routing 的位置

```python
from service_desk.retrieval import TicketQuery, TicketRetriever

retriever = TicketRetriever.load("artifacts/retrieval/minilm-sdc-v1")
candidates = retriever.search(TicketQuery(
    summary=ticket_summary,
    description=ticket_description,
    comments=tuple(comment_bodies),
), top_k=50)

# 以下两个函数属于你后续实现的业务逻辑，不是本仓库已有 API：
# filtered = filter_evidence(query, candidates)
# routing = propose_routing(query, filtered)
```

输入只用当前已知的叙述内容。不要依赖“先预测 service，再按 service 搜索”。
原始票据上的 service/work type 也可能填错，当前召回不使用它们来加分或过滤。
filter 可以读取候选内容和来源 metadata，但保留原始 `rank`，需要重排时另加
`rerank_rank` / `rerank_score`，不要覆盖 cosine 或把它解释成置信度。

50 条候选的单位是 **title+description 分组**，不是50个原始工单，也不是50种
解决方案。同组历史评论可能描述不同事件，filter 应挑选具体评论并保留其
source provenance。缺少合适证据时允许返回空，不要强制编造解决方案。

routing 可以参考选中评论的作者、历史 service/team；历史 Assignee 是另一个
字段，不等于真正解决问题的人。不要只凭聚合组里多数作者直接指定负责人。

## 两个不能直接替换的旧接口

`data-exploratory` 分支的 `TriageEngine.retrieve()` 返回 `(training row index,
lexical score)`。本实现返回 `(group document_id, cosine score, evidence)`。

1. **不能**用 `training_records[hit.document_id]`。要读取 hit.evidence 内对应
   source，必要时调用 `retriever.sources(document_id, offset, limit)`。
2. **不能**把 cosine 填进原来的词法评分公式。旧代码含
   `min(score, 8) * .12`、score 求和及 resolution bonus；应在下游另行评估
   rank 权重或校准方案。
3. 旧 `best_resolution_example()` 会从整份 service catalogue 额外找证据；
   若保留它，必须明确记录是“额外 fallback”，不能冒充 Top-50 内的结果。

本分支没有改写或合并旧 routing pipeline。独立召回可以先接入新的 filter，
再逐步适配旧 pipeline，避免把检索迁移和路由规则变化混成一次改动。

## 前端接入位置

实际页面：`App.tsx → TicketOverview.tsx → TicketProcessor`。
`useRetrieval.ts` 请求 `/retrieval/search`；会取消过期请求并屏蔽切票后的旧响应。
`RetrievalEvidencePanel.tsx` 展示50条候选，勾选表示本次人工review使用的证据。
`AiProposalPanel.tsx` 是旧组件，不是当前应用入口。

上传的 ticket 只存在浏览器状态里，因此传 summary/description/comments，
不要只传 issue ID 让服务端查不存在的工单记录。

`POST /tickets/process` 把本次 model/index version、展示ID、使用ID与人工反馈
一起保存；没有已实现的在线学习、自动更新 FAISS 或 Jira 写回。

## 测试与评价边界

运行 `python -m pytest backend/tests -q` 和前端 typecheck/lint/build。
迁移复现脚本是 `backend/scripts/verify_baseline.py`，结果在
`backend/validation/baseline-parity.json`。细小浮点误差可能让近乎并列候选交换
位置；报告要保留这种差异，不可写成全部严格一致。

之前20条例子的比较是开发集上的 qualitative analysis，不是官方 GT。
FAISS 迁移一致性也不是新的模型准确率。更换 embedding、分组粒度或文本组合后，
应重新比较召回，并独立评估 filter/routing，不能沿用之前指标作为新方案成绩。
