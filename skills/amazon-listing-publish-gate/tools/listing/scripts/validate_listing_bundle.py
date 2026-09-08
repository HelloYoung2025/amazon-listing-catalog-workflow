#!/usr/bin/env python3
"""Validate Amazon Listing Bundle v1.0 legacy or v1.1 current contracts.

The validator checks contract consistency. It does not prove that product facts
are true, Amazon rules are current, an authorizer has real-world authority, or
content is live.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from listing_publication_contract import (
    AUTHORIZATION_KEYS,
    AUTHORIZATION_STATUSES,
    AUTHORIZED_SUBMISSION_ACTIONS,
    BASELINE_ROW_KEYS,
    CHANGE_ROW_KEYS,
    LIVE_EVIDENCE_TYPES,
    READBACK_ROW_KEYS,
    READBACK_STATUSES,
    ROLLBACK_ROW_KEYS,
    canonical_child_readback_value,
    canonical_row_hash,
    canonical_rows_hash,
    validate_publication,
)


SCHEMA_VERSION = "1.0"
ROOT_KEYS = {
    "schema_version", "project", "execution_boundary", "scope",
    "catalog_context", "rule_snapshots", "field_resolutions", "sources",
    "facts", "claims", "conflicts", "variant_topology", "decision_map",
    "surface_assignments", "field_candidates", "enriched_content_handoff",
    "publish_authorization", "baseline", "change_set", "rollback",
    "live_readback", "gates", "record_templates",
}

EXECUTION_BOUNDARIES = {
    "read_only", "local_candidate", "authorized_submission", "rollback_only"
}
MODES = {"audit", "plan", "rebuild", "preflight_qa", "publish_support"}
CONCLUSIONS = {
    "NO_VALID_CONCLUSION", "CONDITIONAL_PASS", "PASS", "BLOCKED", "LIVE_PASS"
}
SURFACES = {
    "core_copy", "catalog_attributes", "size_chart", "media",
    "backend_search_terms", "enriched_content",
}
DATA_PLANES = {
    "catalog_contribution", "seller_listing", "relationship",
    "enriched_content", "external_tool",
}
PRIMARY_CARRIER_KINDS = {
    "NATIVE_VISIBLE", "STRUCTURED_VISIBLE", "A_PLUS_NATIVE_PENDING",
    "IMAGE_TEXT", "ALT_METADATA", "VIDEO_ONLY", "INTERACTIVE_ONLY",
    "BACKEND_HIDDEN", "COMMUNITY_QA",
}
LEGAL_P0_CARRIERS = {"NATIVE_VISIBLE", "STRUCTURED_VISIBLE"}
HOLD_CONTENT = {"HOLD", "CONFLICT", "UNSUPPORTED", "INFERRED_ONLY", "PROHIBITED"}
CONTENT_TYPES = {"BASIC_A_PLUS", "PREMIUM_A_PLUS", "BRAND_STORY"}
HANDOFF_REQUIREMENT_KEYS = {
    "id", "buyer_question", "priority", "application_scope", "fact_ids",
    "claim_ids", "native_answer_required", "early_disclosure_required",
    "upstream_primary_carrier_ref", "assigned_surface", "status",
}
HANDOFF_KEYS = {
    "contract_version", "snapshot_id", "parent_project_id", "parent_bundle_sha256",
    "status", "maximum_output", "marketplace", "locale", "product_type",
    "application_scope", "variant_row_ids", "fact_ids", "claim_ids",
    "blocked_claim_ids", "conflict_ids", "source_ids", "requested_content_types",
    "decision_requirements", "capability_snapshot_ids", "prohibited_actions",
    "created_at", "owner", "checksum",
}
FORBIDDEN_METRIC_KEYS = {
    "minimum_total_words", "min_total_words", "native_text_min_chars",
    "min_total_chars", "keyword_density", "cosmo_score", "alexa_coverage",
    "cdq_weight", "fixed_wait_days", "semantic_score",
}

CRITICAL_CONFLICT_PRIORITIES = {"P0"}

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def err(errors: list[str], code: str, path: str, message: str) -> None:
    errors.append(f"[{code}] {path}: {message}")


def warn(warnings: list[str], code: str, path: str, message: str) -> None:
    warnings.append(f"[{code}] {path}: {message}")


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_community_qa_role(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return (
        "community" in normalized or "customer" in normalized
    ) and any(token in normalized for token in ("qa", "q_and_a", "question", "answer"))


def string_list(value: Any) -> bool:
    return isinstance(value, list) and all(nonempty(x) for x in value)


def unique_strings(value: Any) -> bool:
    return string_list(value) and len(value) == len(set(value))


def isoish(value: Any) -> bool:
    return nonempty(value) and "T" in value and (value.endswith("Z") or "+" in value)


def parse_timestamp(value: Any) -> datetime | None:
    if not isoish(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_handoff_hash(handoff: dict[str, Any]) -> str:
    normalized = copy.deepcopy(handoff)
    normalized["parent_bundle_sha256"] = ""
    normalized["checksum"] = ""
    return canonical_sha256(normalized)


def exact_keys(value: dict[str, Any], expected: set[str], path: str, code: str, errors: list[str]) -> None:
    if set(value) != expected:
        err(errors, code, path, f"must contain exactly {sorted(expected)}")


def obj_list(bundle: dict[str, Any], key: str, errors: list[str]) -> list[dict[str, Any]]:
    value = bundle.get(key)
    if not isinstance(value, list):
        err(errors, "LST-STRUCT-001", key, "must be an array")
        return []
    out: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            err(errors, "LST-STRUCT-002", f"{key}[{index}]", "must be an object")
        else:
            out.append(item)
    return out


def index_by_id(rows: Iterable[dict[str, Any]], path: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        item_id = row.get("id")
        if not nonempty(item_id) or not ID_RE.match(item_id):
            err(errors, "LST-ID-001", f"{path}[{index}].id", "must be a non-empty stable ID")
            continue
        if item_id in result:
            err(errors, "LST-ID-002", f"{path}[{index}].id", f"duplicate ID {item_id}")
            continue
        result[item_id] = row
    return result


def canonical_parent_hash(bundle: dict[str, Any]) -> str:
    normalized = copy.deepcopy(bundle)
    handoff = normalized.get("enriched_content_handoff")
    if isinstance(handoff, dict):
        handoff["parent_bundle_sha256"] = ""
        handoff["checksum"] = ""
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scope_set(scope: Any, key: str) -> set[str]:
    if not isinstance(scope, dict):
        return set()
    value = scope.get(key, [])
    return set(value) if string_list(value) else set()


def application_scope_is_subset(child: Any, parent: Any) -> bool:
    if not isinstance(child, dict) or not isinstance(parent, dict):
        return False
    for key in ("parent_asins", "child_asins", "packs", "colors", "sizes"):
        parent_values = scope_set(parent, key)
        child_values = scope_set(child, key)
        if child_values and not child_values.issubset(parent_values):
            return False
    return True


def validate_application_scope(
    scope: Any,
    path: str,
    parent_scope: dict[str, Any],
    errors: list[str],
    *,
    require_child: bool = True,
) -> None:
    if not isinstance(scope, dict):
        err(errors, "LST-SCOPE-001", path, "must be an object")
        return
    expected = {"parent_asins", "child_asins", "packs", "colors", "sizes"}
    if set(scope) != expected:
        err(errors, "LST-SCOPE-002", path, f"must contain exactly {sorted(expected)}")
    for key in expected:
        if not unique_strings(scope.get(key, [])):
            err(errors, "LST-SCOPE-003", f"{path}.{key}", "must be a unique string array")
    if require_child and not scope_set(scope, "child_asins"):
        err(errors, "LST-SCOPE-004", f"{path}.child_asins", "must bind at least one child")
    parent_children = scope_set(parent_scope, "intended_child_asins")
    parent_parents = scope_set(parent_scope, "parent_asins")
    if not scope_set(scope, "child_asins").issubset(parent_children):
        err(errors, "LST-SCOPE-005", path, "child scope expands beyond intended_child_asins")
    if not scope_set(scope, "parent_asins").issubset(parent_parents):
        err(errors, "LST-SCOPE-006", path, "parent scope expands beyond parent_asins")
    for key in ("packs", "colors", "sizes"):
        allowed = scope_set(parent_scope, key)
        requested = scope_set(scope, key)
        if requested and not requested.issubset(allowed):
            err(errors, "LST-SCOPE-007", f"{path}.{key}", "expands beyond frozen scope")


def require_refs(
    values: Any,
    known: set[str],
    path: str,
    errors: list[str],
    code: str = "LST-REF-001",
) -> None:
    if not unique_strings(values):
        err(errors, code, path, "must be a unique string array")
        return
    unknown = set(values) - known
    if unknown:
        err(errors, code, path, f"unknown references: {sorted(unknown)}")


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            next_path = f"{path}.{key}"
            if key in FORBIDDEN_METRIC_KEYS:
                hits.append(next_path)
            hits.extend(find_forbidden_keys(child, next_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def validate_listing_bundle(
    bundle: Any,
    aplus_result: Any | None = None,
    *,
    aplus_source_path: Path | None = None,
) -> dict[str, Any]:
    if isinstance(bundle, dict) and bundle.get("schema_version") == "1.1":
        from validate_listing_bundle_v11 import validate_listing_bundle_v11
        return validate_listing_bundle_v11(bundle, aplus_result)
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    if not isinstance(bundle, dict):
        return {"ok": False, "errors": ["[LST-STRUCT-000] $: bundle must be an object"], "warnings": [], "counts": {}}

    if bundle.get("schema_version") != SCHEMA_VERSION:
        err(errors, "LST-VERSION-001", "schema_version", f"must equal {SCHEMA_VERSION}")
    missing = ROOT_KEYS - set(bundle)
    extra = set(bundle) - ROOT_KEYS
    if missing:
        err(errors, "LST-ROOT-001", "$", f"missing keys: {sorted(missing)}")
    if extra:
        err(errors, "LST-ROOT-002", "$", f"unknown keys: {sorted(extra)}")

    boundary = bundle.get("execution_boundary")
    if boundary not in EXECUTION_BOUNDARIES:
        err(errors, "LST-AUTH-001", "execution_boundary", "must use the closed execution-boundary set")

    project = bundle.get("project")
    if not isinstance(project, dict):
        err(errors, "LST-PROJECT-001", "project", "must be an object")
        project = {}
    if project.get("mode") not in MODES:
        err(errors, "LST-PROJECT-002", "project.mode", "unsupported mode")
    if project.get("conclusion") not in CONCLUSIONS:
        err(errors, "LST-PROJECT-003", "project.conclusion", "unsupported conclusion")

    for hit in find_forbidden_keys(bundle):
        err(errors, "LST-METRIC-001", hit, "unsupported normative metric or fixed threshold")

    if project.get("status") == "SCAFFOLD":
        if boundary != "read_only":
            err(errors, "LST-AUTH-002", "execution_boundary", "SCAFFOLD must remain read_only")
        if project.get("conclusion") != "NO_VALID_CONCLUSION":
            err(errors, "LST-PROJECT-004", "project.conclusion", "SCAFFOLD cannot claim a conclusion")
        template_path = Path(__file__).resolve().parent.parent / "assets" / "listing-project-bundle-template-v1.0.json"
        try:
            pristine = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            err(errors, "LST-SCAFFOLD-001", "$", f"cannot load pristine scaffold: {exc}")
        else:
            if bundle != pristine:
                err(errors, "LST-SCAFFOLD-002", "$", "SCAFFOLD must remain byte-semantically pristine; populate a copy and change project.status")
        if aplus_result is not None:
            err(errors, "LST-SCAFFOLD-003", "aplus_result", "SCAFFOLD cannot carry an embedded A+ result")
        return {
            "ok": not errors, "errors": errors, "warnings": warnings,
            "counts": counts, "parent_bundle_sha256": canonical_parent_hash(bundle),
            "contract_status": "LEGACY_LOCAL_CONTRACT",
            "result_level": "LEGACY_LOCAL_CONTRACT",
            "publication_authorized": False,
            "live_conclusion_recognized": False,
        }

    scope = bundle.get("scope")
    if not isinstance(scope, dict):
        err(errors, "LST-SCOPE-010", "scope", "must be an object")
        scope = {}
    for key in ("marketplace", "locale", "seller_scope"):
        if not nonempty(scope.get(key)):
            err(errors, "LST-SCOPE-011", f"scope.{key}", "must be bound")
    for key in ("parent_asins", "intended_child_asins", "excluded_child_asins", "packs", "colors", "sizes"):
        if not unique_strings(scope.get(key, [])):
            err(errors, "LST-SCOPE-012", f"scope.{key}", "must be a unique string array")
    intended = scope_set(scope, "intended_child_asins")
    excluded = scope_set(scope, "excluded_child_asins")
    if not intended:
        err(errors, "LST-SCOPE-013", "scope.intended_child_asins", "must bind at least one child")
    if intended & excluded:
        err(errors, "LST-SCOPE-014", "scope", "intended and excluded child scopes overlap")

    sources = obj_list(bundle, "sources", errors)
    source_index = index_by_id(sources, "sources", errors)
    counts["sources"] = len(source_index)
    for index, row in enumerate(sources):
        if row.get("status") not in {"USABLE", "STALE", "BLOCKED"}:
            err(errors, "LST-SOURCE-001", f"sources[{index}].status", "unsupported source status")
        if not nonempty(row.get("type")) or not nonempty(row.get("locator")):
            err(errors, "LST-SOURCE-002", f"sources[{index}]", "type and locator are required")

    context = bundle.get("catalog_context")
    if not isinstance(context, dict):
        err(errors, "LST-IDENTITY-001", "catalog_context", "must be an object")
        context = {}
    if context.get("identity_status") != "FROZEN":
        err(errors, "LST-IDENTITY-002", "catalog_context.identity_status", "must be FROZEN")
    if context.get("schema_status") != "READY":
        err(errors, "LST-SCHEMA-001", "catalog_context.schema_status", "must be READY")
    if context.get("data_plane_status") != "READY":
        err(errors, "LST-PLANE-001", "catalog_context.data_plane_status", "must be READY")
    for key in ("identifier", "identifier_type", "parentage_level", "product_type"):
        if not nonempty(context.get(key)):
            err(errors, "LST-IDENTITY-003", f"catalog_context.{key}", "must be bound")
    require_refs(context.get("source_ids", []), set(source_index), "catalog_context.source_ids", errors)

    rule_rows = obj_list(bundle, "rule_snapshots", errors)
    rule_index = index_by_id(rule_rows, "rule_snapshots", errors)
    counts["rule_snapshots"] = len(rule_index)
    if not rule_rows:
        err(errors, "LST-SCHEMA-002", "rule_snapshots", "at least one current rule snapshot is required")
    for index, row in enumerate(rule_rows):
        path = f"rule_snapshots[{index}]"
        for key in ("marketplace", "locale", "seller_scope", "product_type", "parentage_level", "data_plane", "status", "checksum", "refresh_trigger"):
            if not nonempty(row.get(key)):
                err(errors, "LST-SCHEMA-003", f"{path}.{key}", "is required")
        if row.get("data_plane") not in DATA_PLANES:
            err(errors, "LST-PLANE-002", f"{path}.data_plane", "unsupported data plane")
        if row.get("status") != "CURRENT":
            err(errors, "LST-SCHEMA-004", f"{path}.status", "must be CURRENT")
        if row.get("marketplace") != scope.get("marketplace") or row.get("locale") != scope.get("locale"):
            err(errors, "LST-SCHEMA-005", path, "marketplace/locale does not match frozen scope")
        if row.get("seller_scope") != scope.get("seller_scope"):
            err(errors, "LST-SCHEMA-006", f"{path}.seller_scope", "does not match frozen seller scope")
        if row.get("product_type") != context.get("product_type"):
            err(errors, "LST-SCHEMA-007", f"{path}.product_type", "does not match resolved Product Type")
        if not isoish(row.get("retrieved_at")):
            err(errors, "LST-SCHEMA-008", f"{path}.retrieved_at", "must be an ISO timestamp")
        require_refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors)

    field_rows = obj_list(bundle, "field_resolutions", errors)
    field_index = index_by_id(field_rows, "field_resolutions", errors)
    counts["field_resolutions"] = len(field_index)
    for index, row in enumerate(field_rows):
        path = f"field_resolutions[{index}]"
        for key in ("semantic_role", "canonical_key", "ui_label", "data_plane", "surface", "status"):
            if not nonempty(row.get(key)):
                err(errors, "LST-FIELD-001", f"{path}.{key}", "is required")
        if row.get("canonical_key") == "subtitle":
            err(errors, "LST-FIELD-002", f"{path}.canonical_key", "generic subtitle is not a resolved backend field")
        if is_community_qa_role(row.get("semantic_role")) or is_community_qa_role(row.get("canonical_key")):
            err(errors, "LST-QA-003", path, "Community/customer Q&A is not a writable Listing field")
        if row.get("data_plane") not in DATA_PLANES:
            err(errors, "LST-PLANE-003", f"{path}.data_plane", "unsupported data plane")
        if row.get("surface") not in SURFACES:
            err(errors, "LST-FIELD-003", f"{path}.surface", "unsupported page surface")
        if row.get("status") not in {"RESOLVED", "NOT_AVAILABLE", "HOLD", "PROHIBITED"}:
            err(errors, "LST-FIELD-004", f"{path}.status", "unsupported resolution status")
        for key in ("exists", "editable", "applicable"):
            if not isinstance(row.get(key), bool):
                err(errors, "LST-FIELD-005", f"{path}.{key}", "must be boolean")
        require_refs(row.get("rule_snapshot_ids", []), set(rule_index), f"{path}.rule_snapshot_ids", errors)
        for snapshot_id in row.get("rule_snapshot_ids", []):
            snapshot = rule_index.get(snapshot_id, {})
            if snapshot.get("data_plane") != row.get("data_plane"):
                err(errors, "LST-FIELD-006", f"{path}.rule_snapshot_ids", f"snapshot {snapshot_id} resolves a different data plane")
        validate_application_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)

    fact_rows = obj_list(bundle, "facts", errors)
    fact_index = index_by_id(fact_rows, "facts", errors)
    counts["facts"] = len(fact_index)
    for index, row in enumerate(fact_rows):
        path = f"facts[{index}]"
        if not nonempty(row.get("statement")):
            err(errors, "LST-FACT-001", f"{path}.statement", "is required")
        require_refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors)
        validate_application_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        if row.get("verification_status") not in {"VERIFIED", "UNVERIFIED", "CONFLICT"}:
            err(errors, "LST-FACT-002", f"{path}.verification_status", "unsupported status")
        if row.get("content_status") not in {"PUBLISHABLE", "HOLD", "CONFLICT", "INFERRED_ONLY", "PROHIBITED"}:
            err(errors, "LST-FACT-003", f"{path}.content_status", "unsupported status")

    claim_rows = obj_list(bundle, "claims", errors)
    claim_index = index_by_id(claim_rows, "claims", errors)
    counts["claims"] = len(claim_index)
    for index, row in enumerate(claim_rows):
        path = f"claims[{index}]"
        if not nonempty(row.get("text")):
            err(errors, "LST-CLAIM-001", f"{path}.text", "is required")
        require_refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors)
        require_refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors)
        validate_application_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        if row.get("support_status") not in {"SUPPORTED", "UNSUPPORTED", "CONFLICT"}:
            err(errors, "LST-CLAIM-002", f"{path}.support_status", "unsupported status")
        if row.get("content_status") not in {"PUBLISHABLE", "HOLD", "CONFLICT", "INFERRED_ONLY", "PROHIBITED"}:
            err(errors, "LST-CLAIM-003", f"{path}.content_status", "unsupported status")

    conflict_rows = obj_list(bundle, "conflicts", errors)
    conflict_index = index_by_id(conflict_rows, "conflicts", errors)
    counts["conflicts"] = len(conflict_index)
    for index, row in enumerate(conflict_rows):
        path = f"conflicts[{index}]"
        require_refs(row.get("affected_fact_ids", []), set(fact_index), f"{path}.affected_fact_ids", errors)
        require_refs(row.get("affected_claim_ids", []), set(claim_index), f"{path}.affected_claim_ids", errors)
        require_refs(row.get("affected_child_asins", []), intended, f"{path}.affected_child_asins", errors)
        if row.get("status") not in {"OPEN", "EVIDENCE_REQUESTED", "RESOLVED", "ACCEPTED_RISK", "BLOCKED"}:
            err(errors, "LST-CONFLICT-001", f"{path}.status", "unsupported status")
        if row.get("status") == "ACCEPTED_RISK":
            for key in ("accepted_by", "acceptance_authority", "accepted_at", "expires_at", "severity"):
                if not nonempty(row.get(key)):
                    err(errors, "LST-CONFLICT-002", f"{path}.{key}", "required for ACCEPTED_RISK")
            require_refs(row.get("acceptance_source_ids", []), set(source_index), f"{path}.acceptance_source_ids", errors, "LST-CONFLICT-003")
            if row.get("severity") not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                err(errors, "LST-CONFLICT-004", f"{path}.severity", "must use the closed severity set")
            if not nonempty(row.get("resolution")) or not nonempty(row.get("owner")):
                err(errors, "LST-CONFLICT-006", path, "ACCEPTED_RISK requires a resolution and accountable owner")
            accepted_at = parse_timestamp(row.get("accepted_at"))
            expires_at = parse_timestamp(row.get("expires_at"))
            if accepted_at is None or expires_at is None or accepted_at >= expires_at:
                err(errors, "LST-CONFLICT-007", path, "acceptance timestamps must be valid and ordered")
            elif expires_at <= datetime.now(timezone.utc):
                err(errors, "LST-CONFLICT-008", f"{path}.expires_at", "accepted risk is expired")
            for source_id in row.get("acceptance_source_ids", []):
                if source_index.get(source_id, {}).get("status") != "USABLE":
                    err(errors, "LST-CONFLICT-009", f"{path}.acceptance_source_ids", f"source {source_id} is not usable")

    variant_rows = obj_list(bundle, "variant_topology", errors)
    variant_index = index_by_id(variant_rows, "variant_topology", errors)
    counts["variant_rows"] = len(variant_index)
    variant_children: set[str] = set()
    variant_skus: set[str] = set()
    for index, row in enumerate(variant_rows):
        path = f"variant_topology[{index}]"
        child = row.get("child_asin")
        if not nonempty(child) or child not in intended:
            err(errors, "LST-VARIANT-001", f"{path}.child_asin", "must be an intended child")
        elif child in variant_children:
            err(errors, "LST-VARIANT-002", f"{path}.child_asin", "duplicate child topology row")
        else:
            variant_children.add(child)
        if row.get("status") != "VERIFIED":
            err(errors, "LST-VARIANT-003", f"{path}.status", "must be VERIFIED")
        if not nonempty(row.get("seller_sku")):
            err(errors, "LST-VARIANT-004", f"{path}.seller_sku", "SKU-to-ASIN binding is required")
        elif row.get("seller_sku") in variant_skus:
            err(errors, "LST-VARIANT-006", f"{path}.seller_sku", "duplicate SKU binding")
        else:
            variant_skus.add(row.get("seller_sku"))
        parent = row.get("parent_asin")
        frozen_parents = scope_set(scope, "parent_asins")
        if frozen_parents and parent not in frozen_parents:
            err(errors, "LST-VARIANT-007", f"{path}.parent_asin", "outside frozen parent scope")
        for row_key, scope_key in (("pack", "packs"), ("color", "colors"), ("size", "sizes")):
            value = row.get(row_key)
            allowed = scope_set(scope, scope_key)
            if allowed and value not in allowed:
                err(errors, "LST-VARIANT-008", f"{path}.{row_key}", "outside frozen dimension scope")
            if not allowed and nonempty(value):
                err(errors, "LST-VARIANT-009", f"{path}.{row_key}", "dimension is unresolved or not applicable in frozen scope")
        require_refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors)
        require_refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors)
        row_scope = {
            "parent_asins": [parent] if nonempty(parent) else [],
            "child_asins": [child] if nonempty(child) else [],
            "packs": [row.get("pack")] if nonempty(row.get("pack")) else [],
            "colors": [row.get("color")] if nonempty(row.get("color")) else [],
            "sizes": [row.get("size")] if nonempty(row.get("size")) else [],
        }
        for fact_id in row.get("fact_ids", []):
            if not application_scope_is_subset(row_scope, fact_index.get(fact_id, {}).get("application_scope")):
                err(errors, "LST-VARIANT-010", f"{path}.fact_ids", f"fact {fact_id} does not cover this variant row")
    if variant_children != intended:
        err(errors, "LST-VARIANT-005", "variant_topology", "must cover every intended child exactly once")

    decision_map = bundle.get("decision_map")
    if not isinstance(decision_map, dict) or not isinstance(decision_map.get("requirements"), list):
        err(errors, "LST-DECISION-001", "decision_map", "must contain a requirements array")
        requirements: list[dict[str, Any]] = []
    else:
        requirements = [x for x in decision_map["requirements"] if isinstance(x, dict)]
        if len(requirements) != len(decision_map["requirements"]):
            err(errors, "LST-DECISION-002", "decision_map.requirements", "every item must be an object")
    requirement_index = index_by_id(requirements, "decision_map.requirements", errors)
    counts["decision_requirements"] = len(requirement_index)
    for index, row in enumerate(requirements):
        path = f"decision_map.requirements[{index}]"
        if not nonempty(row.get("buyer_question")):
            err(errors, "LST-DECISION-003", f"{path}.buyer_question", "is required")
        if row.get("priority") not in {"P0", "P1", "P2"}:
            err(errors, "LST-DECISION-004", f"{path}.priority", "unsupported priority")
        if row.get("assigned_surface") not in SURFACES:
            err(errors, "LST-DECISION-005", f"{path}.assigned_surface", "unsupported surface")
        if row.get("status") not in {"READY", "HOLD", "CONFLICT", "OMITTED_WITH_REASON"}:
            err(errors, "LST-DECISION-006", f"{path}.status", "unsupported status")
        if row.get("early_disclosure_required") not in {True, False}:
            err(errors, "LST-DECISION-007", f"{path}.early_disclosure_required", "must be boolean")
        validate_application_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        require_refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors)
        require_refs(row.get("claim_ids", []), set(claim_index), f"{path}.claim_ids", errors)

    assignment_rows = obj_list(bundle, "surface_assignments", errors)
    assignment_index = index_by_id(assignment_rows, "surface_assignments", errors)
    counts["surface_assignments"] = len(assignment_index)
    assignments_by_requirement: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(assignment_rows):
        path = f"surface_assignments[{index}]"
        req_id = row.get("requirement_id")
        if req_id not in requirement_index:
            err(errors, "LST-COVERAGE-001", f"{path}.requirement_id", "unknown decision requirement")
        else:
            assignments_by_requirement.setdefault(req_id, []).append(row)
        if row.get("primary_surface") not in SURFACES:
            err(errors, "LST-COVERAGE-002", f"{path}.primary_surface", "unsupported surface")
        if row.get("primary_carrier_kind") not in PRIMARY_CARRIER_KINDS:
            err(errors, "LST-COVERAGE-003", f"{path}.primary_carrier_kind", "unsupported carrier kind")
        field_id = row.get("field_resolution_id")
        if field_id:
            if field_id not in field_index:
                err(errors, "LST-COVERAGE-004", f"{path}.field_resolution_id", "unknown field resolution")
            else:
                field = field_index[field_id]
                if field.get("status") != "RESOLVED" or not field.get("exists") or not field.get("applicable"):
                    err(errors, "LST-COVERAGE-005", f"{path}.field_resolution_id", "field is not usable")
                if row.get("primary_carrier_kind") in LEGAL_P0_CARRIERS and field.get("visibility") != "BUYER_VISIBLE":
                    err(errors, "LST-COVERAGE-006", f"{path}.field_resolution_id", "native/structured primary must be buyer-visible")
                if row.get("primary_surface") != field.get("surface"):
                    err(errors, "LST-COVERAGE-012", f"{path}.primary_surface", "must match the resolved field surface")
                if not application_scope_is_subset(row.get("application_scope"), field.get("application_scope")):
                    err(errors, "LST-COVERAGE-010", f"{path}.application_scope", "expands the resolved field scope")
        elif row.get("primary_carrier_kind") != "A_PLUS_NATIVE_PENDING":
            err(errors, "LST-COVERAGE-007", f"{path}.field_resolution_id", "a resolved field is required")
        validate_application_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        if req_id in requirement_index and not application_scope_is_subset(row.get("application_scope"), requirement_index[req_id].get("application_scope")):
            err(errors, "LST-COVERAGE-011", f"{path}.application_scope", "expands the decision-requirement scope")

    aplus_coverage: dict[str, bool] = {}
    if isinstance(aplus_result, dict):
        err(
            errors,
            "LST-XBUNDLE-020",
            "aplus_result",
            "legacy v1.0 is a LEGACY_LOCAL_CONTRACT and cannot consume an A+ result; use validate_listing_package.py with migrated current bundles",
        )

    p0_total = 0
    p0_pass = 0
    for req_id, requirement in requirement_index.items():
        if requirement.get("priority") != "P0":
            continue
        p0_total += 1
        rows = assignments_by_requirement.get(req_id, [])
        valid = False
        for row in rows:
            carrier = row.get("primary_carrier_kind")
            surface = row.get("primary_surface")
            if carrier in LEGAL_P0_CARRIERS and surface not in {"media", "backend_search_terms"} and row.get("status") == "PASS":
                valid = True
            elif carrier == "A_PLUS_NATIVE_PENDING" and surface == "enriched_content" and aplus_coverage.get(req_id):
                valid = True
        if requirement.get("early_disclosure_required") and any(r.get("primary_surface") == "enriched_content" for r in rows):
            valid = False
            err(errors, "LST-COVERAGE-008", f"decision_map.requirements[{req_id}]", "early-disclosure P0 cannot use A+ as its only primary surface")
        if not valid:
            err(errors, "LST-COVERAGE-009", f"decision_map.requirements[{req_id}]", "P0 lacks a legal buyer-visible primary carrier")
        else:
            p0_pass += 1
    counts["p0_required"] = p0_total
    counts["p0_pass"] = p0_pass

    candidate_rows = obj_list(bundle, "field_candidates", errors)
    candidate_index = index_by_id(candidate_rows, "field_candidates", errors)
    counts["field_candidates"] = len(candidate_index)
    for index, row in enumerate(candidate_rows):
        path = f"field_candidates[{index}]"
        if is_community_qa_role(row.get("semantic_role")):
            err(errors, "LST-QA-002", f"{path}.semantic_role", "Community Q&A is read-only and cannot be a brand-authored candidate")
        field_id = row.get("field_resolution_id")
        field = field_index.get(field_id)
        if field is None:
            err(errors, "LST-CANDIDATE-001", f"{path}.field_resolution_id", "unknown field resolution")
        elif field.get("status") != "RESOLVED" or not all(field.get(k) is True for k in ("exists", "editable", "applicable")):
            err(errors, "LST-CANDIDATE-002", f"{path}.field_resolution_id", "cannot target unavailable or non-editable field")
        elif row.get("semantic_role") != field.get("semantic_role"):
            err(errors, "LST-CANDIDATE-010", f"{path}.semantic_role", "must match the resolved field semantic role")
        if field is not None and not application_scope_is_subset(row.get("application_scope"), field.get("application_scope")):
            err(errors, "LST-CANDIDATE-011", f"{path}.application_scope", "expands the resolved field scope")
        candidate_scope = row.get("application_scope")
        candidate_children = scope_set(candidate_scope, "child_asins")
        relevant_variants = [
            variant for variant in variant_rows
            if variant.get("child_asin") in candidate_children
        ]
        for scope_key, variant_key in (
            ("parent_asins", "parent_asin"), ("packs", "pack"),
            ("colors", "color"), ("sizes", "size"),
        ):
            expected_values = {
                variant.get(variant_key) for variant in relevant_variants
                if nonempty(variant.get(variant_key))
            }
            if scope_set(candidate_scope, scope_key) != expected_values:
                err(
                    errors, "LST-CANDIDATE-012", f"{path}.application_scope.{scope_key}",
                    "must exactly bind the selected child topology dimensions",
                )
        if row.get("semantic_role") == "subtitle" and field and field.get("canonical_key") == "subtitle":
            err(errors, "LST-CANDIDATE-003", path, "subtitle semantic role has not been resolved to a real field")
        if not nonempty(row.get("value")):
            err(errors, "LST-CANDIDATE-004", f"{path}.value", "consumer/backend candidate value is required")
        validate_application_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        require_refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors)
        require_refs(row.get("claim_ids", []), set(claim_index), f"{path}.claim_ids", errors)
        if row.get("content_status") not in {"DRAFT", "CONDITIONAL", "FINAL", "HOLD"}:
            err(errors, "LST-CANDIDATE-005", f"{path}.content_status", "unsupported status")
        if row.get("content_status") == "FINAL":
            for fact_id in row.get("fact_ids", []):
                fact = fact_index.get(fact_id, {})
                if fact.get("verification_status") != "VERIFIED" or fact.get("content_status") != "PUBLISHABLE":
                    err(errors, "LST-CANDIDATE-006", path, f"FINAL content uses non-publishable fact {fact_id}")
                if not application_scope_is_subset(row.get("application_scope"), fact.get("application_scope")):
                    err(errors, "LST-CANDIDATE-008", path, f"candidate expands fact scope {fact_id}")
            for claim_id in row.get("claim_ids", []):
                claim = claim_index.get(claim_id, {})
                if claim.get("support_status") != "SUPPORTED" or claim.get("content_status") != "PUBLISHABLE":
                    err(errors, "LST-CANDIDATE-007", path, f"FINAL content uses non-publishable claim {claim_id}")
                if not application_scope_is_subset(row.get("application_scope"), claim.get("application_scope")):
                    err(errors, "LST-CANDIDATE-009", path, f"candidate expands claim scope {claim_id}")

    validate_handoff(
        bundle, source_index, fact_index, claim_index, conflict_index,
        variant_index, requirement_index, assignment_index, errors,
    )
    validate_publication(bundle, source_index, field_index, fact_index, claim_index, errors, warnings)

    gates = bundle.get("gates")
    if not isinstance(gates, dict):
        err(errors, "LST-GATE-001", "gates", "must be an object")
        gates = {}
    required_gate_keys = {"identity", "schema_ptd", "data_plane", "truth_variants", "p0_coverage", "candidate_qa", "publication", "live_readback"}
    if set(gates) != required_gate_keys:
        err(errors, "LST-GATE-002", "gates", f"must contain exactly {sorted(required_gate_keys)}")
    for key, value in gates.items():
        if value not in {"NOT_RUN", "PASS", "FAIL", "HOLD", "NOT_APPLICABLE"}:
            err(errors, "LST-GATE-003", f"gates.{key}", "unsupported gate status")

    open_conflicts = [row.get("id") for row in conflict_rows if row.get("status") in {"OPEN", "EVIDENCE_REQUESTED", "BLOCKED"}]
    conclusion = project.get("conclusion")
    if conclusion in {"PASS", "LIVE_PASS"}:
        if open_conflicts:
            err(errors, "LST-CONCLUSION-001", "project.conclusion", f"cannot PASS with open conflicts {open_conflicts}")
        for key in ("identity", "schema_ptd", "data_plane", "truth_variants", "p0_coverage", "candidate_qa"):
            if gates.get(key) != "PASS":
                err(errors, "LST-CONCLUSION-002", f"gates.{key}", "must PASS before project PASS")
        if p0_total != p0_pass:
            err(errors, "LST-CONCLUSION-003", "project.conclusion", "cannot PASS with incomplete P0 coverage")
        for conflict in conflict_rows:
            if conflict.get("status") == "ACCEPTED_RISK" and (
                conflict.get("affected_fact_ids")
                or conflict.get("affected_claim_ids")
                or conflict.get("affected_child_asins")
                or conflict.get("severity") in {"HIGH", "CRITICAL"}
            ):
                err(errors, "LST-CONFLICT-005", "project.conclusion", "truth-, child-, or high-severity conflicts cannot be accepted into PASS")
    if conclusion == "LIVE_PASS":
        if boundary not in {"authorized_submission", "rollback_only"}:
            err(errors, "LST-LIVE-001", "project.conclusion", "LIVE_PASS requires an authorized write boundary")
        if gates.get("publication") != "PASS" or gates.get("live_readback") != "PASS":
            err(errors, "LST-LIVE-002", "gates", "publication and live readback gates must PASS")
    if boundary == "authorized_submission" and gates.get("publication") != "PASS":
        err(errors, "LST-AUTH-034", "gates.publication", "authorized submission requires the publication gate to PASS")

    if boundary in {"read_only", "local_candidate"} and project.get("mode") == "publish_support":
        warn(warnings, "LST-AUTH-W01", "project.mode", "publish_support mode has no write authority under current boundary")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "parent_bundle_sha256": canonical_parent_hash(bundle),
        "contract_status": "LEGACY_LOCAL_CONTRACT",
        "result_level": "LEGACY_LOCAL_CONTRACT",
        "publication_authorized": False,
        "live_conclusion_recognized": False,
    }


def validate_handoff(
    bundle: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    fact_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
    conflict_index: dict[str, dict[str, Any]],
    variant_index: dict[str, dict[str, Any]],
    requirement_index: dict[str, dict[str, Any]],
    assignment_index: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    handoff = bundle.get("enriched_content_handoff")
    if not isinstance(handoff, dict):
        err(errors, "LST-HANDOFF-001", "enriched_content_handoff", "must be an object")
        return
    exact_keys(handoff, HANDOFF_KEYS, "enriched_content_handoff", "LST-HANDOFF-021", errors)
    if handoff.get("contract_version") != "1.0":
        err(errors, "LST-HANDOFF-002", "enriched_content_handoff.contract_version", "must equal 1.0")
    status = handoff.get("status")
    if status not in {"NOT_APPLICABLE", "FROZEN", "CONDITIONAL", "BLOCKED"}:
        err(errors, "LST-HANDOFF-003", "enriched_content_handoff.status", "unsupported status")
        return
    if status == "NOT_APPLICABLE":
        populated_scalar_keys = (
            "snapshot_id", "parent_project_id", "parent_bundle_sha256", "marketplace",
            "locale", "product_type", "created_at", "owner", "checksum",
        )
        if any(nonempty(handoff.get(key)) for key in populated_scalar_keys):
            err(errors, "LST-HANDOFF-022", "enriched_content_handoff", "NOT_APPLICABLE handoff cannot carry frozen identifiers")
        for key in (
            "variant_row_ids", "fact_ids", "claim_ids", "blocked_claim_ids",
            "conflict_ids", "source_ids", "requested_content_types",
            "decision_requirements", "capability_snapshot_ids",
        ):
            if handoff.get(key) != []:
                err(errors, "LST-HANDOFF-023", f"enriched_content_handoff.{key}", "must be empty when NOT_APPLICABLE")
        empty_scope = {"parent_asins": [], "child_asins": [], "packs": [], "colors": [], "sizes": []}
        if handoff.get("application_scope") != empty_scope:
            err(errors, "LST-HANDOFF-024", "enriched_content_handoff.application_scope", "must be empty when NOT_APPLICABLE")
        return
    for key in ("snapshot_id", "parent_project_id", "parent_bundle_sha256", "marketplace", "locale", "product_type", "created_at", "owner", "checksum"):
        if not nonempty(handoff.get(key)):
            err(errors, "LST-HANDOFF-004", f"enriched_content_handoff.{key}", "is required")
    if handoff.get("parent_project_id") != bundle.get("project", {}).get("project_id"):
        err(errors, "LST-HANDOFF-005", "enriched_content_handoff.parent_project_id", "does not match project")
    expected_hash = canonical_parent_hash(bundle)
    if handoff.get("parent_bundle_sha256") != expected_hash:
        err(errors, "LST-HANDOFF-006", "enriched_content_handoff.parent_bundle_sha256", f"must equal canonical bundle hash {expected_hash}")
    scope = bundle.get("scope", {})
    if handoff.get("marketplace") != scope.get("marketplace") or handoff.get("locale") != scope.get("locale"):
        err(errors, "LST-HANDOFF-007", "enriched_content_handoff", "marketplace/locale mismatch")
    if handoff.get("product_type") != bundle.get("catalog_context", {}).get("product_type"):
        err(errors, "LST-HANDOFF-008", "enriched_content_handoff.product_type", "Product Type mismatch")
    if parse_timestamp(handoff.get("created_at")) is None:
        err(errors, "LST-HANDOFF-025", "enriched_content_handoff.created_at", "must be a timezone-qualified ISO timestamp")
    expected_checksum = canonical_handoff_hash(handoff)
    if handoff.get("checksum") != expected_checksum:
        err(errors, "LST-HANDOFF-026", "enriched_content_handoff.checksum", f"must equal canonical handoff hash {expected_checksum}")
    validate_application_scope(handoff.get("application_scope"), "enriched_content_handoff.application_scope", scope, errors)
    require_refs(handoff.get("variant_row_ids", []), set(variant_index), "enriched_content_handoff.variant_row_ids", errors)
    require_refs(handoff.get("fact_ids", []), set(fact_index), "enriched_content_handoff.fact_ids", errors)
    require_refs(handoff.get("claim_ids", []), set(claim_index), "enriched_content_handoff.claim_ids", errors)
    require_refs(handoff.get("blocked_claim_ids", []), set(claim_index), "enriched_content_handoff.blocked_claim_ids", errors)
    require_refs(handoff.get("conflict_ids", []), set(conflict_index), "enriched_content_handoff.conflict_ids", errors)
    require_refs(handoff.get("source_ids", []), set(source_index), "enriched_content_handoff.source_ids", errors)
    for source_id in handoff.get("source_ids", []):
        if source_index.get(source_id, {}).get("status") != "USABLE":
            err(errors, "LST-HANDOFF-027", "enriched_content_handoff.source_ids", f"source {source_id} is not usable")
    if not unique_strings(handoff.get("requested_content_types", [])) or not set(handoff.get("requested_content_types", [])).issubset(CONTENT_TYPES):
        err(errors, "LST-HANDOFF-009", "enriched_content_handoff.requested_content_types", "must use the closed A+ content-type set")
    elif status == "FROZEN" and not handoff.get("requested_content_types"):
        err(errors, "LST-HANDOFF-041", "enriched_content_handoff.requested_content_types", "FROZEN handoff must request at least one A+ content type")
    if "COMMUNITY_QA" in handoff.get("requested_content_types", []):
        err(errors, "LST-QA-001", "enriched_content_handoff.requested_content_types", "Community Q&A cannot be a brand-authored output")
    if handoff.get("maximum_output") not in {"conditional_wireframe", "candidate_package", "preflight_package", "publish_support_package"}:
        err(errors, "LST-HANDOFF-010", "enriched_content_handoff.maximum_output", "unsupported maximum output")
    reqs = handoff.get("decision_requirements")
    if not isinstance(reqs, list):
        err(errors, "LST-HANDOFF-011", "enriched_content_handoff.decision_requirements", "must be an array")
        return
    prohibited = handoff.get("prohibited_actions")
    if not unique_strings(prohibited) or not {"modify_parent_truth", "expand_application_scope", "online_submission"}.issubset(set(prohibited or [])):
        err(errors, "LST-HANDOFF-028", "enriched_content_handoff.prohibited_actions", "mandatory parent protections are missing")
    if not unique_strings(handoff.get("capability_snapshot_ids", [])):
        err(errors, "LST-HANDOFF-029", "enriched_content_handoff.capability_snapshot_ids", "must be a unique string array")
    if status == "FROZEN" and not handoff.get("capability_snapshot_ids"):
        err(errors, "LST-HANDOFF-030", "enriched_content_handoff.capability_snapshot_ids", "FROZEN handoff requires a capability snapshot reference")

    expected_variant_ids = {
        variant_id for variant_id, variant in variant_index.items()
        if variant.get("child_asin") in scope_set(handoff.get("application_scope"), "child_asins")
    }
    if set(handoff.get("variant_row_ids", [])) != expected_variant_ids:
        err(errors, "LST-HANDOFF-031", "enriched_content_handoff.variant_row_ids", "must exactly cover handoff child topology rows")

    seen: set[str] = set()
    for index, row in enumerate(reqs):
        path = f"enriched_content_handoff.decision_requirements[{index}]"
        if not isinstance(row, dict):
            err(errors, "LST-HANDOFF-012", path, "must be an object")
            continue
        exact_keys(row, HANDOFF_REQUIREMENT_KEYS, path, "LST-HANDOFF-032", errors)
        req_id = row.get("id")
        if req_id in seen:
            err(errors, "LST-HANDOFF-013", f"{path}.id", "duplicate requirement")
        seen.add(req_id)
        parent_req = requirement_index.get(req_id)
        if parent_req is None:
            err(errors, "LST-HANDOFF-014", f"{path}.id", "unknown parent decision requirement")
            continue
        if row.get("assigned_surface") != "enriched_content":
            err(errors, "LST-HANDOFF-015", f"{path}.assigned_surface", "handoff requirements must be assigned to enriched_content")
        if row.get("priority") != parent_req.get("priority") or row.get("buyer_question") != parent_req.get("buyer_question"):
            err(errors, "LST-HANDOFF-016", path, "question or priority differs from parent requirement")
        require_refs(row.get("fact_ids", []), set(handoff.get("fact_ids", [])), f"{path}.fact_ids", errors)
        require_refs(row.get("claim_ids", []), set(handoff.get("claim_ids", [])), f"{path}.claim_ids", errors)
        validate_application_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        if row.get("application_scope") != parent_req.get("application_scope"):
            err(errors, "LST-HANDOFF-020", f"{path}.application_scope", "must exactly match the parent decision requirement scope")
        if set(row.get("fact_ids", [])) != set(parent_req.get("fact_ids", [])) or set(row.get("claim_ids", [])) != set(parent_req.get("claim_ids", [])):
            err(errors, "LST-HANDOFF-033", path, "fact/claim references must exactly match the parent decision requirement")
        if row.get("early_disclosure_required") is not parent_req.get("early_disclosure_required"):
            err(errors, "LST-HANDOFF-034", f"{path}.early_disclosure_required", "must exactly match the parent decision requirement")
        if row.get("native_answer_required") not in {True, False}:
            err(errors, "LST-HANDOFF-035", f"{path}.native_answer_required", "must be boolean")
        elif row.get("priority") == "P0" and row.get("native_answer_required") is not True:
            err(errors, "LST-HANDOFF-042", f"{path}.native_answer_required", "P0 enriched-content requirement must retain the native-answer gate")
        upstream_ref = row.get("upstream_primary_carrier_ref")
        if row.get("early_disclosure_required") is True:
            assignment = assignment_index.get(upstream_ref)
            if not nonempty(upstream_ref) or assignment is None:
                err(errors, "LST-HANDOFF-036", f"{path}.upstream_primary_carrier_ref", "must reference an upstream assignment")
            elif (
                assignment.get("requirement_id") != req_id
                or assignment.get("status") != "PASS"
                or assignment.get("primary_carrier_kind") not in LEGAL_P0_CARRIERS
                or assignment.get("primary_surface") in {"media", "backend_search_terms", "enriched_content"}
                or assignment.get("application_scope") != row.get("application_scope")
            ):
                err(errors, "LST-HANDOFF-037", f"{path}.upstream_primary_carrier_ref", "does not reference a legal early native disclosure")
        elif not isinstance(upstream_ref, str) or upstream_ref:
            err(errors, "LST-HANDOFF-038", f"{path}.upstream_primary_carrier_ref", "must be an empty string when early disclosure is not required")
        if row.get("status") != parent_req.get("status"):
            err(errors, "LST-HANDOFF-039", f"{path}.status", "must exactly match the parent decision requirement")
        if row.get("status") not in {"READY", "HOLD", "CONFLICT", "OMITTED_WITH_REASON"}:
            err(errors, "LST-HANDOFF-017", f"{path}.status", "unsupported status")
    expected_requirement_ids = {
        req_id for req_id, requirement in requirement_index.items()
        if requirement.get("assigned_surface") == "enriched_content"
    }
    if seen != expected_requirement_ids:
        err(errors, "LST-HANDOFF-040", "enriched_content_handoff.decision_requirements", "must exactly cover parent requirements assigned to enriched_content")
    if status == "FROZEN":
        blocked = set(handoff.get("claim_ids", [])) & set(handoff.get("blocked_claim_ids", []))
        if blocked:
            err(errors, "LST-HANDOFF-018", "enriched_content_handoff", f"FROZEN handoff includes blocked claims {sorted(blocked)}")
        for conflict_id in handoff.get("conflict_ids", []):
            conflict = conflict_index.get(conflict_id, {})
            if conflict.get("status") in {"OPEN", "EVIDENCE_REQUESTED", "BLOCKED"} or (
                conflict.get("status") == "ACCEPTED_RISK"
                and (conflict.get("affected_fact_ids") or conflict.get("affected_claim_ids") or conflict.get("affected_child_asins"))
            ):
                err(errors, "LST-HANDOFF-019", "enriched_content_handoff", "FROZEN handoff includes an open conflict")



def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Amazon Listing Bundle v1.0 legacy or v1.1 current")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--aplus-result", type=Path)
    parser.add_argument("--print-parent-hash", action="store_true")
    args = parser.parse_args()
    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        # Preserve the historical CLI flag without reading or executing a
        # sibling bundle. Its presence becomes a fail-closed sentinel; the
        # package coordinator is the suite's only cross-bundle path.
        aplus = {} if args.aplus_result else None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [f"[LST-IO-001] {exc}"], "warnings": [], "counts": {}}, ensure_ascii=False, indent=2))
        return 2
    result = validate_listing_bundle(bundle, aplus, aplus_source_path=args.aplus_result)
    if args.print_parent_hash:
        print(result.get("parent_bundle_sha256", ""))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
