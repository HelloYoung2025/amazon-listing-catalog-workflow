#!/usr/bin/env python3
"""Pure Decision Freeze and whole-page Coverage phases for Listing Bundle v1.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from listing_v11_domains import expected_requirement_atom_tuples
from listing_v11_evidence import proving_sources_cover, scope_covers
from listing_v11_field_contract import p0_field_contract_allows
from listing_v11_phase import (
    CATEGORY_ADAPTER_KEYS,
    DECISION_MAP_KEYS,
    DECISION_REQUIREMENT_BASE_KEYS,
    DECISION_REQUIREMENT_DELEGATED_KEYS,
    DISALLOWED_P0_CARRIERS,
    EXPERIMENT_KEYS,
    GATE_REVIEW_KEYS,
    LEGAL_P0_CARRIERS,
    PhaseDelta,
    SURFACES,
    TARGET_STAGES,
    _err,
    _hash_without,
    _index,
    _is_fake_subtitle,
    _isoish,
    _nonempty,
    _normalized_text,
    _obj_list,
    _refs,
    _scope_covers_variant,
    _unique_strings,
    _validate_app_scope,
)


@dataclass(frozen=True)
class DecisionFreezeReport:
    delta: PhaseDelta
    requirements_container: dict[str, Any]
    requirement_rows: tuple[dict[str, Any], ...]
    requirement_index: dict[str, dict[str, Any]]
    p0_requirements: tuple[dict[str, Any], ...]
    denominator: dict[str, Any]
    atoms: tuple[dict[str, Any], ...]
    atom_index: dict[str, dict[str, Any]]


def validate_decision_freeze(
    bundle: dict[str, Any],
    *,
    project: dict[str, Any],
    scope: dict[str, Any],
    variant_rows: list[dict[str, Any]],
    fact_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
    discovery_gate: str,
    market_research_gate: str,
) -> DecisionFreezeReport:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    gates: dict[str, str] = {
        "discovery": discovery_gate,
        "market_research": market_research_gate,
    }
    requirements_container = bundle.get("decision_map") if isinstance(bundle.get("decision_map"), dict) else {}
    if set(requirements_container) != DECISION_MAP_KEYS:
        _err(errors, "L11-DECISION-008", "decision_map", f"must contain exactly {sorted(DECISION_MAP_KEYS)}")
    if requirements_container.get("status") != "FROZEN":
        _err(errors, "L11-DECISION-004", "decision_map.status", "must be FROZEN before denominator freeze")
    requirement_rows = _obj_list(requirements_container.get("requirements"), "decision_map.requirements", errors)
    requirement_index = _index(requirement_rows, "decision_map.requirements", errors)
    counts["decision_requirements"] = len(requirement_index)
    for index, row in enumerate(requirement_rows):
        path = f"decision_map.requirements[{index}]"
        expected_requirement_keys = (
            DECISION_REQUIREMENT_DELEGATED_KEYS
            if row.get("assigned_surface") == "enriched_content"
            else DECISION_REQUIREMENT_BASE_KEYS
        )
        if set(row) != expected_requirement_keys:
            _err(errors, "L11-DECISION-009", path, f"must contain exactly {sorted(expected_requirement_keys)}")
        if not _nonempty(row.get("buyer_question")) or row.get("priority") not in {"P0", "P1", "P2"}:
            _err(errors, "L11-DECISION-001", path, "question and valid priority are required")
        if row.get("status") not in {"READY", "HOLD", "CONFLICT", "OMITTED_WITH_REASON"}:
            _err(errors, "L11-DECISION-011", f"{path}.status", "unsupported requirement status")
        if row.get("priority") == "P0" and row.get("status") != "READY":
            _err(errors, "L11-DECISION-010", f"{path}.status", "every frozen P0 question must be READY and remain in the denominator")
        if row.get("assigned_surface") not in SURFACES or not isinstance(row.get("early_disclosure_required"), bool) or not _nonempty(row.get("owner")):
            _err(errors, "L11-DECISION-012", path, "assigned surface, early-disclosure boolean, and owner are required")
        _validate_app_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        _refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors)
        _refs(row.get("claim_ids", []), set(claim_index), f"{path}.claim_ids", errors)
        if row.get("priority") == "P0" and not row.get("fact_ids") and not row.get("claim_ids"):
            _err(errors, "L11-DECISION-005", path, "P0 requirement needs a frozen Fact/Claim evidence chain")
        if row.get("assigned_surface") == "enriched_content":
            if row.get("native_answer_required") is not True:
                _err(errors, "L11-DECISION-002", f"{path}.native_answer_required", "delegated P0 requires a native A+ answer")
            if row.get("early_disclosure_required") not in {True, False}:
                _err(errors, "L11-DECISION-003", f"{path}.early_disclosure_required", "must be boolean")
            upstream_ref = row.get("upstream_primary_carrier_ref")
            if row.get("early_disclosure_required") is False and (not isinstance(upstream_ref, str) or upstream_ref):
                _err(errors, "L11-DECISION-013", f"{path}.upstream_primary_carrier_ref", "must be empty when early disclosure is not required")
    p0_requirements = [row for row in requirement_rows if row.get("priority") == "P0" and row.get("status") == "READY"]

    denominator = bundle.get("decision_denominator_snapshot") if isinstance(bundle.get("decision_denominator_snapshot"), dict) else {}
    atoms = _obj_list(denominator.get("atoms", []), "decision_denominator_snapshot.atoms", errors)
    atom_index = _index(atoms, "decision_denominator_snapshot.atoms", errors)
    expected_tuples = expected_requirement_atom_tuples(
        p0_requirements, variant_rows, str(scope.get("marketplace", "")), str(scope.get("locale", ""))
    )
    actual_tuples: set[tuple[Any, Any, Any, Any]] = set()
    for index, atom in enumerate(atoms):
        item = (atom.get("requirement_id"), atom.get("marketplace"), atom.get("locale"), atom.get("variant_row_id"))
        if item in actual_tuples:
            _err(errors, "L11-DENOM-001", f"decision_denominator_snapshot.atoms[{index}]", "duplicate requirement atom")
        actual_tuples.add(item)
    if denominator.get("status") == "FROZEN":
        if actual_tuples != expected_tuples:
            _err(errors, "L11-DENOM-002", "decision_denominator_snapshot.atoms", "must exactly equal P0 requirements x applicable real variant rows")
        if denominator.get("checksum") != _hash_without(denominator, "checksum"):
            _err(errors, "L11-DENOM-003", "decision_denominator_snapshot.checksum", "checksum mismatch")
    target_index = TARGET_STAGES.index(project.get("target_stage")) if project.get("target_stage") in TARGET_STAGES else 0
    if target_index >= TARGET_STAGES.index("DECISION_FROZEN") and not atoms:
        _err(errors, "L11-DENOM-004", "decision_denominator_snapshot.atoms", "P0 denominator must be greater than zero")
    gates["decision"] = "PASS" if (
        requirements_container.get("status") == "FROZEN"
        and gates["discovery"] == "PASS"
        and gates["market_research"] == "PASS"
        and denominator.get("status") == "FROZEN"
        and bool(atoms)
        and actual_tuples == expected_tuples
        and not any("[L11-DECISION-" in item for item in errors)
    ) else "BLOCKED"

    gates.pop("discovery", None)
    gates.pop("market_research", None)
    return DecisionFreezeReport(
        delta=PhaseDelta.capture(errors, warnings, counts, gates),
        requirements_container=requirements_container,
        requirement_rows=tuple(requirement_rows),
        requirement_index=requirement_index,
        p0_requirements=tuple(p0_requirements),
        denominator=denominator,
        atoms=tuple(atoms),
        atom_index=atom_index,
    )


@dataclass(frozen=True)
class CoverageReport:
    delta: PhaseDelta
    assertion_rows: tuple[dict[str, Any], ...]
    assertion_index: dict[str, dict[str, Any]]
    assignment_rows: tuple[dict[str, Any], ...]
    assignment_index: dict[str, dict[str, Any]]
    delegated_requirement_ids: frozenset[str]
    delegated_atom_ids: frozenset[str]
    early_delegated_atom_ids: frozenset[str]
    candidate_rows: tuple[dict[str, Any], ...]
    candidate_index: dict[str, dict[str, Any]]
    unit_rows: tuple[dict[str, Any], ...]
    unit_index: dict[str, dict[str, Any]]
    matrix_rows: tuple[dict[str, Any], ...]
    matrix_index: dict[str, dict[str, Any]]


def validate_decision_coverage(
    bundle: dict[str, Any],
    *,
    scope: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    field_index: dict[str, dict[str, Any]],
    fact_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
    conflict_rows: list[dict[str, Any]],
    variant_index: dict[str, dict[str, Any]],
    requirement_rows: list[dict[str, Any]],
    requirement_index: dict[str, dict[str, Any]],
    p0_requirements: list[dict[str, Any]],
    atom_index: dict[str, dict[str, Any]],
    current_gates: dict[str, str],
) -> CoverageReport:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    gates = dict(current_gates)
    if current_gates.get("discovery") != "PASS":
        premature_sections = {
            name: len([row for row in bundle.get(name, []) if isinstance(row, dict)])
            for name in (
                "canonical_assertions", "surface_assignments", "field_candidates", "decision_answer_units",
                "semantic_consistency_matrix",
            )
        }
        premature_sections = {name: count for name, count in premature_sections.items() if count}
        if premature_sections:
            _err(
                errors, "L11-PHASE-001", "discovery.stage_gates",
                f"consumer answer, field allocation, and copy sections require all five discovery stages; populated sections={premature_sections!r}",
            )
    assertion_rows = _obj_list(bundle.get("canonical_assertions"), "canonical_assertions", errors)
    assertion_index = _index(assertion_rows, "canonical_assertions", errors)
    for index, row in enumerate(assertion_rows):
        path = f"canonical_assertions[{index}]"
        if not _nonempty(row.get("statement")) or row.get("status") not in {"FINAL", "HOLD", "CONFLICT"}:
            _err(errors, "L11-ASSERT-001", path, "statement and closed status are required")
        _refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors, nonempty=True)
        _refs(row.get("claim_ids", []), set(claim_index), f"{path}.claim_ids", errors)
        _validate_app_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)

    for requirement in p0_requirements:
        requirement_scope = requirement.get("application_scope", {})
        for fact_id in requirement.get("fact_ids", []):
            fact = fact_index.get(fact_id, {})
            if (
                fact.get("verification_status") != "VERIFIED"
                or fact.get("content_status") != "PUBLISHABLE"
                or not scope_covers(fact.get("application_scope"), requirement_scope)
                or not proving_sources_cover(
                    fact.get("proving_source_ids", []), source_index, scope, fact.get("application_scope", {})
                )
            ):
                _err(errors, "L11-DECISION-006", f"requirement:{requirement.get('id')}.fact_ids", f"fact {fact_id} is not a fully scoped, strongly proven PUBLISHABLE fact")
        for claim_id in requirement.get("claim_ids", []):
            claim = claim_index.get(claim_id, {})
            if (
                claim.get("support_status") != "SUPPORTED"
                or claim.get("content_status") != "PUBLISHABLE"
                or not scope_covers(claim.get("application_scope"), requirement_scope)
                or not proving_sources_cover(
                    claim.get("proving_source_ids", []), source_index, scope, claim.get("application_scope", {})
                )
            ):
                _err(errors, "L11-DECISION-007", f"requirement:{requirement.get('id')}.claim_ids", f"claim {claim_id} is not a fully scoped, strongly proven PUBLISHABLE claim")
        matching_assertions = [
            assertion for assertion in assertion_rows
            if assertion.get("status") == "FINAL"
            and set(assertion.get("fact_ids", [])) == set(requirement.get("fact_ids", []))
            and set(assertion.get("claim_ids", [])) == set(requirement.get("claim_ids", []))
            and scope_covers(assertion.get("application_scope"), requirement.get("application_scope"))
        ]
        if not matching_assertions:
            _err(errors, "L11-ASSERT-002", f"requirement:{requirement.get('id')}", "P0 requirement needs a FINAL assertion with the exact Fact/Claim chain and full scope")
        for claim_id in requirement.get("claim_ids", []):
            if not set(claim_index.get(claim_id, {}).get("fact_ids", [])).issubset(set(requirement.get("fact_ids", []))):
                _err(errors, "L11-ASSERT-003", f"requirement:{requirement.get('id')}", f"claim {claim_id} depends on Facts outside the requirement chain")
    if any(token in item for item in errors for token in ("L11-DECISION-", "L11-ASSERT-")):
        gates["decision"] = "BLOCKED"

    assignment_rows = _obj_list(bundle.get("surface_assignments"), "surface_assignments", errors)
    assignment_index = _index(assignment_rows, "surface_assignments", errors)
    upstream_assignment_ids = {
        str(requirement.get("upstream_primary_carrier_ref"))
        for requirement in p0_requirements
        if requirement.get("assigned_surface") == "enriched_content"
        and requirement.get("early_disclosure_required") is True
        and _nonempty(requirement.get("upstream_primary_carrier_ref"))
    }
    for index, row in enumerate(assignment_rows):
        path = f"surface_assignments[{index}]"
        if row.get("requirement_id") not in requirement_index:
            _err(errors, "L11-SURFACE-001", f"{path}.requirement_id", "unknown requirement")
        requirement = requirement_index.get(row.get("requirement_id"), {})
        is_upstream = str(row.get("id")) in upstream_assignment_ids
        if requirement and row.get("primary_surface") != requirement.get("assigned_surface") and not is_upstream:
            _err(errors, "L11-SURFACE-005", path, "assignment primary surface must exactly match the frozen requirement allocation")
        if requirement and row.get("application_scope") != requirement.get("application_scope"):
            _err(errors, "L11-SURFACE-009", f"{path}.application_scope", "assignment scope must exactly equal its frozen requirement scope")
        if row.get("primary_carrier_kind") in DISALLOWED_P0_CARRIERS and requirement_index.get(row.get("requirement_id"), {}).get("priority") == "P0":
            _err(errors, "L11-SURFACE-002", f"{path}.primary_carrier_kind", "cannot be the P0 primary carrier")
        if row.get("primary_carrier_kind") not in LEGAL_P0_CARRIERS | DISALLOWED_P0_CARRIERS | {"A_PLUS_NATIVE_PENDING"}:
            _err(errors, "L11-SURFACE-003", f"{path}.primary_carrier_kind", "unsupported carrier kind")
        if row.get("field_resolution_id") and row.get("field_resolution_id") not in field_index:
            _err(errors, "L11-SURFACE-004", f"{path}.field_resolution_id", "unknown field")
        field = field_index.get(row.get("field_resolution_id"), {})
        carrier = row.get("primary_carrier_kind")
        if carrier in LEGAL_P0_CARRIERS and not (
            field
            and field.get("status") == "RESOLVED"
            and field.get("exists") is True
            and field.get("editable") is True
            and field.get("applicable") is True
            and field.get("visibility") == "BUYER_VISIBLE"
            and field.get("surface") == row.get("primary_surface")
            and scope_covers(field.get("application_scope"), row.get("application_scope"))
            and p0_field_contract_allows(field, carrier)
        ):
            _err(errors, "L11-SURFACE-006", path, "P0 carrier requires an editable buyer-visible field whose canonical key, semantic role, surface, data plane, and carrier satisfy the closed contract")
        if carrier == "A_PLUS_NATIVE_PENDING" and (row.get("primary_surface") != "enriched_content" or row.get("field_resolution_id")):
            _err(errors, "L11-SURFACE-007", path, "A_PLUS_NATIVE_PENDING must use enriched_content and no parent field")
        if is_upstream and (
            carrier not in LEGAL_P0_CARRIERS
            or row.get("primary_surface") in {"media", "backend_search_terms", "enriched_content"}
            or row.get("status") != "PASS"
        ):
            _err(errors, "L11-SURFACE-010", path, "early disclosure must be a PASS legal native/structured carrier before enriched content")
        _validate_app_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
    for requirement in p0_requirements:
        upstream_ref = requirement.get("upstream_primary_carrier_ref") if requirement.get("assigned_surface") == "enriched_content" else ""
        passing_assignments = [
            row for row in assignment_rows
            if row.get("requirement_id") == requirement.get("id")
            and row.get("status") == "PASS"
            and row.get("id") != upstream_ref
        ]
        if len(passing_assignments) != 1:
            _err(errors, "L11-SURFACE-008", f"requirement:{requirement.get('id')}", "P0 requirement needs exactly one PASS primary assignment")
        if requirement.get("assigned_surface") == "enriched_content" and requirement.get("early_disclosure_required") is True:
            upstream = assignment_index.get(upstream_ref)
            if (
                not _nonempty(upstream_ref)
                or upstream is None
                or upstream.get("requirement_id") != requirement.get("id")
                or upstream.get("status") != "PASS"
                or upstream.get("primary_carrier_kind") not in LEGAL_P0_CARRIERS
                or upstream.get("primary_surface") in {"media", "backend_search_terms", "enriched_content"}
                or upstream.get("application_scope") != requirement.get("application_scope")
            ):
                _err(errors, "L11-SURFACE-011", f"requirement:{requirement.get('id')}", "early disclosure reference must bind one legal upstream PASS assignment with exact scope")
    gates["surfaces"] = "PASS" if assignment_rows and not any("[L11-SURFACE-" in item for item in errors) else "BLOCKED"
    delegated_requirement_ids = {
        requirement_id
        for requirement_id, requirement in requirement_index.items()
        if requirement.get("assigned_surface") == "enriched_content"
        and any(
            assignment.get("requirement_id") == requirement_id
            and assignment.get("primary_surface") == "enriched_content"
            and assignment.get("primary_carrier_kind") == "A_PLUS_NATIVE_PENDING"
            for assignment in assignment_rows
        )
    }
    handoff_for_delegation = bundle.get("enriched_content_handoff")
    handoff_status_for_delegation = (
        handoff_for_delegation.get("status")
        if isinstance(handoff_for_delegation, dict)
        else None
    )
    delegated_atom_ids = {
        atom_id for atom_id, atom in atom_index.items()
        if atom.get("requirement_id") in delegated_requirement_ids
    } if handoff_status_for_delegation in {"FROZEN", "RESULT_RECEIVED"} else set()
    early_delegated_atom_ids = {
        atom_id for atom_id in delegated_atom_ids
        if requirement_index.get(atom_index.get(atom_id, {}).get("requirement_id"), {}).get("early_disclosure_required") is True
    }

    candidate_rows = _obj_list(bundle.get("field_candidates"), "field_candidates", errors)
    candidate_index = _index(candidate_rows, "field_candidates", errors)
    counts["field_candidates"] = len(candidate_index)
    final_by_field_variant: dict[tuple[str, str], list[str]] = {}
    for index, row in enumerate(candidate_rows):
        path = f"field_candidates[{index}]"
        field = field_index.get(row.get("field_resolution_id"), {})
        if not field:
            _err(errors, "L11-CANDIDATE-001", f"{path}.field_resolution_id", "unknown field")
        elif row.get("semantic_role") != field.get("semantic_role"):
            _err(errors, "L11-CANDIDATE-008", f"{path}.semantic_role", "must exactly match the resolved field semantic role")
        if row.get("semantic_role") != field.get("semantic_role"):
            _err(errors, "L11-CANDIDATE-002", f"{path}.semantic_role", "must match resolved field")
        if _is_fake_subtitle(row.get("semantic_role")):
            _err(errors, "L11-CANDIDATE-003", path, "invented subtitle role is forbidden")
        if row.get("content_status") == "FINAL" and row.get("qa_status") != "PASS":
            _err(errors, "L11-CANDIDATE-004", f"{path}.qa_status", "FINAL candidate requires QA PASS")
        if not _nonempty(row.get("value")):
            _err(errors, "L11-CANDIDATE-005", f"{path}.value", "must not be empty")
        _validate_app_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        _refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors, nonempty=True)
        _refs(row.get("claim_ids", []), set(claim_index), f"{path}.claim_ids", errors)
        if field.get("semantic_role") == "ITEM_HIGHLIGHTS" and isinstance(field.get("max_characters"), int) and len(str(row.get("value", ""))) > field["max_characters"]:
            _err(errors, "L11-CANDIDATE-006", f"{path}.value", "exceeds resolved Item Highlights limit")
        if row.get("content_status") == "FINAL" and row.get("qa_status") == "PASS":
            if not (
                field.get("status") == "RESOLVED"
                and field.get("exists") is True
                and field.get("editable") is True
                and field.get("applicable") is True
            ):
                _err(errors, "L11-CANDIDATE-009", path, "FINAL candidate requires a RESOLVED, existing, editable, applicable field")
            for variant_id, variant in variant_index.items():
                if _scope_covers_variant(row.get("application_scope"), variant):
                    final_by_field_variant.setdefault((str(row.get("field_resolution_id")), variant_id), []).append(str(row.get("id")))
    for key, ids in final_by_field_variant.items():
        if len(ids) > 1:
            _err(errors, "L11-CANDIDATE-007", "field_candidates", f"multiple FINAL candidates for field/variant {key}: {ids}")

    unit_rows = _obj_list(bundle.get("decision_answer_units"), "decision_answer_units", errors)
    unit_index = _index(unit_rows, "decision_answer_units", errors)
    counts["decision_answer_units"] = len(unit_index)
    units_by_atom: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(unit_rows):
        path = f"decision_answer_units[{index}]"
        atom = atom_index.get(row.get("atom_id"), {})
        if not atom:
            _err(errors, "L11-ANSWER-001", f"{path}.atom_id", "unknown atom")
        elif row.get("requirement_id") != atom.get("requirement_id") or row.get("variant_row_id") != atom.get("variant_row_id"):
            _err(errors, "L11-ANSWER-002", path, "unit does not match atom tuple")
        units_by_atom.setdefault(str(row.get("atom_id")), []).append(row)
        candidate = candidate_index.get(row.get("field_candidate_id"), {})
        if not candidate or candidate.get("content_status") != "FINAL" or candidate.get("qa_status") != "PASS":
            _err(errors, "L11-ANSWER-003", f"{path}.field_candidate_id", "must bind a FINAL QA-PASS candidate")
        variant = variant_index.get(row.get("variant_row_id"), {})
        field = field_index.get(candidate.get("field_resolution_id"), {}) if candidate else {}
        if (
            not field
            or field.get("status") != "RESOLVED"
            or not field.get("exists")
            or not field.get("applicable")
            or (variant and not _scope_covers_variant(field.get("application_scope"), variant))
        ):
            _err(errors, "L11-ANSWER-009", f"{path}.field_candidate_id", "answer field must be RESOLVED, available, and cover the variant")
        if candidate and variant and not _scope_covers_variant(candidate.get("application_scope"), variant):
            _err(errors, "L11-ANSWER-004", f"{path}.field_candidate_id", "candidate does not cover variant")
        answer = _normalized_text(row.get("answer_text"))
        if not answer or answer not in _normalized_text(candidate.get("value")):
            _err(errors, "L11-ANSWER-005", f"{path}.answer_text", "exact answer text must occur in candidate")
        _refs(row.get("canonical_assertion_ids", []), set(assertion_index), f"{path}.canonical_assertion_ids", errors, nonempty=True)
        _refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors, nonempty=True)
        _refs(row.get("claim_ids", []), set(claim_index), f"{path}.claim_ids", errors)
        requirement = requirement_index.get(atom.get("requirement_id"), {}) if atom else {}
        if requirement.get("assigned_surface") == "enriched_content" and requirement.get("early_disclosure_required") is True:
            expected_answer_assignment = assignment_index.get(requirement.get("upstream_primary_carrier_ref"), {})
        else:
            passing_requirement_assignments = [
                assignment for assignment in assignment_rows
                if assignment.get("requirement_id") == row.get("requirement_id")
                and assignment.get("status") == "PASS"
                and assignment.get("id") != requirement.get("upstream_primary_carrier_ref")
            ]
            expected_answer_assignment = passing_requirement_assignments[0] if len(passing_requirement_assignments) == 1 else {}
        if (
            not expected_answer_assignment
            or candidate.get("field_resolution_id") != expected_answer_assignment.get("field_resolution_id")
        ):
            _err(errors, "L11-ANSWER-016", path, "answer candidate field must exactly equal its single PASS surface-assignment field")
        if (
            set(row.get("fact_ids", [])) != set(requirement.get("fact_ids", []))
            or set(row.get("claim_ids", [])) != set(requirement.get("claim_ids", []))
        ):
            _err(errors, "L11-ANSWER-014", path, "answer Fact/Claim refs must exactly equal its requirement evidence chain")
        if candidate:
            if set(row.get("fact_ids", [])) != set(candidate.get("fact_ids", [])) or set(row.get("claim_ids", [])) != set(candidate.get("claim_ids", [])):
                _err(errors, "L11-ANSWER-006", path, "candidate and answer must carry the same exact requirement evidence chain")
        for assertion_id in row.get("canonical_assertion_ids", []):
            assertion = assertion_index.get(assertion_id, {})
            if assertion.get("status") != "FINAL" or (variant and not _scope_covers_variant(assertion.get("application_scope"), variant)):
                _err(errors, "L11-ANSWER-007", f"{path}.canonical_assertion_ids", "assertion must be FINAL and cover variant")
            if set(assertion.get("fact_ids", [])) != set(row.get("fact_ids", [])) or set(assertion.get("claim_ids", [])) != set(row.get("claim_ids", [])):
                _err(errors, "L11-ANSWER-010", f"{path}.canonical_assertion_ids", "assertion and answer must share the exact closed requirement evidence chain")
            if _normalized_text(assertion.get("statement")) != answer:
                _err(errors, "L11-ANSWER-015", f"{path}.canonical_assertion_ids", "answer text must equal the canonical assertion statement")
        for fact_id in row.get("fact_ids", []):
            fact = fact_index.get(fact_id, {})
            if (
                fact.get("verification_status") != "VERIFIED"
                or fact.get("content_status") != "PUBLISHABLE"
                or not fact.get("proving_source_ids")
                or not proving_sources_cover(fact.get("proving_source_ids", []), source_index, scope, fact.get("application_scope", {}))
                or (variant and not _scope_covers_variant(fact.get("application_scope"), variant))
            ):
                _err(errors, "L11-ANSWER-011", f"{path}.fact_ids", f"fact {fact_id} is not strongly proven, publishable, and variant-scoped")
        for claim_id in row.get("claim_ids", []):
            claim = claim_index.get(claim_id, {})
            if (
                claim.get("support_status") != "SUPPORTED"
                or claim.get("content_status") != "PUBLISHABLE"
                or not claim.get("proving_source_ids")
                or not proving_sources_cover(claim.get("proving_source_ids", []), source_index, scope, claim.get("application_scope", {}))
                or (variant and not _scope_covers_variant(claim.get("application_scope"), variant))
            ):
                _err(errors, "L11-ANSWER-012", f"{path}.claim_ids", f"claim {claim_id} is not strongly proven, publishable, and variant-scoped")
        answer_evidence = set(row.get("fact_ids", [])) | set(row.get("claim_ids", []))
        for conflict in conflict_rows:
            affected = set(conflict.get("affected_fact_ids", [])) | set(conflict.get("affected_claim_ids", []))
            if answer_evidence & affected and conflict.get("status") in {"OPEN", "EVIDENCE_REQUESTED", "BLOCKED"}:
                _err(errors, "L11-ANSWER-013", path, f"answer evidence is affected by unresolved conflict {conflict.get('id')}")
    for atom_id in atom_index:
        if atom_id in delegated_atom_ids and atom_id not in early_delegated_atom_ids:
            continue
        passing = [row for row in units_by_atom.get(atom_id, []) if row.get("status") == "PASS"]
        if len(passing) != 1:
            _err(errors, "L11-ANSWER-008", f"atom:{atom_id}", "each P0 atom requires exactly one PASS answer unit")
    counts["p0_atoms"] = len(atom_index)
    counts["p0_pass"] = sum(1 for atom_id in atom_index if len([row for row in units_by_atom.get(atom_id, []) if row.get("status") == "PASS"]) == 1)
    counts["p0_delegated"] = len(delegated_atom_ids)

    matrix_rows = _obj_list(bundle.get("semantic_consistency_matrix"), "semantic_consistency_matrix", errors)
    matrix_index = _index(matrix_rows, "semantic_consistency_matrix", errors)
    matrix_candidate_ids: set[str] = set()
    matrix_bindings: set[tuple[str, str]] = set()
    for index, row in enumerate(matrix_rows):
        path = f"semantic_consistency_matrix[{index}]"
        if row.get("canonical_assertion_id") not in assertion_index:
            _err(errors, "L11-SEMANTIC-001", f"{path}.canonical_assertion_id", "unknown assertion")
        _refs(row.get("field_candidate_ids", []), set(candidate_index), f"{path}.field_candidate_ids", errors, nonempty=True)
        matrix_candidate_ids.update(row.get("field_candidate_ids", []))
        assertion = assertion_index.get(row.get("canonical_assertion_id"), {})
        for candidate_id in row.get("field_candidate_ids", []):
            candidate = candidate_index.get(candidate_id, {})
            matrix_bindings.add((str(row.get("canonical_assertion_id")), str(candidate_id)))
            if (
                set(assertion.get("fact_ids", [])) != set(candidate.get("fact_ids", []))
                or set(assertion.get("claim_ids", [])) != set(candidate.get("claim_ids", []))
                or _normalized_text(assertion.get("statement")) not in _normalized_text(candidate.get("value"))
            ):
                _err(errors, "L11-SEMANTIC-004", path, "matrix assertion and candidate must share the exact evidence chain and answer text")
        if row.get("status") != "PASS":
            _err(errors, "L11-SEMANTIC-002", f"{path}.status", "final matrix rows must PASS")
    used_candidate_ids = {row.get("field_candidate_id") for row in unit_rows if row.get("status") == "PASS"}
    if not used_candidate_ids.issubset(matrix_candidate_ids):
        _err(errors, "L11-SEMANTIC-003", "semantic_consistency_matrix", "every P0 candidate must be in the assertion matrix")
    for unit in unit_rows:
        if unit.get("status") != "PASS":
            continue
        candidate_id = str(unit.get("field_candidate_id"))
        if not any((str(assertion_id), candidate_id) in matrix_bindings for assertion_id in unit.get("canonical_assertion_ids", [])):
            _err(errors, "L11-SEMANTIC-005", f"answer:{unit.get('id')}", "P0 answer candidate must be matrix-bound to one of its own canonical assertions")

    candidate_errors = any(token in item for item in errors for token in ("L11-CANDIDATE-", "L11-ANSWER-", "L11-ASSERT-", "L11-SEMANTIC-"))
    locally_required_atoms = (set(atom_index) - delegated_atom_ids) | early_delegated_atom_ids
    local_atoms_have_units = all(
        len([row for row in units_by_atom.get(atom_id, []) if row.get("status") == "PASS"]) == 1
        for atom_id in locally_required_atoms
    )
    gates["candidates"] = "PASS" if atom_index and local_atoms_have_units and not candidate_errors else "BLOCKED"

    adapter = bundle.get("category_adapter") if isinstance(bundle.get("category_adapter"), dict) else {}
    if set(adapter) != CATEGORY_ADAPTER_KEYS:
        _err(errors, "L11-ADAPTER-004", "category_adapter", f"must contain exactly {sorted(CATEGORY_ADAPTER_KEYS)}")
    if adapter.get("name") not in {"generic", "apparel/fit", "connected-device", "home/kitchen", "regulated/beauty"}:
        _err(errors, "L11-ADAPTER-001", "category_adapter.name", "unsupported P1 adapter")
    if not _nonempty(adapter.get("version")):
        _err(errors, "L11-ADAPTER-006", "category_adapter.version", "is required")
    if "ptd_fields" in adapter or "field_overrides" in adapter:
        _err(errors, "L11-ADAPTER-002", "category_adapter", "adapter cannot define or override PTD fields")
    for key in ("question_prompts", "evidence_probes", "return_risks", "qa_checks"):
        if not _unique_strings(adapter.get(key, [])):
            _err(errors, "L11-ADAPTER-003", f"category_adapter.{key}", "must be a unique string array")
    if adapter.get("status") not in {"NOT_STARTED", "READY", "COMPLETE", "NOT_REQUIRED_WITH_REASON"}:
        _err(errors, "L11-ADAPTER-005", "category_adapter.status", "unsupported adapter status")
    if (
        adapter.get("name") != "generic"
        and adapter.get("status") in {"READY", "COMPLETE"}
        and any(not adapter.get(key) for key in ("question_prompts", "evidence_probes", "return_risks", "qa_checks"))
    ):
        _err(errors, "L11-ADAPTER-007", "category_adapter", "active specialized adapter must materialize prompts, evidence probes, return risks, and QA checks")

    experiment_rows = _obj_list(bundle.get("experiment_registry"), "experiment_registry", errors)
    _index(experiment_rows, "experiment_registry", errors)
    for index, row in enumerate(experiment_rows):
        path = f"experiment_registry[{index}]"
        if set(row) != EXPERIMENT_KEYS:
            _err(errors, "L11-EXPERIMENT-001", path, f"must contain exactly {sorted(EXPERIMENT_KEYS)}")
        if row.get("status") not in {"PLANNED", "RUNNING", "COMPLETE", "CANCELLED"}:
            _err(errors, "L11-EXPERIMENT-002", f"{path}.status", "unsupported experiment status")
        if not all(_nonempty(row.get(key)) for key in ("hypothesis", "metric", "owner")):
            _err(errors, "L11-EXPERIMENT-003", path, "hypothesis, metric, and owner are required")
        if row.get("status") in {"PLANNED", "RUNNING", "COMPLETE"} and not all(
            _nonempty(row.get(key)) for key in ("baseline_ref", "candidate_ref")
        ):
            _err(errors, "L11-EXPERIMENT-006", path, "active experiment needs explicit baseline and candidate references")
        if row.get("status") == "CANCELLED" and not _nonempty(row.get("decision")):
            _err(errors, "L11-EXPERIMENT-007", f"{path}.decision", "cancelled experiment needs a reason/decision")
        _validate_app_scope(row.get("application_scope"), f"{path}.application_scope", scope, errors)
        if row.get("status") in {"RUNNING", "COMPLETE"} and not _isoish(row.get("started_at")):
            _err(errors, "L11-EXPERIMENT-004", f"{path}.started_at", "RUNNING/COMPLETE needs a timestamp")
        if row.get("status") == "COMPLETE" and (not _isoish(row.get("ended_at")) or not _nonempty(row.get("decision"))):
            _err(errors, "L11-EXPERIMENT-005", path, "COMPLETE needs ended_at and a decision")

    gate_review_rows = _obj_list(bundle.get("gate_reviews"), "gate_reviews", errors)
    _index(gate_review_rows, "gate_reviews", errors)
    for index, row in enumerate(gate_review_rows):
        path = f"gate_reviews[{index}]"
        if set(row) != GATE_REVIEW_KEYS:
            _err(errors, "L11-GATE-001", path, f"must contain exactly {sorted(GATE_REVIEW_KEYS)}")
        if row.get("gate") not in gates or row.get("status") not in {"NOT_RUN", "PASS", "FAIL", "BLOCKED"}:
            _err(errors, "L11-GATE-002", path, "unknown gate or review status")
        if not _nonempty(row.get("reviewer")) or not _isoish(row.get("reviewed_at")):
            _err(errors, "L11-GATE-003", path, "reviewer and timestamp are required")
        _refs(row.get("evidence_source_ids", []), set(source_index), f"{path}.evidence_source_ids", errors)
        if not _unique_strings(row.get("blocker_ids", [])):
            _err(errors, "L11-GATE-004", f"{path}.blocker_ids", "must be a unique string array")
        if row.get("status") == "PASS" and (not row.get("evidence_source_ids") or row.get("blocker_ids")):
            _err(errors, "L11-GATE-005", path, "PASS review requires evidence and no blockers")
        if row.get("status") in {"FAIL", "BLOCKED"} and not row.get("blocker_ids"):
            _err(errors, "L11-GATE-006", path, "FAIL/BLOCKED review requires blocker IDs")

    if not isinstance(bundle.get("experiment_registry"), list) or not isinstance(bundle.get("gate_reviews"), list):
        _err(errors, "L11-STRUCT-006", "$", "experiment_registry and gate_reviews must be arrays")
    phase_gates = {
        "decision": gates["decision"],
        "surfaces": gates["surfaces"],
        "candidates": gates["candidates"],
    }
    return CoverageReport(
        delta=PhaseDelta.capture(errors, warnings, counts, phase_gates),
        assertion_rows=tuple(assertion_rows),
        assertion_index=assertion_index,
        assignment_rows=tuple(assignment_rows),
        assignment_index=assignment_index,
        delegated_requirement_ids=frozenset(delegated_requirement_ids),
        delegated_atom_ids=frozenset(delegated_atom_ids),
        early_delegated_atom_ids=frozenset(early_delegated_atom_ids),
        candidate_rows=tuple(candidate_rows),
        candidate_index=candidate_index,
        unit_rows=tuple(unit_rows),
        unit_index=unit_index,
        matrix_rows=tuple(matrix_rows),
        matrix_index=matrix_index,
    )
