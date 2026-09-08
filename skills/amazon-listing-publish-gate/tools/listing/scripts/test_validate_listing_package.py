#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
import os
from pathlib import Path

from listing_locale_group import (
    GROUP_CONTRACT_VERSION,
    validate_group_manifest,
    validate_listing_locale_group,
)
from listing_v11_lineage import build_lineage_record, canonical_lineage_record_hash
from listing_coordination_receipt import canonical_receipt_hash, canonical_receipt_id
from listing_coordination_ledger import (
    LedgerError,
    append_receipt,
    file_sha256,
    load_receipt_ledger,
    parse_ledger_bytes,
)
from validate_listing_package import (
    DEFAULT_APLUS_VALIDATOR,
    DEFAULT_PARENT_VALIDATOR,
    canonical_handoff_hash,
    canonical_handoff_snapshot_id,
    canonical_parent_hash,
    canonical_sha256,
    hash_block,
    run_validator_cli,
    validate_listing_package,
    validate_listing_package_with_ledger,
)


PARENT = "B0PKGPARENT"
CHILD = "B0PKGCHILD"
HERE = Path(__file__).resolve().parent
PARENT_VALIDATOR_SHA256 = file_sha256(DEFAULT_PARENT_VALIDATOR)
APLUS_VALIDATOR_SHA256 = file_sha256(DEFAULT_APLUS_VALIDATOR)


def validation_results(
    component: str = "COMPONENT_PASS",
    *,
    parent: dict | None = None,
    aplus: dict | None = None,
) -> tuple[dict, dict]:
    parent_result = (
        {
            "ok": True,
            "schema_valid": True,
            "contract_status": "CURRENT_LOCAL_CONTRACT",
            "derived_stage": "HANDOFF_READY",
            "validator_sha256": PARENT_VALIDATOR_SHA256,
            "errors": [],
        }
    )
    aplus_result = (
        {
            "ok": True,
            "structural_valid": True,
            "result_level": component,
            "component_result": component,
            "validator_sha256": APLUS_VALIDATOR_SHA256,
            "errors": [],
        }
    )
    if parent is not None:
        parent_result["validated_input_sha256"] = canonical_sha256(parent)
    if aplus is not None:
        aplus_result["validated_input_sha256"] = canonical_sha256(aplus)
    return parent_result, aplus_result


def reseal_parent(parent: dict) -> None:
    handoff = parent["enriched_content_handoff"]
    handoff["snapshot_id"] = canonical_handoff_snapshot_id(handoff)
    registry = handoff.get("lineage_registry")
    if isinstance(registry, list) and registry and isinstance(registry[0], dict):
        registry[0]["successor_snapshot_id"] = handoff["snapshot_id"]
        registry[0]["record_checksum"] = canonical_lineage_record_hash(registry[0])
        assert handoff["snapshot_id"] == canonical_handoff_snapshot_id(handoff)
    handoff["checksum"] = canonical_handoff_hash(handoff)
    handoff["parent_bundle_sha256"] = canonical_parent_hash(parent)


def make_package(
    *,
    locale: str = "en-US",
    semantic_revision: int = 1,
    predecessor_snapshot_id: str = "",
    refreeze_reason: str = "",
    predecessor_handoff: dict | None = None,
) -> tuple[dict, dict]:
    closure = {
        "status": "PASS",
        "closed_at": "2026-08-28T00:30:00Z",
        "owner": "Research",
        "reason": "P0 evidence closed",
    }
    atom = {
        "id": "ATOM-1",
        "requirement_id": "REQ-1",
        "marketplace": "US",
        "locale": locale,
        "variant_row_id": "V-1",
    }
    requirement = {
        "id": "REQ-1",
        "buyer_question": "What is included?",
        "priority": "P0",
        "application_scope": {
            "parent_asins": [PARENT],
            "child_asins": [CHILD],
            "packs": ["1PK"],
            "colors": ["Black"],
            "sizes": ["M"],
        },
        "fact_ids": ["F-1"],
        "claim_ids": ["C-1"],
        "native_answer_required": True,
        "early_disclosure_required": False,
        "upstream_primary_carrier_ref": "",
        "assigned_surface": "enriched_content",
        "status": "READY",
    }
    denominator = {
        "status": "FROZEN",
        "frozen_at": "2026-08-28T01:00:00Z",
        "requirement_ids": ["REQ-1"],
        "variant_row_ids": ["V-1"],
        "atoms": [copy.deepcopy(atom)],
        "checksum": "",
    }
    denominator["checksum"] = hash_block(denominator)
    ptd = {
        "status": "COMPLETE",
        "expected_fields": [{"id": "FIELD-1", "closure_status": "CLOSED"}],
        "checksum": "",
    }
    ptd["checksum"] = hash_block(ptd)
    handoff_scope = {
        "parent_asins": [PARENT],
        "child_asins": [CHILD],
        "packs": ["1PK"],
        "colors": ["Black"],
        "sizes": ["M"],
    }
    parent = {
        "schema_version": "1.1",
        "project": {
            "project_id": "LISTING-PKG",
            "target_stage": "HANDOFF_READY",
            "conclusion": "CONDITIONAL_PASS",
        },
        "execution_boundary": "read_only",
        "scope": {
            "marketplace": "US",
            "locale": locale,
            "parent_asins": [PARENT],
            "intended_child_asins": [CHILD],
            "packs": ["1PK"],
            "colors": ["Black"],
            "sizes": ["M"],
        },
        "discovery": {"closure": copy.deepcopy(closure)},
        "ptd_field_inventory": ptd,
        "decision_denominator_snapshot": denominator,
        "decision_map": {"requirements": [copy.deepcopy(requirement)]},
        "variant_topology": [{
            "id": "V-1",
            "parent_asin": PARENT,
            "child_asin": CHILD,
            "seller_sku": "SKU-1",
            "pack": "1PK",
            "color": "Black",
            "size": "M",
        }],
        "canonical_assertions": [{
            "id": "ASSERT-1",
            "statement": "Includes one black item.",
            "fact_ids": ["F-1"],
            "claim_ids": ["C-1"],
            "application_scope": copy.deepcopy(handoff_scope),
            "status": "FINAL",
        }],
        "facts": [{"id": "F-1", "statement": "One black item is included."}],
        "claims": [{"id": "C-1", "text": "Includes one black item."}],
        "decision_answer_units": [],
        "enriched_content_handoff": {
            "contract_version": "1.1",
            "snapshot_id": "",
            "parent_project_id": "LISTING-PKG",
            "parent_bundle_sha256": "",
            "status": "FROZEN",
            "maximum_output": "preflight_package",
            "marketplace": "US",
            "locale": locale,
            "product_type": "GENERIC",
            "application_scope": handoff_scope,
            "variant_row_ids": ["V-1"],
            "fact_ids": ["F-1"],
            "claim_ids": ["C-1"],
            "blocked_claim_ids": [],
            "conflict_ids": [],
            "source_ids": ["SRC-1"],
            "requested_content_types": ["PREMIUM_A_PLUS"],
            "decision_requirements": [copy.deepcopy(requirement)],
            "capability_snapshot_ids": ["CAP-1"],
            "discovery_closure_hash": canonical_sha256(closure),
            "ptd_inventory_hash": hash_block(ptd),
            "decision_denominator_hash": hash_block(denominator),
            "canonical_assertion_ids": ["ASSERT-1"],
            "requirement_atoms": [copy.deepcopy(atom)],
            "prohibited_actions": [
                "modify_parent_truth", "expand_application_scope", "online_submission",
            ],
            "created_at": "2026-08-28T01:15:00Z" if semantic_revision > 1 else "2026-08-28T01:05:00Z",
            "owner": "Listing Owner",
            "predecessor_snapshot_id": (
                str(predecessor_handoff.get("snapshot_id", ""))
                if isinstance(predecessor_handoff, dict) else predecessor_snapshot_id
            ),
            "semantic_revision": semantic_revision,
            "refreeze_reason": refreeze_reason,
            "lineage_registry": (
                [build_lineage_record(
                    predecessor_handoff,
                    successor_snapshot_id="",
                    superseded_at="2026-08-28T01:10:00Z",
                )]
                if isinstance(predecessor_handoff, dict) else []
            ),
            "checksum": "",
        },
        "publish_authorization": {"status": "NOT_AUTHORIZED"},
        "live_readback": [],
    }
    reseal_parent(parent)
    frozen_handoff = copy.deepcopy(parent["enriched_content_handoff"])
    snapshot_id = frozen_handoff["snapshot_id"]

    delegated_denominator = copy.deepcopy(denominator)
    delegated_denominator.update({
        "source": "PARENT_HANDOFF",
        "source_hash": denominator["checksum"],
    })
    delegated_denominator["checksum"] = hash_block(delegated_denominator)
    aplus = {
        "schema_version": "1.3",
        "project": {
            "marketplace": "US",
            "locale": locale,
            "write_scope": "read_only",
            "conclusion": "PASS",
        },
        "scope": {
            "status": "FROZEN",
            "marketplaces": ["US"],
            "locales": [locale],
            "parent_asins": [PARENT],
            "intended_child_asins": [CHILD],
            "packs": ["1PK"],
            "colors": ["Black"],
            "sizes_or_capacities": ["M"],
            "other_dimensions": {},
        },
        "workflow_context": {
            "mode": "embedded",
            "parent_bundle_ref": "parent.json",
            "accepted_handoff_snapshot_id": snapshot_id,
            "accepted_at": "2026-08-28T01:20:00Z" if semantic_revision > 1 else "2026-08-28T01:10:00Z",
            "accepted_by": "A+ Owner",
            "execution_boundary": "read_only",
        },
        "enriched_content_handoff": frozen_handoff,
        "decision_denominator_snapshot": delegated_denominator,
        "decision_map": {"requirements": [copy.deepcopy(requirement)]},
        "variants": [{
            "id": "V-1",
            "marketplace": "US",
            "locale": locale,
            "parent_asin": PARENT,
            "child_asin": CHILD,
            "pack": "1PK",
            "color": "Black",
            "size_or_capacity": "M",
        }],
        "canonical_assertions": [{
            "id": "ASSERT-1",
            "statement": "Includes one black item.",
            "fact_ids": ["F-1"],
            "claim_ids": ["C-1"],
            "application_scope": {
                "marketplace": "US",
                "locale": locale,
                "parent_asin": PARENT,
                "child_asins": [CHILD],
                "packs": ["1PK"],
                "colors": ["Black"],
                "sizes_or_capacities": ["M"],
                "other_variants": {},
            },
            "variant_row_ids": ["V-1"],
            "locale_expressions": [{
                "locale": locale,
                "text": "Includes one black item.",
                "fact_ids": ["F-1"],
                "claim_ids": ["C-1"],
            }],
            "publish_status": "PUBLISHABLE",
        }],
        "facts": [{"id": "F-1", "statement": "One black item is included."}],
        "claims": [{"id": "C-1", "text": "Includes one black item."}],
        "decision_answer_units": [{
            "id": "ANSWER-1",
            "requirement_id": "REQ-1",
            "requirement_atom_id": "ATOM-1",
            "variant_row_id": "V-1",
            "primary_carrier_id": "CARRIER-1",
            "text": "Includes one black item.",
            "fact_ids": ["F-1"],
            "claim_ids": ["C-1"],
            "canonical_assertion_ids": ["ASSERT-1"],
            "content_status": "FINAL_CANDIDATE",
            "qa_status": "PASS",
        }],
        "carriers": [{
            "id": "CARRIER-1",
            "carrier_type": "native_text",
            "coverage_role": "PRIMARY_NATIVE_ANSWER",
            "variant_row_ids": ["V-1"],
            "canonical_assertion_ids": ["ASSERT-1"],
            "content_status": "FINAL_CANDIDATE",
            "qa_status": "PASS",
        }],
        "coverage_summary": {
            "p0_atoms_required": 1,
            "p0_atoms_pass": 1,
            "gap_atom_ids": [],
        },
        "delta_evidence_requests": [],
        "component_result": {
            "status": "COMPONENT_PASS",
            "gap_atom_ids": [],
            "open_delta_request_ids": [],
            "page_pass_implied": False,
            "publication_authorized": False,
            "owner": "A+ QA",
        },
    }
    parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
    reseal_parent(parent)
    return parent, aplus


def coordinate(
    parent: dict,
    aplus: dict,
    prior_receipt: dict | None = None,
    *,
    auto_ack: bool = True,
) -> dict:
    if (
        auto_ack
        and parent.get("enriched_content_handoff", {}).get("status") == "RESULT_RECEIVED"
    ):
        frozen_parent = copy.deepcopy(parent)
        frozen_parent["enriched_content_handoff"]["status"] = "FROZEN"
        frozen_parent_result, frozen_aplus_result = validation_results(
            aplus["component_result"]["status"], parent=frozen_parent, aplus=aplus,
        )
        frozen_parent_result["parent_bundle_sha256"] = canonical_parent_hash(frozen_parent)
        awaiting = validate_listing_package(
            frozen_parent,
            aplus,
            parent_validation=frozen_parent_result,
            aplus_validation=frozen_aplus_result,
            prior_receipt=prior_receipt,
        )
        prior_receipt = awaiting.get("coordination_receipt")
    parent_result, aplus_result = validation_results(
        aplus["component_result"]["status"], parent=parent, aplus=aplus,
    )
    parent_result["parent_bundle_sha256"] = canonical_parent_hash(parent)
    return validate_listing_package(
        parent,
        aplus,
        parent_validation=parent_result,
        aplus_validation=aplus_result,
        prior_receipt=prior_receipt,
    )


def controlled_coordinate(
    parent: dict,
    aplus: dict,
    ledger_path: Path,
    *,
    record: bool,
    require_existing: bool = False,
) -> dict:
    parent_result, aplus_result = validation_results(
        aplus["component_result"]["status"], parent=parent, aplus=aplus,
    )
    parent_result["parent_bundle_sha256"] = canonical_parent_hash(parent)
    return validate_listing_package_with_ledger(
        parent,
        aplus,
        parent_validation=parent_result,
        aplus_validation=aplus_result,
        receipt_ledger=ledger_path,
        record_receipt=record,
        parent_validator=DEFAULT_PARENT_VALIDATOR,
        aplus_validator=DEFAULT_APLUS_VALIDATOR,
        require_existing_ledger=require_existing,
    )


def group_manifest(locales: tuple[str, ...] = ("en-US", "fr-FR")) -> dict:
    return {
        "contract_version": GROUP_CONTRACT_VERSION,
        "group_id": "GROUP-US-1",
        "marketplace": "US",
        "members": [{
            "locale": locale,
            "parent_bundle": f"{locale}-parent.json",
            "aplus_bundle": f"{locale}-aplus.json",
            "coordination_ledger": f"{locale}-receipts.jsonl",
        } for locale in locales],
    }


def group_member(locale: str, localized_text: str | None = None) -> dict:
    parent, aplus = make_package(locale=locale)
    if localized_text is not None:
        aplus["canonical_assertions"][0]["locale_expressions"][0]["text"] = localized_text
    return {
        "locale": locale,
        "parent": parent,
        "aplus": aplus,
        "pair_result": coordinate(parent, aplus),
    }


def refreeze_pair(parent: dict, aplus: dict) -> None:
    parent["enriched_content_handoff"]["status"] = "FROZEN"
    reseal_parent(parent)
    aplus["enriched_content_handoff"] = copy.deepcopy(parent["enriched_content_handoff"])
    aplus["workflow_context"]["accepted_handoff_snapshot_id"] = (
        parent["enriched_content_handoff"]["snapshot_id"]
    )
    parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
    reseal_parent(parent)


def replace_exact_scalar(value, old: str, new: str):
    if isinstance(value, dict):
        return {key: replace_exact_scalar(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_exact_scalar(item, old, new) for item in value]
    return new if value == old else value


def clone_real_pair_to_locale(locale: str, localized_text: str) -> tuple[dict, dict]:
    parent_path = HERE / "integration_fixtures" / "listing-v1.1-result-received-pass.json"
    aplus_path = (
        HERE.parent.parent / "aplus" / "scripts" /
        "fixtures" / "aplus-v1.3-embedded-pass.json"
    )
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    aplus = json.loads(aplus_path.read_text(encoding="utf-8"))
    parent = replace_exact_scalar(parent, "en-US", locale)
    aplus = replace_exact_scalar(aplus, "en-US", locale)

    parent["decision_denominator_snapshot"]["checksum"] = hash_block(
        parent["decision_denominator_snapshot"]
    )
    handoff = parent["enriched_content_handoff"]
    handoff["decision_denominator_hash"] = hash_block(parent["decision_denominator_snapshot"])
    handoff.update({
        "status": "FROZEN",
        "snapshot_id": "",
        "parent_bundle_sha256": "",
        "predecessor_snapshot_id": "",
        "semantic_revision": 1,
        "refreeze_reason": "",
        "lineage_registry": [],
        "checksum": "",
    })
    reseal_parent(parent)
    frozen_handoff = copy.deepcopy(parent["enriched_content_handoff"])
    aplus["enriched_content_handoff"] = frozen_handoff
    aplus["workflow_context"]["accepted_handoff_snapshot_id"] = frozen_handoff["snapshot_id"]
    delegated = copy.deepcopy(parent["decision_denominator_snapshot"])
    delegated.update({
        "source": "PARENT_HANDOFF",
        "source_hash": parent["decision_denominator_snapshot"]["checksum"],
    })
    delegated["checksum"] = hash_block(delegated)
    aplus["decision_denominator_snapshot"] = delegated
    aplus["canonical_assertions"][0]["locale_expressions"][0]["text"] = localized_text
    parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
    reseal_parent(parent)
    return parent, aplus


def write_real_group(root: Path) -> Path:
    locales = (
        ("en-US", "Includes one black spatula."),
        ("fr-FR", "Comprend une spatule noire."),
    )
    for locale, localized_text in locales:
        parent, aplus = clone_real_pair_to_locale(locale, localized_text)
        frozen_parent = copy.deepcopy(parent)
        frozen_parent["enriched_content_handoff"]["status"] = "FROZEN"
        awaiting = coordinate(frozen_parent, aplus, auto_ack=False)
        assert awaiting["package_result"] == "AWAITING_RESULT_ACK", awaiting
        awaiting_receipt = awaiting["coordination_receipt"]
        candidate = coordinate(
            parent, aplus, prior_receipt=awaiting_receipt, auto_ack=False,
        )
        assert candidate["package_result"] == "PASS_CANDIDATE", candidate
        pass_receipt = candidate["coordination_receipt"]
        (root / f"{locale}-parent.json").write_text(
            json.dumps(parent, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
        )
        (root / f"{locale}-aplus.json").write_text(
            json.dumps(aplus, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
        )
        ledger_path = root / f"{locale}-receipts.jsonl"
        append_receipt(ledger_path, awaiting_receipt)
        append_receipt(ledger_path, pass_receipt)
    manifest_path = root / "group.json"
    manifest_path.write_text(
        json.dumps(group_manifest(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
    )
    return manifest_path


def frozen_lineage(aplus: dict) -> dict:
    handoff = aplus["enriched_content_handoff"]
    return {
        "snapshot_id": handoff["snapshot_id"],
        "parent_bundle_sha256": handoff["parent_bundle_sha256"],
        "discovery_closure_hash": handoff["discovery_closure_hash"],
        "ptd_inventory_hash": handoff["ptd_inventory_hash"],
        "decision_denominator_hash": handoff["decision_denominator_hash"],
        "handoff_checksum": handoff["checksum"],
    }


def delta_receipt_for_pair(parent: dict, aplus: dict) -> dict:
    delta_parent = copy.deepcopy(parent)
    delta_aplus = copy.deepcopy(aplus)
    delta_parent["enriched_content_handoff"]["status"] = "RECONCILIATION_REQUIRED"
    reseal_parent(delta_parent)
    delta_aplus["component_result"].update({
        "status": "DELTA_REQUIRED",
        "gap_atom_ids": ["ATOM-1"],
        "open_delta_request_ids": ["DELTA-1"],
    })
    delta_aplus["coverage_summary"].update({"p0_atoms_pass": 0, "gap_atom_ids": ["ATOM-1"]})
    delta_aplus["delta_evidence_requests"] = [{
        "id": "DELTA-1",
        "question": "Confirm included quantity.",
        "affected_requirement_ids": ["REQ-1"],
        "affected_atom_ids": ["ATOM-1"],
        "affected_fact_ids": [],
        "affected_claim_ids": [],
        "affected_module_ids": [],
        "handoff_lineage": frozen_lineage(delta_aplus),
        "status": "OPEN",
    }]
    result = coordinate(delta_parent, delta_aplus, auto_ack=False)
    assert result["package_result"] == "DELTA_REQUIRED", result
    assert isinstance(result["coordination_receipt"], dict), result
    return result["coordination_receipt"]


def add_valid_early_disclosure(parent: dict, aplus: dict) -> None:
    scope = copy.deepcopy(parent["enriched_content_handoff"]["application_scope"])
    requirement = parent["decision_map"]["requirements"][0]
    requirement["early_disclosure_required"] = True
    requirement["upstream_primary_carrier_ref"] = "SA-EARLY"
    parent["field_resolutions"] = [{
        "id": "FR-EARLY",
        "semantic_role": "BULLET",
        "canonical_key": "bullet_point",
        "data_plane": "seller_listing",
        "surface": "core_copy",
        "status": "RESOLVED",
        "exists": True,
        "editable": True,
        "applicable": True,
        "visibility": "BUYER_VISIBLE",
        "application_scope": copy.deepcopy(scope),
    }]
    parent["surface_assignments"] = [{
        "id": "SA-EARLY",
        "requirement_id": "REQ-1",
        "primary_surface": "core_copy",
        "primary_carrier_kind": "NATIVE_VISIBLE",
        "field_resolution_id": "FR-EARLY",
        "application_scope": copy.deepcopy(scope),
        "status": "PASS",
    }]
    parent["field_candidates"] = [{
        "id": "FC-EARLY",
        "field_resolution_id": "FR-EARLY",
        "semantic_role": "BULLET",
        "value": "Includes one black item. See A+ for additional proof.",
        "application_scope": copy.deepcopy(scope),
        "fact_ids": ["F-1"],
        "claim_ids": ["C-1"],
        "content_status": "FINAL",
        "qa_status": "PASS",
    }]
    parent["decision_answer_units"] = [{
        "id": "DAU-EARLY",
        "atom_id": "ATOM-1",
        "requirement_id": "REQ-1",
        "variant_row_id": "V-1",
        "answer_text": "Includes one black item.",
        "field_candidate_id": "FC-EARLY",
        "canonical_assertion_ids": ["ASSERT-1"],
        "fact_ids": ["F-1"],
        "claim_ids": ["C-1"],
        "status": "PASS",
    }]
    parent["enriched_content_handoff"]["decision_requirements"] = [copy.deepcopy(requirement)]
    aplus["decision_map"]["requirements"] = [copy.deepcopy(requirement)]
    aplus["decision_answer_units"][0]["early_disclosure_required"] = True
    parent["enriched_content_handoff"]["status"] = "FROZEN"
    reseal_parent(parent)
    aplus["enriched_content_handoff"] = copy.deepcopy(parent["enriched_content_handoff"])
    aplus["workflow_context"]["accepted_handoff_snapshot_id"] = parent["enriched_content_handoff"]["snapshot_id"]
    parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
    reseal_parent(parent)


class ListingPackageCoordinatorTests(unittest.TestCase):
    def test_pure_api_never_returns_terminal_pass(self):
        parent, aplus = make_package()
        frozen_parent = copy.deepcopy(parent)
        frozen_parent["enriched_content_handoff"]["status"] = "FROZEN"
        reseal_parent(frozen_parent)
        awaiting = coordinate(frozen_parent, aplus, auto_ack=False)
        candidate = coordinate(
            parent,
            aplus,
            prior_receipt=awaiting["coordination_receipt"],
            auto_ack=False,
        )
        self.assertFalse(candidate["ok"])
        self.assertEqual(candidate["package_result"], "PASS_CANDIDATE")
        self.assertEqual(candidate["coordination_receipt"]["result"], "PASS")

    def test_ledger_head_blocks_old_await_replay_after_delta(self):
        parent, aplus = make_package()
        frozen_parent = copy.deepcopy(parent)
        frozen_parent["enriched_content_handoff"]["status"] = "FROZEN"
        reseal_parent(frozen_parent)
        delta_parent = copy.deepcopy(parent)
        delta_aplus = copy.deepcopy(aplus)
        delta_parent["enriched_content_handoff"]["status"] = "RECONCILIATION_REQUIRED"
        reseal_parent(delta_parent)
        delta_aplus["component_result"].update({
            "status": "DELTA_REQUIRED",
            "gap_atom_ids": ["ATOM-1"],
            "open_delta_request_ids": ["DELTA-1"],
        })
        delta_aplus["coverage_summary"].update({"p0_atoms_pass": 0, "gap_atom_ids": ["ATOM-1"]})
        delta_aplus["delta_evidence_requests"] = [{
            "id": "DELTA-1",
            "question": "Confirm quantity.",
            "affected_requirement_ids": ["REQ-1"],
            "affected_atom_ids": ["ATOM-1"],
            "affected_fact_ids": [],
            "affected_claim_ids": [],
            "affected_module_ids": [],
            "handoff_lineage": frozen_lineage(delta_aplus),
            "status": "OPEN",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "receipts.jsonl"
            awaiting = controlled_coordinate(frozen_parent, aplus, ledger_path, record=True)
            old_await_hash = awaiting["coordination_receipt"]["receipt_sha256"]
            delta = controlled_coordinate(delta_parent, delta_aplus, ledger_path, record=True)
            self.assertEqual(delta["ledger"]["head_result"], "DELTA_REQUIRED")
            self.assertNotEqual(delta["ledger"]["head_receipt_sha256"], old_await_hash)
            replay = controlled_coordinate(
                parent, aplus, ledger_path, record=False, require_existing=True,
            )
            self.assertFalse(replay["ok"])
            self.assertTrue(any("PKG-RECEIPT-016" in row for row in replay["errors"]), replay["errors"])

    def test_delta_head_requires_exact_superseded_refreeze_lineage(self):
        old_parent, old_aplus = make_package()
        delta_parent = copy.deepcopy(old_parent)
        delta_aplus = copy.deepcopy(old_aplus)
        delta_parent["enriched_content_handoff"]["status"] = "RECONCILIATION_REQUIRED"
        reseal_parent(delta_parent)
        delta_aplus["component_result"].update({
            "status": "DELTA_REQUIRED", "gap_atom_ids": ["ATOM-1"],
            "open_delta_request_ids": ["DELTA-1"],
        })
        delta_aplus["coverage_summary"].update({"p0_atoms_pass": 0, "gap_atom_ids": ["ATOM-1"]})
        delta_aplus["delta_evidence_requests"] = [{
            "id": "DELTA-1", "question": "Confirm quantity.",
            "affected_requirement_ids": ["REQ-1"], "affected_atom_ids": ["ATOM-1"],
            "affected_fact_ids": [], "affected_claim_ids": [], "affected_module_ids": [],
            "handoff_lineage": frozen_lineage(delta_aplus), "status": "OPEN",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "receipts.jsonl"
            controlled_coordinate(delta_parent, delta_aplus, ledger_path, record=True)
            new_parent, new_aplus = make_package(
                semantic_revision=2,
                predecessor_handoff=old_aplus["enriched_content_handoff"],
                refreeze_reason="Claimed refreeze without a SUPERSEDED predecessor.",
            )
            new_parent["enriched_content_handoff"]["status"] = "FROZEN"
            new_parent["enriched_content_handoff"]["lineage_registry"][0]["status"] = "FROZEN"
            reseal_parent(new_parent)
            new_aplus["enriched_content_handoff"] = copy.deepcopy(new_parent["enriched_content_handoff"])
            new_aplus["workflow_context"]["accepted_handoff_snapshot_id"] = (
                new_parent["enriched_content_handoff"]["snapshot_id"]
            )
            result = controlled_coordinate(
                new_parent, new_aplus, ledger_path, record=False, require_existing=True,
            )
            self.assertFalse(result["ok"])
            self.assertTrue(any("PKG-RECEIPT-017" in row for row in result["errors"]), result["errors"])

    def test_ledger_partial_line_is_structured_exit_two_and_never_repaired(self):
        coordinator = HERE / "validate_listing_package.py"
        frozen_path = HERE / "integration_fixtures" / "listing-v1.1-delegated-handoff-pass.json"
        child_path = (
            HERE.parent.parent / "aplus" / "scripts" /
            "fixtures" / "aplus-v1.3-embedded-pass.json"
        )
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "receipts.jsonl"
            ledger_path.write_bytes(b'{"contract_version":')
            before = ledger_path.read_bytes()
            completed = subprocess.run(
                [
                    sys.executable, str(coordinator), str(frozen_path), str(child_path),
                    "--receipt-ledger", str(ledger_path),
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["package_result"], "INFRA_ERROR")
            self.assertTrue(any("PKG-LEDGER-001" in row for row in result["errors"]))
            self.assertEqual(ledger_path.read_bytes(), before)

    def test_ledger_validates_genesis_to_head_not_only_claimed_pass(self):
        fixture = HERE / "integration_fixtures" / "listing-coordination-pass-ledger.jsonl"
        lines = [json.loads(row) for row in fixture.read_text(encoding="utf-8").splitlines()]
        lines[0]["issued_at_basis"] = "2026-08-28T02:00:01Z"
        lines[0]["receipt_id"] = canonical_receipt_id(lines[0])
        lines[0]["receipt_sha256"] = canonical_receipt_hash(lines[0])
        payload = (
            "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in lines)
            + "\n"
        ).encode("utf-8")
        with self.assertRaises(LedgerError) as raised:
            parse_ledger_bytes(payload)
        self.assertIn("PKG-RECEIPT-016", str(raised.exception))

    def test_no_record_does_not_create_ledger_and_concurrent_record_has_one_winner(self):
        coordinator = HERE / "validate_listing_package.py"
        frozen_path = HERE / "integration_fixtures" / "listing-v1.1-delegated-handoff-pass.json"
        child_path = (
            HERE.parent.parent / "aplus" / "scripts" /
            "fixtures" / "aplus-v1.3-embedded-pass.json"
        )
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "receipts.jsonl"
            preview = subprocess.run(
                [
                    sys.executable, str(coordinator), str(frozen_path), str(child_path),
                    "--receipt-ledger", str(ledger_path),
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(preview.returncode, 1)
            self.assertFalse(ledger_path.exists())
            self.assertFalse(json.loads(preview.stdout)["local_evidence_write"]["performed"])

            command = [
                sys.executable, str(coordinator), str(frozen_path), str(child_path),
                "--receipt-ledger", str(ledger_path), "--record-receipt",
            ]
            processes = [
                subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for _ in range(2)
            ]
            completed = [process.communicate(timeout=30) + (process.returncode,) for process in processes]
            self.assertEqual(sorted(row[2] for row in completed), [1, 2], completed)
            self.assertEqual(load_receipt_ledger(ledger_path, allow_missing=False)["entry_count"], 1)
            loser = json.loads(next(row[0] for row in completed if row[2] == 2))
            self.assertTrue(any("PKG-RECEIPT-016" in row for row in loser["errors"]), loser)

    def test_controlled_ledger_rejects_nonbundled_validator_identity(self):
        coordinator = HERE / "validate_listing_package.py"
        frozen_path = HERE / "integration_fixtures" / "listing-v1.1-delegated-handoff-pass.json"
        child_path = (
            HERE.parent.parent / "aplus" / "scripts" /
            "fixtures" / "aplus-v1.3-embedded-pass.json"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_validator = root / "validator.py"
            fake_validator.write_text(
                "import json\nprint(json.dumps({'ok': True, 'schema_valid': True, "
                "'structural_valid': True, 'result_level': 'COMPONENT_PASS', 'errors': []}))\n",
                encoding="utf-8",
            )
            ledger_path = root / "receipts.jsonl"
            completed = subprocess.run(
                [
                    sys.executable, str(coordinator), str(frozen_path), str(child_path),
                    "--receipt-ledger", str(ledger_path), "--record-receipt",
                    "--parent-validator", str(fake_validator),
                    "--aplus-validator", str(fake_validator),
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout)
            self.assertTrue(any("PKG-LEDGER-002" in row for row in result["errors"]), result)
            self.assertFalse(ledger_path.exists())

    def test_result_received_requires_exact_receipt_and_delta_cannot_be_erased(self):
        parent, aplus = make_package()
        parent_result, aplus_result = validation_results(
            parent=parent, aplus=aplus,
        )
        parent_result["parent_bundle_sha256"] = canonical_parent_hash(parent)
        missing = validate_listing_package(
            parent, aplus,
            parent_validation=parent_result,
            aplus_validation=aplus_result,
        )
        self.assertFalse(missing["ok"])
        self.assertTrue(any("PKG-RECEIPT-003" in row for row in missing["errors"]))

        delta_parent = copy.deepcopy(parent)
        delta_aplus = copy.deepcopy(aplus)
        delta_parent["enriched_content_handoff"]["status"] = "RECONCILIATION_REQUIRED"
        reseal_parent(delta_parent)
        delta_aplus["component_result"].update({
            "status": "DELTA_REQUIRED", "gap_atom_ids": ["ATOM-1"],
            "open_delta_request_ids": ["DELTA-1"],
        })
        delta_aplus["coverage_summary"].update({"p0_atoms_pass": 0, "gap_atom_ids": ["ATOM-1"]})
        delta_aplus["delta_evidence_requests"] = [{
            "id": "DELTA-1", "question": "Confirm quantity.",
            "affected_requirement_ids": ["REQ-1"], "affected_atom_ids": ["ATOM-1"],
            "affected_fact_ids": [], "affected_claim_ids": [], "affected_module_ids": [],
            "handoff_lineage": frozen_lineage(delta_aplus), "status": "OPEN",
        }]
        delta = coordinate(delta_parent, delta_aplus, auto_ack=False)
        self.assertEqual(delta["package_result"], "DELTA_REQUIRED")
        self.assertEqual(delta["coordination_receipt"]["result"], "DELTA_REQUIRED")

        erased = coordinate(
            parent, aplus,
            prior_receipt=delta["coordination_receipt"], auto_ack=False,
        )
        self.assertFalse(erased["ok"], erased)
        self.assertTrue(any("PKG-RECEIPT-004" in row for row in erased["errors"]), erased["errors"])

    def test_refreeze_receipt_chain_is_content_addressed_and_deterministic(self):
        old_parent, old_aplus = make_package()
        delta_receipt = delta_receipt_for_pair(old_parent, old_aplus)
        new_parent, new_aplus = make_package(
            semantic_revision=2,
            predecessor_handoff=old_aplus["enriched_content_handoff"],
            refreeze_reason="DELTA evidence resolved by the parent.",
        )
        frozen_parent = copy.deepcopy(new_parent)
        frozen_parent["enriched_content_handoff"]["status"] = "FROZEN"
        missing = coordinate(frozen_parent, new_aplus, auto_ack=False)
        self.assertFalse(missing["ok"])
        self.assertTrue(any("PKG-RECEIPT-010" in row for row in missing["errors"]))

        first = coordinate(
            frozen_parent, new_aplus,
            prior_receipt=delta_receipt, auto_ack=False,
        )
        second = coordinate(
            frozen_parent, new_aplus,
            prior_receipt=delta_receipt, auto_ack=False,
        )
        self.assertEqual(first["package_result"], "AWAITING_RESULT_ACK")
        self.assertEqual(first["coordination_receipt"], second["coordination_receipt"])
        awaiting = first["coordination_receipt"]
        self.assertEqual(awaiting["previous_receipt_hash"], delta_receipt["receipt_sha256"])

        passed = coordinate(
            new_parent, new_aplus,
            prior_receipt=awaiting, auto_ack=False,
        )
        self.assertFalse(passed["ok"])
        self.assertEqual(passed["package_result"], "PASS_CANDIDATE")
        self.assertEqual(passed["coordination_receipt"]["result"], "PASS")
        self.assertEqual(
            passed["coordination_receipt"]["previous_receipt_hash"],
            awaiting["receipt_sha256"],
        )

        tampered = copy.deepcopy(awaiting)
        tampered["previous_receipt_hash"] = "sha256:" + "9" * 64
        tampered["receipt_sha256"] = canonical_receipt_hash(tampered)
        rejected = coordinate(new_parent, new_aplus, prior_receipt=tampered, auto_ack=False)
        self.assertFalse(rejected["ok"])
        self.assertTrue(any("PKG-RECEIPT-" in row for row in rejected["errors"]))

    def test_component_reports_must_bind_exact_full_inputs(self):
        parent, aplus = make_package()
        parent_result, aplus_result = validation_results()
        result = validate_listing_package(
            parent, aplus,
            parent_validation=parent_result,
            aplus_validation=aplus_result,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-VALIDATOR-005" in row for row in result["errors"]))
        self.assertTrue(any("PKG-VALIDATOR-006" in row for row in result["errors"]))

    def test_forward_handoff_ready_frozen_to_component_pass_to_package_pass_no_cycle(self):
        parent, aplus = make_package()
        parent["enriched_content_handoff"]["status"] = "FROZEN"
        reseal_parent(parent)
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "receipts.jsonl"
            frozen = controlled_coordinate(parent, aplus, ledger_path, record=True)
            self.assertTrue(frozen["structural_valid"], frozen["errors"])
            self.assertFalse(frozen["ok"])
            self.assertEqual(frozen["package_result"], "AWAITING_RESULT_ACK")
            self.assertTrue(frozen["local_evidence_write"]["performed"])

            frozen_hash = parent["enriched_content_handoff"]["parent_bundle_sha256"]
            parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
            reseal_parent(parent)
            received = controlled_coordinate(parent, aplus, ledger_path, record=True)
            self.assertEqual(parent["enriched_content_handoff"]["parent_bundle_sha256"], frozen_hash)
            self.assertTrue(received["ok"], received["errors"])
            self.assertEqual(received["package_result"], "PASS")
            self.assertEqual(received["ledger"]["entry_count"], 2)
            self.assertFalse(received["publication_boundary"]["publication_authorized"])

    def test_forward_delta_reconciliation_supersede_and_refreeze(self):
        parent, aplus = make_package()
        parent["enriched_content_handoff"]["status"] = "RECONCILIATION_REQUIRED"
        reseal_parent(parent)
        aplus["component_result"].update({
            "status": "DELTA_REQUIRED",
            "gap_atom_ids": ["ATOM-1"],
            "open_delta_request_ids": ["DELTA-1"],
        })
        aplus["coverage_summary"].update({"p0_atoms_pass": 0, "gap_atom_ids": ["ATOM-1"]})
        aplus["delta_evidence_requests"] = [{
            "id": "DELTA-1",
            "question": "Confirm included quantity.",
            "affected_requirement_ids": ["REQ-1"],
            "affected_atom_ids": ["ATOM-1"],
            "affected_fact_ids": [],
            "affected_claim_ids": [],
            "affected_module_ids": [],
            "handoff_lineage": frozen_lineage(aplus),
            "status": "OPEN",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "receipts.jsonl"
            reconciliation = controlled_coordinate(parent, aplus, ledger_path, record=True)
            self.assertTrue(reconciliation["structural_valid"], reconciliation["errors"])
            self.assertEqual(reconciliation["package_result"], "DELTA_REQUIRED")
            self.assertFalse(reconciliation["ok"])

            parent["enriched_content_handoff"]["status"] = "SUPERSEDED"
            reseal_parent(parent)
            superseded = coordinate(parent, aplus)
            self.assertFalse(superseded["structural_valid"])
            self.assertTrue(any("PKG-HANDOFF-006" in row for row in superseded["errors"]))

            new_parent, new_aplus = make_package(
                semantic_revision=2,
                predecessor_handoff=aplus["enriched_content_handoff"],
                refreeze_reason="DELTA-1 resolved with new parent evidence",
            )
            new_parent["enriched_content_handoff"]["status"] = "FROZEN"
            reseal_parent(new_parent)
            refrozen = controlled_coordinate(new_parent, new_aplus, ledger_path, record=True)
            self.assertEqual(refrozen["package_result"], "AWAITING_RESULT_ACK")
            self.assertTrue(refrozen["structural_valid"], refrozen["errors"])
            new_parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
            reseal_parent(new_parent)
            received = controlled_coordinate(new_parent, new_aplus, ledger_path, record=True)
            self.assertTrue(received["ok"], received["errors"])
            self.assertEqual(received["ledger"]["entry_count"], 3)

    def test_refreeze_rejects_stale_child_snapshot_and_accepts_new_snapshot(self):
        old_parent, old_aplus = make_package()
        delta_receipt = delta_receipt_for_pair(old_parent, old_aplus)
        new_parent, new_aplus = make_package(
            semantic_revision=2,
            predecessor_handoff=old_aplus["enriched_content_handoff"],
            refreeze_reason="A parent evidence delta was resolved",
        )
        stale = coordinate(new_parent, old_aplus)
        self.assertFalse(stale["ok"])
        self.assertTrue(any("PKG-HANDOFF-007" in row or "PKG-HANDOFF-009" in row for row in stale["errors"]))
        fresh = coordinate(new_parent, new_aplus, prior_receipt=delta_receipt)
        self.assertFalse(fresh["ok"])
        self.assertEqual(fresh["package_result"], "PASS_CANDIDATE")

    def test_snapshot_acceptance_cannot_predate_freeze(self):
        parent, aplus = make_package()
        aplus["workflow_context"]["accepted_at"] = "2026-08-27T23:00:00Z"
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-HANDOFF-011" in row for row in result["errors"]))

    def test_content_addressed_snapshot_and_semantic_revision_lineage_are_required(self):
        initial_parent, initial_aplus = make_package()
        initial_snapshot = initial_aplus["enriched_content_handoff"]["snapshot_id"]
        self.assertRegex(initial_snapshot, r"^HO-[0-9a-f]{20}$")

        invalid_revision_parent, invalid_revision_aplus = make_package(semantic_revision=2)
        invalid_revision = coordinate(invalid_revision_parent, invalid_revision_aplus)
        self.assertFalse(invalid_revision["ok"])
        self.assertTrue(any("PKG-LINEAGE-006" in row for row in invalid_revision["errors"]))

        invalid_initial_parent, invalid_initial_aplus = make_package(
            semantic_revision=1,
            predecessor_snapshot_id=initial_snapshot,
            refreeze_reason="Not valid on revision one",
        )
        invalid_initial = coordinate(invalid_initial_parent, invalid_initial_aplus)
        self.assertFalse(invalid_initial["ok"])
        self.assertTrue(any("PKG-LINEAGE-005" in row for row in invalid_initial["errors"]))

        refrozen_parent, refrozen_aplus = make_package(
            semantic_revision=2,
            predecessor_handoff=initial_aplus["enriched_content_handoff"],
            refreeze_reason="Resolved the parent evidence gap",
        )
        delta_receipt = delta_receipt_for_pair(initial_parent, initial_aplus)
        refrozen = coordinate(refrozen_parent, refrozen_aplus, prior_receipt=delta_receipt)
        self.assertFalse(refrozen["ok"])
        self.assertEqual(refrozen["package_result"], "PASS_CANDIDATE")
        self.assertNotEqual(
            refrozen_aplus["enriched_content_handoff"]["snapshot_id"], initial_snapshot,
        )

    def test_coordinator_rejects_random_jump_unsuperseded_and_wrong_successor(self):
        _, previous_aplus = make_package()

        def refrozen_pair() -> tuple[dict, dict]:
            return make_package(
                semantic_revision=2,
                predecessor_handoff=previous_aplus["enriched_content_handoff"],
                refreeze_reason="Parent evidence delta resolved.",
            )

        cases = {
            "random_predecessor": lambda h: h.update({"predecessor_snapshot_id": "HO-" + "9" * 20}),
            "revision_jump": lambda h: h.update({"semantic_revision": 3}),
            "not_superseded": lambda h: h["lineage_registry"][0].update({"status": "FROZEN"}),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                parent, aplus = refrozen_pair()
                parent["enriched_content_handoff"]["status"] = "FROZEN"
                mutate(parent["enriched_content_handoff"])
                reseal_parent(parent)
                aplus["enriched_content_handoff"] = copy.deepcopy(parent["enriched_content_handoff"])
                aplus["workflow_context"]["accepted_handoff_snapshot_id"] = (
                    parent["enriched_content_handoff"]["snapshot_id"]
                )
                parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
                result = coordinate(parent, aplus)
                self.assertFalse(result["ok"], result)
                self.assertTrue(any("PKG-LINEAGE-007" in row for row in result["errors"]), result["errors"])

        parent, aplus = refrozen_pair()
        parent["enriched_content_handoff"]["status"] = "FROZEN"
        reseal_parent(parent)
        handoff = parent["enriched_content_handoff"]
        handoff["lineage_registry"][0]["successor_snapshot_id"] = "HO-" + "8" * 20
        handoff["lineage_registry"][0]["record_checksum"] = canonical_lineage_record_hash(
            handoff["lineage_registry"][0]
        )
        handoff["checksum"] = canonical_handoff_hash(handoff)
        handoff["parent_bundle_sha256"] = canonical_parent_hash(parent)
        aplus["enriched_content_handoff"] = copy.deepcopy(handoff)
        aplus["workflow_context"]["accepted_handoff_snapshot_id"] = handoff["snapshot_id"]
        handoff["status"] = "RESULT_RECEIVED"
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"], result)
        self.assertTrue(any("PKG-LINEAGE-007" in row for row in result["errors"]), result["errors"])

    def test_arbitrary_snapshot_id_cannot_be_resealed_into_a_valid_package(self):
        parent, aplus = make_package()
        fake_id = "HO-00000000000000000000"
        parent_handoff = parent["enriched_content_handoff"]
        parent_handoff["snapshot_id"] = fake_id
        parent_handoff["checksum"] = canonical_handoff_hash(parent_handoff)
        parent_handoff["parent_bundle_sha256"] = canonical_parent_hash(parent)
        child_handoff = copy.deepcopy(parent_handoff)
        child_handoff["status"] = "FROZEN"
        child_handoff["checksum"] = canonical_handoff_hash(child_handoff)
        aplus["enriched_content_handoff"] = child_handoff
        aplus["workflow_context"]["accepted_handoff_snapshot_id"] = fake_id
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-LINEAGE-003" in row for row in result["errors"]), result["errors"])

    def test_runtime_multi_locale_allows_only_locale_expression_text(self):
        members = [
            group_member("en-US", "Includes one black item."),
            group_member("fr-FR", "Comprend un article noir."),
        ]
        result = validate_listing_locale_group(group_manifest(), members)
        self.assertFalse(result["ok"])
        self.assertTrue(result["semantic_match"], result["errors"])
        self.assertEqual(result["package_result"], "SEMANTIC_MATCH")
        self.assertEqual(result["locales"], ["en-US", "fr-FR"])
        self.assertEqual(len(result["member_results"]), 2)
        self.assertFalse(result["publication_boundary"]["publication_authorized"])
        family = result["assertion_families"][0]
        self.assertNotEqual(
            family["localized_text_sha256_by_locale"]["en-US"],
            family["localized_text_sha256_by_locale"]["fr-FR"],
        )
        self.assertEqual(
            family["semantic_projection_sha256_by_locale"]["en-US"],
            family["semantic_projection_sha256_by_locale"]["fr-FR"],
        )

    def test_runtime_multi_locale_rejects_canonical_truth_drift(self):
        en = group_member("en-US")
        fr = group_member("fr-FR")
        fr["parent"]["canonical_assertions"][0]["statement"] = "Includes two black items."
        fr["aplus"]["canonical_assertions"][0]["statement"] = "Includes two black items."
        refreeze_pair(fr["parent"], fr["aplus"])
        fr["pair_result"] = coordinate(fr["parent"], fr["aplus"])
        self.assertEqual(fr["pair_result"]["package_result"], "PASS_CANDIDATE")
        result = validate_listing_locale_group(group_manifest(), [en, fr])
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-GROUP-ASSERT-001" in row for row in result["errors"]))

    def test_runtime_multi_locale_rejects_fact_or_claim_content_drift(self):
        for section, field, code in (
            ("facts", "statement", "PKG-GROUP-FACT-002"),
            ("claims", "text", "PKG-GROUP-CLAIM-002"),
        ):
            with self.subTest(section=section):
                en = group_member("en-US")
                fr = group_member("fr-FR")
                fr["parent"][section][0][field] = "Changed semantic content."
                fr["aplus"][section][0][field] = "Changed semantic content."
                refreeze_pair(fr["parent"], fr["aplus"])
                fr["pair_result"] = coordinate(fr["parent"], fr["aplus"])
                self.assertEqual(fr["pair_result"]["package_result"], "PASS_CANDIDATE")
                result = validate_listing_locale_group(group_manifest(), [en, fr])
                self.assertFalse(result["ok"])
                self.assertTrue(any(code in row for row in result["errors"]), result["errors"])

    def test_runtime_multi_locale_rejects_fact_claim_id_drift(self):
        en = group_member("en-US")
        fr = group_member("fr-FR")
        fr["parent"] = replace_exact_scalar(fr["parent"], "F-1", "F-2")
        fr["parent"] = replace_exact_scalar(fr["parent"], "C-1", "C-2")
        fr["aplus"] = replace_exact_scalar(fr["aplus"], "F-1", "F-2")
        fr["aplus"] = replace_exact_scalar(fr["aplus"], "C-1", "C-2")
        refreeze_pair(fr["parent"], fr["aplus"])
        fr["pair_result"] = coordinate(fr["parent"], fr["aplus"])
        self.assertEqual(fr["pair_result"]["package_result"], "PASS_CANDIDATE")
        result = validate_listing_locale_group(group_manifest(), [en, fr])
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-GROUP-FACT-001" in row for row in result["errors"]))
        self.assertTrue(any("PKG-GROUP-CLAIM-001" in row for row in result["errors"]))

    def test_runtime_multi_locale_rejects_nonlocale_scope_or_variant_drift(self):
        en = group_member("en-US")
        fr = group_member("fr-FR")
        fr["parent"] = replace_exact_scalar(fr["parent"], "M", "L")
        fr["aplus"] = replace_exact_scalar(fr["aplus"], "M", "L")
        refreeze_pair(fr["parent"], fr["aplus"])
        fr["pair_result"] = coordinate(fr["parent"], fr["aplus"])
        self.assertEqual(fr["pair_result"]["package_result"], "PASS_CANDIDATE")
        result = validate_listing_locale_group(group_manifest(), [en, fr])
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-GROUP-SCOPE-001" in row for row in result["errors"]))

    def test_group_manifest_is_closed_and_requires_two_unique_locales(self):
        manifest = group_manifest()
        manifest["semantic_hash"] = "sha256:self-attested"
        invalid = validate_group_manifest(manifest)
        self.assertFalse(invalid["valid"])
        self.assertTrue(any("PKG-GROUP-MANIFEST-001" in row for row in invalid["errors"]))
        for locales in (("en-US",), ("en-US", "en-US")):
            with self.subTest(locales=locales):
                invalid = validate_group_manifest(group_manifest(locales))
                self.assertFalse(invalid["valid"])
                self.assertTrue(any("PKG-GROUP-MANIFEST-00" in row for row in invalid["errors"]))
        missing_locale = group_manifest()
        missing_locale["members"][1]["locale"] = ""
        invalid = validate_group_manifest(missing_locale)
        self.assertFalse(invalid["valid"])
        self.assertTrue(any("PKG-GROUP-MANIFEST-006" in row for row in invalid["errors"]))

    def test_pure_group_layer_never_trusts_pair_result_or_grants_group_pass(self):
        en = group_member("en-US")
        fr = group_member("fr-FR")
        fr["pair_result"] = {
            "ok": False,
            "structural_valid": False,
            "component_valid": False,
            "package_result": "INVALID",
        }
        result = validate_listing_locale_group(group_manifest(), [en, fr])
        self.assertFalse(result["ok"])
        self.assertTrue(result["semantic_match"], result["errors"])
        self.assertEqual(result["package_result"], "SEMANTIC_MATCH")
        self.assertNotEqual(result["package_result"], "GROUP_PASS")
        fr["pair_result"] = {
            "ok": True, "structural_valid": True,
            "component_valid": True, "package_result": "PASS",
        }
        forged = validate_listing_locale_group(group_manifest(), [en, fr])
        self.assertFalse(forged["ok"])
        self.assertEqual(forged["package_result"], "SEMANTIC_MATCH")

    def test_group_runtime_output_is_deterministic_under_member_reordering(self):
        members = [group_member("fr-FR"), group_member("en-US")]
        first = validate_listing_locale_group(group_manifest(), members)
        second = validate_listing_locale_group(group_manifest(), list(reversed(members)))
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True),
            json.dumps(second, ensure_ascii=False, sort_keys=True),
        )

    def test_forward_backend_accepted_frontend_mismatch_is_not_live_pass(self):
        parent, aplus = make_package()
        parent["live_readback"] = [{
            "child_asin": CHILD,
            "status": "ACCEPTED_BACKEND",
            "live_pass": False,
        }]
        reseal_parent(parent)
        accepted = coordinate(parent, aplus)
        self.assertFalse(accepted["ok"])
        self.assertEqual(accepted["package_result"], "PASS_CANDIDATE")
        self.assertEqual(accepted["publication_boundary"]["live_result"], "BACKEND_ACCEPTED_ONLY")
        self.assertFalse(accepted["publication_boundary"]["live_pass"])
        self.assertFalse(accepted["publication_boundary"]["publication_authorized"])

        parent["live_readback"][0]["status"] = "LIVE_MISMATCH"
        parent["project"]["conclusion"] = "LIVE_PASS"
        reseal_parent(parent)
        mismatch = coordinate(parent, aplus)
        self.assertFalse(mismatch["ok"])
        self.assertTrue(mismatch["structural_valid"])
        self.assertEqual(mismatch["package_result"], "BLOCKED")
        self.assertEqual(mismatch["publication_boundary"]["live_result"], "FRONTEND_MISMATCH")
        self.assertTrue(any("PKG-READBACK-001" in row for row in mismatch["business_blockers"]))

    def test_legacy_contracts_are_rejected_from_current_package_pass(self):
        parent, aplus = make_package()
        parent["schema_version"] = "1.0"
        parent_result, aplus_result = validation_results()
        result = validate_listing_package(
            parent, aplus,
            parent_validation=parent_result,
            aplus_validation=aplus_result,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-VERSION-001" in row for row in result["errors"]))

    def test_frozen_parent_mutation_forces_reconciliation_and_refreeze(self):
        parent, aplus = make_package()
        parent["facts"][0]["statement"] = "Two items are included."
        reseal_parent(parent)
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-HASH-004" in row for row in result["errors"]), result["errors"])

    def test_result_authorization_and_readback_progress_do_not_change_frozen_payload_hash(self):
        parent, _ = make_package()
        frozen_hash = canonical_parent_hash(parent)
        parent["project"].update({
            "target_stage": "LIVE_MATCH",
            "conclusion": "LIVE_PASS",
        })
        parent["publish_authorization"] = {"status": "AUTHORIZED", "authorization_id": "AUTH-1"}
        parent["live_readback"] = [{
            "child_asin": CHILD,
            "status": "LIVE_MATCH",
            "live_pass": True,
        }]
        self.assertEqual(canonical_parent_hash(parent), frozen_hash)
        parent["execution_boundary"] = "authorized_submission"
        self.assertNotEqual(canonical_parent_hash(parent), frozen_hash)
        parent["execution_boundary"] = "read_only"
        parent["canonical_assertions"][0]["statement"] = "Includes two black items."
        self.assertNotEqual(canonical_parent_hash(parent), frozen_hash)

    def test_immutable_handoff_difference_is_rejected(self):
        parent, aplus = make_package()
        aplus["enriched_content_handoff"]["product_type"] = "DIFFERENT"
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-HANDOFF-007" in row for row in result["errors"]))

    def test_whole_page_coverage_cannot_ignore_non_delegated_atom(self):
        parent, aplus = make_package()
        second = {
            "id": "ATOM-2",
            "requirement_id": "REQ-2",
            "marketplace": "US",
            "locale": "en-US",
            "variant_row_id": "V-1",
        }
        parent["decision_denominator_snapshot"]["atoms"].append(second)
        parent["decision_denominator_snapshot"]["requirement_ids"].append("REQ-2")
        parent["decision_denominator_snapshot"]["checksum"] = hash_block(parent["decision_denominator_snapshot"])
        parent["enriched_content_handoff"]["decision_denominator_hash"] = hash_block(parent["decision_denominator_snapshot"])
        aplus["enriched_content_handoff"]["decision_denominator_hash"] = hash_block(parent["decision_denominator_snapshot"])
        reseal_parent(parent)
        aplus["enriched_content_handoff"]["checksum"] = canonical_handoff_hash(aplus["enriched_content_handoff"])
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"])
        self.assertEqual(result["coverage"]["gap_atom_ids"], ["ATOM-2"])

    def test_early_disclosure_resolves_same_atom_real_visible_parent_answer(self):
        parent, aplus = make_package()
        add_valid_early_disclosure(parent, aplus)
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"])
        self.assertEqual(result["package_result"], "PASS_CANDIDATE")
        self.assertEqual(result["coverage"]["parent_pass_atom_ids"], ["ATOM-1"])

    def test_early_disclosure_rejects_fake_cross_requirement_nonvisible_and_absent_text(self):
        mutations = (
            lambda parent: parent["decision_map"]["requirements"][0].update({"upstream_primary_carrier_ref": "FAKE"}),
            lambda parent: parent["surface_assignments"][0].update({"requirement_id": "REQ-OTHER"}),
            lambda parent: parent["field_resolutions"][0].update({"visibility": "BACKEND_ONLY"}),
            lambda parent: parent["field_candidates"][0].update({"value": "Different copy."}),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                parent, aplus = make_package()
                add_valid_early_disclosure(parent, aplus)
                mutate(parent)
                parent_requirement = copy.deepcopy(parent["decision_map"]["requirements"][0])
                parent["enriched_content_handoff"]["decision_requirements"] = [parent_requirement]
                aplus["decision_map"]["requirements"] = [copy.deepcopy(parent_requirement)]
                parent["enriched_content_handoff"]["status"] = "FROZEN"
                reseal_parent(parent)
                aplus["enriched_content_handoff"] = copy.deepcopy(parent["enriched_content_handoff"])
                parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
                reseal_parent(parent)
                result = coordinate(parent, aplus)
                self.assertFalse(result["ok"])
                self.assertTrue(any("PKG-EARLY-" in row for row in result["errors"]), result["errors"])

    def test_coordinator_rejects_three_prohibited_p0_primary_field_classes(self):
        cases = (
            ("COMMUNITY_QA", "customer_questions"),
            ("ALT_METADATA", "image_alt_text"),
            ("BACKEND_TERMS", "generic_keyword"),
        )
        for semantic_role, canonical_key in cases:
            with self.subTest(semantic_role=semantic_role):
                parent, aplus = make_package()
                add_valid_early_disclosure(parent, aplus)
                parent["field_resolutions"][0].update({
                    "semantic_role": semantic_role,
                    "canonical_key": canonical_key,
                })
                parent["field_candidates"][0]["semantic_role"] = semantic_role
                parent["enriched_content_handoff"]["status"] = "FROZEN"
                reseal_parent(parent)
                aplus["enriched_content_handoff"] = copy.deepcopy(parent["enriched_content_handoff"])
                aplus["workflow_context"]["accepted_handoff_snapshot_id"] = (
                    parent["enriched_content_handoff"]["snapshot_id"]
                )
                parent["enriched_content_handoff"]["status"] = "RESULT_RECEIVED"
                reseal_parent(parent)
                result = coordinate(parent, aplus)
                self.assertFalse(result["ok"], result)
                self.assertTrue(
                    any("PKG-EARLY-003" in row for row in result["errors"]),
                    result["errors"],
                )

    def test_canonical_assertion_rejects_scope_variant_and_locale_evidence_drift(self):
        mutations = (
            lambda assertion: assertion["application_scope"].update({"colors": ["White"]}),
            lambda assertion: assertion["application_scope"].update({"marketplace": "CA"}),
            lambda assertion: assertion["application_scope"].update({"locale": "fr-CA"}),
            lambda assertion: assertion["application_scope"].update({"other_variants": {"finish": ["Glossy"]}}),
            lambda assertion: assertion.update({"variant_row_ids": ["V-OTHER"]}),
            lambda assertion: assertion["locale_expressions"][0].update({"fact_ids": []}),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                parent, aplus = make_package()
                mutate(aplus["canonical_assertions"][0])
                result = coordinate(parent, aplus)
                self.assertFalse(result["ok"])
                self.assertTrue(any("PKG-ASSERT-00" in row for row in result["errors"]), result["errors"])

    def test_delta_requires_parent_reconciliation_and_exact_gap_mapping(self):
        parent, aplus = make_package()
        parent["enriched_content_handoff"]["status"] = "FROZEN"
        reseal_parent(parent)
        aplus["component_result"].update({
            "status": "DELTA_REQUIRED",
            "gap_atom_ids": ["ATOM-1"],
            "open_delta_request_ids": ["DELTA-1"],
        })
        aplus["coverage_summary"].update({"p0_atoms_pass": 0, "gap_atom_ids": ["ATOM-1"]})
        aplus["delta_evidence_requests"] = [{
            "id": "DELTA-1",
            "question": "Confirm quantity.",
            "affected_requirement_ids": ["REQ-OTHER"],
            "affected_atom_ids": ["ATOM-1"],
            "affected_fact_ids": [],
            "affected_claim_ids": [],
            "affected_module_ids": [],
            "handoff_lineage": frozen_lineage(aplus),
            "status": "OPEN",
        }]
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"])
        self.assertTrue(any("PKG-LINEAGE-001" in row for row in result["errors"]))
        self.assertTrue(any("PKG-DELTA-006" in row for row in result["errors"]))
        self.assertTrue(any("PKG-DELTA-010" in row for row in result["errors"]))

    def test_read_only_component_never_grants_publication_authority(self):
        parent, aplus = make_package()
        result = coordinate(parent, aplus)
        self.assertFalse(result["ok"])
        self.assertEqual(result["package_result"], "PASS_CANDIDATE")
        self.assertFalse(result["publication_boundary"]["coordinator_grants_authority"])
        self.assertFalse(result["publication_boundary"]["publication_authorized"])

    def test_validator_cli_consumes_json_without_importing_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle.json"
            script = root / "validator.py"
            bundle.write_text("{}", encoding="utf-8")
            script.write_text(
                "import json\nprint(json.dumps({'ok': True, 'errors': []}))\n",
                encoding="utf-8",
            )
            result = run_validator_cli(script, bundle, "fixture")
            self.assertTrue(result["ok"])
            self.assertEqual(result["validator_exit_code"], 0)

    def test_real_component_cli_entrypoints_return_deterministic_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent_path = root / "parent.json"
            aplus_path = root / "aplus.json"
            parent_path.write_text('{"schema_version":"1.1"}', encoding="utf-8")
            aplus_path.write_text('{"schema_version":"1.3"}', encoding="utf-8")
            parent_result = run_validator_cli(DEFAULT_PARENT_VALIDATOR, parent_path, "parent")
            aplus_result = run_validator_cli(DEFAULT_APLUS_VALIDATOR, aplus_path, "aplus")
            self.assertFalse(parent_result["ok"])
            self.assertFalse(aplus_result["ok"])
            self.assertEqual(parent_result["validator_exit_code"], 1)
            self.assertEqual(aplus_result["validator_exit_code"], 1)
            self.assertIsInstance(parent_result.get("errors"), list)
            self.assertIsInstance(aplus_result.get("errors"), list)

    def test_real_coordinator_cli_malformed_json_is_deterministic_infra_error(self):
        coordinator = HERE / "validate_listing_package.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent_path = root / "parent.json"
            aplus_path = root / "aplus.json"
            parent_path.write_text("{not-json", encoding="utf-8")
            aplus_path.write_text("{}", encoding="utf-8")
            outputs = []
            for _ in range(2):
                completed = subprocess.run(
                    [sys.executable, str(coordinator), str(parent_path), str(aplus_path)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 2)
                result = json.loads(completed.stdout)
                self.assertEqual(result["package_result"], "INFRA_ERROR")
                self.assertFalse(result["publication_boundary"]["publication_authorized"])
                outputs.append(completed.stdout)
            self.assertEqual(outputs[0], outputs[1])

    def test_pair_cli_requires_controlled_ledger_for_terminal_pass(self):
        coordinator = HERE / "validate_listing_package.py"
        frozen_path = HERE / "integration_fixtures" / "listing-v1.1-delegated-handoff-pass.json"
        received_path = HERE / "integration_fixtures" / "listing-v1.1-result-received-pass.json"
        child_path = (
            HERE.parent.parent / "aplus" / "scripts" /
            "fixtures" / "aplus-v1.3-embedded-pass.json"
        )
        frozen_run = subprocess.run(
            [sys.executable, str(coordinator), str(frozen_path), str(child_path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(frozen_run.returncode, 1, frozen_run.stdout + frozen_run.stderr)
        frozen_result = json.loads(frozen_run.stdout)
        self.assertEqual(frozen_result["package_result"], "AWAITING_RESULT_ACK")
        receipt = frozen_result["coordination_receipt"]

        no_receipt = subprocess.run(
            [sys.executable, str(coordinator), str(received_path), str(child_path)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(no_receipt.returncode, 1)
        self.assertTrue(any(
            "PKG-RECEIPT-003" in row for row in json.loads(no_receipt.stdout)["errors"]
        ))

        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "awaiting.json"
            ledger_path = Path(tmp) / "receipts.jsonl"
            receipt_path.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
            )
            legacy_run = subprocess.run(
                [
                    sys.executable, str(coordinator), str(received_path), str(child_path),
                    "--prior-receipt", str(receipt_path),
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(legacy_run.returncode, 1, legacy_run.stdout + legacy_run.stderr)
            legacy_result = json.loads(legacy_run.stdout)
            self.assertFalse(legacy_result["ok"])
            self.assertEqual(legacy_result["package_result"], "TRANSITION_LEDGER_REQUIRED")

            frozen_record = subprocess.run(
                [
                    sys.executable, str(coordinator), str(frozen_path), str(child_path),
                    "--receipt-ledger", str(ledger_path), "--record-receipt",
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(frozen_record.returncode, 1, frozen_record.stdout + frozen_record.stderr)
            self.assertTrue(json.loads(frozen_record.stdout)["local_evidence_write"]["performed"])
            received_run = subprocess.run(
                [
                    sys.executable, str(coordinator), str(received_path), str(child_path),
                    "--receipt-ledger", str(ledger_path), "--record-receipt",
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(received_run.returncode, 0, received_run.stdout + received_run.stderr)
            received_result = json.loads(received_run.stdout)
            self.assertTrue(received_result["ok"], received_result["errors"])
            self.assertEqual(received_result["package_result"], "PASS")
            self.assertTrue(received_result["local_evidence_write"]["performed"])

            confirm = subprocess.run(
                [
                    sys.executable, str(coordinator), str(received_path), str(child_path),
                    "--receipt-ledger", str(ledger_path),
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(confirm.returncode, 0, confirm.stdout + confirm.stderr)
            self.assertFalse(json.loads(confirm.stdout)["local_evidence_write"]["performed"])

            repeated = subprocess.run(
                [
                    sys.executable, str(coordinator), str(received_path), str(child_path),
                    "--receipt-ledger", str(ledger_path), "--record-receipt",
                ],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(repeated.returncode, 2, repeated.stdout + repeated.stderr)
            repeated_result = json.loads(repeated.stdout)
            self.assertTrue(any(
                "PKG-RECEIPT-016" in row for row in repeated_result["errors"]
            ))
            self.assertTrue(repeated_result["local_evidence_write"]["requested"])
            self.assertFalse(repeated_result["local_evidence_write"]["performed"])

    def test_real_group_cli_runs_both_component_validators_and_pair_per_locale(self):
        coordinator = HERE / "validate_listing_package.py"
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_real_group(Path(tmp))
            outputs = []
            for seed in ("1", "947"):
                environment = dict(os.environ)
                environment["PYTHONHASHSEED"] = seed
                completed = subprocess.run(
                    [sys.executable, str(coordinator), "--group-manifest", str(manifest_path)],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=environment,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                result = json.loads(completed.stdout)
                self.assertTrue(result["ok"], result["errors"])
                self.assertEqual(result["package_result"], "GROUP_PASS")
                self.assertEqual(len(result["member_results"]), 2)
                self.assertTrue(all(
                    row["parent_full_input_sha256"].startswith("sha256:")
                    and row["aplus_full_input_sha256"].startswith("sha256:")
                    and row["terminal_receipt_sha256"].startswith("sha256:")
                    for row in result["member_results"]
                ))
                self.assertFalse(result["publication_boundary"]["publication_authorized"])
                outputs.append(completed.stdout)
            self.assertEqual(outputs[0], outputs[1])

    def test_controlled_group_rejects_stale_or_cross_member_receipt(self):
        coordinator = HERE / "validate_listing_package.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = write_real_group(root)
            en_ledger = (root / "en-US-receipts.jsonl").read_bytes()
            (root / "fr-FR-receipts.jsonl").write_bytes(en_ledger)
            completed = subprocess.run(
                [sys.executable, str(coordinator), "--group-manifest", str(manifest_path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout)
            self.assertFalse(result["ok"])
            self.assertEqual(result["package_result"], "GROUP_MEMBER_BLOCKED")
            self.assertTrue(any("PKG-GROUP-MEMBER-001" in row for row in result["errors"]))

    def test_real_group_cli_rejects_resolved_file_alias_before_validation(self):
        coordinator = HERE / "validate_listing_package.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = write_real_group(root)
            alias_path = root / "fr-parent-alias.json"
            alias_path.symlink_to(root / "en-US-parent.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["members"][1]["parent_bundle"] = alias_path.name
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(coordinator), "--group-manifest", str(manifest_path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["package_result"], "GROUP_INVALID")
            self.assertTrue(any("PKG-GROUP-MANIFEST-008" in row for row in result["errors"]))
            self.assertFalse(result["publication_boundary"]["publication_authorized"])

    def test_group_cli_mode_is_exclusive_and_json_deterministic(self):
        coordinator = HERE / "validate_listing_package.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = write_real_group(root)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(coordinator),
                    str(root / "en-US-parent.json"),
                    str(root / "en-US-aplus.json"),
                    "--group-manifest",
                    str(manifest_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            result = json.loads(completed.stdout)
            self.assertEqual(result["package_result"], "INFRA_ERROR")
            self.assertFalse(result["publication_boundary"]["publication_authorized"])

    def test_real_coordinator_cli_rejects_stale_child_snapshot(self):
        coordinator = HERE / "validate_listing_package.py"
        parent_path = HERE / "integration_fixtures" / "listing-v1.1-result-received-pass.json"
        child_fixture = (
            HERE.parent.parent / "aplus" / "scripts" /
            "fixtures" / "aplus-v1.3-embedded-pass.json"
        )
        with tempfile.TemporaryDirectory() as tmp:
            stale_path = Path(tmp) / "stale-aplus.json"
            stale = json.loads(child_fixture.read_text(encoding="utf-8"))
            stale["workflow_context"]["accepted_handoff_snapshot_id"] = "HO-00000000000000000000"
            stale_path.write_text(
                json.dumps(stale, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(coordinator), str(parent_path), str(stale_path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            result = json.loads(completed.stdout)
            self.assertFalse(result["ok"])
            self.assertEqual(result["package_result"], "INVALID")
            self.assertFalse(result["publication_boundary"]["publication_authorized"])
            self.assertTrue(any("PKG-HANDOFF-008" in row for row in result["errors"]))

    def test_component_validators_do_not_import_each_other(self):
        parent_source = DEFAULT_PARENT_VALIDATOR.read_text(encoding="utf-8")
        child_source = DEFAULT_APLUS_VALIDATOR.read_text(encoding="utf-8")
        self.assertNotIn("spec_from_file_location", parent_source)
        self.assertNotIn("amazon-premium-aplus-planner", parent_source)
        self.assertNotIn("spec_from_file_location", child_source)
        self.assertNotIn("amazon-listing-catalog-workflow", child_source)

    def test_public_integration_fixtures_prove_frozen_then_result_received_without_cycle(self):
        frozen_path = HERE / "integration_fixtures" / "listing-v1.1-delegated-handoff-pass.json"
        received_path = HERE / "integration_fixtures" / "listing-v1.1-result-received-pass.json"
        receipt_path = HERE / "integration_fixtures" / "listing-coordination-awaiting-receipt.json"
        ledger_path = HERE / "integration_fixtures" / "listing-coordination-pass-ledger.jsonl"
        child_path = (
            HERE.parent.parent / "aplus" / "scripts" /
            "fixtures" / "aplus-v1.3-embedded-pass.json"
        )
        child = json.loads(child_path.read_text(encoding="utf-8"))
        child_validation = run_validator_cli(DEFAULT_APLUS_VALIDATOR, child_path, "aplus")
        self.assertTrue(child_validation["ok"], child_validation.get("errors"))

        frozen_parent = json.loads(frozen_path.read_text(encoding="utf-8"))
        frozen_validation = run_validator_cli(DEFAULT_PARENT_VALIDATOR, frozen_path, "parent")
        frozen = validate_listing_package(
            frozen_parent,
            child,
            parent_validation=frozen_validation,
            aplus_validation=child_validation,
        )
        self.assertTrue(frozen["structural_valid"], frozen["errors"])
        self.assertEqual(frozen["package_result"], "AWAITING_RESULT_ACK")
        receipt_fixture = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["coordination_receipt"], receipt_fixture)

        received_parent = json.loads(received_path.read_text(encoding="utf-8"))
        received_validation = run_validator_cli(DEFAULT_PARENT_VALIDATOR, received_path, "parent")
        received = validate_listing_package(
            received_parent,
            child,
            parent_validation=received_validation,
            aplus_validation=child_validation,
            prior_receipt=receipt_fixture,
        )
        self.assertFalse(received["ok"])
        self.assertEqual(received["package_result"], "PASS_CANDIDATE")

        controlled = validate_listing_package_with_ledger(
            received_parent,
            child,
            parent_validation=received_validation,
            aplus_validation=child_validation,
            receipt_ledger=ledger_path,
            record_receipt=False,
            parent_validator=DEFAULT_PARENT_VALIDATOR,
            aplus_validator=DEFAULT_APLUS_VALIDATOR,
            require_existing_ledger=True,
        )
        self.assertTrue(controlled["ok"], controlled["errors"])
        self.assertEqual(controlled["package_result"], "PASS")
        self.assertEqual(controlled["ledger"]["entry_count"], 2)
        self.assertFalse(controlled["publication_boundary"]["publication_authorized"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
