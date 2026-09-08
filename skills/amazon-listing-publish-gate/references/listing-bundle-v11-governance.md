# Listing Bundle v1.1: catalog, field, and publication governance

Use this reference for formal Bundle identity, Product Type, schema/PTD, field paths, facts, variants and publication state. Candidate/field-work restrictions here mean formal records. Separate supported INTERNAL_PROTOTYPE / NOT_FOR_UPLOAD expressions follow the entrypoint's working-lane rules and cannot claim account capabilities, coverage or publication readiness.

## 1. Authority and execution boundary

The bundle starts in `read_only`. The four closed execution boundaries are:

- `read_only`: inspect and report only;
- `local_candidate`: create local candidates and staff artifacts only;
- `authorized_submission`: submit only a separately authorized, exact change set;
- `rollback_only`: restore the captured baseline after a separately authorized rollback decision.

An instruction to “optimize,” “prepare,” or “make a manual” is not submission authority. Authorization must bind account/seller scope, marketplace, ASINs, fields, payload or content IDs, operator, timestamp, and expiry or one-shot limit.

For `authorized_submission`, the validator also binds authorized systems and data planes,
target IDs, exact Change Set IDs, canonical baseline and Change Set hashes, the authorized
action, attempt limit, authorization evidence, and a current validity window. A nonempty
authorization object is not authority by itself. Expired, mismatched, or unverifiable
authorization blocks submission.

## 2. Identity gate

Freeze all of the following before field work:

- marketplace and locale;
- seller/account scope;
- identifier type and identifier;
- parent ASIN, intended child ASINs, and exclusion list;
- parentage level and variation theme;
- pack count, color, size, style, and any other differentiating dimensions;
- Product Type and the evidence used to resolve it.

A URL parameter, selected swatch, filename, screenshot caption, or external ERP label is not enough on its own to bind a child. Conflicting identities block final copy.

## 3. Product Type and rule snapshot

Resolve current requirements from the actual account/marketplace/category context. A usable rule snapshot records:

- marketplace, locale, seller scope, Product Type, parentage level;
- data-plane and schema or template version;
- required, optional, conditional, enumerated, and prohibited fields;
- limits, allowed values, dependency rules, and visibility;
- source references, retrieval time, status, checksum, and refresh trigger.

`CURRENT` is an evidence state, not a promise that a rule never changes. Refresh after template/API/UI/version changes, category remapping, validation errors, or before authorized submission.

Use current Amazon Product Type Definitions documentation as the model for field conditionality, but use the approved project evidence route: read-only Lingxing mapping plus applicable Seller Central screenshots/exports. Do not develop or assume SP-API credentials. If account evidence does not expose the complete field inventory, mark it `PARTIAL`; do not infer that an unseen field is absent.

Refresh these official routes when relevant:

- Product Type Definitions: `https://developer-docs.amazon.com/sp-api/docs/product-type-definitions-api-v2020-09-01-reference`
- Manage product listings: `https://developer-docs.amazon.com/sp-api/docs/manage-product-listings-guide`
- 2026 Item name and Item highlights announcement: `https://sellercentral.amazon.com/seller-forums/discussions/t/145b6d0f-999c-4555-896c-c694bda2e470`
- Item highlights implementation Q&A: `https://sellercentral.amazon.com/seller-forums/discussions/t/e590b18e-8710-4263-a0d8-4aeb66700ba0`

The 2026 public announcement described a 75-character Item name and 125-character Item highlights split for applicable non-media products, with both used as search inputs. Treat that as a dated general rule, not proof that the field exists, is editable, or has the same constraint for this account, marketplace, Product Type, parentage level, or child. Resolve the actual field key and capability from current applicable evidence.

“Flat Profile” has no universal canonical meaning. Resolve it to the actual current surface: Seller Central UI, category-specific spreadsheet, Listings Items API, upload feed, or another named data plane. Do not silently substitute a retired legacy flat/XML feed.

## 4. Data planes

Keep these planes distinct:

| Plane | Typical content | Authority/readback |
|---|---|---|
| `catalog_contribution` | product facts and descriptive attributes | Amazon catalog contribution or authoritative backend |
| `seller_listing` | seller-scoped listing fields | current Seller Central/API response |
| `relationship` | parent/child theme and membership | current relationship data |
| `offer` | price, quantity, fulfillment | out of scope for this Skill |
| `enriched_content` | A+, Premium A+, Brand Story | A+ Manager/backend plus front-end readback |
| `external_tool` | Lingxing/ERP, research, reports | supporting operational mirror only unless independently reconciled and read back |

Never let an external tool’s “success” substitute for Amazon’s authoritative state.

## 5. Field-resolution records

Every consumer or backend candidate must point to a field-resolution record with:

- semantic role, canonical backend key, current UI label, and data plane;
- surface and buyer visibility;
- existence, editability, applicability, requirement state, and allowed values;
- scope and rule-snapshot references;
- resolution status and owner.

Semantic roles include `ITEM_NAME`, `ITEM_HIGHLIGHTS`, bullets, description, material, fit, care, size-chart value, media text, or search terms. They are not backend keys. `ITEM_HIGHLIGHTS` must bind a current capability/rule record and real field resolution. Never accept a generic `subtitle`, `item_subtitle`, or look-alike label as an alias. A subtitle-like message without a verified field is `NOT_AVAILABLE`.

Candidates cannot target unresolved, unavailable, inapplicable, prohibited, or non-editable fields. Required and triggered Conditional fields must each have a resolution row. Unknown Conditional trigger state blocks PTD closure. A P0-relevant Optional field must be resolved or carry evidence that it is unavailable for the applicable scope.

For P0 primary coverage, `canonical_key` is authoritative and must resolve through the validator's closed `canonical_key -> semantic_role -> surface/data_plane/carrier` contract. Relabeling a field never changes its legal carrier class. Current supported mappings include native Item name, Item highlights, bullets, description, and enumerated structured/size attributes. An unknown PTD key may be documented and drafted, but cannot become a P0 primary carrier until the closed contract is extended from current rule/account evidence.

These objects are always supporting-only for P0, regardless of claimed visibility or surface: `COMMUNITY_QA`, `ALT_METADATA`, `BACKEND_TERMS`, Community Q&A canonical keys, image ALT keys, generic keyword/search-term keys, and their aliases. Community Q&A is read-only evidence; it is not a seller-authored listing Field Resolution. The Parent validator and the cross-bundle coordinator both enforce this mapping independently.

## 6. Truth, claims, and conflicts

Use one parent ledger with the same evidence rigor as the A+ child:

- `facts`: verifiable product/catalog facts with evidence and precise application scope;
- `claims`: intended consumer statements linked to facts and a support status;
- `conflicts`: incompatible evidence, identity, variant, field, or publication states.

Each Fact records evidence strength `E0`–`E4`, proving Source IDs, exact source and application scope, what the source proves and cannot prove, allowed expression, prohibited derivation, and refresh condition. Facts and claims entering final copy must be `VERIFIED`/`SUPPORTED` and `PUBLISHABLE`. `HOLD`, `CONFLICT`, unsupported, inferred-only, stale, or materially accepted-risk rows must not be converted to confident consumer text.

Claims such as medical benefit, environmental savings, performance, compatibility, sizing range, support level, material composition, or “fits all” need evidence appropriate to their specificity. A rough estimate must remain clearly labeled and cannot become a precise promise.

## 7. Variant topology and pack isolation

Model each sellable child with its child ASIN, parent, differentiating dimensions, pack count, included items, evidence references, and status. Application scope is an intersection, not a loose tag.

Block when:

- a 2-pack statement is applied to a 3-pack child or vice versa;
- one color/size/material fact is reused outside its verified scope;
- a parent-level candidate assumes all children share an unverified attribute;
- the proposed variation theme conflicts with the current Product Type;
- a child is absent from the frozen intended scope.

## 8. Publication package

Before any authorized submission, capture:

- exact authorization record;
- authoritative baseline per target field/child;
- field-level change set and content IDs where applicable;
- expected state and success criteria;
- rollback values and operator steps;
- ambiguity/reconciliation procedure.

Every baseline, Change Set, and rollback row is field-level and target-specific. Baseline
and Change Set rows bind the same field resolution, authorized data plane, target and
system; their canonical collection hashes are included in the authorization. A rollback
row links the exact Change Set and baseline and must bind the same target/field/plane/system.
A baseline known to contain a false P0 answer, an unresolved conflict, or unsafe content is
never a legal rollback target.

The v1.1 operational-row contract is intentionally closed:

| Object | Required binding |
|---|---|
| baseline | row ID, target, field resolution, data plane, system, before value, capture time, Source IDs, row SHA256 |
| Change Set | row ID, target, field resolution, data plane, system, after value, Fact/Claim IDs, approval identity/time, row SHA256 |
| rollback | row ID, Change Set ID, baseline ID, same target/field/plane/system, rollback value, triggers, owner, row SHA256 |
| live readback | child, state, pass flag, observation time, locator, expected/observed values, usable Source ID |

The authorization's baseline and Change Set hashes are recomputed from the canonical row
collections. Per-row hashes are also recomputed. Arbitrary nonempty SHA-like strings do not
pass.

If submission response is unknown or ambiguous, stop and read back before retrying. Do not create duplicate contributions or content because a network response was unclear.

## 9. Readback state machine

Use distinct states:

1. `NOT_SUBMITTED`
2. `SUBMITTED`
3. `ACCEPTED_BACKEND`
4. `REJECTED_BACKEND`
5. `LIVE_MATCH`
6. `LIVE_MISMATCH`
7. `UNKNOWN`

Only `LIVE_MATCH` on every intended child can support `LIVE_PASS`. Backend acceptance, a green UI banner, or an external connector response cannot.

Each `LIVE_MATCH` is one unique terminal row per intended child, timestamped and
evidence-linked. For a one-field change its expected/observed value is that field value; for
multiple fields it is a canonical JSON object keyed by `field_resolution_id`. The normalized
expected and observed payloads must agree. Read back the exact affected child pages,
buyer-visible fields, variation selection, A+ placement if applicable, and timestamp.
Preserve the first observation and every mismatch; do not auto-retry an ambiguous write.
Trigger rollback or escalation only within the authorized plan.

The machine validator can prove contract consistency, not that a screenshot, DOM capture,
authorization source, or Amazon response is genuine. Report local validation separately
from `LIVE_PASS`; the latter still requires authoritative backend and buyer-visible evidence.

## 10. Version, migration, coordination, and report behavior

Listing Bundle v1.1 is the current contract. Parent v1.0 remains readable only as `LEGACY_LOCAL_CONTRACT`; it cannot receive v1.1 discovery, coverage, handoff, publication, or live status by implication.

Migration is explicit and non-destructive. `tools/listing/scripts/migrate_listing_bundle.py` writes a new v1.1 bundle and migration report; it never overwrites the input, invents Facts, closes Discovery/PTD/Assertion gaps, preserves an old live verdict, or upgrades old authorization. A migrated package must be re-evidenced and re-frozen before any terminal conclusion.

Use the shipped CLI help for exact optional flags:

```bash
python3 tools/listing/scripts/validate_listing_bundle.py /absolute/path/to/listing-bundle.json
python3 tools/listing/scripts/migrate_listing_bundle.py /absolute/path/to/v1.0.json --output /absolute/path/to/v1.1.json
python3 tools/listing/scripts/render_listing_report.py /absolute/path/to/validated-v1.1.json --output /absolute/path/to/report.html
python3 tools/listing/scripts/validate_listing_package.py /absolute/path/to/listing-v1.1.json /absolute/path/to/aplus-v1.3.json
python3 tools/listing/scripts/validate_listing_package.py /absolute/path/to/frozen-listing-v1.1.json /absolute/path/to/aplus-v1.3.json --receipt-ledger /absolute/path/to/coordination.jsonl --record-receipt
python3 tools/listing/scripts/validate_listing_package.py /absolute/path/to/result-received-listing-v1.1.json /absolute/path/to/aplus-v1.3.json --receipt-ledger /absolute/path/to/coordination.jsonl --record-receipt
python3 tools/listing/scripts/validate_listing_package.py --group-manifest /absolute/path/to/listing-locale-group.json
```

When both parent and A+ bundles exist, use `tools/listing/scripts/validate_listing_package.py` as the only cross-bundle coordinator. It validates each bundle with its own validator, binds each validator report to the exact parsed input hash, recomputes canonical hashes, checks the current Handoff state and result, and derives page-level coverage. Parent and child validators must not dynamically import one another.

The first controlled command on a `FROZEN + COMPONENT_PASS` pair records `AWAITING_RESULT_ACK` in the explicit JSONL ledger. After the governed Parent acknowledgement changes only the lifecycle state to `RESULT_RECEIVED`, the second controlled command consumes the current AWAIT head and records terminal PASS. A DELTA advances the same head, making an earlier AWAIT unusable; it must chain through `SUPERSEDED -> semantic_revision + 1 -> new FROZEN -> new AWAITING receipt`. Repeated consumption, fork, rollback, cross-project reuse, a partial final line, or a non-current head fails closed.

The pure API and legacy `--prior-receipt` option remain useful for structural/candidate review but never return terminal PASS. Only the exact bundled-validator CLI plus a valid current ledger head may confirm PASS. `--receipt-ledger` alone reads and never creates or changes the path. `--record-receipt` performs the sole allowed local evidence mutation using an exclusive lock, append, and fsync; the JSON output records `local_evidence_write`. This does not expand `execution_boundary=read_only` or authorize an Amazon, Seller Central, ERP, network, or other external write.

The optional `--group-manifest` mode is also owned by that coordinator. It accepts no pair positionals, global ledger, or recording flag in the same invocation. Paths are resolved relative to the manifest, every referenced file must be unique after symlink resolution, and every member is run through both bundled component-validator CLIs plus ordinary pair confirmation before cross-locale comparison. The closed manifest contains only `contract_version`, `group_id`, `marketplace`, and two or more uniquely keyed locale members with `locale`, Parent path, A+ path, and that pair's `coordination_ledger` path. Each current ledger head must already be terminal PASS and exactly bind the loaded Parent/A+ inputs. Any supplied self-attested hash, PASS flag, authorization, or live claim invalidates the manifest.

The pure semantic comparison function never produces `GROUP_PASS`, even if a caller inserts a fake or stale `pair_result`. It reports only semantic match/fail/invalid and remains fail-closed. `GROUP_PASS` exists only at the controlled exact-file entrypoint after real component validation, terminal pair PASS, exact input-hash binding, terminal receipt validation, and semantic match for every member.

The renderer accepts a structurally valid current Bundle. It may render a business `BLOCKED` or `CONDITIONAL` report, but refuses structurally invalid input. Output is deterministic, local, full-width, and read-only; JSON remains the source of truth. A human-facing report may display ledger version, head receipt hash/result, input hashes, and `local_evidence_write`, but must not reinterpret those diagnostics as Amazon acknowledgement, publication authority, or live evidence. The report escapes untrusted content, allows only safe URL schemes, and contains no persistence, editing, import/export, or submission control.

`gate_reviews` retain reviewer, evidence, and findings; they do not store or override machine conclusions. Do not add a user-editable `derived_gates` object to the Bundle. The validator computes `derived_stage` and `derived_gates`, and the renderer consumes that validation result.
