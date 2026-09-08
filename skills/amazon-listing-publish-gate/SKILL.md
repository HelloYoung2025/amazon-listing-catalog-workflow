---
name: amazon-listing-publish-gate
description: "Amazon Listing/A+ publication gate: validate Listing Bundle v1.1, A+ Bundle v1.3 and Handoff v1.1, run the cross-bundle coordinator and receipt ledger, migrate legacy bundles, render read-only staff HTML, and hold the read_only / publish_support boundary. Use only for preflight_qa, publish_support, formal Bundle validation or multi-locale group checks; never for research, interviewing or copywriting."
---

# Amazon Listing Publish Gate（发布门禁）

这是治理层，不是创作层。它只做四件事：校验正式 Bundle、跑跨文件协调器与回执账本、迁移旧版 Bundle、渲染只读员工报告。研究、提问、写文案、A+ 设计都不在这里，分别属于 `$amazon-listing-catalog-workflow` 与 `$amazon-premium-aplus-planner`。

## 何时加载本 Skill

| 触发 | 做什么 |
|---|---|
| 主入口进入 `preflight_qa` 或 `publish_support` | 把定稿的三通道文案中的 `SAFE` 句装入正式 Bundle，跑校验与协调器 |
| 用户直接给出 `listing-*.json` / `aplus-*.json` 要求校验、迁移或出报告 | 直接运行对应 CLI，返回结构化结果 |
| 两个以上站点/语言要一起过门 | 使用 `--group-manifest` 精确文件入口 |
| A+ 规划器返回 `COMPONENT_PASS` / `DELTA_REQUIRED` 需要记账 | 由父级协调器 CLI 记录回执 |

不要在预研、提问、发散生成、买家评审阶段加载本 Skill。那些阶段产出的是工作稿，不进 Bundle。

## 权限边界（不变）

- 默认 `execution_boundary = read_only`。本 Skill、校验 PASS、HTML、策略批准都**不是**对 Amazon、ERP 或任何外部系统的写入授权。
- `publish_support` 只是"支持发布"，不是授权。真实上线动作需要：账号、站点、语言、child 范围、字段、精确 Change Set、基线、回滚、操作人、有效期。
- `ACCEPTED_BACKEND` 不等于 `LIVE_PASS`；每个目标 child 与 locale 必须回读为 `LIVE_MATCH`。
- 校验器只证明本地合同一致，不证明事实为真、规则最新、授权真实或页面已上线。
- 回执账本是本地证据写入，只在显式 `--record-receipt` + `--receipt-ledger` 时发生；它不改变 read_only，也不证明任何外部状态。

## CLI 一览

下面的路径相对于本 Skill 根目录（即本 SKILL.md 所在目录，安装后通常是 `~/.codex/skills/amazon-listing-publish-gate/`）；调用时拼成绝对路径。

```bash
# Listing Bundle v1.1
python3 tools/listing/scripts/validate_listing_bundle.py <listing.json>
python3 tools/listing/scripts/migrate_listing_bundle.py <v1.0.json> --output <v1.1.json>
python3 tools/listing/scripts/render_listing_report.py <validated-v1.1.json> --output <report.html>

# A+ Bundle v1.3
python3 tools/aplus/scripts/validate_bundle.py <aplus.json>
python3 tools/aplus/scripts/migrate_aplus_bundle.py <legacy.json> --output <aplus-v1.3.json>
python3 tools/aplus/scripts/render_aplus_report.py <validated-v1.3.json> --output <aplus-report.html>

# 跨文件协调器（唯一的 Listing+A+ 组合入口）
python3 tools/listing/scripts/validate_listing_package.py <listing-v1.1.json> <aplus-v1.3.json>
python3 tools/listing/scripts/validate_listing_package.py <frozen-listing.json> <aplus.json> --receipt-ledger <coordination.jsonl> --record-receipt
python3 tools/listing/scripts/validate_listing_package.py --group-manifest <listing-locale-group.json>

# 迁移无损自检（仅证明脚本可用，不代表页面质量）
python3 tools/listing/scripts/run_forward_tests.py
```

父/子校验器互不导入；只有 `validate_listing_package.py` 拥有跨文件真相。纯 API 与旧 `--prior-receipt` 路径永不返回终态 PASS。

## 从三通道文案到 Bundle

主入口定稿产出 `SAFE / CANDIDATE / HOLD` 三通道。进门规则：

- 只有 `SAFE`（每句已绑定 Fact ID 且事实状态为"已证"）可以进入 Bundle 的最终消费者文案。
- `CANDIDATE` 保持在员工核实清单；核实完成、事实台账更新为"已证"后才升级。
- `HOLD`、`CONFLICT`、仅观察、推断、过期或已接受重大风险的内容不得进入最终文案。
- 变体隔离：child / pack / 颜色 / 尺码 / 版本 / 站点 / 语言 不得互相借证。覆盖检查只对真实存在的组合做（某个买家问题 × 某个站点 × 某个语言 × 某个真实 child 行），不把所有维度机械相乘出一堆不存在的组合。
- 答案地图前 10 条买家问题的回答句必须能定位到 Bundle 中的原生可见字段（Title / Highlight / 五点 / 描述 / A+ 正文），ALT、图内文字、视频、后台词、社区 Q&A 只算辅助。

## 结论词

| 结论 | 含义 |
|---|---|
| `PASS` / `COMPONENT_PASS` / `GROUP_PASS` | 本地合同通过；仍需外部授权与回读 |
| `DELTA_REQUIRED` | A+ 返回证据缺口，父级须核对、`SUPERSEDED` 旧快照、revision+1、重新 `FROZEN` |
| `BLOCKED` | 身份、Product Type/PTD、字段能力、pack/child 范围、P0 证据或 handoff 完整性未解 |
| `NO_VALID_CONCLUSION` | 用户问的那个结论本身答不了（例如要判“能否上线”但没有任何后台证据）；只用于范围明确的审计 |
| `CATALOG_COMPLETE / MARKET_BET_NOT_CLOSED`、`STRATEGY_SELECTED / PUBLICATION_BLOCKED` | 工作结论，不写入 Bundle 枚举 |

## 参考文档（按需读）

- [listing-bundle-v11-governance.md](references/listing-bundle-v11-governance.md)：Listing Bundle v1.1 schema、身份门、Product Type 规则快照、字段解析记录、真相/主张/冲突、变体拓扑、发布包、回读状态机、迁移。
- [listing-decision-atoms-and-handoff-v11.md](references/listing-decision-atoms-and-handoff-v11.md)：决策分母、Canonical Assertion、PTD 字段闭合、原子答案与 Coverage Gate、Handoff v1.1 状态机、嵌入式 A+ 边界、多站点组运行时。
- [aplus-bundle-v13-delivery-and-validation.md](references/aplus-bundle-v13-delivery-and-validation.md)：A+ Bundle v1.3 交付包、Handoff 血缘、Gate、结论、基线/Change Set/回滚、`workflow_context`、`enriched_content_handoff`、能力快照、结果块、覆盖校验、发布与回读边界。

历史 Bundle 与报告只读，不原地迁移；显式请求的迁移写到新文件。
