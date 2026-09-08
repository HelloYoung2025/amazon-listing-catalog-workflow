#!/usr/bin/env python3
"""Pure-standard-library validator for Amazon Listing Bundle v1.1.

This module validates the parent Listing contract only.  It intentionally does
not import or execute the A+ validator; cross-bundle validation belongs to the
package coordinator.  The validator proves contract consistency, never product
truth, current Amazon policy, account authority, or live publication.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from listing_v11_decision_coverage_domain import (
    validate_decision_coverage,
    validate_decision_freeze,
)
from listing_v11_discovery_domain import validate_discovery_domain
from listing_v11_domains import derive_stage
from listing_v11_evidence_domain import validate_evidence_domain
from listing_v11_handoff_lineage_domain import validate_handoff_lineage_domain
from listing_v11_lineage import (
    canonical_handoff_hash as _lineage_handoff_hash,
    canonical_handoff_snapshot_id as _lineage_snapshot_id,
)
from listing_v11_security import unicode_issues
from listing_v11_ptd_domain import validate_ptd_domain
from listing_v11_publication_readback_domain import validate_publication_readback_domain
from listing_v11_phase import (
    CONCLUSIONS,
    EXECUTION_BOUNDARIES,
    MODES,
    PhaseDelta,
    ROOT_KEYS,
    SCHEMA_VERSION,
    TARGET_STAGES,
    _err,
    _find_forbidden_keys,
    _nonempty,
    _string_list,
    _unique_strings,
    canonical_sha256,
)
from listing_publication_contract import validate_publication as validate_publication_strict


def canonical_parent_hash(bundle: dict[str, Any]) -> str:
    """Hash the immutable upstream payload bound into an A+ handoff.

    Downstream lifecycle/result/publication/readback fields are deliberately
    excluded, so progressing a frozen package cannot invalidate its own input.
    Execution authority, product meaning, scope, evidence, PTD, decisions, the parent's local answer
    units/candidates, assertions, surfaces, and immutable handoff content remain
    included and therefore fail closed.  Publication authority is validated by
    its own exact contract; changing it must not rewrite the content snapshot.
    """
    handoff = copy.deepcopy(bundle.get("enriched_content_handoff"))
    if not isinstance(handoff, dict):
        handoff = {}
    if handoff.get("status") in {
        "FROZEN", "RESULT_RECEIVED", "RECONCILIATION_REQUIRED", "SUPERSEDED",
    }:
        handoff["status"] = "FROZEN"
    handoff["parent_bundle_sha256"] = ""
    handoff["checksum"] = ""
    projection = {
        "schema_version": bundle.get("schema_version"),
        "execution_boundary": bundle.get("execution_boundary"),
        "scope": copy.deepcopy(bundle.get("scope")),
        "catalog_context": copy.deepcopy(bundle.get("catalog_context")),
        "rule_snapshots": copy.deepcopy(bundle.get("rule_snapshots")),
        "field_resolutions": copy.deepcopy(bundle.get("field_resolutions")),
        "sources": copy.deepcopy(bundle.get("sources")),
        "facts": copy.deepcopy(bundle.get("facts")),
        "claims": copy.deepcopy(bundle.get("claims")),
        "conflicts": copy.deepcopy(bundle.get("conflicts")),
        "variant_topology": copy.deepcopy(bundle.get("variant_topology")),
        "method_registry": copy.deepcopy(bundle.get("method_registry")),
        "discovery": copy.deepcopy(bundle.get("discovery")),
        "market_research": copy.deepcopy(bundle.get("market_research")),
        "ptd_field_inventory": copy.deepcopy(bundle.get("ptd_field_inventory")),
        "decision_map": copy.deepcopy(bundle.get("decision_map")),
        "decision_denominator_snapshot": copy.deepcopy(bundle.get("decision_denominator_snapshot")),
        "canonical_assertions": copy.deepcopy(bundle.get("canonical_assertions")),
        "decision_answer_units": copy.deepcopy(bundle.get("decision_answer_units")),
        "surface_assignments": copy.deepcopy(bundle.get("surface_assignments")),
        "field_candidates": copy.deepcopy(bundle.get("field_candidates")),
        "semantic_consistency_matrix": copy.deepcopy(bundle.get("semantic_consistency_matrix")),
        "category_adapter": copy.deepcopy(bundle.get("category_adapter")),
        "enriched_content_handoff": handoff,
    }
    return canonical_sha256(projection)


def canonical_handoff_hash(handoff: dict[str, Any]) -> str:
    return _lineage_handoff_hash(handoff)


def canonical_handoff_snapshot_id(handoff: dict[str, Any]) -> str:
    """Content-address the immutable handoff so semantic refreezes need a new ID."""
    return _lineage_snapshot_id(handoff)


def _merge_phase(
    delta: PhaseDelta,
    errors: list[str],
    warnings: list[str],
    counts: dict[str, int],
    gates: dict[str, str],
) -> None:
    """Merge one pure domain result without changing legacy ordering."""
    errors.extend(delta.errors)
    warnings.extend(delta.warnings)
    for key, value in delta.counts:
        counts[key] = value
    for key, value in delta.gates:
        gates[key] = value


def validate_listing_bundle_v11(
    bundle: Any,
    aplus_result: Any | None = None,
    *,
    template_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    gates = {
        key: "NOT_RUN" for key in (
            "identity", "rules", "evidence", "truth", "discovery", "decision",
            "market_research", "ptd", "surfaces", "candidates", "handoff", "package",
            "publication", "backend", "live",
        )
    }

    if not isinstance(bundle, dict):
        return {
            "ok": False, "schema_valid": False,
            "errors": ["[L11-STRUCT-000] $: bundle must be an object"],
            "warnings": [], "counts": {}, "derived_gates": gates,
            "derived_stage": "AUTHORITY",
        }
    if bundle.get("schema_version") != SCHEMA_VERSION:
        _err(errors, "L11-VERSION-001", "schema_version", f"must equal {SCHEMA_VERSION}")
    for path, reason in unicode_issues(bundle):
        _err(errors, "L11-UNICODE-001", path, reason)
    missing = ROOT_KEYS - set(bundle)
    extra = set(bundle) - ROOT_KEYS
    if missing:
        _err(errors, "L11-ROOT-001", "$", f"missing keys: {sorted(missing)}")
    if extra:
        _err(errors, "L11-ROOT-002", "$", f"unknown keys: {sorted(extra)}")

    project = bundle.get("project") if isinstance(bundle.get("project"), dict) else {}
    if not project:
        _err(errors, "L11-STRUCT-003", "project", "must be an object")
    if project.get("status") == "SCAFFOLD":
        if bundle.get("execution_boundary") != "read_only":
            _err(errors, "L11-AUTH-001", "execution_boundary", "SCAFFOLD must remain read_only")
        if project.get("conclusion") != "NO_VALID_CONCLUSION":
            _err(errors, "L11-PROJECT-001", "project.conclusion", "SCAFFOLD cannot claim a conclusion")
        path = template_path or Path(__file__).resolve().parent.parent / "assets" / "listing-project-bundle-template.json"
        try:
            pristine = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _err(errors, "L11-SCAFFOLD-001", "$", f"cannot read pristine scaffold: {exc}")
        else:
            if bundle != pristine:
                _err(errors, "LST-SCAFFOLD-002", "$", "SCAFFOLD must remain semantically pristine")
        if aplus_result is not None:
            _err(errors, "LST-SCAFFOLD-003", "aplus_result", "SCAFFOLD cannot carry an A+ result")
        structural_prefixes = ("[L11-STRUCT-", "[L11-ROOT-", "[L11-VERSION-", "[L11-SCAFFOLD-", "[LST-SCAFFOLD-")
        schema_valid = not any(item.startswith(structural_prefixes) for item in errors)
        return {
            "ok": not errors, "schema_valid": schema_valid, "errors": errors,
            "warnings": warnings, "counts": counts, "derived_gates": gates,
            "derived_stage": "AUTHORITY", "parent_bundle_sha256": canonical_parent_hash(bundle),
            "contract_status": "CURRENT_SCAFFOLD",
        }

    if aplus_result is not None:
        _err(errors, "L11-XBUNDLE-001", "aplus_result", "v1.1 cross-bundle validation requires validate_listing_package.py")

    boundary = bundle.get("execution_boundary")
    if boundary not in EXECUTION_BOUNDARIES:
        _err(errors, "L11-AUTH-002", "execution_boundary", "unsupported execution boundary")
    if project.get("mode") not in MODES:
        _err(errors, "L11-PROJECT-002", "project.mode", "unsupported mode")
    if project.get("conclusion") not in CONCLUSIONS:
        _err(errors, "L11-PROJECT-003", "project.conclusion", "unsupported conclusion")
    if project.get("target_stage") not in TARGET_STAGES:
        _err(errors, "L11-PROJECT-004", "project.target_stage", "unsupported target stage")
    if not _nonempty(project.get("project_id")) or not _nonempty(project.get("snapshot_date")):
        _err(errors, "L11-PROJECT-005", "project", "project_id and snapshot_date are required")
    for hit in _find_forbidden_keys(bundle):
        _err(errors, "L11-METHOD-001", hit, "fixed score, word, density, or wait threshold cannot be normative")

    scope = bundle.get("scope") if isinstance(bundle.get("scope"), dict) else {}
    if not scope:
        _err(errors, "L11-STRUCT-004", "scope", "must be an object")
    for key in ("marketplace", "locale", "seller_scope"):
        if not _nonempty(scope.get(key)):
            _err(errors, "L11-SCOPE-001", f"scope.{key}", "must be bound")
    for key in ("parent_asins", "intended_child_asins", "excluded_child_asins", "packs", "colors", "sizes"):
        if not _unique_strings(scope.get(key, [])):
            _err(errors, "L11-SCOPE-002", f"scope.{key}", "must be a unique string array")
    intended = set(scope.get("intended_child_asins", [])) if _string_list(scope.get("intended_child_asins", [])) else set()
    if not intended:
        _err(errors, "L11-SCOPE-003", "scope.intended_child_asins", "must bind at least one child")
    if intended & set(scope.get("excluded_child_asins", [])):
        _err(errors, "L11-SCOPE-004", "scope", "intended and excluded children overlap")

    evidence_report = validate_evidence_domain(
        bundle, project=project, scope=scope, intended=intended,
    )
    _merge_phase(evidence_report.delta, errors, warnings, counts, gates)
    context = evidence_report.catalog_context
    source_rows = list(evidence_report.source_rows)
    source_index = evidence_report.source_index
    rule_rows = list(evidence_report.rule_rows)
    rule_index = evidence_report.rule_index
    field_rows = list(evidence_report.field_rows)
    field_index = evidence_report.field_index
    fact_rows = list(evidence_report.fact_rows)
    fact_index = evidence_report.fact_index
    claim_rows = list(evidence_report.claim_rows)
    claim_index = evidence_report.claim_index
    conflict_rows = list(evidence_report.conflict_rows)
    conflict_index = evidence_report.conflict_index
    variant_rows = list(evidence_report.variant_rows)
    variant_index = evidence_report.variant_index

    discovery_report = validate_discovery_domain(
        bundle,
        project=project,
        scope=scope,
        source_rows=source_rows,
        source_index=source_index,
        fact_index=fact_index,
        claim_index=claim_index,
        conflict_index=conflict_index,
        evidence_gate=gates["evidence"],
    )
    _merge_phase(discovery_report.delta, errors, warnings, counts, gates)
    discovery = discovery_report.discovery
    closure = discovery_report.closure
    market = discovery_report.market_research

    decision_report = validate_decision_freeze(
        bundle,
        project=project,
        scope=scope,
        variant_rows=variant_rows,
        fact_index=fact_index,
        claim_index=claim_index,
        discovery_gate=gates["discovery"],
        market_research_gate=gates["market_research"],
    )
    _merge_phase(decision_report.delta, errors, warnings, counts, gates)
    requirements_container = decision_report.requirements_container
    requirement_rows = list(decision_report.requirement_rows)
    requirement_index = decision_report.requirement_index
    p0_requirements = list(decision_report.p0_requirements)
    denominator = decision_report.denominator
    atoms = list(decision_report.atoms)
    atom_index = decision_report.atom_index

    ptd_report = validate_ptd_domain(
        bundle,
        catalog_context=context,
        scope=scope,
        source_index=source_index,
        rule_index=rule_index,
        field_index=field_index,
    )
    _merge_phase(ptd_report.delta, errors, warnings, counts, gates)
    ptd = ptd_report.inventory
    expected_fields = list(ptd_report.expected_fields)

    coverage_report = validate_decision_coverage(
        bundle,
        scope=scope,
        source_index=source_index,
        field_index=field_index,
        fact_index=fact_index,
        claim_index=claim_index,
        conflict_rows=conflict_rows,
        variant_index=variant_index,
        requirement_rows=requirement_rows,
        requirement_index=requirement_index,
        p0_requirements=p0_requirements,
        atom_index=atom_index,
        current_gates=gates,
    )
    _merge_phase(coverage_report.delta, errors, warnings, counts, gates)
    assertion_rows = list(coverage_report.assertion_rows)
    assertion_index = coverage_report.assertion_index
    assignment_rows = list(coverage_report.assignment_rows)
    assignment_index = coverage_report.assignment_index
    delegated_requirement_ids = set(coverage_report.delegated_requirement_ids)
    delegated_atom_ids = set(coverage_report.delegated_atom_ids)
    early_delegated_atom_ids = set(coverage_report.early_delegated_atom_ids)
    candidate_rows = list(coverage_report.candidate_rows)
    candidate_index = coverage_report.candidate_index
    unit_rows = list(coverage_report.unit_rows)
    unit_index = coverage_report.unit_index
    matrix_rows = list(coverage_report.matrix_rows)
    matrix_index = coverage_report.matrix_index

    handoff_report = validate_handoff_lineage_domain(
        bundle,
        project=project,
        scope=scope,
        catalog_context=context,
        discovery_closure=closure,
        ptd=ptd,
        denominator=denominator,
        requirement_rows=requirement_rows,
        requirement_index=requirement_index,
        atoms=atoms,
        atom_index=atom_index,
        delegated_requirement_ids=delegated_requirement_ids,
        delegated_atom_ids=delegated_atom_ids,
        fact_index=fact_index,
        claim_index=claim_index,
        source_index=source_index,
        assertion_rows=assertion_rows,
        assertion_index=assertion_index,
        variant_rows=variant_rows,
        variant_index=variant_index,
        conflict_rows=conflict_rows,
        parent_bundle_hash=canonical_parent_hash(bundle),
    )
    _merge_phase(handoff_report.delta, errors, warnings, counts, gates)
    handoff = handoff_report.handoff
    status = handoff_report.status
    aplus_needs_coordinator = handoff_report.coordinator_required

    publication_report = validate_publication_readback_domain(
        bundle,
        boundary=boundary,
        project=project,
        source_index=source_index,
        field_index=field_index,
        fact_index=fact_index,
        claim_index=claim_index,
        strict_validator=validate_publication_strict,
    )
    _merge_phase(publication_report.delta, errors, warnings, counts, gates)

    package_dependencies = ("identity", "rules", "evidence", "truth", "discovery", "market_research", "decision", "ptd", "surfaces", "candidates", "handoff")
    gates["package"] = "PASS" if all(gates.get(key) == "PASS" for key in package_dependencies) and not aplus_needs_coordinator and not errors else "BLOCKED"
    if project.get("conclusion") == "PASS" and gates["package"] != "PASS":
        _err(errors, "L11-PROJECT-006", "project.conclusion", "PASS cannot outrun the machine-derived package gate")
    structural_prefixes = ("[L11-STRUCT-", "[L11-ROOT-", "[L11-VERSION-", "[L11-SCAFFOLD-")
    schema_valid = not any(item.startswith(structural_prefixes) for item in errors)
    stage = derive_stage(gates)
    if project.get("target_stage") in TARGET_STAGES and TARGET_STAGES.index(stage) < TARGET_STAGES.index(project["target_stage"]):
        _err(errors, "L11-STAGE-001", "project.target_stage", f"target outruns derived stage {stage}")
    return {
        "ok": not errors,
        "schema_valid": schema_valid,
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "derived_gates": gates,
        "derived_stage": stage,
        "parent_bundle_sha256": canonical_parent_hash(bundle),
        "contract_status": "CURRENT_LOCAL_CONTRACT",
    }
