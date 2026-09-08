#!/usr/bin/env python3
"""Pure enriched-content handoff and lineage phase for Listing Bundle v1.1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from listing_v11_domains import evaluate_handoff
from listing_v11_lineage import (
    canonical_handoff_hash,
    canonical_handoff_snapshot_id,
    validate_lineage_registry,
)
from listing_v11_phase import (
    HANDOFF_KEYS,
    HANDOFF_MAXIMUM_OUTPUTS,
    HANDOFF_STATUSES,
    PhaseDelta,
    _err,
    _hash_without,
    _nonempty,
    _scope_covers_variant,
    _warn,
    canonical_sha256,
)


@dataclass(frozen=True)
class HandoffReport:
    delta: PhaseDelta
    handoff: dict[str, Any]
    status: Any
    coordinator_required: bool


def validate_handoff_lineage_domain(
    bundle: dict[str, Any],
    *,
    project: dict[str, Any],
    scope: dict[str, Any],
    catalog_context: dict[str, Any],
    discovery_closure: dict[str, Any],
    ptd: dict[str, Any],
    denominator: dict[str, Any],
    requirement_rows: list[dict[str, Any]],
    requirement_index: dict[str, dict[str, Any]],
    atoms: list[dict[str, Any]],
    atom_index: dict[str, dict[str, Any]],
    delegated_requirement_ids: set[str],
    delegated_atom_ids: set[str],
    fact_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
    assertion_rows: list[dict[str, Any]],
    assertion_index: dict[str, dict[str, Any]],
    variant_rows: list[dict[str, Any]],
    variant_index: dict[str, dict[str, Any]],
    conflict_rows: list[dict[str, Any]],
    parent_bundle_hash: str,
) -> HandoffReport:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    gates: dict[str, str] = {}
    context = catalog_context
    closure = discovery_closure

    def canonical_parent_hash(_bundle: dict[str, Any]) -> str:
        return parent_bundle_hash
    handoff = bundle.get("enriched_content_handoff") if isinstance(bundle.get("enriched_content_handoff"), dict) else {}
    if set(handoff) != HANDOFF_KEYS:
        _err(errors, "L11-HANDOFF-001", "enriched_content_handoff", f"must contain exactly {sorted(HANDOFF_KEYS)}")
    status = handoff.get("status")
    if handoff.get("contract_version") != "1.1" or status not in HANDOFF_STATUSES:
        _err(errors, "L11-HANDOFF-002", "enriched_content_handoff", "requires contract 1.1 and a closed status")
    if handoff.get("maximum_output") not in HANDOFF_MAXIMUM_OUTPUTS:
        _err(errors, "L11-HANDOFF-028", "enriched_content_handoff.maximum_output", "unsupported current-contract maximum output")
    for lineage_code, lineage_message in validate_lineage_registry(handoff, HANDOFF_KEYS):
        _err(
            errors,
            "L11-HANDOFF-027",
            f"enriched_content_handoff.lineage_registry[{lineage_code}]",
            lineage_message,
        )
    if status == "NOT_APPLICABLE" and (
        delegated_requirement_ids
        or handoff.get("requested_content_types")
        or handoff.get("decision_requirements")
        or handoff.get("requirement_atoms")
    ):
        _err(
            errors,
            "L11-HANDOFF-022",
            "enriched_content_handoff.status",
            "NOT_APPLICABLE cannot waive an enriched-content delegation",
        )
    if status in {"FROZEN", "RESULT_RECEIVED", "RECONCILIATION_REQUIRED", "SUPERSEDED"}:
        for key in ("snapshot_id", "parent_project_id", "marketplace", "locale", "product_type", "created_at", "owner"):
            if not _nonempty(handoff.get(key)):
                _err(errors, "L11-HANDOFF-003", f"enriched_content_handoff.{key}", "is required")
        if handoff.get("parent_project_id") != project.get("project_id"):
            _err(errors, "L11-HANDOFF-004", "enriched_content_handoff.parent_project_id", "parent mismatch")
        if handoff.get("discovery_closure_hash") != canonical_sha256(closure):
            _err(errors, "L11-HANDOFF-005", "enriched_content_handoff.discovery_closure_hash", "discovery closure hash mismatch")
        if handoff.get("ptd_inventory_hash") != _hash_without(ptd, "checksum"):
            _err(errors, "L11-HANDOFF-006", "enriched_content_handoff.ptd_inventory_hash", "PTD inventory hash mismatch")
        if handoff.get("decision_denominator_hash") != _hash_without(denominator, "checksum"):
            _err(errors, "L11-HANDOFF-007", "enriched_content_handoff.decision_denominator_hash", "denominator hash mismatch")
        handoff_requirements = handoff.get("decision_requirements")
        expected_handoff_requirements = [row for row in requirement_rows if row.get("id") in delegated_requirement_ids]
        if handoff_requirements != expected_handoff_requirements:
            _err(errors, "L11-HANDOFF-012", "enriched_content_handoff.decision_requirements", "must exactly carry only delegated enriched-content requirements")
        expected_delegated_atoms = [row for row in atoms if row.get("requirement_id") in delegated_requirement_ids]
        if handoff.get("requirement_atoms") != expected_delegated_atoms:
            _err(errors, "L11-HANDOFF-009", "enriched_content_handoff.requirement_atoms", "must carry the exact delegated subset of the frozen parent atoms")
        delegated_variant_ids = {row.get("variant_row_id") for row in expected_delegated_atoms}
        expected_fact_ids = {
            fact_id for requirement_id in delegated_requirement_ids
            for fact_id in requirement_index.get(requirement_id, {}).get("fact_ids", [])
        }
        expected_claim_ids = {
            claim_id for requirement_id in delegated_requirement_ids
            for claim_id in requirement_index.get(requirement_id, {}).get("claim_ids", [])
        }
        expected_source_ids = {
            source_id
            for fact_id in expected_fact_ids
            for source_id in fact_index.get(fact_id, {}).get("proving_source_ids", [])
        } | {
            source_id
            for claim_id in expected_claim_ids
            for source_id in claim_index.get(claim_id, {}).get("proving_source_ids", [])
        }
        if set(handoff.get("fact_ids", [])) != expected_fact_ids or set(handoff.get("claim_ids", [])) != expected_claim_ids:
            _err(errors, "L11-HANDOFF-015", "enriched_content_handoff", "fact/claim IDs must exactly bind delegated requirements")
        if set(handoff.get("source_ids", [])) != expected_source_ids:
            _err(errors, "L11-HANDOFF-016", "enriched_content_handoff.source_ids", "must exactly carry delegated proving sources")
        expected_assertion_ids = {
            assertion_id
            for assertion_id, assertion in assertion_index.items()
            if assertion.get("status") == "FINAL"
            and any(
                variant_id in delegated_variant_ids
                and _scope_covers_variant(assertion.get("application_scope"), variant_index.get(variant_id, {}))
                and set(assertion.get("fact_ids", [])) == set(requirement_index.get(atom.get("requirement_id"), {}).get("fact_ids", []))
                and set(assertion.get("claim_ids", [])) == set(requirement_index.get(atom.get("requirement_id"), {}).get("claim_ids", []))
                for atom in expected_delegated_atoms
                for variant_id in [atom.get("variant_row_id")]
            )
        }
        if set(handoff.get("canonical_assertion_ids", [])) != expected_assertion_ids:
            _err(errors, "L11-HANDOFF-008", "enriched_content_handoff.canonical_assertion_ids", "must exactly carry assertions for delegated atoms")
        if set(handoff.get("variant_row_ids", [])) != delegated_variant_ids:
            _err(errors, "L11-HANDOFF-013", "enriched_content_handoff.variant_row_ids", "must exactly carry delegated variant rows")
        delegated_variants = [variant_index.get(item, {}) for item in delegated_variant_ids]
        expected_scope = {
            "parent_asins": sorted({str(row.get("parent_asin")) for row in delegated_variants if _nonempty(row.get("parent_asin"))}),
            "child_asins": sorted({str(row.get("child_asin")) for row in delegated_variants if _nonempty(row.get("child_asin"))}),
            "packs": sorted({str(row.get("pack")) for row in delegated_variants if _nonempty(row.get("pack"))}),
            "colors": sorted({str(row.get("color")) for row in delegated_variants if _nonempty(row.get("color"))}),
            "sizes": sorted({str(row.get("size")) for row in delegated_variants if _nonempty(row.get("size"))}),
        }
        if handoff.get("application_scope") != expected_scope:
            _err(errors, "L11-HANDOFF-017", "enriched_content_handoff.application_scope", "must exactly equal delegated variant scope")
        relevant_conflicts = {
            conflict.get("id") for conflict in conflict_rows
            if (set(conflict.get("affected_fact_ids", [])) & expected_fact_ids or set(conflict.get("affected_claim_ids", [])) & expected_claim_ids)
            and conflict.get("status") in {"OPEN", "EVIDENCE_REQUESTED", "BLOCKED"}
        }
        if relevant_conflicts:
            _err(errors, "L11-HANDOFF-018", "enriched_content_handoff.conflict_ids", f"cannot freeze unresolved delegated conflicts {sorted(relevant_conflicts)}")
        if handoff.get("blocked_claim_ids"):
            _err(errors, "L11-HANDOFF-019", "enriched_content_handoff.blocked_claim_ids", "active frozen handoff cannot include blocked claims")
        if not handoff.get("requested_content_types"):
            _err(errors, "L11-HANDOFF-020", "enriched_content_handoff.requested_content_types", "active handoff must request A+ content")
        mandatory_actions = {"modify_parent_truth", "expand_application_scope", "online_submission"}
        if not mandatory_actions.issubset(set(handoff.get("prohibited_actions", []))):
            _err(errors, "L11-HANDOFF-021", "enriched_content_handoff.prohibited_actions", "mandatory parent protections are missing")
        if not expected_delegated_atoms:
            _err(errors, "L11-HANDOFF-014", "enriched_content_handoff.requirement_atoms", "active A+ handoff requires at least one delegated atom")
        revision = handoff.get("semantic_revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            _err(errors, "L11-HANDOFF-023", "enriched_content_handoff.semantic_revision", "must be a positive integer")
        elif revision == 1 and (handoff.get("predecessor_snapshot_id") or handoff.get("refreeze_reason")):
            _err(errors, "L11-HANDOFF-024", "enriched_content_handoff", "initial snapshot cannot claim a predecessor/refreeze")
        elif revision > 1 and (
            not _nonempty(handoff.get("predecessor_snapshot_id"))
            or handoff.get("predecessor_snapshot_id") == handoff.get("snapshot_id")
            or not re.fullmatch(r"HO-[0-9a-f]{20}", str(handoff.get("predecessor_snapshot_id", "")))
            or not _nonempty(handoff.get("refreeze_reason"))
        ):
            _err(errors, "L11-HANDOFF-025", "enriched_content_handoff", "semantic refreeze needs an immutable predecessor and reason")
        expected_snapshot_id = canonical_handoff_snapshot_id(handoff)
        if handoff.get("snapshot_id") != expected_snapshot_id:
            _err(errors, "L11-HANDOFF-026", "enriched_content_handoff.snapshot_id", f"semantic snapshot must be content-addressed as {expected_snapshot_id}")
        if handoff.get("checksum") != canonical_handoff_hash(handoff):
            _err(errors, "L11-HANDOFF-010", "enriched_content_handoff.checksum", "checksum mismatch")
        if handoff.get("parent_bundle_sha256") != canonical_parent_hash(bundle):
            _err(errors, "L11-HANDOFF-011", "enriched_content_handoff.parent_bundle_sha256", "parent bundle hash mismatch")
    gates["handoff"], aplus_needs_coordinator = evaluate_handoff(
        str(status), any("[L11-HANDOFF-" in item for item in errors), handoff.get("requested_content_types", [])
    )
    if status == "RESULT_RECEIVED":
        _warn(warnings, "L11-HANDOFF-W01", "enriched_content_handoff.status", "RESULT_RECEIVED needs the package coordinator; parent-only validation cannot establish whole-page PASS")

    return HandoffReport(
        delta=PhaseDelta.capture(errors, warnings, counts, gates),
        handoff=handoff,
        status=status,
        coordinator_required=aplus_needs_coordinator,
    )
