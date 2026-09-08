#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from validate_listing_bundle import (  # noqa: E402
    canonical_child_readback_value,
    canonical_handoff_hash,
    canonical_parent_hash,
    canonical_row_hash,
    canonical_rows_hash,
    validate_listing_bundle,
)


CHILD = "B0EXAMPLE1"
PARENT = "B0PARENT01"

LEGACY_APLUS_FIXTURE = HERE / "fixtures_legacy" / "embedded_aplus_v12.json"
TEST_TEMP_DIR = tempfile.TemporaryDirectory(prefix="listing-validator-tests-")


def app_scope(children=None, packs=None, colors=None, sizes=None, parents=None):
    return {
        "parent_asins": list([PARENT] if parents is None else parents),
        "child_asins": list([CHILD] if children is None else children),
        "packs": list(["1PK"] if packs is None else packs),
        "colors": list(["Black"] if colors is None else colors),
        "sizes": list(["M"] if sizes is None else sizes),
    }


def valid_bundle():
    scope = app_scope()
    return {
        "schema_version": "1.0",
        "project": {
            "project_id": "LISTING-PROJECT-1",
            "title": "Fixture",
            "mode": "rebuild",
            "status": "READY_FOR_REVIEW",
            "snapshot_date": "2026-08-28",
            "conclusion": "PASS",
            "owner": "qa",
            "notes": "local candidate only",
        },
        "execution_boundary": "read_only",
        "scope": {
            "marketplace": "US",
            "locale": "en-US",
            "seller_scope": "SELLER-1",
            "parent_asins": [PARENT],
            "intended_child_asins": [CHILD],
            "excluded_child_asins": [],
            "packs": ["1PK"],
            "colors": ["Black"],
            "sizes": ["M"],
        },
        "catalog_context": {
            "identity_status": "FROZEN",
            "identifier": CHILD,
            "identifier_type": "ASIN",
            "parentage_level": "child",
            "product_type": "KITCHEN_TOOL",
            "schema_status": "READY",
            "data_plane_status": "READY",
            "source_ids": ["SRC-1"],
            "owner": "qa",
        },
        "rule_snapshots": [{
            "id": "RS-1",
            "marketplace": "US",
            "locale": "en-US",
            "seller_scope": "SELLER-1",
            "product_type": "KITCHEN_TOOL",
            "parentage_level": "child",
            "data_plane": "seller_listing",
            "schema_version": "ptd-fixture",
            "requirements": "LISTING",
            "requirements_enforced": "ENFORCED",
            "source_ids": ["SRC-1"],
            "retrieved_at": "2026-08-28T00:00:00Z",
            "status": "CURRENT",
            "checksum": "sha256:rules",
            "refresh_trigger": "before_authorized_submission",
        }],
        "field_resolutions": [{
            "id": "FR-1",
            "semantic_role": "bullet",
            "canonical_key": "bullet_point",
            "ui_label": "Bullet point",
            "data_plane": "seller_listing",
            "surface": "core_copy",
            "exists": True,
            "editable": True,
            "applicable": True,
            "requirement_status": "OPTIONAL",
            "visibility": "BUYER_VISIBLE",
            "rule_snapshot_ids": ["RS-1"],
            "application_scope": copy.deepcopy(scope),
            "status": "RESOLVED",
            "owner": "qa",
        }],
        "sources": [{
            "id": "SRC-1",
            "type": "authorized_backend",
            "locator": "seller-central-fixture",
            "authority": "primary",
            "retrieved_at": "2026-08-28T00:00:00Z",
            "status": "USABLE",
        }],
        "facts": [{
            "id": "F-1",
            "statement": "One black spatula is included.",
            "source_ids": ["SRC-1"],
            "application_scope": copy.deepcopy(scope),
            "verification_status": "VERIFIED",
            "content_status": "PUBLISHABLE",
            "owner": "qa",
        }],
        "claims": [{
            "id": "C-1",
            "text": "Includes one black spatula.",
            "fact_ids": ["F-1"],
            "source_ids": ["SRC-1"],
            "application_scope": copy.deepcopy(scope),
            "support_status": "SUPPORTED",
            "content_status": "PUBLISHABLE",
            "owner": "qa",
        }],
        "conflicts": [],
        "variant_topology": [{
            "id": "V-1",
            "parent_asin": PARENT,
            "child_asin": CHILD,
            "seller_sku": "SKU-1",
            "variation_theme": "ColorSize",
            "pack": "1PK",
            "color": "Black",
            "size": "M",
            "included_items": ["spatula"],
            "fact_ids": ["F-1"],
            "source_ids": ["SRC-1"],
            "status": "VERIFIED",
        }],
        "decision_map": {
            "status": "READY",
            "requirements": [{
                "id": "DR-1",
                "buyer_question": "What is included?",
                "priority": "P0",
                "application_scope": copy.deepcopy(scope),
                "fact_ids": ["F-1"],
                "claim_ids": ["C-1"],
                "early_disclosure_required": True,
                "assigned_surface": "core_copy",
                "status": "READY",
                "owner": "qa",
            }],
        },
        "surface_assignments": [{
            "id": "SA-1",
            "requirement_id": "DR-1",
            "primary_surface": "core_copy",
            "primary_carrier_kind": "NATIVE_VISIBLE",
            "field_resolution_id": "FR-1",
            "supporting_surfaces": ["media", "enriched_content"],
            "application_scope": copy.deepcopy(scope),
            "status": "PASS",
            "owner": "qa",
        }],
        "field_candidates": [{
            "id": "FC-1",
            "field_resolution_id": "FR-1",
            "semantic_role": "bullet",
            "value": "Includes one black spatula.",
            "application_scope": copy.deepcopy(scope),
            "fact_ids": ["F-1"],
            "claim_ids": ["C-1"],
            "content_status": "FINAL",
            "qa_status": "PASS",
            "owner": "qa",
        }],
        "enriched_content_handoff": {
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
        },
        "publish_authorization": {
            "status": "NOT_AUTHORIZED",
            "authorization_id": "",
            "authorizer": "",
            "authorized_account": "",
            "system": "",
            "data_planes": [],
            "marketplace": "",
            "locale": "",
            "target_ids": [],
            "change_set_ids": [],
            "baseline_sha256": "",
            "change_set_sha256": "",
            "authorized_action": "",
            "attempt_limit": 0,
            "authorized_at": "",
            "expires_at": "",
            "rollback_scope": [],
            "notes": "",
        },
        "baseline": [],
        "change_set": [],
        "rollback": [],
        "live_readback": [],
        "gates": {
            "identity": "PASS",
            "schema_ptd": "PASS",
            "data_plane": "PASS",
            "truth_variants": "PASS",
            "p0_coverage": "PASS",
            "candidate_qa": "PASS",
            "publication": "NOT_RUN",
            "live_readback": "NOT_RUN",
        },
        "record_templates": {},
    }


def set_path(document, path, value):
    parts = path.split(".")
    cursor = document
    for part in parts[:-1]:
        cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
    last = parts[-1]
    if isinstance(cursor, list):
        cursor[int(last)] = value
    else:
        cursor[last] = value


def frozen_handoff_parent():
    bundle = valid_bundle()
    bundle["decision_map"]["requirements"][0].update({
        "early_disclosure_required": False,
        "assigned_surface": "enriched_content",
    })
    bundle["surface_assignments"][0].update({
        "primary_surface": "enriched_content",
        "primary_carrier_kind": "A_PLUS_NATIVE_PENDING",
        "field_resolution_id": "",
        "status": "PASS",
    })
    bundle["enriched_content_handoff"] = {
        "contract_version": "1.0",
        "snapshot_id": "HANDOFF-1",
        "parent_project_id": "LISTING-PROJECT-1",
        "parent_bundle_sha256": "",
        "status": "FROZEN",
        "maximum_output": "preflight_package",
        "marketplace": "US",
        "locale": "en-US",
        "product_type": "KITCHEN_TOOL",
        "application_scope": app_scope(),
        "variant_row_ids": ["V-1"],
        "fact_ids": ["F-1"],
        "claim_ids": ["C-1"],
        "blocked_claim_ids": [],
        "conflict_ids": [],
        "source_ids": ["SRC-1"],
        "requested_content_types": ["PREMIUM_A_PLUS"],
        "decision_requirements": [{
            "id": "DR-1",
            "buyer_question": "What is included?",
            "priority": "P0",
            "application_scope": app_scope(),
            "fact_ids": ["F-1"],
            "claim_ids": ["C-1"],
            "native_answer_required": True,
            "early_disclosure_required": False,
            "upstream_primary_carrier_ref": "",
            "assigned_surface": "enriched_content",
            "status": "READY",
        }],
        "capability_snapshot_ids": ["CAP-1"],
        "prohibited_actions": ["modify_parent_truth", "expand_application_scope", "online_submission"],
        "created_at": "2026-08-28T00:00:00Z",
        "owner": "qa",
        "checksum": "",
    }
    bundle["enriched_content_handoff"]["checksum"] = canonical_handoff_hash(bundle["enriched_content_handoff"])
    bundle["enriched_content_handoff"]["parent_bundle_sha256"] = canonical_parent_hash(bundle)
    return bundle


def minimal_aplus_result(parent):
    # Static historical fixture: Parent tests must never import or execute the
    # sibling A+ validator/test module.  Current cross-bundle work belongs to
    # validate_listing_package.py; this fixture only preserves v1.0 regression
    # coverage as a LEGACY_LOCAL_CONTRACT.
    result = json.loads(LEGACY_APLUS_FIXTURE.read_text(encoding="utf-8"))
    app = {
        "marketplace": "US", "locale": "en-US", "parent_asin": PARENT,
        "child_asins": [CHILD], "packs": ["1PK"], "colors": ["Black"],
        "sizes_or_capacities": ["M"], "other_variants": {"style": ["N/A"]},
    }
    result["scope"].update({
        "parent_asins": [PARENT], "intended_child_asins": [CHILD],
        "packs": ["1PK"], "colors": ["Black"], "sizes_or_capacities": ["M"],
    })
    result["variants"][0].update({
        "child_asin": CHILD, "parent_asin": PARENT, "pack": "1PK",
        "color": "Black", "size_or_capacity": "M",
    })
    result["project"]["focal_identity"].update({
        "identifier": CHILD, "verified_focal_child": CHILD, "provisional_parent": PARENT,
    })
    parent_source = copy.deepcopy(result["sources"][1])
    parent_source.update({
        "id": "SRC-1", "source_type": "DOCUMENTED_SPEC",
        "path_or_url": "/evidence/parent-source.json", "scope": copy.deepcopy(app),
    })
    result["sources"].append(parent_source)
    fact = copy.deepcopy(result["facts"][0])
    fact.update({
        "id": "F-1", "statement": parent["facts"][0]["statement"],
        "scope": copy.deepcopy(app), "evidence_type": "DOCUMENTED_SPEC",
        "evidence_strength": "E3", "source_ids": ["SRC-1"],
        "proving_source_ids": ["SRC-1"],
    })
    claim = copy.deepcopy(result["claims"][0])
    claim.update({
        "id": "C-1", "text": parent["claims"][0]["text"],
        "scope": copy.deepcopy(app), "fact_ids": ["F-1"], "risk_type": "ordinary",
    })
    result["facts"] = [fact]
    result["claims"] = [claim]
    result["decision_map"]["dimensions"][0]["fact_ids"] = ["F-1"]
    result["positioning"]["mechanism_fact_ids"] = ["F-1"]
    result["positioning"]["important_limit_claim_ids"] = ["C-1"]
    module = result["modules"][0]
    module.update({
        "decision_priority": "P0", "decision_question": "What is included?",
        "application_scope": copy.deepcopy(app), "fact_ids": ["F-1"],
        "claim_ids": ["C-1"], "visible_proof_fact_ids": ["F-1"],
        "applied_child_asins": [CHILD],
        "native_body": parent["claims"][0]["text"],
    })
    asset = result["assets"][0]
    asset.update({
        "application_scope": copy.deepcopy(app), "applied_child_asins": [CHILD],
        "claim_ids": ["C-1"], "visible_facts": ["F-1"],
    })
    carrier = result["carriers"][0]
    carrier.update({
        "decision_requirement_ids": ["DR-1"], "application_scope": copy.deepcopy(app),
        "fact_ids": ["F-1"], "claim_ids": ["C-1"],
    })
    answer = result["decision_answer_units"][0]
    answer.update({
        "requirement_id": "DR-1", "priority": "P0", "buyer_question": "What is included?",
        "text": parent["claims"][0]["text"], "application_scope": copy.deepcopy(app),
        "fact_ids": ["F-1"], "claim_ids": ["C-1"],
    })
    result["enriched_content_handoff"] = copy.deepcopy(parent["enriched_content_handoff"])
    parent_path = Path(TEST_TEMP_DIR.name) / "parent-listing-bundle.json"
    parent_path.write_text(json.dumps(parent, ensure_ascii=False), encoding="utf-8")
    result["workflow_context"].update({
        "parent_bundle_ref": str(parent_path),
        "accepted_handoff_snapshot_id": parent["enriched_content_handoff"]["snapshot_id"],
        "accepted_at": "2026-08-28T00:30:00+08:00", "accepted_by": "A+ owner",
        "execution_boundary": "read_only",
    })
    result["coverage_summary"] = {
        "status": "PASS", "p0_required": 1, "p0_pass": 1, "gap_requirement_ids": [],
    }
    return result


def valid_authorized_bundle():
    bundle = valid_bundle()
    now = datetime.now(timezone.utc)
    captured = (now - timedelta(minutes=15)).isoformat()
    approved = (now - timedelta(minutes=10)).isoformat()
    authorized = (now - timedelta(minutes=5)).isoformat()
    expires = (now + timedelta(days=30)).isoformat()
    bundle["project"]["mode"] = "publish_support"
    bundle["execution_boundary"] = "authorized_submission"
    baseline = {
        "id": "BASE-1", "target_id": CHILD, "field_resolution_id": "FR-1",
        "data_plane": "seller_listing", "system": "Seller Central",
        "before_value": "Old bullet", "captured_at": captured,
        "source_ids": ["SRC-1"], "row_sha256": "",
    }
    baseline["row_sha256"] = canonical_row_hash(baseline)
    change = {
        "id": "CHG-1", "target_id": CHILD, "field_resolution_id": "FR-1",
        "data_plane": "seller_listing", "system": "Seller Central",
        "after_value": bundle["field_candidates"][0]["value"],
        "fact_ids": ["F-1"], "claim_ids": ["C-1"],
        "approval_status": "APPROVED", "approved_by": "Brand owner",
        "approved_at": approved, "row_sha256": "",
    }
    change["row_sha256"] = canonical_row_hash(change)
    rollback = {
        "id": "ROLLBACK-1", "change_set_id": "CHG-1", "baseline_id": "BASE-1",
        "target_id": CHILD, "field_resolution_id": "FR-1",
        "data_plane": "seller_listing", "system": "Seller Central",
        "rollback_value": "Old bullet", "trigger_conditions": ["Any live mismatch"],
        "owner": "Operations", "row_sha256": "",
    }
    rollback["row_sha256"] = canonical_row_hash(rollback)
    bundle["baseline"] = [baseline]
    bundle["change_set"] = [change]
    bundle["rollback"] = [rollback]
    bundle["publish_authorization"] = {
        "status": "AUTHORIZED", "authorization_id": "AUTH-1",
        "authorizer": "Brand owner", "authorized_account": "SELLER-1",
        "system": "Seller Central", "data_planes": ["seller_listing"],
        "marketplace": "US", "locale": "en-US", "target_ids": [CHILD],
        "change_set_ids": ["CHG-1"], "baseline_sha256": canonical_rows_hash([baseline]),
        "change_set_sha256": canonical_rows_hash([change]), "authorized_action": "submit",
        "attempt_limit": 1, "authorized_at": authorized, "expires_at": expires,
        "rollback_scope": [CHILD], "notes": "one-shot test authorization",
    }
    bundle["gates"]["publication"] = "PASS"
    return bundle


def valid_live_bundle():
    bundle = valid_authorized_bundle()
    observed_at = datetime.now(timezone.utc).isoformat()
    bundle["sources"].append({
        "id": "SRC-LIVE", "type": "public_frontend",
        "locator": f"https://www.amazon.com/dp/{CHILD}", "authority": "primary",
        "retrieved_at": observed_at, "status": "USABLE",
    })
    expected = bundle["field_candidates"][0]["value"]
    bundle["live_readback"] = [{
        "child_asin": CHILD, "status": "LIVE_MATCH", "live_pass": True,
        "observed_at": observed_at, "locator": f"https://www.amazon.com/dp/{CHILD}",
        "expected_value": expected, "observed_value": expected, "evidence_ref": "SRC-LIVE",
    }]
    bundle["project"]["conclusion"] = "LIVE_PASS"
    bundle["gates"]["live_readback"] = "PASS"
    return bundle


def reseal_handoff(bundle):
    handoff = bundle["enriched_content_handoff"]
    handoff["checksum"] = canonical_handoff_hash(handoff)
    handoff["parent_bundle_sha256"] = canonical_parent_hash(bundle)


def corrected_hx02_bundle():
    bundle = valid_bundle()
    children = ["HX02-2PK", "HX02-3PK"]
    bundle["scope"].update({"intended_child_asins": children, "packs": ["2PK", "3PK"]})
    field_scope = app_scope(children=children, packs=["2PK", "3PK"])
    three_pack_scope = app_scope(children=["HX02-3PK"], packs=["3PK"])
    bundle["field_resolutions"][0]["application_scope"] = copy.deepcopy(field_scope)
    bundle["facts"][0]["application_scope"] = copy.deepcopy(three_pack_scope)
    bundle["claims"][0]["application_scope"] = copy.deepcopy(three_pack_scope)
    bundle["decision_map"]["requirements"][0]["application_scope"] = copy.deepcopy(three_pack_scope)
    bundle["surface_assignments"][0]["application_scope"] = copy.deepcopy(three_pack_scope)
    bundle["field_candidates"][0]["application_scope"] = copy.deepcopy(three_pack_scope)
    base = bundle["variant_topology"][0]
    bundle["variant_topology"] = [
        {**base, "id": "V-2", "child_asin": "HX02-2PK", "seller_sku": "SKU-2", "pack": "2PK", "fact_ids": []},
        {**base, "id": "V-3", "child_asin": "HX02-3PK", "seller_sku": "SKU-3", "pack": "3PK"},
    ]
    return bundle


def corrected_pet_camera_bundle():
    bundle = valid_bundle()
    children = ["CAM-24", "CAM-DUAL"]
    bundle["scope"]["intended_child_asins"] = children
    bundle["catalog_context"]["product_type"] = "PET_CAMERA"
    bundle["rule_snapshots"][0].update({
        "product_type": "PET_CAMERA", "schema_version": "ptd-PET_CAMERA-2026-08-28",
        "checksum": "sha256:pet-camera-rule-snapshot",
    })
    bundle["field_resolutions"][0]["application_scope"] = app_scope(children=children)
    dual_scope = app_scope(children=["CAM-DUAL"])
    bundle["facts"][0].update({"statement": "5 GHz setup is supported.", "application_scope": copy.deepcopy(dual_scope)})
    bundle["claims"][0].update({"text": "Works with 5 GHz Wi-Fi.", "application_scope": copy.deepcopy(dual_scope)})
    bundle["decision_map"]["requirements"][0]["application_scope"] = copy.deepcopy(dual_scope)
    bundle["surface_assignments"][0]["application_scope"] = copy.deepcopy(dual_scope)
    bundle["field_candidates"][0].update({
        "value": "Works with 5 GHz Wi-Fi.", "application_scope": copy.deepcopy(dual_scope),
    })
    base = bundle["variant_topology"][0]
    bundle["variant_topology"] = [
        {**base, "id": "V-24", "child_asin": "CAM-24", "seller_sku": "SKU-24", "fact_ids": []},
        {**base, "id": "V-DUAL", "child_asin": "CAM-DUAL", "seller_sku": "SKU-DUAL"},
    ]
    return bundle


class ListingBundleValidatorTests(unittest.TestCase):
    def test_valid_local_candidate(self):
        result = validate_listing_bundle(valid_bundle())
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["counts"]["p0_pass"], 1)
        self.assertEqual(result["contract_status"], "LEGACY_LOCAL_CONTRACT")
        self.assertFalse(result["publication_authorized"])

    def test_valid_authorized_submission_and_complete_live_readback(self):
        authorized = validate_listing_bundle(valid_authorized_bundle())
        self.assertTrue(authorized["ok"], authorized["errors"])
        live = validate_listing_bundle(valid_live_bundle())
        self.assertTrue(live["ok"], live["errors"])
        self.assertEqual(live["result_level"], "LEGACY_LOCAL_CONTRACT")
        self.assertFalse(live["publication_authorized"])
        self.assertFalse(live["live_conclusion_recognized"])

    def test_pristine_legacy_scaffold_uses_bundled_legacy_canonical(self):
        path = HERE.parent / "assets" / "listing-project-bundle-template-v1.0.json"
        result = validate_listing_bundle(json.loads(path.read_text(encoding="utf-8")))
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["contract_status"], "LEGACY_LOCAL_CONTRACT")

    def test_authorization_boundary_bindings_are_fail_closed(self):
        now = datetime.now(timezone.utc)
        cases = (
            ("authorized_account", "WRONG-SELLER", "LST-AUTH-017"),
            ("marketplace", "CA", "LST-AUTH-018"),
            ("target_ids", ["B0WRONG001"], "LST-AUTH-019"),
            ("change_set_ids", ["CHG-WRONG"], "LST-AUTH-020"),
            ("data_planes", ["relationship"], "LST-AUTH-021"),
            ("system", "Unbound System", "LST-AUTH-022"),
            ("baseline_sha256", "sha256:wrong", "LST-AUTH-023"),
            ("change_set_sha256", "sha256:wrong", "LST-AUTH-024"),
            ("authorized_action", "rollback", "LST-AUTH-025"),
            ("expires_at", (now - timedelta(minutes=1)).isoformat(), "LST-AUTH-028"),
        )
        for key, value, code in cases:
            with self.subTest(key=key):
                bundle = valid_authorized_bundle()
                if key == "expires_at":
                    bundle["publish_authorization"]["authorized_at"] = (now - timedelta(minutes=2)).isoformat()
                bundle["publish_authorization"][key] = value
                result = validate_listing_bundle(bundle)
                self.assertTrue(any(f"[{code}]" in error for error in result["errors"]), result["errors"])

    def test_authorized_submission_cannot_expand_mode_conclusion_or_gate(self):
        cases = (
            ("mode", "audit", "LST-AUTH-032"),
            ("conclusion", "CONDITIONAL_PASS", "LST-AUTH-033"),
            ("gate", "NOT_RUN", "LST-AUTH-034"),
        )
        for kind, value, code in cases:
            with self.subTest(kind=kind):
                bundle = valid_authorized_bundle()
                if kind == "mode":
                    bundle["project"]["mode"] = value
                elif kind == "conclusion":
                    bundle["project"]["conclusion"] = value
                else:
                    bundle["gates"]["publication"] = value
                result = validate_listing_bundle(bundle)
                self.assertTrue(any(f"[{code}]" in error for error in result["errors"]), result["errors"])

    def test_publication_rows_are_closed_hashed_and_bijective(self):
        extra_key = valid_authorized_bundle()
        extra_key["baseline"][0]["unexpected"] = "not authorized"
        result = validate_listing_bundle(extra_key)
        self.assertTrue(any("[LST-BASELINE-001]" in error for error in result["errors"]), result["errors"])

        tampered = valid_authorized_bundle()
        tampered["change_set"][0]["after_value"] = "Unhashed replacement"
        result = validate_listing_bundle(tampered)
        self.assertTrue(any("[LST-CHANGE-002]" in error for error in result["errors"]), result["errors"])

        missing_baseline = valid_authorized_bundle()
        missing_baseline["baseline"] = []
        result = validate_listing_bundle(missing_baseline)
        self.assertTrue(any("[LST-PUBLISH-008]" in error for error in result["errors"]), result["errors"])

        duplicate_rollback = valid_authorized_bundle()
        second = copy.deepcopy(duplicate_rollback["rollback"][0])
        second["id"] = "ROLLBACK-2"
        second["row_sha256"] = canonical_row_hash(second)
        duplicate_rollback["rollback"].append(second)
        result = validate_listing_bundle(duplicate_rollback)
        self.assertTrue(any("[LST-ROLLBACK-009]" in error for error in result["errors"]), result["errors"])

        wrong_restore = valid_authorized_bundle()
        wrong_restore["rollback"][0]["rollback_value"] = "invented rollback"
        wrong_restore["rollback"][0]["row_sha256"] = canonical_row_hash(wrong_restore["rollback"][0])
        result = validate_listing_bundle(wrong_restore)
        self.assertTrue(any("[LST-ROLLBACK-006]" in error for error in result["errors"]), result["errors"])

    def test_live_match_is_bound_to_authorized_expected_value_and_frontend_evidence(self):
        invented = valid_live_bundle()
        invented["live_readback"][0]["expected_value"] = "Invented but equal"
        invented["live_readback"][0]["observed_value"] = "Invented but equal"
        result = validate_listing_bundle(invented)
        self.assertTrue(any("[LST-READBACK-016]" in error for error in result["errors"]), result["errors"])

        backend_only = valid_live_bundle()
        backend_only["sources"][-1]["type"] = "authorized_backend"
        result = validate_listing_bundle(backend_only)
        self.assertTrue(any("[LST-READBACK-014]" in error for error in result["errors"]), result["errors"])

        duplicate = valid_live_bundle()
        duplicate["live_readback"].append(copy.deepcopy(duplicate["live_readback"][0]))
        result = validate_listing_bundle(duplicate)
        self.assertTrue(any("[LST-READBACK-008]" in error for error in result["errors"]), result["errors"])

        preauthorized = valid_live_bundle()
        auth_time = datetime.fromisoformat(preauthorized["publish_authorization"]["authorized_at"])
        preauthorized["live_readback"][0]["observed_at"] = (auth_time - timedelta(seconds=1)).isoformat()
        result = validate_listing_bundle(preauthorized)
        self.assertTrue(any("[LST-READBACK-017]" in error for error in result["errors"]), result["errors"])

    def test_multifield_live_readback_requires_canonical_complete_child_value(self):
        bundle = valid_authorized_bundle()
        field = copy.deepcopy(bundle["field_resolutions"][0])
        field.update({"id": "FR-2", "semantic_role": "title", "canonical_key": "item_name", "ui_label": "Title"})
        bundle["field_resolutions"].append(field)
        candidate = copy.deepcopy(bundle["field_candidates"][0])
        candidate.update({"id": "FC-2", "field_resolution_id": "FR-2", "semantic_role": "title", "value": "Fixture product title"})
        bundle["field_candidates"].append(candidate)
        baseline = copy.deepcopy(bundle["baseline"][0])
        baseline.update({"id": "BASE-2", "field_resolution_id": "FR-2", "before_value": "Old title"})
        baseline["row_sha256"] = canonical_row_hash(baseline)
        bundle["baseline"].append(baseline)
        change = copy.deepcopy(bundle["change_set"][0])
        change.update({"id": "CHG-2", "field_resolution_id": "FR-2", "after_value": candidate["value"]})
        change["row_sha256"] = canonical_row_hash(change)
        bundle["change_set"].append(change)
        rollback = copy.deepcopy(bundle["rollback"][0])
        rollback.update({
            "id": "ROLLBACK-2", "change_set_id": "CHG-2", "baseline_id": "BASE-2",
            "field_resolution_id": "FR-2", "rollback_value": "Old title",
        })
        rollback["row_sha256"] = canonical_row_hash(rollback)
        bundle["rollback"].append(rollback)
        bundle["publish_authorization"].update({
            "change_set_ids": ["CHG-1", "CHG-2"],
            "baseline_sha256": canonical_rows_hash(bundle["baseline"]),
            "change_set_sha256": canonical_rows_hash(bundle["change_set"]),
        })
        observed_at = datetime.now(timezone.utc).isoformat()
        bundle["sources"].append({
            "id": "SRC-LIVE-MULTI", "type": "public_frontend",
            "locator": f"https://www.amazon.com/dp/{CHILD}", "authority": "primary",
            "retrieved_at": observed_at, "status": "USABLE",
        })
        expected = canonical_child_readback_value(bundle["change_set"], CHILD)
        bundle["live_readback"] = [{
            "child_asin": CHILD, "status": "LIVE_MATCH", "live_pass": True,
            "observed_at": observed_at, "locator": f"https://www.amazon.com/dp/{CHILD}",
            "expected_value": expected, "observed_value": expected, "evidence_ref": "SRC-LIVE-MULTI",
        }]
        bundle["project"]["conclusion"] = "LIVE_PASS"
        bundle["gates"]["live_readback"] = "PASS"
        complete = validate_listing_bundle(bundle)
        self.assertTrue(complete["ok"], complete["errors"])

        bundle["live_readback"][0]["expected_value"] = change["after_value"]
        bundle["live_readback"][0]["observed_value"] = change["after_value"]
        incomplete = validate_listing_bundle(bundle)
        self.assertTrue(any("[LST-READBACK-016]" in error for error in incomplete["errors"]), incomplete["errors"])

    def test_single_child_topology_and_candidate_dimensions_are_mandatory(self):
        missing = valid_bundle()
        missing["variant_topology"] = []
        result = validate_listing_bundle(missing)
        self.assertTrue(any("[LST-VARIANT-005]" in error for error in result["errors"]), result["errors"])

        unbound_pack = valid_bundle()
        unbound_pack["field_candidates"][0]["application_scope"]["packs"] = []
        result = validate_listing_bundle(unbound_pack)
        self.assertTrue(any("[LST-CANDIDATE-012]" in error for error in result["errors"]), result["errors"])

    def test_field_candidate_semantics_planes_and_community_qa_are_closed(self):
        semantic = valid_bundle()
        semantic["field_candidates"][0]["semantic_role"] = "title"
        result = validate_listing_bundle(semantic)
        self.assertTrue(any("[LST-CANDIDATE-010]" in error for error in result["errors"]), result["errors"])

        plane = valid_bundle()
        plane["rule_snapshots"][0]["data_plane"] = "relationship"
        result = validate_listing_bundle(plane)
        self.assertTrue(any("[LST-FIELD-006]" in error for error in result["errors"]), result["errors"])

        candidate_qa = valid_bundle()
        candidate_qa["field_candidates"][0]["semantic_role"] = "community_q_and_a"
        result = validate_listing_bundle(candidate_qa)
        self.assertTrue(any("[LST-QA-002]" in error for error in result["errors"]), result["errors"])

        field_qa = valid_bundle()
        field_qa["field_resolutions"][0]["canonical_key"] = "customer_questions_and_answers"
        result = validate_listing_bundle(field_qa)
        self.assertTrue(any("[LST-QA-003]" in error for error in result["errors"]), result["errors"])

    def test_accepted_risk_cannot_hide_truth_or_child_uncertainty_in_pass(self):
        now = datetime.now(timezone.utc)
        bundle = valid_bundle()
        bundle["conflicts"] = [{
            "id": "RISK-1", "description": "A disputed included-item fact",
            "affected_fact_ids": ["F-1"], "affected_claim_ids": [],
            "affected_child_asins": [CHILD], "status": "ACCEPTED_RISK",
            "resolution": "Temporary business acceptance", "owner": "Catalog owner",
            "accepted_by": "Brand owner", "acceptance_authority": "Account owner",
            "accepted_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(days=1)).isoformat(), "severity": "LOW",
            "acceptance_source_ids": ["SRC-1"],
        }]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[LST-CONFLICT-005]" in error for error in result["errors"]), result["errors"])

    def test_scaffold_template_is_valid(self):
        template = json.loads((HERE.parent / "assets" / "listing-project-bundle-template.json").read_text(encoding="utf-8"))
        result = validate_listing_bundle(template)
        self.assertTrue(result["ok"], result["errors"])

    def test_scaffold_pollution_and_embedded_result_are_rejected(self):
        template = json.loads((HERE.parent / "assets" / "listing-project-bundle-template.json").read_text(encoding="utf-8"))
        polluted = copy.deepcopy(template)
        polluted["project"]["notes"] = "operational content hidden in scaffold"
        result = validate_listing_bundle(polluted)
        self.assertTrue(any("[LST-SCAFFOLD-002]" in error for error in result["errors"]), result["errors"])
        result = validate_listing_bundle(template, {})
        self.assertTrue(any("[LST-SCAFFOLD-003]" in error for error in result["errors"]), result["errors"])

    def test_all_negative_fixture_descriptors(self):
        fixture_paths = sorted((HERE / "fixtures").glob("*.json"))
        self.assertGreaterEqual(len(fixture_paths), 10)
        for path in fixture_paths:
            with self.subTest(fixture=path.name):
                descriptor = json.loads(path.read_text(encoding="utf-8"))
                bundle = valid_bundle()
                for mutation in descriptor["mutations"]:
                    self.assertEqual(mutation["op"], "set")
                    set_path(bundle, mutation["path"], mutation["value"])
                result = validate_listing_bundle(bundle)
                code = f"[{descriptor['expected_code']}]"
                self.assertFalse(result["ok"])
                self.assertTrue(any(code in error for error in result["errors"]), result["errors"])

    def test_handoff_hash_must_match(self):
        bundle = frozen_handoff_parent()
        bundle["enriched_content_handoff"]["parent_bundle_sha256"] = "sha256:wrong"
        result = validate_listing_bundle(bundle, minimal_aplus_result(bundle))
        self.assertTrue(any("[LST-HANDOFF-006]" in x for x in result["errors"]))

    def test_handoff_native_answer_and_upstream_reference_are_fail_closed(self):
        native = frozen_handoff_parent()
        native["enriched_content_handoff"]["decision_requirements"][0]["native_answer_required"] = False
        reseal_handoff(native)
        result = validate_listing_bundle(native)
        self.assertTrue(any("[LST-HANDOFF-042]" in error for error in result["errors"]), result["errors"])

        upstream = frozen_handoff_parent()
        upstream["decision_map"]["requirements"][0]["early_disclosure_required"] = True
        upstream["surface_assignments"][0].update({
            "primary_surface": "core_copy", "primary_carrier_kind": "NATIVE_VISIBLE",
            "field_resolution_id": "FR-1", "application_scope": app_scope(packs=[]),
        })
        upstream["enriched_content_handoff"]["decision_requirements"][0].update({
            "early_disclosure_required": True, "upstream_primary_carrier_ref": "SA-1",
        })
        reseal_handoff(upstream)
        result = validate_listing_bundle(upstream)
        self.assertTrue(any("[LST-HANDOFF-037]" in error for error in result["errors"]), result["errors"])

    def test_legacy_embedded_round_trip_is_rejected_for_coordinator(self):
        bundle = frozen_handoff_parent()
        result = validate_listing_bundle(bundle, minimal_aplus_result(bundle))
        self.assertFalse(result["ok"])
        self.assertEqual(result["contract_status"], "LEGACY_LOCAL_CONTRACT")
        self.assertTrue(any("[LST-XBUNDLE-020]" in error for error in result["errors"]), result["errors"])

    def test_legacy_cli_aplus_flag_is_retained_but_never_reads_child(self):
        case_dir = Path(TEST_TEMP_DIR.name) / "legacy-cli-boundary"
        case_dir.mkdir(exist_ok=True)
        parent_path = case_dir / "parent.json"
        parent_path.write_text(json.dumps(valid_bundle(), ensure_ascii=False), encoding="utf-8")
        missing_child = case_dir / "must-not-be-read.json"
        completed = subprocess.run(
            [sys.executable, str(HERE / "validate_listing_bundle.py"), str(parent_path), "--aplus-result", str(missing_child)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(any("[LST-XBUNDLE-020]" in error for error in payload["errors"]), payload)
        self.assertEqual(payload["contract_status"], "LEGACY_LOCAL_CONTRACT")

    def test_legacy_relative_aplus_path_does_not_enable_cross_validation(self):
        bundle = frozen_handoff_parent()
        aplus = minimal_aplus_result(bundle)
        case_dir = Path(TEST_TEMP_DIR.name) / "relative-aplus-case"
        case_dir.mkdir(exist_ok=True)
        parent_path = case_dir / "listing-parent.json"
        child_path = case_dir / "aplus-child.json"
        parent_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        aplus["workflow_context"]["parent_bundle_ref"] = parent_path.name
        result = validate_listing_bundle(bundle, aplus, aplus_source_path=child_path)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[LST-XBUNDLE-020]" in error for error in result["errors"]), result["errors"])

    def test_legacy_parent_never_executes_sibling_aplus_validator(self):
        bundle = frozen_handoff_parent()
        aplus = minimal_aplus_result(bundle)
        aplus["modules"][0]["native_body"] = "This field no longer contains the exact answer."
        result = validate_listing_bundle(bundle, aplus)
        self.assertTrue(any("[LST-XBUNDLE-020]" in error for error in result["errors"]), result["errors"])

    def test_legacy_aplus_terminal_result_is_not_consumed(self):
        bundle = frozen_handoff_parent()
        bundle["project"]["conclusion"] = "CONDITIONAL_PASS"
        reseal_handoff(bundle)
        result = validate_listing_bundle(bundle, minimal_aplus_result(bundle))
        self.assertTrue(any("[LST-XBUNDLE-020]" in error for error in result["errors"]), result["errors"])

    def test_legacy_aplus_scope_is_rejected_before_cross_bundle_use(self):
        bundle = frozen_handoff_parent()
        aplus = minimal_aplus_result(bundle)
        aplus["enriched_content_handoff"]["application_scope"]["child_asins"] = ["CHILD-1", "CHILD-2"]
        result = validate_listing_bundle(bundle, aplus)
        self.assertTrue(any("[LST-XBUNDLE-020]" in x for x in result["errors"]))

    def test_legacy_aplus_fact_payload_is_rejected_before_cross_bundle_use(self):
        bundle = frozen_handoff_parent()
        aplus = minimal_aplus_result(bundle)
        aplus["facts"][0]["statement"] = "Two products are included."
        result = validate_listing_bundle(bundle, aplus)
        self.assertTrue(any("[LST-XBUNDLE-020]" in x for x in result["errors"]))

    def test_forward_hx02_pack_fact_cannot_expand(self):
        bundle = valid_bundle()
        bundle["scope"].update({
            "intended_child_asins": ["HX02-2PK", "HX02-3PK"],
            "packs": ["2PK", "3PK"],
        })
        bundle["field_resolutions"][0]["application_scope"].update({"child_asins": ["HX02-2PK", "HX02-3PK"], "packs": ["2PK", "3PK"]})
        bundle["facts"][0]["application_scope"].update({"child_asins": ["HX02-3PK"], "packs": ["3PK"]})
        bundle["claims"][0]["application_scope"].update({"child_asins": ["HX02-3PK"], "packs": ["3PK"]})
        bundle["decision_map"]["requirements"][0]["application_scope"].update({"child_asins": ["HX02-2PK", "HX02-3PK"], "packs": ["2PK", "3PK"]})
        bundle["surface_assignments"][0]["application_scope"].update({"child_asins": ["HX02-2PK", "HX02-3PK"], "packs": ["2PK", "3PK"]})
        bundle["field_candidates"][0]["application_scope"].update({"child_asins": ["HX02-2PK", "HX02-3PK"], "packs": ["2PK", "3PK"]})
        bundle["variant_topology"] = [
            {**bundle["variant_topology"][0], "id": "V-2", "child_asin": "HX02-2PK", "seller_sku": "SKU-2", "pack": "2PK"},
            {**bundle["variant_topology"][0], "id": "V-3", "child_asin": "HX02-3PK", "seller_sku": "SKU-3", "pack": "3PK"},
        ]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[LST-CANDIDATE-008]" in x for x in result["errors"]), result["errors"])

    def test_forward_hx02_corrected_child_pack_scope_passes(self):
        result = validate_listing_bundle(corrected_hx02_bundle())
        self.assertTrue(result["ok"], result["errors"])

    def test_forward_pet_camera_compatibility_cannot_expand(self):
        bundle = valid_bundle()
        bundle["scope"]["intended_child_asins"] = ["CAM-24", "CAM-DUAL"]
        bundle["field_resolutions"][0]["application_scope"]["child_asins"] = ["CAM-24", "CAM-DUAL"]
        bundle["facts"][0].update({"statement": "5 GHz setup is supported.", "application_scope": app_scope(children=["CAM-DUAL"])})
        bundle["claims"][0].update({"text": "Works with 5 GHz Wi-Fi.", "application_scope": app_scope(children=["CAM-DUAL"])})
        bundle["decision_map"]["requirements"][0]["application_scope"]["child_asins"] = ["CAM-24", "CAM-DUAL"]
        bundle["surface_assignments"][0]["application_scope"]["child_asins"] = ["CAM-24", "CAM-DUAL"]
        bundle["field_candidates"][0]["application_scope"]["child_asins"] = ["CAM-24", "CAM-DUAL"]
        bundle["variant_topology"] = [
            {**bundle["variant_topology"][0], "id": "V-24", "child_asin": "CAM-24", "seller_sku": "SKU-24"},
            {**bundle["variant_topology"][0], "id": "V-DUAL", "child_asin": "CAM-DUAL", "seller_sku": "SKU-DUAL"},
        ]
        result = validate_listing_bundle(bundle)
        self.assertTrue(any("[LST-CANDIDATE-008]" in x for x in result["errors"]), result["errors"])

    def test_forward_pet_camera_corrected_child_compatibility_scope_passes(self):
        result = validate_listing_bundle(corrected_pet_camera_bundle())
        self.assertTrue(result["ok"], result["errors"])

    def test_forward_simple_kitchen_item_needs_no_optional_carrier(self):
        bundle = valid_bundle()
        bundle["project"]["title"] = "Single silicone spatula"
        result = validate_listing_bundle(bundle)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(bundle["execution_boundary"], "read_only")
        self.assertEqual(bundle["enriched_content_handoff"]["status"], "NOT_APPLICABLE")
        self.assertEqual(bundle["enriched_content_handoff"]["requested_content_types"], [])
        self.assertEqual(bundle["enriched_content_handoff"]["decision_requirements"], [])

    def test_forward_backend_accepted_frontend_mismatch_blocks_live(self):
        bundle = valid_authorized_bundle()
        observed_at = datetime.now(timezone.utc).isoformat()
        bundle["sources"].append({
            "id": "SRC-BACKEND-READBACK", "type": "authorized_backend",
            "locator": "seller-central-submission-status", "authority": "primary",
            "retrieved_at": observed_at, "status": "USABLE",
        })
        bundle["live_readback"] = [{
            "child_asin": CHILD, "status": "ACCEPTED_BACKEND", "live_pass": False,
            "observed_at": observed_at, "locator": "seller-central-submission-status",
            "expected_value": bundle["change_set"][0]["after_value"], "observed_value": "accepted",
            "evidence_ref": "SRC-BACKEND-READBACK",
        }]
        accepted = validate_listing_bundle(bundle)
        self.assertTrue(accepted["ok"], accepted["errors"])

        bundle["sources"].append({
            "id": "SRC-FRONTEND-MISMATCH", "type": "public_frontend",
            "locator": f"https://www.amazon.com/dp/{CHILD}", "authority": "primary",
            "retrieved_at": observed_at, "status": "USABLE",
        })
        bundle["project"]["conclusion"] = "LIVE_PASS"
        bundle["gates"]["live_readback"] = "PASS"
        bundle["live_readback"][0].update({
            "status": "LIVE_MISMATCH", "locator": f"https://www.amazon.com/dp/{CHILD}",
            "observed_value": "Wrong live bullet", "evidence_ref": "SRC-FRONTEND-MISMATCH",
        })
        result = validate_listing_bundle(bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("[LST-READBACK-006]" in x for x in result["errors"]), result["errors"])
        self.assertFalse(bundle["live_readback"][0]["live_pass"])
        self.assertEqual(bundle["rollback"][0]["rollback_value"], bundle["baseline"][0]["before_value"])
        self.assertNotEqual(bundle["rollback"][0]["rollback_value"], bundle["live_readback"][0]["observed_value"])

        bundle["live_readback"][0].update({
            "status": "LIVE_MATCH", "live_pass": True,
            "observed_value": bundle["live_readback"][0]["expected_value"],
        })
        corrected = validate_listing_bundle(bundle)
        self.assertTrue(corrected["ok"], corrected["errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
