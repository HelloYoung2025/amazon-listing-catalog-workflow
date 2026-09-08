#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from migrate_listing_bundle import migrate_bundle
from listing_v11_domains import (
    derive_stage, evaluate_discovery, evaluate_evidence, evaluate_handoff,
    evaluate_ptd, evaluate_publication, expected_requirement_atom_tuples,
)
from listing_v11_field_contract import p0_field_contract_allows
from listing_v11_lineage import build_lineage_record, canonical_lineage_record_hash
from validate_listing_bundle import validate_listing_bundle
from validate_listing_bundle_v11 import (
    canonical_handoff_hash,
    canonical_handoff_snapshot_id,
    canonical_parent_hash,
    canonical_sha256,
    validate_listing_bundle_v11,
)


CHILD = "B0V11CHILD"
PARENT = "B0V11PARNT"


def app_scope(children=None, packs=None, colors=None, sizes=None):
    return {
        "parent_asins": [PARENT],
        "child_asins": list([CHILD] if children is None else children),
        "packs": list(["1PK"] if packs is None else packs),
        "colors": list(["Black"] if colors is None else colors),
        "sizes": list(["M"] if sizes is None else sizes),
    }


def hash_block(block):
    normalized = copy.deepcopy(block)
    normalized["checksum"] = ""
    return canonical_sha256(normalized)


def result_digest(value):
    """Independent full-result digest used as a refactor compatibility lock."""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def valid_bundle():
    scope = app_scope()
    bundle = {
        "schema_version": "1.1",
        "project": {
            "project_id": "LISTING-V11", "title": "Listing v1.1 fixture",
            "mode": "rebuild", "status": "READY_FOR_REVIEW",
            "snapshot_date": "2026-08-28", "target_stage": "PACKAGE_PASS",
            "conclusion": "PASS", "owner": "qa", "notes": "local read-only",
        },
        "execution_boundary": "read_only",
        "scope": {
            "marketplace": "US", "locale": "en-US", "seller_scope": "SELLER-1",
            "parent_asins": [PARENT], "intended_child_asins": [CHILD],
            "excluded_child_asins": [], "packs": ["1PK"], "colors": ["Black"], "sizes": ["M"],
        },
        "catalog_context": {
            "identity_status": "FROZEN", "identifier": CHILD, "identifier_type": "ASIN",
            "parentage_level": "child", "product_type": "KITCHEN_TOOL",
            "source_ids": ["SRC-SC"], "owner": "qa",
        },
        "rule_snapshots": [{
            "id": "RS-1", "marketplace": "US", "locale": "en-US", "seller_scope": "SELLER-1",
            "product_type": "KITCHEN_TOOL", "parentage_level": "child", "data_plane": "seller_listing",
            "schema_version": "account-2026-08-28", "requirements": "LISTING",
            "requirements_enforced": "ENFORCED", "source_ids": ["SRC-SC"],
            "retrieved_at": "2026-08-28T00:00:00Z", "status": "CURRENT",
            "checksum": "sha256:rules", "refresh_trigger": "before authorized submission",
        }],
        "field_resolutions": [{
            "id": "FR-BULLET", "semantic_role": "BULLET", "canonical_key": "bullet_point",
            "ui_label": "Bullet point", "data_plane": "seller_listing", "surface": "core_copy",
            "exists": True, "editable": True, "applicable": True, "max_characters": 500,
            "requirement_status": "REQUIRED", "visibility": "BUYER_VISIBLE",
            "rule_snapshot_ids": ["RS-1"], "application_scope": copy.deepcopy(scope),
            "status": "RESOLVED", "owner": "qa",
        }],
        "sources": [{
            "id": "SRC-SC", "type": "seller_central_screenshot", "locator": "/evidence/sc.png",
            "authority": "primary", "evidence_level": "E3", "seller_scope": "SELLER-1",
            "marketplace": "US", "locale": "en-US", "child_asins": [CHILD],
            "application_scope": copy.deepcopy(scope),
            "retrieved_at": "2026-08-28T00:00:00Z", "status": "USABLE",
            "proves": ["catalog identity", "current account fields", "included item"],
            "cannot_prove": ["frontend live state"],
            "capture_metadata": {
                "seller_scope": "SELLER-1", "marketplace": "US",
                "entity": f"{CHILD} / KITCHEN_TOOL", "page_context": "Manage All Inventory > Edit",
                "captured_at": "2026-08-28T00:00:00Z", "capture_region": "complete attributes tab",
                "coverage": "COMPLETE",
            },
        }, {
            "id": "SRC-PRODUCT", "type": "packaging_label", "locator": "/evidence/package.png",
            "authority": "primary", "evidence_level": "E3", "seller_scope": "SELLER-1",
            "marketplace": "US", "locale": "en-US", "child_asins": [CHILD],
            "application_scope": copy.deepcopy(scope),
            "retrieved_at": "2026-08-28T00:00:00Z", "status": "USABLE",
            "proves": ["included item"], "cannot_prove": ["Amazon field availability", "frontend live state"],
        }, {
            "id": "SRC-PDP", "type": "public_frontend", "locator": f"https://www.amazon.com/dp/{CHILD}",
            "authority": "public_observation", "evidence_level": "E2", "seller_scope": "SELLER-1",
            "marketplace": "US", "locale": "en-US", "child_asins": [CHILD],
            "application_scope": copy.deepcopy(scope),
            "retrieved_at": "2026-08-28T00:05:00Z", "status": "USABLE",
            "proves": ["target detail-page census at observation time"],
            "cannot_prove": ["backend truth", "current physical product capability"],
        }, {
            "id": "SRC-COMP", "type": "customer_review", "locator": "https://www.amazon.com/example-competitor",
            "authority": "public_observation", "evidence_level": "E1", "seller_scope": "SELLER-1",
            "marketplace": "US", "locale": "en-US", "child_asins": [CHILD],
            "application_scope": copy.deepcopy(scope),
            "retrieved_at": "2026-08-28T00:10:00Z", "status": "USABLE",
            "proves": ["competitor presentation and buyer-language observation"],
            "cannot_prove": ["target product capability", "market acceptance", "ranking effect"],
        }],
        "facts": [{
            "id": "F-1", "statement": "One black spatula is included.",
            "source_ids": ["SRC-SC", "SRC-PRODUCT"], "proving_source_ids": ["SRC-PRODUCT"],
            "application_scope": copy.deepcopy(scope), "verification_status": "VERIFIED",
            "content_status": "PUBLISHABLE", "evidence_level": "E3",
            "can_prove": ["included item"], "cannot_prove": ["performance"],
            "allowed_expression": "Includes one black spatula.",
            "prohibited_inferences": ["includes accessories"],
            "refresh_trigger": "variant or packaging change", "owner": "qa",
        }],
        "claims": [{
            "id": "C-1", "text": "Includes one black spatula.", "fact_ids": ["F-1"],
            "source_ids": ["SRC-SC", "SRC-PRODUCT"], "proving_source_ids": ["SRC-PRODUCT"],
            "application_scope": copy.deepcopy(scope), "support_status": "SUPPORTED",
            "content_status": "PUBLISHABLE", "evidence_level": "E3",
            "can_prove": ["included item"], "cannot_prove": ["performance"],
            "allowed_expression": "Includes one black spatula.",
            "prohibited_inferences": ["includes accessories"],
            "refresh_trigger": "variant or packaging change", "owner": "qa",
        }],
        "conflicts": [],
        "variant_topology": [{
            "id": "V-1", "parent_asin": PARENT, "child_asin": CHILD, "seller_sku": "SKU-1",
            "variation_theme": "ColorSize", "pack": "1PK", "color": "Black", "size": "M",
            "included_items": ["spatula"], "fact_ids": ["F-1"], "source_ids": ["SRC-SC", "SRC-PRODUCT"],
            "status": "VERIFIED",
        }],
        "method_registry": [
            {"id": "M-OFFICIAL", "name": "Current account field mapping", "classification": "OFFICIAL_CURRENT", "gate_eligible": True, "source_ids": ["SRC-SC"], "status": "CURRENT", "observed_at": "2026-08-28T00:00:00Z", "refresh_trigger": "before authorized submission"},
            {"id": "M-INTENT", "name": "Who-Scenario-Problem", "classification": "MULTI_SOURCE_HEURISTIC", "gate_eligible": False, "source_ids": [], "status": "REFERENCE", "observed_at": "2026-08-28T00:00:00Z", "refresh_trigger": "when positioning evidence changes"},
        ],
        "discovery": {
            "status": "COMPLETE",
            "evidence_pass": {"status": "COMPLETE", "source_ids": ["SRC-SC", "SRC-PRODUCT", "SRC-PDP"], "observations": [{"id": "OBS-1", "statement": "One child and one pack observed."}]},
            "interview_rounds": [{
                "id": "IR-1", "round_type": "TRUTH", "questions": [{
                    "id": "Q-1", "question": "What is included?", "impact_dimensions": ["VARIANT", "PROMISE"],
                    "response_id": "R-1",
                }],
            }, {
                "id": "IR-2", "round_type": "POSITIONING", "questions": [{
                    "id": "Q-2", "question": "Which closed inclusion answer should lead the purchase decision?",
                    "impact_dimensions": ["SCENARIO", "FIELD_ALLOCATION", "STRATEGIC_SELECTION"], "response_id": "R-2",
                }],
            }],
            "responses": [
                {"id": "R-1", "classification": "FACT_LEAD", "status": "ANSWERED", "answer": "One spatula", "p0_impact": True, "source_ids": ["SRC-PRODUCT"], "owner": "qa"},
                {"id": "R-2", "classification": "STRATEGIC_CHOICE", "status": "ANSWERED", "answer": "Lead with exact included quantity to prevent a wrong purchase.", "p0_impact": True, "source_ids": [], "owner": "qa"},
            ],
            "distillations": [
                {"id": "D-1", "record_type": "PRODUCT_TRUTH", "payload": {"coverage": "Scoped included quantity is verified."}, "response_ids": ["R-1"], "fact_ids": ["F-1"], "claim_ids": ["C-1"], "conflict_ids": []},
                {"id": "D-2", "record_type": "ROUND_2_SYNTHESIS", "payload": {"decision": "Exact included quantity is the highest-friction decision."}, "response_ids": ["R-2"], "fact_ids": ["F-1"], "claim_ids": ["C-1"], "conflict_ids": []},
                {"id": "D-3", "record_type": "PRODUCT_INTENT_BRIEF", "payload": {
                    "original_problem": "Buyers could not tell what quantity was included.",
                    "prior_alternative": "Rely on imagery or infer quantity from category convention.",
                    "chosen_form": "State the exact included quantity in a native answer.",
                    "deliberate_tradeoff": "Lead with purchase clarity instead of a broad performance promise.",
                    "intended_mechanism": "A scoped quantity statement removes the inference step.",
                    "longitudinal_observation": "Current research repeatedly exposed quantity ambiguity as a decision risk.",
                    "alternative_explanations": "Price and performance may also matter, but they do not resolve included quantity.",
                    "current_version_continuity": "The verified current pack still contains one black spatula.",
                    "current_choice": "Make exact included quantity the lead purchase-decision answer."
                }, "response_ids": ["R-2"], "fact_ids": ["F-1"], "claim_ids": ["C-1"], "conflict_ids": []},
                {"id": "D-4", "record_type": "ONE_BET_SELECTION", "payload": {
                    "selected_route_id": "ROUTE-QUANTITY-CLARITY",
                    "hero_moment": "The shopper checks exactly what arrives before buying.",
                    "closest_alternative": "A generic category listing that leaves quantity to inference.",
                    "desired_progress": "Choose the correct pack without a preventable quantity surprise.",
                    "mechanism": "A native, scoped one-item statement answers the decision directly.",
                    "material_boundary": "This route proves included quantity, not superior performance.",
                    "rejected_route_ids": ["ROUTE-PERFORMANCE-LEAD"],
                    "rejected_route_reasons": {"ROUTE-PERFORMANCE-LEAD": "No comparative performance evidence supports that lead."},
                    "proof_status": "PROVED",
                    "reversibility_test": "Run a controlled copy test and revert if purchase-quality guardrails worsen.",
                    "route_registry": [{
                        "route_id": "ROUTE-QUANTITY-CLARITY",
                        "core_user_or_state": "A shopper who must confirm the exact pack before purchase.",
                        "hero_moment": "The shopper checks exactly what arrives before buying.",
                        "closest_alternative": "A generic category listing that leaves quantity to inference.",
                        "desired_progress": "Choose the correct pack without a preventable quantity surprise.",
                        "mechanism": "A native, scoped one-item statement answers the decision directly.",
                        "material_boundary": "This route proves included quantity, not superior performance.",
                        "proof_status": "PROVED",
                        "decision_consequence": "Lead the first-screen decision with exact included quantity."
                    }, {
                        "route_id": "ROUTE-PERFORMANCE-LEAD",
                        "core_user_or_state": "A shopper comparing product performance before purchase.",
                        "hero_moment": "The shopper compares this item with a performance-led alternative.",
                        "closest_alternative": "A competing tool with verified comparative performance evidence.",
                        "desired_progress": "Choose the strongest performer for the intended task.",
                        "mechanism": "A comparative performance claim would carry the decision.",
                        "material_boundary": "No target comparative evidence currently supports this route.",
                        "proof_status": "UNSUPPORTED",
                        "decision_consequence": "Reject this route until comparative evidence is established."
                    }]
                }, "response_ids": ["R-2"], "fact_ids": ["F-1"], "claim_ids": ["C-1"], "conflict_ids": []},
            ],
            "evidence_actions": [],
            "stage_gates": [
                {"id": "GATE-RECON", "stage": "RECONNAISSANCE", "status": "PASS", "result": "Target, competitor, use-path, and current-rule reconnaissance completed before Round 1.", "evidence_source_ids": ["SRC-SC", "SRC-PDP", "SRC-COMP"], "record_refs": ["SRC-PDP", "market_research", "VOC-1", "COMP-1", "MR-1"], "reason": "", "closed_at": "2026-08-28T00:30:00Z", "owner": "qa"},
                {"id": "GATE-TRUTH", "stage": "PRODUCT_TRUTH", "status": "PASS", "result": "Scoped inclusion truth closed after Round 1.", "evidence_source_ids": ["SRC-PRODUCT"], "record_refs": ["IR-1", "D-1", "F-1"], "reason": "", "closed_at": "2026-08-28T01:00:00Z", "owner": "qa"},
                {"id": "GATE-R2", "stage": "ROUND_2", "status": "PASS", "result": "Purchase-decision route evaluated in Round 2.", "evidence_source_ids": ["SRC-COMP"], "record_refs": ["IR-2", "R-2", "D-2"], "reason": "", "closed_at": "2026-08-28T01:01:00Z", "owner": "qa"},
                {"id": "GATE-INTENT", "stage": "PRODUCT_INTENT_BRIEF", "status": "PASS", "result": "Intent brief prioritizes preventing wrong included-quantity expectations.", "evidence_source_ids": ["SRC-PRODUCT"], "record_refs": ["IR-2", "Q-2", "R-2", "D-3", "F-1"], "reason": "", "closed_at": "2026-08-28T01:02:00Z", "owner": "qa"},
                {"id": "GATE-ONEBET", "stage": "ONE_BET", "status": "PASS", "result": "One reversible bet selected: exact included quantity leads.", "evidence_source_ids": ["SRC-PRODUCT", "SRC-COMP"], "record_refs": ["IR-2", "Q-2", "R-2", "D-4", "F-1"], "reason": "", "closed_at": "2026-08-28T01:03:00Z", "owner": "qa"},
            ],
            "closure": {"status": "PASS", "reason": "Recon, product truth, Round 2, intent, and one-bet closed.", "closed_at": "2026-08-28T01:04:00Z", "owner": "qa"},
        },
        "market_research": {
            "status": "COMPLETE", "source_ids": ["SRC-COMP"],
            "voc_observations": [{"id": "VOC-1", "statement": "Buyers need the included quantity to be explicit.", "source_ids": ["SRC-COMP"]}],
            "competitor_observations": [{"id": "COMP-1", "statement": "A sampled alternative discloses included quantity in visible copy.", "source_ids": ["SRC-COMP"]}],
            "conclusions": [{"id": "MR-1", "statement": "Quantity answerability is a relevant decision gap; competitor evidence does not prove target contents.", "source_ids": ["SRC-COMP"]}],
            "reason": "", "owner": "qa",
        },
        "ptd_field_inventory": {
            "status": "COMPLETE", "product_type": "KITCHEN_TOOL", "rule_snapshot_ids": ["RS-1"],
            "evidence_source_ids": ["SRC-SC"], "declared_field_count": 1,
            "expected_fields": [{
                "id": "EF-1", "field_resolution_id": "FR-BULLET", "requirement_status": "REQUIRED",
                "trigger_status": "NOT_APPLICABLE", "p0_relevant": True, "closure_status": "CLOSED",
                "evidence_source_ids": ["SRC-SC"], "reason": "visible in complete account field capture",
            }], "checksum": "",
        },
        "decision_map": {"status": "FROZEN", "requirements": [{
            "id": "DR-1", "buyer_question": "What is included?", "priority": "P0",
            "application_scope": copy.deepcopy(scope), "fact_ids": ["F-1"], "claim_ids": ["C-1"],
            "early_disclosure_required": True, "assigned_surface": "core_copy", "status": "READY", "owner": "qa",
        }]},
        "decision_denominator_snapshot": {
            "status": "FROZEN", "frozen_at": "2026-08-28T01:05:00Z",
            "requirement_ids": ["DR-1"], "variant_row_ids": ["V-1"],
            "atoms": [{"id": "ATOM-1", "requirement_id": "DR-1", "marketplace": "US", "locale": "en-US", "variant_row_id": "V-1"}],
            "checksum": "",
        },
        "canonical_assertions": [{
            "id": "CA-1", "statement": "Includes one black spatula.", "fact_ids": ["F-1"],
            "claim_ids": ["C-1"], "application_scope": copy.deepcopy(scope), "status": "FINAL", "owner": "qa",
        }],
        "decision_answer_units": [{
            "id": "DAU-1", "atom_id": "ATOM-1", "requirement_id": "DR-1", "variant_row_id": "V-1",
            "answer_text": "Includes one black spatula.", "field_candidate_id": "FC-1",
            "canonical_assertion_ids": ["CA-1"], "fact_ids": ["F-1"], "claim_ids": ["C-1"],
            "status": "PASS", "owner": "qa",
        }],
        "surface_assignments": [{
            "id": "SA-1", "requirement_id": "DR-1", "primary_surface": "core_copy",
            "primary_carrier_kind": "NATIVE_VISIBLE", "field_resolution_id": "FR-BULLET",
            "supporting_surfaces": ["media"], "application_scope": copy.deepcopy(scope), "status": "PASS", "owner": "qa",
        }],
        "field_candidates": [{
            "id": "FC-1", "field_resolution_id": "FR-BULLET", "semantic_role": "BULLET",
            "value": "Includes one black spatula.", "application_scope": copy.deepcopy(scope),
            "fact_ids": ["F-1"], "claim_ids": ["C-1"], "content_status": "FINAL",
            "qa_status": "PASS", "owner": "qa",
        }],
        "semantic_consistency_matrix": [{
            "id": "SCM-1", "canonical_assertion_id": "CA-1", "field_candidate_ids": ["FC-1"],
            "status": "PASS", "notes": "Exact inclusion answer",
        }],
        "category_adapter": {"name": "generic", "version": "1.0", "status": "READY", "question_prompts": [], "evidence_probes": [], "return_risks": [], "qa_checks": []},
        "experiment_registry": [], "gate_reviews": [],
        "enriched_content_handoff": {
            "contract_version": "1.1", "snapshot_id": "", "parent_project_id": "",
            "parent_bundle_sha256": "", "status": "NOT_APPLICABLE", "maximum_output": "strategy_dependency_only",
            "marketplace": "", "locale": "", "product_type": "", "application_scope": app_scope(children=[], packs=[], colors=[], sizes=[]),
            "variant_row_ids": [], "fact_ids": [], "claim_ids": [], "blocked_claim_ids": [], "conflict_ids": [], "source_ids": [],
            "requested_content_types": [], "decision_requirements": [], "capability_snapshot_ids": [],
            "discovery_closure_hash": "", "ptd_inventory_hash": "", "decision_denominator_hash": "",
            "canonical_assertion_ids": [], "requirement_atoms": [],
            "prohibited_actions": ["modify_parent_truth", "expand_application_scope", "online_submission"],
            "predecessor_snapshot_id": "", "semantic_revision": 0, "refreeze_reason": "",
            "lineage_registry": [],
            "created_at": "", "owner": "", "checksum": "",
        },
        "publish_authorization": {
            "status": "NOT_AUTHORIZED", "authorization_id": "", "authorizer": "", "authorized_account": "",
            "system": "", "data_planes": [], "marketplace": "", "locale": "", "target_ids": [],
            "change_set_ids": [], "baseline_sha256": "", "change_set_sha256": "", "authorized_action": "",
            "attempt_limit": 0, "authorized_at": "", "expires_at": "", "rollback_scope": [], "notes": "",
        },
        "baseline": [], "change_set": [], "rollback": [], "live_readback": [], "record_templates": {},
    }
    bundle["ptd_field_inventory"]["checksum"] = hash_block(bundle["ptd_field_inventory"])
    bundle["decision_denominator_snapshot"]["checksum"] = hash_block(bundle["decision_denominator_snapshot"])
    return bundle


def reseal(bundle):
    bundle["ptd_field_inventory"]["checksum"] = hash_block(bundle["ptd_field_inventory"])
    bundle["decision_denominator_snapshot"]["checksum"] = hash_block(bundle["decision_denominator_snapshot"])


def delegated_handoff_bundle(status="FROZEN"):
    bundle = valid_bundle()
    bundle["project"].update({"target_stage": "HANDOFF_READY", "conclusion": "CONDITIONAL_PASS"})
    requirement = bundle["decision_map"]["requirements"][0]
    requirement.update({
        "assigned_surface": "enriched_content", "native_answer_required": True,
        "early_disclosure_required": False, "upstream_primary_carrier_ref": "",
    })
    bundle["surface_assignments"][0].update({
        "primary_surface": "enriched_content", "primary_carrier_kind": "A_PLUS_NATIVE_PENDING",
        "field_resolution_id": "",
    })
    bundle["field_candidates"] = []
    bundle["decision_answer_units"] = []
    bundle["semantic_consistency_matrix"] = []
    handoff = bundle["enriched_content_handoff"]
    handoff.update({
        "parent_project_id": "LISTING-V11", "status": status,
        "maximum_output": "preflight_package",
        "marketplace": "US", "locale": "en-US", "product_type": "KITCHEN_TOOL",
        "application_scope": app_scope(), "variant_row_ids": ["V-1"], "fact_ids": ["F-1"],
        "claim_ids": ["C-1"], "source_ids": ["SRC-PRODUCT"],
        "requested_content_types": ["PREMIUM_A_PLUS"],
        "decision_requirements": [copy.deepcopy(requirement)],
        "discovery_closure_hash": canonical_sha256(bundle["discovery"]["closure"]),
        "ptd_inventory_hash": hash_block(bundle["ptd_field_inventory"]),
        "decision_denominator_hash": hash_block(bundle["decision_denominator_snapshot"]),
        "canonical_assertion_ids": ["CA-1"],
        "requirement_atoms": copy.deepcopy(bundle["decision_denominator_snapshot"]["atoms"]),
        "predecessor_snapshot_id": "", "semantic_revision": 1, "refreeze_reason": "",
        "lineage_registry": [],
        "created_at": "2026-08-28T02:00:00Z", "owner": "qa",
    })
    handoff["snapshot_id"] = canonical_handoff_snapshot_id(handoff)
    handoff["checksum"] = canonical_handoff_hash(handoff)
    handoff["parent_bundle_sha256"] = canonical_parent_hash(bundle)
    return bundle


class ListingV11Tests(unittest.TestCase):
    def test_p0_field_contract_is_exact_and_unknown_keys_fail_closed(self):
        field = {
            "canonical_key": "item_name",
            "semantic_role": "ITEM_NAME",
            "surface": "core_copy",
            "data_plane": "seller_listing",
        }
        self.assertTrue(p0_field_contract_allows(field, "NATIVE_VISIBLE"))
        for mutation in (
            {"semantic_role": "TITLE"},
            {"surface": "backend_search_terms"},
            {"data_plane": "external_tool"},
            {"canonical_key": "invented_visible_field"},
        ):
            changed = {**field, **mutation}
            self.assertFalse(p0_field_contract_allows(changed, "NATIVE_VISIBLE"), changed)

    def test_valid_current_contract(self):
        result = validate_listing_bundle(valid_bundle())
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["derived_stage"], "PACKAGE_PASS")
        self.assertEqual(result["counts"]["p0_pass"], 1)

    def test_zero_denominator_and_absent_candidate_fail_closed(self):
        bundle = valid_bundle()
        bundle["decision_denominator_snapshot"]["atoms"] = []
        bundle["decision_denominator_snapshot"]["checksum"] = hash_block(bundle["decision_denominator_snapshot"])
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DENOM-004]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        bundle["field_candidates"] = []
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-ANSWER-003]" in item for item in result["errors"]), result["errors"])

    def test_answer_must_exist_and_use_same_assertion_chain(self):
        bundle = valid_bundle()
        bundle["decision_answer_units"][0]["answer_text"] = "Dishwasher safe."
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-ANSWER-005]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        bundle["canonical_assertions"][0]["claim_ids"] = []
        bundle["canonical_assertions"][0]["fact_ids"] = ["F-1"]
        bundle["decision_answer_units"][0]["fact_ids"] = []
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-ANSWER-010]" in item or "[L11-REF-002]" in item for item in result["errors"]), result["errors"])

    def test_duplicate_final_and_partial_variant_coverage_fail(self):
        bundle = valid_bundle()
        duplicate = copy.deepcopy(bundle["field_candidates"][0])
        duplicate["id"] = "FC-2"
        bundle["field_candidates"].append(duplicate)
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-CANDIDATE-007]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        bundle["scope"]["intended_child_asins"].append("B0SECOND")
        bundle["catalog_context"]["source_ids"] = ["SRC-SC"]
        bundle["sources"][0]["child_asins"].append("B0SECOND")
        for key in ("facts", "claims", "field_resolutions"):
            bundle[key][0]["application_scope"]["child_asins"].append("B0SECOND")
        bundle["decision_map"]["requirements"][0]["application_scope"]["child_asins"].append("B0SECOND")
        bundle["surface_assignments"][0]["application_scope"]["child_asins"].append("B0SECOND")
        bundle["field_candidates"][0]["application_scope"]["child_asins"].append("B0SECOND")
        bundle["canonical_assertions"][0]["application_scope"]["child_asins"].append("B0SECOND")
        second = copy.deepcopy(bundle["variant_topology"][0]); second.update({"id": "V-2", "child_asin": "B0SECOND", "seller_sku": "SKU-2"})
        bundle["variant_topology"].append(second)
        bundle["decision_denominator_snapshot"]["variant_row_ids"].append("V-2")
        bundle["decision_denominator_snapshot"]["atoms"].append({"id": "ATOM-2", "requirement_id": "DR-1", "marketplace": "US", "locale": "en-US", "variant_row_id": "V-2"})
        reseal(bundle)
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("atom:ATOM-2" in item and "[L11-ANSWER-008]" in item for item in result["errors"]), result["errors"])

    def test_v11_hx02_two_and_three_pack_use_real_variant_atoms_only(self):
        bundle = valid_bundle()
        children = ["B0HX0202PK", "B0HX0203PK"]
        broad = app_scope(children=children, packs=["2PK", "3PK"])
        bundle["scope"].update({"intended_child_asins": children, "packs": ["2PK", "3PK"]})
        bundle["catalog_context"]["identifier"] = PARENT
        for source in bundle["sources"]:
            source["child_asins"] = children
            source["application_scope"] = copy.deepcopy(broad)
            if source["id"] == "SRC-PDP":
                source["locator"] = f"https://www.amazon.com/dp/{children[0]}"
        for collection in ("facts", "claims", "field_resolutions", "canonical_assertions"):
            bundle[collection][0]["application_scope"] = copy.deepcopy(broad)
        bundle["decision_map"]["requirements"][0]["application_scope"] = copy.deepcopy(broad)
        bundle["surface_assignments"][0]["application_scope"] = copy.deepcopy(broad)
        bundle["field_candidates"][0]["application_scope"] = copy.deepcopy(broad)
        base = bundle["variant_topology"][0]
        bundle["variant_topology"] = [
            {**copy.deepcopy(base), "id": "V-2PK", "child_asin": children[0], "seller_sku": "HX02-SKU-2", "pack": "2PK"},
            {**copy.deepcopy(base), "id": "V-3PK", "child_asin": children[1], "seller_sku": "HX02-SKU-3", "pack": "3PK"},
        ]
        atoms = [
            {"id": "ATOM-2PK", "requirement_id": "DR-1", "marketplace": "US", "locale": "en-US", "variant_row_id": "V-2PK"},
            {"id": "ATOM-3PK", "requirement_id": "DR-1", "marketplace": "US", "locale": "en-US", "variant_row_id": "V-3PK"},
        ]
        bundle["decision_denominator_snapshot"].update({
            "variant_row_ids": ["V-2PK", "V-3PK"], "atoms": atoms,
        })
        first = bundle["decision_answer_units"][0]
        first.update({"atom_id": "ATOM-2PK", "variant_row_id": "V-2PK"})
        second = copy.deepcopy(first); second.update({"id": "DAU-3PK", "atom_id": "ATOM-3PK", "variant_row_id": "V-3PK"})
        bundle["decision_answer_units"] = [first, second]
        reseal(bundle)
        result = validate_listing_bundle(bundle)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["counts"]["p0_atoms"], 2)
        self.assertEqual(result["counts"]["p0_pass"], 2)

    def test_evidence_strength_rule_freshness_and_conflict_are_fail_closed(self):
        bundle = valid_bundle()
        bundle["sources"][1]["type"] = "owner_statement"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-FACT-005]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        bundle["sources"][1]["status"] = "BLOCKED"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-FACT-005]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        bundle["sources"][1]["evidence_level"] = "E0"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-FACT-005]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        bundle["rule_snapshots"][0]["retrieved_at"] = "2020-01-01T00:00:00Z"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-RULE-006]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        bundle["conflicts"] = [{"id": "X-1", "affected_fact_ids": ["F-1"], "affected_claim_ids": [], "status": "OPEN"}]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-ANSWER-013]" in item for item in result["errors"]), result["errors"])

    def test_seller_central_metadata_and_ptd_conditional(self):
        bundle = valid_bundle()
        del bundle["sources"][0]["capture_metadata"]["capture_region"]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-SOURCE-007]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        bundle["sources"][0]["capture_metadata"]["entity"] = "unrelated catalog object"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-SOURCE-014]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle()
        expected = bundle["ptd_field_inventory"]["expected_fields"][0]
        expected.update({"requirement_status": "CONDITIONAL", "trigger_status": "TRIGGERED", "closure_status": "HOLD"})
        reseal(bundle)
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-PTD-008]" in item for item in result["errors"]), result["errors"])

    def test_item_highlights_is_first_class_and_fake_subtitle_is_rejected(self):
        bundle = valid_bundle()
        item = copy.deepcopy(bundle["field_resolutions"][0])
        item.update({
            "id": "FR-IH", "semantic_role": "ITEM_HIGHLIGHTS", "canonical_key": "item_highlights",
            "ui_label": "Item highlights", "max_characters": 125,
            "account_evidence_source_ids": ["SRC-SC"], "requirement_status": "OPTIONAL",
        })
        bundle["field_resolutions"].append(item)
        bundle["ptd_field_inventory"]["expected_fields"].append({
            "id": "EF-IH", "field_resolution_id": "FR-IH", "requirement_status": "OPTIONAL",
            "trigger_status": "NOT_APPLICABLE", "p0_relevant": False, "closure_status": "CLOSED",
            "evidence_source_ids": ["SRC-SC"], "reason": "account field available",
        })
        bundle["ptd_field_inventory"]["declared_field_count"] = 2
        reseal(bundle)
        self.assertTrue(validate_listing_bundle(bundle)["ok"], validate_listing_bundle(bundle)["errors"])
        bundle["field_resolutions"][1]["canonical_key"] = "item_subtitle"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-FIELD-001]" in item for item in result["errors"]), result["errors"])
        unavailable = valid_bundle()
        item = copy.deepcopy(unavailable["field_resolutions"][0])
        item.update({
            "id": "FR-IH", "semantic_role": "ITEM_HIGHLIGHTS", "canonical_key": "item_highlights",
            "ui_label": "Item highlights", "max_characters": None, "exists": False,
            "editable": False, "applicable": False, "status": "NOT_AVAILABLE",
            "account_evidence_source_ids": ["SRC-SC"], "requirement_status": "OPTIONAL",
        })
        unavailable["field_resolutions"].append(item)
        unavailable["ptd_field_inventory"]["expected_fields"].append({
            "id": "EF-IH", "field_resolution_id": "FR-IH", "requirement_status": "OPTIONAL",
            "trigger_status": "NOT_APPLICABLE", "p0_relevant": False,
            "closure_status": "PROVEN_NOT_AVAILABLE", "evidence_source_ids": ["SRC-SC"],
            "reason": "field absent in complete account capture",
        })
        unavailable["ptd_field_inventory"]["declared_field_count"] = 2
        reseal(unavailable)
        self.assertTrue(validate_listing_bundle(unavailable)["ok"], validate_listing_bundle(unavailable)["errors"])

    def test_category_adapter_closed_set_and_no_ptd_override(self):
        for name in ("generic", "apparel/fit", "connected-device", "home/kitchen", "regulated/beauty"):
            with self.subTest(name=name):
                bundle = valid_bundle(); bundle["category_adapter"]["name"] = name
                if name != "generic":
                    bundle["category_adapter"].update({
                        "question_prompts": [f"Close {name} buyer questions"],
                        "evidence_probes": [f"Obtain {name} product evidence"],
                        "return_risks": [f"Audit {name} return risk"],
                        "qa_checks": [f"Run {name} scoped QA"],
                    })
                self.assertTrue(validate_listing_bundle(bundle)["ok"], validate_listing_bundle(bundle)["errors"])
        bundle = valid_bundle(); bundle["category_adapter"]["field_overrides"] = ["item_name"]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-ADAPTER-002]" in item for item in result["errors"]), result["errors"])
        bundle = valid_bundle(); bundle["category_adapter"]["name"] = "regulated/beauty"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-ADAPTER-007]" in item for item in result["errors"]), result["errors"])

    def test_unknown_p0_response_requires_evidence_action(self):
        bundle = valid_bundle()
        response = bundle["discovery"]["responses"][0]
        response.update({"classification": "UNKNOWN_SKIP", "status": "SKIP", "answer": ""})
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DISCOVERY-010]" in item for item in result["errors"]), result["errors"])

    def test_result_received_needs_coordinator_and_project_pass_cannot_outrun(self):
        frozen = delegated_handoff_bundle("FROZEN")
        frozen_result = validate_listing_bundle(frozen)
        self.assertTrue(frozen_result["ok"], frozen_result["errors"])
        self.assertEqual(frozen_result["derived_stage"], "HANDOFF_READY")
        self.assertEqual(frozen_result["counts"]["p0_delegated"], 1)
        bundle = delegated_handoff_bundle("RESULT_RECEIVED")
        self.assertEqual(canonical_parent_hash(frozen), canonical_parent_hash(bundle))
        self.assertEqual(canonical_handoff_hash(frozen["enriched_content_handoff"]), canonical_handoff_hash(bundle["enriched_content_handoff"]))
        bundle["project"]["conclusion"] = "PASS"
        handoff = bundle["enriched_content_handoff"]
        handoff["checksum"] = canonical_handoff_hash(handoff)
        handoff["parent_bundle_sha256"] = canonical_parent_hash(bundle)
        result = validate_listing_bundle(bundle)
        self.assertEqual(result["derived_gates"]["package"], "BLOCKED")
        self.assertTrue(any("[L11-PROJECT-006]" in item for item in result["errors"]), result["errors"])
        self.assertTrue(any("L11-HANDOFF-W01" in item for item in result["warnings"]), result["warnings"])

    def test_not_applicable_handoff_cannot_waive_delegated_p0(self):
        bundle = delegated_handoff_bundle("FROZEN")
        bundle["enriched_content_handoff"] = copy.deepcopy(valid_bundle()["enriched_content_handoff"])
        result = validate_listing_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["counts"]["p0_delegated"], 0)
        self.assertTrue(any("[L11-HANDOFF-022]" in item for item in result["errors"]), result["errors"])
        self.assertTrue(any("[L11-ANSWER-008]" in item for item in result["errors"]), result["errors"])
        self.assertEqual(result["derived_gates"]["package"], "BLOCKED")

    def test_parent_frozen_hash_ignores_downstream_lifecycle_but_not_truth(self):
        frozen = delegated_handoff_bundle("FROZEN")
        baseline = canonical_parent_hash(frozen)
        advanced = copy.deepcopy(frozen)
        advanced["project"].update({"status": "RESULT_RECEIVED", "target_stage": "LIVE_MATCH", "conclusion": "LIVE_PASS"})
        advanced["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
        advanced["gate_reviews"] = [{"id": "GR-1", "status": "PASS"}]
        advanced["experiment_registry"] = [{"id": "EXP-1", "status": "COMPLETE"}]
        advanced["publish_authorization"]["status"] = "AUTHORIZED"
        advanced["baseline"] = [{"id": "BL-LATER"}]
        advanced["change_set"] = [{"id": "CHG-LATER"}]
        advanced["rollback"] = [{"id": "RB-LATER"}]
        advanced["live_readback"] = [{"child_asin": CHILD, "status": "LIVE_MATCH"}]
        self.assertEqual(baseline, canonical_parent_hash(advanced))
        truth_changed = copy.deepcopy(frozen)
        truth_changed["facts"][0]["statement"] = "Two spatulas are included."
        self.assertNotEqual(baseline, canonical_parent_hash(truth_changed))
        local_answer_changed = copy.deepcopy(frozen)
        local_answer_changed["field_candidates"] = [{"id": "FC-LATE", "value": "changed"}]
        self.assertNotEqual(baseline, canonical_parent_hash(local_answer_changed))
        authority_lifecycle_changed = copy.deepcopy(frozen)
        authority_lifecycle_changed["execution_boundary"] = "authorized_submission"
        self.assertNotEqual(baseline, canonical_parent_hash(authority_lifecycle_changed))

    def test_p0_requirement_assertion_answer_candidate_and_matrix_share_one_chain(self):
        bundle = valid_bundle()
        second_fact = copy.deepcopy(bundle["facts"][0])
        second_fact.update({"id": "F-2", "statement": "The handle is black."})
        bundle["facts"].append(second_fact)
        bundle["claims"][0]["fact_ids"] = ["F-2"]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-ASSERT-003]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        unrelated = copy.deepcopy(bundle["canonical_assertions"][0])
        unrelated.update({"id": "CA-OTHER", "statement": "Dishwasher safe.", "claim_ids": []})
        bundle["canonical_assertions"].append(unrelated)
        bundle["semantic_consistency_matrix"][0]["canonical_assertion_id"] = "CA-OTHER"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-SEMANTIC-004]" in item for item in result["errors"]), result["errors"])
        self.assertTrue(any("[L11-SEMANTIC-005]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["claims"][0]["support_status"] = "UNSUPPORTED"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DECISION-007]" in item for item in result["errors"]), result["errors"])
        self.assertEqual(result["derived_gates"]["decision"], "BLOCKED")

    def test_proving_sources_must_be_usable_and_cover_full_bound_scope(self):
        mutations = (
            ("status", "PARTIAL"),
            ("seller_scope", "OTHER-SELLER"),
            ("marketplace", "CA"),
            ("locale", "fr-CA"),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                bundle = valid_bundle()
                bundle["sources"][1][key] = value
                result = validate_listing_bundle(bundle)
                self.assertTrue(any("[L11-FACT-005]" in item for item in result["errors"]), result["errors"])
        for dimension in ("parent_asins", "child_asins", "packs", "colors", "sizes"):
            with self.subTest(dimension=dimension):
                bundle = valid_bundle()
                bundle["sources"][1]["application_scope"][dimension] = []
                if dimension == "child_asins":
                    bundle["sources"][1]["child_asins"] = []
                result = validate_listing_bundle(bundle)
                self.assertTrue(any("[L11-FACT-005]" in item for item in result["errors"]), result["errors"])

    def test_identity_cannot_be_stale_partial_or_lingxing_only(self):
        bundle = valid_bundle()
        lingxing = copy.deepcopy(bundle["sources"][0])
        lingxing.update({
            "id": "SRC-LX", "type": "lingxing_mirror", "locator": "lingxing:readonly",
            "proves": ["catalog identity", "parent child mapping"],
        })
        lingxing.pop("capture_metadata", None)
        bundle["sources"].append(lingxing)
        bundle["catalog_context"]["source_ids"] = ["SRC-LX"]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-IDENTITY-003]" in item for item in result["errors"]), result["errors"])

        for mutation in ("STALE", "PARTIAL"):
            with self.subTest(status=mutation):
                bundle = valid_bundle()
                bundle["sources"][0]["status"] = mutation
                result = validate_listing_bundle(bundle)
                self.assertTrue(any("[L11-IDENTITY-002]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["sources"][0]["proves"] = ["current account fields"]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-IDENTITY-003]" in item for item in result["errors"]), result["errors"])

    def test_current_rule_and_item_highlights_need_current_full_account_evidence(self):
        bundle = valid_bundle()
        bundle["sources"][0]["application_scope"]["packs"] = []
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-RULE-008]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        item = copy.deepcopy(bundle["field_resolutions"][0])
        item.update({
            "id": "FR-IH", "semantic_role": "ITEM_HIGHLIGHTS", "canonical_key": "item_highlights",
            "ui_label": "Item highlights", "max_characters": 125,
            "account_evidence_source_ids": ["SRC-SC"], "requirement_status": "OPTIONAL",
        })
        bundle["field_resolutions"].append(item)
        bundle["sources"][0]["application_scope"]["packs"] = []
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-FIELD-006]" in item for item in result["errors"]), result["errors"])

    def test_p0_field_carrier_matrix_and_final_candidate_are_fail_closed(self):
        cases = (
            ("visibility", "BACKEND_ONLY", "L11-SURFACE-006"),
            ("surface", "enriched_content", "L11-SURFACE-006"),
            ("data_plane", "external_tool", "L11-SURFACE-006"),
            ("editable", False, "L11-CANDIDATE-009"),
        )
        for key, value, code in cases:
            with self.subTest(key=key):
                bundle = valid_bundle()
                bundle["field_resolutions"][0][key] = value
                result = validate_listing_bundle(bundle)
                self.assertTrue(any(f"[{code}]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["surface_assignments"][0]["application_scope"]["packs"] = []
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-SURFACE-009]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        second_field = copy.deepcopy(bundle["field_resolutions"][0])
        second_field["id"] = "FR-OTHER"
        bundle["field_resolutions"].append(second_field)
        bundle["field_candidates"][0]["field_resolution_id"] = "FR-OTHER"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-ANSWER-016]" in item for item in result["errors"]), result["errors"])
        self.assertTrue(any("[L11-PTD-016]" in item for item in result["errors"]), result["errors"])

    def test_p0_cannot_relabel_hidden_metadata_or_community_fields_as_native(self):
        cases = (
            ("COMMUNITY_QA", "customer_questions"),
            ("ALT_METADATA", "image_alt_text"),
            ("BACKEND_TERMS", "generic_keyword"),
        )
        for semantic_role, canonical_key in cases:
            with self.subTest(semantic_role=semantic_role):
                bundle = valid_bundle()
                bundle["field_resolutions"][0].update({
                    "semantic_role": semantic_role,
                    "canonical_key": canonical_key,
                })
                bundle["field_candidates"][0]["semantic_role"] = semantic_role
                result = validate_listing_bundle(bundle)
                self.assertFalse(result["ok"], result)
                self.assertTrue(
                    any("[L11-SURFACE-006]" in item for item in result["errors"]),
                    result["errors"],
                )
                if semantic_role == "COMMUNITY_QA":
                    self.assertTrue(
                        any("[L11-FIELD-007]" in item for item in result["errors"]),
                        result["errors"],
                    )

    def test_ptd_complete_requires_closed_fields_and_complete_applicable_sc_capture(self):
        bundle = valid_bundle()
        bundle["sources"][0]["capture_metadata"]["coverage"] = "PARTIAL"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-PTD-006]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["field_resolutions"][0]["status"] = "HOLD"
        bundle["field_resolutions"][0]["exists"] = False
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-PTD-009]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["ptd_field_inventory"]["expected_fields"][0]["requirement_status"] = "OPTIONAL"
        reseal(bundle)
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-PTD-015]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        duplicate = copy.deepcopy(bundle["ptd_field_inventory"]["expected_fields"][0])
        duplicate["id"] = "EF-DUP"
        bundle["ptd_field_inventory"]["expected_fields"].append(duplicate)
        bundle["ptd_field_inventory"]["declared_field_count"] = 2
        reseal(bundle)
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-PTD-016]" in item for item in result["errors"]), result["errors"])

    def test_discovery_uses_formal_one_to_one_response_objects(self):
        bundle = valid_bundle()
        question = bundle["discovery"]["interview_rounds"][0]["questions"][0]
        question["response"] = question.pop("response_id")
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DISCOVERY-018]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["discovery"]["responses"][0]["inline_note"] = "not contracted"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DISCOVERY-015]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        duplicate = copy.deepcopy(bundle["discovery"]["interview_rounds"][0]["questions"][0])
        duplicate["id"] = "Q-2"
        bundle["discovery"]["interview_rounds"][0]["questions"].append(duplicate)
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DISCOVERY-005]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["discovery"]["responses"][0].update({"classification": "UNKNOWN_SKIP", "status": "ANSWERED"})
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DISCOVERY-022]" in item for item in result["errors"]), result["errors"])

    def test_method_market_and_decision_statuses_control_gates(self):
        bundle = valid_bundle()
        bundle["method_registry"][0]["invented_score"] = 100
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-METHOD-005]" in item for item in result["errors"]), result["errors"])
        self.assertEqual(result["derived_gates"]["package"], "BLOCKED")

        bundle = valid_bundle()
        bundle["method_registry"][0]["observed_at"] = "2020-01-01T00:00:00Z"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-METHOD-008]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["market_research"].update({"status": "COMPLETE", "source_ids": ["SRC-SC"], "conclusions": []})
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-MARKET-004]" in item for item in result["errors"]), result["errors"])
        self.assertEqual(result["derived_gates"]["decision"], "BLOCKED")

        bundle = valid_bundle()
        bundle["market_research"].update({
            "status": "COMPLETE", "source_ids": ["SRC-SC"],
            "conclusions": [{"id": "MR-1", "statement": "", "source_ids": []}],
        })
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-MARKET-007]" in item or "[L11-REF-002]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["decision_map"]["status"] = "DRAFT"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DECISION-004]" in item for item in result["errors"]), result["errors"])
        self.assertEqual(result["derived_gates"]["decision"], "BLOCKED")

        bundle = valid_bundle()
        bundle["decision_map"]["requirements"][0]["status"] = "HOLD"
        reseal(bundle)
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DECISION-010]" in item for item in result["errors"]), result["errors"])
        self.assertEqual(result["derived_gates"]["decision"], "BLOCKED")

        bundle = valid_bundle()
        bundle["decision_map"]["manual_gate"] = "PASS"
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-DECISION-008]" in item for item in result["errors"]), result["errors"])

    def test_gate_reviews_and_experiments_are_records_not_overrides(self):
        bundle = valid_bundle()
        bundle["field_candidates"] = []
        bundle["gate_reviews"] = [{
            "id": "GR-1", "gate": "candidates", "status": "PASS", "reviewer": "owner",
            "reviewed_at": "2026-08-28T03:00:00Z", "evidence_source_ids": [],
            "blocker_ids": [], "notes": "manual override attempt",
        }]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-GATE-005]" in item for item in result["errors"]), result["errors"])
        self.assertEqual(result["derived_gates"]["candidates"], "BLOCKED")

        bundle = valid_bundle()
        bundle["experiment_registry"] = [{
            "id": "EXP-1", "hypothesis": "Copy improves comprehension", "status": "PLANNED",
            "application_scope": app_scope(), "metric": "conversion_rate", "baseline_ref": "",
            "candidate_ref": "", "started_at": "", "ended_at": "", "owner": "qa", "decision": "",
        }]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[L11-EXPERIMENT-006]" in item for item in result["errors"]), result["errors"])
        self.assertEqual(result["derived_gates"]["package"], "BLOCKED")

    def test_handoff_semantic_refreeze_requires_new_content_addressed_lineage(self):
        initial = delegated_handoff_bundle("FROZEN")
        old_id = initial["enriched_content_handoff"]["snapshot_id"]

        reused = copy.deepcopy(initial)
        reused["decision_map"]["requirements"][0]["buyer_question"] = "What exactly is included?"
        reused["enriched_content_handoff"]["decision_requirements"] = copy.deepcopy(reused["decision_map"]["requirements"])
        result = validate_listing_bundle(reused)
        self.assertTrue(any("[L11-HANDOFF-026]" in item or "[L11-HANDOFF-011]" in item for item in result["errors"]), result["errors"])

        refrozen = copy.deepcopy(reused)
        handoff = refrozen["enriched_content_handoff"]
        handoff.update({
            "semantic_revision": 2,
            "predecessor_snapshot_id": old_id,
            "refreeze_reason": "Buyer question clarified without expanding the frozen evidence chain.",
            "lineage_registry": [build_lineage_record(
                initial["enriched_content_handoff"],
                successor_snapshot_id="",
                superseded_at="2026-08-28T02:30:00Z",
            )],
            "created_at": "2026-08-28T03:00:00Z",
            "snapshot_id": "", "checksum": "", "parent_bundle_sha256": "",
        })
        handoff["snapshot_id"] = canonical_handoff_snapshot_id(handoff)
        handoff["lineage_registry"][0]["successor_snapshot_id"] = handoff["snapshot_id"]
        handoff["lineage_registry"][0]["record_checksum"] = canonical_lineage_record_hash(
            handoff["lineage_registry"][0]
        )
        handoff["checksum"] = canonical_handoff_hash(handoff)
        handoff["parent_bundle_sha256"] = canonical_parent_hash(refrozen)
        self.assertNotEqual(old_id, handoff["snapshot_id"])
        result = validate_listing_bundle(refrozen)
        self.assertTrue(result["ok"], result["errors"])

        bad_lineage = copy.deepcopy(refrozen)
        bad_lineage["enriched_content_handoff"]["predecessor_snapshot_id"] = "SNAP-OLD"
        bad_lineage["enriched_content_handoff"]["snapshot_id"] = canonical_handoff_snapshot_id(bad_lineage["enriched_content_handoff"])
        bad_lineage["enriched_content_handoff"]["checksum"] = canonical_handoff_hash(bad_lineage["enriched_content_handoff"])
        bad_lineage["enriched_content_handoff"]["parent_bundle_sha256"] = canonical_parent_hash(bad_lineage)
        result = validate_listing_bundle(bad_lineage)
        self.assertTrue(any("[L11-HANDOFF-025]" in item for item in result["errors"]), result["errors"])

    def test_refreeze_registry_rejects_random_jump_unsuperseded_and_wrong_successor(self):
        previous = delegated_handoff_bundle("FROZEN")
        base = delegated_handoff_bundle("FROZEN")
        handoff = base["enriched_content_handoff"]
        handoff.update({
            "semantic_revision": 2,
            "predecessor_snapshot_id": previous["enriched_content_handoff"]["snapshot_id"],
            "refreeze_reason": "Parent evidence delta resolved.",
            "lineage_registry": [build_lineage_record(
                previous["enriched_content_handoff"],
                successor_snapshot_id="",
                superseded_at="2026-08-28T02:30:00Z",
            )],
            "created_at": "2026-08-28T03:00:00Z",
            "snapshot_id": "", "checksum": "", "parent_bundle_sha256": "",
        })

        def reseal_handoff(bundle: dict) -> None:
            current = bundle["enriched_content_handoff"]
            current["snapshot_id"] = canonical_handoff_snapshot_id(current)
            current["lineage_registry"][0]["successor_snapshot_id"] = current["snapshot_id"]
            current["lineage_registry"][0]["record_checksum"] = canonical_lineage_record_hash(
                current["lineage_registry"][0]
            )
            current["checksum"] = canonical_handoff_hash(current)
            current["parent_bundle_sha256"] = canonical_parent_hash(bundle)

        reseal_handoff(base)
        valid_result = validate_listing_bundle(base)
        self.assertTrue(valid_result["ok"], valid_result["errors"])

        cases = {
            "random_predecessor": lambda h: h.update({"predecessor_snapshot_id": "HO-" + "9" * 20}),
            "revision_jump": lambda h: h.update({"semantic_revision": 3}),
            "not_superseded": lambda h: h["lineage_registry"][0].update({"status": "FROZEN"}),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                bundle = copy.deepcopy(base)
                mutate(bundle["enriched_content_handoff"])
                reseal_handoff(bundle)
                result = validate_listing_bundle(bundle)
                self.assertFalse(result["ok"], result)
                self.assertTrue(
                    any("[L11-HANDOFF-027]" in item for item in result["errors"]),
                    result["errors"],
                )

        wrong_successor = copy.deepcopy(base)
        current = wrong_successor["enriched_content_handoff"]
        current["lineage_registry"][0]["successor_snapshot_id"] = "HO-" + "8" * 20
        current["lineage_registry"][0]["record_checksum"] = canonical_lineage_record_hash(
            current["lineage_registry"][0]
        )
        current["checksum"] = canonical_handoff_hash(current)
        current["parent_bundle_sha256"] = canonical_parent_hash(wrong_successor)
        result = validate_listing_bundle(wrong_successor)
        self.assertFalse(result["ok"], result)
        self.assertTrue(any("[L11-HANDOFF-027]" in item for item in result["errors"]), result["errors"])

    def test_early_aplus_disclosure_requires_a_real_upstream_answer(self):
        bundle = delegated_handoff_bundle("FROZEN")
        requirement = bundle["decision_map"]["requirements"][0]
        requirement.update({"early_disclosure_required": True, "upstream_primary_carrier_ref": "SA-EARLY"})
        early_assignment = copy.deepcopy(valid_bundle()["surface_assignments"][0])
        early_assignment["id"] = "SA-EARLY"
        bundle["surface_assignments"].append(early_assignment)
        bundle["field_candidates"] = copy.deepcopy(valid_bundle()["field_candidates"])
        bundle["decision_answer_units"] = copy.deepcopy(valid_bundle()["decision_answer_units"])
        bundle["semantic_consistency_matrix"] = copy.deepcopy(valid_bundle()["semantic_consistency_matrix"])
        handoff = bundle["enriched_content_handoff"]
        handoff["decision_requirements"] = [copy.deepcopy(requirement)]
        handoff.update({"snapshot_id": "", "checksum": "", "parent_bundle_sha256": ""})
        handoff["snapshot_id"] = canonical_handoff_snapshot_id(handoff)
        handoff["checksum"] = canonical_handoff_hash(handoff)
        handoff["parent_bundle_sha256"] = canonical_parent_hash(bundle)
        result = validate_listing_bundle(bundle)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["counts"]["p0_pass"], 1)
        self.assertEqual(result["counts"]["p0_delegated"], 1)

        missing = copy.deepcopy(bundle)
        missing["decision_answer_units"] = []
        missing["field_candidates"] = []
        missing["semantic_consistency_matrix"] = []
        missing["enriched_content_handoff"]["parent_bundle_sha256"] = canonical_parent_hash(missing)
        result = validate_listing_bundle(missing)
        self.assertTrue(any("[L11-ANSWER-008]" in item for item in result["errors"]), result["errors"])

    def test_v11_direct_api_enforces_strict_publication_and_readback(self):
        bundle = valid_bundle()
        bundle["execution_boundary"] = "authorized_submission"
        bundle["project"].update({"mode": "publish_support", "target_stage": "AUTHORIZED_SUBMISSION"})
        bundle["publish_authorization"]["status"] = "AUTHORIZED"
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[LST-PUBLISH-002]" in item or "[LST-AUTH-012]" in item for item in result["errors"]), result["errors"])

        bundle = valid_bundle()
        bundle["project"]["conclusion"] = "LIVE_PASS"
        result = validate_listing_bundle_v11(bundle)
        self.assertTrue(any("[L11-READBACK-001]" in item for item in result["errors"]), result["errors"])

    def test_unicode_is_fail_closed_without_validator_or_cli_crash(self):
        for text in ("safe\u202ebidi", "Cafe\u0301", "bad\ud800value"):
            with self.subTest(text=ascii(text)):
                bundle = valid_bundle()
                bundle["project"]["title"] = text
                result = validate_listing_bundle_v11(bundle)
                self.assertFalse(result["ok"])
                self.assertTrue(any("[L11-UNICODE-001]" in item for item in result["errors"]), result["errors"])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unicode.json"
            path.write_text(json.dumps({**valid_bundle(), "project": {**valid_bundle()["project"], "title": "bad\ud800value"}}, ensure_ascii=True), encoding="utf-8")
            run = subprocess.run(
                [sys.executable, str(HERE / "validate_listing_bundle.py"), str(path)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(run.returncode, 0)
            payload = json.loads(run.stdout)
            self.assertTrue(any("[L11-UNICODE-001]" in item for item in payload["errors"]), payload)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-utf8.json"
            path.write_bytes(b"\xff")
            run = subprocess.run(
                [sys.executable, str(HERE / "validate_listing_bundle.py"), str(path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(run.returncode, 2)
            self.assertNotIn("Traceback", run.stderr)
            payload = json.loads(run.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(any("[LST-IO-001]" in item for item in payload["errors"]), payload)

    def test_migration_cli_rejects_same_output_and_report_path(self):
        legacy = {
            "schema_version": "1.0", "project": {}, "scope": {}, "sources": [],
            "catalog_context": {}, "rule_snapshots": [], "field_resolutions": [], "facts": [],
            "claims": [], "conflicts": [], "variant_topology": [], "decision_map": {"requirements": []},
            "surface_assignments": [], "field_candidates": [], "enriched_content_handoff": {},
            "publish_authorization": {}, "baseline": [], "change_set": [], "rollback": [], "live_readback": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "legacy.json"
            output_path = Path(directory) / "same.json"
            input_path.write_text(json.dumps(legacy), encoding="utf-8")
            run = subprocess.run(
                [sys.executable, str(HERE / "migrate_listing_bundle.py"), str(input_path),
                 "--output", str(output_path), "--report", str(output_path)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("different files", run.stderr)
            self.assertFalse(output_path.exists())

    def test_migration_cli_invalid_utf8_is_structured_exit_two_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "invalid-utf8.json"
            output_path = Path(directory) / "migrated.json"
            report_path = Path(directory) / "migration-report.json"
            input_path.write_bytes(b"\xff\xfe{")
            run = subprocess.run(
                [sys.executable, str(HERE / "migrate_listing_bundle.py"), str(input_path),
                 "--output", str(output_path), "--report", str(report_path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            self.assertNotIn("Traceback", run.stderr)
            payload = json.loads(run.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(any("[LST-MIGRATION-IO-001]" in item for item in payload["errors"]), payload)
            self.assertFalse(output_path.exists())
            self.assertFalse(report_path.exists())

    def test_renderer_is_deterministic_read_only_and_escapes_untrusted_text(self):
        from render_listing_report import render_listing_report

        bundle = valid_bundle()
        bundle["project"]["title"] = '<img src=x onerror="alert(1)">'
        bundle["sources"][0]["locator"] = "javascript:alert(1)"
        first = render_listing_report(bundle)
        second = render_listing_report(bundle)
        self.assertEqual(first, second)
        self.assertIn("&lt;img", first)
        self.assertNotIn('href="javascript:', first)
        lowered = first.lower()
        self.assertNotIn("localstorage", lowered)
        self.assertNotIn("<input", lowered)
        self.assertNotIn("<form", lowered)
        self.assertIn("@media(max-width:390px)", first)
        self.assertIn("@media(max-width:768px)", first)

    def test_renderer_rejects_structural_invalidity_but_renders_business_block(self):
        from render_listing_report import render_listing_report

        bundle = valid_bundle()
        bundle.pop("scope")
        with self.assertRaises(ValueError):
            render_listing_report(bundle)
        blocked = valid_bundle()
        blocked["field_candidates"] = []
        html = render_listing_report(blocked)
        self.assertIn("BLOCKED", html)

    def test_v11_authorized_status_cannot_bypass_baseline_change_and_rollback(self):
        bundle = valid_bundle()
        bundle["execution_boundary"] = "authorized_submission"
        bundle["project"].update({"mode": "publish_support", "target_stage": "AUTHORIZED_SUBMISSION"})
        bundle["publish_authorization"]["status"] = "AUTHORIZED"
        result = validate_listing_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertEqual(result["derived_gates"]["publication"], "BLOCKED")
        self.assertTrue(any("[LST-PUBLISH-002]" in item or "[LST-AUTH-012]" in item for item in result["errors"]), result["errors"])

    def test_migration_invalidates_legacy_authority_handoff_and_live(self):
        legacy = {
            "schema_version": "1.0",
            "project": {"project_id": "OLD", "title": "Old", "mode": "rebuild", "status": "PASS", "snapshot_date": "2026-08-27", "conclusion": "LIVE_PASS", "owner": "qa"},
            "scope": {"marketplace": "US", "locale": "en-US", "seller_scope": "S", "parent_asins": [PARENT], "intended_child_asins": [CHILD], "excluded_child_asins": [], "packs": [], "colors": [], "sizes": []},
            "catalog_context": {}, "sources": [], "rule_snapshots": [], "field_resolutions": [], "facts": [], "claims": [], "conflicts": [], "variant_topology": [],
            "decision_map": {"requirements": []}, "surface_assignments": [], "field_candidates": [],
            "enriched_content_handoff": {"status": "FROZEN", "requested_content_types": ["PREMIUM_A_PLUS"]},
            "publish_authorization": {"status": "AUTHORIZED"}, "baseline": [{}], "change_set": [{}], "rollback": [{}], "live_readback": [{}],
        }
        legacy.update({
            "canonical_assertions": [{"id": "OLD-ASSERTION"}],
            "decision_answer_units": [{"id": "OLD-ANSWER"}],
            "surface_assignments": [{"id": "OLD-ASSIGNMENT"}],
            "field_candidates": [{"id": "OLD-CANDIDATE"}],
            "semantic_consistency_matrix": [{"id": "OLD-MATRIX"}],
        })
        migrated, report = migrate_bundle(legacy)
        self.assertEqual(migrated["schema_version"], "1.1")
        self.assertEqual(migrated["execution_boundary"], "read_only")
        self.assertEqual(migrated["project"]["conclusion"], "NO_VALID_CONCLUSION")
        self.assertEqual(migrated["publish_authorization"]["status"], "NOT_AUTHORIZED")
        self.assertEqual(migrated["live_readback"], [])
        self.assertEqual(migrated["enriched_content_handoff"]["status"], "DRAFT")
        self.assertTrue(report["authorization_invalidated"])
        self.assertEqual(report["live_rows_discarded"], 1)
        for section in (
            "canonical_assertions", "decision_answer_units", "surface_assignments",
            "field_candidates", "semantic_consistency_matrix",
        ):
            self.assertEqual(migrated[section], [])
            self.assertEqual(report["preclosure_candidate_rows_discarded"][section], 1)

    def test_consumer_candidates_are_forbidden_before_one_bet_closes(self):
        bundle = valid_bundle()
        one_bet = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "ONE_BET")
        one_bet.update({"status": "IN_PROGRESS", "result": "", "record_refs": [], "closed_at": ""})
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-PHASE-001]" in item for item in result["errors"]), result["errors"])

    def test_canonical_assertion_alone_is_forbidden_before_one_bet_closes(self):
        bundle = valid_bundle()
        one_bet = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "ONE_BET")
        one_bet.update({"status": "IN_PROGRESS", "result": "", "record_refs": [], "closed_at": ""})
        for section in (
            "surface_assignments", "field_candidates", "decision_answer_units",
            "semantic_consistency_matrix",
        ):
            bundle[section] = []
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-PHASE-001]" in item for item in result["errors"]), result["errors"])

    def test_round_two_gate_cannot_pass_without_positioning_round(self):
        bundle = valid_bundle()
        bundle["discovery"]["interview_rounds"] = [
            row for row in bundle["discovery"]["interview_rounds"] if row["round_type"] != "POSITIONING"
        ]
        bundle["discovery"]["responses"] = [
            row for row in bundle["discovery"]["responses"] if row["id"] != "R-2"
        ]
        bundle["discovery"]["distillations"] = [
            row for row in bundle["discovery"]["distillations"] if row["id"] != "D-2"
        ]
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-036]" in item for item in result["errors"]), result["errors"])

    def test_rebuild_cannot_skip_required_stages_with_not_required(self):
        bundle = valid_bundle()
        round_two = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "ROUND_2")
        round_two.update({
            "status": "NOT_REQUIRED_WITH_REASON",
            "reason": "already frozen",
            "result": "claimed inherited strategy",
        })
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-041]" in item for item in result["errors"]), result["errors"])
        self.assertTrue(any("[L11-PHASE-001]" in item for item in result["errors"]), result["errors"])

    def test_stage_gate_rejects_ghost_record_refs(self):
        bundle = valid_bundle()
        intent = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "PRODUCT_INTENT_BRIEF")
        intent["record_refs"] = ["GHOST-NODE"]
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-040]" in item for item in result["errors"]), result["errors"])

    def test_one_bet_requires_marked_selection_question_response_and_distillation(self):
        bundle = valid_bundle()
        one_bet = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "ONE_BET")
        one_bet["record_refs"] = ["R-2", "D-2"]
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-046]" in item for item in result["errors"]), result["errors"])

    def test_product_intent_requires_typed_complete_payload(self):
        bundle = valid_bundle()
        intent_record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-3")
        intent_record["payload"].pop("current_choice")
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-045]" in item for item in result["errors"]), result["errors"])

    def test_product_intent_rejects_semantic_placeholders(self):
        bundle = valid_bundle()
        intent_record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-3")
        intent_record["payload"] = {key: "x" for key in intent_record["payload"]}
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-045]" in item for item in result["errors"]), result["errors"])

    def test_typed_strategy_records_require_nonempty_fact_chain(self):
        for record_id in ("D-3", "D-4"):
            with self.subTest(record_id=record_id):
                bundle = valid_bundle()
                record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == record_id)
                record["fact_ids"] = []
                result = validate_listing_bundle_v11(bundle)
                self.assertFalse(result["ok"])
                self.assertTrue(any("[L11-DISCOVERY-049]" in item for item in result["errors"]), result["errors"])

    def test_strategy_stage_requires_its_native_round_question_response_and_fact_chain(self):
        mutations = (
            ("PRODUCT_INTENT_BRIEF", "IR-2"),
            ("PRODUCT_INTENT_BRIEF", "Q-2"),
            ("PRODUCT_INTENT_BRIEF", "R-2"),
            ("PRODUCT_INTENT_BRIEF", "F-1"),
            ("ONE_BET", "IR-2"),
            ("ONE_BET", "Q-2"),
            ("ONE_BET", "R-2"),
            ("ONE_BET", "F-1"),
        )
        for stage, missing_ref in mutations:
            with self.subTest(stage=stage, missing_ref=missing_ref):
                bundle = valid_bundle()
                gate = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == stage)
                gate["record_refs"].remove(missing_ref)
                result = validate_listing_bundle_v11(bundle)
                self.assertFalse(result["ok"])
                self.assertTrue(any("[L11-DISCOVERY-049]" in item for item in result["errors"]), result["errors"])

    def test_strategy_stage_cannot_substitute_an_unrelated_valid_fact(self):
        for stage in ("PRODUCT_INTENT_BRIEF", "ONE_BET"):
            with self.subTest(stage=stage):
                bundle = valid_bundle()
                unrelated = copy.deepcopy(bundle["facts"][0])
                unrelated.update({
                    "id": "F-2",
                    "statement": "The current product is black.",
                    "allowed_expression": "Black color.",
                })
                bundle["facts"].append(unrelated)
                gate = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == stage)
                gate["record_refs"] = ["F-2" if item == "F-1" else item for item in gate["record_refs"]]
                result = validate_listing_bundle_v11(bundle)
                self.assertFalse(result["ok"])
                self.assertTrue(any("[L11-DISCOVERY-049]" in item for item in result["errors"]), result["errors"])

    def test_one_bet_requires_typed_route_rejection_and_reversible_test(self):
        bundle = valid_bundle()
        one_bet_record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-4")
        one_bet_record["payload"]["reversibility_test"] = ""
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-047]" in item for item in result["errors"]), result["errors"])

    def test_one_bet_rejects_ghost_route_and_unsupported_selected_proof(self):
        for mutation in ("ghost", "unsupported"):
            with self.subTest(mutation=mutation):
                bundle = valid_bundle()
                record = next(row for row in bundle["discovery"]["distillations"] if row["id"] == "D-4")
                if mutation == "ghost":
                    record["payload"]["selected_route_id"] = "GHOST-ROUTE"
                else:
                    record["payload"]["proof_status"] = "UNSUPPORTED"
                    record["payload"]["route_registry"][0]["proof_status"] = "UNSUPPORTED"
                result = validate_listing_bundle_v11(bundle)
                self.assertFalse(result["ok"])
                self.assertTrue(any("[L11-DISCOVERY-047]" in item for item in result["errors"]), result["errors"])

    def test_placeholder_strategic_answer_cannot_close_one_bet(self):
        bundle = valid_bundle()
        strategic_response = next(row for row in bundle["discovery"]["responses"] if row["id"] == "R-2")
        strategic_response["answer"] = "x"
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-048]" in item for item in result["errors"]), result["errors"])

    def test_placeholder_stage_result_cannot_fake_discovery_pass(self):
        bundle = valid_bundle()
        one_bet = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "ONE_BET")
        one_bet["result"] = "x"
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-048]" in item for item in result["errors"]), result["errors"])

    def test_recon_requires_target_page_census_source(self):
        bundle = valid_bundle()
        bundle["sources"] = [row for row in bundle["sources"] if row["id"] != "SRC-PDP"]
        bundle["discovery"]["evidence_pass"]["source_ids"].remove("SRC-PDP")
        recon = next(row for row in bundle["discovery"]["stage_gates"] if row["stage"] == "RECONNAISSANCE")
        recon["evidence_source_ids"].remove("SRC-PDP")
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-043]" in item for item in result["errors"]), result["errors"])

    def test_recon_rejects_fake_non_amazon_target_page_locator(self):
        bundle = valid_bundle()
        source = next(row for row in bundle["sources"] if row["id"] == "SRC-PDP")
        source["locator"] = "https://example.com/not-amazon"
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-043]" in item for item in result["errors"]), result["errors"])

    def test_rebuild_reconnaissance_cannot_pass_with_incomplete_market_research(self):
        bundle = valid_bundle()
        bundle["market_research"].update({
            "status": "IN_PROGRESS", "source_ids": [], "voc_observations": [],
            "competitor_observations": [], "conclusions": [],
        })
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-DISCOVERY-039]" in item for item in result["errors"]), result["errors"])

    def test_complete_market_research_requires_competitor_observation(self):
        bundle = valid_bundle()
        bundle["market_research"]["competitor_observations"] = []
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[L11-MARKET-009]" in item for item in result["errors"]), result["errors"])

    def test_negative_fixture_catalog_is_present(self):
        rows = json.loads((HERE / "fixtures_v11" / "negative_cases.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 8)
        self.assertEqual(len({row["name"] for row in rows}), len(rows))

    def test_v11_refactor_full_result_and_hash_goldens(self):
        cases = {
            "non_object": None,
            "valid": valid_bundle(),
            "handoff_frozen": delegated_handoff_bundle("FROZEN"),
        }
        evidence_stale = valid_bundle()
        evidence_stale["sources"][0]["status"] = "STALE"
        cases["evidence_stale"] = evidence_stale

        discovery_open = valid_bundle()
        discovery_open["discovery"]["responses"][0].update({
            "classification": "UNKNOWN_SKIP", "status": "SKIP", "answer": "",
        })
        cases["discovery_open"] = discovery_open

        decision_draft = valid_bundle()
        decision_draft["decision_map"]["status"] = "DRAFT"
        cases["decision_draft"] = decision_draft

        ptd_open = valid_bundle()
        ptd_open["ptd_field_inventory"]["expected_fields"][0].update({
            "requirement_status": "CONDITIONAL", "trigger_status": "TRIGGERED",
            "closure_status": "HOLD",
        })
        ptd_open["ptd_field_inventory"]["checksum"] = ""
        cases["ptd_open"] = ptd_open

        coverage_missing = valid_bundle()
        coverage_missing["field_candidates"] = []
        coverage_missing["decision_answer_units"] = []
        coverage_missing["semantic_consistency_matrix"] = []
        cases["coverage_missing"] = coverage_missing

        result_received = delegated_handoff_bundle("RESULT_RECEIVED")
        result_received["project"]["conclusion"] = "PASS"
        handoff = result_received["enriched_content_handoff"]
        handoff["checksum"] = canonical_handoff_hash(handoff)
        handoff["parent_bundle_sha256"] = canonical_parent_hash(result_received)
        cases["handoff_result_received"] = result_received

        publication_incomplete = valid_bundle()
        publication_incomplete["execution_boundary"] = "authorized_submission"
        publication_incomplete["project"].update({
            "mode": "publish_support", "target_stage": "AUTHORIZED_SUBMISSION",
        })
        publication_incomplete["publish_authorization"]["status"] = "AUTHORIZED"
        cases["publication_incomplete"] = publication_incomplete

        unicode_bidi = valid_bundle()
        unicode_bidi["project"]["title"] = "safe\u202ebidi"
        cases["unicode_bidi"] = unicode_bidi

        expected_result_digests = {
            "non_object": "2a8bfe4c0a4b67d414cfde0783b35767e18acaae6558f7f5a4e4a1e74bdec355",
            "valid": "280e77bcd5aa257ee35e64e236cc337cbd16a0f3057c9673a3ae0f3ba8e839c8",
            "evidence_stale": "8f0722d8fb0a4b64d75b69d1cecd50e25c3ae854a474768a5bccd34848fadb72",
            "discovery_open": "f3be1e8a2bf272c63a4eee69af6d60991c28e5daf4ca77f6f1466239a6750ea3",
            "decision_draft": "00a5fa1ccd97d134f3c9a4ce1c4b89f7adc578db9ecd8dcbd384285692a9bb65",
            "ptd_open": "474ceffd75ae95a6b77a246980927c4f69b74a49a121262b3ec28e54eafa6669",
            "coverage_missing": "d8d21756023615bb440e68d5c85cddac6b04c5024b4e987dde171707f6aa2f74",
            "handoff_frozen": "6cff311149add8cfbc2955611a92b5ad693c6c4ced4d7aa1a99f874ba25c23e0",
            "handoff_result_received": "03ecb1e46254c2021cedc1b6b4f5146177d04fb4e86c1e964b223a5be62f0edb",
            "publication_incomplete": "02006148df1bf6d6440b94e369a15c90a8de58bcbcf89b933b627a34ed666cb8",
            "unicode_bidi": "e35e4987def71caf9b34be02134bc1fba65a5dd62c81ebac632132b043cdeee5",
        }
        actual_results = {
            name: validate_listing_bundle_v11(bundle) for name, bundle in cases.items()
        }
        self.assertEqual(
            {name: result_digest(result) for name, result in actual_results.items()},
            expected_result_digests,
        )
        self.assertEqual(list(actual_results["valid"]), [
            "ok", "schema_valid", "errors", "warnings", "counts", "derived_gates",
            "derived_stage", "parent_bundle_sha256", "contract_status",
        ])
        self.assertEqual(list(actual_results["valid"]["counts"]), [
            "sources", "rule_snapshots", "field_resolutions", "facts", "claims",
            "variant_rows", "discovery_stage_gates", "decision_requirements", "field_candidates",
            "decision_answer_units", "p0_atoms", "p0_pass", "p0_delegated",
        ])
        self.assertEqual(list(actual_results["valid"]["derived_gates"]), [
            "identity", "rules", "evidence", "truth", "discovery", "decision",
            "market_research", "ptd", "surfaces", "candidates", "handoff", "package",
            "publication", "backend", "live",
        ])

        frozen = delegated_handoff_bundle("FROZEN")
        advanced = copy.deepcopy(frozen)
        advanced["project"].update({
            "status": "RESULT_RECEIVED", "target_stage": "LIVE_MATCH", "conclusion": "LIVE_PASS",
        })
        advanced["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
        advanced["gate_reviews"] = [{"id": "GR-1", "status": "PASS"}]
        advanced["experiment_registry"] = [{"id": "EXP-1", "status": "COMPLETE"}]
        advanced["publish_authorization"]["status"] = "AUTHORIZED"
        advanced["baseline"] = [{"id": "BL-LATER"}]
        advanced["change_set"] = [{"id": "CHG-LATER"}]
        advanced["rollback"] = [{"id": "RB-LATER"}]
        advanced["live_readback"] = [{"child_asin": CHILD, "status": "LIVE_MATCH"}]
        truth_changed = copy.deepcopy(frozen)
        truth_changed["facts"][0]["statement"] = "Two spatulas are included."
        self.assertEqual(canonical_sha256({"z": "雪", "a": [2, 1]}), "sha256:33d81fd6cd58739306cd13babeba6cb934e1ed0fbb2ac0b654af87ae20ec3755")
        self.assertEqual(canonical_handoff_snapshot_id(frozen["enriched_content_handoff"]), "HO-5995c285b4d62ed110a9")
        self.assertEqual(canonical_handoff_hash(frozen["enriched_content_handoff"]), "sha256:fcbfa7a1ca15b6e0db57be92fcd468e2d90c84825b3d5f095d68639a16c1eb92")
        self.assertEqual(canonical_parent_hash(frozen), "sha256:bc252a5a18a5f4e131a78e2f3233bde90516826eba84ebc366ceb19506c2ccc2")
        self.assertEqual(canonical_parent_hash(advanced), "sha256:bc252a5a18a5f4e131a78e2f3233bde90516826eba84ebc366ceb19506c2ccc2")
        self.assertEqual(canonical_parent_hash(truth_changed), "sha256:9dcff189dc46de0d29a1a96301ca2521d19eafb86354e922de06aec0c82a36b3")

        for name, bundle, expected_stdout_digest, expected_hash_line in (
            (
                "valid", valid_bundle(),
                "4cec657cc88aa94445ad22327aa9b5786ac9cd3f8b2d779be7e561ad264db03b",
                "sha256:a68d5d2dfbc09526648af2eb69d27132818e7caf82c22241219f35bf56fdad14\n",
            ),
            (
                "handoff_frozen", delegated_handoff_bundle("FROZEN"),
                "e15ae6a7389ae80d97633b3c26300af196f1ab144cff4a8220c1e22c3bcc2c02",
                "sha256:bc252a5a18a5f4e131a78e2f3233bde90516826eba84ebc366ceb19506c2ccc2\n",
            ),
        ):
            with self.subTest(cli=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "bundle.json"
                path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
                run = subprocess.run(
                    [sys.executable, str(HERE / "validate_listing_bundle.py"), str(path)],
                    capture_output=True, check=False,
                )
                self.assertEqual(run.returncode, 0, run.stderr.decode())
                self.assertEqual(run.stderr, b"")
                self.assertEqual(hashlib.sha256(run.stdout).hexdigest(), expected_stdout_digest)
                hash_run = subprocess.run(
                    [
                        sys.executable, str(HERE / "validate_listing_bundle.py"), str(path),
                        "--print-parent-hash",
                    ],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(hash_run.returncode, 0, hash_run.stderr)
                self.assertEqual(hash_run.stdout, expected_hash_line)

    def test_refactored_v11_domains_leave_input_unchanged_and_repeat_exactly(self):
        for bundle in (valid_bundle(), delegated_handoff_bundle("FROZEN")):
            before = copy.deepcopy(bundle)
            first = validate_listing_bundle_v11(bundle)
            second = validate_listing_bundle_v11(bundle)
            self.assertEqual(bundle, before)
            self.assertEqual(first, second)

    def test_version_dispatch_and_shared_publication_contract_have_no_import_cycle(self):
        legacy_source = (HERE / "validate_listing_bundle.py").read_text(encoding="utf-8")
        current_source = (HERE / "validate_listing_bundle_v11.py").read_text(encoding="utf-8")
        publication_source = (HERE / "listing_publication_contract.py").read_text(encoding="utf-8")
        self.assertIn("from validate_listing_bundle_v11 import validate_listing_bundle_v11", legacy_source)
        self.assertNotIn("from validate_listing_bundle import", current_source)
        self.assertNotIn("import validate_listing_bundle", current_source)
        self.assertNotIn("validate_listing_bundle_v11", publication_source)
        self.assertNotIn("validate_listing_bundle", publication_source)

    def test_domain_functions_are_deterministic_and_side_effect_free(self):
        bundle = valid_bundle()
        sources = {row["id"]: row for row in bundle["sources"]}
        self.assertEqual(evaluate_evidence(bundle["sources"], bundle["discovery"]["evidence_pass"]), "PASS")
        self.assertEqual(evaluate_discovery("PASS", 0, "PASS"), "PASS")
        expected = expected_requirement_atom_tuples(
            bundle["decision_map"]["requirements"], bundle["variant_topology"], "US", "en-US"
        )
        self.assertEqual(expected, {("DR-1", "US", "en-US", "V-1")})
        self.assertEqual(evaluate_ptd("COMPLETE", bundle["ptd_field_inventory"]["expected_fields"], True, False), "PASS")
        self.assertEqual(evaluate_handoff("FROZEN", False, ["PREMIUM_A_PLUS"]), ("PASS", True))
        self.assertEqual(evaluate_publication("read_only", "NOT_AUTHORIZED", set())["publication"], "NOT_RUN")
        self.assertEqual(derive_stage({"identity": "PASS", "rules": "BLOCKED"}), "IDENTITY_FROZEN")
        self.assertEqual(sources["SRC-PRODUCT"]["status"], "USABLE")


if __name__ == "__main__":
    unittest.main()
