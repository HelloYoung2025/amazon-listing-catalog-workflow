#!/usr/bin/env python3
"""Validate Listing 1.1 + embedded A+ 1.3 pairs or one locale group.

This is the suite's only cross-bundle coordinator.  The two component
validators remain independent: this module executes their CLIs, consumes their
JSON results, and validates the immutable frozen handoff plus whole-page atomic
coverage.  ``--group-manifest`` repeats that real pair validation for every
locale before comparing frozen semantic truth.  It never submits content and
never grants publication authority.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from listing_v11_field_contract import p0_field_contract_allows
from listing_coordination_receipt import (
    build_coordination_receipt,
    coordination_chain_id,
    delta_fingerprint,
    full_input_hash,
    validate_coordination_receipt,
)
from listing_coordination_ledger import (
    LedgerError,
    append_receipt,
    file_sha256,
    load_receipt_ledger,
)
from listing_v11_lineage import (
    canonical_handoff_hash as _lineage_handoff_hash,
    canonical_handoff_snapshot_id as _lineage_snapshot_id,
    validate_lineage_registry,
)
from listing_locale_group import (
    GROUP_CONTRACT_VERSION,
    validate_group_manifest,
    validate_listing_locale_group,
)


PARENT_VERSION = "1.1"
APLUS_VERSION = "1.3"
HANDOFF_VERSION = "1.1"
LIFECYCLE_FIELDS = {"status", "parent_bundle_sha256", "checksum"}
ACTIVE_HANDOFF_STATES = {
    "FROZEN", "RESULT_RECEIVED", "RECONCILIATION_REQUIRED", "SUPERSEDED",
}
PARENT_FREEZE_FIELDS = (
    "schema_version", "execution_boundary", "scope", "catalog_context", "rule_snapshots",
    "field_resolutions", "sources", "facts", "claims", "conflicts",
    "variant_topology", "method_registry", "discovery", "market_research",
    "ptd_field_inventory", "decision_map", "decision_denominator_snapshot",
    "canonical_assertions", "decision_answer_units", "surface_assignments",
    "field_candidates", "semantic_consistency_matrix", "category_adapter",
)
FINAL_APLUS_CONTENT = {"FINAL_CANDIDATE", "APPROVED", "PUBLISHED"}
LEGAL_PARENT_CARRIERS = {"NATIVE_VISIBLE", "STRUCTURED_VISIBLE"}
TERMINAL_READBACK = {"LIVE_MATCH", "LIVE_MISMATCH"}
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

HERE = Path(__file__).resolve().parent
DEFAULT_PARENT_VALIDATOR = HERE / "validate_listing_bundle.py"
DEFAULT_APLUS_VALIDATOR = (
    HERE.parent.parent / "aplus" / "scripts" / "validate_bundle.py"
)


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_block(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    normalized = copy.deepcopy(value)
    if "checksum" in normalized:
        normalized["checksum"] = ""
    elif "hash" in normalized:
        normalized["hash"] = ""
    return canonical_sha256(normalized)


def canonical_handoff_hash(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return ""
    return _lineage_handoff_hash(handoff)


def canonical_handoff_snapshot_id(handoff: Any) -> str:
    """Return the parent's content-addressed ID for one immutable handoff.

    Lifecycle acknowledgements are deliberately normalized so FROZEN,
    RESULT_RECEIVED, RECONCILIATION_REQUIRED and SUPERSEDED all keep the same
    snapshot identity.  Any semantic field (including authority or explicit
    refreeze lineage) changes the identity.
    """
    if not isinstance(handoff, dict):
        return ""
    return _lineage_snapshot_id(handoff)


def canonical_parent_hash(bundle: Any) -> str:
    if not isinstance(bundle, dict):
        return ""
    normalized = {
        key: copy.deepcopy(bundle.get(key)) for key in PARENT_FREEZE_FIELDS
        if key in bundle
    }
    handoff = copy.deepcopy(bundle.get("enriched_content_handoff"))
    if isinstance(handoff, dict):
        if handoff.get("status") in ACTIVE_HANDOFF_STATES:
            handoff["status"] = "FROZEN"
        handoff["parent_bundle_sha256"] = ""
        handoff["checksum"] = ""
        normalized["enriched_content_handoff"] = handoff
    return canonical_sha256(normalized)


def immutable_handoff(handoff: Any) -> Any:
    if not isinstance(handoff, dict):
        return handoff
    return {key: copy.deepcopy(value) for key, value in handoff.items() if key not in LIFECYCLE_FIELDS}


def _objects(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _index(value: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _objects(value):
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id:
            result[row_id] = row
    return result


def _ids(value: Any) -> set[str]:
    return {item for item in value if isinstance(item, str) and item} if isinstance(value, list) else set()


def _atom_identity(atom: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return tuple(str(atom.get(key, "")) for key in (
        "id", "requirement_id", "marketplace", "locale", "variant_row_id",
    ))


def _scope_values(scope: Any, key: str) -> set[str]:
    if not isinstance(scope, dict):
        return set()
    aliases = {
        "sizes": ("sizes", "sizes_or_capacities"),
        "child_asins": ("child_asins", "intended_child_asins"),
        "parent_asins": ("parent_asins", "parent_asin"),
        "marketplaces": ("marketplaces", "marketplace"),
        "locales": ("locales", "locale"),
    }
    for candidate in aliases.get(key, (key,)):
        value = scope.get(candidate)
        if isinstance(value, list):
            return {str(item) for item in value if str(item)}
        if isinstance(value, str) and value:
            return {value}
    return set()


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _scope_covers_variant(scope: Any, variant: dict[str, Any]) -> bool:
    if not isinstance(scope, dict):
        return False
    for scope_key, variant_key in (
        ("parent_asins", "parent_asin"), ("child_asins", "child_asin"),
        ("packs", "pack"), ("colors", "color"), ("sizes", "size"),
    ):
        value = str(variant.get(variant_key, ""))
        if value and value not in _scope_values(scope, scope_key):
            return False
    return True


def _assertion_scope_projection(
    scope: Any, marketplace: str, locale: str, *, allow_context_fallback: bool,
) -> dict[str, Any]:
    mapping = scope if isinstance(scope, dict) else {}
    other_variants: dict[str, tuple[str, ...]] = {}
    raw_other = mapping.get("other_variants")
    if isinstance(raw_other, dict):
        for key, value in raw_other.items():
            values = value if isinstance(value, list) else [value]
            normalized_values = tuple(sorted({
                str(item).strip() for item in values
                if str(item).strip().casefold() not in {"", "n/a", "not applicable", "none"}
            }))
            if normalized_values:
                other_variants[str(key)] = normalized_values
    return {
        "marketplaces": _scope_values(scope, "marketplaces") or (
            {marketplace} if allow_context_fallback and marketplace else set()
        ),
        "locales": _scope_values(scope, "locales") or (
            {locale} if allow_context_fallback and locale else set()
        ),
        "parent_asins": _scope_values(scope, "parent_asins"),
        "child_asins": _scope_values(scope, "child_asins"),
        "packs": _scope_values(scope, "packs"),
        "colors": _scope_values(scope, "colors"),
        "sizes": _scope_values(scope, "sizes"),
        "other_variants": other_variants,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _parent_answer_bindings(
    parent: dict[str, Any],
    parent_atoms: dict[str, dict[str, Any]],
    parent_variants: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Resolve real parent answers all the way to visible fields and assignments."""
    candidates = _index(parent.get("field_candidates"))
    fields = _index(parent.get("field_resolutions"))
    assignments = _objects(parent.get("surface_assignments"))
    assertions = _index(parent.get("canonical_assertions"))
    result: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: dict[str, int] = {}
    for unit in _objects(parent.get("decision_answer_units")):
        atom_id = str(unit.get("atom_id", ""))
        if unit.get("status") != "PASS" or atom_id not in parent_atoms:
            continue
        raw_pass_counts[atom_id] = raw_pass_counts.get(atom_id, 0) + 1
        atom = parent_atoms[atom_id]
        variant_id = str(atom.get("variant_row_id", ""))
        variant = parent_variants.get(variant_id)
        candidate = candidates.get(str(unit.get("field_candidate_id", "")))
        if (
            variant is None
            or candidate is None
            or str(unit.get("requirement_id", "")) != str(atom.get("requirement_id", ""))
            or str(unit.get("variant_row_id", "")) != variant_id
            or candidate.get("content_status") != "FINAL"
            or candidate.get("qa_status") != "PASS"
            or not _scope_covers_variant(candidate.get("application_scope"), variant)
        ):
            continue
        field = fields.get(str(candidate.get("field_resolution_id", "")))
        if (
            field is None
            or field.get("status") != "RESOLVED"
            or field.get("exists") is not True
            or field.get("editable") is not True
            or field.get("applicable") is not True
            or field.get("visibility") != "BUYER_VISIBLE"
            or not _scope_covers_variant(field.get("application_scope"), variant)
        ):
            continue
        answer_text = _normalized_text(unit.get("answer_text"))
        if not answer_text or answer_text not in _normalized_text(candidate.get("value")):
            continue
        assertion_ids = _ids(unit.get("canonical_assertion_ids"))
        if not assertion_ids or any(
            assertion_id not in assertions
            or assertions[assertion_id].get("status") != "FINAL"
            or not _scope_covers_variant(assertions[assertion_id].get("application_scope"), variant)
            for assertion_id in assertion_ids
        ):
            continue
        assignment_ids = {
            str(row.get("id", ""))
            for row in assignments
            if row.get("status") == "PASS"
            and str(row.get("requirement_id", "")) == str(atom.get("requirement_id", ""))
            and str(row.get("field_resolution_id", "")) == str(field.get("id", ""))
            and row.get("primary_carrier_kind") in LEGAL_PARENT_CARRIERS
            and row.get("primary_surface") not in {"media", "backend_search_terms", "enriched_content"}
            and row.get("primary_surface") == field.get("surface")
            and p0_field_contract_allows(field, row.get("primary_carrier_kind"))
            and _scope_covers_variant(row.get("application_scope"), variant)
        }
        if not assignment_ids:
            continue
        result.setdefault(atom_id, []).append({
            "unit": unit,
            "candidate": candidate,
            "field": field,
            "assignment_ids": assignment_ids,
        })
    return result, raw_pass_counts


def _variant_identity(row: dict[str, Any], marketplace: str, locale: str) -> dict[str, str]:
    return {
        "marketplace": str(row.get("marketplace") or marketplace),
        "locale": str(row.get("locale") or locale),
        "parent_asin": str(row.get("parent_asin", "")),
        "child_asin": str(row.get("child_asin", "")),
        "pack": str(row.get("pack", "")),
        "color": str(row.get("color", "")),
        "size": str(row.get("size", row.get("size_or_capacity", ""))),
    }


def _validator_summary(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"ok": False, "schema_valid": False, "result_level": "INVALID"}
    return {
        key: result.get(key) for key in (
            "ok", "schema_valid", "contract_status", "derived_stage",
            "result_level", "component_result", "project_conclusion",
            "validator_sha256", "validated_input_sha256",
        ) if key in result
    }


def run_validator_cli(script: Path, bundle: Path, label: str) -> dict[str, Any]:
    """Run a component validator without importing the sibling Skill."""
    script = script.expanduser().resolve()
    bundle = bundle.expanduser().resolve()
    if not script.is_file():
        raise RuntimeError(f"{label} validator not found: {script}")
    try:
        completed = subprocess.run(
            [sys.executable, str(script), str(bundle)],
            cwd=script.parent,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"{label} validator execution failed: {exc}") from exc
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise RuntimeError(f"{label} validator emitted non-JSON output: {detail}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{label} validator result must be an object")
    result.pop("bundle", None)
    result["validator_exit_code"] = completed.returncode
    result["validator_sha256"] = file_sha256(script)
    result["validated_input_sha256"] = full_input_hash(_read_json(bundle))
    return result


def _append_validator_errors(
    errors: list[str], label: str, result: Any, *, require_schema_valid: bool = False,
) -> None:
    if not isinstance(result, dict):
        errors.append(f"[PKG-VALIDATOR-001] {label}: missing validator result")
        return
    if require_schema_valid and result.get("schema_valid") is not True:
        errors.append(f"[PKG-VALIDATOR-002] {label}: structural schema validation did not pass")
    if result.get("ok") is not True:
        rows = result.get("errors") if isinstance(result.get("errors"), list) else []
        if rows:
            for row in rows:
                errors.append(f"[PKG-{label.upper()}-VALIDATOR] {row}")
        else:
            errors.append(f"[PKG-VALIDATOR-003] {label}: component validator did not pass")


def _child_atoms(aplus: dict[str, Any]) -> list[dict[str, Any]]:
    denominator = aplus.get("decision_denominator_snapshot")
    if not isinstance(denominator, dict):
        return []
    return _objects(denominator.get("atoms", denominator.get("requirement_atoms", [])))


def _child_requirements(aplus: dict[str, Any]) -> list[dict[str, Any]]:
    decision_map = aplus.get("decision_map")
    if isinstance(decision_map, dict):
        rows = _objects(decision_map.get("requirements"))
        if rows:
            return rows
    denominator = aplus.get("decision_denominator_snapshot")
    if isinstance(denominator, dict):
        return _objects(denominator.get("requirements"))
    return []


def _frozen_parent_input(parent: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the exact prior FROZEN input from RESULT_RECEIVED.

    The frozen payload hash and handoff checksum deliberately normalize the
    lifecycle acknowledgement, so the only permitted acknowledgement change is
    the handoff status itself.
    """
    frozen = copy.deepcopy(parent)
    handoff = frozen.get("enriched_content_handoff")
    if isinstance(handoff, dict):
        handoff["status"] = "FROZEN"
    return frozen


def _coordination_receipt_for_state(
    parent: dict[str, Any],
    aplus: dict[str, Any],
    *,
    parent_state: str,
    component_result: str,
    prior_receipt: Any,
    parent_validator_sha256: str,
    aplus_validator_sha256: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate the previous receipt and emit the deterministic next receipt."""
    issues: list[str] = []
    handoff = parent.get("enriched_content_handoff")
    handoff = handoff if isinstance(handoff, dict) else {}
    snapshot_id = str(handoff.get("snapshot_id", ""))
    revision = handoff.get("semantic_revision")
    revision = revision if isinstance(revision, int) and not isinstance(revision, bool) else 0
    predecessor = str(handoff.get("predecessor_snapshot_id", ""))

    prior = prior_receipt if isinstance(prior_receipt, dict) else None
    if prior_receipt is not None:
        for issue in validate_coordination_receipt(prior_receipt):
            issues.append(f"[PKG-RECEIPT-001] prior receipt: {issue}")
    if prior_receipt is not None and prior is None:
        issues.append("[PKG-RECEIPT-002] prior receipt must be an object")
    if issues:
        return None, issues

    current_parent_hash = full_input_hash(parent)
    current_aplus_hash = full_input_hash(aplus)
    current_delta = delta_fingerprint(aplus)
    project = parent.get("project") if isinstance(parent.get("project"), dict) else {}
    current_project_id = str(project.get("project_id", ""))
    current_chain_id = coordination_chain_id(parent)
    if prior is not None and (
        prior.get("project_id") != current_project_id
        or prior.get("chain_id") != current_chain_id
    ):
        return None, ["[PKG-RECEIPT-016] receipt project/chain differs from the current package"]
    if prior is not None and (
        prior.get("parent_validator_sha256") != parent_validator_sha256
        or prior.get("aplus_validator_sha256") != aplus_validator_sha256
    ):
        return None, ["[PKG-RECEIPT-016] receipt validator identity differs from the current validation"]

    if parent_state == "RESULT_RECEIVED" and component_result == "COMPONENT_PASS":
        if prior is None:
            return None, [
                "[PKG-RECEIPT-003] RESULT_RECEIVED cannot reach PASS without the prior AWAITING_RESULT_ACK receipt"
            ]
        if prior.get("result") == "PASS" and (
            prior.get("handoff_snapshot_id") == snapshot_id
            and prior.get("semantic_revision") == revision
            and prior.get("parent_full_sha256") == current_parent_hash
            and prior.get("aplus_full_sha256") == current_aplus_hash
            and prior.get("delta_fingerprint") == current_delta
        ):
            return copy.deepcopy(prior), []
        if prior.get("result") == "DELTA_REQUIRED" and (
            prior.get("handoff_snapshot_id") == snapshot_id
            and prior.get("semantic_revision") == revision
        ):
            return None, [
                "[PKG-RECEIPT-004] a DELTA receipt on this snapshot requires SUPERSEDED and semantic refreeze before PASS"
            ]
        expected_parent_hash = full_input_hash(_frozen_parent_input(parent))
        if prior.get("result") != "AWAITING_RESULT_ACK":
            issues.append("[PKG-RECEIPT-005] terminal PASS requires an AWAITING_RESULT_ACK predecessor")
        if prior.get("handoff_snapshot_id") != snapshot_id or prior.get("semantic_revision") != revision:
            issues.append("[PKG-RECEIPT-006] prior receipt snapshot/revision differs from RESULT_RECEIVED")
        if prior.get("parent_full_sha256") != expected_parent_hash:
            issues.append("[PKG-RECEIPT-007] prior receipt is not bound to the exact FROZEN parent input")
        if prior.get("aplus_full_sha256") != current_aplus_hash:
            issues.append("[PKG-RECEIPT-008] prior receipt is not bound to the exact current A+ input")
        if prior.get("delta_fingerprint") != current_delta:
            issues.append("[PKG-RECEIPT-009] prior receipt delta fingerprint differs from the current component")
        if issues:
            return None, issues
        return build_coordination_receipt(
            parent=parent, aplus=aplus, handoff_snapshot_id=snapshot_id,
            semantic_revision=revision, result="PASS",
            parent_validator_sha256=parent_validator_sha256,
            aplus_validator_sha256=aplus_validator_sha256,
            previous_receipt=prior,
        ), []

    if parent_state == "FROZEN" and component_result == "COMPONENT_PASS":
        if prior is None:
            if revision != 1 or predecessor:
                return None, [
                    "[PKG-RECEIPT-010] a refrozen revision requires the preceding DELTA receipt"
                ]
            return build_coordination_receipt(
                parent=parent, aplus=aplus, handoff_snapshot_id=snapshot_id,
                semantic_revision=revision, result="AWAITING_RESULT_ACK",
                parent_validator_sha256=parent_validator_sha256,
                aplus_validator_sha256=aplus_validator_sha256,
            ), []
        if (
            prior.get("result") == "AWAITING_RESULT_ACK"
            and prior.get("handoff_snapshot_id") == snapshot_id
            and prior.get("semantic_revision") == revision
            and prior.get("parent_full_sha256") == current_parent_hash
            and prior.get("aplus_full_sha256") == current_aplus_hash
            and prior.get("delta_fingerprint") == current_delta
        ):
            return copy.deepcopy(prior), []
        if prior.get("result") != "DELTA_REQUIRED":
            issues.append("[PKG-RECEIPT-011] refrozen input requires a DELTA_REQUIRED predecessor receipt")
        if prior.get("handoff_snapshot_id") != predecessor:
            issues.append("[PKG-RECEIPT-012] DELTA receipt snapshot must equal the handoff predecessor")
        if prior.get("semantic_revision") != revision - 1:
            issues.append("[PKG-RECEIPT-013] refreeze semantic revision must increment the DELTA receipt revision by one")
        if prior.get("handoff_snapshot_id") == snapshot_id:
            issues.append("[PKG-RECEIPT-014] DELTA and refrozen receipts cannot use the same snapshot")
        if issues:
            return None, issues
        return build_coordination_receipt(
            parent=parent, aplus=aplus, handoff_snapshot_id=snapshot_id,
            semantic_revision=revision, result="AWAITING_RESULT_ACK",
            parent_validator_sha256=parent_validator_sha256,
            aplus_validator_sha256=aplus_validator_sha256,
            previous_receipt=prior,
        ), []

    if parent_state == "RECONCILIATION_REQUIRED" and component_result == "DELTA_REQUIRED":
        if prior is not None and (
            prior.get("result") == "DELTA_REQUIRED"
            and prior.get("handoff_snapshot_id") == snapshot_id
            and prior.get("semantic_revision") == revision
            and prior.get("parent_full_sha256") == current_parent_hash
            and prior.get("aplus_full_sha256") == current_aplus_hash
            and prior.get("delta_fingerprint") == current_delta
        ):
            return copy.deepcopy(prior), []
        if prior is not None and (
            prior.get("handoff_snapshot_id") != snapshot_id
            or prior.get("semantic_revision") != revision
        ):
            return None, [
                "[PKG-RECEIPT-015] a DELTA transition must chain from the same accepted snapshot/revision"
            ]
        return build_coordination_receipt(
            parent=parent, aplus=aplus, handoff_snapshot_id=snapshot_id,
            semantic_revision=revision, result="DELTA_REQUIRED",
            parent_validator_sha256=parent_validator_sha256,
            aplus_validator_sha256=aplus_validator_sha256,
            previous_receipt=prior,
        ), []

    return None, []


def validate_listing_package(
    parent: Any,
    aplus: Any,
    *,
    parent_validation: Any,
    aplus_validation: Any,
    prior_receipt: Any | None = None,
) -> dict[str, Any]:
    """Coordinate independently validated bundles into one fail-closed result."""
    errors: list[str] = []
    warnings: list[str] = []
    business_blockers: list[str] = []

    if not isinstance(parent, dict) or not isinstance(aplus, dict):
        return {
            "ok": False,
            "structural_valid": False,
            "component_valid": False,
            "component_result": "INVALID",
            "package_result": "INVALID",
            "publication_boundary": {
                "coordinator_grants_authority": False,
                "publication_authorized": False,
                "live_pass": False,
            },
            "coordination_receipt": None,
            "receipt_required_for_next_state": False,
            "errors": ["[PKG-STRUCT-001] parent and A+ bundles must be JSON objects"],
            "business_blockers": [],
            "warnings": [],
        }

    if parent.get("schema_version") != PARENT_VERSION:
        errors.append(
            f"[PKG-VERSION-001] parent.schema_version: expected {PARENT_VERSION}; "
            "legacy contracts cannot participate in current Package PASS"
        )
    if aplus.get("schema_version") != APLUS_VERSION:
        errors.append(
            f"[PKG-VERSION-002] aplus.schema_version: expected {APLUS_VERSION}; "
            "legacy contracts cannot participate in current Package PASS"
        )
    _append_validator_errors(errors, "parent", parent_validation, require_schema_valid=True)
    _append_validator_errors(errors, "aplus", aplus_validation)
    parent_full_sha256 = full_input_hash(parent)
    aplus_full_sha256 = full_input_hash(aplus)
    if not isinstance(parent_validation, dict) or parent_validation.get("validated_input_sha256") != parent_full_sha256:
        errors.append("[PKG-VALIDATOR-005] parent validation is not bound to the exact parent input")
    if not isinstance(aplus_validation, dict) or aplus_validation.get("validated_input_sha256") != aplus_full_sha256:
        errors.append("[PKG-VALIDATOR-006] A+ validation is not bound to the exact A+ input")
    if not isinstance(aplus_validation, dict) or aplus_validation.get("structural_valid") is not True:
        errors.append("[PKG-VALIDATOR-004] aplus: structural report contract did not validate")

    project = parent.get("project") if isinstance(parent.get("project"), dict) else {}
    scope = parent.get("scope") if isinstance(parent.get("scope"), dict) else {}
    workflow = aplus.get("workflow_context") if isinstance(aplus.get("workflow_context"), dict) else {}
    aplus_project = aplus.get("project") if isinstance(aplus.get("project"), dict) else {}
    parent_handoff = parent.get("enriched_content_handoff")
    child_handoff = aplus.get("enriched_content_handoff")
    if not isinstance(parent_handoff, dict) or not isinstance(child_handoff, dict):
        errors.append("[PKG-HANDOFF-001] both bundles require handoff objects")
        parent_handoff = parent_handoff if isinstance(parent_handoff, dict) else {}
        child_handoff = child_handoff if isinstance(child_handoff, dict) else {}

    if parent_handoff.get("contract_version") != HANDOFF_VERSION or child_handoff.get("contract_version") != HANDOFF_VERSION:
        errors.append(f"[PKG-HANDOFF-002] both handoffs must use contract {HANDOFF_VERSION}")
    if workflow.get("mode") != "embedded":
        errors.append("[PKG-HANDOFF-003] A+ package coordination requires embedded mode")
    if child_handoff.get("status") != "FROZEN":
        errors.append("[PKG-HANDOFF-004] embedded A+ must preserve the accepted FROZEN snapshot")
    parent_state = str(parent_handoff.get("status", ""))
    if parent_state not in {"FROZEN", "RESULT_RECEIVED", "RECONCILIATION_REQUIRED", "SUPERSEDED"}:
        errors.append("[PKG-HANDOFF-005] parent handoff is not in a coordinatable lifecycle state")
    if parent_state == "SUPERSEDED":
        errors.append("[PKG-HANDOFF-006] superseded handoff cannot participate in Package PASS")

    if immutable_handoff(parent_handoff) != immutable_handoff(child_handoff):
        errors.append("[PKG-HANDOFF-007] immutable frozen handoff payloads are not deeply equal")
    snapshot_id = str(child_handoff.get("snapshot_id", ""))
    if workflow.get("accepted_handoff_snapshot_id") != snapshot_id:
        errors.append("[PKG-HANDOFF-008] accepted snapshot ID does not match the child FROZEN snapshot")
    if parent_handoff.get("snapshot_id") != snapshot_id:
        errors.append("[PKG-HANDOFF-009] parent and child snapshot IDs differ; refreeze is required")
    if child_handoff.get("parent_project_id") != project.get("project_id"):
        errors.append("[PKG-HANDOFF-010] handoff parent project ID mismatch")
    created_at = _parse_timestamp(child_handoff.get("created_at"))
    accepted_at = _parse_timestamp(workflow.get("accepted_at"))
    if created_at is None or accepted_at is None or accepted_at < created_at:
        errors.append("[PKG-HANDOFF-011] accepted_at must be a valid time at or after the frozen snapshot")
    expected_snapshot_id = canonical_handoff_snapshot_id(child_handoff)
    if not snapshot_id or snapshot_id != expected_snapshot_id:
        errors.append(
            f"[PKG-LINEAGE-003] frozen snapshot must be content-addressed as {expected_snapshot_id}"
        )
    revision = child_handoff.get("semantic_revision")
    predecessor = child_handoff.get("predecessor_snapshot_id")
    refreeze_reason = child_handoff.get("refreeze_reason")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("[PKG-LINEAGE-004] semantic_revision must be a positive integer")
    elif revision == 1 and (predecessor or refreeze_reason):
        errors.append(
            "[PKG-LINEAGE-005] initial semantic revision cannot claim a predecessor or refreeze reason"
        )
    elif revision > 1 and (
        not isinstance(predecessor, str)
        or not re.fullmatch(r"HO-[0-9a-f]{20}", predecessor)
        or predecessor == snapshot_id
        or not isinstance(refreeze_reason, str)
        or not refreeze_reason.strip()
    ):
        errors.append(
            "[PKG-LINEAGE-006] refrozen revision requires a different content-addressed "
            "predecessor and a non-empty reason"
        )
    for lineage_code, lineage_message in validate_lineage_registry(child_handoff, HANDOFF_V11_KEYS):
        errors.append(f"[PKG-LINEAGE-007] {lineage_code}: {lineage_message}")

    expected_parent_hash = canonical_parent_hash(parent)
    validated_parent_hash = (
        str(parent_validation.get("parent_bundle_sha256", ""))
        if isinstance(parent_validation, dict) else ""
    )
    if validated_parent_hash != expected_parent_hash:
        errors.append("[PKG-HASH-000] coordinator and parent validator freeze projections disagree")
    if parent_handoff.get("parent_bundle_sha256") != expected_parent_hash:
        errors.append("[PKG-HASH-001] current parent_bundle_sha256 mismatch")
    if parent_handoff.get("checksum") != canonical_handoff_hash(parent_handoff):
        errors.append("[PKG-HASH-002] current parent handoff checksum mismatch")
    if child_handoff.get("checksum") != canonical_handoff_hash(child_handoff):
        errors.append("[PKG-HASH-003] child FROZEN handoff checksum mismatch")
    frozen_parent = copy.deepcopy(parent)
    frozen_parent["enriched_content_handoff"] = copy.deepcopy(child_handoff)
    if child_handoff.get("parent_bundle_sha256") != canonical_parent_hash(frozen_parent):
        errors.append("[PKG-HASH-004] child parent hash does not reconstruct the accepted FROZEN parent")

    closure = parent.get("discovery", {}).get("closure") if isinstance(parent.get("discovery"), dict) else None
    ptd = parent.get("ptd_field_inventory")
    denominator = parent.get("decision_denominator_snapshot")
    closure_hash = canonical_sha256(closure)
    ptd_hash = hash_block(ptd)
    denominator_hash = hash_block(denominator)
    for field, expected, code in (
        ("discovery_closure_hash", closure_hash, "PKG-HASH-005"),
        ("ptd_inventory_hash", ptd_hash, "PKG-HASH-006"),
        ("decision_denominator_hash", denominator_hash, "PKG-HASH-007"),
    ):
        if parent_handoff.get(field) != expected or child_handoff.get(field) != expected:
            errors.append(f"[{code}] {field} does not bind the current frozen parent block")

    child_denominator = aplus.get("decision_denominator_snapshot")
    if isinstance(child_denominator, dict):
        declared_child_hash = child_denominator.get("checksum", child_denominator.get("hash"))
        if declared_child_hash != hash_block(child_denominator):
            errors.append("[PKG-HASH-008] A+ delegated denominator checksum mismatch")
        source_hash = child_denominator.get("source_hash")
        if source_hash not in (None, "") and source_hash != denominator_hash:
            errors.append("[PKG-HASH-009] A+ delegated denominator source_hash differs from parent")
    else:
        errors.append("[PKG-STRUCT-002] A+ decision denominator must be an object")

    marketplace = str(scope.get("marketplace", ""))
    locale = str(scope.get("locale", ""))
    if (
        child_handoff.get("marketplace") != marketplace
        or child_handoff.get("locale") != locale
        or aplus_project.get("marketplace") != marketplace
        or aplus_project.get("locale") != locale
    ):
        errors.append("[PKG-SCOPE-001] marketplace/locale binding mismatch")

    parent_variants = _index(parent.get("variant_topology"))
    child_variants = _index(aplus.get("variants"))
    delegated_variant_ids = _ids(child_handoff.get("variant_row_ids"))
    if delegated_variant_ids != set(child_variants):
        errors.append("[PKG-SCOPE-002] A+ real variant rows must exactly match delegated variant IDs")
    if not delegated_variant_ids.issubset(parent_variants):
        errors.append("[PKG-SCOPE-003] A+ variant scope expands beyond parent real rows")
    for variant_id in sorted(delegated_variant_ids & set(parent_variants) & set(child_variants)):
        if _variant_identity(parent_variants[variant_id], marketplace, locale) != _variant_identity(child_variants[variant_id], marketplace, locale):
            errors.append(f"[PKG-SCOPE-004] variant {variant_id!r} identity differs across bundles")

    for key in ("parent_asins", "child_asins", "packs", "colors", "sizes"):
        handoff_values = _scope_values(child_handoff.get("application_scope"), key)
        parent_values = (
            _scope_values(scope, "child_asins") if key == "child_asins"
            else _scope_values(scope, key)
        )
        if handoff_values - parent_values:
            errors.append(f"[PKG-SCOPE-005] handoff {key} expands parent scope")

    parent_atoms = _index(denominator.get("atoms") if isinstance(denominator, dict) else None)
    delegated_atoms = _index(child_handoff.get("requirement_atoms"))
    child_atoms = _index(_child_atoms(aplus))
    if set(delegated_atoms) != set(child_atoms):
        errors.append("[PKG-ATOM-001] A+ denominator atoms must exactly equal delegated handoff atoms")
    if not set(delegated_atoms).issubset(parent_atoms):
        errors.append("[PKG-ATOM-002] delegated atom is absent from parent frozen denominator")
    for atom_id in sorted(set(delegated_atoms) & set(child_atoms) & set(parent_atoms)):
        identities = {
            _atom_identity(parent_atoms[atom_id]),
            _atom_identity(delegated_atoms[atom_id]),
            _atom_identity(child_atoms[atom_id]),
        }
        if len(identities) != 1:
            errors.append(f"[PKG-ATOM-003] atom {atom_id!r} identity differs across bundles")
        variant_id = str(parent_atoms[atom_id].get("variant_row_id", ""))
        if variant_id not in parent_variants or variant_id not in delegated_variant_ids:
            errors.append(f"[PKG-ATOM-004] atom {atom_id!r} is not bound to a delegated real variant")

    parent_requirements = _index(
        parent.get("decision_map", {}).get("requirements")
        if isinstance(parent.get("decision_map"), dict) else None
    )
    handoff_requirements = _index(child_handoff.get("decision_requirements"))
    child_requirements = _index(_child_requirements(aplus))
    if set(handoff_requirements) != set(child_requirements):
        errors.append("[PKG-REQUIREMENT-001] child requirements must exactly equal the frozen delegated requirements")
    if not set(handoff_requirements).issubset(parent_requirements):
        errors.append("[PKG-REQUIREMENT-002] delegated requirement is absent from parent decision map")
    for requirement_id in sorted(set(handoff_requirements) & set(child_requirements)):
        if handoff_requirements[requirement_id] != child_requirements[requirement_id]:
            errors.append(f"[PKG-REQUIREMENT-003] requirement {requirement_id!r} differs from frozen handoff")

    parent_assertions = _index(parent.get("canonical_assertions"))
    child_assertions = _index(aplus.get("canonical_assertions"))
    frozen_assertion_ids = _ids(child_handoff.get("canonical_assertion_ids"))
    if not frozen_assertion_ids or not frozen_assertion_ids.issubset(parent_assertions):
        errors.append("[PKG-ASSERT-001] frozen assertion IDs must be a non-empty parent subset")
    if frozen_assertion_ids != set(child_assertions):
        errors.append("[PKG-ASSERT-002] child assertions must exactly equal frozen assertion IDs")
    for assertion_id in sorted(frozen_assertion_ids & set(parent_assertions) & set(child_assertions)):
        parent_assertion = parent_assertions[assertion_id]
        child_assertion = child_assertions[assertion_id]
        for field in ("statement", "fact_ids", "claim_ids"):
            if parent_assertion.get(field) != child_assertion.get(field):
                errors.append(f"[PKG-ASSERT-003] assertion {assertion_id!r} changes {field}")
        if parent_assertion.get("status") != "FINAL" or child_assertion.get("publish_status") != "PUBLISHABLE":
            errors.append(f"[PKG-ASSERT-004] assertion {assertion_id!r} is not publishable on both sides")
        expected_variant_ids = {
            variant_id for variant_id in delegated_variant_ids & set(parent_variants)
            if _scope_covers_variant(parent_assertion.get("application_scope"), parent_variants[variant_id])
        }
        child_variant_ids = _ids(child_assertion.get("variant_row_ids"))
        if not expected_variant_ids or child_variant_ids != expected_variant_ids:
            errors.append(
                f"[PKG-ASSERT-005] assertion {assertion_id!r} variant projection differs "
                "from its frozen parent application scope"
            )
        expected_scope = _assertion_scope_projection(
            parent_assertion.get("application_scope"), marketplace, locale,
            allow_context_fallback=True,
        )
        actual_scope = _assertion_scope_projection(
            child_assertion.get("application_scope"), marketplace, locale,
            allow_context_fallback=False,
        )
        if actual_scope != expected_scope:
            errors.append(
                f"[PKG-ASSERT-006] assertion {assertion_id!r} marketplace/locale/application "
                "scope projection differs from parent"
            )
        locale_rows = _objects(child_assertion.get("locale_expressions"))
        if (
            len(locale_rows) != 1
            or locale_rows[0].get("locale") != locale
            or _ids(locale_rows[0].get("fact_ids")) != _ids(parent_assertion.get("fact_ids"))
            or _ids(locale_rows[0].get("claim_ids")) != _ids(parent_assertion.get("claim_ids"))
        ):
            errors.append(
                f"[PKG-ASSERT-007] assertion {assertion_id!r} requires one locale-specific "
                "expression with the exact frozen evidence chain"
            )

    parent_fact_ids = _ids(child_handoff.get("fact_ids"))
    parent_claim_ids = _ids(child_handoff.get("claim_ids"))
    child_facts = _index(aplus.get("facts"))
    child_claims = _index(aplus.get("claims"))
    if parent_fact_ids != set(child_facts) or parent_claim_ids | _ids(child_handoff.get("blocked_claim_ids")) != set(child_claims):
        errors.append("[PKG-EVIDENCE-001] child fact/claim IDs differ from the frozen evidence set")
    parent_facts = _index(parent.get("facts"))
    parent_claims = _index(parent.get("claims"))
    for fact_id in sorted(parent_fact_ids & set(parent_facts) & set(child_facts)):
        parent_fact = parent_facts[fact_id]
        child_fact = child_facts[fact_id]
        if parent_fact.get("statement") != child_fact.get("statement"):
            errors.append(f"[PKG-EVIDENCE-002] fact {fact_id!r} statement changed in A+")
        if _ids(parent_fact.get("proving_source_ids")) != _ids(child_fact.get("proving_source_ids")):
            errors.append(f"[PKG-EVIDENCE-004] fact {fact_id!r} proving sources changed in A+")
        for key in ("parent_asins", "child_asins", "packs", "colors", "sizes"):
            if _scope_values(child_fact.get("scope"), key) - _scope_values(parent_fact.get("application_scope"), key):
                errors.append(f"[PKG-EVIDENCE-005] fact {fact_id!r} expands {key} scope in A+")
    for claim_id in sorted(parent_claim_ids & set(parent_claims) & set(child_claims)):
        parent_claim = parent_claims[claim_id]
        child_claim = child_claims[claim_id]
        if parent_claim.get("text") != child_claim.get("text"):
            errors.append(f"[PKG-EVIDENCE-003] claim {claim_id!r} text changed in A+")
        if _ids(parent_claim.get("fact_ids")) != _ids(child_claim.get("fact_ids")):
            errors.append(f"[PKG-EVIDENCE-006] claim {claim_id!r} fact chain changed in A+")
        for key in ("parent_asins", "child_asins", "packs", "colors", "sizes"):
            if _scope_values(child_claim.get("scope"), key) - _scope_values(parent_claim.get("application_scope"), key):
                errors.append(f"[PKG-EVIDENCE-007] claim {claim_id!r} expands {key} scope in A+")

    parent_bindings, raw_parent_pass_counts = _parent_answer_bindings(
        parent, parent_atoms, parent_variants,
    )
    parent_pass_atoms = {
        atom_id for atom_id, bindings in parent_bindings.items()
        if len(bindings) == 1 and raw_parent_pass_counts.get(atom_id) == 1
    }
    assignment_index = _index(parent.get("surface_assignments"))
    for requirement_id, requirement in sorted(handoff_requirements.items()):
        if requirement.get("early_disclosure_required") is not True:
            continue
        upstream_ref = str(requirement.get("upstream_primary_carrier_ref", ""))
        assignment = assignment_index.get(upstream_ref)
        if assignment is None:
            errors.append(
                f"[PKG-EARLY-001] requirement {requirement_id!r} upstream reference "
                "does not resolve to a real parent Surface Assignment"
            )
            continue
        if (
            assignment.get("requirement_id") != requirement_id
            or assignment.get("status") != "PASS"
            or assignment.get("primary_carrier_kind") not in LEGAL_PARENT_CARRIERS
            or assignment.get("primary_surface") in {"media", "backend_search_terms", "enriched_content"}
        ):
            errors.append(
                f"[PKG-EARLY-002] requirement {requirement_id!r} upstream assignment is "
                "cross-requirement, non-native, non-visible, or not PASS"
            )
            continue
        requirement_atom_ids = {
            atom_id for atom_id, atom in delegated_atoms.items()
            if atom.get("requirement_id") == requirement_id
        }
        for atom_id in sorted(requirement_atom_ids):
            matching = [
                binding for binding in parent_bindings.get(atom_id, [])
                if upstream_ref in binding["assignment_ids"]
            ]
            if len(matching) != 1 or raw_parent_pass_counts.get(atom_id) != 1:
                errors.append(
                    f"[PKG-EARLY-003] atom {atom_id!r} must resolve through its declared "
                    "upstream assignment to exactly one real parent PASS answer"
                )
                continue
            binding = matching[0]
            field = binding["field"]
            candidate = binding["candidate"]
            unit = binding["unit"]
            if field.get("visibility") != "BUYER_VISIBLE":
                errors.append(f"[PKG-EARLY-004] atom {atom_id!r} upstream field is not buyer-visible")
            if _normalized_text(unit.get("answer_text")) not in _normalized_text(candidate.get("value")):
                errors.append(f"[PKG-EARLY-005] atom {atom_id!r} upstream answer is absent from the FINAL candidate")
    child_component = aplus.get("component_result") if isinstance(aplus.get("component_result"), dict) else {}
    declared_component = str(child_component.get("status", "INVALID"))
    if isinstance(aplus_validation, dict) and aplus_validation.get("result_level") != declared_component:
        errors.append("[PKG-COMPONENT-002] child validator result_level differs from component_result.status")
    child_gap_ids = _ids(child_component.get("gap_atom_ids"))
    open_delta_ids = _ids(child_component.get("open_delta_request_ids"))
    child_pass_atoms = set(delegated_atoms) - child_gap_ids if declared_component == "COMPONENT_PASS" else set()
    if declared_component == "COMPONENT_PASS" and (child_gap_ids or open_delta_ids):
        errors.append("[PKG-COMPONENT-001] COMPONENT_PASS cannot carry gaps or open delta requests")
    if child_component.get("page_pass_implied") is not False or child_component.get("publication_authorized") is not False:
        errors.append("[PKG-AUTH-001] A+ component cannot imply page PASS or publication authority")

    child_answers = _objects(aplus.get("decision_answer_units"))
    child_carriers = _index(aplus.get("carriers"))
    for atom_id in sorted(child_pass_atoms):
        atom = delegated_atoms.get(atom_id, {})
        valid_answers: list[dict[str, Any]] = []
        for answer in child_answers:
            answer_atom_id = str(answer.get("requirement_atom_id", answer.get("atom_id", "")))
            carrier = child_carriers.get(str(answer.get("primary_carrier_id", "")), {})
            assertion_ids = _ids(answer.get("canonical_assertion_ids"))
            if (
                answer_atom_id == atom_id
                and str(answer.get("variant_row_id", "")) == str(atom.get("variant_row_id", ""))
                and answer.get("content_status") in FINAL_APLUS_CONTENT
                and answer.get("qa_status") == "PASS"
                and bool(assertion_ids)
                and assertion_ids.issubset(frozen_assertion_ids)
                and carrier.get("carrier_type") == "native_text"
                and carrier.get("coverage_role") == "PRIMARY_NATIVE_ANSWER"
                and carrier.get("content_status") in FINAL_APLUS_CONTENT
                and carrier.get("qa_status") == "PASS"
                and str(atom.get("variant_row_id", "")) in _ids(carrier.get("variant_row_ids"))
                and assertion_ids.issubset(_ids(carrier.get("canonical_assertion_ids")))
            ):
                valid_answers.append(answer)
        if len(valid_answers) != 1:
            errors.append(
                f"[PKG-COVERAGE-002] delegated atom {atom_id!r} requires exactly one "
                "FINAL QA-PASS native answer"
            )

    coverage_summary = aplus.get("coverage_summary") if isinstance(aplus.get("coverage_summary"), dict) else {}
    if (
        coverage_summary.get("p0_atoms_required") != len(delegated_atoms)
        or coverage_summary.get("p0_atoms_pass") != len(child_pass_atoms)
        or _ids(coverage_summary.get("gap_atom_ids")) != child_gap_ids
    ):
        errors.append("[PKG-COVERAGE-003] A+ declared atom summary differs from the component result")

    delta_rows = _index(aplus.get("delta_evidence_requests"))
    actual_open_delta_ids = {row_id for row_id, row in delta_rows.items() if row.get("status") == "OPEN"}
    if open_delta_ids != actual_open_delta_ids:
        errors.append("[PKG-DELTA-001] component open delta IDs do not match A+ delta rows")
    if parent_state == "RESULT_RECEIVED" and (declared_component != "COMPONENT_PASS" or actual_open_delta_ids or child_gap_ids):
        errors.append("[PKG-DELTA-002] RESULT_RECEIVED requires a gap-free COMPONENT_PASS; otherwise reconcile and refreeze")
    if parent_state == "RECONCILIATION_REQUIRED" and declared_component != "DELTA_REQUIRED":
        errors.append("[PKG-DELTA-003] RECONCILIATION_REQUIRED must bind a DELTA_REQUIRED child result")
    if declared_component == "DELTA_REQUIRED" and not (actual_open_delta_ids or child_gap_ids):
        errors.append("[PKG-DELTA-004] DELTA_REQUIRED must identify an open request or atom gap")
    if declared_component == "DELTA_REQUIRED" and not actual_open_delta_ids:
        errors.append("[PKG-DELTA-005] DELTA_REQUIRED requires at least one mapped OPEN evidence request")
    if parent_state == "FROZEN" and declared_component == "DELTA_REQUIRED":
        errors.append("[PKG-LINEAGE-001] a DELTA_REQUIRED child requires parent RECONCILIATION_REQUIRED")
    if parent_state == "RECONCILIATION_REQUIRED" and not actual_open_delta_ids:
        errors.append("[PKG-LINEAGE-002] reconciliation requires an OPEN delta on the accepted snapshot")

    child_module_ids = set(_index(aplus.get("modules")))
    mapped_gap_atoms: set[str] = set()
    for delta_id in sorted(actual_open_delta_ids):
        delta = delta_rows[delta_id]
        affected_requirements = _ids(delta.get("affected_requirement_ids"))
        affected_atoms = _ids(delta.get("affected_atom_ids"))
        affected_facts = _ids(delta.get("affected_fact_ids"))
        affected_claims = _ids(delta.get("affected_claim_ids"))
        affected_modules = _ids(delta.get("affected_module_ids"))
        if not affected_requirements or not affected_requirements.issubset(handoff_requirements):
            errors.append(f"[PKG-DELTA-006] delta {delta_id!r} must map to frozen delegated requirements")
        if not affected_facts.issubset(parent_fact_ids) or not affected_claims.issubset(parent_claim_ids):
            errors.append(f"[PKG-DELTA-007] delta {delta_id!r} expands the frozen fact/claim set")
        if affected_modules and not affected_modules.issubset(child_module_ids):
            errors.append(f"[PKG-DELTA-008] delta {delta_id!r} references unknown A+ modules")
        atom_mapping_valid = (
            bool(affected_atoms)
            and affected_atoms.issubset(child_gap_ids)
            and all(
                delegated_atoms.get(atom_id, {}).get("requirement_id") in affected_requirements
                for atom_id in affected_atoms
            )
        )
        if not atom_mapping_valid:
            errors.append(f"[PKG-DELTA-009] delta {delta_id!r} does not map to any declared gap atom")
        if atom_mapping_valid:
            mapped_gap_atoms.update(affected_atoms)
        expected_lineage = {
            "snapshot_id": child_handoff.get("snapshot_id", ""),
            "parent_bundle_sha256": child_handoff.get("parent_bundle_sha256", ""),
            "discovery_closure_hash": child_handoff.get("discovery_closure_hash", ""),
            "ptd_inventory_hash": child_handoff.get("ptd_inventory_hash", ""),
            "decision_denominator_hash": child_handoff.get("decision_denominator_hash", ""),
            "handoff_checksum": child_handoff.get("checksum", ""),
        }
        if delta.get("handoff_lineage") != expected_lineage:
            errors.append(
                f"[PKG-DELTA-011] delta {delta_id!r} is not bound to the exact accepted frozen lineage"
            )
    if child_gap_ids - mapped_gap_atoms:
        errors.append(
            f"[PKG-DELTA-010] gap atoms lack an OPEN delta mapping: "
            f"{sorted(child_gap_ids - mapped_gap_atoms)!r}"
        )

    required_atoms = set(parent_atoms)
    covered_atoms = parent_pass_atoms | child_pass_atoms
    coverage_gaps = sorted(required_atoms - covered_atoms)
    overlap = sorted(parent_pass_atoms & child_pass_atoms)
    if overlap:
        warnings.append(f"[PKG-COVERAGE-W01] redundant parent/A+ coverage for atoms {overlap!r}")
    if not required_atoms:
        errors.append("[PKG-COVERAGE-001] whole-page P0 denominator cannot be 0/0")

    parent_boundary = str(parent.get("execution_boundary", ""))
    child_boundary = str(workflow.get("execution_boundary", ""))
    if child_boundary != "read_only" or aplus_project.get("write_scope") != "read_only":
        errors.append("[PKG-AUTH-002] A+ 1.3 package coordination is read_only")
    if parent_boundary in {"read_only", "local_candidate"}:
        authorization = parent.get("publish_authorization")
        if isinstance(authorization, dict) and authorization.get("status") not in {None, "", "NOT_AUTHORIZED"}:
            errors.append("[PKG-AUTH-003] read-only parent cannot carry publication authorization")

    readback = _objects(parent.get("live_readback"))
    readback_statuses = {str(row.get("status", "")) for row in readback if row.get("status")}
    intended_children = _scope_values(scope, "child_asins")
    live_children = {
        str(row.get("child_asin", "")) for row in readback
        if row.get("status") == "LIVE_MATCH" and row.get("live_pass") is True
    }
    live_pass = bool(intended_children) and live_children == intended_children and readback_statuses == {"LIVE_MATCH"}
    if "LIVE_MISMATCH" in readback_statuses:
        live_result = "FRONTEND_MISMATCH"
    elif live_pass:
        live_result = "LIVE_MATCH"
    elif "ACCEPTED_BACKEND" in readback_statuses:
        live_result = "BACKEND_ACCEPTED_ONLY"
    else:
        live_result = "NOT_ASSESSED"
    if project.get("conclusion") == "LIVE_PASS" and not live_pass:
        business_blockers.append("[PKG-READBACK-001] ACCEPTED_BACKEND or frontend mismatch cannot establish LIVE_PASS")

    coordination_receipt: dict[str, Any] | None = None
    if (
        not errors
        and not business_blockers
        and (not coverage_gaps or declared_component == "DELTA_REQUIRED")
    ):
        coordination_receipt, receipt_issues = _coordination_receipt_for_state(
            parent,
            aplus,
            parent_state=parent_state,
            component_result=declared_component,
            prior_receipt=prior_receipt,
            parent_validator_sha256=(
                str(parent_validation.get("validator_sha256", ""))
                if isinstance(parent_validation, dict) else ""
            ),
            aplus_validator_sha256=(
                str(aplus_validation.get("validator_sha256", ""))
                if isinstance(aplus_validation, dict) else ""
            ),
        )
        errors.extend(receipt_issues)

    component_error_tokens = (
        "[PKG-PARENT-VALIDATOR]", "[PKG-APLUS-VALIDATOR]",
        "[PKG-VALIDATOR-003]", "[PKG-COMPONENT-", "[PKG-COVERAGE-002]",
        "[PKG-COVERAGE-003]",
    )
    structural_errors = [
        row for row in errors if not any(token in row for token in component_error_tokens)
    ]
    structural_valid = (
        isinstance(parent_validation, dict)
        and parent_validation.get("schema_valid") is True
        and isinstance(aplus_validation, dict)
        and aplus_validation.get("structural_valid") is True
        and not structural_errors
    )
    component_valid = (
        isinstance(parent_validation, dict)
        and parent_validation.get("ok") is True
        and isinstance(aplus_validation, dict)
        and aplus_validation.get("ok") is True
        and not any(any(token in row for token in component_error_tokens[2:]) for row in errors)
    )
    if not structural_valid:
        package_result = "INVALID"
    elif not component_valid or business_blockers:
        package_result = "BLOCKED"
    elif parent_state == "RECONCILIATION_REQUIRED" or declared_component == "DELTA_REQUIRED":
        package_result = "DELTA_REQUIRED"
    elif parent_state == "FROZEN" and declared_component == "COMPONENT_PASS":
        package_result = "AWAITING_RESULT_ACK"
    elif parent_state == "RESULT_RECEIVED" and declared_component == "COMPONENT_PASS" and not coverage_gaps:
        package_result = "PASS_CANDIDATE"
    else:
        package_result = "BLOCKED"

    publication_boundary = {
        "parent_execution_boundary": parent_boundary,
        "aplus_execution_boundary": child_boundary,
        "upstream_authorization_present": bool(
            isinstance(parent.get("publish_authorization"), dict)
            and parent.get("publish_authorization", {}).get("status") == "AUTHORIZED"
        ),
        "coordinator_grants_authority": False,
        "publication_authorized": False,
        "backend_accepted": "ACCEPTED_BACKEND" in readback_statuses,
        "live_result": live_result,
        "live_pass": live_pass,
    }
    return {
        "ok": False,
        "execution_boundary": "read_only",
        "structural_valid": structural_valid,
        "component_valid": component_valid,
        "component_result": declared_component,
        "package_result": package_result,
        "handoff_state": parent_state,
        "coverage": {
            "required_atom_ids": sorted(required_atoms),
            "parent_pass_atom_ids": sorted(parent_pass_atoms),
            "aplus_pass_atom_ids": sorted(child_pass_atoms),
            "covered_atom_ids": sorted(covered_atoms),
            "gap_atom_ids": coverage_gaps,
        },
        "hashes": {
            "current_parent_bundle_sha256": expected_parent_hash,
            "frozen_parent_bundle_sha256": str(child_handoff.get("parent_bundle_sha256", "")),
            "parent_full_input_sha256": parent_full_sha256,
            "aplus_full_input_sha256": aplus_full_sha256,
            "discovery_closure_hash": closure_hash,
            "ptd_inventory_hash": ptd_hash,
            "decision_denominator_hash": denominator_hash,
        },
        "publication_boundary": publication_boundary,
        "component_validations": {
            "parent": _validator_summary(parent_validation),
            "aplus": _validator_summary(aplus_validation),
        },
        "coordination_receipt": coordination_receipt,
        "receipt_required_for_next_state": package_result in {
            "AWAITING_RESULT_ACK", "DELTA_REQUIRED", "PASS_CANDIDATE",
        },
        "local_evidence_write": {
            "requested": False,
            "performed": False,
            "ledger_path": "",
            "receipt_sha256": "",
            "external_write": False,
        },
        "errors": sorted(set(errors)),
        "business_blockers": sorted(set(business_blockers)),
        "warnings": sorted(set(warnings)),
    }


def _bundled_validator_hashes(
    parent_validator: Path,
    aplus_validator: Path,
) -> tuple[str, str]:
    parent_path = parent_validator.expanduser().resolve()
    aplus_path = aplus_validator.expanduser().resolve()
    if parent_path != DEFAULT_PARENT_VALIDATOR.resolve() or aplus_path != DEFAULT_APLUS_VALIDATOR.resolve():
        raise LedgerError(
            "[PKG-LEDGER-002] controlled receipt ledgers require the bundled default validator paths"
        )
    return file_sha256(parent_path), file_sha256(aplus_path)


def _refreeze_against_delta_head_issues(parent: dict[str, Any], head: Any) -> list[str]:
    if not isinstance(head, dict) or head.get("result") != "DELTA_REQUIRED":
        return []
    handoff = parent.get("enriched_content_handoff")
    handoff = handoff if isinstance(handoff, dict) else {}
    if handoff.get("status") != "FROZEN":
        return []
    registry = handoff.get("lineage_registry")
    record = registry[0] if isinstance(registry, list) and len(registry) == 1 and isinstance(registry[0], dict) else {}
    valid = (
        handoff.get("predecessor_snapshot_id") == head.get("handoff_snapshot_id")
        and handoff.get("semantic_revision") == head.get("semantic_revision", 0) + 1
        and handoff.get("snapshot_id") != head.get("handoff_snapshot_id")
        and record.get("snapshot_id") == head.get("handoff_snapshot_id")
        and record.get("semantic_revision") == head.get("semantic_revision")
        and record.get("status") == "SUPERSEDED"
        and record.get("successor_snapshot_id") == handoff.get("snapshot_id")
    )
    return [] if valid else [
        "[PKG-RECEIPT-017] DELTA head requires the old snapshot SUPERSEDED, revision + 1, and a new FROZEN successor"
    ]


def _terminal_receipt_binds(
    receipt: Any,
    parent: dict[str, Any],
    aplus: dict[str, Any],
    *,
    parent_validator_sha256: str,
    aplus_validator_sha256: str,
) -> bool:
    handoff = parent.get("enriched_content_handoff")
    handoff = handoff if isinstance(handoff, dict) else {}
    project = parent.get("project") if isinstance(parent.get("project"), dict) else {}
    return (
        isinstance(receipt, dict)
        and receipt.get("result") == "PASS"
        and receipt.get("project_id") == project.get("project_id")
        and receipt.get("chain_id") == coordination_chain_id(parent)
        and receipt.get("handoff_snapshot_id") == handoff.get("snapshot_id")
        and receipt.get("semantic_revision") == handoff.get("semantic_revision")
        and receipt.get("parent_full_sha256") == full_input_hash(parent)
        and receipt.get("aplus_full_sha256") == full_input_hash(aplus)
        and receipt.get("parent_validator_sha256") == parent_validator_sha256
        and receipt.get("aplus_validator_sha256") == aplus_validator_sha256
        and not validate_coordination_receipt(receipt)
    )


def validate_listing_package_with_ledger(
    parent: dict[str, Any],
    aplus: dict[str, Any],
    *,
    parent_validation: dict[str, Any],
    aplus_validation: dict[str, Any],
    receipt_ledger: Path,
    record_receipt: bool,
    parent_validator: Path,
    aplus_validator: Path,
    require_existing_ledger: bool = False,
) -> dict[str, Any]:
    """Controlled local entrypoint; only this path may confirm terminal PASS."""
    expected_parent_validator, expected_aplus_validator = _bundled_validator_hashes(
        parent_validator, aplus_validator,
    )
    if (
        parent_validation.get("validator_sha256") != expected_parent_validator
        or aplus_validation.get("validator_sha256") != expected_aplus_validator
    ):
        raise LedgerError(
            "[PKG-LEDGER-002] component reports do not bind the bundled validator identities"
        )
    ledger = load_receipt_ledger(
        receipt_ledger, allow_missing=not require_existing_ledger,
    )
    head = ledger.get("head")
    result = validate_listing_package(
        parent,
        aplus,
        parent_validation=parent_validation,
        aplus_validation=aplus_validation,
        prior_receipt=head,
    )
    result["ledger"] = {
        "contract_version": ledger["contract_version"],
        "entry_count": ledger["entry_count"],
        "ledger_sha256": ledger["ledger_sha256"],
        "head_receipt_sha256": (
            str(head.get("receipt_sha256", "")) if isinstance(head, dict) else ""
        ),
        "head_result": str(head.get("result", "")) if isinstance(head, dict) else "",
    }
    result["local_evidence_write"] = {
        "requested": record_receipt,
        "performed": False,
        "ledger_path": str(receipt_ledger),
        "receipt_sha256": "",
        "external_write": False,
    }

    errors = list(result.get("errors", []))
    handoff = parent.get("enriched_content_handoff")
    handoff = handoff if isinstance(handoff, dict) else {}
    if isinstance(head, dict) and head.get("result") == "DELTA_REQUIRED" and (
        handoff.get("status") == "RESULT_RECEIVED"
        and head.get("handoff_snapshot_id") == handoff.get("snapshot_id")
        and head.get("semantic_revision") == handoff.get("semantic_revision")
    ):
        errors.append("[PKG-RECEIPT-016] stale AWAIT replay attempted after the ledger advanced to DELTA")
    errors.extend(_refreeze_against_delta_head_issues(parent, head))
    result["errors"] = sorted(set(errors))
    candidate = result.get("coordination_receipt")

    if record_receipt:
        if result["errors"] or result.get("business_blockers") or not isinstance(candidate, dict):
            detail = result["errors"][0] if result["errors"] else "no recordable receipt transition"
            raise LedgerError(f"[PKG-LEDGER-002] record requested for an invalid transition: {detail}")
        if isinstance(head, dict) and candidate.get("receipt_sha256") == head.get("receipt_sha256"):
            raise LedgerError("[PKG-RECEIPT-016] repeated receipt consumption or duplicate record attempt")
        ledger = append_receipt(receipt_ledger, candidate)
        head = ledger["head"]
        result["ledger"] = {
            "contract_version": ledger["contract_version"],
            "entry_count": ledger["entry_count"],
            "ledger_sha256": ledger["ledger_sha256"],
            "head_receipt_sha256": str(head.get("receipt_sha256", "")),
            "head_result": str(head.get("result", "")),
        }
        result["local_evidence_write"].update({
            "performed": True,
            "receipt_sha256": str(head.get("receipt_sha256", "")),
        })

    terminal = _terminal_receipt_binds(
        head,
        parent,
        aplus,
        parent_validator_sha256=expected_parent_validator,
        aplus_validator_sha256=expected_aplus_validator,
    )
    if terminal and not result["errors"] and not result.get("business_blockers"):
        if record_receipt or (
            isinstance(candidate, dict)
            and candidate.get("receipt_sha256") == head.get("receipt_sha256")
        ):
            result["ok"] = True
            result["package_result"] = "PASS"
            result["coordination_receipt"] = copy.deepcopy(head)
            result["receipt_required_for_next_state"] = False
    elif result.get("package_result") == "PASS_CANDIDATE":
        result["package_result"] = "TRANSITION_LEDGER_REQUIRED"
        result["ok"] = False
    return result


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _infra_result(
    message: str,
    *,
    local_write_requested: bool = False,
    ledger_path: str = "",
) -> dict[str, Any]:
    return {
        "ok": False,
        "execution_boundary": "read_only",
        "structural_valid": False,
        "component_valid": False,
        "component_result": "INVALID",
        "package_result": "INFRA_ERROR",
        "publication_boundary": {
            "coordinator_grants_authority": False,
            "publication_authorized": False,
            "live_pass": False,
        },
        "coordination_receipt": None,
        "receipt_required_for_next_state": False,
        "local_evidence_write": {
            "requested": local_write_requested,
            "performed": False,
            "ledger_path": ledger_path,
            "receipt_sha256": "",
            "external_write": False,
        },
        "errors": [f"[PKG-INFRA-001] {message}"],
        "business_blockers": [],
        "warnings": [],
    }


def _group_preflight_result(manifest: Any, errors: list[str]) -> dict[str, Any]:
    shape = validate_group_manifest(manifest)
    members = shape.get("members", []) if isinstance(shape, dict) else []
    return {
        "ok": False,
        "structural_valid": False,
        "component_valid": False,
        "semantic_match": False,
        "package_result": "GROUP_INVALID",
        "group_contract_version": GROUP_CONTRACT_VERSION,
        "group_id": manifest.get("group_id", "") if isinstance(manifest, dict) else "",
        "marketplace": manifest.get("marketplace", "") if isinstance(manifest, dict) else "",
        "locales": sorted(
            str(row.get("locale", "")) for row in members
            if isinstance(row, dict) and row.get("locale")
        ),
        "member_results": [],
        "assertion_families": [],
        "hashes": {},
        "publication_boundary": {
            "execution_boundary": "read_only",
            "coordinator_grants_authority": False,
            "publication_authorized": False,
            "live_pass": False,
        },
        "errors": sorted(set(errors)),
        "warnings": [],
    }


def _resolved_file_identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino


def validate_listing_locale_group_files(
    manifest_path: Path,
    parent_validator: Path,
    aplus_validator: Path,
) -> dict[str, Any]:
    """Controlled GROUP_PASS entrypoint using exact files and real validators."""
    manifest = _read_json(manifest_path)
    shape = validate_group_manifest(manifest)
    if not shape["valid"]:
        return _group_preflight_result(manifest, shape["errors"])

    base_dir = manifest_path.parent
    resolved_members: list[dict[str, Any]] = []
    seen_files: dict[tuple[int, int], str] = {}
    preflight_errors: list[str] = []
    for member in shape["members"]:
        locale = member["locale"]
        resolved: dict[str, Any] = {"locale": locale}
        for role in ("parent_bundle", "aplus_bundle", "coordination_ledger"):
            candidate = Path(member[role]).expanduser()
            path = (candidate if candidate.is_absolute() else base_dir / candidate).resolve()
            resolved[role] = path
            identity = _resolved_file_identity(path)
            prior = seen_files.get(identity)
            label = f"{locale}.{role}"
            if prior is not None:
                preflight_errors.append(
                    f"[PKG-GROUP-MANIFEST-008] resolved bundle file {label} aliases {prior}"
                )
            else:
                seen_files[identity] = label
        resolved_members.append(resolved)
    if preflight_errors:
        return _group_preflight_result(manifest, preflight_errors)

    runtime_members: list[dict[str, Any]] = []
    for member in resolved_members:
        parent_path = member["parent_bundle"]
        aplus_path = member["aplus_bundle"]
        ledger_path = member["coordination_ledger"]
        parent = _read_json(parent_path)
        aplus = _read_json(aplus_path)
        parent_validation = run_validator_cli(parent_validator, parent_path, "parent")
        aplus_validation = run_validator_cli(aplus_validator, aplus_path, "aplus")
        pair_result = validate_listing_package_with_ledger(
            parent,
            aplus,
            parent_validation=parent_validation,
            aplus_validation=aplus_validation,
            receipt_ledger=ledger_path,
            record_receipt=False,
            parent_validator=parent_validator,
            aplus_validator=aplus_validator,
            require_existing_ledger=True,
        )
        runtime_members.append({
            "locale": member["locale"],
            "parent": parent,
            "aplus": aplus,
            "pair_result": pair_result,
            "ledger_path": str(ledger_path),
        })

    member_errors: list[str] = []
    controlled_members: list[dict[str, Any]] = []
    for member in runtime_members:
        locale = str(member.get("locale", ""))
        parent = member["parent"]
        aplus = member["aplus"]
        pair = member["pair_result"]
        receipt = pair.get("coordination_receipt") if isinstance(pair, dict) else None
        parent_hash = full_input_hash(parent)
        aplus_hash = full_input_hash(aplus)
        pair_hashes = pair.get("hashes") if isinstance(pair.get("hashes"), dict) else {}
        ledger = pair.get("ledger") if isinstance(pair.get("ledger"), dict) else {}
        binding_ok = (
            pair.get("ok") is True
            and pair.get("package_result") == "PASS"
            and pair.get("structural_valid") is True
            and pair.get("component_valid") is True
            and pair_hashes.get("parent_full_input_sha256") == parent_hash
            and pair_hashes.get("aplus_full_input_sha256") == aplus_hash
            and isinstance(receipt, dict)
            and receipt.get("result") == "PASS"
            and receipt.get("parent_full_sha256") == parent_hash
            and receipt.get("aplus_full_sha256") == aplus_hash
            and ledger.get("head_receipt_sha256") == receipt.get("receipt_sha256")
            and ledger.get("head_result") == "PASS"
            and not validate_coordination_receipt(receipt)
        )
        if not binding_ok:
            member_errors.append(
                f"[PKG-GROUP-MEMBER-001] {locale}: real component validation, pair PASS, exact input hashes, and terminal receipt did not all bind"
            )
        controlled_members.append({
            "locale": locale,
            "parent": parent,
            "aplus": aplus,
            "parent_full_input_sha256": parent_hash,
            "aplus_full_input_sha256": aplus_hash,
            "terminal_receipt_sha256": (
                str(receipt.get("receipt_sha256", "")) if isinstance(receipt, dict) else ""
            ),
            "ledger_sha256": str(ledger.get("ledger_sha256", "")),
        })
    if member_errors:
        result = _group_preflight_result(manifest, member_errors)
        result["package_result"] = "GROUP_MEMBER_BLOCKED"
        result["member_results"] = [{
            "locale": row["locale"],
            "parent_full_input_sha256": row["parent_full_input_sha256"],
            "aplus_full_input_sha256": row["aplus_full_input_sha256"],
            "terminal_receipt_sha256": row["terminal_receipt_sha256"],
            "ledger_sha256": row["ledger_sha256"],
        } for row in controlled_members]
        return result

    semantic = validate_listing_locale_group(manifest, controlled_members)
    if semantic.get("semantic_match") is not True:
        semantic["package_result"] = "GROUP_INVALID"
        return semantic
    semantic["ok"] = True
    semantic["component_valid"] = True
    semantic["package_result"] = "GROUP_PASS"
    semantic["member_results"] = [{
        "locale": row["locale"],
        "parent_full_input_sha256": row["parent_full_input_sha256"],
        "aplus_full_input_sha256": row["aplus_full_input_sha256"],
        "terminal_receipt_sha256": row["terminal_receipt_sha256"],
        "ledger_sha256": row["ledger_sha256"],
    } for row in controlled_members]
    return semantic


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent_bundle", type=Path, nargs="?")
    parser.add_argument("aplus_bundle", type=Path, nargs="?")
    parser.add_argument(
        "--group-manifest",
        type=Path,
        help="validate two or more locale pairs described by the closed group contract",
    )
    parser.add_argument(
        "--prior-receipt",
        type=Path,
        help="legacy sidecar compatibility; never sufficient for terminal PASS",
    )
    parser.add_argument(
        "--receipt-ledger",
        type=Path,
        help="controlled append-only local JSONL receipt ledger",
    )
    parser.add_argument(
        "--record-receipt",
        action="store_true",
        help="append the valid next receipt to --receipt-ledger using lock, append and fsync",
    )
    parser.add_argument("--parent-validator", type=Path, default=DEFAULT_PARENT_VALIDATOR)
    parser.add_argument("--aplus-validator", type=Path, default=DEFAULT_APLUS_VALIDATOR)
    args = parser.parse_args()
    try:
        pair_requested = args.parent_bundle is not None or args.aplus_bundle is not None
        pair_complete = args.parent_bundle is not None and args.aplus_bundle is not None
        if args.group_manifest is not None:
            if pair_requested:
                raise RuntimeError("choose either two pair paths or --group-manifest, not both")
            if args.prior_receipt is not None:
                raise RuntimeError("group mode reads one coordination_ledger path per manifest member")
            if args.receipt_ledger is not None or args.record_receipt:
                raise RuntimeError("group mode is confirmation-only and reads ledger paths from its manifest")
            result = validate_listing_locale_group_files(
                args.group_manifest.expanduser().resolve(),
                args.parent_validator,
                args.aplus_validator,
            )
        else:
            if not pair_complete:
                raise RuntimeError("provide both parent_bundle and aplus_bundle, or --group-manifest")
            if args.record_receipt and args.receipt_ledger is None:
                raise RuntimeError("--record-receipt requires --receipt-ledger")
            if args.receipt_ledger is not None and args.prior_receipt is not None:
                raise RuntimeError("choose controlled --receipt-ledger or legacy --prior-receipt, not both")
            parent_path = args.parent_bundle.expanduser().resolve()
            aplus_path = args.aplus_bundle.expanduser().resolve()
            parent = _read_json(parent_path)
            aplus = _read_json(aplus_path)
            prior_receipt = (
                _read_json(args.prior_receipt.expanduser().resolve())
                if args.prior_receipt is not None else None
            )
            parent_validation = run_validator_cli(args.parent_validator, parent_path, "parent")
            aplus_validation = run_validator_cli(args.aplus_validator, aplus_path, "aplus")
            if args.receipt_ledger is not None:
                ledger_path = args.receipt_ledger.expanduser().absolute()
                if ledger_path in {parent_path, aplus_path}:
                    raise RuntimeError("receipt ledger cannot overwrite a bundle input")
                result = validate_listing_package_with_ledger(
                    parent,
                    aplus,
                    parent_validation=parent_validation,
                    aplus_validation=aplus_validation,
                    receipt_ledger=ledger_path,
                    record_receipt=args.record_receipt,
                    parent_validator=args.parent_validator,
                    aplus_validator=args.aplus_validator,
                    require_existing_ledger=False,
                )
            else:
                result = validate_listing_package(
                    parent, aplus,
                    parent_validation=parent_validation,
                    aplus_validation=aplus_validation,
                    prior_receipt=prior_receipt,
                )
                if result.get("package_result") == "PASS_CANDIDATE":
                    result["package_result"] = "TRANSITION_LEDGER_REQUIRED"
                    result["warnings"] = sorted(set(result.get("warnings", [])) | {
                        "[PKG-RECEIPT-W01] terminal PASS requires the controlled monotonic receipt ledger"
                    })
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps(_infra_result(
            str(exc),
            local_write_requested=bool(args.record_receipt),
            ledger_path=(str(args.receipt_ledger.expanduser().absolute()) if args.receipt_ledger else ""),
        ), ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    result.setdefault("execution_boundary", "read_only")
    result.setdefault("local_evidence_write", {
        "requested": False,
        "performed": False,
        "ledger_path": "",
        "receipt_sha256": "",
        "external_write": False,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
