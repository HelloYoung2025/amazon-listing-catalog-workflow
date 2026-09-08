#!/usr/bin/env python3
"""Pure A+ v1.3 domain rules shared by the local validator and tests.

The functions in this module do not read files, import the Listing validator,
mutate their inputs, or make network calls. They return deterministic values
and issue codes; the CLI validator owns JSON parsing and presentation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

from aplus_v13_lineage import (
    canonical_handoff_snapshot_id as _lineage_snapshot_id,
    validate_lineage_registry,
)


MIRROR_SOURCE_TYPES = {
    "LINGXING_OPERATIONAL_MIRROR",
    "EXTERNAL_OPERATIONAL_MIRROR",
}
MIRROR_FORBIDDEN_SOLE_PROOF_CLASSES = {
    "PTD_SCHEMA",
    "PHYSICAL_PRODUCT",
    "PERFORMANCE",
    "FRONTEND_LIVE_STATE",
}
CATEGORY_ADAPTER_IDS = {
    "generic",
    "apparel/fit",
    "connected-device",
    "home/kitchen",
    "regulated/beauty",
}
CATEGORY_ADAPTER_KEYS = {
    "id",
    "status",
    "investigation_prompts",
    "evidence_probes",
    "return_risks",
    "qa_checks",
    "owner",
}
DELTA_LINEAGE_KEYS = {
    "snapshot_id",
    "parent_bundle_sha256",
    "discovery_closure_hash",
    "ptd_inventory_hash",
    "decision_denominator_hash",
    "handoff_checksum",
}
HANDOFF_V11_KEYS = {
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
HANDOFF_SNAPSHOT_RE = re.compile(r"^HO-[0-9a-f]{20}$")


def _text_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item.strip() for item in value if isinstance(item, str) and item.strip()}


def _scope_values(scope: Mapping[str, Any], key: str) -> set[str]:
    value = scope.get(key, set())
    if isinstance(value, set):
        return {str(item) for item in value if str(item)}
    if isinstance(value, list):
        return {str(item) for item in value if str(item)}
    return set()


def scope_covers_variant(
    scope: Mapping[str, Any],
    variant: Mapping[str, Any],
    marketplace: str,
    locale: str,
) -> bool:
    """Return whether a normalized source/assertion scope covers one real row."""
    targets = {
        "marketplaces": marketplace,
        "locales": locale,
        "parent_asins": str(variant.get("parent_asin", "")),
        "child_asins": str(variant.get("child_asin", "")),
        "packs": str(variant.get("pack", "")),
        "colors": str(variant.get("color", "")),
        "sizes_or_capacities": str(variant.get("size_or_capacity", "")),
    }
    for key, target in targets.items():
        allowed = _scope_values(scope, key)
        if allowed and target not in allowed:
            return False
    return bool(_scope_values(scope, "child_asins"))


def validate_evidence_pass(
    evidence_pass: Mapping[str, Any],
    source_map: Mapping[str, Mapping[str, Any]],
    source_scopes: Mapping[str, Mapping[str, Any]],
    atom_map: Mapping[str, Mapping[str, Any]],
    variant_map: Mapping[str, Mapping[str, Any]],
    marketplace: str,
    locale: str,
) -> tuple[bool, tuple[str, ...]]:
    """Validate the standalone pre-interview evidence pass."""
    issues: list[str] = []
    if evidence_pass.get("status") != "COMPLETE":
        issues.append("[A13-EVIDENCE-001] $.discovery.evidence_pass.status: standalone requires COMPLETE")
    source_ids = _text_set(evidence_pass.get("source_ids"))
    observations = _text_set(evidence_pass.get("observations"))
    if not source_ids:
        issues.append("[A13-EVIDENCE-002] $.discovery.evidence_pass.source_ids: at least one source required")
    if not observations:
        issues.append("[A13-EVIDENCE-003] $.discovery.evidence_pass.observations: at least one observation required")
    usable_ids: set[str] = set()
    for source_id in sorted(source_ids):
        source = source_map.get(source_id)
        if source is None:
            issues.append(f"[A13-EVIDENCE-004] $.discovery.evidence_pass.source_ids: unknown source {source_id!r}")
            continue
        if source.get("fetch_status") != "ok":
            issues.append(f"[A13-EVIDENCE-005] $.discovery.evidence_pass.source_ids: source {source_id!r} is not USABLE")
            continue
        usable_ids.add(source_id)
    for atom_id, atom in sorted(atom_map.items()):
        variant_id = str(atom.get("variant_row_id", ""))
        variant = variant_map.get(variant_id)
        if variant is None:
            continue
        if not any(
            scope_covers_variant(source_scopes.get(source_id, {}), variant, marketplace, locale)
            for source_id in usable_ids
        ):
            issues.append(
                f"[A13-EVIDENCE-006] $.discovery.evidence_pass.source_ids: no USABLE scoped source covers atom {atom_id!r}"
            )
    return not issues, tuple(sorted(issues))


def validate_distillation_coverage(
    question_rows: Mapping[str, Mapping[str, Any]],
    distillation_rows: Mapping[str, Mapping[str, Any]],
    known_fact_ids: Iterable[str],
    known_claim_ids: Iterable[str],
    known_action_ids: Iterable[str],
) -> tuple[bool, tuple[str, ...]]:
    """Validate that material answered questions were actually distilled."""
    issues: list[str] = []
    fact_ids = set(known_fact_ids)
    claim_ids = set(known_claim_ids)
    action_ids = set(known_action_ids)
    covered: dict[str, list[Mapping[str, Any]]] = {}
    for distillation_id, row in sorted(distillation_rows.items()):
        for question_id in _text_set(row.get("question_ids")):
            covered.setdefault(question_id, []).append(row)
        unknown_facts = _text_set(row.get("fact_ids")) - fact_ids
        unknown_claims = _text_set(row.get("claim_ids")) - claim_ids
        unknown_actions = _text_set(row.get("evidence_action_ids")) - action_ids
        if unknown_facts or unknown_claims or unknown_actions:
            issues.append(
                f"[A13-DISCOVERY-020] $.discovery.distillations[{distillation_id}]: unknown Fact/Claim/Evidence Action references"
            )
        if row.get("result_type") == "FACT_LEAD" and not (
            _text_set(row.get("fact_ids")) or _text_set(row.get("claim_ids"))
        ):
            issues.append(
                f"[A13-DISCOVERY-021] $.discovery.distillations[{distillation_id}]: FACT_LEAD requires a Fact or Claim reference"
            )
    for question_id, question in sorted(question_rows.items()):
        response_class = question.get("response_class")
        if response_class == "UNKNOWN_SKIP":
            continue
        matches = [row for row in covered.get(question_id, []) if row.get("result_type") == response_class]
        if not matches:
            issues.append(
                f"[A13-DISCOVERY-022] question {question_id!r}: answered question requires a matching distillation"
            )
    return not issues, tuple(sorted(issues))


def derive_discovery_closure(
    workflow_mode: str,
    evidence_pass_valid: bool,
    distillations_valid: bool,
    evidence_actions: Mapping[str, Mapping[str, Any]],
) -> str:
    """Derive closure; a caller-provided PASS never controls this value."""
    if workflow_mode == "embedded":
        return "NOT_REQUIRED_WITH_REASON"
    statuses = {str(row.get("status", "")) for row in evidence_actions.values()}
    if "OPEN" in statuses:
        return "IN_PROGRESS"
    if not evidence_pass_valid or not distillations_valid:
        return "BLOCKED"
    return "PASS"


def requirement_applies_to_variant(
    requirement_scope: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> bool:
    checks = (
        ("parent_asins", str(variant.get("parent_asin", ""))),
        ("child_asins", str(variant.get("child_asin", ""))),
        ("packs", str(variant.get("pack", ""))),
        ("colors", str(variant.get("color", ""))),
        ("sizes_or_capacities", str(variant.get("size_or_capacity", ""))),
    )
    return all(not _scope_values(requirement_scope, key) or value in _scope_values(requirement_scope, key) for key, value in checks)


def expected_decision_pairs(
    requirements: Mapping[str, Mapping[str, Any]],
    requirement_scopes: Mapping[str, Mapping[str, Any]],
    variants: Mapping[str, Mapping[str, Any]],
) -> frozenset[tuple[str, str]]:
    """Derive the exact P0/real-row denominator without a Cartesian product."""
    return frozenset(
        (requirement_id, variant_id)
        for requirement_id, requirement in requirements.items()
        if requirement.get("priority") == "P0" and requirement.get("status", "READY") == "READY"
        for variant_id, variant in variants.items()
        if requirement_applies_to_variant(requirement_scopes.get(requirement_id, {}), variant)
    )


def validate_category_adapter(adapter: Any, workflow_mode: str) -> tuple[bool, tuple[str, ...]]:
    """Validate the closed A+ investigation adapter, never Amazon PTD fields."""
    issues: list[str] = []
    if not isinstance(adapter, dict):
        return False, ("[A13-ADAPTER-001] $.category_adapter: required object",)
    keys = set(adapter)
    if keys != CATEGORY_ADAPTER_KEYS:
        issues.append(
            f"[A13-ADAPTER-002] $.category_adapter: exact keys required; missing={sorted(CATEGORY_ADAPTER_KEYS-keys)!r}, extra={sorted(keys-CATEGORY_ADAPTER_KEYS)!r}"
        )
    if adapter.get("id") not in CATEGORY_ADAPTER_IDS:
        issues.append("[A13-ADAPTER-003] $.category_adapter.id: unsupported adapter")
    expected_status = "SELECTED" if workflow_mode == "standalone" else "PARENT_BOUND"
    if adapter.get("status") != expected_status:
        issues.append(f"[A13-ADAPTER-004] $.category_adapter.status: expected {expected_status}")
    for key in ("investigation_prompts", "evidence_probes", "return_risks", "qa_checks"):
        value = adapter.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            issues.append(f"[A13-ADAPTER-005] $.category_adapter.{key}: required string array")
    if not isinstance(adapter.get("owner"), str) or not adapter.get("owner", "").strip():
        issues.append("[A13-ADAPTER-006] $.category_adapter.owner: required non-empty string")
    return not issues, tuple(sorted(issues))


def validate_delta_lineage(
    request_id: str,
    request: Mapping[str, Any],
    workflow_mode: str,
    handoff: Mapping[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    """Bind an open parent-evidence delta to the exact frozen handoff lineage."""
    issues: list[str] = []
    if request.get("status") != "OPEN":
        return True, ()
    if workflow_mode != "embedded":
        return False, (
            f"[A13-DELTA-030] $.delta_evidence_requests[{request_id}]: standalone evidence gaps belong in discovery.evidence_actions",
        )
    if request.get("gap_type") != "PARENT_EVIDENCE":
        issues.append(
            f"[A13-DELTA-031] $.delta_evidence_requests[{request_id}].gap_type: embedded OPEN delta must be PARENT_EVIDENCE"
        )
    lineage = request.get("handoff_lineage")
    if not isinstance(lineage, dict) or set(lineage) != DELTA_LINEAGE_KEYS:
        issues.append(
            f"[A13-DELTA-032] $.delta_evidence_requests[{request_id}].handoff_lineage: exact lineage keys required"
        )
        return False, tuple(sorted(issues))
    expected = {
        "snapshot_id": handoff.get("snapshot_id", ""),
        "parent_bundle_sha256": handoff.get("parent_bundle_sha256", ""),
        "discovery_closure_hash": handoff.get("discovery_closure_hash", ""),
        "ptd_inventory_hash": handoff.get("ptd_inventory_hash", ""),
        "decision_denominator_hash": handoff.get("decision_denominator_hash", ""),
        "handoff_checksum": handoff.get("checksum", ""),
    }
    if lineage != expected:
        issues.append(
            f"[A13-DELTA-033] $.delta_evidence_requests[{request_id}].handoff_lineage: stale or mismatched frozen lineage"
        )
    return not issues, tuple(sorted(issues))


def canonical_handoff_snapshot_id(handoff: Mapping[str, Any]) -> str:
    """Content-address immutable handoff semantics without lifecycle fields."""
    return _lineage_snapshot_id(handoff)


def validate_handoff_shape(
    handoff: Any,
    workflow_mode: str,
) -> tuple[bool, tuple[str, ...]]:
    """Validate the closed v1.1 handoff and semantic-refreeze lineage."""
    issues: list[str] = []
    if not isinstance(handoff, dict):
        return False, ("[A13-HANDOFF-036] $.enriched_content_handoff: required object",)
    keys = set(handoff)
    if keys != HANDOFF_V11_KEYS:
        issues.append(
            "[A13-HANDOFF-036] $.enriched_content_handoff: exact v1.1 keys required; "
            f"missing={sorted(HANDOFF_V11_KEYS-keys)!r}, extra={sorted(keys-HANDOFF_V11_KEYS)!r}"
        )
    for lineage_code, lineage_message in validate_lineage_registry(handoff, HANDOFF_V11_KEYS):
        issues.append(
            f"[A13-HANDOFF-044] $.enriched_content_handoff.lineage_registry[{lineage_code}]: {lineage_message}"
        )
    revision = handoff.get("semantic_revision")
    predecessor = handoff.get("predecessor_snapshot_id")
    reason = handoff.get("refreeze_reason")
    if not isinstance(predecessor, str) or not isinstance(reason, str):
        issues.append(
            "[A13-HANDOFF-037] $.enriched_content_handoff: predecessor_snapshot_id and refreeze_reason must be strings"
        )
    if workflow_mode == "embedded":
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            issues.append(
                "[A13-HANDOFF-038] $.enriched_content_handoff.semantic_revision: embedded handoff requires a positive integer"
            )
        elif revision == 1 and (predecessor or reason):
            issues.append(
                "[A13-HANDOFF-039] $.enriched_content_handoff: initial semantic snapshot cannot claim predecessor/refreeze"
            )
        elif revision > 1 and (
            not isinstance(predecessor, str)
            or not HANDOFF_SNAPSHOT_RE.fullmatch(predecessor)
            or predecessor == handoff.get("snapshot_id")
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            issues.append(
                "[A13-HANDOFF-040] $.enriched_content_handoff: semantic refreeze requires an immutable predecessor and reason"
            )
        snapshot_id = handoff.get("snapshot_id")
        if not isinstance(snapshot_id, str) or not HANDOFF_SNAPSHOT_RE.fullmatch(snapshot_id):
            issues.append(
                "[A13-HANDOFF-041] $.enriched_content_handoff.snapshot_id: expected content-addressed HO-<20 hex>"
            )
        elif snapshot_id != canonical_handoff_snapshot_id(handoff):
            issues.append(
                "[A13-HANDOFF-042] $.enriched_content_handoff.snapshot_id: semantic snapshot hash mismatch"
            )
    elif revision != 0 or predecessor or reason:
        issues.append(
            "[A13-HANDOFF-043] $.enriched_content_handoff: standalone NOT_APPLICABLE handoff requires semantic_revision=0 and empty lineage"
        )
    return not issues, tuple(sorted(issues))


def derive_coverage_result(
    closure_status: str,
    denominator_status: str,
    required_atoms: Iterable[str],
    passed_atoms: Iterable[str],
    open_delta_atoms: Iterable[str],
    blocked_local_atoms: Iterable[str],
    open_evidence_action: bool,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Derive child state without converting local work gaps into parent deltas."""
    required = set(required_atoms)
    passed = set(passed_atoms)
    gap_atoms = required - passed
    delta_atoms = set(open_delta_atoms)
    stale_delta_atoms = delta_atoms - gap_atoms
    covered_by_delta = gap_atoms & delta_atoms
    uncovered = gap_atoms - covered_by_delta
    if closure_status == "BLOCKED" or set(blocked_local_atoms) & gap_atoms:
        status = "BLOCKED"
    elif gap_atoms and not uncovered and not stale_delta_atoms:
        status = "DELTA_REQUIRED"
    elif gap_atoms:
        status = "IN_PROGRESS"
    elif stale_delta_atoms:
        status = "BLOCKED"
    elif open_evidence_action or closure_status == "IN_PROGRESS":
        status = "IN_PROGRESS"
    elif closure_status == "CONDITIONAL":
        status = "CONDITIONAL"
    elif closure_status in {"PASS", "NOT_REQUIRED_WITH_REASON"} and denominator_status == "FROZEN" and required:
        status = "COMPONENT_PASS"
    else:
        status = "NOT_EVALUATED"
    return status, tuple(sorted(gap_atoms)), tuple(sorted(stale_delta_atoms))


def structural_valid_v13(
    root: Any,
    required_keys: Iterable[str],
    allowed_extra_keys: Iterable[str],
    errors: Iterable[str],
) -> bool:
    """Separate JSON/schema validity from an otherwise renderable business block."""
    if not isinstance(root, dict) or root.get("schema_version") != "1.3":
        return False
    required = set(required_keys)
    allowed = required | set(allowed_extra_keys)
    if required - set(root) or set(root) - allowed:
        return False
    if root.get("project", {}).get("status") == "SCAFFOLD":
        return False
    mappings = {
        "project", "scope", "workflow_context", "enriched_content_handoff",
        "discovery", "decision_denominator_snapshot", "coverage_summary",
        "component_result", "category_adapter",
    }
    arrays = {
        "sources", "facts", "claims", "variants", "modules", "assets",
        "canonical_assertions", "decision_answer_units", "carriers",
        "delta_evidence_requests", "gates",
    }
    if any(not isinstance(root.get(key), dict) for key in mappings):
        return False
    if any(not isinstance(root.get(key), list) for key in arrays):
        return False
    structural_markers = (
        ": required object",
        ": required array",
        ": required string",
        ": required boolean",
        ": unsupported value",
        "missing top-level keys",
        "unknown top-level keys",
        "has unknown top-level keys",
        "duplicate id",
        "[A13-ADAPTER-002]",
        "[A13-ADAPTER-003]",
        "[A13-ADAPTER-004]",
        "[A13-ADAPTER-005]",
        "[A13-ADAPTER-006]",
        "[A13-HANDOFF-036]",
        "[A13-HANDOFF-037]",
    )
    return not any(any(marker in error for marker in structural_markers) for error in errors)
