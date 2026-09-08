#!/usr/bin/env python3
"""Pure PTD inventory and conditional-field closure phase for Listing Bundle v1.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from listing_v11_domains import evaluate_ptd
from listing_v11_evidence import source_can_prove_account_field
from listing_v11_phase import (
    EXPECTED_FIELD_KEYS,
    PTD_KEYS,
    PhaseDelta,
    _err,
    _hash_without,
    _index,
    _obj_list,
    _refs,
)


@dataclass(frozen=True)
class PtdReport:
    delta: PhaseDelta
    inventory: dict[str, Any]
    expected_fields: tuple[dict[str, Any], ...]


def validate_ptd_domain(
    bundle: dict[str, Any],
    *,
    catalog_context: dict[str, Any],
    scope: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    rule_index: dict[str, dict[str, Any]],
    field_index: dict[str, dict[str, Any]],
) -> PtdReport:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    gates: dict[str, str] = {}
    context = catalog_context
    ptd = bundle.get("ptd_field_inventory") if isinstance(bundle.get("ptd_field_inventory"), dict) else {}
    if set(ptd) != PTD_KEYS:
        _err(errors, "L11-PTD-012", "ptd_field_inventory", f"must contain exactly {sorted(PTD_KEYS)}")
    expected_fields = _obj_list(ptd.get("expected_fields", []), "ptd_field_inventory.expected_fields", errors)
    if ptd.get("product_type") != context.get("product_type"):
        _err(errors, "L11-PTD-014", "ptd_field_inventory.product_type", "must equal the frozen Product Type")
    expected_field_index = _index(expected_fields, "ptd_field_inventory.expected_fields", errors)
    for index, row in enumerate(expected_fields):
        path = f"ptd_field_inventory.expected_fields[{index}]"
        if set(row) != EXPECTED_FIELD_KEYS:
            _err(errors, "L11-PTD-013", path, f"must contain exactly {sorted(EXPECTED_FIELD_KEYS)}")
        field = field_index.get(row.get("field_resolution_id"))
        if field is None:
            _err(errors, "L11-PTD-001", f"{path}.field_resolution_id", "unknown field resolution")
        if row.get("requirement_status") not in {"REQUIRED", "CONDITIONAL", "OPTIONAL"}:
            _err(errors, "L11-PTD-002", f"{path}.requirement_status", "unsupported requirement status")
        if field is not None and row.get("requirement_status") != field.get("requirement_status"):
            _err(errors, "L11-PTD-015", path, "inventory requirement status must exactly match its Field Resolution")
        if row.get("requirement_status") == "CONDITIONAL" and row.get("trigger_status") == "UNKNOWN":
            _err(errors, "L11-PTD-003", f"{path}.trigger_status", "conditional trigger cannot remain unknown")
        if row.get("requirement_status") == "CONDITIONAL" and row.get("trigger_status") == "TRIGGERED" and row.get("closure_status") != "CLOSED":
            _err(errors, "L11-PTD-008", f"{path}.closure_status", "triggered conditional field must close")
        if row.get("requirement_status") == "REQUIRED" and row.get("closure_status") != "CLOSED":
            _err(errors, "L11-PTD-004", f"{path}.closure_status", "required field must close")
        if row.get("p0_relevant") and row.get("closure_status") not in {"CLOSED", "PROVEN_NOT_AVAILABLE"}:
            _err(errors, "L11-PTD-005", f"{path}.closure_status", "P0-relevant optional field must resolve or be proven unavailable")
        _refs(row.get("evidence_source_ids", []), set(source_index), f"{path}.evidence_source_ids", errors, nonempty=True)
        if field is not None and row.get("closure_status") == "CLOSED" and not (
            field.get("status") == "RESOLVED"
            and field.get("exists") is True
            and field.get("applicable") is True
        ):
            _err(errors, "L11-PTD-009", path, "CLOSED field must map to a RESOLVED, existing, applicable Field Resolution")
        if field is not None and row.get("closure_status") == "PROVEN_NOT_AVAILABLE" and not (
            field.get("status") == "NOT_AVAILABLE"
            and field.get("exists") is False
        ):
            _err(errors, "L11-PTD-010", path, "PROVEN_NOT_AVAILABLE must map to an unavailable Field Resolution")
        if field is not None and not any(
            source_can_prove_account_field(
                source_index.get(source_id, {}), scope, field.get("application_scope", {})
            )
            for source_id in row.get("evidence_source_ids", [])
        ):
            _err(errors, "L11-PTD-011", f"{path}.evidence_source_ids", "field closure needs applicable USABLE Seller Central evidence")
    _refs(ptd.get("rule_snapshot_ids", []), set(rule_index), "ptd_field_inventory.rule_snapshot_ids", errors, nonempty=True)
    _refs(ptd.get("evidence_source_ids", []), set(source_index), "ptd_field_inventory.evidence_source_ids", errors, nonempty=True)
    screenshot_sources = [source_index.get(item, {}) for item in ptd.get("evidence_source_ids", [])]
    complete_capture = any(
        source_can_prove_account_field(
            row,
            scope,
            {
                "parent_asins": list(scope.get("parent_asins", [])),
                "child_asins": list(scope.get("intended_child_asins", [])),
                "packs": list(scope.get("packs", [])),
                "colors": list(scope.get("colors", [])),
                "sizes": list(scope.get("sizes", [])),
            },
            require_complete_capture=True,
        )
        for row in screenshot_sources
    )
    if ptd.get("status") == "COMPLETE":
        inventoried_field_ids = {row.get("field_resolution_id") for row in expected_fields}
        if inventoried_field_ids != set(field_index) or len(inventoried_field_ids) != len(expected_fields):
            _err(errors, "L11-PTD-016", "ptd_field_inventory.expected_fields", "COMPLETE inventory must enumerate every Field Resolution exactly once")
        if ptd.get("declared_field_count") != len(expected_fields) or not complete_capture:
            _err(errors, "L11-PTD-006", "ptd_field_inventory", "COMPLETE requires full captured inventory and exact declared count")
        if ptd.get("checksum") != _hash_without(ptd, "checksum"):
            _err(errors, "L11-PTD-007", "ptd_field_inventory.checksum", "checksum mismatch")
    ptd_errors = any("[L11-PTD-" in item for item in errors)
    gates["ptd"] = evaluate_ptd(ptd.get("status"), expected_fields, complete_capture, ptd_errors)

    return PtdReport(
        delta=PhaseDelta.capture(errors, warnings, counts, gates),
        inventory=ptd,
        expected_fields=tuple(expected_fields),
    )
