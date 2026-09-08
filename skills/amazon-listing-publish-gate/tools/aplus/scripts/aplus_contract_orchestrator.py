#!/usr/bin/env python3
"""Validate the encoded structural invariants of Amazon A+ bundle v1.1-v1.3.

The validator can reject unsupported structure, cross-scope reuse, unsafe
publish envelopes, and invalid attribution. It cannot prove product truth,
policy currency, authorization authenticity, visual fidelity, or live render.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from aplus_entry_domain import (
    derive_result_level,
    required_pass_gate_ids,
    validator_exit_code,
)
from aplus_io import read_json_document, read_local_parent_bundle
from aplus_publication_reports import (
    build_publication_report,
    build_readback_coverage_report,
    build_readback_row_report,
)
from aplus_bundle_content_domain import validate_content
from aplus_bundle_foundation_domain import validate_foundation
from aplus_bundle_governance_domain import validate_governance
from aplus_v13_lineage import canonical_handoff_hash as _lineage_handoff_hash
from aplus_v13_domain import (
    MIRROR_SOURCE_TYPES,
    expected_decision_pairs,
    structural_valid_v13,
    validate_category_adapter,
    validate_delta_lineage,
)
from aplus_v13_reports import (
    build_coverage_report,
    build_discovery_report,
    build_fact_evidence_report,
    build_handoff_report,
)


SCHEMA_VERSIONS = {"1.1", "1.2", "1.3"}
ROOT_KEYS_V11 = {
    "schema_version", "project", "scope", "platform_limits", "sources", "facts",
    "claims", "decision_map", "competitor_insights", "positioning", "conflicts",
    "variants", "modules", "assets", "publish_authorization", "baseline",
    "change_set", "rollback", "live_readback", "gates", "experiments",
}
V12_ONLY_KEYS = {
    "workflow_context", "enriched_content_handoff", "capability_snapshots",
    "decision_answer_units", "carriers", "coverage_summary",
    "delta_evidence_requests",
}
ROOT_KEYS_V12 = ROOT_KEYS_V11 | V12_ONLY_KEYS
V13_ONLY_KEYS = {
    "discovery", "decision_denominator_snapshot", "canonical_assertions",
    "component_result", "category_adapter", "voc_insights",
}
ROOT_KEYS_V13 = ROOT_KEYS_V12 | V13_ONLY_KEYS
MODES = {"audit", "plan", "rebuild", "preflight_qa", "publish_support"}
TARGET_TYPES = {"live_asin", "prelaunch_sku", "hypothetical_fixture"}
CONCLUSIONS = {"PASS", "CONDITIONAL_PASS", "BLOCKED", "NO_VALID_CONCLUSION", "ROLLBACK"}
IDENTIFIER_TYPES = {"asin", "sku", "url", "unknown"}
IDENTITY_STATUSES = {"UNVERIFIED", "VERIFIED_PARENT", "VERIFIED_CHILD", "CONFLICT", "NOT_APPLICABLE"}
SCOPE_STATUSES = {"UNVERIFIED", "PARTIAL", "FROZEN", "CONFLICT"}
CONDITIONAL_STATUSES = {"NOT_EVALUATED", "ACTIVE", "CLEARED", "BLOCKED"}
MAXIMUM_WORK_LEGACY = {
    "audit_only", "audit_and_gap_report", "audit_gap_report_and_conditional_wireframe",
    "conditional_copy", "full_production",
}
MAXIMUM_WORK_V13 = {
    "audit_only", "audit_and_gap_report", "strategy_dependency_only", "full_production",
}
# Kept as the legacy default for v1.1/v1.2 domain calls. v1.3 replaces this
# value in the per-validation ops map before content validation.
MAXIMUM_WORK = MAXIMUM_WORK_LEGACY
CONTENT_STATUSES = {"CONDITIONAL_DRAFT", "FINAL_CANDIDATE", "APPROVED", "PUBLISHED", "RETIRED"}
FINAL_CONTENT_STATUSES = {"FINAL_CANDIDATE", "APPROVED", "PUBLISHED"}
FETCH_STATUSES = {
    "ok", "partial", "blocked", "historical", "not_accessed", "not_attempted",
    "missing_attachment", "described_not_available", "skipped_by_scope",
}
EVIDENCE_TYPES = {
    "OFFICIAL_PLATFORM_RULE", "DOCUMENTED_SPEC", "PHYSICAL_OBSERVED", "PHYSICAL_TEST",
    "BACKEND_OBSERVED", "PUBLIC_OBSERVED", "VERIFIED_ACCOUNT_DATA", "OWNER_STATED",
    "COMPETITOR_ONLY", "VOC_ONLY", "INFERENCE",
} | MIRROR_SOURCE_TYPES
SOURCE_TYPES = EVIDENCE_TYPES
EVIDENCE_STRENGTHS = {"E0", "E1", "E2", "E3", "E4"}
PUBLISH_STATUSES = {"PUBLISHABLE", "HOLD", "CONFLICT", "PROHIBITED"}
RISK_TYPES = {
    "ordinary", "performance", "comparative", "environmental", "health", "safety",
    "certification", "quantified",
}
HIGH_RISK_TYPES = RISK_TYPES - {"ordinary"}
UNSUPPORTED_CONSUMER_EVIDENCE = {
    "OFFICIAL_PLATFORM_RULE", "PUBLIC_OBSERVED", "OWNER_STATED", "COMPETITOR_ONLY",
    "VOC_ONLY", "INFERENCE",
}
DECISION_STATUSES = {"NOT_STARTED", "UNKNOWN", "SUPPORTED", "HOLD", "CONFLICT"}
COMPETITOR_ROLES = {"direct", "premium_anchor", "value_anchor", "mechanism_peer", "adjacent_alternative", "status_quo"}
COMPETITOR_STATUSES = {"PROVISIONAL", "FROZEN", "RETIRED", "BLOCKED"}
CONFLICT_STATUSES = {"OPEN", "EVIDENCE_REQUESTED", "RESOLVED", "ACCEPTED_LIMIT", "BLOCKED"}
VARIANT_STATUSES = {"UNVERIFIED", "VERIFIED", "PLANNED", "APPLIED", "LIVE_PASS", "CONFLICT", "BLOCKED", "RETIRED"}
PRIORITIES = {"P0", "P1", "P2"}
QA_STATUSES = {"NOT_STARTED", "HOLD", "PASS", "FAILED", "BLOCKED"}
GATE_STATUSES = {"NOT_STARTED", "PASS", "HOLD", "BLOCKED", "FAILED", "ROLLBACK"}
CONTENT_ELIGIBILITY = {"UNVERIFIED", "BASIC", "PREMIUM", "INELIGIBLE", "BLOCKED"}
SYNTHETIC_PERSON = {"yes", "no", "unknown"}
GENERATION_METHODS = {
    "unknown", "real_photography", "composite_with_real_product",
    "ai_generated_person_or_setting", "ai_assisted_edit",
}
AUTHORIZATION_STATUSES = {"NOT_AUTHORIZED", "REQUESTED", "AUTHORIZED", "EXPIRED", "REVOKED", "OUT_OF_SCOPE"}
AUTHORIZED_ACTIONS = {"edit", "submit", "apply", "publish", "rollback"}
BASELINE_STATUSES = {"NOT_FROZEN", "FROZEN", "STALE", "CONFLICT"}
CONCURRENT_EDIT_STATUSES = {"UNKNOWN", "FROZEN", "COORDINATED", "CONFLICT"}
CHANGE_APPROVAL_STATUSES = {"NOT_APPROVED", "APPROVED", "REJECTED", "EXPIRED"}
CHANGE_STATUSES = {"PLANNED", "APPLIED", "VERIFIED", "ROLLED_BACK", "FAILED"}
ROLLBACK_STATUSES = {"NOT_READY", "READY", "TRIGGERED", "COMPLETED", "FAILED", "BLOCKED"}
READBACK_PHASES = {"FIRST_READBACK", "FOLLOWUP_READBACK", "FINAL_READBACK", "ROLLBACK_READBACK"}
READBACK_FIELD_STATUSES = {"UNKNOWN", "PASS", "MISMATCH", "NOT_VISIBLE", "NOT_APPLICABLE", "FETCH_BLOCKED"}
READBACK_STATUSES = {"NOT_STARTED", "PARTIAL", "PASS", "MISMATCH", "BLOCKED", "FOLLOWUP_REQUIRED"}
READBACK_FIELDS = {
    "identity", "quantity", "color", "size_or_capacity", "included_items", "copy",
    "assets", "alt", "module_order",
}
EXPERIMENT_TYPES = {"single_variable", "multi_attribute_package", "descriptive_before_after"}
EXPERIMENT_ELIGIBILITY = {"UNVERIFIED", "ELIGIBLE", "INELIGIBLE", "BLOCKED"}
EXPERIMENT_STATUSES = {"NOT_STARTED", "READY", "RUNNING", "PAUSED", "COMPLETE", "INVALID", "CANCELLED"}
ATTRIBUTION_BOUNDARIES = {"ELEMENT_LEVEL", "PACKAGE_LEVEL", "DESCRIPTIVE_ONLY"}
WORKFLOW_MODES = {"standalone", "embedded"}
EXECUTION_BOUNDARIES = {"read_only", "local_candidate", "authorized_submission", "rollback_only"}
HANDOFF_STATUSES = {"NOT_APPLICABLE", "FROZEN", "CONDITIONAL", "BLOCKED"}
HANDOFF_STATUSES_V13 = {
    "NOT_APPLICABLE", "DRAFT", "FROZEN", "RESULT_RECEIVED",
    "RECONCILIATION_REQUIRED", "SUPERSEDED",
}
HANDOFF_MAXIMUM_OUTPUTS_LEGACY = {
    "conditional_wireframe", "candidate_package", "preflight_package", "publish_support_package",
}
HANDOFF_MAXIMUM_OUTPUTS_V13 = {
    "strategy_dependency_only", "candidate_package", "preflight_package", "publish_support_package",
}
A_PLUS_CONTENT_TYPES = {"BASIC_A_PLUS", "PREMIUM_A_PLUS", "BRAND_STORY"}
CAPABILITY_STATUSES = {"CURRENT", "STALE", "BLOCKED"}
CARRIER_TYPES = {"native_text", "static_visual", "motion_video", "interactive_detail", "structured_comparison", "brand_authored_qa"}
COVERAGE_ROLES = {"PRIMARY_NATIVE_ANSWER", "SUPPORTING_PROOF", "PROOF_ONLY", "DECORATIVE"}
COVERAGE_STATUSES = {"NOT_EVALUATED", "PASS", "GAP", "HOLD", "CONFLICT"}
DELTA_STATUSES = {"OPEN", "RESOLVED", "CANCELLED"}
DISCOVERY_MODES = {"standalone", "parent_bound"}
EVIDENCE_PASS_STATUSES = {"NOT_STARTED", "PARTIAL", "COMPLETE", "BLOCKED"}
DISCOVERY_CLOSURE_STATUSES = {
    "NOT_STARTED", "IN_PROGRESS", "PASS", "CONDITIONAL", "BLOCKED",
    "NOT_REQUIRED_WITH_REASON",
}
DISCOVERY_PHASES = {"TRUTH", "POSITIONING"}
DISCOVERY_STAGE_GATE_KEYS = {
    "id", "stage", "status", "result", "evidence_source_ids",
    "record_refs", "reason", "closed_at", "owner",
}
DISCOVERY_STAGE_TYPES = (
    "RECONNAISSANCE", "PRODUCT_TRUTH", "ROUND_2",
    "PRODUCT_INTENT_BRIEF", "ONE_BET",
)
DISCOVERY_STAGE_STATUSES = {
    "NOT_STARTED", "IN_PROGRESS", "PASS", "NOT_REQUIRED_WITH_REASON", "BLOCKED",
}
DISCOVERY_EFFECTS = {
    "AUDIENCE", "SCENARIO", "PROBLEM", "PROMISE", "BOUNDARY",
    "VARIANT", "EVIDENCE", "FIELD_ALLOCATION", "STRATEGIC_SELECTION",
}
DISCOVERY_DISTILLATION_TYPES = {
    "PRODUCT_TRUTH", "ROUND_2_SYNTHESIS", "PRODUCT_INTENT_BRIEF", "ONE_BET_SELECTION",
}
PRODUCT_INTENT_PAYLOAD_KEYS = {
    "original_problem", "prior_alternative", "chosen_form", "deliberate_tradeoff",
    "intended_mechanism", "longitudinal_observation", "alternative_explanations",
    "current_version_continuity", "current_choice",
}
ONE_BET_PAYLOAD_KEYS = {
    "selected_route_id", "hero_moment", "closest_alternative", "desired_progress",
    "mechanism", "material_boundary", "rejected_route_ids", "rejected_route_reasons",
    "proof_status", "reversibility_test", "route_registry",
}
ROUTE_REGISTRY_KEYS = {
    "route_id", "core_user_or_state", "hero_moment", "closest_alternative",
    "desired_progress", "mechanism", "material_boundary", "proof_status",
    "decision_consequence",
}
ROUTE_PROOF_STATUSES = {
    "PROVED", "PROOF_TASK_BOUND", "HYPOTHESIS_ONLY", "UNSUPPORTED",
}
SELECTABLE_ROUTE_PROOF_STATUSES = {"PROVED", "PROOF_TASK_BOUND", "HYPOTHESIS_ONLY"}
VOC_INSIGHT_KEYS = {
    "id", "observation", "buyer_question", "use_path", "decision_implication",
    "source_ids", "marketplace", "locale", "observed_at", "fetch_status",
    "status", "target_product_proof_prohibited", "owner",
}
RESPONSE_CLASSES = {"FACT_LEAD", "STRATEGIC_CHOICE", "HYPOTHESIS", "UNKNOWN_SKIP"}
EVIDENCE_ACTION_STATUSES = {"OPEN", "RESOLVED", "CANCELLED"}
DENOMINATOR_STATUSES = {"NOT_STARTED", "DRAFT", "FROZEN", "BLOCKED"}
DENOMINATOR_SOURCES = {"STANDALONE", "PARENT_HANDOFF"}
ASSERTION_STATUSES = {"PUBLISHABLE", "HOLD", "CONFLICT", "PROHIBITED"}
ATOM_STATUSES = {"READY", "HOLD", "CONFLICT", "OMITTED_WITH_REASON"}
COMPONENT_RESULT_STATUSES = {"NOT_EVALUATED", "IN_PROGRESS", "COMPONENT_PASS", "DELTA_REQUIRED", "BLOCKED", "CONDITIONAL"}
FACT_CLASSES = {
    "UNCLASSIFIED", "GENERAL", "IDENTITY_MAPPING", "ACCOUNT_OPERATIONAL_STATE",
    "PTD_SCHEMA", "PHYSICAL_PRODUCT", "PERFORMANCE", "FRONTEND_LIVE_STATE",
}
FORBIDDEN_V12_KEYS = {
    "minimum_total_words", "min_total_words", "native_text_min_chars", "min_total_chars",
    "keyword_density", "cosmo_score", "alexa_coverage", "cdq_weight",
    "fixed_wait_days", "semantic_score",
}

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2}))?$")
AMAZON_SUFFIXES = {
    "com", "ca", "de", "fr", "it", "es", "nl", "pl", "se", "sg", "in",
    "ae", "sa", "be", "co.uk", "co.jp", "com.au", "com.br", "com.mx", "com.tr",
}
SCOPE_SET_FIELDS = ("marketplaces", "locales", "parent_asins", "child_asins", "packs", "colors", "sizes_or_capacities")
ALLOWED_ROOT_EXTRAS = {"record_templates"}
OUTPUT_RANK = {
    "conditional_wireframe": 0,
    "strategy_dependency_only": 0,
    "candidate_package": 1,
    "preflight_package": 2,
    "publish_support_package": 3,
}
MODE_MINIMUM_OUTPUT = {
    "audit": 0,
    "plan": 0,
    "rebuild": 1,
    "preflight_qa": 2,
    "publish_support": 3,
}


def is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_substantive_human_text(value: Any) -> bool:
    """Reject empty/placeholder summaries without treating prose as Gate authority."""
    if not isinstance(value, str):
        return False
    text = " ".join(value.strip().split())
    normalized = text.casefold().replace(" ", "")
    if normalized in {"x", "xx", "tbd", "todo", "n/a", "na", "unknown", "placeholder", "已完成", "待定", "未知"}:
        return False
    alphanumeric = [char.casefold() for char in text if char.isalnum()]
    return len(text) >= 12 and len(set(alphanumeric)) >= 4


def normalized_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().split())


def require_mapping(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path}: required object")
        return {}
    return value


def require_text(obj: dict[str, Any], key: str, path: str, errors: list[str]) -> str:
    value = obj.get(key)
    if not is_text(value):
        errors.append(f"{path}.{key}: required non-empty string")
        return ""
    return value.strip()


def require_string(obj: dict[str, Any], key: str, path: str, errors: list[str]) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        errors.append(f"{path}.{key}: required string")
        return ""
    return value.strip()


def require_list(obj: dict[str, Any], key: str, path: str, errors: list[str]) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        errors.append(f"{path}.{key}: required array")
        return []
    return value


def require_enum(
    obj: dict[str, Any], key: str, path: str, allowed: set[str], errors: list[str],
    *, lower: bool = False,
) -> str:
    raw = require_text(obj, key, path, errors)
    value = raw.lower() if lower else raw
    if value and value not in allowed:
        errors.append(f"{path}.{key}: unsupported value {raw!r}; expected one of {sorted(allowed)!r}")
    return value


def check_iso(value: str, path: str, errors: list[str], *, optional: bool = False) -> None:
    if not value and optional:
        return
    if not value or not ISO_RE.fullmatch(value):
        errors.append(f"{path}: expected exact YYYY-MM-DD or timezone-qualified ISO timestamp")
        return
    try:
        if "T" in value:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            date.fromisoformat(value)
    except ValueError:
        errors.append(f"{path}: invalid calendar date or timestamp")


def check_asin(value: str, path: str, errors: list[str], *, optional: bool = False) -> None:
    if not value and optional:
        return
    if not value or not ASIN_RE.fullmatch(value):
        errors.append(f"{path}: expected a 10-character uppercase alphanumeric ASIN")


def string_set(values: list[Any], path: str, errors: list[str], *, nonempty: bool = False) -> set[str]:
    result: set[str] = set()
    if nonempty and not values:
        errors.append(f"{path}: at least one value required")
    for index, raw in enumerate(values):
        if not is_text(raw):
            errors.append(f"{path}[{index}]: required non-empty string")
            continue
        value = raw.strip()
        if value in result:
            errors.append(f"{path}[{index}]: duplicate value {value!r}")
        result.add(value)
    return result


def unique_rows(rows: list[Any], path: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(rows):
        row_path = f"{path}[{index}]"
        row = require_mapping(raw, row_path, errors)
        row_id = require_text(row, "id", row_path, errors)
        if row_id in result:
            errors.append(f"{row_path}.id: duplicate id {row_id!r}")
        elif row_id:
            result[row_id] = row
    return result


def validate_other_dimensions(value: Any, path: str, errors: list[str]) -> dict[str, set[str]]:
    raw = require_mapping(value, path, errors)
    result: dict[str, set[str]] = {}
    for key, values in raw.items():
        if not is_text(key):
            errors.append(f"{path}: dimension names must be non-empty strings")
            continue
        if not isinstance(values, list):
            errors.append(f"{path}.{key}: required array")
            continue
        result[key] = string_set(values, f"{path}.{key}", errors, nonempty=True)
    return result


def validate_top_scope(value: Any, path: str, errors: list[str]) -> tuple[dict[str, Any], str, set[str]]:
    raw = require_mapping(value, path, errors)
    status = require_enum(raw, "status", path, SCOPE_STATUSES, errors)
    result: dict[str, Any] = {}
    for key in SCOPE_SET_FIELDS:
        result[key] = string_set(require_list(raw, key if key != "child_asins" else "intended_child_asins", path, errors), f"{path}.{key if key != 'child_asins' else 'intended_child_asins'}", errors)
    result["other"] = validate_other_dimensions(raw.get("other_dimensions"), f"{path}.other_dimensions", errors)
    source_ids = string_set(require_list(raw, "source_ids", path, errors), f"{path}.source_ids", errors)
    for asin in result["parent_asins"] | result["child_asins"]:
        check_asin(asin, f"{path}.ASIN[{asin}]", errors)
    return result, status, source_ids


def validate_app_scope(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    raw = require_mapping(value, path, errors)
    marketplace = require_text(raw, "marketplace", path, errors)
    locale = require_text(raw, "locale", path, errors)
    parent = require_string(raw, "parent_asin", path, errors)
    result: dict[str, Any] = {
        "marketplaces": {marketplace} if marketplace else set(),
        "locales": {locale} if locale else set(),
        "parent_asins": {parent} if parent else set(),
    }
    for key in ("child_asins", "packs", "colors", "sizes_or_capacities"):
        result[key] = string_set(require_list(raw, key, path, errors), f"{path}.{key}", errors)
    result["other"] = validate_other_dimensions(raw.get("other_variants"), f"{path}.other_variants", errors)
    for asin in result["parent_asins"] | result["child_asins"]:
        check_asin(asin, f"{path}.ASIN[{asin}]", errors)
    return result


def ensure_scope_subset(
    child: dict[str, Any], parent: dict[str, Any], child_path: str,
    parent_label: str, errors: list[str],
) -> None:
    for key in SCOPE_SET_FIELDS:
        child_values = child.get(key, set())
        parent_values = parent.get(key, set())
        if child_values and not parent_values:
            errors.append(f"{child_path}.{key}: proving/container {parent_label} leaves this dimension unresolved")
        elif child_values and not child_values.issubset(parent_values):
            errors.append(f"{child_path}.{key}: values {sorted(child_values - parent_values)!r} exceed {parent_label} scope")
    for key, child_values in child.get("other", {}).items():
        parent_values = parent.get("other", {}).get(key, set())
        if not parent_values:
            errors.append(f"{child_path}.other_variants.{key}: not contained by {parent_label}")
        elif not child_values.issubset(parent_values):
            errors.append(f"{child_path}.other_variants.{key}: values exceed {parent_label} scope")


def require_complete_scope(
    scope: dict[str, Any], envelope: dict[str, Any], path: str,
    errors: list[str], *, require_child: bool,
) -> None:
    if require_child and not scope["child_asins"]:
        errors.append(f"{path}.child_asins: final live-target scope requires at least one child")
    for key in SCOPE_SET_FIELDS:
        if envelope.get(key) and not scope.get(key):
            errors.append(f"{path}.{key}: final/publishable scope must explicitly cover this frozen dimension")
    for key, values in envelope.get("other", {}).items():
        if values and not scope.get("other", {}).get(key):
            errors.append(f"{path}.other_variants.{key}: final/publishable scope must be explicit")


def is_official_amazon_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if host in {"developer-docs.amazon.com", "aboutamazon.com", "www.aboutamazon.com", "amazon.science", "www.amazon.science"}:
        return True
    for service in ("sellercentral", "sell", "advertising"):
        prefix = f"{service}.amazon."
        if host.startswith(prefix) and host[len(prefix):] in AMAZON_SUFFIXES:
            return True
    return False


def is_live_amazon_product_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    retail_suffix = ""
    for prefix in ("www.amazon.", "amazon."):
        if host.startswith(prefix):
            retail_suffix = host[len(prefix):]
            break
    if retail_suffix not in AMAZON_SUFFIXES:
        return False
    path = parsed.path.rstrip("/")
    return "/dp/" in path or "/gp/product/" in path


def amazon_product_asin(value: str) -> str:
    if not is_live_amazon_product_url(value):
        return ""
    parts = [part for part in urlsplit(value).path.split("/") if part]
    for marker in ("dp", "product"):
        for index, part in enumerate(parts[:-1]):
            if part.casefold() == marker:
                candidate = parts[index + 1].upper()
                return candidate if ASIN_RE.fullmatch(candidate) else ""
    return ""


def is_community_qa_label(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    tokens = set(normalized.split())
    audience = bool(tokens & {"community", "customer", "customers"})
    qa_signal = "qa" in tokens or "q&a" in value.casefold() or bool(tokens & {"question", "questions", "answer", "answers"})
    return audience and qa_signal


def parse_iso_moment(value: str) -> datetime | None:
    if not value or not ISO_RE.fullmatch(value):
        return None
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc)
        parsed_date = date.fromisoformat(value)
        return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
    except ValueError:
        return None


def canonical_parent_hash(bundle: dict[str, Any]) -> str:
    normalized = copy.deepcopy(bundle)
    handoff = normalized.get("enriched_content_handoff")
    if isinstance(handoff, dict):
        handoff["parent_bundle_sha256"] = ""
        handoff["checksum"] = ""
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_parent_bundle_reference(
    parent_bundle_ref: str,
    child_handoff: dict[str, Any],
    bundle_source_path: Path | None,
    child_fact_map: dict[str, dict[str, Any]],
    child_fact_scopes: dict[str, dict[str, Any]],
    child_claim_map: dict[str, dict[str, Any]],
    child_claim_scopes: dict[str, dict[str, Any]],
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    parent, reference_issue = read_local_parent_bundle(parent_bundle_ref, bundle_source_path)
    if reference_issue or parent is None:
        return False, [reference_issue or "cannot read local parent bundle"]

    expected_hash = canonical_parent_hash(parent)
    declared_hash = child_handoff.get("parent_bundle_sha256")
    if declared_hash != expected_hash:
        issues.append("parent_bundle_sha256 does not match the recomputed local parent hash")
    parent_handoff = parent.get("enriched_content_handoff")
    if parent_handoff != child_handoff:
        issues.append("embedded handoff is not an exact copy of the local frozen parent handoff")
    if not isinstance(parent_handoff, dict) or parent_handoff.get("status") != "FROZEN":
        issues.append("local parent bundle does not contain a FROZEN handoff")
    if parent.get("project", {}).get("status") == "SCAFFOLD":
        issues.append("local parent bundle is still a SCAFFOLD")

    parent_facts = {
        str(row.get("id")): row for row in parent.get("facts", [])
        if isinstance(row, dict) and is_text(row.get("id"))
    }
    parent_claims = {
        str(row.get("id")): row for row in parent.get("claims", [])
        if isinstance(row, dict) and is_text(row.get("id"))
    }
    handoff_marketplace = str(child_handoff.get("marketplace", ""))
    handoff_locale = str(child_handoff.get("locale", ""))

    def parent_scope(value: Any) -> dict[str, Any]:
        raw = value if isinstance(value, dict) else {}
        return {
            "marketplaces": {handoff_marketplace} if handoff_marketplace else set(),
            "locales": {handoff_locale} if handoff_locale else set(),
            "parent_asins": set(raw.get("parent_asins", [])) if isinstance(raw.get("parent_asins"), list) else set(),
            "child_asins": set(raw.get("child_asins", [])) if isinstance(raw.get("child_asins"), list) else set(),
            "packs": set(raw.get("packs", [])) if isinstance(raw.get("packs"), list) else set(),
            "colors": set(raw.get("colors", [])) if isinstance(raw.get("colors"), list) else set(),
            "sizes_or_capacities": set(raw.get("sizes", [])) if isinstance(raw.get("sizes"), list) else set(),
            "other": {},
        }

    def scope_within(child_scope: dict[str, Any], parent_row: dict[str, Any]) -> bool:
        allowed = parent_scope(parent_row.get("application_scope"))
        for key in SCOPE_SET_FIELDS:
            if child_scope.get(key) and not child_scope[key].issubset(allowed.get(key, set())):
                return False
        return True

    for fact_id in child_handoff.get("fact_ids", []):
        child_fact = child_fact_map.get(fact_id)
        parent_fact = parent_facts.get(fact_id)
        if child_fact is None or parent_fact is None:
            issues.append(f"fact {fact_id!r} is not present in both child and parent bundles")
            continue
        if normalized_text(child_fact.get("statement")) != normalized_text(parent_fact.get("statement")):
            issues.append(f"child fact {fact_id!r} changes the parent statement")
        if not scope_within(child_fact_scopes.get(fact_id, {}), parent_fact):
            issues.append(f"child fact {fact_id!r} expands the parent fact scope")
        parent_sources = set(parent_fact.get("source_ids", [])) if isinstance(parent_fact.get("source_ids"), list) else set()
        child_proving = set(child_fact.get("proving_source_ids", [])) if isinstance(child_fact.get("proving_source_ids"), list) else set()
        if not child_proving or not child_proving.issubset(parent_sources):
            issues.append(f"child fact {fact_id!r} changes the parent proving-source chain")

    for claim_id in child_handoff.get("claim_ids", []):
        child_claim = child_claim_map.get(claim_id)
        parent_claim = parent_claims.get(claim_id)
        if child_claim is None or parent_claim is None:
            issues.append(f"claim {claim_id!r} is not present in both child and parent bundles")
            continue
        if normalized_text(child_claim.get("text")) != normalized_text(parent_claim.get("text")):
            issues.append(f"child claim {claim_id!r} changes the parent claim text")
        child_fact_ids = set(child_claim.get("fact_ids", [])) if isinstance(child_claim.get("fact_ids"), list) else set()
        parent_fact_ids = set(parent_claim.get("fact_ids", [])) if isinstance(parent_claim.get("fact_ids"), list) else set()
        if child_fact_ids != parent_fact_ids:
            issues.append(f"child claim {claim_id!r} changes the parent fact mapping")
        if not scope_within(child_claim_scopes.get(claim_id, {}), parent_claim):
            issues.append(f"child claim {claim_id!r} expands the parent claim scope")

    # This validator deliberately does not import or execute the sibling Listing
    # validator. Cross-bundle terminal validation belongs to the package
    # coordinator. Here we only verify immutable local linkage and a small set of
    # parent invariants needed to keep an embedded child from hiding parent gaps.
    parent_requirements = {
        str(row.get("id")): row for row in parent.get("decision_map", {}).get("requirements", [])
        if isinstance(row, dict) and is_text(row.get("id"))
    }
    parent_assignments = {
        str(row.get("requirement_id")) for row in parent.get("surface_assignments", [])
        if isinstance(row, dict) and is_text(row.get("requirement_id"))
        and row.get("status") == "PASS"
    }
    missing_parent_p0 = sorted(
        requirement_id for requirement_id, requirement in parent_requirements.items()
        if requirement.get("priority") == "P0"
        and requirement.get("status", "READY") == "READY"
        and requirement_id not in parent_assignments
    )
    if missing_parent_p0:
        issues.append(f"local parent has uncovered P0 requirements {missing_parent_p0!r}")
    return not issues, issues


def scaffold_pollution_paths(root: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    template_path = Path(__file__).resolve().parents[1] / "assets" / "aplus-project-bundle-template.json"
    try:
        canonical = json.loads(template_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        hits.append("$.__canonical_scaffold_unavailable__")
    else:
        def differences(actual: Any, expected: Any, path: str = "$") -> list[str]:
            if type(actual) is not type(expected):
                return [path]
            if isinstance(actual, dict):
                result: list[str] = []
                for key in sorted(set(actual) | set(expected)):
                    child_path = f"{path}.{key}"
                    if key not in actual or key not in expected:
                        result.append(child_path)
                    else:
                        result.extend(differences(actual[key], expected[key], child_path))
                return result
            if isinstance(actual, list):
                if len(actual) != len(expected):
                    return [path]
                result: list[str] = []
                for index, (left, right) in enumerate(zip(actual, expected)):
                    result.extend(differences(left, right, f"{path}[{index}]"))
                return result
            return [] if actual == expected else [path]

        if root.get("schema_version") == canonical.get("schema_version"):
            hits.extend(differences(root, canonical)[:20])
    project = root.get("project") if isinstance(root.get("project"), dict) else {}
    if project.get("conclusion") != "NO_VALID_CONCLUSION":
        hits.append("$.project.conclusion")
    if project.get("write_scope") != "read_only":
        hits.append("$.project.write_scope")

    workflow = root.get("workflow_context")
    if isinstance(workflow, dict):
        if workflow.get("mode") != "standalone" or workflow.get("execution_boundary") != "read_only":
            hits.append("$.workflow_context")
        if any(workflow.get(key) for key in ("parent_bundle_ref", "accepted_handoff_snapshot_id", "accepted_at", "accepted_by")):
            hits.append("$.workflow_context.accepted_handoff")

    handoff = root.get("enriched_content_handoff")
    if isinstance(handoff, dict):
        if handoff.get("status") != "NOT_APPLICABLE":
            hits.append("$.enriched_content_handoff.status")
        for key in (
            "snapshot_id", "parent_project_id", "parent_bundle_sha256", "marketplace", "locale",
            "product_type", "variant_row_ids", "fact_ids", "claim_ids", "blocked_claim_ids",
            "conflict_ids", "source_ids", "requested_content_types", "decision_requirements",
            "capability_snapshot_ids", "created_at", "owner", "checksum",
        ):
            if handoff.get(key):
                hits.append(f"$.enriched_content_handoff.{key}")

    for key in (
        "sources", "facts", "claims", "competitor_insights", "voc_insights", "conflicts", "variants",
        "modules", "assets", "capability_snapshots", "decision_answer_units", "carriers",
        "delta_evidence_requests", "change_set", "live_readback", "experiments",
    ):
        value = root.get(key)
        if isinstance(value, list) and value:
            hits.append(f"$.{key}")

    summary = root.get("coverage_summary")
    empty_summary = {
        "status": "NOT_EVALUATED", "p0_required": 0, "p0_pass": 0,
        "gap_requirement_ids": [],
    }
    if root.get("schema_version") == "1.3":
        empty_summary.update({"p0_atoms_required": 0, "p0_atoms_pass": 0, "gap_atom_ids": []})
    if isinstance(summary, dict) and summary != empty_summary:
        hits.append("$.coverage_summary")
    authorization = root.get("publish_authorization")
    if isinstance(authorization, dict) and authorization.get("status") != "NOT_AUTHORIZED":
        hits.append("$.publish_authorization.status")
    baseline = root.get("baseline")
    if isinstance(baseline, dict) and baseline.get("status") != "NOT_FROZEN":
        hits.append("$.baseline.status")
    rollback = root.get("rollback")
    if isinstance(rollback, dict) and rollback.get("status") != "NOT_READY":
        hits.append("$.rollback.status")
    return sorted(set(hits))


def find_forbidden_v12_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_V12_KEYS:
                hits.append(child_path)
            hits.extend(find_forbidden_v12_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_v12_keys(child, f"{path}[{index}]"))
    return hits


def validate_handoff_application_scope(
    value: Any, path: str, marketplace: str, locale: str, errors: list[str]
) -> dict[str, Any]:
    raw = require_mapping(value, path, errors)
    expected = {"parent_asins", "child_asins", "packs", "colors", "sizes"}
    if set(raw) != expected:
        errors.append(f"{path}: must contain exactly {sorted(expected)!r}")
    result: dict[str, Any] = {
        "marketplaces": {marketplace} if marketplace else set(),
        "locales": {locale} if locale else set(),
        "parent_asins": string_set(require_list(raw, "parent_asins", path, errors), f"{path}.parent_asins", errors),
        "child_asins": string_set(require_list(raw, "child_asins", path, errors), f"{path}.child_asins", errors),
        "packs": string_set(require_list(raw, "packs", path, errors), f"{path}.packs", errors),
        "colors": string_set(require_list(raw, "colors", path, errors), f"{path}.colors", errors),
        "sizes_or_capacities": string_set(require_list(raw, "sizes", path, errors), f"{path}.sizes", errors),
        "other": {},
    }
    for asin in result["parent_asins"] | result["child_asins"]:
        check_asin(asin, f"{path}.ASIN[{asin}]", errors)
    return result


def validate_v12_contract(
    root: dict[str, Any],
    schema_version: str,
    project: dict[str, Any],
    mode: str,
    conclusion: str,
    marketplace: str,
    locale: str,
    envelope: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
    fact_map: dict[str, dict[str, Any]],
    fact_scopes: dict[str, dict[str, Any]],
    claim_map: dict[str, dict[str, Any]],
    claim_scopes: dict[str, dict[str, Any]],
    conflicts: dict[str, dict[str, Any]],
    module_map: dict[str, dict[str, Any]],
    module_scopes: dict[str, dict[str, Any]],
    asset_map: dict[str, dict[str, Any]],
    child_asins: set[str],
    bundle_source_path: Path | None,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:

    workflow = require_mapping(root.get("workflow_context"), "$.workflow_context", errors)
    workflow_mode = require_enum(workflow, "mode", "$.workflow_context", WORKFLOW_MODES, errors)
    execution_boundary = require_enum(workflow, "execution_boundary", "$.workflow_context", EXECUTION_BOUNDARIES, errors)
    parent_bundle_ref = require_string(workflow, "parent_bundle_ref", "$.workflow_context", errors)
    accepted_snapshot_id = require_string(workflow, "accepted_handoff_snapshot_id", "$.workflow_context", errors)
    accepted_at = require_string(workflow, "accepted_at", "$.workflow_context", errors)
    accepted_by = require_string(workflow, "accepted_by", "$.workflow_context", errors)
    if execution_boundary in {"authorized_submission", "rollback_only"} and project.get("write_scope") != "explicit_write":
        errors.append("[A12-AUTH-001] $.workflow_context.execution_boundary: write boundary requires explicit_write")

    handoff = require_mapping(root.get("enriched_content_handoff"), "$.enriched_content_handoff", errors)
    expected_contract = "1.1" if schema_version == "1.3" else "1.0"
    code = "A13" if schema_version == "1.3" else "A12"
    if require_text(handoff, "contract_version", "$.enriched_content_handoff", errors) != expected_contract:
        errors.append(f"[{code}-HANDOFF-001] $.enriched_content_handoff.contract_version: must equal {expected_contract!r}")
    handoff_status = require_enum(
        handoff, "status", "$.enriched_content_handoff",
        HANDOFF_STATUSES_V13 if schema_version == "1.3" else HANDOFF_STATUSES, errors,
    )
    maximum_output_options = (
        HANDOFF_MAXIMUM_OUTPUTS_V13 if schema_version == "1.3" else HANDOFF_MAXIMUM_OUTPUTS_LEGACY
    )
    maximum_output = require_enum(
        handoff, "maximum_output", "$.enriched_content_handoff", maximum_output_options, errors,
    )
    handoff_marketplace = require_string(handoff, "marketplace", "$.enriched_content_handoff", errors)
    handoff_locale = require_string(handoff, "locale", "$.enriched_content_handoff", errors)
    handoff_scope: dict[str, Any] | None = None
    handoff_requirements: dict[str, dict[str, Any]] = {}
    handoff_requirement_refs: dict[str, dict[str, set[str]]] = {}
    allowed_fact_ids: set[str] = set(fact_map)
    allowed_claim_ids: set[str] = set(claim_map)
    blocked_claim_ids: set[str] = set()
    handoff_conflict_ids: set[str] = set()
    handoff_capability_ids: set[str] = set()
    parent_bundle_verified: bool | None = None

    if workflow_mode == "standalone":
        parent_bundle_verified = None
        if handoff_status != "NOT_APPLICABLE":
            errors.append(f"[{code}-HANDOFF-002] $.enriched_content_handoff.status: standalone mode requires NOT_APPLICABLE")
        if any((parent_bundle_ref, accepted_snapshot_id, accepted_at, accepted_by)):
            errors.append(f"[{code}-HANDOFF-003] $.workflow_context: standalone mode cannot claim an accepted parent handoff")
    elif workflow_mode == "embedded":
        parent_bundle_verified = False
        if handoff_status != "FROZEN":
            errors.append(f"[{code}-HANDOFF-004] $.enriched_content_handoff.status: embedded mode requires FROZEN")
        for key in ("snapshot_id", "parent_project_id", "parent_bundle_sha256", "product_type", "created_at", "owner", "checksum"):
            require_text(handoff, key, "$.enriched_content_handoff", errors)
        if not parent_bundle_ref:
            errors.append("[A12-HANDOFF-005] $.workflow_context.parent_bundle_ref: required in embedded mode")
        if accepted_snapshot_id != handoff.get("snapshot_id"):
            errors.append("[A12-HANDOFF-006] $.workflow_context.accepted_handoff_snapshot_id: must match frozen snapshot")
        if not accepted_at or not accepted_by:
            errors.append("[A12-HANDOFF-007] $.workflow_context: accepted_at and accepted_by are required")
        elif accepted_at:
            check_iso(accepted_at, "$.workflow_context.accepted_at", errors)
        parent_hash = str(handoff.get("parent_bundle_sha256", ""))
        if not parent_hash.startswith("sha256:") or not SHA256_RE.fullmatch(parent_hash[7:]):
            errors.append("[A12-HANDOFF-008] $.enriched_content_handoff.parent_bundle_sha256: expected sha256:<64 hex>")
        if handoff_marketplace != marketplace or handoff_locale != locale:
            errors.append("[A12-HANDOFF-009] $.enriched_content_handoff: marketplace/locale must match project")
        handoff_scope = validate_handoff_application_scope(
            handoff.get("application_scope"), "$.enriched_content_handoff.application_scope",
            marketplace, locale, errors,
        )
        # Parent handoff binds sellable children; product-specific extra dimensions
        # remain constrained by the already-frozen A+ top-level envelope.
        handoff_scope["other"] = envelope.get("other", {})
        ensure_scope_subset(handoff_scope, envelope, "$.enriched_content_handoff.application_scope", "top-level envelope", errors)
        allowed_fact_ids = string_set(require_list(handoff, "fact_ids", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.fact_ids", errors)
        allowed_claim_ids = string_set(require_list(handoff, "claim_ids", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.claim_ids", errors)
        blocked_claim_ids = string_set(require_list(handoff, "blocked_claim_ids", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.blocked_claim_ids", errors)
        handoff_conflict_ids = string_set(require_list(handoff, "conflict_ids", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.conflict_ids", errors)
        for key, values, known in (
            ("fact_ids", allowed_fact_ids, fact_map),
            ("claim_ids", allowed_claim_ids, claim_map),
            ("blocked_claim_ids", blocked_claim_ids, claim_map),
            ("conflict_ids", handoff_conflict_ids, conflicts),
        ):
            unknown = values - set(known)
            if unknown:
                errors.append(f"[A12-HANDOFF-010] $.enriched_content_handoff.{key}: unknown IDs {sorted(unknown)!r}")
        extra_facts = set(fact_map) - allowed_fact_ids
        extra_claims = set(claim_map) - allowed_claim_ids - blocked_claim_ids
        if extra_facts or extra_claims:
            errors.append(f"[A12-HANDOFF-011] $.enriched_content_handoff: embedded bundle adds parent-owned facts/claims {sorted(extra_facts | extra_claims)!r}")
        if allowed_claim_ids & blocked_claim_ids:
            errors.append("[A12-HANDOFF-012] $.enriched_content_handoff: allowed and blocked claims must be disjoint")
        for conflict_id in handoff_conflict_ids:
            if conflicts.get(conflict_id, {}).get("status") in {"OPEN", "EVIDENCE_REQUESTED", "BLOCKED"}:
                errors.append(f"[A12-HANDOFF-013] $.enriched_content_handoff.conflict_ids: open conflict {conflict_id!r} cannot enter a FROZEN handoff")
        source_ids = string_set(require_list(handoff, "source_ids", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.source_ids", errors)
        unknown_sources = source_ids - set(source_map)
        if unknown_sources:
            errors.append(f"[A12-HANDOFF-014] $.enriched_content_handoff.source_ids: unknown IDs {sorted(unknown_sources)!r}")
        content_types = string_set(require_list(handoff, "requested_content_types", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.requested_content_types", errors, nonempty=True)
        invalid_content_types = content_types - A_PLUS_CONTENT_TYPES
        if invalid_content_types:
            errors.append(f"[A12-QA-001] $.enriched_content_handoff.requested_content_types: unsupported or community Q&A types {sorted(invalid_content_types)!r}")
        string_set(require_list(handoff, "variant_row_ids", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.variant_row_ids", errors, nonempty=True)
        handoff_capability_ids = string_set(require_list(handoff, "capability_snapshot_ids", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.capability_snapshot_ids", errors)
        prohibited = string_set(require_list(handoff, "prohibited_actions", "$.enriched_content_handoff", errors), "$.enriched_content_handoff.prohibited_actions", errors, nonempty=True)
        if not {"modify_parent_truth", "expand_application_scope", "online_submission"}.issubset(prohibited):
            errors.append("[A12-HANDOFF-015] $.enriched_content_handoff.prohibited_actions: missing mandatory parent protections")
        created_at = require_text(handoff, "created_at", "$.enriched_content_handoff", errors)
        check_iso(created_at, "$.enriched_content_handoff.created_at", errors)
        requirement_rows = require_list(handoff, "decision_requirements", "$.enriched_content_handoff", errors)
        handoff_requirements = unique_rows(requirement_rows, "$.enriched_content_handoff.decision_requirements", errors)
        for req_id, requirement in handoff_requirements.items():
            path = f"$.enriched_content_handoff.decision_requirements[{req_id}]"
            require_text(requirement, "buyer_question", path, errors)
            require_enum(requirement, "priority", path, PRIORITIES, errors)
            if require_text(requirement, "assigned_surface", path, errors) != "enriched_content":
                errors.append(f"[A12-HANDOFF-016] {path}.assigned_surface: must be enriched_content")
            if requirement.get("native_answer_required") not in {True, False} or requirement.get("early_disclosure_required") not in {True, False}:
                errors.append(f"[A12-HANDOFF-017] {path}: native/early disclosure flags must be boolean")
            req_scope = validate_handoff_application_scope(requirement.get("application_scope"), f"{path}.application_scope", marketplace, locale, errors)
            ensure_scope_subset(req_scope, handoff_scope, f"{path}.application_scope", "frozen handoff", errors)
            requirement_refs: dict[str, set[str]] = {}
            for key, known in (("fact_ids", allowed_fact_ids), ("claim_ids", allowed_claim_ids)):
                values = string_set(require_list(requirement, key, path, errors), f"{path}.{key}", errors)
                requirement_refs[key] = values
                if not values.issubset(known):
                    errors.append(f"[A12-HANDOFF-018] {path}.{key}: outside frozen handoff")
            handoff_requirement_refs[req_id] = requirement_refs
            if requirement.get("status") not in {"READY", "HOLD", "CONFLICT", "OMITTED_WITH_REASON"}:
                errors.append(f"[A12-HANDOFF-019] {path}.status: unsupported status")
            if requirement.get("early_disclosure_required") and not is_text(requirement.get("upstream_primary_carrier_ref")):
                errors.append(f"[A12-COVERAGE-001] {path}.upstream_primary_carrier_ref: early P0 requires an upstream primary disclosure")
        dependency_only_outputs = {"conditional_wireframe", "strategy_dependency_only"}
        if maximum_output in dependency_only_outputs and conclusion == "PASS":
            errors.append(f"[{code}-HANDOFF-020] $.project.conclusion: dependency-only handoff cannot produce PASS")
        required_rank = MODE_MINIMUM_OUTPUT.get(mode, 0)
        if conclusion == "PASS" and OUTPUT_RANK.get(maximum_output, -1) < required_rank:
            errors.append(
                f"[A12-HANDOFF-021] $.enriched_content_handoff.maximum_output: "
                f"{mode} PASS requires an output boundary at rank {required_rank} or higher"
            )
        if mode == "publish_support" and maximum_output != "publish_support_package":
            errors.append("[A12-HANDOFF-022] $.enriched_content_handoff.maximum_output: publish_support requires publish_support_package")
        if maximum_output in dependency_only_outputs:
            content_rows = [
                row for section in ("modules", "assets", "decision_answer_units", "carriers")
                for row in root.get(section, []) if isinstance(row, dict)
            ]
            applied_rows = [
                row for section in ("modules", "assets")
                for row in root.get(section, []) if isinstance(row, dict)
                and row.get("applied_child_asins")
            ]
            if content_rows or applied_rows:
                errors.append(
                    f"[{code}-HANDOFF-023] $.enriched_content_handoff.maximum_output: "
                    "dependency-only handoff cannot contain module, asset, answer-unit, carrier, or applied content"
                )
        if OUTPUT_RANK.get(maximum_output, -1) < OUTPUT_RANK["publish_support_package"]:
            if execution_boundary in {"authorized_submission", "rollback_only"} or project.get("write_scope") != "read_only":
                errors.append("[A12-HANDOFF-024] $.enriched_content_handoff.maximum_output: pre-publication output cannot authorize online writes")
            published_rows = [
                row for section in ("modules", "assets")
                for row in root.get(section, []) if isinstance(row, dict)
                and row.get("content_status") == "PUBLISHED"
            ]
            applied_variants = [
                row for row in root.get("variants", []) if isinstance(row, dict)
                and row.get("status") in {"APPLIED", "LIVE_PASS"}
            ]
            if published_rows or applied_variants or root.get("change_set") or root.get("live_readback"):
                errors.append("[A12-HANDOFF-025] $.enriched_content_handoff.maximum_output: pre-publication output cannot contain published/applied/live state")

        if schema_version == "1.2":
            parent_bundle_verified, parent_issues = validate_parent_bundle_reference(
                parent_bundle_ref, handoff, bundle_source_path,
                fact_map, fact_scopes, claim_map, claim_scopes,
            )
            for issue in parent_issues:
                message = f"$.workflow_context.parent_bundle_ref: {issue}"
                errors.append(f"[{code}-PARENT-001] {message}")
        else:
            parent_bundle_verified = None
            warnings.append("A+ v1.3 validates only the frozen child handoff; parent file integrity is coordinator-owned.")

    if mode == "publish_support" and execution_boundary != "authorized_submission":
        errors.append("[A12-AUTH-002] $.workflow_context.execution_boundary: publish_support requires authorized_submission")

    capability_rows = require_list(root, "capability_snapshots", "$", errors)
    capability_map = unique_rows(capability_rows, "$.capability_snapshots", errors)
    capability_fields: dict[str, set[str]] = {}
    capability_modules: dict[str, set[str]] = {}
    for capability_id, capability in capability_map.items():
        path = f"$.capability_snapshots[{capability_id}]"
        if require_text(capability, "marketplace", path, errors) != marketplace or require_text(capability, "locale", path, errors) != locale:
            errors.append(f"[A12-CAP-001] {path}: marketplace/locale mismatch")
        require_text(capability, "account_scope", path, errors)
        require_enum(capability, "content_type", path, A_PLUS_CONTENT_TYPES, errors)
        require_enum(capability, "eligibility_status", path, CONTENT_ELIGIBILITY, errors)
        modules = string_set(require_list(capability, "available_module_types", path, errors), f"{path}.available_module_types", errors)
        fields = string_set(require_list(capability, "backend_field_paths", path, errors), f"{path}.backend_field_paths", errors)
        capability_modules[capability_id] = modules
        capability_fields[capability_id] = fields
        require_mapping(capability.get("field_limits"), f"{path}.field_limits", errors)
        source_ids = string_set(require_list(capability, "source_ids", path, errors), f"{path}.source_ids", errors, nonempty=True)
        for source_id in source_ids:
            source = source_map.get(source_id)
            if source is None:
                errors.append(f"[A12-CAP-002] {path}.source_ids: unknown source {source_id!r}")
            elif source.get("fetch_status") != "ok" or source.get("source_type") not in {"OFFICIAL_PLATFORM_RULE", "BACKEND_OBSERVED", "VERIFIED_ACCOUNT_DATA"}:
                errors.append(f"[A12-CAP-003] {path}.source_ids: source {source_id!r} is unusable for capability")
        retrieved_at = require_text(capability, "retrieved_at", path, errors)
        check_iso(retrieved_at, f"{path}.retrieved_at", errors)
        status = require_enum(capability, "status", path, CAPABILITY_STATUSES, errors)
        require_text(capability, "owner", path, errors)
        require_text(capability, "checksum", path, errors)
        if status == "CURRENT" and (not modules or not fields):
            errors.append(f"[A12-CAP-004] {path}: CURRENT snapshot requires module types and backend field paths")
    if schema_version == "1.2" and conclusion == "PASS" and not capability_map:
        errors.append("[A12-CAP-005] $.capability_snapshots: project PASS requires a current capability snapshot")
    if workflow_mode == "embedded" and not handoff_capability_ids.issubset(set(capability_map)):
        errors.append("[A12-CAP-006] $.enriched_content_handoff.capability_snapshot_ids: unknown capability snapshot")

    carrier_rows = require_list(root, "carriers", "$", errors)
    carrier_map = unique_rows(carrier_rows, "$.carriers", errors)
    carrier_scopes: dict[str, dict[str, Any]] = {}
    carrier_answer_ids: dict[str, set[str]] = {}
    carrier_requirement_ids: dict[str, set[str]] = {}
    for carrier_id, carrier in carrier_map.items():
        path = f"$.carriers[{carrier_id}]"
        carrier_type = require_enum(carrier, "carrier_type", path, CARRIER_TYPES, errors)
        if is_community_qa_label(carrier.get("carrier_type")):
            errors.append(f"[A12-QA-002] {path}.carrier_type: Community Q&A is read-only and cannot be a brand-authored carrier")
        coverage_role = require_enum(carrier, "coverage_role", path, COVERAGE_ROLES, errors)
        module_id = require_text(carrier, "module_id", path, errors)
        if module_id not in module_map:
            errors.append(f"[A12-CARRIER-001] {path}.module_id: unknown module")
        field_path = require_text(carrier, "backend_field_path", path, errors)
        capability_id = require_string(carrier, "capability_snapshot_id", path, errors)
        capability = capability_map.get(capability_id)
        if capability is None:
            if not (schema_version == "1.3" and not capability_map and not capability_id):
                errors.append(f"[A12-CARRIER-002] {path}.capability_snapshot_id: unknown capability snapshot")
        else:
            if capability.get("status") != "CURRENT":
                errors.append(f"[A12-CARRIER-003] {path}.capability_snapshot_id: capability snapshot is not CURRENT")
            if field_path not in capability_fields.get(capability_id, set()):
                errors.append(f"[A12-CARRIER-004] {path}.backend_field_path: unavailable in capability snapshot")
            if module_id in module_map and module_map[module_id].get("module_type") not in capability_modules.get(capability_id, set()):
                errors.append(f"[A12-CARRIER-005] {path}: module type unavailable in capability snapshot")
            if workflow_mode == "embedded" and handoff_capability_ids and capability_id not in handoff_capability_ids:
                errors.append(f"[A12-CARRIER-015] {path}.capability_snapshot_id: outside frozen handoff")
        requirement_ids = string_set(require_list(carrier, "decision_requirement_ids", path, errors), f"{path}.decision_requirement_ids", errors)
        carrier_requirement_ids[carrier_id] = requirement_ids
        fact_ids = string_set(require_list(carrier, "fact_ids", path, errors), f"{path}.fact_ids", errors)
        claim_ids = string_set(require_list(carrier, "claim_ids", path, errors), f"{path}.claim_ids", errors)
        answer_ids = string_set(require_list(carrier, "answer_unit_ids", path, errors), f"{path}.answer_unit_ids", errors)
        asset_ids = string_set(require_list(carrier, "asset_ids", path, errors), f"{path}.asset_ids", errors)
        carrier_answer_ids[carrier_id] = answer_ids
        if workflow_mode == "embedded" and not requirement_ids.issubset(set(handoff_requirements)):
            errors.append(f"[A12-CARRIER-006] {path}.decision_requirement_ids: outside frozen handoff")
        for key, values, known in (("fact_ids", fact_ids, fact_map), ("claim_ids", claim_ids, claim_map), ("asset_ids", asset_ids, asset_map)):
            unknown = values - set(known)
            if unknown:
                errors.append(f"[A12-CARRIER-007] {path}.{key}: unknown IDs {sorted(unknown)!r}")
        module = module_map.get(module_id, {})
        module_fact_ids = set(module.get("fact_ids", [])) if isinstance(module.get("fact_ids"), list) else set()
        module_claim_ids = set(module.get("claim_ids", [])) if isinstance(module.get("claim_ids"), list) else set()
        if not fact_ids.issubset(module_fact_ids) or not claim_ids.issubset(module_claim_ids):
            errors.append(f"[A12-CARRIER-016] {path}: carrier fact/claim refs must be a subset of its module refs")
        if workflow_mode == "embedded" and (not fact_ids.issubset(allowed_fact_ids) or not claim_ids.issubset(allowed_claim_ids) or claim_ids & blocked_claim_ids):
            errors.append(f"[A12-CARRIER-008] {path}: references facts/claims outside frozen allowed set")
        carrier_scope = validate_app_scope(carrier.get("application_scope"), f"{path}.application_scope", errors)
        carrier_scopes[carrier_id] = carrier_scope
        ensure_scope_subset(carrier_scope, envelope, f"{path}.application_scope", "top-level envelope", errors)
        if handoff_scope is not None:
            ensure_scope_subset(carrier_scope, handoff_scope, f"{path}.application_scope", "frozen handoff", errors)
        if module_id in module_scopes:
            ensure_scope_subset(carrier_scope, module_scopes[module_id], f"{path}.application_scope", f"module {module_id!r}", errors)
        for fact_id in fact_ids:
            if fact_id in fact_scopes:
                ensure_scope_subset(carrier_scope, fact_scopes[fact_id], f"{path}.application_scope", f"fact {fact_id!r}", errors)
            if carrier.get("content_status") in FINAL_CONTENT_STATUSES and fact_map.get(fact_id, {}).get("publish_status") != "PUBLISHABLE":
                errors.append(f"[A12-CARRIER-009] {path}: final carrier uses non-publishable fact {fact_id!r}")
        for claim_id in claim_ids:
            if claim_id in claim_scopes:
                ensure_scope_subset(carrier_scope, claim_scopes[claim_id], f"{path}.application_scope", f"claim {claim_id!r}", errors)
            if carrier.get("content_status") in FINAL_CONTENT_STATUSES and claim_map.get(claim_id, {}).get("publish_status") != "PUBLISHABLE":
                errors.append(f"[A12-CARRIER-010] {path}: final carrier uses non-publishable claim {claim_id!r}")
        if carrier_type == "static_visual" and not asset_ids:
            errors.append(f"[A12-CARRIER-011] {path}.asset_ids: static_visual requires an asset")
        if carrier_type == "native_text" and coverage_role == "PRIMARY_NATIVE_ANSWER" and not answer_ids:
            errors.append(f"[A12-CARRIER-012] {path}.answer_unit_ids: primary native carrier requires an answer unit")
        require_text(carrier, "mobile_behavior", path, errors)
        content_status = require_enum(carrier, "content_status", path, CONTENT_STATUSES, errors)
        qa_status = require_enum(carrier, "qa_status", path, QA_STATUSES, errors)
        require_text(carrier, "owner", path, errors)
        if conclusion == "PASS" and (content_status not in FINAL_CONTENT_STATUSES or qa_status != "PASS"):
            errors.append(f"[A12-CARRIER-013] {path}: project PASS requires final content and QA PASS")

    answer_rows = require_list(root, "decision_answer_units", "$", errors)
    answer_map = unique_rows(answer_rows, "$.decision_answer_units", errors)
    answers_by_requirement: dict[str, list[str]] = {}
    if workflow_mode == "standalone":
        if schema_version == "1.3":
            requirement_rows = root.get("decision_map", {}).get("requirements", []) if isinstance(root.get("decision_map"), dict) else []
            handoff_requirements = {
                str(row.get("id")): row for row in requirement_rows
                if isinstance(row, dict) and is_text(row.get("id"))
            }
            handoff_requirement_refs = {
                requirement_id: {
                    "fact_ids": set(row.get("fact_ids", [])) if isinstance(row.get("fact_ids"), list) else set(),
                    "claim_ids": set(row.get("claim_ids", [])) if isinstance(row.get("claim_ids"), list) else set(),
                }
                for requirement_id, row in handoff_requirements.items()
            }
        else:
            handoff_requirements = {
                module_id: {
                    "id": module_id,
                    "priority": module.get("decision_priority"),
                    "buyer_question": module.get("decision_question"),
                    "native_answer_required": True,
                    "early_disclosure_required": False,
                    "scope_normalized": module_scopes.get(module_id, {}),
                }
                for module_id, module in module_map.items()
            }
            handoff_requirement_refs = {
                module_id: {
                    "fact_ids": set(module.get("fact_ids", [])) if isinstance(module.get("fact_ids"), list) else set(),
                    "claim_ids": set(module.get("claim_ids", [])) if isinstance(module.get("claim_ids"), list) else set(),
                }
                for module_id, module in module_map.items()
            }
    for answer_id, answer in answer_map.items():
        path = f"$.decision_answer_units[{answer_id}]"
        requirement_id = require_text(answer, "requirement_id", path, errors)
        requirement = handoff_requirements.get(requirement_id)
        if requirement is None:
            errors.append(f"[A12-ANSWER-001] {path}.requirement_id: unknown decision requirement")
        else:
            if require_enum(answer, "priority", path, PRIORITIES, errors) != requirement.get("priority"):
                errors.append(f"[A12-ANSWER-002] {path}.priority: differs from assigned requirement")
            if require_text(answer, "buyer_question", path, errors) != requirement.get("buyer_question"):
                errors.append(f"[A12-ANSWER-003] {path}.buyer_question: differs from assigned requirement")
        carrier_id = require_text(answer, "primary_carrier_id", path, errors)
        carrier = carrier_map.get(carrier_id)
        if carrier is None:
            errors.append(f"[A12-ANSWER-004] {path}.primary_carrier_id: unknown carrier")
        elif answer_id not in carrier_answer_ids.get(carrier_id, set()):
            errors.append(f"[A12-ANSWER-005] {path}: carrier does not reference this answer unit")
        elif requirement_id not in carrier_requirement_ids.get(carrier_id, set()):
            errors.append(f"[A12-ANSWER-020] {path}.requirement_id: primary carrier does not reference this requirement")
        module_id = require_text(answer, "module_id", path, errors)
        if module_id not in module_map:
            errors.append(f"[A12-ANSWER-006] {path}.module_id: unknown module")
        elif carrier and carrier.get("module_id") != module_id:
            errors.append(f"[A12-ANSWER-007] {path}.module_id: differs from primary carrier")
        native_field_path = require_text(answer, "native_field_path", path, errors)
        if carrier is not None and native_field_path != carrier.get("backend_field_path"):
            errors.append(f"[A12-ANSWER-021] {path}.native_field_path: must exactly match the primary carrier backend_field_path")
        text = require_text(answer, "text", path, errors)
        field_parts = native_field_path.split(".")
        native_field_value = ""
        if (
            len(field_parts) == 3
            and field_parts[0] == "modules"
            and field_parts[1] == module_id
            and field_parts[2] in {"native_headline", "native_body"}
            and module_id in module_map
        ):
            native_field_value = str(module_map[module_id].get(field_parts[2], ""))
        else:
            errors.append(f"[A12-ANSWER-015] {path}.native_field_path: must resolve to this module's native_headline or native_body")
        if text and native_field_value and normalized_text(text) not in normalized_text(native_field_value):
            errors.append(f"[A12-ANSWER-016] {path}.text: exact normalized answer text is absent from the resolved native field")
        answer_scope = validate_app_scope(answer.get("application_scope"), f"{path}.application_scope", errors)
        ensure_scope_subset(answer_scope, envelope, f"{path}.application_scope", "top-level envelope", errors)
        if handoff_scope is not None:
            ensure_scope_subset(answer_scope, handoff_scope, f"{path}.application_scope", "frozen handoff", errors)
        if carrier_id in carrier_scopes:
            ensure_scope_subset(answer_scope, carrier_scopes[carrier_id], f"{path}.application_scope", f"carrier {carrier_id!r}", errors)
        fact_ids = string_set(require_list(answer, "fact_ids", path, errors), f"{path}.fact_ids", errors)
        claim_ids = string_set(require_list(answer, "claim_ids", path, errors), f"{path}.claim_ids", errors)
        for key, values, known, scopes in (("fact_ids", fact_ids, fact_map, fact_scopes), ("claim_ids", claim_ids, claim_map, claim_scopes)):
            unknown = values - set(known)
            if unknown:
                errors.append(f"[A12-ANSWER-008] {path}.{key}: unknown IDs {sorted(unknown)!r}")
            for value in values & set(scopes):
                ensure_scope_subset(answer_scope, scopes[value], f"{path}.application_scope", f"{key[:-4]} {value!r}", errors)
        if workflow_mode == "embedded" and (not fact_ids.issubset(allowed_fact_ids) or not claim_ids.issubset(allowed_claim_ids) or claim_ids & blocked_claim_ids):
            errors.append(f"[A12-ANSWER-009] {path}: references facts/claims outside frozen allowed set")
        requirement_refs = handoff_requirement_refs.get(requirement_id, {"fact_ids": set(), "claim_ids": set()})
        if not fact_ids.issubset(requirement_refs.get("fact_ids", set())) or not claim_ids.issubset(requirement_refs.get("claim_ids", set())):
            errors.append(f"[A12-ANSWER-017] {path}: answer fact/claim refs must stay within the assigned requirement")
        if requirement is not None and requirement.get("priority") == "P0" and not (fact_ids or claim_ids):
            errors.append(f"[A12-ANSWER-018] {path}: a P0 native answer requires at least one fact or claim reference")
        if carrier is not None:
            carrier_fact_ids = set(carrier.get("fact_ids", [])) if isinstance(carrier.get("fact_ids"), list) else set()
            carrier_claim_ids = set(carrier.get("claim_ids", [])) if isinstance(carrier.get("claim_ids"), list) else set()
            if not fact_ids.issubset(carrier_fact_ids) or not claim_ids.issubset(carrier_claim_ids):
                errors.append(f"[A12-ANSWER-019] {path}: answer fact/claim refs must be a subset of its carrier refs")
        early = answer.get("early_disclosure_required")
        if early not in {True, False}:
            errors.append(f"[A12-ANSWER-010] {path}.early_disclosure_required: required boolean")
        elif requirement is not None and early != requirement.get("early_disclosure_required"):
            errors.append(f"[A12-ANSWER-011] {path}.early_disclosure_required: differs from requirement")
        content_status = require_enum(answer, "content_status", path, CONTENT_STATUSES, errors)
        qa_status = require_enum(answer, "qa_status", path, QA_STATUSES, errors)
        require_text(answer, "owner", path, errors)
        if carrier is not None and capability_map:
            capability_id = carrier.get("capability_snapshot_id")
            if native_field_path not in capability_fields.get(capability_id, set()):
                errors.append(f"[A12-ANSWER-012] {path}.native_field_path: not in carrier capability snapshot")
        if content_status in FINAL_CONTENT_STATUSES:
            for fact_id in fact_ids:
                if fact_map.get(fact_id, {}).get("publish_status") != "PUBLISHABLE":
                    errors.append(f"[A12-ANSWER-013] {path}: final answer uses non-publishable fact {fact_id!r}")
            for claim_id in claim_ids:
                if claim_map.get(claim_id, {}).get("publish_status") != "PUBLISHABLE":
                    errors.append(f"[A12-ANSWER-014] {path}: final answer uses non-publishable claim {claim_id!r}")
        if text:
            answers_by_requirement.setdefault(requirement_id, []).append(answer_id)

    for carrier_id, answer_ids in carrier_answer_ids.items():
        unknown = answer_ids - set(answer_map)
        if unknown:
            errors.append(f"[A12-CARRIER-014] $.carriers[{carrier_id}].answer_unit_ids: unknown IDs {sorted(unknown)!r}")

    p0_requirements = {
        req_id for req_id, requirement in handoff_requirements.items()
        if requirement.get("priority") == "P0" and requirement.get("native_answer_required", True)
        and requirement.get("status", "READY") == "READY"
    }
    passed: set[str] = set()
    for req_id in p0_requirements:
        for answer_id in answers_by_requirement.get(req_id, []):
            answer = answer_map[answer_id]
            carrier = carrier_map.get(answer.get("primary_carrier_id"), {})
            if (
                answer.get("content_status") in FINAL_CONTENT_STATUSES
                and answer.get("qa_status") == "PASS"
                and carrier.get("carrier_type") == "native_text"
                and carrier.get("coverage_role") == "PRIMARY_NATIVE_ANSWER"
                and carrier.get("content_status") in FINAL_CONTENT_STATUSES
                and carrier.get("qa_status") == "PASS"
                and is_text(answer.get("text"))
            ):
                passed.add(req_id)
                break
    gaps = sorted(p0_requirements - passed)
    summary = require_mapping(root.get("coverage_summary"), "$.coverage_summary", errors)
    summary_status = require_enum(summary, "status", "$.coverage_summary", COVERAGE_STATUSES, errors)
    for key, expected in (("p0_required", len(p0_requirements)), ("p0_pass", len(passed))):
        if summary.get(key) != expected:
            errors.append(f"[A12-COVERAGE-002] $.coverage_summary.{key}: expected derived value {expected}")
    summary_gaps = string_set(require_list(summary, "gap_requirement_ids", "$.coverage_summary", errors), "$.coverage_summary.gap_requirement_ids", errors)
    if summary_gaps != set(gaps):
        errors.append(f"[A12-COVERAGE-003] $.coverage_summary.gap_requirement_ids: expected {gaps!r}")
    if not gaps and summary_status != "PASS":
        errors.append("[A12-COVERAGE-004] $.coverage_summary.status: complete native coverage must be PASS")
    if gaps and summary_status == "PASS":
        errors.append("[A12-COVERAGE-005] $.coverage_summary.status: missing P0 native answers cannot PASS")
    if conclusion == "PASS" and (summary_status != "PASS" or gaps):
        errors.append("[A12-COVERAGE-006] $.project.conclusion: PASS requires complete v1.2 Native Answer Coverage")
    if conclusion == "PASS" and mode in {"plan", "rebuild", "preflight_qa", "publish_support"} and not module_map:
        errors.append("[A12-COVERAGE-007] $.modules: PASS planning/build mode requires at least one module")

    delta_rows = require_list(root, "delta_evidence_requests", "$", errors)
    delta_map = unique_rows(delta_rows, "$.delta_evidence_requests", errors)
    for request_id, request in delta_map.items():
        path = f"$.delta_evidence_requests[{request_id}]"
        require_text(request, "question", path, errors)
        req_ids = string_set(require_list(request, "affected_requirement_ids", path, errors), f"{path}.affected_requirement_ids", errors)
        for key, known in (
            ("affected_requirement_ids", set(handoff_requirements)),
            ("affected_fact_ids", set(fact_map)),
            ("affected_claim_ids", set(claim_map)),
            ("affected_module_ids", set(module_map)),
        ):
            values = req_ids if key == "affected_requirement_ids" else string_set(require_list(request, key, path, errors), f"{path}.{key}", errors)
            unknown = values - known
            if unknown:
                errors.append(f"[A12-DELTA-001] {path}.{key}: unknown IDs {sorted(unknown)!r}")
        require_text(request, "decisive_evidence", path, errors)
        require_text(request, "owner", path, errors)
        require_enum(request, "status", path, DELTA_STATUSES, errors)
    if conclusion == "PASS" and any(row.get("status") == "OPEN" for row in delta_map.values()):
        errors.append("[A12-DELTA-002] $.project.conclusion: PASS cannot retain open delta evidence requests")

    return {
        "capability_snapshots": len(capability_map),
        "decision_answer_units": len(answer_map),
        "carriers": len(carrier_map),
        "delta_evidence_requests": len(delta_map),
        "p0_required": len(p0_requirements),
        "p0_pass": len(passed),
        "parent_bundle_verified": parent_bundle_verified,
    }


def canonical_object_hash(value: Any) -> str:
    """Return the suite-wide deterministic hash for a JSON value."""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_handoff_hash(handoff: dict[str, Any]) -> str:
    return _lineage_handoff_hash(handoff)


def valid_sha256_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and bool(SHA256_RE.fullmatch(value[7:]))


def report_structure_valid(root: Any, errors: list[str] | tuple[str, ...] = ()) -> bool:
    """Return whether a populated v1.3 object is safe to inspect as a report.

    This is intentionally narrower than business validity and broader than a
    component PASS: a BLOCKED/CONDITIONAL bundle remains renderable, while a
    malformed root, missing contract blocks, or a scaffold does not.
    """
    return structural_valid_v13(root, ROOT_KEYS_V13, ALLOWED_ROOT_EXTRAS, errors)


def validate_v13_discovery(
    discovery_value: Any,
    voc_insights_value: Any,
    workflow_mode: str,
    decision_requirements: dict[str, dict[str, Any]],
    atom_map: dict[str, dict[str, Any]],
    source_map: dict[str, dict[str, Any]],
    source_scopes: dict[str, dict[str, Any]],
    fact_map: dict[str, dict[str, Any]],
    claim_map: dict[str, dict[str, Any]],
    competitor_map: dict[str, dict[str, Any]],
    variant_map: dict[str, dict[str, Any]],
    marketplace: str,
    locale: str,
    errors: list[str],
) -> tuple[str, dict[str, dict[str, Any]], bool]:
    """Validate standalone interviewing or an immutable parent-bound closure."""
    discovery = require_mapping(discovery_value, "$.discovery", errors)
    voc_map = unique_rows(require_list({"voc_insights": voc_insights_value}, "voc_insights", "$", errors), "$.voc_insights", errors)
    usable_voc_source_ids: set[str] = set()
    usable_voc_ids: set[str] = set()
    for voc_id, insight in voc_map.items():
        path = f"$.voc_insights[{voc_id}]"
        if set(insight) != VOC_INSIGHT_KEYS:
            errors.append(f"[A13-STAGE-024] {path}: VOC insight must use exact keys {sorted(VOC_INSIGHT_KEYS)!r}")
        if insight.get("marketplace") != marketplace or insight.get("locale") != locale:
            errors.append(f"[A13-STAGE-024] {path}: VOC insight must match the frozen marketplace and locale")
        for key in ("observation", "buyer_question", "use_path", "decision_implication", "owner"):
            if not is_substantive_human_text(insight.get(key)):
                errors.append(f"[A13-STAGE-024] {path}.{key}: requires substantive human-readable text")
        observed_at = require_text(insight, "observed_at", path, errors)
        check_iso(observed_at, f"{path}.observed_at", errors)
        fetch_status = require_enum(insight, "fetch_status", path, FETCH_STATUSES, errors)
        status = require_enum(insight, "status", path, COMPETITOR_STATUSES, errors)
        if insight.get("target_product_proof_prohibited") is not True:
            errors.append(f"[A13-STAGE-024] {path}.target_product_proof_prohibited: must be true")
        source_ids = string_set(require_list(insight, "source_ids", path, errors), f"{path}.source_ids", errors, nonempty=True)
        valid_source_ids = {
            source_id for source_id in source_ids
            if source_id in source_map
            and source_map[source_id].get("fetch_status") == "ok"
            and source_map[source_id].get("source_type") == "VOC_ONLY"
        }
        if valid_source_ids != source_ids:
            errors.append(f"[A13-STAGE-024] {path}.source_ids: every VOC source must exist, be usable, and remain typed VOC_ONLY")
        if fetch_status == "ok" and status in {"PROVISIONAL", "FROZEN"} and valid_source_ids:
            usable_voc_ids.add(voc_id)
            usable_voc_source_ids.update(valid_source_ids)
    discovery_mode = require_enum(discovery, "mode", "$.discovery", DISCOVERY_MODES, errors)
    evidence_pass = require_mapping(discovery.get("evidence_pass"), "$.discovery.evidence_pass", errors)
    require_enum(evidence_pass, "status", "$.discovery.evidence_pass", EVIDENCE_PASS_STATUSES, errors)
    string_set(require_list(evidence_pass, "source_ids", "$.discovery.evidence_pass", errors), "$.discovery.evidence_pass.source_ids", errors)
    string_set(require_list(evidence_pass, "observations", "$.discovery.evidence_pass", errors), "$.discovery.evidence_pass.observations", errors)
    require_text(evidence_pass, "owner", "$.discovery.evidence_pass", errors)
    rounds = unique_rows(require_list(discovery, "interview_rounds", "$.discovery", errors), "$.discovery.interview_rounds", errors)
    question_map: dict[str, dict[str, Any]] = {}
    round_phases: set[str] = set()
    round_ids_by_phase: dict[str, set[str]] = {"TRUTH": set(), "POSITIONING": set()}
    question_ids_by_phase: dict[str, set[str]] = {"TRUTH": set(), "POSITIONING": set()}
    positioning_strategic_choice_question_ids: set[str] = set()
    strategic_selection_question_ids: set[str] = set()
    question_round_id_by_id: dict[str, str] = {}
    question_requirement_ids_by_id: dict[str, set[str]] = {}
    for round_id, round_row in rounds.items():
        path = f"$.discovery.interview_rounds[{round_id}]"
        round_phase = require_enum(round_row, "phase", path, DISCOVERY_PHASES, errors)
        if round_phase:
            round_phases.add(round_phase)
            round_ids_by_phase[round_phase].add(round_id)
        require_text(round_row, "owner", path, errors)
        for index, raw_question in enumerate(require_list(round_row, "questions", path, errors)):
            qpath = f"{path}.questions[{index}]"
            question = require_mapping(raw_question, qpath, errors)
            question_id = require_text(question, "id", qpath, errors)
            if question_id in question_map:
                errors.append(f"{qpath}.id: duplicate question id {question_id!r}")
            elif question_id:
                question_map[question_id] = question
                if round_phase:
                    question_ids_by_phase[round_phase].add(question_id)
                    question_round_id_by_id[question_id] = round_id
            require_text(question, "question", qpath, errors)
            effects = string_set(require_list(question, "decision_effects", qpath, errors), f"{qpath}.decision_effects", errors, nonempty=True)
            if effects - DISCOVERY_EFFECTS:
                errors.append(f"[A13-DISCOVERY-001] {qpath}.decision_effects: unsupported effects {sorted(effects-DISCOVERY_EFFECTS)!r}")
            require_string(question, "answer", qpath, errors)
            response_class = require_enum(question, "response_class", qpath, RESPONSE_CLASSES, errors)
            requirement_ids = string_set(require_list(question, "affected_requirement_ids", qpath, errors), f"{qpath}.affected_requirement_ids", errors)
            if question_id:
                question_requirement_ids_by_id[question_id] = requirement_ids
            if requirement_ids - set(decision_requirements):
                errors.append(f"[A13-DISCOVERY-002] {qpath}.affected_requirement_ids: unknown requirements")
            if response_class != "UNKNOWN_SKIP" and not is_text(question.get("answer")):
                errors.append(f"[A13-DISCOVERY-003] {qpath}.answer: non-skip response requires an answer")
            if response_class == "STRATEGIC_CHOICE" and not is_substantive_human_text(question.get("answer")):
                errors.append(f"[A13-STAGE-023] {qpath}.answer: strategic choice needs a substantive human-readable answer; typed records remain Gate authority")
            if round_phase == "POSITIONING" and response_class == "STRATEGIC_CHOICE" and question_id:
                positioning_strategic_choice_question_ids.add(question_id)
            if (
                round_phase == "POSITIONING"
                and response_class == "STRATEGIC_CHOICE"
                and "STRATEGIC_SELECTION" in effects
                and question_id
            ):
                strategic_selection_question_ids.add(question_id)
            require_text(question, "owner", qpath, errors)
    action_map = unique_rows(require_list(discovery, "evidence_actions", "$.discovery", errors), "$.discovery.evidence_actions", errors)
    for action_id, action in action_map.items():
        path = f"$.discovery.evidence_actions[{action_id}]"
        question_ids = string_set(require_list(action, "trigger_question_ids", path, errors), f"{path}.trigger_question_ids", errors, nonempty=True)
        if question_ids - set(question_map):
            errors.append(f"[A13-DISCOVERY-004] {path}.trigger_question_ids: unknown question")
        requirement_ids = string_set(require_list(action, "affected_requirement_ids", path, errors), f"{path}.affected_requirement_ids", errors)
        if requirement_ids - set(decision_requirements):
            errors.append(f"[A13-DISCOVERY-005] {path}.affected_requirement_ids: unknown requirements")
        require_text(action, "decisive_evidence", path, errors)
        require_text(action, "owner", path, errors)
        require_enum(action, "status", path, EVIDENCE_ACTION_STATUSES, errors)
    distillations = unique_rows(require_list(discovery, "distillations", "$.discovery", errors), "$.discovery.distillations", errors)
    distillation_ids_by_phase: dict[str, set[str]] = {"TRUTH": set(), "POSITIONING": set()}
    typed_distillation_ids: dict[str, set[str]] = {
        record_type: set() for record_type in DISCOVERY_DISTILLATION_TYPES
    }
    typed_distillation_question_ids: dict[str, set[str]] = {}
    typed_distillation_fact_ids: dict[str, set[str]] = {}
    one_bet_proof_by_id: dict[str, str] = {}
    for distillation_id, distillation in distillations.items():
        path = f"$.discovery.distillations[{distillation_id}]"
        question_ids = string_set(require_list(distillation, "question_ids", path, errors), f"{path}.question_ids", errors, nonempty=True)
        if question_ids - set(question_map):
            errors.append(f"[A13-DISCOVERY-006] {path}.question_ids: unknown question")
        for phase, phase_question_ids in question_ids_by_phase.items():
            if question_ids and question_ids.issubset(phase_question_ids):
                distillation_ids_by_phase[phase].add(distillation_id)
        require_enum(distillation, "result_type", path, RESPONSE_CLASSES, errors)
        require_text(distillation, "statement", path, errors)
        record_type = distillation.get("record_type")
        typed_strategy_record = record_type in {"PRODUCT_INTENT_BRIEF", "ONE_BET_SELECTION"}
        distillation_fact_ids = string_set(
            require_list(distillation, "fact_ids", path, errors), f"{path}.fact_ids", errors,
            nonempty=typed_strategy_record,
        )
        string_set(require_list(distillation, "claim_ids", path, errors), f"{path}.claim_ids", errors)
        evidence_action_ids = string_set(require_list(distillation, "evidence_action_ids", path, errors), f"{path}.evidence_action_ids", errors)
        if evidence_action_ids - set(action_map):
            errors.append(f"[A13-DISCOVERY-007] {path}.evidence_action_ids: unknown evidence action")
        require_text(distillation, "owner", path, errors)
        payload = distillation.get("payload")
        if record_type is not None:
            if record_type not in DISCOVERY_DISTILLATION_TYPES:
                errors.append(f"[A13-STAGE-019] {path}.record_type: unsupported typed discovery record")
            else:
                typed_distillation_ids[record_type].add(distillation_id)
            if typed_strategy_record:
                typed_distillation_question_ids[distillation_id] = set(question_ids)
                typed_distillation_fact_ids[distillation_id] = set(distillation_fact_ids)
                invalid_fact_ids = distillation_fact_ids - set(fact_map)
                if not distillation_fact_ids or invalid_fact_ids:
                    code = "A13-STAGE-020" if record_type == "PRODUCT_INTENT_BRIEF" else "A13-STAGE-021"
                    errors.append(
                        f"[{code}] {path}.fact_ids: typed strategy record requires a nonempty current-product Fact chain; "
                        f"unknown={sorted(invalid_fact_ids)!r}"
                    )
            if not isinstance(payload, dict):
                errors.append(f"[A13-STAGE-019] {path}.payload: typed discovery record requires an object payload")
            elif record_type == "PRODUCT_INTENT_BRIEF":
                if set(payload) != PRODUCT_INTENT_PAYLOAD_KEYS or any(not is_substantive_human_text(payload.get(key)) for key in PRODUCT_INTENT_PAYLOAD_KEYS):
                    errors.append(f"[A13-STAGE-020] {path}.payload: Product Intent Brief requires exact substantive dimensions {sorted(PRODUCT_INTENT_PAYLOAD_KEYS)!r}")
            elif record_type == "ONE_BET_SELECTION":
                scalar_keys = ONE_BET_PAYLOAD_KEYS - {"selected_route_id", "rejected_route_ids", "rejected_route_reasons", "route_registry", "proof_status"}
                rejected_ids = payload.get("rejected_route_ids") if isinstance(payload, dict) else None
                rejected_reasons = payload.get("rejected_route_reasons") if isinstance(payload, dict) else None
                route_registry = payload.get("route_registry") if isinstance(payload, dict) else None
                route_rows = route_registry if isinstance(route_registry, list) else []
                route_ids = [row.get("route_id") for row in route_rows if isinstance(row, dict)]
                route_map = {
                    str(row.get("route_id")): row for row in route_rows
                    if isinstance(row, dict) and is_text(row.get("route_id"))
                }
                selected_route_id = payload.get("selected_route_id") if isinstance(payload, dict) else None
                selected_route = route_map.get(str(selected_route_id), {})
                if isinstance(payload.get("proof_status"), str):
                    one_bet_proof_by_id[distillation_id] = payload["proof_status"]
                route_registry_valid = (
                    isinstance(route_registry, list)
                    and len(route_rows) >= 2
                    and len(route_rows) == len(route_registry)
                    and len(route_ids) == len(set(route_ids))
                    and all(
                        set(route) == ROUTE_REGISTRY_KEYS
                        and is_text(route.get("route_id"))
                        and route.get("proof_status") in ROUTE_PROOF_STATUSES
                        and all(
                            is_substantive_human_text(route.get(key))
                            for key in ROUTE_REGISTRY_KEYS - {"route_id", "proof_status"}
                        )
                        for route in route_rows
                    )
                )
                if (
                    set(payload) != ONE_BET_PAYLOAD_KEYS
                    or any(not is_substantive_human_text(payload.get(key)) for key in scalar_keys)
                    or not is_text(selected_route_id)
                    or not isinstance(rejected_ids, list) or not rejected_ids
                    or any(not is_text(item) for item in rejected_ids)
                    or len(rejected_ids) != len(set(rejected_ids))
                    or not isinstance(rejected_reasons, dict)
                    or set(rejected_reasons) != set(rejected_ids)
                    or any(not is_substantive_human_text(reason) for reason in rejected_reasons.values())
                    or selected_route_id in set(rejected_ids or [])
                    or not route_registry_valid
                    or set(route_map) != {str(selected_route_id), *[str(item) for item in rejected_ids or []]}
                    or selected_route.get("proof_status") not in SELECTABLE_ROUTE_PROOF_STATUSES
                    or payload.get("proof_status") != selected_route.get("proof_status")
                    or any(
                        payload.get(key) != selected_route.get(key)
                        for key in {"hero_moment", "closest_alternative", "desired_progress", "mechanism", "material_boundary"}
                    )
                ):
                    errors.append(f"[A13-STAGE-021] {path}.payload: One-Bet needs a real two-plus route registry, one evidence-supported selected route, exact rejected-route disposition, aligned route consequences, substantive boundary, and reversible test")
    stage_rows = require_list(discovery, "stage_gates", "$.discovery", errors)
    stage_map: dict[str, dict[str, Any]] = {}
    stage_closed_times: dict[str, datetime] = {}
    usable_source_ids = {
        source_id for source_id, source in source_map.items()
        if source.get("fetch_status") == "ok"
    }
    competitor_source_ids = {
        source_id
        for insight in competitor_map.values()
        if insight.get("fetch_status") == "ok" and insight.get("status") in {"PROVISIONAL", "FROZEN"}
        for source_id in insight.get("source_ids", [])
        if isinstance(source_id, str) and source_id in usable_source_ids
    }
    target_research_source_ids = {
        source_id for source_id, source in source_map.items()
        if source_id in usable_source_ids
        and source.get("source_type") in {
            "PUBLIC_OBSERVED", "BACKEND_OBSERVED", "DOCUMENTED_SPEC",
            "PHYSICAL_OBSERVED", "PHYSICAL_TEST", "VERIFIED_ACCOUNT_DATA",
        }
        and source_id not in competitor_source_ids
    }
    target_child_asins = {
        str(variant.get("child_asin")) for variant in variant_map.values()
        if is_text(variant.get("child_asin"))
    }
    target_page_source_ids = {
        source_id for source_id, source in source_map.items()
        if source_id in usable_source_ids
        and source.get("source_type") == "PUBLIC_OBSERVED"
        and is_live_amazon_product_url(str(source.get("path_or_url", "")))
        and amazon_product_asin(str(source.get("path_or_url", ""))) in target_child_asins
        and source_id not in competitor_source_ids
    }
    for index, raw_stage in enumerate(stage_rows):
        path = f"$.discovery.stage_gates[{index}]"
        stage_row = require_mapping(raw_stage, path, errors)
        if set(stage_row) != DISCOVERY_STAGE_GATE_KEYS:
            errors.append(
                f"[A13-STAGE-001] {path}: stage gate must use exact keys "
                f"{sorted(DISCOVERY_STAGE_GATE_KEYS)!r}"
            )
        stage = require_enum(stage_row, "stage", path, set(DISCOVERY_STAGE_TYPES), errors)
        gate_id = require_text(stage_row, "id", path, errors)
        if stage in stage_map:
            errors.append(f"[A13-STAGE-002] {path}.stage: duplicate stage {stage!r}")
        elif stage:
            stage_map[stage] = stage_row
        expected_id = f"STAGE-{stage}" if stage else ""
        if gate_id and expected_id and gate_id != expected_id:
            errors.append(f"[A13-STAGE-003] {path}.id: expected {expected_id!r}")
        status = require_enum(stage_row, "status", path, DISCOVERY_STAGE_STATUSES, errors)
        result = require_string(stage_row, "result", path, errors)
        reason = require_string(stage_row, "reason", path, errors)
        source_ids = string_set(
            require_list(stage_row, "evidence_source_ids", path, errors),
            f"{path}.evidence_source_ids", errors,
        )
        unknown_sources = source_ids - set(source_map)
        if unknown_sources:
            errors.append(f"[A13-STAGE-004] {path}.evidence_source_ids: unknown IDs {sorted(unknown_sources)!r}")
        unusable_sources = source_ids - usable_source_ids - unknown_sources
        if unusable_sources:
            errors.append(f"[A13-STAGE-005] {path}.evidence_source_ids: unusable IDs {sorted(unusable_sources)!r}")
        record_refs = string_set(
            require_list(stage_row, "record_refs", path, errors),
            f"{path}.record_refs", errors,
        )
        closed_at = require_string(stage_row, "closed_at", path, errors)
        require_text(stage_row, "owner", path, errors)
        if status in {"PASS", "NOT_REQUIRED_WITH_REASON"}:
            if not result or not record_refs or not closed_at:
                errors.append(
                    f"[A13-STAGE-006] {path}: a closed stage requires result, record_refs, and closed_at"
                )
            check_iso(closed_at, f"{path}.closed_at", errors)
            if not is_substantive_human_text(result):
                errors.append(f"[A13-STAGE-023] {path}.result: closed stage needs a substantive human-readable summary; real referenced records remain Gate authority")
            moment = parse_iso_moment(closed_at)
            if moment is not None and stage:
                stage_closed_times[stage] = moment
        elif closed_at:
            errors.append(f"[A13-STAGE-007] {path}.closed_at: open stage cannot have a closure timestamp")
        if status == "NOT_REQUIRED_WITH_REASON" and not reason:
            errors.append(f"[A13-STAGE-008] {path}.reason: required for NOT_REQUIRED_WITH_REASON")
        if workflow_mode == "standalone" and status == "NOT_REQUIRED_WITH_REASON":
            errors.append(f"[A13-STAGE-009] {path}.status: standalone work cannot skip a required stage")
        if workflow_mode == "embedded" and status in {"PASS", "NOT_REQUIRED_WITH_REASON"}:
            if status != "NOT_REQUIRED_WITH_REASON" or "PARENT_HANDOFF" not in record_refs:
                errors.append(
                    f"[A13-STAGE-010] {path}: embedded closure must be NOT_REQUIRED_WITH_REASON and bind PARENT_HANDOFF"
                )

    missing_stages = set(DISCOVERY_STAGE_TYPES) - set(stage_map)
    extra_stages = set(stage_map) - set(DISCOVERY_STAGE_TYPES)
    if missing_stages or extra_stages or len(stage_rows) != len(DISCOVERY_STAGE_TYPES):
        errors.append(
            f"[A13-STAGE-011] $.discovery.stage_gates: require exactly one row for every stage; "
            f"missing={sorted(missing_stages)!r}, extra={sorted(extra_stages)!r}"
        )
    if workflow_mode == "standalone":
        if not competitor_map or not competitor_source_ids:
            errors.append(
                "[A13-STAGE-012] $.competitor_insights: standalone reconnaissance requires at least one usable competitor insight"
            )
        if not usable_voc_ids or not usable_voc_source_ids:
            errors.append(
                "[A13-STAGE-024] $.voc_insights: standalone reconnaissance requires at least one usable, source-bound VOC/use-path insight"
            )
        recon_sources = set(stage_map.get("RECONNAISSANCE", {}).get("evidence_source_ids", []))
        recon_refs = set(stage_map.get("RECONNAISSANCE", {}).get("record_refs", []))
        if (
            not (recon_sources & target_research_source_ids)
            or not (recon_sources & target_page_source_ids)
            or not (recon_sources & competitor_source_ids)
            or not (recon_refs & target_page_source_ids)
            or not (recon_refs & set(competitor_map))
            or not (recon_sources & usable_voc_source_ids)
            or not (recon_refs & usable_voc_ids)
        ):
            errors.append(
                "[A13-STAGE-022] $.discovery.stage_gates[RECONNAISSANCE]: PASS requires a selected-child target-PDP census, real competitor insight, and usable VOC/use-path insight with matching refs/sources"
            )
        if stage_map.get("PRODUCT_TRUTH", {}).get("status") == "PASS":
            if "TRUTH" not in round_phases or evidence_pass.get("status") != "COMPLETE":
                errors.append(
                    "[A13-STAGE-014] $.discovery.stage_gates[PRODUCT_TRUTH]: PASS requires a TRUTH round and COMPLETE evidence pass"
                )
        if stage_map.get("ROUND_2", {}).get("status") == "PASS" and "POSITIONING" not in round_phases:
            errors.append(
                "[A13-STAGE-015] $.discovery.stage_gates[ROUND_2]: PASS requires a POSITIONING round"
            )

        known_stage_refs = (
            {"POSITIONING", "PARENT_HANDOFF"}
            | set(source_map) | set(competitor_map) | set(voc_map) | set(rounds) | set(question_map)
            | set(distillations) | set(action_map) | set(fact_map) | set(claim_map)
            | set(decision_requirements)
        )
        for stage, stage_row in stage_map.items():
            refs = set(stage_row.get("record_refs", []))
            unknown_refs = refs - known_stage_refs
            if unknown_refs:
                errors.append(f"[A13-STAGE-019] $.discovery.stage_gates[{stage}].record_refs: unknown refs {sorted(unknown_refs)!r}")
        truth_refs = set(stage_map.get("PRODUCT_TRUTH", {}).get("record_refs", []))
        if stage_map.get("PRODUCT_TRUTH", {}).get("status") == "PASS" and not (
            truth_refs & round_ids_by_phase["TRUTH"]
            and truth_refs & distillation_ids_by_phase["TRUTH"]
        ):
            errors.append("[A13-STAGE-019] $.discovery.stage_gates[PRODUCT_TRUTH]: PASS requires a TRUTH round and TRUTH-derived distillation")
        round_two_refs = set(stage_map.get("ROUND_2", {}).get("record_refs", []))
        if stage_map.get("ROUND_2", {}).get("status") == "PASS" and not (
            round_two_refs & round_ids_by_phase["POSITIONING"]
            and round_two_refs & distillation_ids_by_phase["POSITIONING"]
        ):
            errors.append("[A13-STAGE-019] $.discovery.stage_gates[ROUND_2]: PASS requires a POSITIONING round and POSITIONING-derived distillation")
        def typed_positioning_chain_is_bound(
            record_id: str,
            stage_refs: set[str],
            *,
            require_strategic_selection: bool,
            require_selected_requirement: bool,
        ) -> bool:
            record_question_ids = typed_distillation_question_ids.get(record_id, set())
            record_fact_ids = typed_distillation_fact_ids.get(record_id, set())
            if (
                not record_question_ids
                or not record_fact_ids
                or not record_question_ids.issubset(positioning_strategic_choice_question_ids)
                or any(question_id not in question_round_id_by_id for question_id in record_question_ids)
            ):
                return False
            selection_question_ids = record_question_ids & strategic_selection_question_ids
            if require_strategic_selection and not selection_question_ids:
                return False
            required_refs = (
                {record_id}
                | record_question_ids
                | {question_round_id_by_id[question_id] for question_id in record_question_ids}
                | record_fact_ids
            )
            if require_selected_requirement:
                selected_requirement_ids = {
                    requirement_id
                    for question_id in selection_question_ids
                    for requirement_id in question_requirement_ids_by_id.get(question_id, set())
                }
                if not selected_requirement_ids:
                    return False
                required_refs |= selected_requirement_ids
            return required_refs.issubset(stage_refs)

        intent_refs = set(stage_map.get("PRODUCT_INTENT_BRIEF", {}).get("record_refs", []))
        bound_intent_record_ids = {
            record_id for record_id in typed_distillation_ids["PRODUCT_INTENT_BRIEF"]
            if typed_positioning_chain_is_bound(
                record_id, intent_refs,
                require_strategic_selection=False,
                require_selected_requirement=False,
            )
        }
        if stage_map.get("PRODUCT_INTENT_BRIEF", {}).get("status") == "PASS" and not bound_intent_record_ids:
            errors.append(
                "[A13-STAGE-020] $.discovery.stage_gates[PRODUCT_INTENT_BRIEF]: PASS requires one bound chain: "
                "typed Product Intent record, native POSITIONING round/question, and that record's current-product Facts"
            )
        one_bet_refs = set(stage_map.get("ONE_BET", {}).get("record_refs", []))
        bound_one_bet_record_ids = {
            record_id for record_id in typed_distillation_ids["ONE_BET_SELECTION"]
            if typed_positioning_chain_is_bound(
                record_id, one_bet_refs,
                require_strategic_selection=True,
                require_selected_requirement=True,
            )
        }
        if stage_map.get("ONE_BET", {}).get("status") == "PASS" and not bound_one_bet_record_ids:
            errors.append(
                "[A13-STAGE-021] $.discovery.stage_gates[ONE_BET]: PASS requires one bound chain: typed One-Bet record, "
                "native POSITIONING/STRATEGIC_SELECTION question, its selected requirement, and that record's current-product Facts"
            )
        if stage_map.get("ONE_BET", {}).get("status") == "PASS" and not any(
            one_bet_proof_by_id.get(record_id) == "PROVED"
            for record_id in bound_one_bet_record_ids
        ):
            errors.append("[A13-STAGE-021] $.discovery.stage_gates[ONE_BET]: PASS and consumer construction require selected route proof_status PROVED")

    ordered_moments = [stage_closed_times.get(stage) for stage in DISCOVERY_STAGE_TYPES]
    if all(moment is not None for moment in ordered_moments):
        if any(ordered_moments[index] > ordered_moments[index + 1] for index in range(len(ordered_moments) - 1)):
            errors.append(
                "[A13-STAGE-016] $.discovery.stage_gates: closure times must follow reconnaissance -> product truth -> round 2 -> product intent -> one bet"
            )
    all_stage_gates_closed = (
        len(stage_map) == len(DISCOVERY_STAGE_TYPES)
        and all(
            stage_map.get(stage, {}).get("status")
            == ("PASS" if workflow_mode == "standalone" else "NOT_REQUIRED_WITH_REASON")
            for stage in DISCOVERY_STAGE_TYPES
        )
    )

    closure = require_mapping(discovery.get("closure"), "$.discovery.closure", errors)
    declared_closure = require_enum(closure, "status", "$.discovery.closure", DISCOVERY_CLOSURE_STATUSES, errors)
    closed_at = require_string(closure, "closed_at", "$.discovery.closure", errors)
    if closed_at:
        check_iso(closed_at, "$.discovery.closure.closed_at", errors)
    require_text(closure, "owner", "$.discovery.closure", errors)
    reason = require_string(closure, "reason", "$.discovery.closure", errors)
    discovery_report = build_discovery_report(
        workflow_mode=workflow_mode,
        discovery_mode=discovery_mode,
        evidence_pass=evidence_pass,
        has_rounds=bool(rounds),
        question_map=question_map,
        action_map=action_map,
        distillations=distillations,
        declared_closure=declared_closure,
        closure_reason=reason,
        decision_requirements=decision_requirements,
        atom_map=atom_map,
        source_map=source_map,
        source_scopes=source_scopes,
        fact_map=fact_map,
        claim_map=claim_map,
        variant_map=variant_map,
        marketplace=marketplace,
        locale=locale,
    )
    errors.extend(discovery_report.errors)
    if discovery_report.derived_closure in {"PASS", "NOT_REQUIRED_WITH_REASON"} and not all_stage_gates_closed:
        errors.append(
            "[A13-STAGE-017] $.discovery.closure: cannot close until all governed stages are closed"
        )
    return discovery_report.derived_closure, action_map, all_stage_gates_closed


def validate_v13_handoff_binding(
    handoff: dict[str, Any],
    workflow_mode: str,
    assertions: dict[str, dict[str, Any]],
    atom_rows: list[Any],
    source_hash: str,
    variant_map: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    """Validate the child copy of immutable handoff payload; never read parent."""
    handoff_assertions: set[str] = set()
    handoff_atom_rows: list[Any] = []
    if workflow_mode == "embedded":
        handoff_assertions = string_set(
            require_list(handoff, "canonical_assertion_ids", "$.enriched_content_handoff", errors),
            "$.enriched_content_handoff.canonical_assertion_ids", errors, nonempty=True,
        )
        handoff_atom_rows = require_list(handoff, "requirement_atoms", "$.enriched_content_handoff", errors)
    handoff_report = build_handoff_report(
        handoff=handoff,
        workflow_mode=workflow_mode,
        assertion_ids=set(assertions),
        handoff_assertion_ids=handoff_assertions,
        atom_rows=atom_rows,
        handoff_atom_rows=handoff_atom_rows,
        source_hash=source_hash,
        variant_ids=set(variant_map),
    )
    errors.extend(handoff_report.errors)



def validate_v13_coverage_and_result(
    root: dict[str, Any],
    atom_map: dict[str, dict[str, Any]],
    decision_requirements: dict[str, dict[str, Any]],
    answers_by_atom: dict[str, list[dict[str, Any]]],
    answer_map: dict[str, dict[str, Any]],
    carrier_map: dict[str, dict[str, Any]],
    closure_status: str,
    denominator_status: str,
    delta_map: dict[str, dict[str, Any]],
    action_map: dict[str, dict[str, Any]],
    conclusion: str,
    assertions: dict[str, dict[str, Any]],
    expected_denominator_hash: str,
    errors: list[str],
) -> dict[str, Any]:
    """Derive atom coverage and the non-authorizing component result."""
    capabilities = {
        str(row.get("id")): row for row in root.get("capability_snapshots", [])
        if isinstance(row, dict) and is_text(row.get("id"))
    }
    summary = require_mapping(root.get("coverage_summary"), "$.coverage_summary", errors)
    summary_gaps = string_set(require_list(summary, "gap_atom_ids", "$.coverage_summary", errors), "$.coverage_summary.gap_atom_ids", errors)
    component = require_mapping(root.get("component_result"), "$.component_result", errors)
    declared_component = require_enum(component, "status", "$.component_result", COMPONENT_RESULT_STATUSES, errors)
    component_gaps = string_set(require_list(component, "gap_atom_ids", "$.component_result", errors), "$.component_result.gap_atom_ids", errors)
    component_deltas = string_set(require_list(component, "open_delta_request_ids", "$.component_result", errors), "$.component_result.open_delta_request_ids", errors)
    require_text(component, "owner", "$.component_result", errors)
    coverage_report = build_coverage_report(
        capabilities=capabilities,
        atom_map=atom_map,
        decision_requirements=decision_requirements,
        answers_by_atom=answers_by_atom,
        carrier_map=carrier_map,
        closure_status=closure_status,
        denominator_status=denominator_status,
        delta_map=delta_map,
        action_map=action_map,
        conclusion=conclusion,
        assertion_count=len(assertions),
        expected_denominator_hash=expected_denominator_hash,
        summary_required=summary.get("p0_atoms_required"),
        summary_pass=summary.get("p0_atoms_pass"),
        summary_gap_ids=summary_gaps,
        declared_component=declared_component,
        component_gap_ids=component_gaps,
        component_delta_ids=component_deltas,
        page_pass_implied=component.get("page_pass_implied"),
        publication_authorized=component.get("publication_authorized"),
    )
    errors.extend(coverage_report.errors)
    return dict(coverage_report.counts)

def validate_v13_contract(
    root: dict[str, Any],
    project: dict[str, Any],
    conclusion: str,
    marketplace: str,
    locale: str,
    envelope: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
    source_scopes: dict[str, dict[str, Any]],
    fact_map: dict[str, dict[str, Any]],
    fact_scopes: dict[str, dict[str, Any]],
    claim_map: dict[str, dict[str, Any]],
    claim_scopes: dict[str, dict[str, Any]],
    competitor_map: dict[str, dict[str, Any]],
    module_map: dict[str, dict[str, Any]],
    carrier_map: dict[str, dict[str, Any]],
    answer_map: dict[str, dict[str, Any]],
    delta_map: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    """Validate v1.3 discovery, frozen-parent bindings and atom coverage.

    This function intentionally validates only the child contract. The package
    coordinator owns parent terminal state and cross-file reconciliation.
    """
    workflow = require_mapping(root.get("workflow_context"), "$.workflow_context", errors)
    workflow_mode = str(workflow.get("mode", ""))
    handoff = require_mapping(root.get("enriched_content_handoff"), "$.enriched_content_handoff", errors)
    _, adapter_issues = validate_category_adapter(root.get("category_adapter"), workflow_mode)
    errors.extend(adapter_issues)

    # Real variant rows are the only allowed atom denominator. We never create a
    # pack/color/size cartesian product from top-level scope lists.
    variant_map: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(require_list(root, "variants", "$", errors)):
        path = f"$.variants[{index}]"
        row = require_mapping(raw, path, errors)
        row_id = require_text(row, "id", path, errors)
        if row_id in variant_map:
            errors.append(f"{path}.id: duplicate id {row_id!r}")
        elif row_id:
            variant_map[row_id] = row

    assertions = unique_rows(
        require_list(root, "canonical_assertions", "$", errors),
        "$.canonical_assertions", errors,
    )
    assertion_scopes: dict[str, dict[str, Any]] = {}
    for assertion_id, assertion in assertions.items():
        path = f"$.canonical_assertions[{assertion_id}]"
        require_text(assertion, "statement", path, errors)
        assertion_scope = validate_app_scope(assertion.get("application_scope"), f"{path}.application_scope", errors)
        assertion_scopes[assertion_id] = assertion_scope
        ensure_scope_subset(assertion_scope, envelope, f"{path}.application_scope", "top-level envelope", errors)
        variant_ids = string_set(require_list(assertion, "variant_row_ids", path, errors), f"{path}.variant_row_ids", errors, nonempty=True)
        unknown_variants = variant_ids - set(variant_map)
        if unknown_variants:
            errors.append(f"[A13-ASSERT-001] {path}.variant_row_ids: unknown IDs {sorted(unknown_variants)!r}")
        if len(variant_ids) != 1:
            errors.append(f"[A13-ASSERT-006] {path}.variant_row_ids: each assertion must bind exactly one real variant row")
        elif not unknown_variants:
            variant = variant_map[next(iter(variant_ids))]
            expected_scope = {
                "marketplaces": {str(variant.get("marketplace", ""))},
                "locales": {str(variant.get("locale", ""))},
                "parent_asins": {str(variant.get("parent_asin", ""))},
                "child_asins": {str(variant.get("child_asin", ""))},
                "packs": {str(variant.get("pack", ""))},
                "colors": {str(variant.get("color", ""))},
                "sizes_or_capacities": {str(variant.get("size_or_capacity", ""))},
            }
            if any(assertion_scope.get(key) != values for key, values in expected_scope.items()):
                errors.append(f"[A13-ASSERT-007] {path}.application_scope: must exactly match its real variant row")
        fact_ids = string_set(require_list(assertion, "fact_ids", path, errors), f"{path}.fact_ids", errors)
        claim_ids = string_set(require_list(assertion, "claim_ids", path, errors), f"{path}.claim_ids", errors)
        if not (fact_ids or claim_ids):
            errors.append(f"[A13-ASSERT-002] {path}: assertion requires at least one fact or claim")
        if fact_ids - set(fact_map) or claim_ids - set(claim_map):
            errors.append(f"[A13-ASSERT-003] {path}: unknown fact or claim reference")
        for claim_id in claim_ids & set(claim_map):
            claim_fact_ids = set(claim_map[claim_id].get("fact_ids", [])) if isinstance(claim_map[claim_id].get("fact_ids"), list) else set()
            if not claim_fact_ids or not claim_fact_ids.issubset(fact_ids):
                errors.append(f"[A13-ASSERT-008] {path}: assertion must carry the complete fact chain for claim {claim_id!r}")
        locale_rows = require_list(assertion, "locale_expressions", path, errors)
        seen_locales: set[str] = set()
        for index, raw_expression in enumerate(locale_rows):
            expression_path = f"{path}.locale_expressions[{index}]"
            expression = require_mapping(raw_expression, expression_path, errors)
            expression_locale = require_text(expression, "locale", expression_path, errors)
            if expression_locale in seen_locales:
                errors.append(f"[A13-ASSERT-009] {expression_path}.locale: duplicate locale")
            seen_locales.add(expression_locale)
            require_text(expression, "text", expression_path, errors)
            expression_facts = string_set(require_list(expression, "fact_ids", expression_path, errors), f"{expression_path}.fact_ids", errors)
            expression_claims = string_set(require_list(expression, "claim_ids", expression_path, errors), f"{expression_path}.claim_ids", errors)
            if not expression_facts.issubset(fact_ids) or not expression_claims.issubset(claim_ids):
                errors.append(f"[A13-ASSERT-010] {expression_path}: locale expression cannot expand the canonical evidence chain")
        if seen_locales != {locale}:
            errors.append(f"[A13-ASSERT-011] {path}.locale_expressions: must contain exactly the project locale {locale!r}")
        for fact_id in fact_ids & set(fact_scopes):
            ensure_scope_subset(assertion_scope, fact_scopes[fact_id], f"{path}.application_scope", f"fact {fact_id!r}", errors)
        for claim_id in claim_ids & set(claim_scopes):
            ensure_scope_subset(assertion_scope, claim_scopes[claim_id], f"{path}.application_scope", f"claim {claim_id!r}", errors)
        status = require_enum(assertion, "publish_status", path, ASSERTION_STATUSES, errors)
        require_text(assertion, "owner", path, errors)
        if status == "PUBLISHABLE":
            for fact_id in fact_ids:
                if fact_map.get(fact_id, {}).get("publish_status") != "PUBLISHABLE":
                    errors.append(f"[A13-ASSERT-004] {path}: publishable assertion uses non-publishable fact {fact_id!r}")
            for claim_id in claim_ids:
                if claim_map.get(claim_id, {}).get("publish_status") != "PUBLISHABLE":
                    errors.append(f"[A13-ASSERT-005] {path}: publishable assertion uses non-publishable claim {claim_id!r}")

    denominator = require_mapping(root.get("decision_denominator_snapshot"), "$.decision_denominator_snapshot", errors)
    denominator_status = require_enum(denominator, "status", "$.decision_denominator_snapshot", DENOMINATOR_STATUSES, errors)
    denominator_source = require_enum(denominator, "source", "$.decision_denominator_snapshot", DENOMINATOR_SOURCES, errors)
    source_hash = require_string(denominator, "source_hash", "$.decision_denominator_snapshot", errors)
    frozen_at = require_string(denominator, "frozen_at", "$.decision_denominator_snapshot", errors)
    if denominator_status == "FROZEN":
        check_iso(frozen_at, "$.decision_denominator_snapshot.frozen_at", errors)
    decision_map = require_mapping(root.get("decision_map"), "$.decision_map", errors)
    requirement_rows = require_list(decision_map, "requirements", "$.decision_map", errors)
    decision_requirements = unique_rows(requirement_rows, "$.decision_map.requirements", errors)
    requirement_scopes: dict[str, dict[str, Any]] = {}
    for requirement_id, requirement in decision_requirements.items():
        path = f"$.decision_map.requirements[{requirement_id}]"
        require_text(requirement, "buyer_question", path, errors)
        require_enum(requirement, "priority", path, PRIORITIES, errors)
        requirement_scope = validate_handoff_application_scope(
            requirement.get("application_scope"), f"{path}.application_scope", marketplace, locale, errors,
        )
        requirement_scopes[requirement_id] = requirement_scope
        fact_ids = string_set(require_list(requirement, "fact_ids", path, errors), f"{path}.fact_ids", errors)
        claim_ids = string_set(require_list(requirement, "claim_ids", path, errors), f"{path}.claim_ids", errors)
        if fact_ids - set(fact_map) or claim_ids - set(claim_map):
            errors.append(f"[A13-DENOM-006] {path}: unknown fact or claim reference")
        for key in ("native_answer_required", "early_disclosure_required"):
            if requirement.get(key) not in {True, False}:
                errors.append(f"[A13-DENOM-007] {path}.{key}: required boolean")
        if require_text(requirement, "assigned_surface", path, errors) != "enriched_content":
            errors.append(f"[A13-DENOM-008] {path}.assigned_surface: must be enriched_content")
        require_enum(requirement, "status", path, ATOM_STATUSES, errors)

    atom_rows = require_list(denominator, "atoms", "$.decision_denominator_snapshot", errors)
    atom_map = unique_rows(atom_rows, "$.decision_denominator_snapshot.atoms", errors)
    denominator_hash = require_text(denominator, "checksum", "$.decision_denominator_snapshot", errors)
    hashable_denominator = copy.deepcopy(denominator)
    hashable_denominator["checksum"] = ""
    expected_denominator_hash = canonical_object_hash(hashable_denominator)
    if denominator_hash and denominator_hash != expected_denominator_hash:
        errors.append("[A13-DENOM-003] $.decision_denominator_snapshot.checksum: does not match canonical projection")

    if workflow_mode == "embedded" and handoff.get("decision_requirements") != requirement_rows:
        errors.append("[A13-HANDOFF-029] $.decision_map.requirements: must exactly match delegated frozen handoff requirements")
    requirement_ids = string_set(require_list(denominator, "requirement_ids", "$.decision_denominator_snapshot", errors), "$.decision_denominator_snapshot.requirement_ids", errors)
    variant_ids = string_set(require_list(denominator, "variant_row_ids", "$.decision_denominator_snapshot", errors), "$.decision_denominator_snapshot.variant_row_ids", errors)
    if requirement_ids != set(decision_requirements):
        errors.append("[A13-DENOM-009] $.decision_denominator_snapshot.requirement_ids: must exactly match delegated requirements")
    if variant_ids != {str(atom.get('variant_row_id', '')) for atom in atom_map.values()}:
        errors.append("[A13-DENOM-010] $.decision_denominator_snapshot.variant_row_ids: must exactly match delegated atoms")

    for atom_id, atom in atom_map.items():
        path = f"$.decision_denominator_snapshot.atoms[{atom_id}]"
        if set(atom) != {"id", "requirement_id", "marketplace", "locale", "variant_row_id"}:
            errors.append(f"[A13-ATOM-007] {path}: atom must use the exact minimal frozen shape")
        requirement_id = require_text(atom, "requirement_id", path, errors)
        if requirement_id not in decision_requirements:
            errors.append(f"[A13-ATOM-001] {path}.requirement_id: unknown requirement")
        if require_text(atom, "marketplace", path, errors) != marketplace or require_text(atom, "locale", path, errors) != locale:
            errors.append(f"[A13-ATOM-002] {path}: marketplace/locale mismatch")
        variant_row_id = require_text(atom, "variant_row_id", path, errors)
        if variant_row_id not in variant_map:
            errors.append(f"[A13-ATOM-003] {path}.variant_row_id: unknown real variant row")

    if denominator_status == "FROZEN":
        if not variant_map:
            errors.append("[A13-DENOM-004] $.variants: frozen denominator requires real variant rows")
        expected_pairs = set(expected_decision_pairs(
            decision_requirements, requirement_scopes, variant_map,
        ))
        actual_pairs = {
            (str(atom.get("requirement_id", "")), str(atom.get("variant_row_id", "")))
            for atom in atom_map.values()
        }
        if expected_pairs != actual_pairs:
            errors.append(
                "[A13-DENOM-005] $.decision_denominator_snapshot.atoms: "
                f"P0 atoms must exactly cover real requirement/variant pairs; missing={sorted(expected_pairs-actual_pairs)!r}, extra={sorted(actual_pairs-expected_pairs)!r}"
            )
    if workflow_mode == "embedded":
        if denominator_source != "PARENT_HANDOFF":
            errors.append("[A13-DENOM-011] $.decision_denominator_snapshot.source: embedded mode requires PARENT_HANDOFF")
        if source_hash != handoff.get("decision_denominator_hash"):
            errors.append("[A13-DENOM-012] $.decision_denominator_snapshot.source_hash: must bind the full parent denominator hash")
    elif denominator_source != "STANDALONE" or source_hash:
        errors.append("[A13-DENOM-013] $.decision_denominator_snapshot: standalone mode requires STANDALONE source and empty source_hash")

    closure_status, action_map, all_stage_gates_closed = validate_v13_discovery(
        root.get("discovery"), root.get("voc_insights"), workflow_mode, decision_requirements, atom_map,
        source_map, source_scopes, fact_map, claim_map, competitor_map, variant_map,
        marketplace, locale, errors,
    )

    candidate_sections = {
        section: len([row for row in root.get(section, []) if isinstance(row, dict)])
        for section in ("modules", "assets", "decision_answer_units", "carriers", "canonical_assertions")
    }
    candidate_sections = {name: count for name, count in candidate_sections.items() if count}
    if candidate_sections and not all_stage_gates_closed:
        errors.append(
            "[A13-PHASE-002] $.discovery.stage_gates: consumer-facing A+ candidates are forbidden before all governed stages close; "
            f"populated sections={candidate_sections!r}"
        )
    conditional = project.get("conditional_draft", {}) if isinstance(project.get("conditional_draft"), dict) else {}
    if conditional.get("maximum_work") == "full_production" and not all_stage_gates_closed:
        errors.append(
            "[A13-PHASE-003] $.project.conditional_draft.maximum_work: full_production requires all governed stages closed"
        )
    if workflow_mode == "standalone" and all_stage_gates_closed:
        positioning = root.get("positioning") if isinstance(root.get("positioning"), dict) else {}
        required_positioning_fields = (
            "core_audience", "high_value_situation", "job", "category",
            "primary_benefit", "statement", "owner",
        )
        if positioning.get("status") != "SUPPORTED" or any(
            not is_text(positioning.get(key)) for key in required_positioning_fields
        ):
            errors.append(
                "[A13-STAGE-018] $.positioning: Product Intent Brief and One-Bet closure require one supported, non-empty positioning route"
            )

    validate_v13_handoff_binding(
        handoff, workflow_mode, assertions, atom_rows, source_hash, variant_map, errors,
    )

    for request_id, request in delta_map.items():
        path = f"$.delta_evidence_requests[{request_id}]"
        affected_atoms = string_set(
            require_list(request, "affected_atom_ids", path, errors),
            f"{path}.affected_atom_ids", errors,
            nonempty=request.get("status") == "OPEN",
        )
        if affected_atoms - set(atom_map):
            errors.append(f"[A13-DELTA-036] {path}.affected_atom_ids: unknown atom IDs {sorted(affected_atoms-set(atom_map))!r}")
        require_enum(
            request, "gap_type", path,
            {"PARENT_EVIDENCE", "STANDALONE_EVIDENCE", "LOCAL_CONSTRUCTION", "LOCAL_QA", "CAPABILITY"},
            errors,
        )
        _, lineage_issues = validate_delta_lineage(
            request_id, request, workflow_mode, handoff,
        )
        errors.extend(lineage_issues)

    def variant_scope_is_exact(scope: dict[str, Any], variant: dict[str, Any]) -> bool:
        return (
            scope.get("marketplaces") == {str(variant.get("marketplace", ""))}
            and scope.get("locales") == {str(variant.get("locale", ""))}
            and scope.get("parent_asins") == {str(variant.get("parent_asin", ""))}
            and scope.get("child_asins") == {str(variant.get("child_asin", ""))}
            and scope.get("packs") == {str(variant.get("pack", ""))}
            and scope.get("colors") == {str(variant.get("color", ""))}
            and scope.get("sizes_or_capacities") == {str(variant.get("size_or_capacity", ""))}
        )

    answers_by_atom: dict[str, list[dict[str, Any]]] = {}
    for answer_id, answer in answer_map.items():
        path = f"$.decision_answer_units[{answer_id}]"
        atom_id = require_text(answer, "requirement_atom_id", path, errors)
        atom = atom_map.get(atom_id)
        if atom is None:
            errors.append(f"[A13-ANSWER-030] {path}.requirement_atom_id: unknown atom")
            continue
        if answer.get("requirement_id") != atom.get("requirement_id"):
            errors.append(f"[A13-ANSWER-031] {path}.requirement_id: differs from atom")
        variant_id = require_text(answer, "variant_row_id", path, errors)
        if variant_id != atom.get("variant_row_id"):
            errors.append(f"[A13-ANSWER-032] {path}.variant_row_id: differs from atom")
        assertion_ids = string_set(require_list(answer, "canonical_assertion_ids", path, errors), f"{path}.canonical_assertion_ids", errors)
        allowed_assertions = set(handoff.get("canonical_assertion_ids", [])) if workflow_mode == "embedded" else set(assertions)
        if not assertion_ids or not assertion_ids.issubset(allowed_assertions):
            errors.append(f"[A13-ANSWER-033] {path}.canonical_assertion_ids: must be a non-empty subset of frozen assertions")
        if any(assertions.get(assertion_id, {}).get("publish_status") != "PUBLISHABLE" for assertion_id in assertion_ids):
            errors.append(f"[A13-ANSWER-034] {path}: final answer cannot use held/conflicting assertion")
        answer_fact_ids = set(answer.get("fact_ids", [])) if isinstance(answer.get("fact_ids"), list) else set()
        answer_claim_ids = set(answer.get("claim_ids", [])) if isinstance(answer.get("claim_ids"), list) else set()
        requirement = decision_requirements.get(str(atom.get("requirement_id", "")), {})
        atom_fact_ids = set(requirement.get("fact_ids", [])) if isinstance(requirement.get("fact_ids"), list) else set()
        atom_claim_ids = set(requirement.get("claim_ids", [])) if isinstance(requirement.get("claim_ids"), list) else set()
        if not answer_fact_ids.issubset(atom_fact_ids) or not answer_claim_ids.issubset(atom_claim_ids):
            errors.append(f"[A13-ANSWER-036] {path}: answer evidence must be a subset of its atom evidence")
        module = module_map.get(str(answer.get("module_id", "")), {})
        module_fact_ids = set(module.get("fact_ids", [])) if isinstance(module.get("fact_ids"), list) else set()
        module_claim_ids = set(module.get("claim_ids", [])) if isinstance(module.get("claim_ids"), list) else set()
        if not module_fact_ids.issubset(atom_fact_ids) or not module_claim_ids.issubset(atom_claim_ids):
            errors.append(f"[A13-ANSWER-037] {path}: module evidence must stay within its atom/handoff evidence")
        carrier = carrier_map.get(str(answer.get("primary_carrier_id", "")), {})
        carrier_fact_ids = set(carrier.get("fact_ids", [])) if isinstance(carrier.get("fact_ids"), list) else set()
        carrier_claim_ids = set(carrier.get("claim_ids", [])) if isinstance(carrier.get("claim_ids"), list) else set()
        carrier_assertion_ids = set(carrier.get("canonical_assertion_ids", [])) if isinstance(carrier.get("canonical_assertion_ids"), list) else set()
        if not carrier_fact_ids.issubset(module_fact_ids) or not carrier_claim_ids.issubset(module_claim_ids):
            errors.append(f"[A13-ANSWER-038] {path}: carrier evidence must be a subset of module evidence")
        if not assertion_ids.issubset(carrier_assertion_ids):
            errors.append(f"[A13-ANSWER-039] {path}: answer assertions must be carried by the primary carrier")
        if variant_id in variant_map:
            answer_scope = validate_app_scope(answer.get("application_scope"), f"{path}.application_scope", errors)
            if not variant_scope_is_exact(answer_scope, variant_map[variant_id]):
                errors.append(f"[A13-ANSWER-035] {path}.application_scope: must exactly match its real variant row")
            for assertion_id in sorted(assertion_ids):
                assertion = assertions.get(assertion_id, {})
                assertion_variants = set(assertion.get("variant_row_ids", [])) if isinstance(assertion.get("variant_row_ids"), list) else set()
                if assertion_variants != {variant_id} or not variant_scope_is_exact(
                    assertion_scopes.get(assertion_id, {}), variant_map[variant_id],
                ):
                    errors.append(
                        f"[A13-ANSWER-040] {path}.canonical_assertion_ids: assertion {assertion_id!r} does not exactly cover this atom variant"
                    )
        answers_by_atom.setdefault(atom_id, []).append(answer)

    for carrier_id, carrier in carrier_map.items():
        path = f"$.carriers[{carrier_id}]"
        variant_ids = string_set(require_list(carrier, "variant_row_ids", path, errors), f"{path}.variant_row_ids", errors, nonempty=True)
        if variant_ids - set(variant_map):
            errors.append(f"[A13-CARRIER-030] {path}.variant_row_ids: unknown variants")
        assertion_ids = string_set(require_list(carrier, "canonical_assertion_ids", path, errors), f"{path}.canonical_assertion_ids", errors)
        if assertion_ids - set(assertions):
            errors.append(f"[A13-CARRIER-031] {path}.canonical_assertion_ids: unknown assertions")

    for index, raw_asset in enumerate(root.get("assets", [])):
        if not isinstance(raw_asset, dict):
            continue
        path = f"$.assets[{index}]"
        variant_ids = string_set(require_list(raw_asset, "variant_row_ids", path, errors), f"{path}.variant_row_ids", errors, nonempty=True)
        if variant_ids - set(variant_map):
            errors.append(f"[A13-ASSET-030] {path}.variant_row_ids: unknown variants")
        assertion_ids = string_set(require_list(raw_asset, "canonical_assertion_ids", path, errors), f"{path}.canonical_assertion_ids", errors)
        if assertion_ids - set(assertions):
            errors.append(f"[A13-ASSET-031] {path}.canonical_assertion_ids: unknown assertions")

    return validate_v13_coverage_and_result(
        root, atom_map, decision_requirements, answers_by_atom, answer_map, carrier_map,
        closure_status, denominator_status, delta_map, action_map, conclusion,
        assertions, expected_denominator_hash, errors,
    )


def _domain_ops() -> dict[str, Any]:
    """Expose validation primitives to dependency-injected pure domains."""
    names = (
        "require_mapping", "require_text", "require_string", "require_list",
        "require_enum", "check_iso", "check_asin", "string_set", "unique_rows",
        "validate_app_scope", "ensure_scope_subset", "require_complete_scope",
        "is_text", "is_official_amazon_url", "is_community_qa_label",
        "parse_iso_moment", "required_pass_gate_ids", "report_structure_valid",
        "validate_v12_contract", "validate_v13_contract",
        "build_fact_evidence_report", "build_publication_report",
        "build_readback_row_report", "build_readback_coverage_report",
        "SOURCE_TYPES", "FETCH_STATUSES", "MIRROR_SOURCE_TYPES",
        "CONTENT_ELIGIBILITY", "EVIDENCE_TYPES", "FACT_CLASSES",
        "EVIDENCE_STRENGTHS", "PUBLISH_STATUSES", "RISK_TYPES",
        "CONTENT_STATUSES", "FINAL_CONTENT_STATUSES",
        "UNSUPPORTED_CONSUMER_EVIDENCE", "HIGH_RISK_TYPES",
        "DECISION_STATUSES", "COMPETITOR_ROLES", "COMPETITOR_STATUSES",
        "CONFLICT_STATUSES", "MAXIMUM_WORK", "VARIANT_STATUSES", "PRIORITIES",
        "QA_STATUSES", "SYNTHETIC_PERSON", "GENERATION_METHODS", "SHA256_RE",
        "GATE_STATUSES", "EXPERIMENT_TYPES", "EXPERIMENT_ELIGIBILITY",
        "ATTRIBUTION_BOUNDARIES", "EXPERIMENT_STATUSES", "CONCLUSIONS",
        "AUTHORIZATION_STATUSES", "AUTHORIZED_ACTIONS", "BASELINE_STATUSES",
        "CONCURRENT_EDIT_STATUSES", "CHANGE_APPROVAL_STATUSES", "CHANGE_STATUSES",
        "ROLLBACK_STATUSES", "READBACK_PHASES", "READBACK_FIELDS",
        "READBACK_FIELD_STATUSES", "READBACK_STATUSES",
    )
    namespace = globals()
    return {name: namespace[name] for name in names}


def validate_bundle(data: Any, *, source_path: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    root = require_mapping(data, "$", errors)
    schema_version = require_text(root, "schema_version", "$", errors)
    expected_keys = ROOT_KEYS_V13 if schema_version == "1.3" else ROOT_KEYS_V12 if schema_version == "1.2" else ROOT_KEYS_V11
    missing = sorted(expected_keys - set(root))
    if missing:
        errors.append(f"$: missing top-level keys: {', '.join(missing)}")
    if schema_version and schema_version not in SCHEMA_VERSIONS:
        errors.append("$.schema_version: populated bundles must use '1.1', '1.2', or '1.3'")
    if schema_version == "1.1":
        extras = sorted(set(root) & V12_ONLY_KEYS)
        if extras:
            errors.append(f"$: schema 1.1 cannot carry v1.2-only keys: {', '.join(extras)}")
        unknown = sorted(set(root) - ROOT_KEYS_V11)
        if unknown:
            errors.append(f"$: schema 1.1 has unknown top-level keys: {', '.join(unknown)}")
    elif schema_version == "1.2":
        extras = sorted(set(root) - ROOT_KEYS_V12 - ALLOWED_ROOT_EXTRAS)
        if extras:
            errors.append(f"$: schema 1.2 has unknown top-level keys: {', '.join(extras)}")
    elif schema_version == "1.3":
        extras = sorted(set(root) - ROOT_KEYS_V13 - ALLOWED_ROOT_EXTRAS)
        if extras:
            errors.append(f"$: schema 1.3 has unknown top-level keys: {', '.join(extras)}")
    for forbidden_path in find_forbidden_v12_keys(root):
        metric_code = "A13" if schema_version == "1.3" else "A12" if schema_version == "1.2" else "A11"
        errors.append(f"[{metric_code}-METRIC-001] {forbidden_path}: unsupported normative metric or fixed threshold")
    project = require_mapping(root.get("project"), "$.project", errors)
    if str(project.get("status", "")).strip() == "SCAFFOLD":
        pollution = scaffold_pollution_paths(root)
        if pollution:
            errors.append(f"[A12-SCAFFOLD-001] $: populated SCAFFOLD contains operational data at {pollution!r}")
        warnings.append("Template scaffold only: populate and change project.status before delivery.")
        errors = sorted(dict.fromkeys(errors))
        warnings = sorted(dict.fromkeys(warnings))
        return {
            "ok": not errors, "template_only": True, "errors": errors, "warnings": warnings,
            "counts": {key: len(root.get(key, [])) if isinstance(root.get(key), list) else 0 for key in ("sources", "facts", "claims", "variants", "modules", "assets", "capability_snapshots", "decision_answer_units", "carriers", "delta_evidence_requests", "canonical_assertions", "gates", "experiments")},
            "native_coverage_assessed": False,
            "atom_coverage_assessed": False,
            "structural_valid": False,
            "parent_bundle_verified": None,
            "project_conclusion": str(project.get("conclusion", "NO_VALID_CONCLUSION")),
            "result_level": "TEMPLATE_ONLY" if not errors else "INVALID",
        }

    require_text(project, "title", "$.project", errors)
    marketplace = require_text(project, "marketplace", "$.project", errors)
    locale = require_text(project, "locale", "$.project", errors)
    target_type = require_enum(project, "target_type", "$.project", TARGET_TYPES, errors)
    mode = require_enum(project, "mode", "$.project", MODES, errors)
    require_text(project, "status", "$.project", errors)
    snapshot_date = require_text(project, "snapshot_date", "$.project", errors)
    check_iso(snapshot_date, "$.project.snapshot_date", errors)
    write_scope = require_enum(project, "write_scope", "$.project", {"read_only", "explicit_write"}, errors)
    conclusion = require_enum(project, "conclusion", "$.project", CONCLUSIONS, errors)
    focal = require_mapping(project.get("focal_identity"), "$.project.focal_identity", errors)
    focal_identifier = require_text(focal, "identifier", "$.project.focal_identity", errors)
    identifier_type = require_enum(focal, "identifier_type", "$.project.focal_identity", IDENTIFIER_TYPES, errors)
    identity_status = require_enum(focal, "identity_status", "$.project.focal_identity", IDENTITY_STATUSES, errors)
    verified_child = require_string(focal, "verified_focal_child", "$.project.focal_identity", errors)
    provisional_parent = require_string(focal, "provisional_parent", "$.project.focal_identity", errors)
    focal_source_ids = string_set(require_list(focal, "verification_source_ids", "$.project.focal_identity", errors), "$.project.focal_identity.verification_source_ids", errors)
    if identifier_type == "asin":
        check_asin(focal_identifier, "$.project.focal_identity.identifier", errors)
    check_asin(verified_child, "$.project.focal_identity.verified_focal_child", errors, optional=True)
    check_asin(provisional_parent, "$.project.focal_identity.provisional_parent", errors, optional=True)
    conditional = require_mapping(project.get("conditional_draft"), "$.project.conditional_draft", errors)
    conditional_status = require_enum(conditional, "status", "$.project.conditional_draft", CONDITIONAL_STATUSES, errors)
    maximum_work_options = MAXIMUM_WORK_V13 if schema_version == "1.3" else MAXIMUM_WORK_LEGACY
    maximum_work = require_enum(
        conditional, "maximum_work", "$.project.conditional_draft", maximum_work_options, errors,
    )
    blocked_outputs = string_set(require_list(conditional, "blocked_outputs", "$.project.conditional_draft", errors), "$.project.conditional_draft.blocked_outputs", errors)
    string_set(require_list(conditional, "blocker_ids", "$.project.conditional_draft", errors), "$.project.conditional_draft.blocker_ids", errors)

    envelope, scope_status, scope_source_ids = validate_top_scope(root.get("scope"), "$.scope", errors)
    if envelope["marketplaces"] != ({marketplace} if marketplace else set()):
        errors.append("$.scope.marketplaces: must exactly match project marketplace")
    if envelope["locales"] != ({locale} if locale else set()):
        errors.append("$.scope.locales: must exactly match project locale")

    ops = _domain_ops()
    ops["MAXIMUM_WORK"] = maximum_work_options
    foundation = validate_foundation(
        root, schema_version=schema_version, marketplace=marketplace, locale=locale,
        target_type=target_type, identity_status=identity_status,
        verified_child=verified_child, conclusion=conclusion,
        focal_source_ids=focal_source_ids,
        scope_source_ids=scope_source_ids, scope_status=scope_status,
        envelope=envelope, ops=ops,
    )
    errors.extend(foundation.errors)
    warnings.extend(foundation.warnings)
    source_map = foundation.source_map
    source_scopes = foundation.source_scopes
    limits = foundation.limits
    alt_max = foundation.alt_max
    available_module_types = foundation.available_module_types
    content_eligibility = foundation.content_eligibility
    facts_raw = foundation.facts_raw
    fact_map = foundation.fact_map
    fact_scopes = foundation.fact_scopes
    claims_raw = foundation.claims_raw
    claim_map = foundation.claim_map
    claim_scopes = foundation.claim_scopes

    content = validate_content(
        root, schema_version=schema_version, marketplace=marketplace, locale=locale,
        target_type=target_type, identity_status=identity_status,
        verified_child=verified_child, mode=mode, conclusion=conclusion,
        write_scope=write_scope, scope_status=scope_status,
        conditional_status=conditional_status,
        maximum_work=maximum_work, blocked_outputs=blocked_outputs,
        envelope=envelope, source_map=source_map, fact_map=fact_map,
        fact_scopes=fact_scopes, claim_map=claim_map, claim_scopes=claim_scopes,
        limits=limits, alt_max=alt_max, available_module_types=available_module_types,
        content_eligibility=content_eligibility, ops=ops,
    )
    errors.extend(content.errors)
    warnings.extend(content.warnings)
    decision_map = content.decision_map
    decision_status = content.decision_status
    competitor_map = content.competitor_map
    positioning = content.positioning
    conflicts = content.conflicts
    variants_raw = content.variants_raw
    variant_rows = content.variant_rows
    child_asins = content.child_asins
    content_ids = content.content_ids
    unresolved_target = content.unresolved_target
    modules_raw = content.modules_raw
    module_map = content.module_map
    module_scopes = content.module_scopes
    assets_raw = content.assets_raw
    asset_map = content.asset_map

    governance = validate_governance(
        root, schema_version=schema_version, project=project, mode=mode,
        conclusion=conclusion, marketplace=marketplace, locale=locale,
        identity_status=identity_status,
        write_scope=write_scope, snapshot_date=snapshot_date,
        scope_status=scope_status, envelope=envelope, source_map=source_map,
        source_scopes=source_scopes, fact_map=fact_map, fact_scopes=fact_scopes,
        claim_map=claim_map, claim_scopes=claim_scopes, conflicts=conflicts,
        module_map=module_map, module_scopes=module_scopes, asset_map=asset_map,
        child_asins=child_asins, content_ids=content_ids, variant_rows=variant_rows,
        source_path=source_path, ops=ops,
    )
    errors.extend(governance.errors)
    warnings.extend(governance.warnings)
    parent_bundle_verified = governance.parent_bundle_verified
    v12_counts = governance.version_counts
    gate_map = governance.gate_map
    experiments = governance.experiments

    if not facts_raw:
        warnings.append("No facts recorded; only a gap report can be supported.")
    if mode in {"plan", "rebuild", "preflight_qa", "publish_support"} and not modules_raw:
        warnings.append("No modules recorded for a planning/build mode.")
    if conclusion == "PASS" and warnings:
        warnings.append("Review warnings before treating the PASS package as shareable.")
    counts = {
        "sources": len(source_map), "facts": len(fact_map), "claims": len(claim_map),
        "variants": len(variants_raw), "modules": len(module_map), "assets": len(asset_map),
        "gates": len(gate_map), "experiments": len(experiments),
    }
    counts.update(v12_counts)
    result_level = derive_result_level(
        schema_version=schema_version,
        has_errors=bool(errors),
        mode=mode,
        conclusion=conclusion,
        component_result=v12_counts.get("component_result", "LOCAL_CONTRACT_PASS"),
    )
    return {
        "ok": not errors,
        "template_only": False,
        "errors": sorted(dict.fromkeys(errors)),
        "warnings": sorted(dict.fromkeys(warnings)),
        "counts": counts,
        "native_coverage_assessed": schema_version == "1.2",
        "atom_coverage_assessed": schema_version == "1.3",
        "structural_valid": report_structure_valid(root, errors),
        "parent_bundle_verified": parent_bundle_verified,
        "project_conclusion": conclusion or "NO_VALID_CONCLUSION",
        "result_level": result_level,
        "page_pass_implied": False,
        "publication_authorized_by_component": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to an A+ project bundle JSON file")
    args = parser.parse_args()
    path = args.bundle.expanduser().resolve()
    payload, io_issue = read_json_document(path)
    if io_issue:
        print(json.dumps({"ok": False, "errors": [io_issue]}, ensure_ascii=False, indent=2))
        return 2
    result = validate_bundle(payload, source_path=path)
    result["bundle"] = str(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return validator_exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
