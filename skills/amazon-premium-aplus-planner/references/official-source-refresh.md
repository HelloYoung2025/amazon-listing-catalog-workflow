# Official Source Refresh Route

Snapshot verified: `2026-08-28`

This file is a routing aid, not a permanent statement of Amazon policy. Recheck the sources required by the current task, marketplace, locale, account UI, category, and content type. Record the new verification date in the project source register; update this reference only when explicitly maintaining the Skill.

## Refresh discipline

- Capture the target PDP, selected child, competitor pages, child matrix, content applications, and relevant backend state for the current task date.
- Recheck A+ Builder/Premium eligibility, module specifications, MYE eligibility, AI-media disclosures, and category rules whenever the task depends on them.
- Treat sign-in-gated help or account UI as scoped account evidence and preserve screenshots/exports.
- A renamed field, hidden field, or changed UI is a reason to refresh, not a reason to invent an equivalent.
- Record official source, publication/update date when shown, retrieval date, marketplace, and what the source actually establishes.

## Current official routes

| Topic | Official route | Verify |
|---|---|---|
| Product Type Definitions | https://developer-docs.amazon.com/sp-api/docs/product-type-definitions-api-v2020-09-01-reference | current Product Type schema model, requirements, enums, and conditionality; account evidence still resolves actual applicability |
| Manage product listings | https://developer-docs.amazon.com/sp-api/docs/manage-product-listings-guide | current PTD/listing workflow model; this Skill does not develop or assume API credentials |
| Item name and Item highlights change | https://sellercentral.amazon.com/seller-forums/discussions/t/145b6d0f-999c-4555-896c-c694bda2e470 | dated general limits, rollout, search/display statements, and affected categories |
| Item highlights official Q&A | https://sellercentral.amazon.com/seller-forums/discussions/t/e590b18e-8710-4263-a0d8-4aeb66700ba0 | relationship between Item name and Item highlights; current account field availability still needs proof |
| A+ eligibility, Basic/Premium, Brand Story, current module counts | https://sellercentral.amazon.com/help/hub/reference/external/G202102930 | account eligibility, module choices, application and quality rules |
| A+ design guidance | https://sell.amazon.com/blog/a-plus-content-design-guide | current design, native text, image, mobile and module recommendations |
| A+ product overview and AI-ready workflow | https://sell.amazon.com/tools/a-content | current creation/apply/review flow and AI-ready features |
| A+ API field examples and ALT constraints | https://developer-docs.amazon.com/sp-api/lang-en_US/docs/a-plus-content-examples | exact module field limits for the current content model |
| ALT/Image Keywords moderator guidance | https://sellercentral.amazon.com/seller-forums/discussions/t/79c48d14-7001-470d-ae54-d21d9b301312 | simple image description, screen-reader purpose, and stated search use |
| Manage Your Experiments | https://sell.amazon.com/tools/manage-your-experiments | eligibility, supported experiment types, duration/result guidance, start and automatic-publication settings |
| Amazon Brand Analytics | https://sell.amazon.com/tools/amazon-brand-analytics | current reports and account eligibility |
| Brand Analytics use and SQP concepts | https://sell.amazon.com/blog/brand-analytics | current query/funnel fields and intended analysis use |
| Alexa for Shopping, formerly Rufus | https://www.aboutamazon.com/news/retail/amazon-rufus-ai-assistant-personalized-shopping-features | current name, surfaces, and information sources |
| Alexa for Shopping overview | https://www.aboutamazon.com/news/retail/alexa-for-shopping-ai-assistant | current shopping questions, contextual preferences and product comparison capabilities; no seller field-weight guarantee |
| COSMO research | https://www.amazon.science/publications/cosmo-a-large-scale-e-commerce-common-sense-knowledge-generation-and-serving-system-at-amazon | research claims about intent/common-sense knowledge, not seller field weights |
| Alexa for Shopping advertising prompts | https://advertising.amazon.com/library/news/agentic-shopping-advertising | current paid conversational-ad path; keep separate from organic recommendation |
| AI-generated realistic people | https://sellercentral.amazon.com/seller-forums/discussions/t/aa0aee06-aff4-497a-a4b6-9b2ebe06f715 | current metadata/checkbox/disclosure route and scope |

## Facts supported by this snapshot

As of the snapshot date:

- Amazon announced a 75-character Item name and 125-character Item highlights split for applicable non-media products. The official Q&A described both as search inputs and Item highlights as visible under Item name. This is not proof that a specific account/Product Type exposes an editable field; verify its real key, requirement state, limit, scope, and frontend rendering.
- Amazon Help described Basic A+ as allowing up to five modules chosen from fourteen and Premium A+ as allowing up to seven chosen from nineteen. These are current platform parameters, not a mandate to fill every slot.
- Premium capabilities included richer modules such as hotspots, video, enhanced comparisons, carousels, and Q&A, subject to eligibility and current account availability.
- SP-API A+ examples showed image `altText` constraints of up to 100 characters for the documented modules. The moderator guidance described ALT as a simple image description used by screen readers and stated that it helps products in search results.
- Rufus was renamed Alexa for Shopping on 2026-05-13. Amazon described the experience as drawing from product catalog information, reviews, Community Q&A, information across the web, and conversational/user context.
- Amazon Science described COSMO as an e-commerce common-sense knowledge system informed by behavior relationships and user intent. It did not publish a seller-editable A+ or ALT weighting formula.
- Manage Your Experiments described random audience splitting, a run-to-significance option, and an official custom-duration recommendation of eight to ten weeks, with some experiments potentially concluding sooner. Always use the current account's supported experiment types and result fields.

## Do not infer

Maintenance note checked 2026-09-05, separate from the historical snapshot above: the MYE public overview describes PDP-visitor randomization and sales/conversion results, with preselected start and automatic-publication behavior. Inspect actual account settings and separate authorization before scheduling. Those results do not isolate search impressions or Alexa referral causality. The current Alexa overview describes contextual shopping and comparisons, not a seller-controlled allocation formula. Account capabilities and category-specific comparison rules still require current scoped verification.

- Do not promise that adding A+ or ALT creates an independent Alexa/COSMO traffic boost.
- Do not present COSMO relation types as hidden listing fields or a scoring rubric.
- Do not treat `subtitle` or `item_subtitle` as an alias for Item highlights. Resolve the actual field from current applicable account evidence.
- Do not mix Alexa for Shopping paid conversational prompts with organic recommendation or PDP content effects.
- Do not turn Amazon's aggregate marketing uplift language into a target ASIN forecast.
- Do not treat an official maximum module count as the correct module count for every product.
- Do not treat forum seller opinions as policy. A moderator answer can clarify an official workflow but should still be labeled as such.

## If current evidence changes

Use the live verified rule in the project. Preserve the previous snapshot as historical context, record the conflict, and identify which planned copy, asset, field, or experiment must change. Do not silently rewrite a source date or claim that the older rule never existed.
