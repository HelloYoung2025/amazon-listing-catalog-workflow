#!/usr/bin/env python3
"""Pure Discovery/Methods/Market Research phase for Listing Bundle v1.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from listing_v11_domains import evaluate_discovery, evaluate_evidence
from listing_v11_evidence import source_context_matches, source_covers
from listing_v11_phase import (
    DISCOVERY_CLOSURES,
    DISCOVERY_KEYS,
    DISCOVERY_QUESTION_KEYS,
    DISCOVERY_RESPONSE_KEYS,
    DISCOVERY_STAGE_GATE_KEYS,
    DISCOVERY_STAGE_STATUSES,
    DISCOVERY_STAGE_TYPES,
    DISCOVERY_DISTILLATION_TYPES,
    IMPACT_DIMENSIONS,
    MARKET_RESEARCH_KEYS,
    MARKET_RESEARCH_ROW_KEYS,
    METHOD_CLASSES,
    METHOD_KEYS,
    ONE_BET_PAYLOAD_KEYS,
    PRODUCT_INTENT_PAYLOAD_KEYS,
    ROUTE_PROOF_STATUSES,
    ROUTE_REGISTRY_KEYS,
    SELECTABLE_ROUTE_PROOF_STATUSES,
    PhaseDelta,
    RESPONSE_CLASSES,
    _err,
    _index,
    _isoish,
    _nonempty,
    _obj_list,
    _refs,
    _unique_strings,
)


MARKETPLACE_RETAIL_SUFFIX = {
    "US": "com", "CA": "ca", "UK": "co.uk", "DE": "de", "FR": "fr",
    "IT": "it", "ES": "es", "JP": "co.jp", "AU": "com.au", "MX": "com.mx",
    "BR": "com.br", "IN": "in", "SG": "sg", "AE": "ae", "SA": "sa",
    "NL": "nl", "PL": "pl", "SE": "se", "BE": "be", "TR": "com.tr",
}


@dataclass(frozen=True)
class DiscoveryReport:
    delta: PhaseDelta
    discovery: dict[str, Any]
    closure: dict[str, Any]
    market_research: dict[str, Any]


def _substantive_human_text(value: Any) -> bool:
    """Reject empty/placeholder summaries without treating prose as Gate authority."""
    if not isinstance(value, str):
        return False
    text = " ".join(value.strip().split())
    normalized = text.casefold().replace(" ", "")
    if normalized in {"x", "xx", "tbd", "todo", "n/a", "na", "unknown", "placeholder", "已完成", "待定", "未知"}:
        return False
    alphanumeric = [char.casefold() for char in text if char.isalnum()]
    return len(text) >= 12 and len(set(alphanumeric)) >= 4


def _amazon_product_asin(value: Any, marketplace: Any) -> str:
    """Return the ASIN only for the frozen marketplace's live Amazon PDP URL."""
    if not isinstance(value, str) or not isinstance(marketplace, str):
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    expected_suffix = MARKETPLACE_RETAIL_SUFFIX.get(marketplace.upper())
    if parsed.scheme != "https" or not parsed.hostname or not expected_suffix:
        return ""
    host = parsed.hostname.lower().rstrip(".")
    if host not in {f"amazon.{expected_suffix}", f"www.amazon.{expected_suffix}"}:
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    for marker in ("dp", "product"):
        for index, part in enumerate(parts[:-1]):
            if part.casefold() == marker:
                candidate = parts[index + 1].upper()
                return candidate if len(candidate) == 10 and candidate.isalnum() else ""
    return ""


def validate_discovery_domain(
    bundle: dict[str, Any],
    *,
    project: dict[str, Any],
    scope: dict[str, Any],
    source_rows: list[dict[str, Any]],
    source_index: dict[str, dict[str, Any]],
    fact_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
    conflict_index: dict[str, dict[str, Any]],
    evidence_gate: str,
) -> DiscoveryReport:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    gates: dict[str, str] = {"evidence": evidence_gate}
    method_rows = _obj_list(bundle.get("method_registry"), "method_registry", errors)
    _index(method_rows, "method_registry", errors)
    for index, row in enumerate(method_rows):
        path = f"method_registry[{index}]"
        if set(row) != METHOD_KEYS:
            _err(errors, "L11-METHOD-005", path, f"must contain exactly {sorted(METHOD_KEYS)}")
        if row.get("classification") not in METHOD_CLASSES:
            _err(errors, "L11-METHOD-002", f"{path}.classification", "unsupported method class")
        if not isinstance(row.get("gate_eligible"), bool):
            _err(errors, "L11-METHOD-003", f"{path}.gate_eligible", "must be boolean")
        if not _nonempty(row.get("name")) or not _isoish(row.get("observed_at")):
            _err(errors, "L11-METHOD-012", path, "name and timezone-qualified observed_at are required")
        if row.get("classification") in {"MULTI_SOURCE_HEURISTIC", "COMMUNITY_HYPOTHESIS", "PROHIBITED_REJECTED"} and row.get("gate_eligible"):
            _err(errors, "L11-METHOD-004", path, "heuristics, hypotheses, and rejected practices cannot control gates")
        _refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors)
        if row.get("status") not in {"CURRENT", "REFERENCE", "STALE", "REJECTED"}:
            _err(errors, "L11-METHOD-006", f"{path}.status", "unsupported method status")
        if not _nonempty(row.get("refresh_trigger")):
            _err(errors, "L11-METHOD-007", f"{path}.refresh_trigger", "is required")
        if row.get("gate_eligible"):
            method_sources = [source_index.get(item, {}) for item in row.get("source_ids", [])]
            method_scope = {
                "parent_asins": list(scope.get("parent_asins", [])),
                "child_asins": list(scope.get("intended_child_asins", [])),
                "packs": list(scope.get("packs", [])),
                "colors": list(scope.get("colors", [])),
                "sizes": list(scope.get("sizes", [])),
            }
            if (
                row.get("status") != "CURRENT"
                or not _isoish(row.get("observed_at"))
                or str(row.get("observed_at"))[:10] < str(project.get("snapshot_date"))
                or not method_sources
                or any(not source_covers(source, scope, method_scope) for source in method_sources)
            ):
                _err(errors, "L11-METHOD-008", path, "gate-eligible method requires fresh CURRENT evidence covering the full frozen context/scope")
            classification = row.get("classification")
            if classification == "OFFICIAL_CURRENT" and not any(
                source.get("type") in {"amazon_official_rule", "seller_central_screenshot", "seller_central_export"}
                and source.get("evidence_level") in {"E3", "E4"}
                for source in method_sources
            ):
                _err(errors, "L11-METHOD-009", path, "OFFICIAL_CURRENT needs current official/account evidence")
            if classification == "ACCOUNT_OBSERVED" and not any(
                source.get("type") in {"seller_central_screenshot", "seller_central_export"}
                for source in method_sources
            ):
                _err(errors, "L11-METHOD-010", path, "ACCOUNT_OBSERVED needs Seller Central evidence")
            if classification == "TARGET_PRODUCT_EVIDENCE" and not any(
                source.get("type") in {
                    "physical_sample", "physical_measurement", "packaging_label",
                    "manufacturer_specification", "authorized_product_record", "lab_test", "certification",
                }
                and source.get("evidence_level") in {"E3", "E4"}
                for source in method_sources
            ):
                _err(errors, "L11-METHOD-011", path, "TARGET_PRODUCT_EVIDENCE needs strong product evidence")

    discovery = bundle.get("discovery") if isinstance(bundle.get("discovery"), dict) else {}
    if set(discovery) != DISCOVERY_KEYS:
        _err(errors, "L11-DISCOVERY-013", "discovery", f"must contain exactly {sorted(DISCOVERY_KEYS)}")
    if discovery.get("status") not in {"NOT_STARTED", "IN_PROGRESS", "COMPLETE", "CONDITIONAL", "BLOCKED", "NOT_REQUIRED_WITH_REASON"}:
        _err(errors, "L11-DISCOVERY-020", "discovery.status", "unsupported discovery status")
    evidence_pass = discovery.get("evidence_pass") if isinstance(discovery.get("evidence_pass"), dict) else {}
    _refs(evidence_pass.get("source_ids", []), set(source_index), "discovery.evidence_pass.source_ids", errors)
    observations = _obj_list(evidence_pass.get("observations", []), "discovery.evidence_pass.observations", errors)
    observation_index = _index(observations, "discovery.evidence_pass.observations", errors)
    gates["evidence"] = evaluate_evidence(source_rows, evidence_pass)
    if any(not source_context_matches(source_index.get(item, {}), scope) for item in evidence_pass.get("source_ids", [])):
        gates["evidence"] = "BLOCKED"
        _err(errors, "L11-DISCOVERY-014", "discovery.evidence_pass.source_ids", "evidence pass sources must be USABLE and context-bound")
    if gates["evidence"] == "BLOCKED":
        _err(errors, "L11-DISCOVERY-001", "discovery.evidence_pass", "evidence pass must be COMPLETE and source-bound")
    response_rows = _obj_list(discovery.get("responses", []), "discovery.responses", errors)
    response_index = _index(response_rows, "discovery.responses", errors)
    for index, response in enumerate(response_rows):
        path = f"discovery.responses[{index}]"
        if set(response) != DISCOVERY_RESPONSE_KEYS:
            _err(errors, "L11-DISCOVERY-015", path, f"must contain exactly {sorted(DISCOVERY_RESPONSE_KEYS)}")
        if response.get("classification") not in RESPONSE_CLASSES:
            _err(errors, "L11-DISCOVERY-006", f"{path}.classification", "unsupported response class")
        if response.get("status") not in {"ANSWERED", "UNKNOWN", "SKIP"}:
            _err(errors, "L11-DISCOVERY-007", f"{path}.status", "unsupported response status")
        if not isinstance(response.get("p0_impact"), bool):
            _err(errors, "L11-DISCOVERY-008", f"{path}.p0_impact", "must be boolean")
        _refs(response.get("source_ids", []), set(source_index), f"{path}.source_ids", errors)
        if response.get("status") == "ANSWERED" and not _nonempty(response.get("answer")):
            _err(errors, "L11-DISCOVERY-016", f"{path}.answer", "ANSWERED response requires text")
        if not _nonempty(response.get("owner")):
            _err(errors, "L11-DISCOVERY-021", f"{path}.owner", "is required")
        if (
            (response.get("classification") == "UNKNOWN_SKIP") != (response.get("status") in {"UNKNOWN", "SKIP"})
            or (response.get("status") in {"UNKNOWN", "SKIP"} and _nonempty(response.get("answer")))
        ):
            _err(errors, "L11-DISCOVERY-022", path, "UNKNOWN_SKIP must use UNKNOWN/SKIP with no asserted answer; other classes must be ANSWERED")
        if response.get("classification") == "FACT_LEAD" and response.get("status") == "ANSWERED" and not response.get("source_ids"):
            _err(errors, "L11-DISCOVERY-017", f"{path}.source_ids", "FACT_LEAD requires evidence references")
        if response.get("classification") == "FACT_LEAD" and response.get("status") == "ANSWERED" and any(
            not source_context_matches(source_index.get(source_id, {}), scope)
            for source_id in response.get("source_ids", [])
        ):
            _err(errors, "L11-DISCOVERY-019", f"{path}.source_ids", "FACT_LEAD evidence must be USABLE and bound to the frozen seller/marketplace/locale")
        if response.get("classification") == "STRATEGIC_CHOICE" and response.get("status") == "ANSWERED" and not _substantive_human_text(response.get("answer")):
            _err(errors, "L11-DISCOVERY-048", f"{path}.answer", "strategic choice needs a substantive human-readable answer; typed records remain the Gate authority")
    rounds = _obj_list(discovery.get("interview_rounds", []), "discovery.interview_rounds", errors)
    round_index = _index(rounds, "discovery.interview_rounds", errors)
    round_types: set[str] = set()
    round_ids_by_type: dict[str, set[str]] = {"TRUTH": set(), "POSITIONING": set()}
    question_ids_by_type: dict[str, set[str]] = {"TRUTH": set(), "POSITIONING": set()}
    response_ids_by_type: dict[str, set[str]] = {"TRUTH": set(), "POSITIONING": set()}
    strategic_selection_question_ids: set[str] = set()
    strategic_selection_response_ids: set[str] = set()
    question_id_by_response: dict[str, str] = {}
    round_id_by_response: dict[str, str] = {}
    referenced_response_ids: list[str] = []
    for r_index, round_row in enumerate(rounds):
        round_type = round_row.get("round_type")
        if round_type not in {"TRUTH", "POSITIONING"}:
            _err(errors, "L11-DISCOVERY-024", f"discovery.interview_rounds[{r_index}].round_type", "must be TRUTH or POSITIONING")
        else:
            round_types.add(str(round_type))
            round_id = round_row.get("id")
            if isinstance(round_id, str) and round_id:
                round_ids_by_type[str(round_type)].add(round_id)
        questions = _obj_list(round_row.get("questions", []), f"discovery.interview_rounds[{r_index}].questions", errors)
        _index(questions, f"discovery.interview_rounds[{r_index}].questions", errors)
        for q_index, question in enumerate(questions):
            qpath = f"discovery.interview_rounds[{r_index}].questions[{q_index}]"
            if set(question) != DISCOVERY_QUESTION_KEYS:
                _err(errors, "L11-DISCOVERY-018", qpath, f"must contain exactly {sorted(DISCOVERY_QUESTION_KEYS)}")
            if not _nonempty(question.get("question")) or not _unique_strings(question.get("impact_dimensions", [])):
                _err(errors, "L11-DISCOVERY-002", qpath, "question and impact dimensions are required")
            elif not set(question["impact_dimensions"]).issubset(IMPACT_DIMENSIONS):
                _err(errors, "L11-DISCOVERY-003", f"{qpath}.impact_dimensions", "unsupported impact dimension")
            response_id = question.get("response_id")
            if response_id not in response_index:
                _err(errors, "L11-DISCOVERY-004", f"{qpath}.response_id", "must reference one formal discovery response")
            elif isinstance(response_id, str):
                referenced_response_ids.append(response_id)
                if round_type in response_ids_by_type:
                    response_ids_by_type[str(round_type)].add(response_id)
            question_id = question.get("id")
            if isinstance(question_id, str) and question_id and round_type in question_ids_by_type:
                question_ids_by_type[str(round_type)].add(question_id)
                if isinstance(response_id, str):
                    question_id_by_response[response_id] = question_id
                    if isinstance(round_row.get("id"), str) and round_row.get("id"):
                        round_id_by_response[response_id] = str(round_row["id"])
                if "STRATEGIC_SELECTION" in question.get("impact_dimensions", []):
                    strategic_selection_question_ids.add(question_id)
                    if isinstance(response_id, str):
                        strategic_selection_response_ids.add(response_id)
    if set(referenced_response_ids) != set(response_index) or len(referenced_response_ids) != len(set(referenced_response_ids)):
        _err(errors, "L11-DISCOVERY-005", "discovery", "every formal response must be referenced by exactly one question")
    distillations = _obj_list(discovery.get("distillations", []), "discovery.distillations", errors)
    distillation_index = _index(distillations, "discovery.distillations", errors)
    distillation_ids_by_type: dict[str, set[str]] = {"TRUTH": set(), "POSITIONING": set()}
    typed_distillation_ids: dict[str, set[str]] = {
        record_type: set() for record_type in DISCOVERY_DISTILLATION_TYPES
    }
    one_bet_proof_by_id: dict[str, str] = {}
    for index, row in enumerate(distillations):
        path = f"discovery.distillations[{index}]"
        _refs(row.get("response_ids", []), set(response_index), f"discovery.distillations[{index}].response_ids", errors, nonempty=True)
        distillation_id = row.get("id")
        if isinstance(distillation_id, str):
            response_ids = set(row.get("response_ids", []))
            for round_type, allowed_response_ids in response_ids_by_type.items():
                if response_ids and response_ids.issubset(allowed_response_ids):
                    distillation_ids_by_type[round_type].add(distillation_id)
        record_type = row.get("record_type")
        payload = row.get("payload")
        if record_type is not None:
            if record_type not in DISCOVERY_DISTILLATION_TYPES:
                _err(errors, "L11-DISCOVERY-044", f"{path}.record_type", "unsupported typed discovery record")
            elif isinstance(distillation_id, str):
                typed_distillation_ids[str(record_type)].add(distillation_id)
            if not isinstance(payload, dict):
                _err(errors, "L11-DISCOVERY-044", f"{path}.payload", "typed discovery record requires an object payload")
            elif record_type == "PRODUCT_INTENT_BRIEF":
                if set(payload) != PRODUCT_INTENT_PAYLOAD_KEYS or any(not _substantive_human_text(payload.get(key)) for key in PRODUCT_INTENT_PAYLOAD_KEYS):
                    _err(errors, "L11-DISCOVERY-045", f"{path}.payload", f"Product Intent Brief requires exact substantive dimensions {sorted(PRODUCT_INTENT_PAYLOAD_KEYS)}")
            elif record_type == "ONE_BET_SELECTION":
                if set(payload) != ONE_BET_PAYLOAD_KEYS:
                    _err(errors, "L11-DISCOVERY-047", f"{path}.payload", f"One-Bet requires exact dimensions {sorted(ONE_BET_PAYLOAD_KEYS)}")
                else:
                    scalar_keys = ONE_BET_PAYLOAD_KEYS - {"selected_route_id", "rejected_route_ids", "rejected_route_reasons", "route_registry", "proof_status"}
                    rejected_ids = payload.get("rejected_route_ids")
                    rejected_reasons = payload.get("rejected_route_reasons")
                    route_registry = payload.get("route_registry")
                    route_rows = route_registry if isinstance(route_registry, list) else []
                    route_ids = [row.get("route_id") for row in route_rows if isinstance(row, dict)]
                    route_map = {
                        str(row.get("route_id")): row for row in route_rows
                        if isinstance(row, dict) and _nonempty(row.get("route_id"))
                    }
                    selected_route_id = payload.get("selected_route_id")
                    selected_route = route_map.get(str(selected_route_id), {})
                    if isinstance(distillation_id, str) and isinstance(payload.get("proof_status"), str):
                        one_bet_proof_by_id[distillation_id] = payload["proof_status"]
                    route_registry_valid = (
                        isinstance(route_registry, list)
                        and len(route_rows) >= 2
                        and len(route_rows) == len(route_registry)
                        and len(route_ids) == len(set(route_ids))
                        and all(
                            set(route) == ROUTE_REGISTRY_KEYS
                            and _nonempty(route.get("route_id"))
                            and route.get("proof_status") in ROUTE_PROOF_STATUSES
                            and all(
                                _substantive_human_text(route.get(key))
                                for key in ROUTE_REGISTRY_KEYS - {"route_id", "proof_status"}
                            )
                            for route in route_rows
                        )
                    )
                    if (
                        any(not _substantive_human_text(payload.get(key)) for key in scalar_keys)
                        or not _nonempty(selected_route_id)
                        or not _unique_strings(rejected_ids)
                        or not isinstance(rejected_ids, list) or not rejected_ids
                        or not isinstance(rejected_reasons, dict)
                        or set(rejected_reasons) != set(rejected_ids)
                        or any(not _substantive_human_text(reason) for reason in rejected_reasons.values())
                        or selected_route_id in set(rejected_ids)
                        or not route_registry_valid
                        or set(route_map) != {str(selected_route_id), *[str(item) for item in rejected_ids or []]}
                        or selected_route.get("proof_status") not in SELECTABLE_ROUTE_PROOF_STATUSES
                        or payload.get("proof_status") != selected_route.get("proof_status")
                        or any(
                            payload.get(key) != selected_route.get(key)
                            for key in {"hero_moment", "closest_alternative", "desired_progress", "mechanism", "material_boundary"}
                        )
                    ):
                        _err(errors, "L11-DISCOVERY-047", f"{path}.payload", "One-Bet needs a real two-plus route registry, one evidence-supported selected route, exact rejected-route disposition, aligned route consequences, substantive boundary, and reversible test")
        for key, allowed in (("fact_ids", set(fact_index)), ("claim_ids", set(claim_index)), ("conflict_ids", set(conflict_index))):
            typed_strategy_fact_chain = key == "fact_ids" and record_type in {
                "PRODUCT_INTENT_BRIEF", "ONE_BET_SELECTION",
            }
            _refs(
                row.get(key, []), allowed, f"discovery.distillations[{index}].{key}", errors,
                nonempty=typed_strategy_fact_chain,
            )
        if record_type in {"PRODUCT_INTENT_BRIEF", "ONE_BET_SELECTION"} and not row.get("fact_ids"):
            _err(
                errors, "L11-DISCOVERY-049", f"{path}.fact_ids",
                "typed Product Intent and One-Bet records require a nonempty current-product Fact chain",
            )
    action_rows = _obj_list(discovery.get("evidence_actions", []), "discovery.evidence_actions", errors)
    action_index = _index(action_rows, "discovery.evidence_actions", errors)
    actions_by_response = {row.get("response_id") for row in action_rows if row.get("status") in {"OPEN", "RESOLVED"}}
    for index, row in enumerate(action_rows):
        if row.get("response_id") not in response_index or row.get("status") not in {"OPEN", "RESOLVED", "CANCELLED_WITH_REASON"}:
            _err(errors, "L11-DISCOVERY-009", f"discovery.evidence_actions[{index}]", "invalid response reference or status")
    for response_id, response in response_index.items():
        if response.get("p0_impact") and response.get("status") in {"UNKNOWN", "SKIP"} and response_id not in actions_by_response:
            _err(errors, "L11-DISCOVERY-010", f"response:{response_id}", "P0 UNKNOWN/SKIP requires an evidence action")
    stage_rows = _obj_list(discovery.get("stage_gates", []), "discovery.stage_gates", errors)
    _index(stage_rows, "discovery.stage_gates", errors)
    counts["discovery_stage_gates"] = len(stage_rows)
    stage_by_name: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(stage_rows):
        path = f"discovery.stage_gates[{index}]"
        if set(row) != DISCOVERY_STAGE_GATE_KEYS:
            _err(errors, "L11-DISCOVERY-025", path, f"must contain exactly {sorted(DISCOVERY_STAGE_GATE_KEYS)}")
        stage = row.get("stage")
        if stage not in DISCOVERY_STAGE_TYPES:
            _err(errors, "L11-DISCOVERY-026", f"{path}.stage", "unsupported discovery stage")
        elif stage in stage_by_name:
            _err(errors, "L11-DISCOVERY-027", f"{path}.stage", "duplicate discovery stage")
        else:
            stage_by_name[str(stage)] = row
        status = row.get("status")
        if status not in DISCOVERY_STAGE_STATUSES:
            _err(errors, "L11-DISCOVERY-028", f"{path}.status", "unsupported stage status")
        evidence_ids = row.get("evidence_source_ids", [])
        _refs(evidence_ids, set(source_index), f"{path}.evidence_source_ids", errors)
        if any(not source_context_matches(source_index.get(item, {}), scope) for item in evidence_ids):
            _err(errors, "L11-DISCOVERY-029", f"{path}.evidence_source_ids", "stage evidence must be USABLE and context-bound")
        if not _unique_strings(row.get("record_refs", [])):
            _err(errors, "L11-DISCOVERY-030", f"{path}.record_refs", "must be a unique string array")
        if status in {"PASS", "NOT_REQUIRED_WITH_REASON"}:
            if not all(_nonempty(row.get(key)) for key in ("result", "closed_at", "owner")) or not row.get("record_refs"):
                _err(errors, "L11-DISCOVERY-031", path, "closed stage requires result, record refs, closed_at, and owner")
            if not _isoish(row.get("closed_at")):
                _err(errors, "L11-DISCOVERY-032", f"{path}.closed_at", "must be timezone-qualified ISO time")
            if not _substantive_human_text(row.get("result")):
                _err(errors, "L11-DISCOVERY-048", f"{path}.result", "closed stage needs a substantive human-readable summary; real referenced records remain the Gate authority")
            if status == "NOT_REQUIRED_WITH_REASON" and not _nonempty(row.get("reason")):
                _err(errors, "L11-DISCOVERY-033", f"{path}.reason", "NOT_REQUIRED_WITH_REASON requires a reason")
    if set(stage_by_name) != set(DISCOVERY_STAGE_TYPES):
        _err(errors, "L11-DISCOVERY-034", "discovery.stage_gates", f"must contain exactly one row for each stage {list(DISCOVERY_STAGE_TYPES)}")
    if stage_by_name.get("PRODUCT_TRUTH", {}).get("status") == "PASS" and "TRUTH" not in round_types:
        _err(errors, "L11-DISCOVERY-035", "discovery.stage_gates", "PRODUCT_TRUTH PASS requires a TRUTH round")
    if stage_by_name.get("ROUND_2", {}).get("status") == "PASS" and "POSITIONING" not in round_types:
        _err(errors, "L11-DISCOVERY-036", "discovery.stage_gates", "ROUND_2 PASS requires a POSITIONING round")
    all_strategy_stages_pass = (
        set(stage_by_name) == set(DISCOVERY_STAGE_TYPES)
        and all(stage_by_name[stage].get("status") == "PASS" for stage in DISCOVERY_STAGE_TYPES)
    )
    closed_times: list[datetime] = []
    for stage in DISCOVERY_STAGE_TYPES:
        value = stage_by_name.get(stage, {}).get("closed_at")
        if _isoish(value):
            closed_times.append(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    if len(closed_times) == len(DISCOVERY_STAGE_TYPES) and closed_times != sorted(closed_times):
        _err(errors, "L11-DISCOVERY-037", "discovery.stage_gates", "closed_at times must follow Recon -> Product Truth -> Round 2 -> Product Intent -> One-Bet order")
    closure = discovery.get("closure") if isinstance(discovery.get("closure"), dict) else {}
    closure_status = closure.get("status")
    if closure_status not in DISCOVERY_CLOSURES:
        _err(errors, "L11-DISCOVERY-011", "discovery.closure.status", "unsupported closure")
    if closure_status == "NOT_REQUIRED_WITH_REASON" and (not _nonempty(closure.get("reason")) or gates["evidence"] != "PASS"):
        _err(errors, "L11-DISCOVERY-012", "discovery.closure", "NOT_REQUIRED requires reason and complete evidence pass")
    expected_discovery_status = {
        "PASS": "COMPLETE",
        "NOT_REQUIRED_WITH_REASON": "NOT_REQUIRED_WITH_REASON",
        "CONDITIONAL": "CONDITIONAL",
        "BLOCKED": "BLOCKED",
        "IN_PROGRESS": "IN_PROGRESS",
        "NOT_STARTED": "NOT_STARTED",
    }.get(closure_status)
    if expected_discovery_status and discovery.get("status") != expected_discovery_status:
        _err(errors, "L11-DISCOVERY-023", "discovery.status", f"must equal {expected_discovery_status} for closure {closure_status}")
    open_p0_actions = [row for row in action_rows if row.get("status") == "OPEN" and response_index.get(row.get("response_id"), {}).get("p0_impact")]
    base_discovery_gate = evaluate_discovery(closure_status, len(open_p0_actions), gates["evidence"])
    if closure_status in {"PASS", "NOT_REQUIRED_WITH_REASON"} and not all_strategy_stages_pass:
        _err(errors, "L11-DISCOVERY-038", "discovery.closure", "closure cannot pass before all five discovery stages close")

    market = bundle.get("market_research") if isinstance(bundle.get("market_research"), dict) else {}
    if set(market) != MARKET_RESEARCH_KEYS:
        _err(errors, "L11-MARKET-002", "market_research", f"must contain exactly {sorted(MARKET_RESEARCH_KEYS)}")
    _refs(market.get("source_ids", []), set(source_index), "market_research.source_ids", errors)
    for key in ("voc_observations", "competitor_observations", "conclusions"):
        rows = _obj_list(market.get(key), f"market_research.{key}", errors)
        for index, row in enumerate(rows):
            path = f"market_research.{key}[{index}]"
            if set(row) != MARKET_RESEARCH_ROW_KEYS:
                _err(errors, "L11-MARKET-006", path, f"must contain exactly {sorted(MARKET_RESEARCH_ROW_KEYS)}")
            if not _nonempty(row.get("id")) or not _nonempty(row.get("statement")):
                _err(errors, "L11-MARKET-007", path, "id and statement are required")
            _refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors, nonempty=True)
            if not set(row.get("source_ids", [])).issubset(set(market.get("source_ids", []))):
                _err(errors, "L11-MARKET-008", f"{path}.source_ids", "row evidence must be included in market_research.source_ids")
    market_status = market.get("status")
    if market_status not in {"NOT_STARTED", "IN_PROGRESS", "COMPLETE", "NOT_REQUIRED_WITH_REASON", "BLOCKED"}:
        _err(errors, "L11-MARKET-003", "market_research.status", "unsupported status")
    if market_status == "COMPLETE":
        if not market.get("competitor_observations"):
            _err(errors, "L11-MARKET-009", "market_research.competitor_observations", "COMPLETE reconnaissance requires at least one source-bound competitor observation")
        if not market.get("voc_observations"):
            _err(errors, "L11-MARKET-010", "market_research.voc_observations", "COMPLETE reconnaissance requires at least one source-bound VOC observation")
        if (
            not market.get("source_ids")
            or any(not source_context_matches(source_index.get(item, {}), scope) for item in market.get("source_ids", []))
            or not market.get("conclusions")
            or not _nonempty(market.get("owner"))
        ):
            _err(errors, "L11-MARKET-004", "market_research", "COMPLETE requires owner, usable scoped sources, and at least one VOC observation, competitor observation, and conclusion")
    if market_status == "NOT_REQUIRED_WITH_REASON" and (
        not _nonempty(market.get("reason")) or not _nonempty(market.get("owner"))
    ):
        _err(errors, "L11-MARKET-005", "market_research.reason", "is required")
    gates["market_research"] = "PASS" if market_status in {"COMPLETE", "NOT_REQUIRED_WITH_REASON"} and not any("[L11-MARKET-" in item for item in errors) else "BLOCKED"
    recon_status = stage_by_name.get("RECONNAISSANCE", {}).get("status")
    if project.get("mode") == "rebuild" and (market_status != "COMPLETE" or recon_status != "PASS"):
        _err(errors, "L11-DISCOVERY-039", "discovery.stage_gates", "rebuild requires completed pre-interview market reconnaissance before Round 1")
    if project.get("mode") == "rebuild" and any(
        stage_by_name.get(stage, {}).get("status") != "PASS" for stage in DISCOVERY_STAGE_TYPES
    ):
        _err(errors, "L11-DISCOVERY-041", "discovery.stage_gates", "rebuild construction requires PASS for all five stages; NOT_REQUIRED_WITH_REASON may document a bounded audit but cannot open construction")

    market_row_ids = {
        str(row.get("id"))
        for key in ("voc_observations", "competitor_observations", "conclusions")
        for row in market.get(key, []) if isinstance(row, dict) and _nonempty(row.get("id"))
    }
    known_stage_refs = (
        {"market_research"}
        | {str(row.get("id")) for row in method_rows if _nonempty(row.get("id"))}
        | set(source_index)
        | set(observation_index)
        | set(round_index)
        | set(response_index)
        | set(distillation_index)
        | set(action_index)
        | set(fact_index)
        | set(claim_index)
        | set(conflict_index)
        | market_row_ids
        | {question_id for ids in question_ids_by_type.values() for question_id in ids}
    )
    for stage, row in stage_by_name.items():
        record_refs = set(row.get("record_refs", []))
        unknown_refs = record_refs - known_stage_refs
        if unknown_refs:
            _err(errors, "L11-DISCOVERY-040", f"discovery.stage_gates:{stage}.record_refs", f"unknown record refs {sorted(unknown_refs)!r}")
    if recon_status == "PASS":
        recon = stage_by_name["RECONNAISSANCE"]
        recon_refs = set(recon.get("record_refs", []))
        recon_sources = set(recon.get("evidence_source_ids", []))
        competitor_ids = {
            str(row.get("id")) for row in market.get("competitor_observations", [])
            if isinstance(row, dict) and _nonempty(row.get("id"))
        }
        voc_ids = {
            str(row.get("id")) for row in market.get("voc_observations", [])
            if isinstance(row, dict) and _nonempty(row.get("id"))
        }
        conclusion_ids = {
            str(row.get("id")) for row in market.get("conclusions", [])
            if isinstance(row, dict) and _nonempty(row.get("id"))
        }
        competitor_source_ids = {
            str(source_id)
            for row in market.get("competitor_observations", []) if isinstance(row, dict)
            for source_id in row.get("source_ids", [])
        }
        target_page_source_ids = {
            source_id for source_id in recon_sources
            if source_index.get(source_id, {}).get("type") in {
                "public_frontend", "amazon_detail_page", "target_product_page", "browser_capture",
            }
            and _amazon_product_asin(
                source_index.get(source_id, {}).get("locator"), scope.get("marketplace")
            ) in set(scope.get("intended_child_asins", []))
        }
        if (
            "market_research" not in recon_refs
            or not (recon_refs & competitor_ids)
            or not (recon_refs & voc_ids)
            or not (recon_refs & conclusion_ids)
            or not (recon_sources & competitor_source_ids)
            or not (recon_sources & set(evidence_pass.get("source_ids", [])))
            or not target_page_source_ids
            or not (recon_refs & target_page_source_ids)
        ):
            _err(errors, "L11-DISCOVERY-043", "discovery.stage_gates:RECONNAISSANCE", "PASS requires a target-page census ref/source, market record, competitor/VOC/conclusion refs, competitor evidence, and target-audit evidence")
    truth_refs = set(stage_by_name.get("PRODUCT_TRUTH", {}).get("record_refs", []))
    if stage_by_name.get("PRODUCT_TRUTH", {}).get("status") == "PASS" and not (
        truth_refs & round_ids_by_type["TRUTH"]
        and truth_refs & distillation_ids_by_type["TRUTH"]
        and truth_refs & set(fact_index)
    ):
        _err(errors, "L11-DISCOVERY-040", "discovery.stage_gates:PRODUCT_TRUTH", "PASS requires a TRUTH round ref, a TRUTH-derived distillation ref, and a Fact ref")
    round_two_refs = set(stage_by_name.get("ROUND_2", {}).get("record_refs", []))
    strategic_choice_ids = {
        response_id for response_id in response_ids_by_type["POSITIONING"]
        if response_index.get(response_id, {}).get("classification") == "STRATEGIC_CHOICE"
    }
    if stage_by_name.get("ROUND_2", {}).get("status") == "PASS" and not (
        round_two_refs & round_ids_by_type["POSITIONING"]
        and round_two_refs & strategic_choice_ids
        and round_two_refs & distillation_ids_by_type["POSITIONING"]
    ):
        _err(errors, "L11-DISCOVERY-040", "discovery.stage_gates:ROUND_2", "PASS requires a POSITIONING round ref, a strategic-choice response ref, and its positioning distillation ref")
    def typed_positioning_chain_is_bound(record_id: str, stage_refs: set[str]) -> bool:
        record = distillation_index.get(record_id, {})
        response_ids = set(record.get("response_ids", []))
        fact_ids = set(record.get("fact_ids", []))
        if (
            not response_ids
            or not fact_ids
            or not response_ids.issubset(response_ids_by_type["POSITIONING"])
            or any(response_id not in question_id_by_response for response_id in response_ids)
            or any(response_id not in round_id_by_response for response_id in response_ids)
        ):
            return False
        required_refs = (
            {record_id}
            | response_ids
            | {question_id_by_response[response_id] for response_id in response_ids}
            | {round_id_by_response[response_id] for response_id in response_ids}
            | fact_ids
        )
        return required_refs.issubset(stage_refs)

    intent_refs = set(stage_by_name.get("PRODUCT_INTENT_BRIEF", {}).get("record_refs", []))
    bound_intent_record_ids = {
        record_id for record_id in typed_distillation_ids["PRODUCT_INTENT_BRIEF"]
        if typed_positioning_chain_is_bound(record_id, intent_refs)
    }
    if stage_by_name.get("PRODUCT_INTENT_BRIEF", {}).get("status") == "PASS" and not bound_intent_record_ids:
        _err(
            errors, "L11-DISCOVERY-049", "discovery.stage_gates:PRODUCT_INTENT_BRIEF",
            "PASS requires one bound chain: typed Product Intent record, POSITIONING round, native question/response, and that record's current-product Facts",
        )
    one_bet_refs = set(stage_by_name.get("ONE_BET", {}).get("record_refs", []))
    selected_choice_ids = {
        response_id for response_id in strategic_selection_response_ids
        if response_index.get(response_id, {}).get("classification") == "STRATEGIC_CHOICE"
    }
    selected_distillation_ids = {
        distillation_id for distillation_id, row in distillation_index.items()
        if set(row.get("response_ids", [])) & selected_choice_ids
    }
    typed_one_bet_ids = typed_distillation_ids["ONE_BET_SELECTION"] & selected_distillation_ids
    if stage_by_name.get("ONE_BET", {}).get("status") == "PASS" and not (
        one_bet_refs & strategic_selection_question_ids
        and one_bet_refs & selected_choice_ids
        and one_bet_refs & typed_one_bet_ids
    ):
        _err(errors, "L11-DISCOVERY-046", "discovery.stage_gates:ONE_BET", "PASS requires a STRATEGIC_SELECTION question, its strategic-choice response, and a typed One-Bet Selection record")
    bound_one_bet_record_ids = {
        record_id for record_id in typed_one_bet_ids
        if typed_positioning_chain_is_bound(record_id, one_bet_refs)
    }
    if stage_by_name.get("ONE_BET", {}).get("status") == "PASS" and not bound_one_bet_record_ids:
        _err(
            errors, "L11-DISCOVERY-049", "discovery.stage_gates:ONE_BET",
            "PASS requires one bound chain: typed One-Bet record, POSITIONING round, STRATEGIC_SELECTION question/response, and that record's current-product Facts",
        )
    if stage_by_name.get("ONE_BET", {}).get("status") == "PASS" and not any(
        one_bet_proof_by_id.get(record_id) == "PROVED"
        for record_id in bound_one_bet_record_ids
    ):
        _err(errors, "L11-DISCOVERY-047", "discovery.stage_gates:ONE_BET", "PASS and consumer construction require the selected route proof_status to be PROVED")
    gates["discovery"] = "PASS" if (
        base_discovery_gate == "PASS"
        and all_strategy_stages_pass
        and gates["market_research"] == "PASS"
        and not any("[L11-DISCOVERY-" in item for item in errors)
    ) else "BLOCKED"

    return DiscoveryReport(
        delta=PhaseDelta.capture(errors, warnings, counts, gates),
        discovery=discovery,
        closure=closure,
        market_research=market,
    )
