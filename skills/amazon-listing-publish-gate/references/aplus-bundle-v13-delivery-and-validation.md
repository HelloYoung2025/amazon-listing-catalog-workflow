# Delivery and Validation

Use this reference for formal project Bundles, staff upload-preparation HTML, preflight QA, publish support, rollback, live readback or experiments. Its maximum_work and Gate restrictions govern formal Bundle contents, not separate supported INTERNAL_PROTOTYPE / NOT_FOR_UPLOAD working drafts under the discovery/strategy references. Such drafts cannot imply formal coverage, field capability or authority; unsupported claims remain excluded.

## Required delivery package

A substantial rebuild should include:

1. final conclusion and authority boundary;
2. Scope Envelope and source register;
3. current-state evidence pass, Discovery/Socratic closure, and evidence actions;
4. Product Truth, Claim, Conflict, and real variant records;
5. Customer Decision Map, denominator atoms, Canonical Assertions, and bounded positioning;
6. competitor/VOC matrix and category-parity analysis;
7. current capability snapshot, module allocation, carriers, and native answer units;
8. parent/child/Pack/locale application matrix;
9. Asset Manifest and AI/synthetic status;
10. prohibited/hold claims and delta evidence requests;
11. production SOP, owners, derived gates, QA, rollback, and live readback;
12. experiment plan and source-refresh notes.

Lead with `最终的结论` for a Chinese staff handoff. Separate what can be designed, what can be published, and what remains blocked.

## Current embedded Handoff v1.1 lineage

An embedded A+ Bundle accepts the Parent's frozen Handoff exactly; it does not recreate or refreeze it. `semantic_revision=1` has empty predecessor, reason, and `lineage_registry`. Every revision after 1 must carry exactly one immediate-predecessor registry record containing the prior content-addressed snapshot, Handoff checksum, parent-bundle hash, `SUPERSEDED` status, exact successor, prior revision, ordered creation/supersession times, full immutable prior Handoff projection, and record checksum. The embedded predecessor projection must reproduce the old snapshot and checksum, and nested registry records recursively prove the earlier chain.

Random predecessor IDs, revision jumps, a predecessor not marked `SUPERSEDED`, successor mismatch, malformed time order, or altered record/projection block the A+ component. The Parent and package coordinator apply the same contract. A+ may return an exact `delta_evidence_request`; only the Parent can update evidence and create a new frozen successor. Local hash validation proves contract integrity, not external Amazon truth or publication.

## Legacy v1.1/v1.2 background

The historical sections below document fields retained for migration and compatibility. Do not start a new project from the legacy v1.1 shape. A+ v1.1/v1.2 inputs are read-only `LEGACY_LOCAL_CONTRACT` and cannot receive v1.3 Coverage, embedded Handoff, publication authority, or live status by implication.

The old empty template used `project.status: "SCAFFOLD"`; a populated legacy bundle used these top-level keys:

```text
project, scope, platform_limits, sources, facts, claims,
decision_map, competitor_insights, positioning, conflicts,
variants, modules, assets, publish_authorization, baseline,
change_set, rollback, live_readback, gates, experiments
```

### Project

Required for a deliverable:

```json
{
  "title": "...",
  "marketplace": "US",
  "locale": "en-US",
  "target_type": "live_asin|prelaunch_sku|hypothetical_fixture",
  "focal_identity": {
    "identifier": "...",
    "identifier_type": "asin|sku|url|unknown",
    "identity_status": "UNVERIFIED|VERIFIED_PARENT|VERIFIED_CHILD|CONFLICT|NOT_APPLICABLE",
    "verified_focal_child": "",
    "provisional_parent": "",
    "verification_source_ids": []
  },
  "mode": "audit|plan|rebuild|preflight_qa|publish_support",
  "status": "ACTIVE",
  "snapshot_date": "YYYY-MM-DD",
  "write_scope": "read_only|explicit_write",
  "conclusion": "PASS|CONDITIONAL_PASS|BLOCKED|NO_VALID_CONCLUSION|ROLLBACK",
  "conditional_draft": {
    "status": "NOT_EVALUATED|ACTIVE|CLEARED|BLOCKED",
    "maximum_work": "audit_only|audit_and_gap_report|strategy_dependency_only|full_production",
    "blocked_outputs": [],
    "blocker_ids": []
  }
}
```

Do not force an unverified parent, URL, SKU, or guessed ASIN into `verified_focal_child`. Preserve the supplied identifier and its status. In v1.3, `strategy_dependency_only` means source/evidence audits, gap and research tasks, answerability gaps, route/proof matrices, and dependency skeletons only. It explicitly excludes Title, Highlight, bullets, module prose, wireframes, image concepts, ALT, baseline copy, conditional alternatives, or any other consumer-facing candidate. `full_production` becomes admissible only after Product Truth, Round 2, Product Intent, and One-Bet gates close; it does not imply publish authorization.

### Structured scope

Use a top-level Scope Envelope and repeat the applicable subset on every source, fact, claim, module, and asset. The canonical shape is:

```json
{
  "marketplace": "US",
  "locale": "en-US",
  "parent_asin": "",
  "child_asins": [],
  "packs": [],
  "colors": [],
  "sizes_or_capacities": [],
  "other_variants": {}
}
```

The top-level `scope` also carries `status`, plural marketplace/locale/parent fields, the intended child set, and `source_ids`. Use `N/A` only when a field truly does not apply; use an empty value plus an explicit blocker when it is unknown. A narrower source or fact cannot prove a broader claim.

### Platform limits

Do not rely on a permanent built-in constant. Store the task's verified value and source:

```json
{
  "alt_max_chars": 100,
  "basic_max_modules": 5,
  "premium_max_modules": 7,
  "available_module_types": [],
  "content_type_eligibility": "UNVERIFIED",
  "last_verified_at": "YYYY-MM-DD",
  "source_ids": ["SRC-OFFICIAL-ALT"]
}
```

Use `source_ids` as the v1.1 evidence field. The template also retains singular `source_id` as a primary-source alias; when populated, it must name a member of `source_ids`. Limits, available module types, eligibility, rules, and names are dynamic and need dated applicable sources.

### Facts

Each fact needs:

```text
id, statement, scope, evidence_type, evidence_strength,
source_ids, proving_source_ids, observed_at, publish_status, owner
```

Optional but useful: unit, allowed_expression, prohibited_derivation, conflict_group, evidence_action, expires_at.

`proving_source_ids` are the specific readable, applicable sources that establish the fact. `source_ids` may also contain context or conflict evidence. A failed fetch, competitor statement, category norm, VOC, owner memory, or inference cannot be the sole proving source for a consumer-facing product claim.

### Claims

Each claim needs:

```text
id, text, scope, risk_type, fact_ids, publish_status,
consumer_facing, content_status, owner
```

Publishable consumer claims must reference publishable facts whose structured scope contains the claim scope. `HOLD`, `CONFLICT`, or `PROHIBITED` claims cannot be consumer-facing. High-risk claims require applicable strong evidence and compliance review. `CONDITIONAL_DRAFT` is a production state, not proof that a claim is publishable.

### Decision map, competitor insight, positioning, and conflicts

- `decision_map` covers trigger, core/secondary user, scene, job, alternative, pain, outcome, objection, decision criterion, disqualifier, and evidence needed. Every supported answer references facts/sources; unknowns remain explicit.
- `competitor_insights` records competitor role, exact child/marketplace/locale/date/fetch status, category parity, target-verified differences, decision gaps, claim risks, and structural patterns. Competitor evidence may identify a question or pattern, but cannot prove the target product.
- `positioning` is bounded to supported audience, situation, job, category, benefit, mechanism facts, and important limit claims. It is not a license to convert inference into fact.
- `conflicts` records all competing statements, affected outputs, decisive evidence, owner, due date, maximum permissible work, and status. Do not ask the user to choose which physical fact is true; create an evidence action.

### Variants

Each intended child row needs:

```text
child_asin, parent_asin, marketplace, locale, pack, color,
size_or_capacity, other_variant, aplus_content_id,
brand_story_id, status, owner
```

Include `source_ids`. Use `N/A` rather than leaving a dimension blank when it genuinely does not apply. A verified child row needs applicable evidence; a provisional or conflicting row remains explicitly non-publishable.

### Modules

Each module needs:

```text
id, decision_priority, decision_question, wrong_user_or_use,
module_type, module_type_verified_at, eligibility_source_ids,
content_status, evidence_gate_status, application_scope,
native_headline, native_body, fact_ids, claim_ids, hold_claim_ids,
applied_child_asins, image_brief, visible_proof_fact_ids,
on_image_text, mobile_plan, prohibited_claims, acceptance_tests,
owner, qa_status, experiment_eligible
```

Module count and order follow decision impact, misbuy/return risk, VOC frequency, differentiation, evidence, and AI-shopping question coverage. They are not inherited from another product or forced to a fixed maximum.

### Assets

Each asset needs:

```text
id, module_id, asset_role, content_status, file, sha256, alt,
application_scope, applied_child_asins, claim_ids, visible_facts,
synthetic_person, generation_method, product_reference_files,
must_show, must_not_change, product_fidelity_owner,
product_fidelity_status, product_fidelity_evidence,
ai_rule_checked_at, ai_rule_source_ids, qa_status
```

An asset cannot move to final when its target product structure, quantity, colors, included items, or child scope are unverified. AI or compositing may create a setting or person only when the product reference and fidelity checks preserve the real product. ALT describes the visible image within the current platform limit; it is not a hidden claims field.

### Publish authorization, baseline, Change Set, rollback, and live readback

`publish_support` requires all of the following structured objects:

- `publish_authorization`: exact actor, expiry, systems, marketplace/locale/content IDs/children, allowed and prohibited actions, and approved Change Set IDs;
- `baseline`: frozen current content/application/copy/assets/ALT/frontend evidence plus concurrent-edit status;
- `change_set`: field/module-level before and after references, child/locale scope, linked facts/claims/assets, owner, approval, applied time, and status;
- `rollback`: baseline link, triggers, safe method, owner, protected P0 facts, verification steps, and evidence;
- `live_readback`: one row per child and locale for identity, quantity, color, size/capacity, included items, copy, assets, ALT, module order, observed content ID, device/viewport, fetch status, evidence, mismatch action, and follow-up.

The first frontend check is `FIRST_READBACK`. It is an observation, not an automatic success or permanent-absence decision. Record `MISMATCH`, `NOT_VISIBLE`, or `FETCH_BLOCKED` field states and schedule a follow-up rather than rewriting history. `Saved`, `Submitted`, or `Approved` in the backend is not proof of `LIVE_PASS`.

### Gates and experiments

Gate rows need `id`, `status`, `owner`, `evidence`, and `failure_action`. Experiment rows need `experiment_type`, a causal hypothesis, exact version difference, treatment components, primary metric, guardrails, run/stop rule, eligibility status and sources, attribution boundary, status, owner, result sources, and conclusion. A multi-attribute package can evaluate the package only; a descriptive before/after observation is not causal.

## Conditional draft and first handoff

When focal identity, child/pack scope, included items, safety/compliance, or another P0 fact is unresolved:

1. preserve the exact unresolved identifier and evidence status;
2. set `project.conditional_draft.status` to `ACTIVE` or `BLOCKED`;
3. name every blocked output and blocker/conflict ID;
4. within the formal Bundle's `maximum_work`, deliver only audits, gap/evidence/research tasks and strategy dependencies; do not insert copy, wireframes, image/ALT or other candidate records. A separate, clearly marked internal working artifact may contain independently supported prototypes under the entrypoint's threshold; unresolved claims stay excluded;
5. use `CONDITIONAL_PASS`, `BLOCKED`, or `NO_VALID_CONCLUSION` as appropriate; never `PASS`;
6. do not assign final copy/assets to an unverified child and do not imply publish authority.

The first evidence handoff should be ordered as: Scope Envelope → source register and fetch status → initial Product Truth and variant matrix → initial Customer Decision Map → conflicts/blockers → one batched question set containing only answers that could change audience, scenario, problem, promise, boundary, variant, evidence, or module choice. A skipped answer remains unknown; it does not become permission to infer.

## HTML reading manual

Use `assets/full-width-report-shell.html` when suitable.

Requirements:

- self-contained and usable without a network connection unless external citations are intentionally linked;
- responsive, 100% of available browser width, with modest edge padding;
- not A4, page-break, or PDF-card layout;
- semantic headings, landmark elements, table captions/headers, keyboard-accessible controls if any;
- tables and evidence galleries may scroll or expand without clipping the whole page;
- critical facts and conclusions remain native text, not only images;
- screenshots include meaningful local ALT;
- no claim of tabs, persistence, copy buttons, dashboards, or other features that were not implemented;
- desktop, tablet, and phone checks use task-appropriate widths; 390px is a practical phone check, not a universal platform rule;
- include exact output date, source dates, current/blocked status, owners, and sign-off.

The HTML is a reading and work-reference artifact unless the user explicitly requests a functional workflow tool.

## Gates

### G0 Facts

- target marketplace and locale bound; focal identity preserved exactly and, for `PASS` or publish support, verified to the intended child;
- intended child matrix complete enough for the content scope;
- physical facts, inclusions, dimensions/fit/compatibility, care, tests, and certificates mapped;
- each consumer claim references scoped Fact IDs with applicable `proving_source_ids`;
- every source/fact/claim/module/asset scope is contained by the frozen Scope Envelope;
- material conflicts have owners and evidence actions.

Failure in the formal Bundle: allow only `audit_only`, `audit_and_gap_report` or `strategy_dependency_only`; block formal consumer candidates, module/asset records, applied-child finalization and publish. Never set `full_production` while this Gate is open. Separate supported internal prototypes do not close this Gate and cannot assert the missing facts.

### G1 Copy

- priority buyer questions have native answers;
- core and wrong user/use case are explicit;
- every claim has allowed scope and no prohibited derivation;
- legal/compliance and product-fact review are separately signed.

Failure: return to claim owner; do not hide the claim in an image or ALT.

### G2 Assets

- product structure, quantity, color, accessories, scale, and mechanism match the sample;
- visible content matches applied child scope;
- AI/synthetic method, reference files, fidelity owner/evidence, and current disclosure check recorded;
- desktop/mobile plan and ALT present.

Failure: rework the asset; copy cannot cure a false image.

### G3 Build

- current module types, native fields, assets, ALT, content IDs, locales, and applied ASINs recorded;
- shared and child-specific content applied as planned;
- preview evidence captured.

Failure: do not submit.

### G4 Preview

- desktop, tablet, and phone reading order checked;
- no critical crop, overflow, unreadable burned-in text, empty/repeated ALT, or variant conflict;
- interactive module behavior, when used, is tested;
- planned copy, asset manifest, and preview agree.

Failure: do not publish.

### G5 Live readback

- after publication, every intended child and locale is read from the frontend;
- quantity, color, size/capacity, included item, copy, image, ALT, and module order are checked;
- the first observation is labeled `FIRST_READBACK`, with expected and observed content IDs, device/viewport, field-level results, screenshot/DOM evidence, and time;
- propagation delay, `FETCH_BLOCKED`, `NOT_VISIBLE`, or one failed fetch is not treated as permanent absence or success;
- mismatches have an owner, an action, and a follow-up readback record.

Failure: restore the frozen previous content/application when safe and open a diagnostic case.

### G6 Experiment

- P0 content stable;
- platform eligibility and traffic checked;
- hypothesis, versions, primary metric, guardrails, and attribution limit pre-registered;
- run to the current platform's valid conclusion rule.

Failure: retain the truthful stable version; do not choose a winner from short-term noise.

## Conclusions

- `PASS`: all required evidence and acceptance checks for the stated scope passed.
- `CONDITIONAL_PASS`: useful strategy or production work may continue, but named facts/assets/publish actions remain blocked.
- `BLOCKED`: diagnosis is valid, but a required input or authority prevents the requested terminal action.
- `NO_VALID_CONCLUSION`: the target, evidence, or source integrity is insufficient even for a bounded conclusion.
- `ROLLBACK`: restore a frozen prior creative/application state because the changed state failed a defined guardrail.

Do not use `PASS` for a plan to imply publish approval.

## Baseline, Change Set, and rollback

Publish support requires:

- exact authorization for system, marketplace, locale, content IDs, children, allowed actions, and approved Change Set IDs;
- a frozen `baseline` containing current content IDs, status, locale, applications, copy, assets, ALT, and frontend evidence;
- a field-level or module-level `change_set` with before/after references, fact/claim/asset IDs, owners, approval, and application status;
- exact previous values or content/application state plus frozen or explicitly acknowledged parallel edits;
- a `rollback` record with trigger, responsible person, safe method, protected P0 facts, and verification steps;
- `live_readback` rows for every intended child and locale, starting with `FIRST_READBACK` and continuing until each mismatch is resolved or explicitly blocked;
- independent QA that does not rely only on the builder's self-check.

Never restore a known false P0 statement merely because it was in the old version. In that case, stop and create a corrected safe state.

## Experiment plan

Refresh current Manage Your Experiments eligibility and capabilities. Distinguish:

- factual repairs: apply directly after review;
- single-variable persuasion tests: suitable for attribution;
- multi-attribute package tests: valid for comparing complete versions, not for claiming which component caused the result;
- non-MYE before/after observation: descriptive only, not causal.

Prefer current official conversion/sales metrics as the primary result and add business guardrails appropriate to the product: returns, wrong size, incompatible model, missing accessory expectation, support/capacity complaint, negative review themes, or profit.

AI-shopping answer accuracy is semantic QA. It does not by itself prove traffic or business lift.

## Independent QA

For a major package, give an independent reviewer the Skill, the target request, and the minimum raw evidence, without supplying the intended answer. Ask it to test:

- whether observable sources were investigated before questions;
- whether the questions are batched, material, and non-repetitive;
- whether any target claim depends only on owner memory, competitor, VOC, or inference;
- whether module count/order is chosen rather than inherited;
- whether all applied children are represented;
- whether wrong-user and high-risk limits are visible before purchase;
- whether ALT, AI assets, mobile composition, and native text respect evidence;
- whether the conclusion and write authority are correctly bounded.

## Validator

Run:

```bash
python3 tools/aplus/scripts/validate_bundle.py /absolute/path/to/bundle.json
```

Exit code `0` means the bundle meets the encoded structural invariants. It does not validate live Amazon truth. Review errors first, then warnings, then perform human/source QA.

The validator preserves read-only legacy checks for v1.1/v1.2 and enforces the v1.3 contract below. It rejects unsupported enums, invalid scope chains, unavailable proving sources, consumer-ineligible claims, incomplete final assets, false atom coverage, invalid experiment attribution, and incomplete publish governance. An `ok: true` result proves only the encoded local invariants. It does **not** prove source truth, physical-product fidelity, current Amazon policy, legal sufficiency, real-world authorization, or live rendering.

`result_level` distinguishes template, invalid, legacy, current local-contract, and live-verification states as implemented by the current validator. The original project decision remains separately available as
`project_conclusion`; therefore a conditional project does not get mislabeled as live merely
because its local contract is valid.
# Bundle v1.3 and Handoff v1.1 result contract

This section defines the current interface with `$amazon-listing-catalog-workflow`. A+ v1.1/v1.2 remain read-only legacy inputs and do not silently gain v1.3 native coverage.

## Version behavior

- A+ v1.3 is the only current new-project contract and the only version that can use Handoff v1.1.
- A+ v1.1/v1.2 remain readable as `LEGACY_LOCAL_CONTRACT`; they cannot inherit v1.3 coverage, authorization, handoff, or live conclusions.
- Do not infer v1.3 Discovery, assertions, denominator atoms, or answer units from legacy native copy.
- Reject current-version blocks smuggled into a legacy bundle and reject unknown top-level extensions.
- Legacy Community Q&A modules, open conflicts, and forbidden algorithmic/fixed-threshold metrics remain invalid.
- Migration is explicit and non-destructive; it creates an unclosed v1.3 candidate plus report and invalidates old authorization, Handoff, and LIVE conclusions.

## `workflow_context`

Use `standalone` when this Skill owns Discovery. Use `embedded` only with a frozen parent Handoff v1.1. Record the parent bundle reference, accepted snapshot, acceptance time, accepting owner, execution boundary, and component result. The A+ boundary may never exceed the parent's and defaults to read-only.

Standalone v1.3 carries `discovery`, `decision_map.requirements`, `decision_denominator_snapshot`, `canonical_assertions`, real variant rows, research records, and the selected category method. Embedded v1.3 binds the parent-owned source objects by an immutable handoff and constructs only the delegated A+ projection.

The local `decision_denominator_snapshot` is a delegated projection with `status`, `source`, `source_hash`, `frozen_at`, exact `requirement_ids`, exact `variant_row_ids`, minimal five-field `atoms`, and `checksum`. In standalone mode `source=STANDALONE` and `source_hash` is empty. In embedded mode `source=PARENT_HANDOFF`; `source_hash` equals the parent handoff's full `decision_denominator_hash`, while the local checksum covers the delegated projection only. Do not confuse those two hashes.

## `enriched_content_handoff`

The embedded Handoff v1.1 binds:

- contract version, snapshot ID, parent project ID, parent bundle reference and SHA-256;
- marketplace, locale, Product Type, and complete application scope;
- real variant rows plus Discovery closure, PTD inventory, and decision-denominator hashes;
- the delegated enriched-content Canonical Assertions, decision requirements, and requirement atoms over `(requirement_id, marketplace, locale, variant_row_id)`; the `decision_denominator_hash` still binds the complete parent denominator;
- variant-row, Fact, Claim, blocked-Claim, Conflict, and Source references;
- requested A+ content types;
- assigned decision requirements with priority, scope, Fact/Claim references, native-answer and early-disclosure flags;
- capability snapshot references, prohibited actions, creation time, owner, and checksum.
- semantic lineage: content-addressed snapshot ID, positive `semantic_revision`,
  predecessor snapshot ID, and refreeze reason.

An embedded A+ bundle must reproduce the frozen child handoff exactly. The child validator validates the local handoff shape, immutable checksum, exact delegated requirements/atoms/assertions, denominator source hash, variants, and scope; it deliberately does not load or validate a parent file. The sole cross-Bundle coordinator recomputes the parent frozen projection, validates `parent_bundle_sha256`, and reconciles the parent and child. A syntactically plausible hash is therefore never a package PASS. The child must not add a child, Pack, color, size, locale, Fact, Claim, assertion, content type, or decision requirement. A handoff containing a blocked claim or open conflict cannot support final affected content.

Handoff states are `NOT_APPLICABLE`, `DRAFT`, `FROZEN`, `RESULT_RECEIVED`, `RECONCILIATION_REQUIRED`, and `SUPERSEDED`. Only FROZEN supports new embedded work. The Handoff v1.1 object uses an exact closed key set. Revision 1 has no predecessor/refreeze reason; a later semantic revision must name a distinct content-addressed predecessor and a non-empty reason. `snapshot_id` is itself content-addressed from the immutable handoff semantics. Lifecycle-only progress normalizes to the frozen checksum projection; a Fact, scope, PTD, assertion, requirement, atom, authority, or other frozen-semantic change invalidates it. A+ returns a local `component_result`; it cannot mutate or re-freeze the parent object.

### Parent coordination receipt boundary

A+ stops after returning `COMPONENT_PASS` or `DELTA_REQUIRED`; it never generates, acknowledges, stores, infers, reads, or writes a coordination receipt or JSONL ledger. Pure/no-ledger coordination can only form `PASS_CANDIDATE`, never terminal PASS. The controlled Parent package coordinator reads the current ledger head with `--receipt-ledger <path>`; it appends a receipt only when staff explicitly add `--record-receipt`, using a lock, append, and fsync. For the normal path, that controlled CLI records `AWAITING_RESULT_ACK` from `FROZEN + COMPONENT_PASS`. Only after the governed Parent lifecycle changes to `RESULT_RECEIVED` may it consume that exact current head and record the chained terminal PASS receipt.

For a delta path, the controlled coordinator records DELTA as the new ledger head, making an older AWAIT unusable. The old Snapshot becomes `SUPERSEDED`, `semantic_revision` increments by one, and a new `FROZEN` Snapshot must record a new AWAITING receipt chained to the DELTA head. The new `RESULT_RECEIVED` state then consumes that current head and records PASS. A+ does not perform any of these Parent lifecycle transitions. In locale-group mode, every member supplies its own ledger path and must already have a current terminal-PASS head exactly bound to that Parent, A+, and the bundled validators.

The ledger is local auditable evidence. `--record-receipt` is an explicit local evidence write, not an Amazon, Seller Central, ERP, network, or other external write. It is strictly separate from Amazon backend/readback evidence and is not a digital signature, trusted timestamp, Fact/Claim or evidence-truth proof, Amazon backend/platform acknowledgement, publication authorization, or evidence of `LIVE_MATCH`/`LIVE_PASS`. If an adversary can replace the entire ledger, Skill, or validators, use external trusted storage or signatures. Generated HTML never creates, saves, edits, or appends the ledger; when it says `NOT_INCLUDED`, staff must inspect Parent coordinator/ledger output rather than infer state.

## Capability snapshots

Separate current Amazon rules from account/module capability. A capability snapshot records marketplace, locale, account scope, content type, eligibility, available module types, backend field paths, field limits, Source IDs, retrieval time, status, owner, and checksum. A carrier must reference a current applicable snapshot and a field path available in that snapshot.

## Result blocks

### `carriers`

Use only `native_text`, `static_visual`, `motion_video`, `interactive_detail`, `structured_comparison`, or `brand_authored_qa`. Record module, backend field path, capability snapshot, decision requirements, scope, Fact/Claim references, answer units, assets, mobile behavior, role, content state, QA state, and owner.

### `decision_answer_units`

Record requirement atom, priority, buyer question, primary carrier, module, native field path, approved text, variant-row scope, Canonical Assertion, Fact/Claim references, early-disclosure flag, content state, QA state, and owner. The normalized approved text must be an exact excerpt of the resolved module field; semantic similarity or a detached answer record does not pass.

Each answer unit names `requirement_atom_id`, `variant_row_id`, and `canonical_assertion_ids`. Carriers and assets also carry exact variant and assertion references. Evidence remains on one chain: answer ⊆ carrier ⊆ module ⊆ delegated requirement/handoff, with publishable assertions and exact real-variant scope.

### `coverage_summary`

This is a derived summary over real requirement atoms: status, P0 required count, P0 pass count, and exact gap atom IDs. The validator recomputes it, rejects a zero denominator at Decision Freeze or later, and ignores manual Gate claims. Do not add total-word, character-volume, keyword-density, COSMO, Alexa, CDQ, or timing thresholds.

### `component_result`

The closed statuses are `NOT_EVALUATED`, `IN_PROGRESS`, `COMPONENT_PASS`, `DELTA_REQUIRED`, `BLOCKED`, and `CONDITIONAL`. Record exact `gap_atom_ids`, open delta IDs, owner, `page_pass_implied: false`, and `publication_authorized: false`. `IN_PROGRESS` covers unfinished local construction or QA; `DELTA_REQUIRED` is reserved for current gap atoms fully mapped to OPEN parent-evidence requests. `COMPONENT_PASS` means only that the delegated A+ component contract is complete; it is never the whole Listing result and never grants write authority.

### `delta_evidence_requests`

Each request records a question, affected requirement atoms/Facts/Claims/assertions/modules, decisive evidence, `gap_type`, owner, and state. An OPEN embedded request uses `gap_type=PARENT_EVIDENCE`, names at least one current gap atom, and carries exact lineage: snapshot ID, parent bundle SHA-256, Discovery closure hash, PTD inventory hash, decision-denominator hash, and handoff checksum. It is returned to the parent; it does not create or modify a publishable Fact or Claim inside A+. A stale lineage, a passed/nonexistent atom, or a local construction/QA gap cannot produce `DELTA_REQUIRED`. A material delta changes the parent to `RECONCILIATION_REQUIRED`; the old snapshot becomes `SUPERSEDED` before a replacement is frozen.

## Coverage validation

For every Handoff requirement atom assigned to A+:

1. Resolve the requirement to a decision answer unit.
2. Bind a final, QA-passed native carrier when `native_answer_required=true`.
3. Verify answer, carrier, module, asset, and application scopes contain that exact real variant row and are contained by the Handoff and parent assertion/fact/claim scopes.
4. Enforce `answer Fact/Claim refs ⊆ carrier refs ⊆ module refs`, with the answer refs also
   contained by the assigned handoff requirement.
5. Reject final answers that use HOLD/CONFLICT/PROHIBITED evidence.
6. Verify approved answer text actually exists in the bound native field and preserves the Canonical Assertion.
7. Derive `SUPPORTED`, `PARTIAL`, `HOLD`, or `CONFLICT` without a word-count score.

`static_visual`, ALT, video, interaction, comparison, or brand-authored Q&A cannot alone satisfy an early P0 native disclosure. Community Q&A must never enter the writable carrier list.

## Publish and readback boundary

Embedded handoff is content-planning authority, not Seller Central write authority. In v1.3, `maximum_output` is `strategy_dependency_only`, `candidate_package`, `preflight_package`, or `publish_support_package`. `strategy_dependency_only` carries no module, asset, answer-unit, carrier, wireframe, copy, image, or ALT candidate. A+ may return a local candidate, preflight package, or explicitly authorized publish-support package only up to the parent `maximum_output`.

For v1.3 publish support, a variant needs the content ID(s) actually in the authorized change set; do not mechanically require both an A+ content ID and a Brand Story ID. An embedded bundle cannot exceed parent `maximum_output`, bypass `prohibited_actions`, or use a read-only parent boundary for publish support. Authorization must be current, bind the actual system and Change Set, and rely on usable authorized evidence.

Backend Saved/Submitted/Accepted/Approved/Published does not equal front-end PASS. Preserve the first child/locale observation and require live matching readback for each intended target. A local file labeled `PUBLIC_OBSERVED` is not sufficient live evidence; the record must bind a buyer-visible Amazon locator, capture metadata, checksum/evidence, and independent readback state.

## v1.3 delivery, migration, and HTML

The current A+ v1.3 delivery includes the authority boundary, source/fetch register, Discovery closure or frozen parent Handoff, Product Truth/Claims, real variants, decision denominator and Canonical Assertions, competitor/VOC findings, positioning, capability snapshot, modules/carriers/answer units, asset manifest, delta evidence requests, QA, and any separately authorized publication/readback records.

Use the shipped CLI help for exact optional flags:

```bash
python3 tools/aplus/scripts/validate_bundle.py /absolute/path/to/aplus-bundle.json
python3 tools/aplus/scripts/migrate_aplus_bundle.py /absolute/path/to/legacy-aplus.json --output /absolute/path/to/aplus-v1.3.json
python3 tools/aplus/scripts/render_aplus_report.py /absolute/path/to/validated-v1.3.json --output /absolute/path/to/aplus-report.html
```

Migration never overwrites input, output, or its migration report. The migrated bundle uses `MIGRATED_NEEDS_REVIEW`, keeps unresolved Discovery, evidence, assertions, decisions, capability, and QA states open, preserves unknown legacy extensions in the output and migration report, and does not preserve legacy write authority, Handoff, or LIVE conclusions. An embedded legacy bundle cannot become embedded v1.3 until its current parent v1.1 freezes a new Handoff. The shipped versioned v1.2 scaffold remains a read-only `TEMPLATE_ONLY` compatibility fixture.

JSON is the only source of truth. The HTML renderer refuses a structurally invalid bundle but may render a contract-valid `BLOCKED` or `CONDITIONAL` project with conspicuous blockers. For the same canonical Bundle and renderer version it produces byte-stable, local, full-width output, escapes untrusted content, allows only safe URL protocols, and contains no persistence, editable product facts, import/export, or online action control.

For v1.3, an unknown root key, a missing required contract block, a wrong root
container type, a duplicate record ID, or a malformed closed category adapter
sets `structural_valid=false`. Business blockers with intact structure remain
renderable. Validator `errors` and `warnings` are globally deduplicated and
sorted so identical JSON produces identical diagnostics across Python hash
seeds.

The staff report exposes version and hash, scope, evidence, Owner, acceptance condition, blockers, and status badges that distinguish official rule, account observation, target-product evidence, internal heuristic, community hypothesis, and rejected normative rule. It is a reading artifact, not proof of Seller Central publication.
