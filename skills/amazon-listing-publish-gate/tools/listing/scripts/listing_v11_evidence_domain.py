#!/usr/bin/env python3
"""Pure Evidence/Identity/Rules/Truth phase for Listing Bundle v1.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AbstractSet

from listing_v11_domains import current_rule_has_strong_source
from listing_v11_evidence import (
    proving_sources_cover,
    source_can_prove_account_field,
    source_context_matches,
    source_covers,
    variant_scope,
)
from listing_v11_field_contract import is_community_qa_field
from listing_v11_phase import (
    DATA_PLANES,
    EVIDENCE_LEVELS,
    PhaseDelta,
    SOURCE_STATUSES,
    SURFACES,
    _err,
    _index,
    _is_fake_subtitle,
    _isoish,
    _nonempty,
    _obj_list,
    _refs,
    _scope_sets,
    _unique_strings,
    _validate_app_scope,
)


@dataclass(frozen=True)
class EvidenceReport:
    delta: PhaseDelta
    catalog_context: dict[str, Any]
    source_rows: tuple[dict[str, Any], ...]
    source_index: dict[str, dict[str, Any]]
    rule_rows: tuple[dict[str, Any], ...]
    rule_index: dict[str, dict[str, Any]]
    field_rows: tuple[dict[str, Any], ...]
    field_index: dict[str, dict[str, Any]]
    fact_rows: tuple[dict[str, Any], ...]
    fact_index: dict[str, dict[str, Any]]
    claim_rows: tuple[dict[str, Any], ...]
    claim_index: dict[str, dict[str, Any]]
    conflict_rows: tuple[dict[str, Any], ...]
    conflict_index: dict[str, dict[str, Any]]
    variant_rows: tuple[dict[str, Any], ...]
    variant_index: dict[str, dict[str, Any]]


def validate_evidence_domain(
    bundle: dict[str, Any],
    *,
    project: dict[str, Any],
    scope: dict[str, Any],
    intended: AbstractSet[str],
) -> EvidenceReport:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    gates: dict[str, str] = {}
    source_rows = _obj_list(bundle.get("sources"), "sources", errors)
    source_index = _index(source_rows, "sources", errors)
    counts["sources"] = len(source_index)
    for index, row in enumerate(source_rows):
        path = f"sources[{index}]"
        if not _nonempty(row.get("type")) or not _nonempty(row.get("locator")):
            _err(errors, "L11-SOURCE-001", path, "type and locator are required")
        if row.get("status") not in SOURCE_STATUSES:
            _err(errors, "L11-SOURCE-002", f"{path}.status", "unsupported source status")
        if row.get("evidence_level") not in EVIDENCE_LEVELS:
            _err(errors, "L11-SOURCE-003", f"{path}.evidence_level", "must use E0-E4")
        if not _isoish(row.get("retrieved_at")):
            _err(errors, "L11-SOURCE-004", f"{path}.retrieved_at", "must be an ISO timestamp")
        for key in ("proves", "cannot_prove", "child_asins"):
            if not _unique_strings(row.get(key, [])):
                _err(errors, "L11-SOURCE-005", f"{path}.{key}", "must be a unique string array")
        if not set(row.get("child_asins", [])).issubset(intended):
            _err(errors, "L11-SOURCE-006", f"{path}.child_asins", "expands child scope")
        _validate_app_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        if set(row.get("child_asins", [])) != _scope_sets(row.get("application_scope")).get("child_asins", set()):
            _err(errors, "L11-SOURCE-011", path, "child_asins must exactly mirror application_scope.child_asins")
        if row.get("status") == "USABLE" and not source_context_matches(row, scope):
            _err(errors, "L11-SOURCE-012", path, "USABLE source must bind frozen seller/marketplace/locale")
        if row.get("type") in {"seller_central_screenshot", "seller_central_export"}:
            meta = row.get("capture_metadata")
            required = {
                "seller_scope", "marketplace", "entity", "page_context",
                "captured_at", "capture_region", "coverage",
            }
            if not isinstance(meta, dict) or not required.issubset(meta):
                _err(errors, "L11-SOURCE-007", f"{path}.capture_metadata", "Seller Central evidence lacks account/site/entity/page/time/region context")
            elif meta.get("coverage") not in {"COMPLETE", "PARTIAL"}:
                _err(errors, "L11-SOURCE-008", f"{path}.capture_metadata.coverage", "must be COMPLETE or PARTIAL")
            elif (
                meta.get("seller_scope") != scope.get("seller_scope")
                or meta.get("marketplace") != scope.get("marketplace")
                or not _nonempty(meta.get("entity"))
                or not _nonempty(meta.get("page_context"))
                or not _nonempty(meta.get("capture_region"))
                or not _isoish(meta.get("captured_at"))
            ):
                _err(errors, "L11-SOURCE-010", f"{path}.capture_metadata", "Seller Central evidence context does not bind the frozen account/site/entity/page/time/region")
            else:
                preliminary_context = bundle.get("catalog_context") if isinstance(bundle.get("catalog_context"), dict) else {}
                entity_text = str(meta.get("entity", "")).casefold()
                entity_tokens = {
                    str(value).casefold()
                    for value in (
                        preliminary_context.get("identifier"), preliminary_context.get("product_type"),
                        *scope.get("parent_asins", []), *scope.get("intended_child_asins", []),
                    )
                    if _nonempty(value)
                }
                if entity_tokens and not any(token in entity_text for token in entity_tokens):
                    _err(errors, "L11-SOURCE-014", f"{path}.capture_metadata.entity", "must identify the frozen ASIN or Product Type")
        if row.get("type") == "lingxing_mirror":
            forbidden = {"ptd", "product_performance", "amazon_live_state"} & set(row.get("proves", []))
            if forbidden:
                _err(errors, "L11-SOURCE-009", f"{path}.proves", f"Lingxing cannot prove {sorted(forbidden)}")
            allowed_mirror_proofs = {"catalog identity", "asin sku mapping", "parent child mapping"}
            if not set(row.get("proves", [])).issubset(allowed_mirror_proofs):
                _err(errors, "L11-SOURCE-013", f"{path}.proves", "Lingxing is auxiliary identity/mapping evidence only")

    context = bundle.get("catalog_context") if isinstance(bundle.get("catalog_context"), dict) else {}
    if not context:
        _err(errors, "L11-STRUCT-005", "catalog_context", "must be an object")
    if context.get("identity_status") == "FROZEN" and all(_nonempty(context.get(key)) for key in ("identifier", "identifier_type", "parentage_level", "product_type")):
        _refs(context.get("source_ids", []), set(source_index), "catalog_context.source_ids", errors, nonempty=True)
        identity_sources = [source_index.get(item, {}) for item in context.get("source_ids", [])]
        root_application_scope = {
            "parent_asins": list(scope.get("parent_asins", [])),
            "child_asins": list(scope.get("intended_child_asins", [])),
            "packs": list(scope.get("packs", [])),
            "colors": list(scope.get("colors", [])),
            "sizes": list(scope.get("sizes", [])),
        }
        if not identity_sources or any(not source_context_matches(source, scope) for source in identity_sources):
            _err(errors, "L11-IDENTITY-002", "catalog_context.source_ids", "identity evidence must be USABLE and context-bound")
        if not any(
            source.get("type") != "lingxing_mirror"
            and "catalog identity" in set(source.get("proves", []))
            and source_covers(source, scope, root_application_scope)
            for source in identity_sources
        ):
            _err(errors, "L11-IDENTITY-003", "catalog_context.source_ids", "identity needs non-Lingxing USABLE evidence explicitly proving catalog identity across full scope")
        gates["identity"] = "PASS" if not any("[L11-IDENTITY-" in item for item in errors) else "BLOCKED"
    else:
        gates["identity"] = "BLOCKED"
        _err(errors, "L11-IDENTITY-001", "catalog_context", "identity and Product Type must be frozen")

    rule_rows = _obj_list(bundle.get("rule_snapshots"), "rule_snapshots", errors)
    rule_index = _index(rule_rows, "rule_snapshots", errors)
    counts["rule_snapshots"] = len(rule_index)
    current_rules = 0
    for index, row in enumerate(rule_rows):
        path = f"rule_snapshots[{index}]"
        _refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors, nonempty=True)
        proving_rules = [source_index.get(item, {}) for item in row.get("source_ids", [])]
        if not current_rule_has_strong_source(row, source_index):
            _err(errors, "L11-RULE-007", f"{path}.source_ids", "CURRENT rule requires usable E3/E4 official or account evidence")
        root_application_scope = {
            "parent_asins": list(scope.get("parent_asins", [])),
            "child_asins": list(scope.get("intended_child_asins", [])),
            "packs": list(scope.get("packs", [])),
            "colors": list(scope.get("colors", [])),
            "sizes": list(scope.get("sizes", [])),
        }
        if not any(
            source.get("type") in {"amazon_official_rule", "seller_central_screenshot", "seller_central_export"}
            and source.get("evidence_level") in {"E3", "E4"}
            and source_covers(source, scope, root_application_scope)
            for source in proving_rules
        ):
            _err(errors, "L11-RULE-008", f"{path}.source_ids", "CURRENT rule evidence must be USABLE, context-bound, and cover the full frozen scope")
        if row.get("status") != "CURRENT":
            _err(errors, "L11-RULE-001", f"{path}.status", "must be CURRENT")
        else:
            current_rules += 1
        if row.get("marketplace") != scope.get("marketplace") or row.get("locale") != scope.get("locale"):
            _err(errors, "L11-RULE-002", path, "marketplace/locale mismatch")
        if row.get("seller_scope") != scope.get("seller_scope") or row.get("product_type") != context.get("product_type"):
            _err(errors, "L11-RULE-003", path, "seller scope/Product Type mismatch")
        if row.get("data_plane") not in DATA_PLANES:
            _err(errors, "L11-RULE-004", f"{path}.data_plane", "unsupported data plane")
        if not _isoish(row.get("retrieved_at")):
            _err(errors, "L11-RULE-005", f"{path}.retrieved_at", "must be an ISO timestamp")
        elif _nonempty(project.get("snapshot_date")) and str(row.get("retrieved_at"))[:10] < str(project.get("snapshot_date")):
            _err(errors, "L11-RULE-006", f"{path}.retrieved_at", "CURRENT rule predates the project snapshot")
    gates["rules"] = "PASS" if current_rules and not any("[L11-RULE-" in item for item in errors) else "BLOCKED"

    field_rows = _obj_list(bundle.get("field_resolutions"), "field_resolutions", errors)
    field_index = _index(field_rows, "field_resolutions", errors)
    counts["field_resolutions"] = len(field_index)
    for index, row in enumerate(field_rows):
        path = f"field_resolutions[{index}]"
        if is_community_qa_field(row):
            _err(errors, "L11-FIELD-007", path, "Community Q&A is read-only and cannot be a brand-authored Field Resolution")
        if _is_fake_subtitle(row.get("canonical_key")) or _is_fake_subtitle(row.get("semantic_role")):
            _err(errors, "L11-FIELD-001", path, "generic or invented subtitle is forbidden; resolve ITEM_HIGHLIGHTS")
        for flag in ("exists", "editable", "applicable"):
            if not isinstance(row.get(flag), bool):
                _err(errors, "L11-FIELD-005", f"{path}.{flag}", "must be boolean")
        if row.get("semantic_role") == "ITEM_HIGHLIGHTS":
            if row.get("status") == "RESOLVED" and (
                not _nonempty(row.get("canonical_key"))
                or not isinstance(row.get("max_characters"), int)
                or row.get("max_characters", 0) <= 0
                or not row.get("exists")
                or not row.get("applicable")
            ):
                _err(errors, "L11-FIELD-002", path, "resolved ITEM_HIGHLIGHTS requires actual key, availability, and current positive character limit")
            account_refs = row.get("account_evidence_source_ids", [])
            _refs(account_refs, set(source_index), f"{path}.account_evidence_source_ids", errors, nonempty=True)
            if not any(
                source_can_prove_account_field(
                    source_index.get(item, {}), scope, row.get("application_scope", {})
                )
                for item in account_refs
            ):
                _err(errors, "L11-FIELD-006", f"{path}.account_evidence_source_ids", "ITEM_HIGHLIGHTS key, availability, and limit require applicable current account evidence")
        if row.get("data_plane") not in DATA_PLANES or row.get("surface") not in SURFACES:
            _err(errors, "L11-FIELD-003", path, "unsupported data plane or surface")
        if row.get("status") not in {"RESOLVED", "NOT_AVAILABLE", "HOLD", "PROHIBITED"}:
            _err(errors, "L11-FIELD-004", f"{path}.status", "unsupported field status")
        _refs(row.get("rule_snapshot_ids", []), set(rule_index), f"{path}.rule_snapshot_ids", errors, nonempty=True)
        _validate_app_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)

    fact_rows = _obj_list(bundle.get("facts"), "facts", errors)
    fact_index = _index(fact_rows, "facts", errors)
    claim_rows = _obj_list(bundle.get("claims"), "claims", errors)
    claim_index = _index(claim_rows, "claims", errors)
    counts.update({"facts": len(fact_index), "claims": len(claim_index)})
    for kind, rows, index_map in (("FACT", fact_rows, fact_index), ("CLAIM", claim_rows, claim_index)):
        for index, row in enumerate(rows):
            path = f"{kind.lower()}s[{index}]"
            text_key = "statement" if kind == "FACT" else "text"
            if not _nonempty(row.get(text_key)):
                _err(errors, f"L11-{kind}-001", f"{path}.{text_key}", "is required")
            _refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors, nonempty=True)
            _refs(row.get("proving_source_ids", []), set(source_index), f"{path}.proving_source_ids", errors)
            _validate_app_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
            if row.get("evidence_level") not in EVIDENCE_LEVELS:
                _err(errors, f"L11-{kind}-002", f"{path}.evidence_level", "must use E0-E4")
            for key in ("can_prove", "cannot_prove", "prohibited_inferences"):
                if not _unique_strings(row.get(key, [])):
                    _err(errors, f"L11-{kind}-003", f"{path}.{key}", "must be a unique string array")
            if not _nonempty(row.get("allowed_expression")) or not _nonempty(row.get("refresh_trigger")):
                _err(errors, f"L11-{kind}-004", path, "allowed_expression and refresh_trigger are required")
            publishable = row.get("content_status") == "PUBLISHABLE"
            if publishable and (
                not row.get("proving_source_ids")
                or not proving_sources_cover(
                    row.get("proving_source_ids", []), source_index, scope, row.get("application_scope", {})
                )
            ):
                _err(errors, f"L11-{kind}-005", f"{path}.proving_source_ids", "every proving source must be USABLE E3/E4 product evidence covering seller/market/locale and full variant scope")
            if kind == "CLAIM":
                _refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors, nonempty=True)
    conflict_rows = _obj_list(bundle.get("conflicts"), "conflicts", errors)
    conflict_index = _index(conflict_rows, "conflicts", errors)
    for index, row in enumerate(conflict_rows):
        _refs(row.get("affected_fact_ids", []), set(fact_index), f"conflicts[{index}].affected_fact_ids", errors)
        _refs(row.get("affected_claim_ids", []), set(claim_index), f"conflicts[{index}].affected_claim_ids", errors)
        if row.get("status") not in {"OPEN", "EVIDENCE_REQUESTED", "RESOLVED", "BLOCKED"}:
            _err(errors, "L11-CONFLICT-001", f"conflicts[{index}].status", "unsupported conflict status")

    variant_rows = _obj_list(bundle.get("variant_topology"), "variant_topology", errors)
    variant_index = _index(variant_rows, "variant_topology", errors)
    counts["variant_rows"] = len(variant_index)
    children: list[str] = []
    for index, row in enumerate(variant_rows):
        path = f"variant_topology[{index}]"
        child = row.get("child_asin")
        children.append(str(child))
        if child not in intended or row.get("status") != "VERIFIED" or not _nonempty(row.get("seller_sku")):
            _err(errors, "L11-VARIANT-001", path, "must bind one verified intended child and SKU")
        for row_key, scope_key in (("pack", "packs"), ("color", "colors"), ("size", "sizes")):
            allowed = set(scope.get(scope_key, []))
            actual = row.get(row_key)
            if allowed and actual not in allowed:
                _err(errors, "L11-VARIANT-002", f"{path}.{row_key}", "outside frozen scope")
            if not allowed and _nonempty(actual):
                _err(errors, "L11-VARIANT-003", f"{path}.{row_key}", "dimension is not applicable in frozen scope")
        _refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors)
        _refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors, nonempty=True)
        if not any(
            source_covers(source_index.get(source_id, {}), scope, variant_scope(row))
            for source_id in row.get("source_ids", [])
        ):
            _err(errors, "L11-VARIANT-005", f"{path}.source_ids", "verified variant needs a USABLE source covering exact parent/child/pack/color/size scope")
    if len(children) != len(set(children)) or set(children) != intended:
        _err(errors, "L11-VARIANT-004", "variant_topology", "must cover every intended child exactly once")
    truth_errors = any(token in item for item in errors for token in ("L11-FACT-", "L11-CLAIM-", "L11-CONFLICT-", "L11-VARIANT-"))
    gates["truth"] = "BLOCKED" if truth_errors else "PASS"

    return EvidenceReport(
        delta=PhaseDelta.capture(errors, warnings, counts, gates),
        catalog_context=context,
        source_rows=tuple(source_rows),
        source_index=source_index,
        rule_rows=tuple(rule_rows),
        rule_index=rule_index,
        field_rows=tuple(field_rows),
        field_index=field_index,
        fact_rows=tuple(fact_rows),
        fact_index=fact_index,
        claim_rows=tuple(claim_rows),
        claim_index=claim_index,
        conflict_rows=tuple(conflict_rows),
        conflict_index=conflict_index,
        variant_rows=tuple(variant_rows),
        variant_index=variant_index,
    )
