#!/usr/bin/env python3
"""Pure domain decisions shared by the Listing v1.1 validator and tests.

Functions here have no filesystem, network, clock, or cross-Skill effects.
They consume already-parsed contract values and return deterministic decisions.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


STRONG_PRODUCT_SOURCE_TYPES = {
    "physical_sample", "physical_measurement", "packaging_label",
    "manufacturer_specification", "authorized_product_record", "lab_test",
    "certification",
}
CURRENT_RULE_SOURCE_TYPES = {
    "amazon_official_rule", "seller_central_screenshot", "seller_central_export"
}


def evaluate_evidence(source_rows: Iterable[Mapping[str, Any]], evidence_pass: Mapping[str, Any]) -> str:
    usable = {str(row.get("id")) for row in source_rows if row.get("status") == "USABLE"}
    bound = set(evidence_pass.get("source_ids", []))
    return "PASS" if evidence_pass.get("status") == "COMPLETE" and bool(bound) and bound.issubset(usable) else "BLOCKED"


def current_rule_has_strong_source(rule: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]) -> bool:
    return any(
        source.get("status") == "USABLE"
        and source.get("evidence_level") in {"E3", "E4"}
        and source.get("type") in CURRENT_RULE_SOURCE_TYPES
        for source_id in rule.get("source_ids", [])
        for source in [sources.get(str(source_id), {})]
    )


def has_strong_product_source(source_ids: Iterable[str], sources: Mapping[str, Mapping[str, Any]]) -> bool:
    return any(
        source.get("type") in STRONG_PRODUCT_SOURCE_TYPES
        and source.get("status") == "USABLE"
        and source.get("evidence_level") in {"E3", "E4"}
        for source_id in source_ids
        for source in [sources.get(str(source_id), {})]
    )


def evaluate_discovery(closure_status: str, open_p0_action_count: int, evidence_gate: str) -> str:
    if closure_status in {"PASS", "NOT_REQUIRED_WITH_REASON"} and open_p0_action_count == 0 and evidence_gate == "PASS":
        return "PASS"
    if closure_status == "CONDITIONAL":
        return "CONDITIONAL"
    return "BLOCKED"


def expected_requirement_atom_tuples(
    requirements: Iterable[Mapping[str, Any]],
    variants: Iterable[Mapping[str, Any]],
    marketplace: str,
    locale: str,
) -> set[tuple[str, str, str, str]]:
    def applies(scope: Any, variant: Mapping[str, Any]) -> bool:
        if not isinstance(scope, dict):
            return False
        mapping = {
            "parent_asins": variant.get("parent_asin"),
            "child_asins": variant.get("child_asin"),
            "packs": variant.get("pack"),
            "colors": variant.get("color"),
            "sizes": variant.get("size"),
        }
        for key, actual in mapping.items():
            allowed = set(scope.get(key, [])) if isinstance(scope.get(key, []), list) else set()
            if allowed and actual not in allowed:
                return False
        return True

    return {
        (str(requirement.get("id")), marketplace, locale, str(variant.get("id")))
        for requirement in requirements
        if requirement.get("priority") == "P0" and requirement.get("status") == "READY"
        for variant in variants
        if applies(requirement.get("application_scope"), variant)
    }


def evaluate_ptd(status: str, expected_fields: Iterable[Mapping[str, Any]], complete_capture: bool, has_domain_error: bool) -> str:
    rows = list(expected_fields)
    return "PASS" if status == "COMPLETE" and bool(rows) and complete_capture and not has_domain_error else "BLOCKED"


def evaluate_handoff(status: str, has_domain_error: bool, requested_content_types: Iterable[str]) -> tuple[str, bool]:
    gate = "PASS" if status in {"NOT_APPLICABLE", "FROZEN", "RESULT_RECEIVED"} and not has_domain_error else "BLOCKED"
    coordinator_required = bool(list(requested_content_types)) and status != "NOT_APPLICABLE"
    return gate, coordinator_required


def evaluate_publication(
    boundary: str,
    authorization_status: str,
    readback_statuses: set[str],
) -> dict[str, str]:
    if boundary in {"read_only", "local_candidate"}:
        return {"publication": "NOT_RUN", "backend": "NOT_RUN", "live": "NOT_RUN"}
    publication = "PASS" if authorization_status == "AUTHORIZED" else "BLOCKED"
    backend = "PASS" if readback_statuses & {"ACCEPTED_BACKEND", "LIVE_MATCH", "LIVE_MISMATCH"} else "NOT_RUN"
    live = "PASS" if readback_statuses == {"LIVE_MATCH"} and bool(readback_statuses) else ("BLOCKED" if "LIVE_MISMATCH" in readback_statuses else "NOT_RUN")
    return {"publication": publication, "backend": backend, "live": live}


def derive_stage(gates: Mapping[str, str]) -> str:
    ordered = [
        ("identity", "IDENTITY_FROZEN"), ("rules", "RULES_READY"),
        ("evidence", "EVIDENCE_READY"), ("truth", "TRUTH_READY"),
        ("discovery", "DISCOVERY_CLOSED"), ("market_research", "DISCOVERY_CLOSED"),
        ("decision", "DECISION_FROZEN"),
        ("ptd", "PTD_CLOSED"), ("surfaces", "SURFACES_READY"),
        ("candidates", "CANDIDATE_READY"), ("handoff", "HANDOFF_READY"),
        ("package", "PACKAGE_PASS"), ("publication", "AUTHORIZED_SUBMISSION"),
        ("backend", "BACKEND_ACCEPTED"), ("live", "LIVE_MATCH"),
    ]
    stage = "AUTHORITY"
    for gate, candidate in ordered:
        if gates.get(gate) != "PASS":
            break
        stage = candidate
    return stage
