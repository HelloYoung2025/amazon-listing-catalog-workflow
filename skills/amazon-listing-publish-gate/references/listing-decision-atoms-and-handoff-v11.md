# Listing Bundle v1.1: decisions, surfaces, construction, and A+ handoff

This reference governs formal Bundle construction after Discovery closure. Earlier research, questions and supported INTERNAL_PROTOTYPE / NOT_FOR_UPLOAD expressions are separate working drafts governed by the discovery and positioning references.

## 1. Freeze the decision denominator

Express buyer needs as answerable questions. Each requirement records the question, intent, `P0/P1/P2` priority, real variant scope, Fact/Claim links, early-disclosure requirement, accepted primary surfaces, and evidence gap.

Use return risk, misuse or compliance risk, decision friction, repeated VOC, verified differentiation, and evidence strength. Search volume alone does not set priority.

Before `DECISION_FROZEN`, create `decision_denominator_snapshot` from the frozen requirements and real variant rows. Expand only existing atoms:

`(requirement_id, marketplace, locale, variant_row_id)`

The variant row already contains child, pack, color, size, and other dimensions. Do not create a Cartesian product of independent arrays. At `DECISION_FROZEN` or later, P0 required count must be greater than zero.

Typical P0 questions include exact identity and contents, selection/fit/compatibility, material or care facts likely to cause return, safety or regulated limits, and a child-specific difference that changes the purchase.

## 2. Freeze canonical assertions

A `canonical_assertion` is the smallest stable product answer that may be expressed across multiple page surfaces. It binds:

- assertion ID and normalized meaning;
- exact marketplace/locale/variant scope;
- Fact and Claim IDs;
- required boundary or early disclosure;
- allowed paraphrases and prohibited expansion;
- status and owner.

Locale-specific wording may vary, but it must preserve the same assertion and cannot widen scope, certainty, performance, or inclusion. Where two surfaces intentionally differ, record the reason; otherwise title, highlights, bullets, attributes, size/fit, media, A+, and comparison content must not contradict the assertion.

## 3. PTD field closure and surfaces

Close the current `ptd_field_inventory` before construction. Every Required and triggered Conditional field is resolved. Unknown Conditional trigger state blocks closure. A P0-relevant Optional field is either resolved or evidenced unavailable.

Closed planning surfaces:

- `core_copy`: Item name, verified Item highlights, supported bullets and descriptions;
- `catalog_attributes`: structured buyer-visible attributes;
- `size_chart`: applicable Amazon size/fit content;
- `media`: images, video, visible text, and allowed metadata;
- `backend_search_terms`: hidden discovery metadata;
- `enriched_content`: Basic/Premium A+ and Brand Story.

A surface assignment is a plan, not proof of coverage.

Check decisive field/module and asset feasibility before committing the chosen route's formal allocation. Unknown A+ capability references may remain empty under the existing contract, but this conveys no capability PASS and may leave construction blocked. Keep the conditional buying reason, selection guidance and proof movement from the working comparison/Answer Map when compiling existing requirements and fields; do not add schema keys or shrink the complete P0 denominator.

## 4. Construct top-down visible copy

Formal field candidates, imagery specifications and Answer Units require Product Truth, Round 2, Product Intent Brief, One-Bet selection, Decision and PTD closure. Supported internal route expressions and A+ opening concepts may precede route selection outside the Bundle; they cannot claim field availability or upload readiness. After formal closure:

1. **Item name:** brand and the most important product/variation identity allowed by the current rule and field resolution.
2. **Item highlights:** only when a current real field is resolved; use the applicable remaining product detail, material, use case, or decision answer without duplicating or contradicting Item name.
3. **Bullets:** answer the highest-priority remaining buyer questions in natural language.
4. **Description/Details/Size:** place deeper native answers and structured selection information where supported.
5. **Media/ALT:** demonstrate visible proof and reading order; ALT describes what is visible and never introduces a hidden claim.
6. **Backend terms:** add relevant discoverability language without using them as visible P0 answers.
7. **A+/Brand Story:** deepen decisions, proof, comparison, selection, use, and brand context without repairing a missing early disclosure.

Do not impose keyword density, total words, fixed intent count, fixed repetition count, a semantic score, or a COSMO/Alexa traffic target. Current Amazon rule snapshots govern field constraints; internal heuristics only help create candidates.

## 5. Atomic answer and Coverage Gate

Every non-delegated `decision_answer_unit` binds one requirement atom to:

- a real Field Resolution;
- one FINAL candidate with `qa_status=PASS`;
- answer text actually present in that candidate;
- Canonical Assertion, Fact, and Claim references;
- exact variant scope;
- carrier role and evidence status.

The same Field Resolution and variant row may have at most one effective FINAL candidate. A candidate that is absent, on HOLD, unsupported, scoped to only part of the atom, or semantically unrelated to the requirement cannot pass.

Acceptable P0 primary carriers are native visible fields and buyer-visible structured attributes/size content. ALT, image-only text, video-only content, backend terms, Community Q&A, and decorative/proof-only A+ are supporting-only. An early-disclosure P0 must be answered above or near the buying controls where a supported field permits; A+ may reinforce it.

Coverage is derived from the atoms and valid answer units. Ignore self-reported surface status, manual Gate rows, total copy length, keyword density, 500-word rules, 90% targets, CDQ weights, COSMO/Alexa scores, or fixed timing claims.

An atom is A+-delegated only when its parent requirement is assigned to `enriched_content` and its exact surface assignment is `A_PLUS_NATIVE_PENDING`. At `HANDOFF_READY`, that delegated atom does not need a parent Field Candidate or parent Answer Unit. It instead needs a fully frozen requirement, variant, assertion, Fact/Claim evidence chain, and handoff entry. Every other atom still needs exactly one parent-native PASS unit. A parent-only validator may establish `HANDOFF_READY`, but cannot combine the delegated result into whole-page `PACKAGE_PASS`; only the cross-bundle coordinator can do that after an A+ `COMPONENT_PASS`.

## 6. Handoff v1.1 state machine

At `HANDOFF_READY`, create one parent-owned `enriched_content_handoff`:

`DRAFT -> FROZEN -> RESULT_RECEIVED`

If A+ discovers a material evidence gap:

`RECONCILIATION_REQUIRED -> parent updates evidence/truth/decisions -> old snapshot SUPERSEDED -> new FROZEN`

A frozen handoff contains:

- snapshot ID, parent version/path/hash, canonical checksum, creation time, and owner;
- marketplace, locale, Product Type, real variant rows, parent/child/Pack scope;
- Discovery closure hash, PTD inventory hash, and the hash of the **complete parent P0 denominator**;
- only the Canonical Assertions, real variants, requirement atoms, and Fact/Claim/Conflict references delegated to A+;
- only A+-assigned questions, priority, exact scope, native-answer and early-disclosure rules;
- upstream primary-carrier reference for every early-disclosure requirement;
- A+ capability/module snapshot references when current evidence is available; an empty list is allowed and conveys no capability claim;
- maximum output and prohibited actions.

`handoff.decision_requirements` and `handoff.requirement_atoms` are therefore a strict enriched-content subset of the complete frozen parent denominator, never a second denominator and never an instruction for A+ to repeat already-closed core-copy answers. The complete denominator hash remains unchanged so the coordinator can prove that local PASS atoms plus delegated A+ PASS atoms cover the same original P0 set.

The parent need not be terminal PASS to freeze at `HANDOFF_READY`; this avoids a circular dependency. A+ returns `COMPONENT_PASS` or `DELTA_REQUIRED`. The cross-bundle coordinator verifies the parent hash, immutable handoff payload, A+ result, variant containment, and final page coverage before a parent terminal result. A pure lifecycle transition from `FROZEN` to `RESULT_RECEIVED`, `RECONCILIATION_REQUIRED`, or `SUPERSEDED` does not change the immutable payload hash. The first freeze uses `semantic_revision=1` with empty predecessor/reason. A semantic refreeze increments the positive revision, binds the prior content-addressed `HO-...` snapshot in `predecessor_snapshot_id`, records a non-empty `refreeze_reason`, and receives a new content-addressed snapshot ID. Any change to scope, facts, assertions, PTD, denominator, delegated atoms, or frozen decision text without that new snapshot fails closed.

Every semantic revision after 1 also carries exactly one immediate-predecessor record in `lineage_registry`. The record is closed and content-addressed: prior snapshot ID, prior Handoff checksum, prior parent-bundle hash, `SUPERSEDED` state, exact successor snapshot, prior revision, creation/supersession times, the full immutable prior Handoff projection, and its record checksum. The prior revision must equal current revision minus one; the successor must equal the current snapshot; timestamps must be ordered; and the embedded prior projection must reproduce the old snapshot and checksum. Its own registry recursively proves earlier revisions. A random predecessor string, skipped revision, non-superseded record, mismatched successor, altered prior payload, or checksum mismatch blocks Parent, A+, and coordinator validation. This establishes deterministic package lineage; it is not a claim that local JSON proves the authenticity of an external Amazon event.

### Controlled monotonic coordination ledger

Handoff lineage proves semantic refreezes; a separate append-only JSONL ledger preserves the content-addressed local result sequence. The coordinator, not staff or either component Skill, generates these closed receipts:

1. `FROZEN + COMPONENT_PASS` returns `AWAITING_RESULT_ACK` and an AWAITING receipt.
2. The controlled CLI records that AWAIT receipt as the current ledger head. `RESULT_RECEIVED` can reach package `PASS` only by consuming that exact current head and recording a terminal PASS receipt chained to it.
3. `RECONCILIATION_REQUIRED + DELTA_REQUIRED` returns a DELTA receipt containing the exact delta fingerprint.
4. A DELTA receipt can never precede PASS on the same snapshot/revision. The old handoff must be `SUPERSEDED`; the new handoff must use the old snapshot as predecessor, increment the revision by one, and enter `FROZEN`. Its AWAITING receipt chains to the old DELTA receipt before a later RESULT_RECEIVED acknowledgement.

Every receipt binds project and chain IDs, exact parsed Parent and A+ input hashes, bundled validator hashes, frozen snapshot, semantic revision, result, delta fingerprint, previous receipt hash, and deterministic time basis. The ledger validates every line from genesis to current head. Missing, partial, stale, cross-member, edited, forked, rolled-back, repeated, or self-inconsistent transitions fail closed. A component-validator report is accepted only when the coordinator binds it to the exact input hash it validated.

The pure coordinator API and legacy sidecar mode may emit `PASS_CANDIDATE` or `TRANSITION_LEDGER_REQUIRED`, but never terminal PASS. Only the controlled CLI using the bundled validator identities and current ledger head may record or confirm terminal PASS. `--receipt-ledger` reads; `--record-receipt` explicitly authorizes only the local append, lock, fsync, and audit update. Without `--record-receipt`, no ledger is created or changed. Output reports `local_evidence_write`; the external execution boundary remains read-only.

This local ledger detects ordinary process replay, accidental deletion, forks, rollback, and inconsistent package assembly. It is not a digital signature, trusted timestamp, proof of operator identity, Fact/Claim or evidence-truth proof, Amazon backend/platform acknowledgement, publication authorization, or evidence of `LIVE_MATCH`/`LIVE_PASS`. An attacker able to replace the entire ledger, Skill, or validator can replace this evidence; use external signing or trusted storage when that adversary is in scope.

## 7. Embedded A+ boundary

In embedded mode, `$amazon-premium-aplus-planner` accepts the frozen contract and must not:

- repeat the product interview or create another truth ledger;
- change facts, claims, conflicts, assertions, decisions, or Product Type;
- add children, packs, marketplaces, or locales;
- mutate or re-freeze the parent snapshot;
- exceed the parent execution boundary or maximum output.

A+ returns modules with actual backend field paths, native answer units, other carriers, asset/ALT metadata, exact application scope, QA state, blockers, and `delta_evidence_requests`. Community Q&A remains read-only; Premium A+ brand-authored Q&A is a separate carrier.

The old handoff becomes unusable after any relevant parent evidence, scope, assertion, decision, PTD, or capability change. Reconciliation occurs in the parent; never patch the frozen object in place.

A capability-only child blocker returns to the Parent as an ordinary report naming actual capability evidence, affected delegated atoms and possible remedies, not as a `PARENT_EVIDENCE` delta. Before an AWAIT receipt, continue local construction only if a supported option preserves the frozen semantics and scope; after AWAIT, changed A+ inputs cannot consume the old receipt. The current controlled ledger admits a semantic refreeze only after a genuine DELTA predecessor; if a needed allocation change has no such legal path, retain BLOCKED and report the contract limitation rather than inventing a delta, resetting the ledger or bypassing it with another chain. This clarification creates no state, receipt or permission.

## 8. Multi-locale group runtime

Locale groups are optional and run only after each locale has its own valid Listing 1.1 parent, embedded A+ 1.3 child, and Handoff 1.1. Do not put multiple locales into one member Bundle and do not let a group manifest certify its inputs.

For every manifest member, the controlled file-based coordinator executes the bundled parent Validator and A+ Validator, then confirms ordinary pair coordination against that member's current receipt-ledger head. The head must be a terminal PASS exactly bound to the Parent and A+ full input hashes and bundled validator identities. One failing member stops the group with `GROUP_MEMBER_BLOCKED`. A valid group requires at least two unique locale members in one marketplace and compares the same assertion-family IDs across all members:

- canonical parent and A+ statement stays unchanged;
- Fact/Claim IDs and governed semantic content stay unchanged;
- parent/A+ application scopes, requirement scopes, atom identities, and real variant rows are exact-equal after removing only locale identity;
- every assertion has exactly one expression for the member locale with the same Fact/Claim chain;
- only `canonical_assertions[].locale_expressions[].text` may differ as localized wording.

The pure `listing_locale_group` layer only returns `SEMANTIC_MATCH`, `SEMANTIC_FAIL`, or `SEMANTIC_INVALID`; it never trusts a caller-provided pair result and never grants `GROUP_PASS`. Only the controlled exact-file entrypoint may convert a semantic match into `GROUP_PASS`, after both bundled component validators, the pair coordinator, exact Parent/A+ input hashes, and each ledger's current terminal PASS head all bind.

Localized wording may not enlarge product truth, certainty, included items, performance, child/Pack/color/size coverage, or buyer promise. The result remains `read_only`; controlled `GROUP_PASS` is a deterministic local package result, not publication authority or evidence of Amazon live state.
