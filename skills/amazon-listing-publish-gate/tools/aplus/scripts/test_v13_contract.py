#!/usr/bin/env python3
from __future__ import annotations

import copy
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import test_validate_bundle as legacy
from aplus_entry_domain import (
    authorization_action_issues,
    authorization_target_issue,
    authorization_time_issues,
    derive_result_level,
    local_parent_reference_issue,
    migration_path_issue,
    publication_entry_issues,
    required_pass_gate_ids,
    validator_exit_code,
)
from aplus_v13_domain import canonical_handoff_snapshot_id
from aplus_publication_reports import (
    build_publication_report,
    build_readback_coverage_report,
    build_readback_row_report,
)
from aplus_v13_reports import build_fact_evidence_report
from aplus_v13_lineage import build_lineage_record, canonical_lineage_record_hash
from migrate_aplus_bundle import migrate
from render_aplus_report import render
from validate_bundle import canonical_handoff_hash, canonical_object_hash, validate_bundle


def valid_v13() -> dict:
    bundle = legacy.upgrade_v12()
    bundle["schema_version"] = "1.3"
    bundle["sources"].append(legacy.source(
        "SRC-COMP", "COMPETITOR_ONLY", "https://www.amazon.com/dp/B0COMPET01",
        source_scope=legacy.app_scope(child="B0COMPET01", parent=None),
    ))
    bundle["sources"].append(legacy.source(
        "SRC-VOC", "VOC_ONLY", "https://www.amazon.com/dp/B0EXAMPLE1#customerReviews",
    ))
    bundle["competitor_insights"] = [{
        "id": "COMP-1", "competitor_role": "direct",
        "marketplace": bundle["project"]["marketplace"],
        "locale": bundle["project"]["locale"], "child_asin": "B0COMPET01",
        "observed_at": "2026-08-28T00:20:00+08:00", "fetch_status": "ok",
        "status": "FROZEN", "copying_prohibited": True,
        "source_ids": ["SRC-COMP"], "target_verified_difference_fact_ids": [],
        "category_parity": ["Same buyer decision category."],
        "decision_gaps": ["Competitor research establishes the comparison set, not target truth."],
        "claim_risks": ["Do not copy or convert competitor claims into target facts."],
        "borrowable_structural_patterns": ["Answer the high-friction decision early."],
    }]
    bundle["voc_insights"] = [{
        "id": "VOC-1",
        "observation": "Buyers ask what is included before they commit to the selected child.",
        "buyer_question": "What exactly arrives with this selected product?",
        "use_path": "The shopper checks included items before comparing secondary performance claims.",
        "decision_implication": "The page should answer included quantity early without converting VOC into target-product proof.",
        "source_ids": ["SRC-VOC"],
        "marketplace": bundle["project"]["marketplace"],
        "locale": bundle["project"]["locale"],
        "observed_at": "2026-08-28T00:25:00+08:00",
        "fetch_status": "ok",
        "status": "FROZEN",
        "target_product_proof_prohibited": True,
        "owner": "Research owner",
    }]
    bundle["category_adapter"] = {
        "id": "generic", "status": "SELECTED",
        "investigation_prompts": ["Verify the included item."],
        "evidence_probes": ["Inspect the scoped product specification."],
        "return_risks": ["Wrong included-item expectation."],
        "qa_checks": ["Answer and image match the selected child."],
        "owner": "Strategy",
    }
    for fact in bundle["facts"]:
        fact["fact_class"] = "PHYSICAL_PRODUCT" if fact["id"] == "FACT-1" else "PERFORMANCE"
    bundle["enriched_content_handoff"].update({
        "contract_version": "1.1",
        "maximum_output": "strategy_dependency_only",
        "discovery_closure_hash": "",
        "ptd_inventory_hash": "",
        "decision_denominator_hash": "",
        "canonical_assertion_ids": [],
        "requirement_atoms": [],
        "predecessor_snapshot_id": "",
        "semantic_revision": 0,
        "refreeze_reason": "",
        "lineage_registry": [],
    })
    variant = bundle["variants"][0]
    variant["id"] = "V-1"
    module = bundle["modules"][0]
    requirement_id = module["id"]
    requirement = {
        "id": requirement_id,
        "buyer_question": module["decision_question"],
        "priority": "P0",
        "application_scope": {
            "parent_asins": [variant["parent_asin"]],
            "child_asins": [variant["child_asin"]],
            "packs": [variant["pack"]],
            "colors": [variant["color"]],
            "sizes": [variant["size_or_capacity"]],
        },
        "fact_ids": copy.deepcopy(module["fact_ids"]),
        "claim_ids": copy.deepcopy(module["claim_ids"]),
        "native_answer_required": True,
        "early_disclosure_required": False,
        "upstream_primary_carrier_ref": "",
        "assigned_surface": "enriched_content",
        "status": "READY",
    }
    atom = {
        "id": "ATOM-1",
        "requirement_id": requirement_id,
        "marketplace": bundle["project"]["marketplace"],
        "locale": bundle["project"]["locale"],
        "variant_row_id": "V-1",
    }
    assertion = {
        "id": "ASSERT-1",
        "statement": "One device is included.",
        "application_scope": copy.deepcopy(module["application_scope"]),
        "variant_row_ids": ["V-1"],
        "fact_ids": copy.deepcopy(module["fact_ids"]),
        "claim_ids": copy.deepcopy(module["claim_ids"]),
        "locale_expressions": [{"locale": bundle["project"]["locale"], "text": "One device is included.", "fact_ids": copy.deepcopy(module["fact_ids"]), "claim_ids": copy.deepcopy(module["claim_ids"])}],
        "publish_status": "PUBLISHABLE",
        "owner": "Content QA",
    }
    denominator = {
        "status": "FROZEN",
        "source": "STANDALONE",
        "source_hash": "",
        "frozen_at": "2026-08-28T01:00:00+08:00",
        "requirement_ids": [requirement_id],
        "variant_row_ids": ["V-1"],
        "atoms": [atom],
        "checksum": "",
    }
    denominator["checksum"] = canonical_object_hash(denominator)
    bundle["decision_denominator_snapshot"] = denominator
    bundle["decision_map"]["requirements"] = [requirement]
    bundle["canonical_assertions"] = [assertion]
    bundle["discovery"] = {
        "mode": "standalone",
        "evidence_pass": {"status": "COMPLETE", "source_ids": ["SRC-SPEC"], "observations": ["Included quantity verified."], "owner": "Research"},
        "stage_gates": [
            {"id": "STAGE-RECONNAISSANCE", "stage": "RECONNAISSANCE", "status": "PASS", "result": "Target page, competitor set, and VOC use path were inspected before interviewing.", "evidence_source_ids": ["SRC-PDP-BASE", "SRC-COMP", "SRC-VOC"], "record_refs": ["COMP-1", "VOC-1", "SRC-PDP-BASE"], "reason": "", "closed_at": "2026-08-28T00:30:00+08:00", "owner": "Research"},
            {"id": "STAGE-PRODUCT_TRUTH", "stage": "PRODUCT_TRUTH", "status": "PASS", "result": "Round 1 and product truth are closed.", "evidence_source_ids": ["SRC-SPEC"], "record_refs": ["ROUND-1", "D-1"], "reason": "", "closed_at": "2026-08-28T01:00:00+08:00", "owner": "Research"},
            {"id": "STAGE-ROUND_2", "stage": "ROUND_2", "status": "PASS", "result": "Round 2 selected the high-value decision and boundary.", "evidence_source_ids": ["SRC-SPEC", "SRC-COMP"], "record_refs": ["ROUND-2", "D-2"], "reason": "", "closed_at": "2026-08-28T01:02:00+08:00", "owner": "Strategy"},
            {"id": "STAGE-PRODUCT_INTENT_BRIEF", "stage": "PRODUCT_INTENT_BRIEF", "status": "PASS", "result": "Product intent, designed tradeoff, and wrong job are explicit.", "evidence_source_ids": ["SRC-SPEC", "SRC-COMP"], "record_refs": ["ROUND-2", "Q-2", "D-3", "FACT-1", "FACT-2"], "reason": "", "closed_at": "2026-08-28T01:03:00+08:00", "owner": "Strategy"},
            {"id": "STAGE-ONE_BET", "stage": "ONE_BET", "status": "PASS", "result": "One reversible market bet is selected for construction.", "evidence_source_ids": ["SRC-SPEC", "SRC-COMP"], "record_refs": ["ROUND-2", "Q-2", "D-4", "FACT-1", "FACT-2", requirement_id], "reason": "", "closed_at": "2026-08-28T01:04:00+08:00", "owner": "Strategy"},
        ],
        "interview_rounds": [
            {
                "id": "ROUND-1", "phase": "TRUTH", "owner": "Research",
                "questions": [{
                    "id": "Q-1", "question": "What is included?", "decision_effects": ["EVIDENCE"],
                    "answer": "One device.", "response_class": "FACT_LEAD",
                    "affected_requirement_ids": [requirement_id], "owner": "Research",
                }],
            },
            {
                "id": "ROUND-2", "phase": "POSITIONING", "owner": "Strategy",
                "questions": [{
                    "id": "Q-2", "question": "Which buyer decision should this content win first?",
                    "decision_effects": ["AUDIENCE", "SCENARIO", "PROMISE", "BOUNDARY", "STRATEGIC_SELECTION"],
                    "answer": "Help the scoped buyer choose the correct included item without overstating performance.",
                    "response_class": "STRATEGIC_CHOICE",
                    "affected_requirement_ids": [requirement_id], "owner": "Strategy",
                }],
            },
        ],
        "distillations": [
            {
                "id": "D-1", "record_type": "PRODUCT_TRUTH", "payload": {"coverage": "Included quantity is verified."}, "question_ids": ["Q-1"], "result_type": "FACT_LEAD",
                "statement": "One device is included.", "fact_ids": copy.deepcopy(module["fact_ids"]),
                "claim_ids": copy.deepcopy(module["claim_ids"]), "evidence_action_ids": [], "owner": "Research",
            },
            {
                "id": "D-2", "record_type": "ROUND_2_SYNTHESIS", "payload": {"decision": "Included-item clarity is the lead decision."}, "question_ids": ["Q-2"], "result_type": "STRATEGIC_CHOICE",
                "statement": "Lead with the included-item decision and its tested boundary.",
                "fact_ids": copy.deepcopy(module["fact_ids"]), "claim_ids": copy.deepcopy(module["claim_ids"]),
                "evidence_action_ids": [], "owner": "Strategy",
            },
            {
                "id": "D-3", "record_type": "PRODUCT_INTENT_BRIEF", "payload": {
                    "original_problem": "Buyers could not confirm the included item before purchase.",
                    "prior_alternative": "Infer contents from imagery or category convention.",
                    "chosen_form": "Use a native scoped answer for the included item.",
                    "deliberate_tradeoff": "Prioritize decision clarity over an unproven broad performance lead.",
                    "intended_mechanism": "The direct answer removes an avoidable inference step.",
                    "longitudinal_observation": "Current research repeatedly exposed included-item ambiguity as a risk.",
                    "alternative_explanations": "Price and performance can matter but do not answer what arrives.",
                    "current_version_continuity": "The verified current product still contains one device.",
                    "current_choice": "Lead with exact included-item clarity."
                }, "question_ids": ["Q-2"], "result_type": "STRATEGIC_CHOICE",
                "statement": "The product intent is to make the scoped included-item decision explicit.",
                "fact_ids": copy.deepcopy(module["fact_ids"]), "claim_ids": copy.deepcopy(module["claim_ids"]),
                "evidence_action_ids": [], "owner": "Strategy",
            },
            {
                "id": "D-4", "record_type": "ONE_BET_SELECTION", "payload": {
                    "selected_route_id": "ROUTE-INCLUDED-ITEM-CLARITY",
                    "hero_moment": "The buyer checks what arrives before committing.",
                    "closest_alternative": "A generic category page that leaves contents to inference.",
                    "desired_progress": "Choose the correct item without a preventable contents surprise.",
                    "mechanism": "A native scoped statement answers the included-item question directly.",
                    "material_boundary": "This route proves contents, not comparative performance.",
                    "rejected_route_ids": ["ROUTE-PERFORMANCE-LEAD"],
                    "rejected_route_reasons": {"ROUTE-PERFORMANCE-LEAD": "No comparative evidence supports that lead."},
                    "proof_status": "PROVED",
                    "reversibility_test": "Run one controlled content test and revert if purchase-quality guardrails worsen.",
                    "route_registry": [{
                        "route_id": "ROUTE-INCLUDED-ITEM-CLARITY",
                        "core_user_or_state": "A buyer who must confirm exactly what arrives before purchase.",
                        "hero_moment": "The buyer checks what arrives before committing.",
                        "closest_alternative": "A generic category page that leaves contents to inference.",
                        "desired_progress": "Choose the correct item without a preventable contents surprise.",
                        "mechanism": "A native scoped statement answers the included-item question directly.",
                        "material_boundary": "This route proves contents, not comparative performance.",
                        "proof_status": "PROVED",
                        "decision_consequence": "Lead the first-screen decision with exact included-item clarity."
                    }, {
                        "route_id": "ROUTE-PERFORMANCE-LEAD",
                        "core_user_or_state": "A buyer comparing performance among otherwise similar products.",
                        "hero_moment": "The buyer compares verified performance before choosing a product.",
                        "closest_alternative": "A competitor backed by comparative performance evidence.",
                        "desired_progress": "Choose the strongest performer for the intended task.",
                        "mechanism": "A comparative performance claim would carry the purchase decision.",
                        "material_boundary": "No comparative evidence currently supports this target route.",
                        "proof_status": "UNSUPPORTED",
                        "decision_consequence": "Reject this route until comparative evidence is established."
                    }]
                }, "question_ids": ["Q-2"], "result_type": "STRATEGIC_CHOICE",
                "statement": "Select included-item clarity as the single reversible market bet.",
                "fact_ids": copy.deepcopy(module["fact_ids"]), "claim_ids": copy.deepcopy(module["claim_ids"]),
                "evidence_action_ids": [], "owner": "Strategy",
            },
        ],
        "evidence_actions": [],
        "closure": {"status": "PASS", "closed_at": "2026-08-28T01:05:00+08:00", "owner": "Research", "reason": "Material gaps closed."},
    }
    answer = bundle["decision_answer_units"][0]
    answer.update({"requirement_atom_id": "ATOM-1", "variant_row_id": "V-1", "canonical_assertion_ids": ["ASSERT-1"]})
    carrier = bundle["carriers"][0]
    carrier.update({"variant_row_ids": ["V-1"], "canonical_assertion_ids": ["ASSERT-1"]})
    for asset in bundle["assets"]:
        asset.update({"variant_row_ids": ["V-1"], "canonical_assertion_ids": ["ASSERT-1"]})
    bundle["coverage_summary"].update({"p0_atoms_required": 1, "p0_atoms_pass": 1, "gap_atom_ids": []})
    bundle["component_result"] = {
        "status": "COMPONENT_PASS", "gap_atom_ids": [], "open_delta_request_ids": [],
        "page_pass_implied": False, "publication_authorized": False, "owner": "Content QA",
    }
    return bundle


def valid_v13_embedded() -> dict:
    bundle = valid_v13()
    requirement_rows = copy.deepcopy(bundle["decision_map"]["requirements"])
    atom_rows = copy.deepcopy(bundle["decision_denominator_snapshot"]["atoms"])
    bundle["workflow_context"] = {
        "mode": "embedded", "parent_bundle_ref": "frozen-parent.json",
        "accepted_handoff_snapshot_id": "", "accepted_at": "2026-08-28T02:05:00+08:00",
        "accepted_by": "A+ owner", "execution_boundary": "read_only",
    }
    bundle["category_adapter"]["status"] = "PARENT_BOUND"
    bundle["discovery"] = {
        "mode": "parent_bound",
        "evidence_pass": {"status": "COMPLETE", "source_ids": ["SRC-SPEC"], "observations": ["Bound to frozen parent evidence."], "owner": "A+ owner"},
        "stage_gates": [
            {"id": f"STAGE-{stage}", "stage": stage, "status": "NOT_REQUIRED_WITH_REASON", "result": "The frozen parent handoff supplies this governed stage.", "evidence_source_ids": ["SRC-SPEC"], "record_refs": ["PARENT_HANDOFF"], "reason": "Embedded A+ must consume the frozen parent result rather than repeat or change it.", "closed_at": f"2026-08-28T01:0{index}:00+08:00", "owner": "A+ owner"}
            for index, stage in enumerate(("RECONNAISSANCE", "PRODUCT_TRUTH", "ROUND_2", "PRODUCT_INTENT_BRIEF", "ONE_BET"))
        ],
        "interview_rounds": [], "distillations": [], "evidence_actions": [],
        "closure": {"status": "NOT_REQUIRED_WITH_REASON", "closed_at": "", "owner": "A+ owner", "reason": "Frozen parent discovery is authoritative."},
    }
    parent_hash = "sha256:" + "a" * 64
    bundle["decision_denominator_snapshot"].update({"source": "PARENT_HANDOFF", "source_hash": parent_hash, "checksum": ""})
    bundle["decision_denominator_snapshot"]["checksum"] = canonical_object_hash(bundle["decision_denominator_snapshot"])
    variant = bundle["variants"][0]
    module = bundle["modules"][0]
    bundle["enriched_content_handoff"] = {
        "contract_version": "1.1", "snapshot_id": "", "parent_project_id": "PARENT-1",
        "parent_bundle_sha256": "sha256:" + "b" * 64, "status": "FROZEN",
        "maximum_output": "preflight_package", "marketplace": bundle["project"]["marketplace"],
        "locale": bundle["project"]["locale"], "product_type": "DEVICE",
        "application_scope": {"parent_asins": [variant["parent_asin"]], "child_asins": [variant["child_asin"]], "packs": [variant["pack"]], "colors": [variant["color"]], "sizes": [variant["size_or_capacity"]]},
        "variant_row_ids": ["V-1"], "fact_ids": copy.deepcopy(module["fact_ids"]),
        "claim_ids": copy.deepcopy(module["claim_ids"]), "blocked_claim_ids": [], "conflict_ids": [],
        "source_ids": ["SRC-SPEC", "SRC-TEST", "SRC-BACKEND"], "requested_content_types": ["PREMIUM_A_PLUS"],
        "decision_requirements": requirement_rows, "capability_snapshot_ids": ["CAP-1"],
        "discovery_closure_hash": "sha256:" + "c" * 64, "ptd_inventory_hash": "sha256:" + "d" * 64,
        "decision_denominator_hash": parent_hash, "canonical_assertion_ids": ["ASSERT-1"],
        "requirement_atoms": atom_rows,
        "prohibited_actions": ["modify_parent_truth", "expand_application_scope", "online_submission"],
        "predecessor_snapshot_id": "", "semantic_revision": 1, "refreeze_reason": "",
        "lineage_registry": [],
        "created_at": "2026-08-28T02:00:00+08:00", "owner": "Parent owner", "checksum": "",
    }
    bundle["enriched_content_handoff"]["snapshot_id"] = canonical_handoff_snapshot_id(
        bundle["enriched_content_handoff"]
    )
    bundle["workflow_context"]["accepted_handoff_snapshot_id"] = bundle["enriched_content_handoff"]["snapshot_id"]
    bundle["enriched_content_handoff"]["checksum"] = canonical_handoff_hash(bundle["enriched_content_handoff"])
    return bundle


def refrozen_v13_embedded() -> dict:
    previous = valid_v13_embedded()
    bundle = valid_v13_embedded()
    handoff = bundle["enriched_content_handoff"]
    handoff.update({
        "semantic_revision": 2,
        "predecessor_snapshot_id": previous["enriched_content_handoff"]["snapshot_id"],
        "refreeze_reason": "Parent evidence delta resolved and the frozen snapshot was replaced.",
        "lineage_registry": [build_lineage_record(
            previous["enriched_content_handoff"],
            successor_snapshot_id="",
            superseded_at="2026-08-28T02:10:00+08:00",
        )],
        "created_at": "2026-08-28T02:20:00+08:00",
        "snapshot_id": "",
        "checksum": "",
    })
    handoff["snapshot_id"] = canonical_handoff_snapshot_id(handoff)
    handoff["lineage_registry"][0]["successor_snapshot_id"] = handoff["snapshot_id"]
    handoff["lineage_registry"][0]["record_checksum"] = canonical_lineage_record_hash(
        handoff["lineage_registry"][0]
    )
    handoff["checksum"] = canonical_handoff_hash(handoff)
    bundle["workflow_context"].update({
        "accepted_handoff_snapshot_id": handoff["snapshot_id"],
        "accepted_at": "2026-08-28T02:25:00+08:00",
    })
    return bundle


def errors(result: dict) -> str:
    return "\n".join(result["errors"])


def add_valid_alternate_positioning_question(bundle: dict) -> str:
    """Add a second legal carrier so relation-chain substitution can be tested."""
    question_id = "Q-ALT"
    requirement_id = bundle["decision_map"]["requirements"][0]["id"]
    positioning_round = next(
        row for row in bundle["discovery"]["interview_rounds"] if row["phase"] == "POSITIONING"
    )
    positioning_round["questions"].append({
        "id": question_id,
        "question": "Should the alternate supported route lead the purchase decision?",
        "decision_effects": ["AUDIENCE", "PROMISE", "BOUNDARY", "STRATEGIC_SELECTION"],
        "answer": "Keep the alternate route documented, but do not select it for the current build.",
        "response_class": "STRATEGIC_CHOICE",
        "affected_requirement_ids": [requirement_id],
        "owner": "Strategy",
    })
    bundle["discovery"]["distillations"].append({
        "id": "D-ALT",
        "record_type": "ROUND_2_SYNTHESIS",
        "payload": {"decision": "The alternate route remains a documented rejected option."},
        "question_ids": [question_id],
        "result_type": "STRATEGIC_CHOICE",
        "statement": "The alternate route is not the selected strategy.",
        "fact_ids": ["FACT-2"],
        "claim_ids": ["CLAIM-2"],
        "evidence_action_ids": [],
        "owner": "Strategy",
    })
    return question_id


def mark_atom_gap(bundle: dict, *, component_status: str, delta_ids: list[str] | None = None) -> None:
    requirement_id = bundle["decision_map"]["requirements"][0]["id"]
    bundle["project"]["conclusion"] = "CONDITIONAL_PASS"
    bundle["decision_answer_units"][0].update({"content_status": "CONDITIONAL_DRAFT", "qa_status": "HOLD"})
    bundle["coverage_summary"].update({
        "status": "GAP", "p0_pass": 0, "gap_requirement_ids": [requirement_id],
        "p0_atoms_pass": 0, "gap_atom_ids": ["ATOM-1"],
    })
    bundle["component_result"].update({
        "status": component_status, "gap_atom_ids": ["ATOM-1"],
        "open_delta_request_ids": list(delta_ids or []),
    })


def parent_evidence_delta(bundle: dict) -> dict:
    handoff = bundle["enriched_content_handoff"]
    return {
        "id": "DELTA-1", "question": "Verify the parent-owned product limit.",
        "affected_requirement_ids": [bundle["decision_map"]["requirements"][0]["id"]],
        "affected_atom_ids": ["ATOM-1"], "affected_fact_ids": [],
        "affected_claim_ids": [], "affected_module_ids": [bundle["modules"][0]["id"]],
        "decisive_evidence": "Parent-verified scoped specification.",
        "gap_type": "PARENT_EVIDENCE",
        "handoff_lineage": {
            "snapshot_id": handoff["snapshot_id"],
            "parent_bundle_sha256": handoff["parent_bundle_sha256"],
            "discovery_closure_hash": handoff["discovery_closure_hash"],
            "ptd_inventory_hash": handoff["ptd_inventory_hash"],
            "decision_denominator_hash": handoff["decision_denominator_hash"],
            "handoff_checksum": handoff["checksum"],
        },
        "owner": "Parent owner", "status": "OPEN",
    }


class APlusV13Tests(unittest.TestCase):
    def test_valid_standalone_component_passes(self):
        result = validate_bundle(valid_v13())
        self.assertTrue(result["ok"], errors(result))
        self.assertEqual(result["result_level"], "COMPONENT_PASS")
        self.assertTrue(result["atom_coverage_assessed"])
        self.assertTrue(result["structural_valid"])
        self.assertFalse(result["page_pass_implied"])

    def test_consumer_candidates_are_forbidden_before_one_bet_closes(self):
        bundle = valid_v13()
        one_bet = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "ONE_BET")
        one_bet.update({"status": "IN_PROGRESS", "result": "", "record_refs": [], "closed_at": ""})
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-PHASE-002]", errors(result))
        self.assertIn("[A13-PHASE-003]", errors(result))

    def test_round_two_gate_cannot_pass_without_positioning_round(self):
        bundle = valid_v13()
        bundle["discovery"]["interview_rounds"] = [
            row for row in bundle["discovery"]["interview_rounds"] if row["phase"] != "POSITIONING"
        ]
        bundle["discovery"]["distillations"] = [
            row for row in bundle["discovery"]["distillations"] if row["id"] != "D-2"
        ]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-015]", errors(result))

    def test_reconnaissance_requires_a_usable_competitor_insight(self):
        bundle = valid_v13()
        bundle["competitor_insights"] = []
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-012]", errors(result))

    def test_reconnaissance_requires_a_usable_voc_use_path_insight(self):
        bundle = valid_v13()
        bundle["voc_insights"] = []
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-024]", errors(result))

    def test_reconnaissance_requires_selected_child_target_pdp_census(self):
        bundle = valid_v13()
        recon = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "RECONNAISSANCE")
        recon["evidence_source_ids"] = ["SRC-SPEC", "SRC-COMP"]
        recon["record_refs"] = ["SRC-SPEC", "COMP-1"]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-022]", errors(result))

    def test_stage_gate_rejects_ghost_record_refs(self):
        bundle = valid_v13()
        intent = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "PRODUCT_INTENT_BRIEF")
        intent["record_refs"] = ["GHOST-NODE"]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-019]", errors(result))

    def test_product_intent_requires_typed_complete_payload(self):
        bundle = valid_v13()
        intent_record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-3")
        intent_record["payload"].pop("current_choice")
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-020]", errors(result))

    def test_product_intent_rejects_semantic_placeholders(self):
        bundle = valid_v13()
        intent_record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-3")
        intent_record["payload"] = {key: "x" for key in intent_record["payload"]}
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-020]", errors(result))

    def test_typed_strategy_records_require_nonempty_current_fact_ids(self):
        for record_id, error_code in (("D-3", "A13-STAGE-020"), ("D-4", "A13-STAGE-021")):
            for case, fact_ids in (("empty", []), ("unknown", ["FACT-GHOST"])):
                with self.subTest(record_id=record_id, case=case):
                    bundle = valid_v13()
                    record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == record_id)
                    record["fact_ids"] = fact_ids
                    result = validate_bundle(bundle)
                    self.assertFalse(result["ok"])
                    self.assertIn(f"[{error_code}]", errors(result))

    def test_product_intent_stage_rejects_unrelated_legal_fact_or_question_carrier(self):
        for case in ("fact", "question", "round"):
            with self.subTest(case=case):
                bundle = valid_v13()
                intent_record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-3")
                intent_stage = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "PRODUCT_INTENT_BRIEF")
                if case == "fact":
                    intent_record["fact_ids"] = ["FACT-1"]
                    intent_stage["record_refs"] = ["ROUND-2", "Q-2", "D-3", "FACT-2"]
                else:
                    if case == "question":
                        alternate_question_id = add_valid_alternate_positioning_question(bundle)
                        intent_stage["record_refs"] = [
                            "ROUND-2", alternate_question_id, "D-3", "FACT-1", "FACT-2",
                        ]
                    else:
                        intent_stage["record_refs"] = ["Q-2", "D-3", "FACT-1", "FACT-2"]
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("[A13-STAGE-020]", errors(result))

    def test_one_bet_requires_typed_route_rejection_and_reversible_test(self):
        bundle = valid_v13()
        one_bet_record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-4")
        one_bet_record["payload"]["reversibility_test"] = ""
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-021]", errors(result))

    def test_one_bet_rejects_ghost_route_and_unsupported_selected_proof(self):
        for mutation in ("ghost", "unsupported"):
            with self.subTest(mutation=mutation):
                bundle = valid_v13()
                record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-4")
                if mutation == "ghost":
                    record["payload"]["selected_route_id"] = "GHOST-ROUTE"
                else:
                    record["payload"]["proof_status"] = "UNSUPPORTED"
                    record["payload"]["route_registry"][0]["proof_status"] = "UNSUPPORTED"
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("[A13-STAGE-021]", errors(result))

    def test_one_bet_stage_rejects_unrelated_legal_fact_or_question_carrier(self):
        for case in ("fact", "question", "round", "requirement"):
            with self.subTest(case=case):
                bundle = valid_v13()
                requirement_id = bundle["decision_map"]["requirements"][0]["id"]
                one_bet_record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-4")
                one_bet_stage = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "ONE_BET")
                if case == "fact":
                    one_bet_record["fact_ids"] = ["FACT-1"]
                    one_bet_stage["record_refs"] = ["ROUND-2", "Q-2", "D-4", "FACT-2", requirement_id]
                elif case == "question":
                    alternate_question_id = add_valid_alternate_positioning_question(bundle)
                    one_bet_stage["record_refs"] = [
                        "ROUND-2", alternate_question_id, "D-4", "FACT-1", "FACT-2", requirement_id,
                    ]
                elif case == "round":
                    one_bet_stage["record_refs"] = [
                        "Q-2", "D-4", "FACT-1", "FACT-2", requirement_id,
                    ]
                else:
                    strategic_question = next(
                        question
                        for round_row in bundle["discovery"]["interview_rounds"]
                        for question in round_row["questions"]
                        if question["id"] == "Q-2"
                    )
                    strategic_question["affected_requirement_ids"] = []
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("[A13-STAGE-021]", errors(result))

    def test_voc_insight_rejects_missing_or_extra_keys(self):
        for case in ("missing", "extra"):
            with self.subTest(case=case):
                bundle = valid_v13()
                if case == "missing":
                    bundle["voc_insights"][0].pop("use_path")
                else:
                    bundle["voc_insights"][0]["unexpected"] = "not allowed"
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("[A13-STAGE-024]", errors(result))

    def test_current_template_has_exact_usable_voc_insight_shape(self):
        expected_keys = {
            "id", "observation", "buyer_question", "use_path", "decision_implication",
            "source_ids", "marketplace", "locale", "observed_at", "fetch_status",
            "status", "target_product_proof_prohibited", "owner",
        }
        template_path = Path(__file__).resolve().parents[1] / "assets" / "aplus-project-bundle-template.json"
        template = json.loads(template_path.read_text(encoding="utf-8"))
        template_row = template["record_templates"]["voc_insight"]
        self.assertEqual(len(template_row), 13)
        self.assertEqual(set(template_row), expected_keys)

        bundle = valid_v13()
        populated_row = copy.deepcopy(template_row)
        populated_row.update(copy.deepcopy(bundle["voc_insights"][0]))
        bundle["voc_insights"] = [populated_row]
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], errors(result))

    def test_placeholder_strategic_answer_cannot_close_one_bet(self):
        bundle = valid_v13()
        strategic_question = next(
            question
            for round_row in bundle["discovery"]["interview_rounds"]
            for question in round_row["questions"]
            if question["id"] == "Q-2"
        )
        strategic_question["answer"] = "x"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-023]", errors(result))

    def test_placeholder_stage_result_cannot_fake_discovery_pass(self):
        bundle = valid_v13()
        one_bet = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "ONE_BET")
        one_bet["result"] = "x"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-023]", errors(result))

    def test_one_bet_closure_requires_one_supported_positioning_route(self):
        bundle = valid_v13()
        bundle["positioning"].update({"status": "UNKNOWN", "statement": ""})
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-STAGE-018]", errors(result))

    def test_valid_embedded_uses_only_frozen_child_contract(self):
        result = validate_bundle(valid_v13_embedded())
        self.assertTrue(result["ok"], errors(result))
        self.assertEqual(result["result_level"], "COMPONENT_PASS")
        self.assertIsNone(result["parent_bundle_verified"])

    def test_handoff_hash_is_stable_for_lifecycle_only(self):
        handoff = valid_v13_embedded()["enriched_content_handoff"]
        expected = canonical_handoff_hash(handoff)
        for status in ("FROZEN", "RESULT_RECEIVED", "RECONCILIATION_REQUIRED", "SUPERSEDED"):
            advanced = copy.deepcopy(handoff)
            advanced["status"] = status
            advanced["parent_bundle_sha256"] = "sha256:" + "e" * 64
            advanced["checksum"] = "sha256:" + "f" * 64
            self.assertEqual(canonical_handoff_hash(advanced), expected)

    def test_handoff_hash_changes_for_upstream_semantics(self):
        handoff = valid_v13_embedded()["enriched_content_handoff"]
        expected = canonical_handoff_hash(handoff)
        mutations = (
            lambda row: row["fact_ids"].append("FACT-NEW"),
            lambda row: row["application_scope"]["packs"].append("3"),
            lambda row: row.update({"ptd_inventory_hash": "sha256:" + "0" * 64}),
            lambda row: row["decision_requirements"][0].update({"buyer_question": "Changed?"}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(handoff)
                mutation(changed)
                self.assertNotEqual(canonical_handoff_hash(changed), expected)

    def test_embedded_handoff_semantic_lineage_is_closed_and_content_addressed(self):
        missing_key = valid_v13_embedded()
        missing_key["enriched_content_handoff"].pop("semantic_revision")
        result = validate_bundle(missing_key)
        self.assertFalse(result["ok"])
        self.assertFalse(result["structural_valid"])
        self.assertIn("[A13-HANDOFF-036]", errors(result))

        stale_snapshot = valid_v13_embedded()
        stale_snapshot["enriched_content_handoff"]["snapshot_id"] = "HO-" + "0" * 20
        stale_snapshot["workflow_context"]["accepted_handoff_snapshot_id"] = "HO-" + "0" * 20
        stale_snapshot["enriched_content_handoff"]["checksum"] = canonical_handoff_hash(
            stale_snapshot["enriched_content_handoff"]
        )
        stale_result = validate_bundle(stale_snapshot)
        self.assertFalse(stale_result["ok"])
        self.assertIn("[A13-HANDOFF-042]", errors(stale_result))

        invalid_refreeze = valid_v13_embedded()
        invalid_refreeze["enriched_content_handoff"].update({
            "semantic_revision": 2,
            "predecessor_snapshot_id": "",
            "refreeze_reason": "",
        })
        invalid_refreeze["enriched_content_handoff"]["snapshot_id"] = canonical_handoff_snapshot_id(
            invalid_refreeze["enriched_content_handoff"]
        )
        invalid_refreeze["workflow_context"]["accepted_handoff_snapshot_id"] = invalid_refreeze["enriched_content_handoff"]["snapshot_id"]
        invalid_refreeze["enriched_content_handoff"]["checksum"] = canonical_handoff_hash(
            invalid_refreeze["enriched_content_handoff"]
        )
        refreeze_result = validate_bundle(invalid_refreeze)
        self.assertFalse(refreeze_result["ok"])
        self.assertIn("[A13-HANDOFF-040]", errors(refreeze_result))

    def test_refreeze_registry_rejects_random_jump_unsuperseded_and_wrong_successor(self):
        valid = refrozen_v13_embedded()
        valid_result = validate_bundle(valid)
        self.assertTrue(valid_result["ok"], errors(valid_result))

        def reseal(bundle: dict) -> None:
            handoff = bundle["enriched_content_handoff"]
            handoff["snapshot_id"] = canonical_handoff_snapshot_id(handoff)
            handoff["lineage_registry"][0]["successor_snapshot_id"] = handoff["snapshot_id"]
            handoff["lineage_registry"][0]["record_checksum"] = canonical_lineage_record_hash(
                handoff["lineage_registry"][0]
            )
            handoff["checksum"] = canonical_handoff_hash(handoff)
            bundle["workflow_context"]["accepted_handoff_snapshot_id"] = handoff["snapshot_id"]

        cases = {
            "random_predecessor": lambda h: h.update({"predecessor_snapshot_id": "HO-" + "9" * 20}),
            "revision_jump": lambda h: h.update({"semantic_revision": 3}),
            "not_superseded": lambda h: h["lineage_registry"][0].update({"status": "FROZEN"}),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                bundle = refrozen_v13_embedded()
                mutate(bundle["enriched_content_handoff"])
                reseal(bundle)
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"], result)
                self.assertIn("[A13-HANDOFF-044]", errors(result))

        wrong_successor = refrozen_v13_embedded()
        handoff = wrong_successor["enriched_content_handoff"]
        handoff["lineage_registry"][0]["successor_snapshot_id"] = "HO-" + "8" * 20
        handoff["lineage_registry"][0]["record_checksum"] = canonical_lineage_record_hash(
            handoff["lineage_registry"][0]
        )
        handoff["checksum"] = canonical_handoff_hash(handoff)
        result = validate_bundle(wrong_successor)
        self.assertFalse(result["ok"], result)
        self.assertIn("[A13-HANDOFF-044]", errors(result))

    def test_embedded_parent_bound_forbids_local_reinterview(self):
        bundle = valid_v13_embedded()
        bundle["discovery"]["interview_rounds"] = [{"id": "R-X", "phase": "TRUTH", "questions": [], "owner": "A+"}]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-DISCOVERY-010]", errors(result))

    def test_embedded_requirements_atoms_assertions_and_hash_are_exact(self):
        mutations = (
            lambda b: b["decision_map"]["requirements"][0].update({"buyer_question": "Changed?"}),
            lambda b: b["decision_denominator_snapshot"]["atoms"][0].update({"variant_row_id": "V-X"}),
            lambda b: b["canonical_assertions"][0].update({"id": "ASSERT-X"}),
            lambda b: b["decision_denominator_snapshot"].update({"source_hash": "sha256:" + "0" * 64}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bundle = valid_v13_embedded()
                mutation(bundle)
                bundle["decision_denominator_snapshot"]["checksum"] = ""
                bundle["decision_denominator_snapshot"]["checksum"] = canonical_object_hash(bundle["decision_denominator_snapshot"])
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])

    def test_embedded_partial_pack_cannot_pass(self):
        bundle = valid_v13_embedded()
        bundle["decision_answer_units"][0]["application_scope"]["packs"] = ["2"]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-ANSWER-035]", errors(result))

    def test_embedded_new_evidence_must_return_as_delta(self):
        bundle = valid_v13_embedded()
        handoff = bundle["enriched_content_handoff"]
        bundle["delta_evidence_requests"] = [{
            "id": "DELTA-1", "question": "Verify new limit.",
            "affected_requirement_ids": [bundle["decision_map"]["requirements"][0]["id"]],
            "affected_atom_ids": ["ATOM-1"],
            "affected_fact_ids": [], "affected_claim_ids": [], "affected_module_ids": [bundle["modules"][0]["id"]],
            "decisive_evidence": "Parent-verified specification.",
            "gap_type": "PARENT_EVIDENCE",
            "handoff_lineage": {
                "snapshot_id": handoff["snapshot_id"],
                "parent_bundle_sha256": handoff["parent_bundle_sha256"],
                "discovery_closure_hash": handoff["discovery_closure_hash"],
                "ptd_inventory_hash": handoff["ptd_inventory_hash"],
                "decision_denominator_hash": handoff["decision_denominator_hash"],
                "handoff_checksum": handoff["checksum"],
            },
            "owner": "Parent owner", "status": "OPEN",
        }]
        bundle["project"]["conclusion"] = "CONDITIONAL_PASS"
        bundle["decision_answer_units"][0].update({"content_status": "CONDITIONAL_DRAFT", "qa_status": "HOLD"})
        bundle["coverage_summary"].update({
            "status": "GAP", "p0_pass": 0,
            "gap_requirement_ids": [bundle["decision_map"]["requirements"][0]["id"]],
            "p0_atoms_pass": 0, "gap_atom_ids": ["ATOM-1"],
        })
        bundle["component_result"].update({
            "status": "DELTA_REQUIRED", "gap_atom_ids": ["ATOM-1"],
            "open_delta_request_ids": ["DELTA-1"],
        })
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], errors(result))
        injected = copy.deepcopy(bundle)
        injected["facts"].append(copy.deepcopy(injected["facts"][0]))
        injected["facts"][-1]["id"] = "CHILD-NEW-FACT"
        self.assertFalse(validate_bundle(injected)["ok"])

    def test_community_qa_cannot_be_brand_authored_carrier(self):
        bundle = valid_v13_embedded()
        bundle["carriers"][0]["carrier_type"] = "community_qa"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("carrier_type", errors(result))

    def test_locale_expression_cannot_expand_assertion_chain(self):
        bundle = valid_v13_embedded()
        bundle["canonical_assertions"][0]["locale_expressions"][0]["fact_ids"].append("OUTSIDE-FACT")
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-ASSERT-010]", errors(result))

    def test_zero_p0_denominator_cannot_pass(self):
        bundle = valid_v13()
        bundle["decision_map"]["requirements"] = []
        bundle["decision_denominator_snapshot"]["requirement_ids"] = []
        bundle["decision_denominator_snapshot"]["variant_row_ids"] = []
        bundle["decision_denominator_snapshot"]["atoms"] = []
        bundle["decision_denominator_snapshot"]["checksum"] = ""
        bundle["decision_denominator_snapshot"]["checksum"] = canonical_object_hash(bundle["decision_denominator_snapshot"])
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-COVERAGE-030]", errors(result))

    def test_atom_answer_scope_must_match_real_variant(self):
        bundle = valid_v13()
        bundle["decision_answer_units"][0]["application_scope"]["packs"] = ["2"]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-ANSWER-035]", errors(result))

    def test_duplicate_primary_answer_is_rejected(self):
        bundle = valid_v13()
        duplicate = copy.deepcopy(bundle["decision_answer_units"][0])
        duplicate["id"] = "ANSWER-2"
        bundle["decision_answer_units"].append(duplicate)
        bundle["carriers"][0]["answer_unit_ids"].append("ANSWER-2")
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-COVERAGE-033]", errors(result))

    def test_unknown_skip_on_p0_requires_evidence_action(self):
        bundle = valid_v13()
        question = bundle["discovery"]["interview_rounds"][0]["questions"][0]
        question.update({"answer": "", "response_class": "UNKNOWN_SKIP"})
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-DISCOVERY-008]", errors(result))

    def test_standalone_evidence_pass_is_complete_nonempty_usable_and_scoped(self):
        mutations = (
            (lambda b: b["discovery"]["evidence_pass"].update({"status": "PARTIAL"}), "[A13-EVIDENCE-001]"),
            (lambda b: b["discovery"]["evidence_pass"].update({"source_ids": []}), "[A13-EVIDENCE-002]"),
            (lambda b: b["discovery"]["evidence_pass"].update({"observations": []}), "[A13-EVIDENCE-003]"),
            (lambda b: next(row for row in b["sources"] if row["id"] == "SRC-SPEC").update({"fetch_status": "partial"}), "[A13-EVIDENCE-005]"),
            (lambda b: next(row for row in b["sources"] if row["id"] == "SRC-SPEC")["scope"].update({"child_asins": []}), "[A13-EVIDENCE-006]"),
        )
        for mutation, expected_code in mutations:
            with self.subTest(expected_code=expected_code):
                bundle = valid_v13()
                mutation(bundle)
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn(expected_code, errors(result))

    def test_answered_socratic_question_requires_valid_distillation(self):
        bundle = valid_v13()
        bundle["discovery"]["distillations"] = []
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-DISCOVERY-022]", errors(result))
        self.assertIn("[A13-DISCOVERY-023]", errors(result))

    def test_discovery_closure_is_derived_not_self_reported(self):
        bundle = valid_v13()
        bundle["discovery"]["evidence_pass"]["status"] = "PARTIAL"
        bundle["discovery"]["closure"]["status"] = "PASS"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("expected derived value 'BLOCKED'", errors(result))

    def test_operational_mirror_cannot_solely_prove_physical_or_performance_fact(self):
        for fact_id, source_id, mirror_type in (
            ("FACT-1", "SRC-SPEC", "LINGXING_OPERATIONAL_MIRROR"),
            ("FACT-2", "SRC-TEST", "EXTERNAL_OPERATIONAL_MIRROR"),
        ):
            with self.subTest(fact_id=fact_id, mirror_type=mirror_type):
                bundle = valid_v13()
                source = next(row for row in bundle["sources"] if row["id"] == source_id)
                source.update({
                    "source_type": mirror_type,
                    "mirror_system": "Lingxing ERP" if mirror_type.startswith("LINGXING") else "External ERP",
                    "mirror_snapshot_id": "MIRROR-20260828-01",
                    "mirror_limitations": ["Operational mirror; not direct product or Amazon live-state proof."],
                })
                fact = next(row for row in bundle["facts"] if row["id"] == fact_id)
                fact["evidence_type"] = mirror_type
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("[A13-MIRROR-002]", errors(result))

    def test_answer_assertion_scope_must_exactly_cover_atom(self):
        bundle = valid_v13()
        bundle["canonical_assertions"][0]["application_scope"]["packs"] = ["2"]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-ASSERT-007]", errors(result))
        self.assertIn("[A13-ANSWER-040]", errors(result))

    def test_local_construction_gap_stays_in_progress(self):
        bundle = valid_v13()
        mark_atom_gap(bundle, component_status="IN_PROGRESS")
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], errors(result))
        self.assertEqual(result["result_level"], "IN_PROGRESS")

    def test_delta_required_cannot_hide_unmapped_local_gap(self):
        bundle = valid_v13()
        mark_atom_gap(bundle, component_status="DELTA_REQUIRED")
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("expected derived value 'IN_PROGRESS'", errors(result))

    def test_embedded_parent_evidence_gap_requires_open_delta_and_exact_lineage(self):
        bundle = valid_v13_embedded()
        bundle["delta_evidence_requests"] = [parent_evidence_delta(bundle)]
        mark_atom_gap(bundle, component_status="DELTA_REQUIRED", delta_ids=["DELTA-1"])
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], errors(result))
        self.assertEqual(result["result_level"], "DELTA_REQUIRED")

        stale = copy.deepcopy(bundle)
        stale["delta_evidence_requests"][0]["handoff_lineage"]["ptd_inventory_hash"] = "sha256:" + "0" * 64
        stale_result = validate_bundle(stale)
        self.assertFalse(stale_result["ok"])
        self.assertIn("[A13-DELTA-033]", errors(stale_result))

    def test_open_delta_requires_atom_and_cannot_target_passed_atom(self):
        missing_atom = valid_v13_embedded()
        delta = parent_evidence_delta(missing_atom)
        delta["affected_atom_ids"] = []
        missing_atom["delta_evidence_requests"] = [delta]
        result = validate_bundle(missing_atom)
        self.assertFalse(result["ok"])
        self.assertIn("affected_atom_ids: at least one value required", errors(result))

        stale = valid_v13_embedded()
        stale["delta_evidence_requests"] = [parent_evidence_delta(stale)]
        stale["project"]["conclusion"] = "CONDITIONAL_PASS"
        stale["component_result"].update({
            "status": "BLOCKED", "gap_atom_ids": [],
            "open_delta_request_ids": ["DELTA-1"],
        })
        stale_result = validate_bundle(stale)
        self.assertFalse(stale_result["ok"])
        self.assertIn("[A13-DELTA-034]", errors(stale_result))

    def test_unknown_v13_root_and_nested_shape_are_structurally_invalid(self):
        unknown_root = valid_v13()
        unknown_root["surprise_extension"] = {"trusted": True}
        result = validate_bundle(unknown_root)
        self.assertFalse(result["ok"])
        self.assertFalse(result["structural_valid"])

        malformed = valid_v13()
        malformed["discovery"]["evidence_pass"]["source_ids"] = "SRC-SPEC"
        malformed_result = validate_bundle(malformed)
        self.assertFalse(malformed_result["ok"])
        self.assertFalse(malformed_result["structural_valid"])

    def test_standalone_category_adapter_uses_exact_closed_schema(self):
        mutations = (
            lambda b: b["category_adapter"].update({"amazon_ptd_fields": []}),
            lambda b: b["category_adapter"].update({"id": "invented-category"}),
            lambda b: b["category_adapter"].update({"status": "PARENT_BOUND"}),
            lambda b: b.update({"category_adapter": []}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bundle = valid_v13()
                mutation(bundle)
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertFalse(result["structural_valid"])

    def test_cli_output_is_deterministic_across_python_hash_seeds(self):
        bundle = valid_v13()
        bundle["surprise_extension"] = {"trusted": True}
        bundle["category_adapter"]["amazon_ptd_fields"] = []
        bundle["discovery"]["evidence_pass"]["source_ids"] = []
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = Path(temp_dir) / "invalid-v13.json"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            outputs: list[str] = []
            for seed in ("1", "777", "123456"):
                env = dict(os.environ)
                env["PYTHONHASHSEED"] = seed
                completed = subprocess.run(
                    [sys.executable, str(scripts / "validate_bundle.py"), str(bundle_path)],
                    text=True, capture_output=True, check=False, env=env,
                )
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                payload = json.loads(completed.stdout)
                self.assertEqual(payload["errors"], sorted(payload["errors"]))
                self.assertEqual(payload["warnings"], sorted(payload["warnings"]))
                outputs.append(completed.stdout)
            self.assertEqual(len(set(outputs)), 1)

    def test_legacy_malformed_ipv6_parent_reference_is_structured_infra_error(self):
        bundle = legacy.embedded_v12_bundle()
        bundle["workflow_context"]["parent_bundle_ref"] = "http://[::1"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[A-IO-REF-001]" in item for item in result["errors"]), result)

        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = Path(temp_dir) / "malformed-reference.json"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(scripts / "validate_bundle.py"), str(bundle_path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(any("[A-IO-REF-001]" in item for item in payload["errors"]), payload)

    def test_entry_and_publication_domain_helpers_are_pure_and_deterministic(self):
        self.assertIn("[A-IO-REF-001]", local_parent_reference_issue("http://[::1") or "")
        self.assertEqual(required_pass_gate_ids("plan", False), ("G0", "G1", "G2", "G3", "G4"))
        self.assertEqual(required_pass_gate_ids("publish_support", True), ("G0", "G1", "G2", "G3", "G4", "G5", "G6"))
        self.assertEqual(
            derive_result_level(
                schema_version="1.2", has_errors=False, mode="plan",
                conclusion="PASS", component_result="COMPONENT_PASS",
            ),
            "LEGACY_LOCAL_CONTRACT",
        )
        self.assertEqual(
            derive_result_level(
                schema_version="1.3", has_errors=False, mode="publish_support",
                conclusion="PASS", component_result="COMPONENT_PASS",
            ),
            "LIVE_VERIFIED",
        )
        self.assertEqual(validator_exit_code({"ok": False, "errors": ["[A-IO-REF-001] malformed"]}), 2)
        self.assertEqual(validator_exit_code({"ok": False, "errors": ["ordinary contract failure"]}), 1)
        self.assertEqual(
            publication_entry_issues(
                mode="publish_support", write_scope="read_only",
                identity_status="UNVERIFIED", scope_status="PARTIAL",
                authorization_status="NOT_AUTHORIZED",
            ),
            (
                "$.project.write_scope: publish_support requires explicit_write",
                "$.project: publish_support requires VERIFIED_CHILD identity and FROZEN scope",
                "$.publish_authorization.status: publish_support requires AUTHORIZED",
            ),
        )
        authorization_start = datetime(2030, 1, 2, tzinfo=timezone.utc)
        authorization_end = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(
            len(authorization_time_issues(
                authorized_at=authorization_start, expires_at=authorization_end,
                snapshot_at=authorization_start, validation_at=authorization_start,
            )),
            3,
        )
        self.assertIsNotNone(authorization_target_issue(
            marketplaces={"US"}, locales={"en-US"}, content_ids={"A"}, child_asins={"B0CHILD001"},
            expected_marketplace="US", expected_locale="en-US",
            expected_content_ids={"A"}, expected_child_asins={"B0DIFFER01"},
        ))
        self.assertEqual(
            authorization_action_issues({"submit", "invented"}, {"submit", "apply"}),
            (
                "$.publish_authorization.allowed_actions: unsupported values ['invented']",
                "$.publish_authorization.allowed_actions: explicit submit and apply authority required",
            ),
        )
        source = Path("source.json")
        self.assertEqual(
            migration_path_issue(source, Path("same.json"), Path("same.json")),
            "migration output and report must be different files",
        )

    def test_missing_capability_cannot_produce_component_pass(self):
        bundle = valid_v13()
        bundle["capability_snapshots"] = []
        bundle["carriers"][0]["capability_snapshot_id"] = ""
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-RESULT-001]", errors(result))

    def test_component_cannot_claim_page_or_publish_authority(self):
        bundle = valid_v13()
        bundle["component_result"]["publication_authorized"] = True
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-RESULT-005]", errors(result))

    def test_migration_invalidates_authority_and_live_state(self):
        legacy_bundle = legacy.upgrade_v12()
        legacy_bundle["project"]["write_scope"] = "explicit_write"
        legacy_bundle["variants"][0]["status"] = "LIVE_PASS"
        migrated, report = migrate(legacy_bundle)
        self.assertEqual(migrated["schema_version"], "1.3")
        self.assertEqual(migrated["project"]["write_scope"], "read_only")
        self.assertEqual(migrated["project"]["conclusion"], "NO_VALID_CONCLUSION")
        self.assertEqual(migrated["variants"][0]["status"], "VERIFIED")
        self.assertFalse(report["authority_escalated"])
        self.assertFalse(report["new_contract_ready"])
        for section in ("modules", "assets", "carriers", "decision_answer_units", "canonical_assertions"):
            self.assertEqual(migrated[section], [])
            self.assertGreaterEqual(report["discarded_candidate_counts"].get(section, 0), 0)

    def test_v11_migration_adds_contract_roots_without_inventing_pass(self):
        migrated, report = migrate(legacy.valid_bundle())
        for key in ("discovery", "decision_denominator_snapshot", "canonical_assertions", "component_result"):
            self.assertIn(key, migrated)
        self.assertEqual(migrated["component_result"]["status"], "NOT_EVALUATED")
        self.assertEqual(migrated["canonical_assertions"], [])
        self.assertIn("workflow_context", report["added_root_keys"])

    def test_v13_rejects_legacy_conditional_copy_and_wireframe_boundaries(self):
        for legacy_value in ("audit_gap_report_and_conditional_wireframe", "conditional_copy"):
            with self.subTest(legacy_value=legacy_value):
                bundle = valid_v13()
                bundle["project"]["conditional_draft"]["maximum_work"] = legacy_value
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("$.project.conditional_draft.maximum_work", errors(result))
                self.assertIn("unsupported value", errors(result))

    def test_v13_strategy_dependency_only_rejects_consumer_content_rows(self):
        bundle = valid_v13()
        bundle["project"]["conditional_draft"].update({
            "status": "BLOCKED",
            "maximum_work": "strategy_dependency_only",
            "blocked_outputs": [
                "consumer_final_copy", "final_product_imagery", "module_wireframes",
                "image_alt_concepts", "publishing",
            ],
            "blocker_ids": ["BLOCK-PRODUCT-TRUTH"],
        })
        bundle["project"]["conclusion"] = "BLOCKED"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-PHASE-001]", errors(result))

    def test_v13_embedded_strategy_dependency_only_rejects_content_package(self):
        bundle = valid_v13_embedded()
        bundle["enriched_content_handoff"]["maximum_output"] = "strategy_dependency_only"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A13-HANDOFF-023]", errors(result))

    def test_legacy_scaffold_migrates_to_renderable_blocked_review(self):
        template_path = Path(__file__).resolve().parents[1] / "assets" / "aplus-project-bundle-template.json"
        legacy_scaffold = json.loads(template_path.read_text(encoding="utf-8"))
        legacy_scaffold["schema_version"] = "1.2"
        for key in ("discovery", "decision_denominator_snapshot", "canonical_assertions", "component_result"):
            legacy_scaffold.pop(key, None)
        legacy_scaffold["decision_map"].pop("requirements", None)
        legacy_scaffold["enriched_content_handoff"]["contract_version"] = "1.0"
        for key in ("discovery_closure_hash", "ptd_inventory_hash", "decision_denominator_hash", "canonical_assertion_ids", "requirement_atoms"):
            legacy_scaffold["enriched_content_handoff"].pop(key, None)
        for key in ("p0_atoms_required", "p0_atoms_pass", "gap_atom_ids"):
            legacy_scaffold["coverage_summary"].pop(key, None)
        migrated, _ = migrate(legacy_scaffold)
        self.assertEqual(migrated["project"]["status"], "MIGRATED_NEEDS_REVIEW")
        validation = validate_bundle(migrated)
        self.assertFalse(validation["ok"])
        self.assertFalse(validation["template_only"])
        self.assertTrue(validation["structural_valid"])
        self.assertIn("Validator阻断项", render(migrated, validation))

    def test_renderer_is_deterministic_and_escapes_untrusted_content(self):
        bundle = valid_v13()
        bundle["project"]["title"] = "<script>alert(1)</script>"
        validation = validate_bundle(bundle)
        self.assertTrue(validation["ok"], errors(validation))
        first = render(bundle, validation)
        second = render(bundle, validation)
        self.assertEqual(first, second)
        self.assertNotIn("<script>alert(1)</script>", first)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", first)
        self.assertNotIn("localStorage", first)
        self.assertNotIn("<input", first)
        self.assertNotIn("<button", first)

    def test_renderer_allows_structural_business_block_and_displays_errors(self):
        bundle = valid_v13()
        bundle["component_result"]["status"] = "BLOCKED"
        validation = validate_bundle(bundle)
        self.assertFalse(validation["ok"])
        self.assertTrue(validation["structural_valid"])
        rendered = render(bundle, validation)
        self.assertIn("Validator阻断项", rendered)
        self.assertIn("A13-RESULT-001", rendered)

    def test_renderer_never_links_unsafe_source_scheme(self):
        bundle = valid_v13()
        source = next(row for row in bundle["sources"] if row["id"] == "SRC-SPEC")
        source["path_or_url"] = "javascript:alert(1)"
        validation = validate_bundle(bundle)
        rendered = render(bundle, validation)
        self.assertNotIn('href="javascript:', rendered)
        self.assertIn("javascript:alert(1)", rendered)

    def test_legacy_versions_are_explicitly_legacy(self):
        for bundle in (legacy.valid_bundle(), legacy.upgrade_v12()):
            result = validate_bundle(bundle)
            self.assertTrue(result["ok"], errors(result))
            self.assertEqual(result["result_level"], "LEGACY_LOCAL_CONTRACT")

    def test_versioned_v12_scaffold_cli_regression(self):
        skill_root = Path(__file__).resolve().parents[1]
        template = skill_root / "assets" / "aplus-project-bundle-template-v1.2.json"
        result = subprocess.run(
            [sys.executable, str(skill_root / "scripts" / "validate_bundle.py"), str(template)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["template_only"])
        self.assertEqual(payload["result_level"], "TEMPLATE_ONLY")
        self.assertNotIn("A12-SCAFFOLD-001", "\n".join(payload["errors"]))

    def test_public_embedded_fixture_passes_child_cli(self):
        skill_root = Path(__file__).resolve().parents[1]
        fixture = skill_root / "scripts" / "fixtures" / "aplus-v1.3-embedded-pass.json"
        result = subprocess.run(
            [sys.executable, str(skill_root / "scripts" / "validate_bundle.py"), str(fixture)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["result_level"], "COMPONENT_PASS")
        self.assertIsNone(payload["parent_bundle_verified"])

    def test_cli_migration_and_renderer_round_trip_without_overwrite(self):
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "legacy.json"
            migrated = root / "migrated.json"
            report = root / "migration-report.json"
            html_one = root / "report-one.html"
            html_two = root / "report-two.html"
            source.write_text(json.dumps(legacy.valid_bundle(), ensure_ascii=False), encoding="utf-8")
            migration = subprocess.run(
                [sys.executable, str(scripts / "migrate_aplus_bundle.py"), str(source), "--output", str(migrated), "--report", str(report)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(migration.returncode, 0, migration.stdout + migration.stderr)
            migrated_payload = json.loads(migrated.read_text(encoding="utf-8"))
            validation = validate_bundle(migrated_payload)
            self.assertTrue(validation["structural_valid"])
            self.assertFalse(validation["ok"])
            self.assertEqual(migrated_payload["project"]["conclusion"], "NO_VALID_CONCLUSION")
            second_migration = subprocess.run(
                [sys.executable, str(scripts / "migrate_aplus_bundle.py"), str(source), "--output", str(migrated), "--report", str(report)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(second_migration.returncode, 2)
            for output in (html_one, html_two):
                rendered = subprocess.run(
                    [sys.executable, str(scripts / "render_aplus_report.py"), str(migrated), "--output", str(output)],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
            self.assertEqual(html_one.read_bytes(), html_two.read_bytes())
            self.assertIn("Validator阻断项", html_one.read_text(encoding="utf-8"))

    def test_migration_cli_rejects_output_report_collision_with_structured_exit_two(self):
        scripts = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "legacy.json"
            collision = root / "collision.json"
            source.write_text(json.dumps(legacy.valid_bundle(), ensure_ascii=False), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(scripts / "migrate_aplus_bundle.py"), str(source),
                 "--output", str(collision), "--report", str(collision)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertFalse(collision.exists())
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["error"], "migration output and report must be different files")

    def test_refactor_reports_are_deterministic_pure_and_non_authorizing(self):
        fact_args = {
            "schema_version": "1.3",
            "fact_id": "FACT-MIRROR",
            "fact_class": "PHYSICAL_PRODUCT",
            "publish_status": "PUBLISHABLE",
            "proving_types": {"LINGXING_OPERATIONAL_MIRROR"},
        }
        before_fact_args = copy.deepcopy(fact_args)
        fact_report = build_fact_evidence_report(**fact_args)
        self.assertEqual(fact_report, build_fact_evidence_report(**fact_args))
        self.assertEqual(fact_args, before_fact_args)
        self.assertTrue(any("A13-MIRROR-002" in item for item in fact_report.errors))

        publication_args = {
            "mode": "publish_support",
            "write_scope": "explicit_write",
            "identity_status": "VERIFIED_CHILD",
            "scope_status": "FROZEN",
            "authorization_status": "AUTHORIZED",
            "authorized_at": datetime(2026, 8, 27, tzinfo=timezone.utc),
            "expires_at": datetime(2099, 9, 3, tzinfo=timezone.utc),
            "snapshot_at": datetime(2026, 8, 28, tzinfo=timezone.utc),
            "validation_at": datetime(2026, 8, 28, tzinfo=timezone.utc),
            "systems": {"Seller Central"},
            "marketplaces": {"US"},
            "locales": {"en-US"},
            "content_ids": {"A+-001", "BS-001"},
            "child_asins": {"B0EXAMPLE1"},
            "actions": {"edit", "submit", "apply", "rollback"},
            "expected_marketplace": "US",
            "expected_locale": "en-US",
            "expected_content_ids": {"A+-001", "BS-001"},
            "expected_child_asins": {"B0EXAMPLE1"},
            "allowed_actions": {"edit", "submit", "apply", "publish", "rollback"},
        }
        before_publication_args = copy.deepcopy(publication_args)
        publication_report = build_publication_report(**publication_args)
        self.assertEqual(publication_report.errors, ())
        self.assertEqual(publication_report, build_publication_report(**publication_args))
        self.assertEqual(publication_args, before_publication_args)

        publish_bundle = legacy.valid_publish_bundle()
        before_bundle = copy.deepcopy(publish_bundle)
        row = publish_bundle["live_readback"][0]
        source = next(item for item in publish_bundle["sources"] if item["id"] == "SRC-PDP-LIVE")
        raw_scope = source["scope"]
        normalized_scope = {
            "marketplaces": {raw_scope["marketplace"]},
            "locales": {raw_scope["locale"]},
            "parent_asins": {raw_scope["parent_asin"]},
            "child_asins": set(raw_scope["child_asins"]),
            "packs": set(raw_scope["packs"]),
            "colors": set(raw_scope["colors"]),
            "sizes_or_capacities": set(raw_scope["sizes_or_capacities"]),
        }
        row_report = build_readback_row_report(
            path="$.live_readback[RB-001]",
            phase=row["readback_phase"],
            child_asin=row["child_asin"],
            marketplace=row["marketplace"],
            locale=row["locale"],
            expected_content_id=row["expected_content_id"],
            observed_content_id=row["observed_content_id"],
            checked_at=datetime.fromisoformat(row["checked_at"]),
            fetch_status=row["fetch_status"],
            field_statuses=set(row["field_checks"].values()),
            evidence_source_ids=set(row["evidence_source_ids"]),
            status=row["status"],
            mismatch_action=row["mismatch_action"],
            followup_required=row["followup_required"],
            expected_content_by_key={("B0EXAMPLE1", "US", "en-US"): "A+-001"},
            source_map={"SRC-PDP-LIVE": source},
            source_scopes={"SRC-PDP-LIVE": normalized_scope},
        )
        self.assertEqual(row_report.errors, ())
        coverage_report = build_readback_coverage_report(
            intended_keys={row_report.key},
            first_readback_keys={row_report.key},
            pass_keys={row_report.key},
            conclusion="PASS",
        )
        self.assertEqual(coverage_report.errors, ())
        self.assertEqual(publish_bundle, before_bundle)

    def test_bundle_orchestrator_is_small_wired_deterministic_and_input_pure(self):
        scripts = Path(__file__).resolve().parent
        entry_path = scripts / "validate_bundle.py"
        validator_path = scripts / "aplus_contract_orchestrator.py"
        self.assertLessEqual(len(entry_path.read_text(encoding="utf-8").splitlines()), 40)
        tree = ast.parse(validator_path.read_text(encoding="utf-8"))
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "validate_bundle"
        )
        self.assertLessEqual(function.end_lineno - function.lineno + 1, 300)
        source = ast.get_source_segment(validator_path.read_text(encoding="utf-8"), function)
        self.assertIn("validate_foundation(", source)
        self.assertIn("validate_content(", source)
        self.assertIn("validate_governance(", source)
        self.assertNotIn('sources_raw = require_list(root, "sources"', source)
        self.assertNotIn('readback_rows = require_list(root, "live_readback"', source)
        for filename in (
            "aplus_bundle_foundation_domain.py",
            "aplus_bundle_content_domain.py",
            "aplus_bundle_governance_domain.py",
        ):
            domain_source = (scripts / filename).read_text(encoding="utf-8")
            self.assertNotIn("from validate_bundle import", domain_source)
            self.assertNotIn("import validate_bundle", domain_source)

        bundle = valid_v13()
        before = copy.deepcopy(bundle)
        first = validate_bundle(bundle)
        second = validate_bundle(bundle)
        self.assertEqual(first, second)
        self.assertEqual(bundle, before)

    def test_refactor_golden_results_preserve_legacy_and_v13_contracts(self):
        expected = {
            "legacy11_valid": "43e6095ea1cbcd743b603e37c431d113e98af6e081559100811136bcd4279c9d",
            "legacy12_valid": "b7f3e824c10e5a5f3ab7a677d97ddbda7050a1730b4fcdf9d9320419bad4c40d",
            "legacy11_publish_valid": "2e5cfe5a11a1f20084444084c7b31b7f6d03bf51969ba3d87e79b72bb58ebcd3",
            "legacy12_publish_valid": "69d92ee3ede307e99b723ac07f349f94425e45665cf558deb623826c2506f088",
            "legacy12_readback_bad": "799493a51cdbaabb78c59cb4c8eff2f10a849b633bc1b9f335ccc517793f087b",
            "legacy12_malformed_ref": "20223496fd5924c3d87399b76f3365a39d7742c1a22575f12bcd62feb70a5657",
            "v13_standalone_valid": "5742f7ce0f919353e11fd6a03f315e437a3dca23c1bb55e3913548b9b4bbb9ce",
            "v13_evidence_bad": "6394f182679789640d0f119b798ffcb054c79386992cf552982460d259f4646b",
            "v13_discovery_bad": "c2d32eb0cad29b4a5862bb8350e1b7a1ce1836a28657acd1e6d6c6f126a10c90",
            "v13_decision_bad": "f0c987dc27f57a303b3f0732de052a0903597e25316c93a915b2389b235c1a32",
            "v13_handoff_bad": "1449794e2f6454c19c51c56579ff3aa9b47a84d90d5dde5e52330494804fc601",
            "v13_embedded_fixture": "8b2a67228246b49715ec8934d863245e301760abd9b4b07caae2b2cca5e086b9",
        }
        cases: dict[str, tuple[dict, Path | None]] = {
            "legacy11_valid": (legacy.valid_bundle(), None),
            "legacy12_valid": (legacy.upgrade_v12(), None),
            "legacy11_publish_valid": (legacy.valid_publish_bundle(), None),
            "legacy12_publish_valid": (legacy.upgrade_v12(legacy.valid_publish_bundle()), None),
            "v13_standalone_valid": (valid_v13(), None),
        }
        bundle = valid_v13()
        bundle["sources"][0].update(fetch_status="blocked", block_reason="golden mutation")
        cases["v13_evidence_bad"] = (bundle, None)
        bundle = valid_v13(); bundle["discovery"]["evidence_pass"]["status"] = "INCOMPLETE"
        cases["v13_discovery_bad"] = (bundle, None)
        bundle = valid_v13(); bundle["decision_answer_units"] = []
        cases["v13_decision_bad"] = (bundle, None)
        bundle = valid_v13(); bundle["enriched_content_handoff"]["lineage_registry"] = {}
        cases["v13_handoff_bad"] = (bundle, None)
        bundle = legacy.upgrade_v12(legacy.valid_publish_bundle())
        bundle["live_readback"][0]["observed_content_id"] = "A+-OTHER"
        cases["legacy12_readback_bad"] = (bundle, None)
        bundle = legacy.embedded_v12_bundle()
        bundle["workflow_context"]["parent_bundle_ref"] = "http://[::1"
        cases["legacy12_malformed_ref"] = (bundle, None)
        fixture = Path(__file__).resolve().parent / "fixtures" / "aplus-v1.3-embedded-pass.json"
        cases["v13_embedded_fixture"] = (json.loads(fixture.read_text(encoding="utf-8")), fixture)

        for name, (bundle, source_path) in cases.items():
            with self.subTest(name=name):
                before = copy.deepcopy(bundle)
                result = validate_bundle(bundle, source_path=source_path)
                payload = json.dumps(
                    result, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")
                self.assertEqual(hashlib.sha256(payload).hexdigest(), expected[name])
                self.assertEqual(bundle, before)


if __name__ == "__main__":
    unittest.main()
