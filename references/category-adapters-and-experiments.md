# Category adapters and experiments

只在产品命中某个品类时读对应一节；它提供预研三员的追加探针、退货风险与 QA 问题，从不提供产品事实。`category_adapter` / `experiment_registry` 的对象结构只在进入 `$amazon-listing-publish-gate` 正式 Bundle 时才需要。

Read only the adapter relevant to the product. Adapters supply investigation prompts, evidence probes, return-risk checks, and QA questions. They never create Amazon fields, replace Product Type/PTD evidence, or contribute a product fact.

Record exactly one selected adapter in `category_adapter`; use `generic` when no specialized adapter applies. The closed adapter IDs are `generic`, `apparel/fit`, `connected-device`, `home/kitchen`, and `regulated/beauty`. The object contains exactly `name`, `version`, `status`, `question_prompts`, `evidence_probes`, `return_risks`, and `qa_checks`. For a cross-category product, select the dominant risk adapter and add any other evidence questions to Discovery; do not invent a second adapter object or PTD override.

## `generic`

Investigate identity, included/not included, material, dimensions, use/care, intended and unsuitable users, important limits, packaging, variants, warranty/claims and return-preventing selection information where applicable. Mark inapplicable items with reasons. For unfamiliar Product Types investigate current marketplace requirements; this adapter is not a complete category compliance library. New products and resellers may have unknown origin or no sales history; record the absence and continue present-use research.

## `apparel/fit`

Probe body and product measurements, measurement method, fit preference, size transitions, stretch versus tested recovery, coverage, support/compression level, fabric label, care, skin contact, closures, removable/included inserts, and variant-specific imagery. Do not infer cup range, maternity-stage coverage, support level, breathability, shrinkage, or fit from seamless construction or fiber content alone. For actual bra/cup products, full-coverage cups are not a full-bust or busty-engineered claim. For actual nursing products, a clip-down nursing clasp is not hands-free pumping compatibility. Removable foam cups are not absorbent or leakproof nursing pads. If a sibling SKU owns pumping or sports, keep those jobs off the everyday nursing child.

For every affected child, ensure size-chart units, garment measurements, body measurements, fit guidance, title/highlights/bullets, images, and A+ do not contradict one another. A remembered measurement or generic category behavior remains `HOLD`.

## `connected-device`

Where the product uses the relevant subsystem, probe power, voltage, network bands and setup conditions, supported operating systems, ports, hardware/firmware revision, storage, subscription/payment, privacy, installation, accessories, warranty, and safety certification. State incompatible systems and required paid capability before the corresponding benefit.

When relevant, build child-scoped working records for network/setup behavior, subscription/storage capability, and pack/accessory contents. These records are evidence tools, not backend field names.

## `home/kitchen`

Probe exact dimensions, usable capacity, material, food-contact or surface suitability where relevant, load/temperature/water limits, assembly, included parts, consumables, replacement parts, cleaning, storage footprint, and foreseeable misuse. Separate measured values from packaging values and marketing estimates.

## `regulated/beauty`

Probe ingredients/materials, quantity, allergen/dietary information, directions, warnings, storage, shelf life, jurisdiction, applicable registration/certification, and claim substantiation. Keep medical, disease, treatment, safety, comparative, and quantified efficacy statements blocked until the required evidence and review are present.

## Experiment registry

Known factual, compliance, identity, scope, accessibility, and mobile defects are repairs, not experiment candidates. Experiment only between truthful, evidence-supported persuasion alternatives.

The exact `experiment_registry` object contains `id`, `hypothesis`, `status`, `application_scope`, `metric`, `baseline_ref`, `candidate_ref`, `started_at`, `ended_at`, `owner`, and `decision`. Each active experiment records:

- hypothesis and customer decision expected to change;
- exact parent/child/Pack/color/size scope (marketplace and locale remain bound by the parent Bundle);
- explicit frozen baseline and candidate references;
- primary metric, owner, and lifecycle timestamps;
- a completion/cancellation decision. Guardrails, eligibility evidence, stop rules, and attribution limits belong in the referenced experiment plan/evidence, not as invented Bundle keys.

`gate_reviews` are evidence records, not override controls. A `PASS` review needs a reviewer, timestamp, usable evidence references, and no blockers; `FAIL`/`BLOCKED` needs blocker IDs. Neither a review nor a self-reported project conclusion can replace machine-derived Gates.

Do not use a fixed 7–14-day rule. Follow the current account's supported experiment types, traffic eligibility, duration options, and result semantics. A multi-attribute winner does not prove which individual element caused the result. A conversion lift does not by itself prove lower returns, higher profit, COSMO ingestion, or Alexa recommendation causality.

Keep content-understanding checks, search-funnel observations, PDP conversion experiments and return/profit analysis distinct. Use only available report definitions and comparable scope/periods; SQP impressions/clicks/cart adds/purchases do not by themselves identify Alexa or organic-only traffic. Note changes in price, delivery, stock, reviews and other confounders. Before any separately authorized experiment, inspect actual start and auto-publish settings: preparing or approving copy does not authorize scheduling, spend or automatic publication. Store these checks in the referenced plan/evidence, not new registry keys.
