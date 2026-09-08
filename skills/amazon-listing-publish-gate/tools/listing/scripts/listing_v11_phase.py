#!/usr/bin/env python3
"""Shared immutable phase result, constants, and pure validation primitives."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class PhaseDelta:
    """One domain's ordered, side-effect-free contribution to the facade."""

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    counts: tuple[tuple[str, int], ...] = ()
    gates: tuple[tuple[str, str], ...] = ()

    @classmethod
    def capture(
        cls,
        errors: list[str],
        warnings: list[str],
        counts: dict[str, int],
        gates: dict[str, str],
    ) -> "PhaseDelta":
        return cls(tuple(errors), tuple(warnings), tuple(counts.items()), tuple(gates.items()))


SCHEMA_VERSION = "1.1"
ROOT_KEYS = {
    "schema_version", "project", "execution_boundary", "scope",
    "catalog_context", "rule_snapshots", "field_resolutions", "sources",
    "facts", "claims", "conflicts", "variant_topology", "method_registry",
    "discovery", "market_research", "ptd_field_inventory", "decision_map",
    "decision_denominator_snapshot", "canonical_assertions",
    "decision_answer_units", "surface_assignments", "field_candidates",
    "semantic_consistency_matrix", "category_adapter", "experiment_registry",
    "gate_reviews", "enriched_content_handoff", "publish_authorization",
    "baseline", "change_set", "rollback", "live_readback", "record_templates",
}
EXECUTION_BOUNDARIES = {
    "read_only", "local_candidate", "authorized_submission", "rollback_only"
}
MODES = {"audit", "plan", "rebuild", "preflight_qa", "publish_support"}
CONCLUSIONS = {
    "NO_VALID_CONCLUSION", "CONDITIONAL_PASS", "PASS", "BLOCKED", "LIVE_PASS"
}
TARGET_STAGES = [
    "AUTHORITY", "IDENTITY_FROZEN", "RULES_READY", "EVIDENCE_READY",
    "TRUTH_READY", "DISCOVERY_CLOSED", "DECISION_FROZEN", "PTD_CLOSED",
    "SURFACES_READY", "CANDIDATE_READY", "HANDOFF_READY", "PACKAGE_PASS",
    "AUTHORIZED_SUBMISSION", "BACKEND_ACCEPTED", "LIVE_MATCH",
]
SURFACES = {
    "core_copy", "catalog_attributes", "size_chart", "media",
    "backend_search_terms", "enriched_content", "product_details",
}
DATA_PLANES = {
    "catalog_contribution", "seller_listing", "relationship",
    "enriched_content", "external_tool",
}
LEGAL_P0_CARRIERS = {"NATIVE_VISIBLE", "STRUCTURED_VISIBLE"}
DISALLOWED_P0_CARRIERS = {
    "IMAGE_TEXT", "ALT_METADATA", "VIDEO_ONLY", "INTERACTIVE_ONLY",
    "BACKEND_HIDDEN", "COMMUNITY_QA", "PROOF_ONLY",
}
EVIDENCE_LEVELS = {"E0", "E1", "E2", "E3", "E4"}
SOURCE_STATUSES = {"USABLE", "PARTIAL", "STALE", "BLOCKED", "MISSING"}
WEAK_ONLY_SOURCE_TYPES = {
    "owner_statement", "community_voc", "customer_review", "lingxing_mirror"
}
DISCOVERY_CLOSURES = {
    "NOT_STARTED", "IN_PROGRESS", "PASS", "CONDITIONAL", "BLOCKED",
    "NOT_REQUIRED_WITH_REASON",
}
RESPONSE_CLASSES = {
    "FACT_LEAD", "STRATEGIC_CHOICE", "HYPOTHESIS", "UNKNOWN_SKIP"
}
IMPACT_DIMENSIONS = {
    "AUDIENCE", "SCENARIO", "PROBLEM", "PROMISE", "BOUNDARY", "VARIANT",
    "EVIDENCE", "FIELD_ALLOCATION", "STRATEGIC_SELECTION",
}
METHOD_CLASSES = {
    "OFFICIAL_CURRENT", "ACCOUNT_OBSERVED", "TARGET_PRODUCT_EVIDENCE",
    "MULTI_SOURCE_HEURISTIC", "COMMUNITY_HYPOTHESIS", "PROHIBITED_REJECTED",
}
HANDOFF_STATUSES = {
    "NOT_APPLICABLE", "DRAFT", "FROZEN", "RESULT_RECEIVED",
    "RECONCILIATION_REQUIRED", "SUPERSEDED",
}
HANDOFF_MAXIMUM_OUTPUTS = {
    "strategy_dependency_only", "candidate_package", "preflight_package", "publish_support_package",
}
HANDOFF_KEYS = {
    "contract_version", "snapshot_id", "parent_project_id",
    "parent_bundle_sha256", "status", "maximum_output", "marketplace", "locale",
    "product_type", "application_scope", "variant_row_ids", "fact_ids",
    "claim_ids", "blocked_claim_ids", "conflict_ids", "source_ids",
    "requested_content_types", "decision_requirements", "capability_snapshot_ids",
    "discovery_closure_hash", "ptd_inventory_hash", "decision_denominator_hash",
    "canonical_assertion_ids", "requirement_atoms", "prohibited_actions",
    "predecessor_snapshot_id", "semantic_revision", "refreeze_reason",
    "lineage_registry", "created_at", "owner", "checksum",
}
DISCOVERY_KEYS = {
    "status", "evidence_pass", "interview_rounds", "responses",
    "distillations", "evidence_actions", "stage_gates", "closure",
}
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
DISCOVERY_RESPONSE_KEYS = {
    "id", "classification", "status", "answer", "p0_impact", "source_ids", "owner",
}
DISCOVERY_QUESTION_KEYS = {"id", "question", "impact_dimensions", "response_id"}
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
METHOD_KEYS = {
    "id", "name", "classification", "gate_eligible", "source_ids",
    "status", "observed_at", "refresh_trigger",
}
MARKET_RESEARCH_KEYS = {
    "status", "source_ids", "voc_observations", "competitor_observations",
    "conclusions", "reason", "owner",
}
MARKET_RESEARCH_ROW_KEYS = {"id", "statement", "source_ids"}
DECISION_MAP_KEYS = {"status", "requirements"}
DECISION_REQUIREMENT_BASE_KEYS = {
    "id", "buyer_question", "priority", "application_scope", "fact_ids",
    "claim_ids", "early_disclosure_required", "assigned_surface", "status", "owner",
}
DECISION_REQUIREMENT_DELEGATED_KEYS = {
    *DECISION_REQUIREMENT_BASE_KEYS, "native_answer_required", "upstream_primary_carrier_ref",
}
PTD_KEYS = {
    "status", "product_type", "rule_snapshot_ids", "evidence_source_ids",
    "declared_field_count", "expected_fields", "checksum",
}
EXPECTED_FIELD_KEYS = {
    "id", "field_resolution_id", "requirement_status", "trigger_status",
    "p0_relevant", "closure_status", "evidence_source_ids", "reason",
}
CATEGORY_ADAPTER_KEYS = {
    "name", "version", "status", "question_prompts", "evidence_probes",
    "return_risks", "qa_checks",
}
GATE_REVIEW_KEYS = {
    "id", "gate", "status", "reviewer", "reviewed_at",
    "evidence_source_ids", "blocker_ids", "notes",
}
EXPERIMENT_KEYS = {
    "id", "hypothesis", "status", "application_scope", "metric",
    "baseline_ref", "candidate_ref", "started_at", "ended_at", "owner", "decision",
}
FORBIDDEN_METRIC_KEYS = {
    "minimum_total_words", "min_total_words", "native_text_min_chars",
    "min_total_chars", "keyword_density", "cosmo_score", "alexa_coverage",
    "cdq_weight", "fixed_wait_days", "semantic_score", "attribute_completeness_target",
}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def _err(errors: list[str], code: str, path: str, message: str) -> None:
    errors.append(f"[{code}] {path}: {message}")


def _warn(warnings: list[str], code: str, path: str, message: str) -> None:
    warnings.append(f"[{code}] {path}: {message}")


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(_nonempty(item) for item in value)


def _unique_strings(value: Any) -> bool:
    return _string_list(value) and len(value) == len(set(value))


def _isoish(value: Any) -> bool:
    if not _nonempty(value):
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    try:
        encoded = payload.encode("utf-8")
    except UnicodeEncodeError:
        # Unicode validation rejects lone surrogates, but hashing must stay
        # total so malformed input returns a deterministic FAIL, not a crash.
        encoded = payload.encode("utf-8", errors="backslashreplace")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _hash_without(value: dict[str, Any], *keys: str) -> str:
    normalized = copy.deepcopy(value)
    for key in keys:
        normalized[key] = ""
    return canonical_sha256(normalized)

def _find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in FORBIDDEN_METRIC_KEYS:
                hits.append(child)
            hits.extend(_find_forbidden_keys(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_find_forbidden_keys(item, f"{path}[{index}]"))
    return hits


def _obj_list(value: Any, path: str, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _err(errors, "L11-STRUCT-001", path, "must be an array")
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            rows.append(item)
        else:
            _err(errors, "L11-STRUCT-002", f"{path}[{index}]", "must be an object")
    return rows


def _index(rows: Iterable[dict[str, Any]], path: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        item_id = row.get("id")
        if not _nonempty(item_id) or not ID_RE.fullmatch(str(item_id)):
            _err(errors, "L11-ID-001", f"{path}[{index}].id", "must be a stable ID")
        elif item_id in result:
            _err(errors, "L11-ID-002", f"{path}[{index}].id", f"duplicate ID {item_id}")
        else:
            result[str(item_id)] = row
    return result


def _refs(value: Any, allowed: set[str], path: str, errors: list[str], *, nonempty: bool = False) -> None:
    if not _unique_strings(value):
        _err(errors, "L11-REF-001", path, "must be a unique string array")
        return
    if nonempty and not value:
        _err(errors, "L11-REF-002", path, "must not be empty")
    unknown = set(value) - allowed
    if unknown:
        _err(errors, "L11-REF-003", path, f"unknown references: {sorted(unknown)}")


def _scope_sets(scope: Any) -> dict[str, set[str]]:
    if not isinstance(scope, dict):
        return {}
    return {
        key: set(scope.get(key, [])) if _string_list(scope.get(key, [])) else set()
        for key in ("parent_asins", "child_asins", "packs", "colors", "sizes")
    }


def _validate_app_scope(value: Any, path: str, root_scope: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(value, dict):
        _err(errors, "L11-SCOPE-020", path, "must be an object")
        return
    expected = {"parent_asins", "child_asins", "packs", "colors", "sizes"}
    if set(value) != expected:
        _err(errors, "L11-SCOPE-021", path, f"must contain exactly {sorted(expected)}")
        return
    root = {
        "parent_asins": set(root_scope.get("parent_asins", [])),
        "child_asins": set(root_scope.get("intended_child_asins", [])),
        "packs": set(root_scope.get("packs", [])),
        "colors": set(root_scope.get("colors", [])),
        "sizes": set(root_scope.get("sizes", [])),
    }
    for key in expected:
        if not _unique_strings(value.get(key, [])):
            _err(errors, "L11-SCOPE-022", f"{path}.{key}", "must be a unique string array")
        elif not set(value[key]).issubset(root[key]):
            _err(errors, "L11-SCOPE-023", f"{path}.{key}", "expands frozen scope")


def _scope_covers_variant(scope: Any, row: dict[str, Any]) -> bool:
    values = _scope_sets(scope)
    mapping = {
        "parent_asins": row.get("parent_asin"),
        "child_asins": row.get("child_asin"),
        "packs": row.get("pack"),
        "colors": row.get("color"),
        "sizes": row.get("size"),
    }
    for key, actual in mapping.items():
        allowed = values.get(key, set())
        if allowed and actual not in allowed:
            return False
    return True


def _scope_subset(child: Any, parent: Any) -> bool:
    child_sets = _scope_sets(child)
    parent_sets = _scope_sets(parent)
    if not child_sets or not parent_sets:
        return False
    for key, child_values in child_sets.items():
        if child_values and not child_values.issubset(parent_sets.get(key, set())):
            return False
    return True


def _normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _is_fake_subtitle(value: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")
    return normalized in {"subtitle", "item_subtitle", "product_subtitle"} or normalized.endswith("_subtitle")
