---
name: amazon-premium-aplus-planner
description: "Plan, audit or rebuild Amazon Premium A+, Basic A+ and Brand Story as module-level briefs with native copy, image briefs, ALT and capability checks. Embedded mode consumes the Listing entry's intent brief, winning direction and fact ledger without re-interviewing; standalone mode reuses the Listing entry's three recon agents for A+-only work. Excludes ads-only work, review manipulation and any Seller Central write; formal A+ Bundle v1.3 validation lives in amazon-listing-publish-gate."
---

# Amazon Premium A+ Planner（A+ 规划器）

A+ 的职责是**深化证明与选择**：Listing 首屏已经说了买什么、为什么；A+ 用模块把"为什么可信、我该选哪个、什么情况不适合"讲透。它不重新定位，不重新访谈。

默认 `read_only`。设计批准不是发布授权。正式 A+ Bundle v1.3、Handoff、协调器交给 `$amazon-listing-publish-gate`。

## 两种入口

| 模式 | 何时 | 输入 | 不做 |
|---|---|---|---|
| **Embedded（嵌入式）** | 主入口 `$amazon-listing-catalog-workflow` 定稿后交接 | 产品意图简报、胜出方向与淘汰理由、事实台账（SAFE/CANDIDATE/HOLD）、字段分工、答案地图中"A+ 承担"的行、图片素材现状、老板第二轮决定 | 不重新访谈、不重新定位、不复活落选方向、不扩大 child/pack 范围、不自行补事实 |
| **Standalone（独立）** | 用户只选 E（A+），无 Listing 续做 | 链接、附件、后台截图 | 不把用户送回 Listing 菜单再确认一次 |

Standalone 直接复用主入口的阶段 0–3：自己出一张简版任务确认卡（只列 E 的范围与动作），起同样的三个预研员（产品调查 / 竞对拆解 / 买家问题），发同样的第一轮题包，合成同样的意图简报与取舍表；读 `$amazon-listing-catalog-workflow/references/01-recon-and-fact-ledger.md` 与 `02-two-round-questions.md`。之后从下面第 2 步开始。Listing 字段在 standalone 里只作上下文，不产出替换文案。

Embedded 的触发条件就是主入口的定稿交接简报（意图简报 + 胜出方向 + 事实台账三档 + 字段分工），不需要任何 FROZEN / Handoff v1.1 状态；那些只在进 publish-gate 做正式 Bundle 时才出现。

请求嵌入式续做但交接缺失 / 过期 / 不匹配 → 暴露并要求主入口核对，不静默改 standalone。

## 工作流（Embedded 从第 2 步开始）

1. **预研与合成**（仅 standalone）：同主入口阶段 1–3。
2. **能力核查**：刷新当前账号的 A+ Builder / Premium 资格、可用模块、规格上限、AI 媒体披露规则（读 [official-source-refresh.md](references/official-source-refresh.md) 的路由，记录核对日期）。未知能力标"待核"，不假设 Premium 模块可用。
3. **模块序列设计**：按买家决策问题选模块，不按模板凑数。序列必须完成一次 **欲望 – 事实 – 边界** 三段：为什么想离开旧的凑合 → 什么机制让选择可信 → 什么情况不该买。读 [01-aplus-strategy-and-modules.md](references/01-aplus-strategy-and-modules.md)。
4. **发散生成**（重建或旧内容平庸时）：起 2 个文案员按主入口 03 的视角（从 场景任务 / 选对去顾虑 / 破惯例 中选两个最贴合胜出方向的）各写完整 A+ 序列（模块标题 + 正文 + 画面指令 + ALT），互不可见。Embedded 模式下视角固定服务胜出方向，不许换主线。
5. **评审与裁决**：主入口 04 的模拟买家 1 名（用"不该买的人"人设）只读英文模块文案；真相检查器逐句对台账；规则检查器核对模块字数、比较图只限同品牌、图上文字、ALT 上限、AI 图像披露。主智能体选一个序列，吸收具体句子，写淘汰理由。
6. **模块卡与视觉简报**：每个模块一张标准卡（见 01）；每张图一份素材记录（生成方式、合成人物、产品保真负责人）。
7. **编辑验收**：读 [02-editorial-acceptance.md](references/02-editorial-acceptance.md)，做四项检查：理解 / 选对 / 拒错 / 手机端。
8. **交付**：模块级 A+ 方案 + Brand Story（如适用）+ 视觉简报 + ALT + 能力核查表 + 证据请求清单，写进主入口的全宽 HTML 第 8 节，或 standalone 单独出 HTML（用 `assets/full-width-report-shell.html`）。
9. **回传**：Embedded 模式下，事实缺口以"证据请求"返回主入口（哪个模块、哪句、需要什么证据、降级句），不自行补事实，不改台账。

子智能体预算（回炉与重试计入）：
- Embedded：≤ 5 次 = 生成 2 + 评审 3（买家 1 名“不该买的人”+ 真相 1 + 规则 1）。整页含 A+ 的总预算因此是 Listing 12 + A+ 5。
- Standalone：预研 3 + 生成 3 + 评审 5 = 11，与主入口同口径 ≤ 12；能力核查由主智能体自己做，不起子智能体。
超出即降级为主智能体单独执行并声明。

## 证据规则（A+ 特有）

- 每个模块的每句正文、每条图上文字、每个画面里的产品行为都要绑定 fact_id 或标 `[NEEDS PROOF]`。图片不能替代关键事实的文字：尺码、安全、兼容、含不含、pack、使用限制必须有原生文字。
- 老板记忆、竞品文案、评论、社群帖、推断默认 HOLD，不能成为本品事实；可以作为研究假设与中性澄清。
- Brand Story 的历史陈述（"创立于""因为某次经历"）必须有来源绑定（老板书面答复、官网、注册记录）；没有来源就不写历史，写现在。
- 新品、转售、无销售史：不发明创始故事。
- 变体隔离：`Parent × Child × 站点 × 语言 × Pack × 颜色 × 尺码 × A+ Content ID × Brand Story ID`，一个模块只对它标注的 child 说话。
- AI 只能生成人物与环境（在权利与平台规则允许时）；产品本体用实拍或受控参考，不改形状、接口、扣具、数量、颜色、比例、覆盖、内含物。每张图记生成方式与保真状态；`unknown` 阻塞消费者可见使用。
- 比较图只限同品牌真实差异；不点竞品名；不做"others"隐含对比，除非当日核对过规则允许。
- Premium Q&A 是品牌撰写的事实内容，不模仿社区 Q&A、不编买家对话。

## 结论词

| 结论 | 含义 |
|---|---|
| `COMPONENT_PASS` | A+ 组件完成（正式化时由 publish-gate 校验） |
| `DELTA_REQUIRED` | 返回证据请求，等主入口核对与重新冻结 |
| `IN_PROGRESS` / `BLOCKED` | 本地构建或 QA 未完成；能力不足也用这个，不伪造证据缺口 |
| `CATALOG_COMPLETE / MARKET_BET_NOT_CLOSED` | 事实都齐了，但还没找到值得赌的卖点（工作结论，不进 Bundle） |

## 参考文档

- [01-aplus-strategy-and-modules.md](references/01-aplus-strategy-and-modules.md)：决策地图、模块选择表、标准模块卡、文案链、欲望–事实–边界、ALT、AI 图像、Brand Story。
- [02-editorial-acceptance.md](references/02-editorial-acceptance.md)：理解 / 选对 / 拒错 / 手机端四项验收，独立 QA 提问清单，HTML 要求。
- [official-source-refresh.md](references/official-source-refresh.md)：官方来源路由与刷新纪律（快照日期见文件头，任务当日必须重新核对）。
- 正式 Bundle v1.3、Handoff v1.1、结果块、覆盖校验：`$amazon-listing-publish-gate/references/aplus-bundle-v13-delivery-and-validation.md`。

## 不做什么

- 不重新访谈已冻结的事实与意图简报；不重选主购买理由；不复活落选方向。
- 不用 HOLD、冲突、仅观察、推断的内容写模块文案或画面。
- 不承诺 Premium 模块、不假设字段能力、不宣称 ALT 或 A+ 有独立的 Alexa/COSMO 权重。
- 不生成、读取或写入协调回执账本；那是 publish-gate 的事。
- 不扩展广告、定价、库存、评论操作、任何线上写入。
