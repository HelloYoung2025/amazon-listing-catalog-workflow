#!/usr/bin/env python3
"""Pure, deterministic semantic reports for the A+ Bundle v1.3 contract.

The entry validator owns JSON shape parsing and path presentation.  These
reports consume already-normalized local values, perform no I/O, never mutate
their inputs, and return all derived errors/state explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from aplus_v13_domain import (
    MIRROR_FORBIDDEN_SOLE_PROOF_CLASSES,
    MIRROR_SOURCE_TYPES,
    derive_coverage_result,
    derive_discovery_closure,
    validate_distillation_coverage,
    validate_evidence_pass,
    validate_handoff_shape,
)
from aplus_v13_lineage import canonical_handoff_hash


FINAL_CONTENT_STATUSES = {"FINAL_CANDIDATE", "APPROVED", "PUBLISHED"}
SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item.strip() for item in value if isinstance(item, str) and item.strip()}


@dataclass(frozen=True)
class EvidenceReport:
    errors: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveryReport:
    errors: tuple[str, ...]
    derived_closure: str


@dataclass(frozen=True)
class HandoffReport:
    errors: tuple[str, ...]


@dataclass(frozen=True)
class CoverageReport:
    errors: tuple[str, ...]
    counts: Mapping[str, Any]


def build_fact_evidence_report(
    *,
    schema_version: str,
    fact_id: str,
    fact_class: str,
    publish_status: str,
    proving_types: Iterable[str],
) -> EvidenceReport:
    """Report v1.3 proof-class restrictions without re-reading a source."""
    issues: list[str] = []
    path = f"$.facts[{fact_id}]"
    types = set(proving_types)
    if schema_version == "1.3" and publish_status == "PUBLISHABLE":
        if fact_class == "UNCLASSIFIED":
            issues.append(
                f"[A13-MIRROR-001] {path}.fact_class: publishable v1.3 fact cannot remain UNCLASSIFIED"
            )
        if (
            fact_class in MIRROR_FORBIDDEN_SOLE_PROOF_CLASSES
            and types
            and types.issubset(MIRROR_SOURCE_TYPES)
        ):
            issues.append(
                f"[A13-MIRROR-002] {path}.proving_source_ids: operational mirrors cannot solely prove {fact_class}"
            )
    return EvidenceReport(tuple(issues))


def build_discovery_report(
    *,
    workflow_mode: str,
    discovery_mode: str,
    evidence_pass: Mapping[str, Any],
    has_rounds: bool,
    question_map: Mapping[str, Mapping[str, Any]],
    action_map: Mapping[str, Mapping[str, Any]],
    distillations: Mapping[str, Mapping[str, Any]],
    declared_closure: str,
    closure_reason: str,
    decision_requirements: Mapping[str, Mapping[str, Any]],
    atom_map: Mapping[str, Mapping[str, Any]],
    source_map: Mapping[str, Mapping[str, Any]],
    source_scopes: Mapping[str, Mapping[str, Any]],
    fact_map: Mapping[str, Mapping[str, Any]],
    claim_map: Mapping[str, Mapping[str, Any]],
    variant_map: Mapping[str, Mapping[str, Any]],
    marketplace: str,
    locale: str,
) -> DiscoveryReport:
    """Derive standalone/parent-bound Discovery closure and semantic issues."""
    issues: list[str] = []
    evidence_pass_valid = True
    if workflow_mode == "standalone":
        evidence_pass_valid, evidence_issues = validate_evidence_pass(
            evidence_pass, source_map, source_scopes, atom_map, variant_map,
            marketplace, locale,
        )
        issues.extend(evidence_issues)

    distillations_valid, distillation_issues = validate_distillation_coverage(
        question_map, distillations, fact_map, claim_map, action_map,
    )
    if workflow_mode == "standalone":
        issues.extend(distillation_issues)

    p0_requirement_ids = {
        str(atom.get("requirement_id")) for atom in atom_map.values()
        if decision_requirements.get(str(atom.get("requirement_id")), {}).get("priority") == "P0"
        and decision_requirements.get(str(atom.get("requirement_id")), {}).get("status") == "READY"
    }
    action_question_ids = {
        question_id
        for action in action_map.values()
        for question_id in _text_set(action.get("trigger_question_ids"))
    }
    for question_id, question in question_map.items():
        if (
            question.get("response_class") == "UNKNOWN_SKIP"
            and _text_set(question.get("affected_requirement_ids")) & p0_requirement_ids
            and question_id not in action_question_ids
        ):
            issues.append(
                f"[A13-DISCOVERY-008] question {question_id!r}: P0 UNKNOWN_SKIP requires an evidence action"
            )

    if declared_closure == "NOT_REQUIRED_WITH_REASON" and not closure_reason:
        issues.append(
            "[A13-DISCOVERY-009] $.discovery.closure.reason: required for NOT_REQUIRED_WITH_REASON"
        )
    if workflow_mode == "embedded":
        if discovery_mode != "parent_bound" or has_rounds or distillations or action_map:
            issues.append(
                "[A13-DISCOVERY-010] $.discovery: embedded mode must use parent_bound without local re-interview"
            )
        if declared_closure != "NOT_REQUIRED_WITH_REASON":
            issues.append(
                "[A13-DISCOVERY-011] $.discovery.closure.status: embedded mode must record NOT_REQUIRED_WITH_REASON"
            )
    elif discovery_mode != "standalone":
        issues.append(
            "[A13-DISCOVERY-012] $.discovery.mode: standalone workflow requires standalone discovery"
        )

    derived_closure = derive_discovery_closure(
        workflow_mode, evidence_pass_valid, distillations_valid, action_map,
    )
    if declared_closure != derived_closure:
        issues.append(
            f"[A13-DISCOVERY-023] $.discovery.closure.status: expected derived value {derived_closure!r}"
        )
    return DiscoveryReport(tuple(sorted(issues)), derived_closure)


def build_handoff_report(
    *,
    handoff: Mapping[str, Any],
    workflow_mode: str,
    assertion_ids: set[str],
    handoff_assertion_ids: set[str],
    atom_rows: list[Any],
    handoff_atom_rows: list[Any],
    source_hash: str,
    variant_ids: set[str],
) -> HandoffReport:
    """Validate one child-local Handoff/lineage binding without parent I/O."""
    issues: list[str] = []
    _, shape_issues = validate_handoff_shape(handoff, workflow_mode)
    issues.extend(shape_issues)
    if workflow_mode != "embedded":
        return HandoffReport(tuple(sorted(issues)))
    for key in ("discovery_closure_hash", "ptd_inventory_hash", "decision_denominator_hash"):
        if not isinstance(handoff.get(key), str) or not SHA256_REF_RE.fullmatch(str(handoff.get(key))):
            issues.append(
                f"[A13-HANDOFF-030] $.enriched_content_handoff.{key}: expected sha256:<64 hex>"
            )
    if handoff_assertion_ids != assertion_ids:
        issues.append(
            "[A13-HANDOFF-031] $.enriched_content_handoff.canonical_assertion_ids: must exactly match child assertions"
        )
    if handoff_atom_rows != atom_rows:
        issues.append(
            "[A13-HANDOFF-032] $.enriched_content_handoff.requirement_atoms: must exactly match denominator atoms"
        )
    if handoff.get("decision_denominator_hash") != source_hash:
        issues.append(
            "[A13-HANDOFF-033] $.enriched_content_handoff.decision_denominator_hash: must match child parent-source hash"
        )
    handoff_variants = (
        set(handoff.get("variant_row_ids", []))
        if isinstance(handoff.get("variant_row_ids"), list) else set()
    )
    if handoff_variants != variant_ids:
        issues.append(
            "[A13-HANDOFF-034] $.enriched_content_handoff.variant_row_ids: must exactly match child variant rows"
        )
    if handoff.get("checksum") != canonical_handoff_hash(handoff):
        issues.append(
            "[A13-HANDOFF-035] $.enriched_content_handoff.checksum: immutable handoff checksum mismatch"
        )
    return HandoffReport(tuple(sorted(issues)))


def build_coverage_report(
    *,
    capabilities: Mapping[str, Mapping[str, Any]],
    atom_map: Mapping[str, Mapping[str, Any]],
    decision_requirements: Mapping[str, Mapping[str, Any]],
    answers_by_atom: Mapping[str, list[Mapping[str, Any]]],
    carrier_map: Mapping[str, Mapping[str, Any]],
    closure_status: str,
    denominator_status: str,
    delta_map: Mapping[str, Mapping[str, Any]],
    action_map: Mapping[str, Mapping[str, Any]],
    conclusion: str,
    assertion_count: int,
    expected_denominator_hash: str,
    summary_required: Any,
    summary_pass: Any,
    summary_gap_ids: set[str],
    declared_component: str,
    component_gap_ids: set[str],
    component_delta_ids: set[str],
    page_pass_implied: Any,
    publication_authorized: Any,
) -> CoverageReport:
    """Derive atomic native coverage and the non-authorizing child result."""
    issues: list[str] = []
    required_atoms = {
        atom_id for atom_id, atom in atom_map.items()
        if decision_requirements.get(str(atom.get("requirement_id")), {}).get("priority") == "P0"
        and decision_requirements.get(str(atom.get("requirement_id")), {}).get("status") == "READY"
        and decision_requirements.get(str(atom.get("requirement_id")), {}).get("native_answer_required", True) is True
    }
    passed_atoms: set[str] = set()
    blocked_local_atoms: set[str] = set()
    for atom_id in required_atoms:
        valid_primary_answers: list[str] = []
        for answer in answers_by_atom.get(atom_id, []):
            carrier = carrier_map.get(str(answer.get("primary_carrier_id", "")), {})
            capability = capabilities.get(str(carrier.get("capability_snapshot_id", "")), {})
            available_fields = (
                set(capability.get("backend_field_paths", []))
                if isinstance(capability.get("backend_field_paths"), list) else set()
            )
            if (
                answer.get("qa_status") in {"FAILED", "BLOCKED"}
                or carrier.get("qa_status") in {"FAILED", "BLOCKED"}
                or capability.get("status") == "BLOCKED"
            ):
                blocked_local_atoms.add(atom_id)
            if (
                answer.get("content_status") in FINAL_CONTENT_STATUSES
                and answer.get("qa_status") == "PASS"
                and carrier.get("carrier_type") == "native_text"
                and carrier.get("coverage_role") == "PRIMARY_NATIVE_ANSWER"
                and carrier.get("content_status") in FINAL_CONTENT_STATUSES
                and carrier.get("qa_status") == "PASS"
                and str(answer.get("variant_row_id", "")) in (
                    set(carrier.get("variant_row_ids", []))
                    if isinstance(carrier.get("variant_row_ids"), list) else set()
                )
                and capability.get("status") == "CURRENT"
                and answer.get("native_field_path") in available_fields
                and _is_text(answer.get("text"))
            ):
                valid_primary_answers.append(str(answer.get("id", "")))
        if len(valid_primary_answers) == 1:
            passed_atoms.add(atom_id)
        elif len(valid_primary_answers) > 1:
            issues.append(
                f"[A13-COVERAGE-033] atom {atom_id!r}: multiple valid FINAL PRIMARY answers {valid_primary_answers!r}"
            )

    gap_atoms = sorted(required_atoms - passed_atoms)
    if denominator_status == "FROZEN" and not required_atoms:
        issues.append(
            "[A13-COVERAGE-030] $.decision_denominator_snapshot: frozen denominator cannot have 0 P0 atoms"
        )
    for key, actual, expected in (
        ("p0_atoms_required", summary_required, len(required_atoms)),
        ("p0_atoms_pass", summary_pass, len(passed_atoms)),
    ):
        if actual != expected:
            issues.append(f"[A13-COVERAGE-031] $.coverage_summary.{key}: expected derived value {expected}")
    if summary_gap_ids != set(gap_atoms):
        issues.append(
            f"[A13-COVERAGE-032] $.coverage_summary.gap_atom_ids: expected {gap_atoms!r}"
        )

    open_delta_ids = sorted(
        delta_id for delta_id, row in delta_map.items() if row.get("status") == "OPEN"
    )
    open_delta_atoms = {
        atom_id
        for delta_id in open_delta_ids
        for atom_id in delta_map[delta_id].get("affected_atom_ids", [])
        if isinstance(atom_id, str)
    }
    open_action = any(row.get("status") == "OPEN" for row in action_map.values())
    derived_component, derived_gap_atoms, stale_delta_atoms = derive_coverage_result(
        closure_status, denominator_status, required_atoms, passed_atoms,
        open_delta_atoms, blocked_local_atoms, open_action,
    )
    if list(derived_gap_atoms) != gap_atoms:
        issues.append("[A13-RESULT-006] internal component-gap derivation mismatch")
    if stale_delta_atoms:
        issues.append(
            "[A13-DELTA-034] $.delta_evidence_requests: OPEN deltas must map only to "
            f"current gap atoms {list(stale_delta_atoms)!r}"
        )
    if derived_component == "DELTA_REQUIRED" and set(gap_atoms) - open_delta_atoms:
        issues.append(
            "[A13-DELTA-035] $.component_result: every DELTA_REQUIRED gap atom needs an OPEN delta request"
        )
    if page_pass_implied is not False or publication_authorized is not False:
        issues.append(
            "[A13-RESULT-005] $.component_result: a child component result cannot imply page PASS or publication authority"
        )
    if declared_component != derived_component:
        issues.append(
            f"[A13-RESULT-001] $.component_result.status: expected derived value {derived_component!r}"
        )
    if component_gap_ids != set(gap_atoms) or component_delta_ids != set(open_delta_ids):
        issues.append(
            "[A13-RESULT-002] $.component_result: gap/delta IDs must match derived state"
        )
    if declared_component == "COMPONENT_PASS" and conclusion != "PASS":
        issues.append(
            "[A13-RESULT-003] $.project.conclusion: COMPONENT_PASS requires child project PASS"
        )
    if conclusion == "PASS" and declared_component != "COMPONENT_PASS":
        issues.append(
            "[A13-RESULT-004] $.project.conclusion: PASS requires COMPONENT_PASS"
        )

    counts = {
        "requirement_atoms": len(atom_map),
        "p0_atoms_required": len(required_atoms),
        "p0_atoms_pass": len(passed_atoms),
        "canonical_assertions": assertion_count,
        "component_result": derived_component,
        "decision_denominator_hash": expected_denominator_hash,
    }
    return CoverageReport(tuple(sorted(issues)), counts)
