#!/usr/bin/env python3

import copy
import importlib.util
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from validate_bundle import validate_bundle


CHILD = "B0EXAMPLE1"
PARENT = "B0PARENT01"


def app_scope(*, child=CHILD, parent=PARENT, color="White"):
    return {
        "marketplace": "US",
        "locale": "en-US",
        "parent_asin": parent or "",
        "child_asins": [child] if child else [],
        "packs": ["1"],
        "colors": [color],
        "sizes_or_capacities": ["N/A"],
        "other_variants": {"style": ["N/A"]},
    }


def source(source_id, source_type, path_or_url, *, source_scope=None, observed="2026-08-27T12:00:00+08:00"):
    return {
        "id": source_id,
        "source_type": source_type,
        "path_or_url": path_or_url,
        "scope": source_scope if source_scope is not None else app_scope(),
        "observed_at": observed,
        "time_window": "point_in_time",
        "timezone": "Asia/Kuala_Lumpur",
        "fetch_status": "ok",
        "block_reason": "",
        "can_establish": ["The scoped observation described by this source."],
        "cannot_establish": ["Unscoped claims."],
        "owner": "Evidence owner",
    }


def default_publish_objects():
    return {
        "publish_authorization": {
            "status": "NOT_AUTHORIZED", "authorization_id": "", "authorized_by": "",
            "authorized_at": "", "expires_at": "", "systems": [], "marketplaces": [],
            "locales": [], "content_ids": [], "child_asins": [], "allowed_actions": [],
            "prohibited_actions": [], "change_set_ids": [], "source_ids": [],
        },
        "baseline": {
            "id": "", "status": "NOT_FROZEN", "captured_at": "", "content_ids": [],
            "application_state_ref": "", "copy_snapshot_ref": "", "asset_snapshot_ref": "",
            "alt_snapshot_ref": "", "frontend_source_ids": [],
            "concurrent_edit_status": "UNKNOWN", "owner": "",
        },
        "change_set": [],
        "rollback": {
            "status": "NOT_READY", "baseline_id": "", "trigger_conditions": [],
            "method": "", "responsible_owner": "", "protected_p0_fact_ids": [],
            "verification_steps": [], "source_ids": [],
        },
        "live_readback": [],
    }


def valid_bundle():
    sources = [
        source(
            "SRC-ALT", "OFFICIAL_PLATFORM_RULE",
            "https://developer-docs.amazon.com/sp-api/docs/a-plus-content-examples",
            source_scope=app_scope(child=None, parent=None),
        ),
        source("SRC-SPEC", "DOCUMENTED_SPEC", "/evidence/spec.pdf"),
        source("SRC-TEST", "PHYSICAL_TEST", "/evidence/test.pdf"),
        source("SRC-BACKEND", "BACKEND_OBSERVED", "/evidence/backend-export.json"),
        source("SRC-PDP-BASE", "PUBLIC_OBSERVED", "https://www.amazon.com/dp/B0EXAMPLE1"),
        source("SRC-PDP-LIVE", "PUBLIC_OBSERVED", "https://www.amazon.com/dp/B0EXAMPLE1", observed="2026-08-27T14:00:00+08:00"),
        source("SRC-AUTH", "VERIFIED_ACCOUNT_DATA", "/evidence/write-authorization.json"),
    ]
    bundle = {
        "schema_version": "1.1",
        "project": {
            "title": "Example Premium A+ rebuild",
            "marketplace": "US",
            "locale": "en-US",
            "target_type": "live_asin",
            "focal_identity": {
                "identifier": CHILD,
                "identifier_type": "asin",
                "identity_status": "VERIFIED_CHILD",
                "verified_focal_child": CHILD,
                "provisional_parent": PARENT,
                "verification_source_ids": ["SRC-BACKEND", "SRC-PDP-BASE"],
            },
            "mode": "rebuild",
            "status": "ACTIVE",
            "snapshot_date": "2026-08-27",
            "write_scope": "read_only",
            "conclusion": "PASS",
            "conditional_draft": {
                "status": "CLEARED",
                "maximum_work": "full_production",
                "blocked_outputs": [],
                "blocker_ids": [],
            },
        },
        "scope": {
            "status": "FROZEN",
            "marketplaces": ["US"],
            "locales": ["en-US"],
            "parent_asins": [PARENT],
            "intended_child_asins": [CHILD],
            "packs": ["1"],
            "colors": ["White"],
            "sizes_or_capacities": ["N/A"],
            "other_dimensions": {"style": ["N/A"]},
            "source_ids": ["SRC-BACKEND"],
        },
        "platform_limits": {
            "alt_max_chars": 100,
            "basic_max_modules": 5,
            "premium_max_modules": 7,
            "available_module_types": ["PREMIUM_IMAGE_TEXT"],
            "content_type_eligibility": "PREMIUM",
            "last_verified_at": "2026-08-27T12:00:00+08:00",
            "source_id": "SRC-ALT",
            "source_ids": ["SRC-ALT"],
        },
        "sources": sources,
        "facts": [
            {
                "id": "FACT-1", "statement": "The selected child includes one device.",
                "scope": app_scope(), "evidence_type": "DOCUMENTED_SPEC",
                "evidence_strength": "E3", "source_ids": ["SRC-SPEC"],
                "proving_source_ids": ["SRC-SPEC"], "observed_at": "2026-08-27",
                "publish_status": "PUBLISHABLE", "owner": "Product",
            },
            {
                "id": "FACT-2", "statement": "The tested operating limit is 10 hours.",
                "scope": app_scope(), "evidence_type": "PHYSICAL_TEST",
                "evidence_strength": "E4", "source_ids": ["SRC-TEST"],
                "proving_source_ids": ["SRC-TEST"], "observed_at": "2026-08-27",
                "publish_status": "PUBLISHABLE", "owner": "Lab",
            },
        ],
        "claims": [
            {
                "id": "CLAIM-1", "text": "One device is included.", "scope": app_scope(),
                "risk_type": "ordinary", "fact_ids": ["FACT-1"],
                "publish_status": "PUBLISHABLE", "consumer_facing": True,
                "content_status": "FINAL_CANDIDATE", "owner": "Product",
            },
            {
                "id": "CLAIM-2", "text": "Up to 10 hours under stated test conditions.",
                "scope": app_scope(), "risk_type": "performance", "fact_ids": ["FACT-2"],
                "publish_status": "PUBLISHABLE", "consumer_facing": True,
                "content_status": "FINAL_CANDIDATE", "owner": "Compliance",
            },
        ],
        "decision_map": {
            "status": "SUPPORTED",
            "dimensions": [
                {"id": "core_user", "answer": "A buyer who needs the scoped device.", "status": "SUPPORTED", "fact_ids": ["FACT-1"], "source_ids": ["SRC-SPEC"]}
            ],
            "owner": "Strategy",
        },
        "competitor_insights": [],
        "positioning": {
            "status": "SUPPORTED", "core_audience": "Scoped buyers",
            "high_value_situation": "Before purchase", "job": "Choose the correct item",
            "category": "Device", "primary_benefit": "Clear contents",
            "mechanism_fact_ids": ["FACT-1"], "important_limit_claim_ids": ["CLAIM-2"],
            "statement": "A clearly scoped device with tested limits.", "owner": "Strategy",
        },
        "conflicts": [],
        "variants": [
            {
                "child_asin": CHILD, "parent_asin": PARENT, "marketplace": "US",
                "locale": "en-US", "pack": "1", "color": "White",
                "size_or_capacity": "N/A", "other_variant": "N/A",
                "aplus_content_id": "A+-001", "brand_story_id": "BS-001",
                "status": "VERIFIED", "source_ids": ["SRC-BACKEND"], "owner": "Operations",
            }
        ],
        "modules": [
            {
                "id": "M01", "decision_priority": "P0",
                "decision_question": "What is included and what is the tested limit?",
                "wrong_user_or_use": "Do not use outside the stated conditions.",
                "module_type": "PREMIUM_IMAGE_TEXT", "module_type_verified_at": "2026-08-27",
                "eligibility_source_ids": ["SRC-ALT", "SRC-BACKEND"],
                "content_status": "FINAL_CANDIDATE", "evidence_gate_status": "PASS",
                "application_scope": app_scope(), "native_headline": "Know What You Receive",
                "native_body": "One device is included. See the tested conditions.",
                "fact_ids": ["FACT-1", "FACT-2"], "claim_ids": ["CLAIM-1", "CLAIM-2"],
                "hold_claim_ids": [], "applied_child_asins": [CHILD],
                "image_brief": "Show the real device and included contents.",
                "visible_proof_fact_ids": ["FACT-1"], "on_image_text": "",
                "mobile_plan": "Keep product and native headline visible.",
                "prohibited_claims": ["No untested absolute performance"],
                "acceptance_tests": ["Contents match the selected child."],
                "owner": "Creative", "qa_status": "PASS", "experiment_eligible": True,
            }
        ],
        "assets": [
            {
                "id": "A01", "module_id": "M01", "asset_role": "contents proof",
                "content_status": "FINAL_CANDIDATE", "file": "device-contents.jpg",
                "sha256": "a" * 64,
                "alt": "White device beside its included cable on a table.",
                "application_scope": app_scope(), "applied_child_asins": [CHILD],
                "claim_ids": ["CLAIM-1"], "visible_facts": ["FACT-1"],
                "synthetic_person": "no", "generation_method": "real_photography",
                "product_reference_files": ["device-contents.jpg"],
                "must_show": ["Actual device", "Included cable"],
                "must_not_change": ["Quantity", "Color", "Included item"],
                "product_fidelity_owner": "Product",
                "product_fidelity_status": "PASS",
                "product_fidelity_evidence": ["Physical sample comparison"],
                "ai_rule_checked_at": "", "ai_rule_source_ids": [], "qa_status": "PASS",
            }
        ],
        "gates": [
            {"id": gate, "status": "PASS", "owner": "Independent QA",
             "evidence": [f"{gate}-evidence"], "failure_action": "Stop and correct."}
            for gate in ("G0", "G1", "G2", "G3", "G4")
        ],
        "experiments": [],
    }
    bundle.update(default_publish_objects())
    return bundle


def valid_publish_bundle():
    bundle = valid_bundle()
    bundle["project"].update({"mode": "publish_support", "write_scope": "explicit_write"})
    bundle["variants"][0]["status"] = "LIVE_PASS"
    bundle["gates"].append({
        "id": "G5", "status": "PASS", "owner": "Independent QA",
        "evidence": ["resolved-live-readback"], "failure_action": "Use safe rollback.",
    })
    bundle["publish_authorization"] = {
        "status": "AUTHORIZED", "authorization_id": "AUTH-001",
        "authorized_by": "Brand owner", "authorized_at": "2026-08-27T12:30:00+08:00",
        "expires_at": "2099-09-03T12:30:00+08:00", "systems": ["Seller Central"],
        "marketplaces": ["US"], "locales": ["en-US"],
        "content_ids": ["A+-001", "BS-001"], "child_asins": [CHILD],
        "allowed_actions": ["edit", "submit", "apply", "rollback"],
        "prohibited_actions": ["catalog_write", "price_change"],
        "change_set_ids": ["CHG-001"], "source_ids": ["SRC-AUTH"],
    }
    bundle["baseline"] = {
        "id": "BASE-001", "status": "FROZEN",
        "captured_at": "2026-08-27T12:15:00+08:00",
        "content_ids": ["A+-001", "BS-001"],
        "application_state_ref": "baseline/application.json",
        "copy_snapshot_ref": "baseline/copy.json", "asset_snapshot_ref": "baseline/assets.json",
        "alt_snapshot_ref": "baseline/alt.json", "frontend_source_ids": ["SRC-PDP-BASE"],
        "concurrent_edit_status": "FROZEN", "owner": "Operations",
    }
    bundle["change_set"] = [
        {
            "id": "CHG-001", "system": "Seller Central", "content_id": "A+-001",
            "marketplace": "US", "locale": "en-US", "child_asins": [CHILD],
            "field_or_module": "M01.native_headline",
            "before_value_ref": "baseline/copy.json#/M01/native_headline",
            "after_value_ref": "candidate/copy.json#/M01/native_headline",
            "fact_ids": ["FACT-1"], "claim_ids": ["CLAIM-1"], "asset_ids": ["A01"],
            "owner": "Operations", "approval_status": "APPROVED",
            "applied_at": "2026-08-27T13:00:00+08:00", "status": "VERIFIED",
        }
    ]
    bundle["rollback"] = {
        "status": "READY", "baseline_id": "BASE-001",
        "trigger_conditions": ["Wrong-child or factual P0 mismatch"],
        "method": "Restore the frozen content and application state.",
        "responsible_owner": "Operations", "protected_p0_fact_ids": ["FACT-1"],
        "verification_steps": ["Read every intended child after restoration."],
        "source_ids": ["SRC-BACKEND"],
    }
    bundle["live_readback"] = [
        {
            "id": "RB-001", "readback_phase": "FIRST_READBACK", "child_asin": CHILD,
            "marketplace": "US", "locale": "en-US", "expected_content_id": "A+-001",
            "observed_content_id": "A+-001", "checked_at": "2026-08-27T14:00:00+08:00",
            "device": "desktop browser", "viewport": "1440x900", "fetch_status": "ok",
            "field_checks": {key: "PASS" for key in (
                "identity", "quantity", "color", "size_or_capacity", "included_items",
                "copy", "assets", "alt", "module_order"
            )},
            "evidence_source_ids": ["SRC-PDP-LIVE"], "status": "PASS",
            "mismatch_action": "", "followup_required": False, "owner": "Independent QA",
        }
    ]
    return bundle


def errors(result):
    return "\n".join(result["errors"])


def find_source(bundle, source_id):
    return next(row for row in bundle["sources"] if row["id"] == source_id)


def upgrade_v12(bundle=None):
    bundle = copy.deepcopy(bundle if bundle is not None else valid_bundle())
    bundle["schema_version"] = "1.2"
    module = bundle["modules"][0]
    module_id = module["id"]
    capability_id = "CAP-1"
    carrier_id = "CARRIER-1"
    answer_id = "ANSWER-1"
    field_path = f"modules.{module_id}.native_body"
    bundle["workflow_context"] = {
        "mode": "standalone",
        "parent_bundle_ref": "",
        "accepted_handoff_snapshot_id": "",
        "accepted_at": "",
        "accepted_by": "",
        "execution_boundary": "authorized_submission" if bundle["project"]["write_scope"] == "explicit_write" else "read_only",
    }
    bundle["enriched_content_handoff"] = {
        "contract_version": "1.0",
        "snapshot_id": "",
        "parent_project_id": "",
        "parent_bundle_sha256": "",
        "status": "NOT_APPLICABLE",
        "maximum_output": "conditional_wireframe",
        "marketplace": "",
        "locale": "",
        "product_type": "",
        "application_scope": {"parent_asins": [], "child_asins": [], "packs": [], "colors": [], "sizes": []},
        "variant_row_ids": [],
        "fact_ids": [],
        "claim_ids": [],
        "blocked_claim_ids": [],
        "conflict_ids": [],
        "source_ids": [],
        "requested_content_types": [],
        "decision_requirements": [],
        "capability_snapshot_ids": [],
        "prohibited_actions": ["modify_parent_truth", "expand_application_scope", "online_submission"],
        "created_at": "",
        "owner": "",
        "checksum": "",
    }
    bundle["capability_snapshots"] = [{
        "id": capability_id,
        "marketplace": bundle["project"]["marketplace"],
        "locale": bundle["project"]["locale"],
        "account_scope": "fixture-account",
        "content_type": "PREMIUM_A_PLUS",
        "eligibility_status": "PREMIUM",
        "available_module_types": [module["module_type"]],
        "backend_field_paths": [field_path],
        "field_limits": {},
        "source_ids": ["SRC-ALT", "SRC-BACKEND"],
        "retrieved_at": "2026-08-27T12:00:00+08:00",
        "status": "CURRENT",
        "owner": "Operations",
        "checksum": "sha256:capability-fixture",
    }]
    bundle["decision_answer_units"] = [{
        "id": answer_id,
        "requirement_id": module_id,
        "priority": module["decision_priority"],
        "buyer_question": module["decision_question"],
        "primary_carrier_id": carrier_id,
        "module_id": module_id,
        "native_field_path": field_path,
        "text": "One device is included.",
        "application_scope": copy.deepcopy(module["application_scope"]),
        "fact_ids": copy.deepcopy(module["fact_ids"]),
        "claim_ids": copy.deepcopy(module["claim_ids"]),
        "early_disclosure_required": False,
        "content_status": "FINAL_CANDIDATE",
        "qa_status": "PASS",
        "owner": "Content QA",
    }]
    bundle["carriers"] = [{
        "id": carrier_id,
        "carrier_type": "native_text",
        "coverage_role": "PRIMARY_NATIVE_ANSWER",
        "module_id": module_id,
        "backend_field_path": field_path,
        "capability_snapshot_id": capability_id,
        "decision_requirement_ids": [module_id],
        "application_scope": copy.deepcopy(module["application_scope"]),
        "fact_ids": copy.deepcopy(module["fact_ids"]),
        "claim_ids": copy.deepcopy(module["claim_ids"]),
        "answer_unit_ids": [answer_id],
        "asset_ids": [],
        "mobile_behavior": "Native text remains readable on mobile.",
        "content_status": "FINAL_CANDIDATE",
        "qa_status": "PASS",
        "owner": "Content QA",
    }]
    bundle["coverage_summary"] = {
        "status": "PASS", "p0_required": 1, "p0_pass": 1,
        "gap_requirement_ids": [],
    }
    bundle["delta_evidence_requests"] = []
    return bundle


def embedded_v12_bundle():
    bundle = upgrade_v12()
    module = bundle["modules"][0]
    requirement_id = "REQ-PARENT-1"
    bundle["workflow_context"] = {
        "mode": "embedded",
        "parent_bundle_ref": "/evidence/parent-listing-bundle.json",
        "accepted_handoff_snapshot_id": "HANDOFF-1",
        "accepted_at": "2026-08-28T00:30:00+08:00",
        "accepted_by": "A+ owner",
        "execution_boundary": "read_only",
    }
    bundle["enriched_content_handoff"] = {
        "contract_version": "1.0",
        "snapshot_id": "HANDOFF-1",
        "parent_project_id": "PARENT-PROJECT-1",
        "parent_bundle_sha256": "sha256:" + "a" * 64,
        "status": "FROZEN",
        "maximum_output": "preflight_package",
        "marketplace": "US",
        "locale": "en-US",
        "product_type": "DEVICE",
        "application_scope": {
            "parent_asins": [PARENT], "child_asins": [CHILD], "packs": ["1"],
            "colors": ["White"], "sizes": ["N/A"],
        },
        "variant_row_ids": ["V-PARENT-1"],
        "fact_ids": [row["id"] for row in bundle["facts"]],
        "claim_ids": [row["id"] for row in bundle["claims"]],
        "blocked_claim_ids": [],
        "conflict_ids": [],
        "source_ids": ["SRC-SPEC", "SRC-TEST", "SRC-BACKEND"],
        "requested_content_types": ["PREMIUM_A_PLUS"],
        "decision_requirements": [{
            "id": requirement_id,
            "buyer_question": module["decision_question"],
            "priority": module["decision_priority"],
            "application_scope": {
                "parent_asins": [PARENT], "child_asins": [CHILD], "packs": ["1"],
                "colors": ["White"], "sizes": ["N/A"],
            },
            "fact_ids": copy.deepcopy(module["fact_ids"]),
            "claim_ids": copy.deepcopy(module["claim_ids"]),
            "native_answer_required": True,
            "early_disclosure_required": False,
            "upstream_primary_carrier_ref": "",
            "assigned_surface": "enriched_content",
            "status": "READY",
        }],
        "capability_snapshot_ids": ["CAP-1"],
        "prohibited_actions": ["modify_parent_truth", "expand_application_scope", "online_submission"],
        "created_at": "2026-08-28T00:00:00+08:00",
        "owner": "Parent Listing owner",
        "checksum": "sha256:handoff-fixture",
    }
    bundle["decision_answer_units"][0]["requirement_id"] = requirement_id
    bundle["carriers"][0]["decision_requirement_ids"] = [requirement_id]
    return bundle


def load_local_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load test dependency: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def matching_parent_bundle(aplus_bundle):
    parent_scripts = Path(__file__).resolve().parents[2] / "listing" / "scripts"
    parent_tests = load_local_module("listing_parent_fixture_for_aplus", parent_scripts / "test_validate_listing_bundle.py")
    parent_validator = load_local_module("listing_parent_validator_for_aplus", parent_scripts / "validate_listing_bundle.py")
    try:
        parent = parent_tests.frozen_handoff_parent()
    finally:
        parent_tests.TEST_TEMP_DIR.cleanup()
    replacements = {
        "PARENT-1": PARENT,
        "CHILD-1": CHILD,
        "1PK": "1",
        "Black": "White",
        "M": "N/A",
        "DR-1": "REQ-PARENT-1",
        "F-1": "FACT-1",
        "C-1": "CLAIM-1",
        "SRC-1": "SRC-SPEC",
        "V-1": "V-PARENT-1",
        "KITCHEN_TOOL": "DEVICE",
        "LISTING-PROJECT-1": "PARENT-PROJECT-1",
    }

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace(child) for child in value]
        return replacements.get(value, value)

    parent = replace(parent)
    parent_scope = {
        "parent_asins": [PARENT], "child_asins": [CHILD], "packs": ["1"],
        "colors": ["White"], "sizes": ["N/A"],
    }
    parent["sources"] = [
        {
            "id": source_id, "type": "authorized_backend", "locator": source_id.casefold(),
            "authority": "primary", "retrieved_at": "2026-08-28T00:00:00Z", "status": "USABLE",
        }
        for source_id in ("SRC-SPEC", "SRC-TEST", "SRC-BACKEND")
    ]
    parent["catalog_context"]["source_ids"] = ["SRC-BACKEND"]
    parent["rule_snapshots"][0]["source_ids"] = ["SRC-BACKEND"]
    parent["facts"] = [
        {
            "id": row["id"], "statement": row["statement"],
            "source_ids": [row["proving_source_ids"][0]],
            "application_scope": copy.deepcopy(parent_scope),
            "verification_status": "VERIFIED", "content_status": "PUBLISHABLE",
            "owner": row["owner"],
        }
        for row in aplus_bundle["facts"]
    ]
    parent["claims"] = [
        {
            "id": row["id"], "text": row["text"], "fact_ids": copy.deepcopy(row["fact_ids"]),
            "source_ids": [next(
                fact["proving_source_ids"][0] for fact in aplus_bundle["facts"]
                if fact["id"] in row["fact_ids"]
            )],
            "application_scope": copy.deepcopy(parent_scope),
            "support_status": "SUPPORTED", "content_status": "PUBLISHABLE",
            "owner": row["owner"],
        }
        for row in aplus_bundle["claims"]
    ]
    fact_ids = [row["id"] for row in parent["facts"]]
    claim_ids = [row["id"] for row in parent["claims"]]
    parent["variant_topology"][0].update({"fact_ids": fact_ids, "source_ids": ["SRC-BACKEND"]})
    parent_requirement = parent["decision_map"]["requirements"][0]
    parent_requirement.update({
        "buyer_question": aplus_bundle["modules"][0]["decision_question"],
        "fact_ids": fact_ids, "claim_ids": claim_ids,
        "assigned_surface": "enriched_content", "early_disclosure_required": False,
    })
    parent["surface_assignments"][0].update({
        "requirement_id": "REQ-PARENT-1", "primary_surface": "enriched_content",
        "primary_carrier_kind": "A_PLUS_NATIVE_PENDING", "field_resolution_id": "",
        "status": "PASS",
    })
    parent["field_candidates"][0].update({"fact_ids": fact_ids, "claim_ids": claim_ids})

    handoff = copy.deepcopy(aplus_bundle["enriched_content_handoff"])
    handoff.update({
        "fact_ids": fact_ids, "claim_ids": claim_ids,
        "source_ids": ["SRC-SPEC", "SRC-TEST", "SRC-BACKEND"],
    })
    handoff["decision_requirements"][0].update({
        "fact_ids": fact_ids, "claim_ids": claim_ids,
        "upstream_primary_carrier_ref": "",
    })
    parent["enriched_content_handoff"] = handoff
    handoff["checksum"] = parent_validator.canonical_handoff_hash(handoff)
    handoff["parent_bundle_sha256"] = parent_validator.canonical_parent_hash(parent)
    aplus_bundle["enriched_content_handoff"] = copy.deepcopy(handoff)
    aplus_bundle["workflow_context"]["accepted_handoff_snapshot_id"] = handoff["snapshot_id"]
    return parent


@contextmanager
def verified_embedded_bundle():
    bundle = embedded_v12_bundle()
    parent = matching_parent_bundle(bundle)
    with tempfile.TemporaryDirectory() as temp_dir:
        parent_path = Path(temp_dir) / "listing-parent.json"
        parent_path.write_text(json.dumps(parent, ensure_ascii=False), encoding="utf-8")
        child_path = Path(temp_dir) / "aplus-child.json"
        bundle["workflow_context"]["parent_bundle_ref"] = str(parent_path)
        yield bundle, parent, parent_path, child_path


class BundleValidatorTests(unittest.TestCase):
    def test_actual_v11_template_is_valid_scaffold(self):
        template_path = Path(__file__).resolve().parents[1] / "assets" / "aplus-project-bundle-template.json"
        result = validate_bundle(json.loads(template_path.read_text(encoding="utf-8")))
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["template_only"])
        self.assertEqual(result["result_level"], "TEMPLATE_ONLY")

    def test_valid_populated_rebuild_passes(self):
        result = validate_bundle(valid_bundle())
        self.assertTrue(result["ok"], result)

    def test_valid_publish_support_passes(self):
        result = validate_bundle(valid_publish_bundle())
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result_level"], "LEGACY_LOCAL_CONTRACT")

    def test_schema_version_is_closed(self):
        bundle = valid_bundle(); bundle["schema_version"] = "1.0"
        self.assertIn("must use '1.1'", errors(validate_bundle(bundle)))

    def test_strict_dates_reject_prefix_junk_bad_day_and_naive_time(self):
        for value in ("2026-08-27junk", "2026-02-30", "2026-08-27T10:00:00"):
            with self.subTest(value=value):
                bundle = valid_bundle(); bundle["project"]["snapshot_date"] = value
                self.assertIn("snapshot_date", errors(validate_bundle(bundle)))

    def test_live_pass_requires_verified_focal_child(self):
        bundle = valid_bundle()
        bundle["project"]["focal_identity"].update({"identity_status": "UNVERIFIED", "verified_focal_child": "", "verification_source_ids": []})
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("PASS requires", errors(result))

    def test_non_asin_conditional_rebuild_without_variants_passes(self):
        bundle = valid_bundle()
        bundle["project"].update({"target_type": "prelaunch_sku", "conclusion": "CONDITIONAL_PASS"})
        bundle["project"]["focal_identity"] = {
            "identifier": "SKU-NEW-001", "identifier_type": "sku", "identity_status": "UNVERIFIED",
            "verified_focal_child": "", "provisional_parent": "", "verification_source_ids": [],
        }
        bundle["project"]["conditional_draft"] = {
            "status": "ACTIVE", "maximum_work": "audit_gap_report_and_conditional_wireframe",
            "blocked_outputs": ["consumer_final_copy", "final_product_imagery", "publishing"],
            "blocker_ids": ["BLOCK-IDENTITY"],
        }
        bundle["scope"].update({"status": "PARTIAL", "parent_asins": [], "intended_child_asins": []})
        bundle["variants"] = []
        for row in bundle["sources"]:
            row["scope"]["parent_asin"] = ""; row["scope"]["child_asins"] = []
        for row in bundle["facts"] + bundle["claims"]:
            row["scope"]["parent_asin"] = ""; row["scope"]["child_asins"] = []
        module = bundle["modules"][0]
        module["application_scope"]["parent_asin"] = ""; module["application_scope"]["child_asins"] = []
        module.update({"content_status": "CONDITIONAL_DRAFT", "evidence_gate_status": "HOLD", "qa_status": "HOLD", "applied_child_asins": []})
        asset = bundle["assets"][0]
        asset["application_scope"]["parent_asin"] = ""; asset["application_scope"]["child_asins"] = []
        asset.update({"content_status": "CONDITIONAL_DRAFT", "qa_status": "HOLD", "applied_child_asins": []})
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], result)

    def test_unresolved_rebuild_cannot_masquerade_as_final(self):
        bundle = valid_bundle(); bundle["variants"] = []
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("unresolved rebuild", errors(result))

    def test_source_type_enum_is_closed(self):
        bundle = valid_bundle(); find_source(bundle, "SRC-SPEC")["source_type"] = "competitor_blog"
        self.assertIn("unsupported value", errors(validate_bundle(bundle)))

    def test_risk_type_enum_is_closed(self):
        bundle = valid_bundle(); bundle["claims"][1]["risk_type"] = "environment claim"
        self.assertIn("unsupported value", errors(validate_bundle(bundle)))

    def test_asset_qa_enum_is_closed(self):
        bundle = valid_bundle(); bundle["assets"][0]["qa_status"] = "probably"
        self.assertIn("unsupported value", errors(validate_bundle(bundle)))

    def test_publishable_fact_requires_proving_source(self):
        bundle = valid_bundle(); bundle["facts"][0]["proving_source_ids"] = []
        self.assertIn("publishable fact requires", errors(validate_bundle(bundle)))

    def test_blocked_source_cannot_prove_fact(self):
        bundle = valid_bundle(); find_source(bundle, "SRC-SPEC").update({"fetch_status": "blocked", "block_reason": "CAPTCHA"})
        self.assertIn("is not usable", errors(validate_bundle(bundle)))

    def test_proving_source_type_must_match_fact(self):
        bundle = valid_bundle(); find_source(bundle, "SRC-SPEC")["source_type"] = "COMPETITOR_ONLY"
        self.assertIn("does not match evidence_type", errors(validate_bundle(bundle)))

    def test_proving_source_scope_must_contain_fact(self):
        bundle = valid_bundle(); find_source(bundle, "SRC-SPEC")["scope"]["colors"] = ["Black"]
        self.assertIn("proving source", errors(validate_bundle(bundle)))

    def test_consumer_false_claim_cannot_enter_module_or_asset(self):
        bundle = valid_bundle(); bundle["claims"][0]["consumer_facing"] = False
        self.assertIn("consumer_facing=true", errors(validate_bundle(bundle)))

    def test_cross_child_claim_application_is_blocked(self):
        bundle = valid_bundle()
        second = copy.deepcopy(bundle["variants"][0]); second.update({"child_asin": "B0EXAMPLE2", "color": "Black"})
        bundle["variants"].append(second)
        bundle["scope"]["intended_child_asins"].append("B0EXAMPLE2"); bundle["scope"]["colors"].append("Black")
        module = bundle["modules"][0]
        module["application_scope"] = app_scope(child="B0EXAMPLE2", color="Black"); module["applied_child_asins"] = ["B0EXAMPLE2"]
        asset = bundle["assets"][0]
        asset["application_scope"] = app_scope(child="B0EXAMPLE2", color="Black"); asset["applied_child_asins"] = ["B0EXAMPLE2"]
        self.assertIn("claim", errors(validate_bundle(bundle)))

    def test_unknown_visible_fact_is_blocked(self):
        bundle = valid_bundle(); bundle["assets"][0]["visible_facts"] = ["FACT-NOT-REAL"]
        self.assertIn("unknown fact id", errors(validate_bundle(bundle)))

    def test_pass_gate_requires_evidence(self):
        bundle = valid_bundle(); bundle["gates"][0]["evidence"] = []
        self.assertIn("PASS gate requires", errors(validate_bundle(bundle)))

    def test_platform_limit_requires_official_amazon_source(self):
        bundle = valid_bundle(); find_source(bundle, "SRC-ALT")["path_or_url"] = "https://sellercentral.amazon.com.evil.example/help"
        self.assertIn("not an official Amazon", errors(validate_bundle(bundle)))

    def test_platform_limit_source_must_be_readable_and_official_type(self):
        for mutation in ({"fetch_status": "blocked", "block_reason": "CAPTCHA"}, {"source_type": "VOC_ONLY"}):
            with self.subTest(mutation=mutation):
                bundle = valid_bundle(); find_source(bundle, "SRC-ALT").update(mutation)
                self.assertIn("platform_limits.source_ids", errors(validate_bundle(bundle)))

    def test_final_ai_asset_requires_references_fidelity_and_rule_evidence(self):
        bundle = valid_bundle()
        bundle["assets"][0].update({
            "synthetic_person": "yes", "generation_method": "ai_generated_person_or_setting",
            "product_reference_files": [], "product_fidelity_owner": "",
            "product_fidelity_status": "HOLD", "product_fidelity_evidence": [],
            "ai_rule_checked_at": "", "ai_rule_source_ids": [],
        })
        text = errors(validate_bundle(bundle))
        self.assertIn("AI/composite asset", text)
        self.assertIn("final product-depicting asset", text)

    def test_final_asset_cannot_keep_unknown_generation(self):
        bundle = valid_bundle(); bundle["assets"][0].update({"synthetic_person": "unknown", "generation_method": "unknown"})
        self.assertIn("cannot retain unknown", errors(validate_bundle(bundle)))

    def test_valid_single_variable_experiment_passes_with_g6(self):
        bundle = valid_bundle()
        bundle["experiments"] = [{
            "id": "EXP-1", "experiment_type": "single_variable",
            "hypothesis": "A clearer headline improves conversion.",
            "version_difference": "Only the headline changes.", "treatment_components": ["native_headline"],
            "primary_metric": "conversion", "guardrails": ["returns"],
            "run_rule": "Use the current valid MYE conclusion rule.", "stop_rule": "Do not stop early.",
            "eligibility_status": "ELIGIBLE", "eligibility_source_ids": ["SRC-BACKEND"],
            "attribution_boundary": "ELEMENT_LEVEL", "status": "READY", "owner": "Experiment owner",
            "result_source_ids": [], "conclusion": "NO_VALID_CONCLUSION",
        }]
        bundle["gates"].append({"id": "G6", "status": "PASS", "owner": "Experiment QA", "evidence": ["preregistration"], "failure_action": "Keep stable version."})
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], result)

    def test_multi_attribute_experiment_cannot_claim_element_causality(self):
        bundle = valid_bundle()
        bundle["experiments"] = [{
            "id": "EXP-1", "experiment_type": "multi_attribute_package", "hypothesis": "Package wins.",
            "version_difference": "Headline and image change.", "treatment_components": ["headline", "image"],
            "primary_metric": "sales", "guardrails": ["returns"], "run_rule": "Run validly.",
            "stop_rule": "No early stop.", "eligibility_status": "INELIGIBLE", "eligibility_source_ids": [],
            "attribution_boundary": "ELEMENT_LEVEL", "status": "RUNNING", "owner": "Owner",
            "result_source_ids": [], "conclusion": "PASS",
        }]
        text = errors(validate_bundle(bundle))
        self.assertIn("PACKAGE_LEVEL", text)
        self.assertIn("active MYE requires", text)
        self.assertIn("experiments require G6", text)

    def test_publish_support_requires_authorization_envelope(self):
        bundle = valid_bundle(); bundle["project"].update({"mode": "publish_support", "write_scope": "explicit_write"})
        bundle["gates"].append({"id": "G5", "status": "PASS", "owner": "QA", "evidence": ["placeholder"], "failure_action": "Rollback."})
        text = errors(validate_bundle(bundle))
        self.assertIn("publish_authorization", text)
        self.assertIn("baseline", text)

    def test_publish_authorization_targets_are_exact(self):
        bundle = valid_publish_bundle(); bundle["publish_authorization"]["child_asins"].append("B0EXAMPLE2")
        self.assertIn("must exactly match intended", errors(validate_bundle(bundle)))

    def test_publish_change_set_must_be_approved_and_authorized(self):
        bundle = valid_publish_bundle(); bundle["change_set"][0].update({"approval_status": "NOT_APPROVED", "content_id": "A+-OTHER"})
        text = errors(validate_bundle(bundle))
        self.assertIn("outside authorization", text)
        self.assertIn("requires APPROVED", text)

    def test_publish_rollback_must_link_frozen_baseline_and_p0_facts(self):
        bundle = valid_publish_bundle(); bundle["rollback"].update({"baseline_id": "WRONG", "protected_p0_fact_ids": []})
        text = errors(validate_bundle(bundle))
        self.assertIn("must reference frozen baseline", text)
        self.assertIn("at least one value required", text)

    def test_fetch_blocked_readback_cannot_pass_or_imply_absence(self):
        bundle = valid_publish_bundle()
        rb = bundle["live_readback"][0]
        rb.update({"fetch_status": "blocked", "observed_content_id": "", "status": "PASS", "followup_required": False})
        rb["field_checks"] = {key: "FETCH_BLOCKED" for key in rb["field_checks"]}
        text = errors(validate_bundle(bundle))
        self.assertIn("PASS requires readable evidence", text)
        self.assertIn("requires follow-up", text)

    def test_competitor_copying_prohibition_is_structural(self):
        bundle = valid_bundle()
        bundle["competitor_insights"] = [{
            "id": "COMP-1", "competitor_role": "direct", "marketplace": "US", "locale": "en-US",
            "child_asin": "B0COMPETE1", "observed_at": "2026-08-27", "fetch_status": "ok",
            "source_ids": ["SRC-PDP-BASE"], "category_parity": [],
            "target_verified_difference_fact_ids": ["FACT-1"], "decision_gaps": [],
            "claim_risks": [], "borrowable_structural_patterns": [],
            "copying_prohibited": False, "status": "FROZEN",
        }]
        self.assertIn("copying_prohibited: must be true", errors(validate_bundle(bundle)))

    def test_public_page_alone_cannot_prove_consumer_product_claim(self):
        bundle = valid_bundle()
        bundle["facts"][0]["evidence_type"] = "PUBLIC_OBSERVED"
        find_source(bundle, "SRC-SPEC")["source_type"] = "PUBLIC_OBSERVED"
        self.assertIn("unsupported consumer evidence", errors(validate_bundle(bundle)))

    def test_duplicate_and_oversize_alt_fail(self):
        bundle = valid_bundle(); bundle["assets"][0]["alt"] = "x" * 101
        duplicate = copy.deepcopy(bundle["assets"][0]); duplicate["id"] = "A02"; bundle["assets"].append(duplicate)
        text = errors(validate_bundle(bundle))
        self.assertIn("exceeds verified limit", text)
        self.assertIn("duplicates asset", text)

    def test_v12_valid_standalone_passes(self):
        result = validate_bundle(upgrade_v12())
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["native_coverage_assessed"])
        self.assertEqual(result["counts"]["p0_pass"], 1)
        self.assertIsNone(result["parent_bundle_verified"])
        self.assertEqual(result["result_level"], "LEGACY_LOCAL_CONTRACT")

    def test_v11_remains_compatible_without_native_coverage_claim(self):
        result = validate_bundle(valid_bundle())
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["native_coverage_assessed"])
        self.assertEqual(result["result_level"], "LEGACY_LOCAL_CONTRACT")
        self.assertTrue(any("compatibility mode" in warning for warning in result["warnings"]))

    def test_v11_cannot_carry_v12_blocks(self):
        bundle = valid_bundle()
        bundle["workflow_context"] = {"mode": "standalone"}
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("schema 1.1 cannot carry", errors(result))

    def test_v12_requires_all_contract_blocks(self):
        bundle = upgrade_v12()
        del bundle["carriers"]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("missing top-level keys", errors(result))

    def test_v12_valid_embedded_handoff_passes(self):
        with verified_embedded_bundle() as (bundle, _parent, _parent_path, child_path):
            result = validate_bundle(bundle, source_path=child_path)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["counts"]["p0_pass"], 1)
            self.assertTrue(result["parent_bundle_verified"])
            self.assertEqual(result["result_level"], "LEGACY_LOCAL_CONTRACT")

    def test_v12_embedded_scope_expansion_fails(self):
        bundle = embedded_v12_bundle()
        bundle["carriers"][0]["application_scope"]["child_asins"] = [CHILD, "B0EXAMPLE2"]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("frozen handoff", errors(result))

    def test_v12_static_visual_or_alt_cannot_satisfy_p0(self):
        bundle = upgrade_v12()
        bundle["carriers"][0].update({
            "carrier_type": "static_visual", "coverage_role": "PROOF_ONLY",
            "asset_ids": ["A01"],
        })
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-COVERAGE-005]", errors(result))

    def test_v12_short_complete_copy_passes_without_500_word_rule(self):
        bundle = upgrade_v12()
        bundle["decision_answer_units"][0]["text"] = "One device is included."
        bundle["modules"][0]["native_body"] = "One device is included."
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result_level"], "LEGACY_LOCAL_CONTRACT")

    def test_v12_long_copy_missing_p0_fails(self):
        bundle = upgrade_v12()
        bundle["modules"][0]["native_body"] = "Lifestyle story. " * 600
        bundle["decision_answer_units"] = []
        bundle["carriers"][0]["answer_unit_ids"] = []
        bundle["coverage_summary"] = {
            "status": "GAP", "p0_required": 1, "p0_pass": 0,
            "gap_requirement_ids": ["M01"],
        }
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-COVERAGE-006]", errors(result))

    def test_v12_rejects_fixed_500_threshold(self):
        bundle = upgrade_v12()
        bundle["coverage_summary"]["native_text_min_chars"] = 500
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-METRIC-001]", errors(result))

    def test_v12_community_qa_cannot_masquerade_as_brand_carrier(self):
        bundle = upgrade_v12()
        bundle["carriers"][0]["carrier_type"] = "community_customer_qa"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-QA-002]", errors(result))

    def test_v12_open_conflict_blocks_pass(self):
        bundle = upgrade_v12()
        bundle["conflicts"] = [{
            "id": "CONFLICT-1", "statements": ["A", "B"],
            "source_ids": ["SRC-SPEC"], "affected_fact_ids": ["FACT-1"],
            "affected_claim_ids": ["CLAIM-1"], "affected_module_ids": ["M01"],
            "affected_asset_ids": [], "affected_child_asins": [CHILD],
            "impact": "P0 answer may be wrong.", "decisive_evidence": "Authoritative specification.",
            "owner": "Evidence owner", "due_date": "2026-09-01",
            "maximum_work": "conditional_copy", "status": "OPEN",
        }]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-CONFLICT-001]", errors(result))

    def test_v12_open_delta_request_blocks_pass(self):
        bundle = upgrade_v12()
        bundle["delta_evidence_requests"] = [{
            "id": "DELTA-1", "question": "Verify the included quantity.",
            "affected_requirement_ids": ["M01"], "affected_fact_ids": ["FACT-1"],
            "affected_claim_ids": ["CLAIM-1"], "affected_module_ids": ["M01"],
            "decisive_evidence": "Current pack manifest.", "owner": "Product",
            "status": "OPEN",
        }]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-DELTA-002]", errors(result))

    def test_v12_noncomplete_experiment_cannot_claim_pass(self):
        bundle = upgrade_v12()
        bundle["experiments"] = [{
            "id": "EXP-V12", "experiment_type": "single_variable",
            "hypothesis": "Headline may help.", "version_difference": "Headline only.",
            "treatment_components": ["headline"], "primary_metric": "conversion",
            "guardrails": ["returns"], "run_rule": "Use valid MYE rules.",
            "stop_rule": "No early stop.", "eligibility_status": "UNVERIFIED",
            "eligibility_source_ids": [], "attribution_boundary": "ELEMENT_LEVEL",
            "status": "NOT_STARTED", "owner": "Experiment owner",
            "result_source_ids": [], "conclusion": "PASS",
        }]
        bundle["gates"].append({"id": "G6", "status": "PASS", "owner": "QA", "evidence": ["plan"], "failure_action": "Stop."})
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-EXPERIMENT-001]", errors(result))

    def test_v12_pass_cannot_have_empty_modules(self):
        bundle = upgrade_v12()
        bundle["modules"] = []
        bundle["assets"] = []
        bundle["decision_answer_units"] = []
        bundle["carriers"] = []
        bundle["coverage_summary"] = {
            "status": "PASS", "p0_required": 0, "p0_pass": 0,
            "gap_requirement_ids": [],
        }
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-COVERAGE-007]", errors(result))

    def test_v12_publish_support_needs_only_actual_content_type_id(self):
        bundle = upgrade_v12(valid_publish_bundle())
        bundle["variants"][0]["brand_story_id"] = ""
        bundle["publish_authorization"]["content_ids"] = ["A+-001"]
        bundle["baseline"]["content_ids"] = ["A+-001"]
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result_level"], "LEGACY_LOCAL_CONTRACT")

    def test_v12_native_answer_must_exist_in_resolved_field(self):
        bundle = upgrade_v12()
        bundle["modules"][0]["native_body"] = "A long lifestyle story with no included-item answer. " * 50
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-ANSWER-016]", errors(result))
        self.assertEqual(result["result_level"], "INVALID")

    def test_v12_answer_refs_must_chain_through_carrier_and_module(self):
        cases = []

        answer_outside_carrier = upgrade_v12()
        answer_outside_carrier["carriers"][0]["fact_ids"] = ["FACT-1"]
        cases.append((answer_outside_carrier, "[A12-ANSWER-019]"))

        carrier_outside_module = upgrade_v12()
        carrier_outside_module["modules"][0]["fact_ids"] = ["FACT-1"]
        cases.append((carrier_outside_module, "[A12-CARRIER-016]"))

        answer_without_refs = upgrade_v12()
        answer_without_refs["decision_answer_units"][0].update({"fact_ids": [], "claim_ids": []})
        cases.append((answer_without_refs, "[A12-ANSWER-018]"))

        field_mismatch = upgrade_v12()
        field_mismatch["decision_answer_units"][0]["native_field_path"] = "modules.M01.native_headline"
        cases.append((field_mismatch, "[A12-ANSWER-021]"))

        requirement_link_missing = upgrade_v12()
        requirement_link_missing["carriers"][0]["decision_requirement_ids"] = []
        cases.append((requirement_link_missing, "[A12-ANSWER-020]"))

        for bundle, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn(expected_code, errors(result))

        embedded = embedded_v12_bundle()
        embedded["enriched_content_handoff"]["decision_requirements"][0]["fact_ids"] = ["FACT-1"]
        result = validate_bundle(embedded)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-ANSWER-017]", errors(result))

    def test_v12_embedded_pass_requires_verified_local_parent(self):
        result = validate_bundle(embedded_v12_bundle())
        self.assertFalse(result["ok"])
        self.assertFalse(result["parent_bundle_verified"])
        self.assertIn("[A12-PARENT-001]", errors(result))
        self.assertEqual(result["result_level"], "INVALID")

    def test_v12_malformed_parent_reference_fails_closed_even_when_conditional(self):
        bundle = embedded_v12_bundle()
        bundle["project"]["conclusion"] = "CONDITIONAL_PASS"
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["parent_bundle_verified"])
        self.assertEqual(result["result_level"], "INVALID")
        self.assertEqual(result["project_conclusion"], "CONDITIONAL_PASS")
        self.assertIn("[A12-PARENT-001]", errors(result))

    def test_v12_parent_hash_or_handoff_mismatch_blocks_pass(self):
        with verified_embedded_bundle() as (bundle, _parent, _parent_path, child_path):
            bundle["enriched_content_handoff"]["parent_bundle_sha256"] = "sha256:" + "0" * 64
            result = validate_bundle(bundle, source_path=child_path)
            self.assertFalse(result["ok"])
            self.assertIn("[A12-PARENT-001]", errors(result))

    def test_v12_embedded_child_cannot_mutate_parent_truth(self):
        mutations = (
            lambda bundle: bundle["facts"][0].update({"statement": "Two devices are included."}),
            lambda bundle: bundle["claims"][0].update({"text": "Two devices are included."}),
            lambda bundle: bundle["claims"][0].update({"fact_ids": ["FACT-2"]}),
            lambda bundle: bundle["facts"][0].update({"proving_source_ids": ["SRC-TEST"]}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with verified_embedded_bundle() as (bundle, _parent, _parent_path, child_path):
                    mutation(bundle)
                    result = validate_bundle(bundle, source_path=child_path)
                    self.assertFalse(result["ok"])
                    self.assertIn("[A12-PARENT-001]", errors(result))
                    self.assertFalse(result["parent_bundle_verified"])

    def test_v12_parent_validator_does_not_hide_unrelated_p0_gap(self):
        with verified_embedded_bundle() as (bundle, parent, parent_path, child_path):
            extra_requirement = copy.deepcopy(parent["decision_map"]["requirements"][0])
            extra_requirement.update({
                "id": "REQ-UNRELATED-P0", "buyer_question": "What is the unrelated limit?",
                "assigned_surface": "media", "fact_ids": ["FACT-1"], "claim_ids": ["CLAIM-1"],
            })
            parent["decision_map"]["requirements"].append(extra_requirement)
            parent_validator_path = Path(__file__).resolve().parents[2] / "listing" / "scripts" / "validate_listing_bundle.py"
            parent_validator = load_local_module("listing_parent_validator_unrelated_gap", parent_validator_path)
            parent["enriched_content_handoff"]["parent_bundle_sha256"] = parent_validator.canonical_parent_hash(parent)
            bundle["enriched_content_handoff"] = copy.deepcopy(parent["enriched_content_handoff"])
            parent_path.write_text(json.dumps(parent, ensure_ascii=False), encoding="utf-8")
            result = validate_bundle(bundle, source_path=child_path)
            self.assertFalse(result["ok"])
            self.assertIn("[A12-PARENT-001]", errors(result))

    def test_v12_maximum_output_and_read_only_block_publish_support(self):
        limited = embedded_v12_bundle()
        limited["project"]["mode"] = "preflight_qa"
        limited["enriched_content_handoff"]["maximum_output"] = "candidate_package"
        result = validate_bundle(limited)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-HANDOFF-021]", errors(result))

        published = embedded_v12_bundle()
        published["modules"][0]["content_status"] = "PUBLISHED"
        result = validate_bundle(published)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-HANDOFF-025]", errors(result))

        read_only_publish = upgrade_v12(valid_publish_bundle())
        read_only_publish["workflow_context"]["execution_boundary"] = "read_only"
        result = validate_bundle(read_only_publish)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-AUTH-002]", errors(result))

    def test_publish_authorization_expiry_system_source_and_scope_are_enforced(self):
        mutations = (
            (lambda bundle: bundle["publish_authorization"].update({"expires_at": "2000-01-01T00:00:00Z"}), "[A-AUTH-001]"),
            (lambda bundle: bundle["publish_authorization"].update({"systems": ["Lingxing"]}), "[A-AUTH-003]"),
            (lambda bundle: bundle["publish_authorization"].update({"source_ids": ["SRC-SPEC"]}), "inapplicable type"),
            (lambda bundle: find_source(bundle, "SRC-AUTH")["scope"].update({"child_asins": ["B0EXAMPLE2"]}), "authorization source"),
            (lambda bundle: bundle["change_set"][0].update({"system": "Lingxing"}), "[A-AUTH-005]"),
        )
        for mutation, expected in mutations:
            with self.subTest(expected=expected):
                bundle = valid_publish_bundle()
                mutation(bundle)
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn(expected, errors(result))

    def test_local_stale_or_cross_child_public_observed_cannot_prove_live_readback(self):
        mutations = (
            lambda bundle: find_source(bundle, "SRC-PDP-LIVE").update({"path_or_url": "/evidence/live-readback.png"}),
            lambda bundle: find_source(bundle, "SRC-PDP-LIVE").update({"path_or_url": "https://www.amazon.com/dp/B0EXAMPLE2"}),
            lambda bundle: bundle["live_readback"][0].update({"evidence_source_ids": ["SRC-PDP-BASE"]}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bundle = valid_publish_bundle()
                mutation(bundle)
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("[A-READBACK-001]", errors(result))

    def test_polluted_scaffold_is_rejected(self):
        template_path = Path(__file__).resolve().parents[1] / "assets" / "aplus-project-bundle-template.json"
        template = json.loads(template_path.read_text(encoding="utf-8"))
        mutations = (
            lambda bundle: bundle["project"].update({"title": "Polluted fixture"}),
            lambda bundle: bundle["scope"].update({"status": "FROZEN"}),
            lambda bundle: bundle["gates"][0].update({"status": "PASS"}),
            lambda bundle: bundle["record_templates"].update({"polluted": True}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bundle = copy.deepcopy(template)
                mutation(bundle)
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("[A12-SCAFFOLD-001]", errors(result))
                self.assertEqual(result["result_level"], "INVALID")

    def test_v11_open_conflict_blocks_pass(self):
        bundle = valid_bundle()
        bundle["conflicts"] = [{
            "id": "CONFLICT-1", "statements": ["A", "B"],
            "source_ids": ["SRC-SPEC"], "affected_fact_ids": ["FACT-1"],
            "affected_claim_ids": ["CLAIM-1"], "affected_module_ids": ["M01"],
            "affected_asset_ids": [], "affected_child_asins": [CHILD],
            "impact": "P0 answer may be wrong.", "decisive_evidence": "Authoritative specification.",
            "owner": "Evidence owner", "due_date": "2026-09-01",
            "maximum_work": "conditional_copy", "status": "OPEN",
        }]
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A11-CONFLICT-001]", errors(result))

    def test_v11_community_qa_module_is_rejected(self):
        for label in ("community_qa", "customer Q&A", "Customer Questions", "community-answer"):
            with self.subTest(label=label):
                bundle = valid_bundle()
                bundle["modules"][0]["module_type"] = label
                bundle["platform_limits"]["available_module_types"].append(label)
                result = validate_bundle(bundle)
                self.assertFalse(result["ok"])
                self.assertIn("[A-QA-003]", errors(result))

    def test_v11_rejects_unknown_top_level_and_forbidden_metrics(self):
        unknown = valid_bundle()
        unknown["record_templates"] = {}
        result = validate_bundle(unknown)
        self.assertFalse(result["ok"])
        self.assertIn("unknown top-level keys", errors(result))

        fixed_metric = valid_bundle()
        fixed_metric["modules"][0]["cosmo_score"] = 99
        result = validate_bundle(fixed_metric)
        self.assertFalse(result["ok"])
        self.assertIn("[A11-METRIC-001]", errors(result))

    def test_v11_validation_does_not_mutate_input(self):
        bundle = valid_bundle()
        before = copy.deepcopy(bundle)
        result = validate_bundle(bundle)
        self.assertTrue(result["ok"], result)
        self.assertEqual(bundle, before)

    def test_v12_long_copy_cannot_fake_coverage_when_p0_is_image_or_alt_only(self):
        bundle = upgrade_v12()
        bundle["modules"][0]["native_body"] = "Lifestyle story. " * 600
        bundle["decision_answer_units"] = []
        bundle["carriers"][0].update({
            "carrier_type": "static_visual", "coverage_role": "PROOF_ONLY",
            "answer_unit_ids": [], "asset_ids": ["A01"],
        })
        bundle["coverage_summary"] = {
            "status": "PASS", "p0_required": 1, "p0_pass": 1,
            "gap_requirement_ids": [],
        }
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertIn("[A12-COVERAGE-002]", errors(result))
        self.assertIn("[A12-COVERAGE-005]", errors(result))


if __name__ == "__main__":
    unittest.main()
