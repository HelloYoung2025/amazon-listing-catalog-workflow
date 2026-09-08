"""Executable working-draft/formal-Bundle boundaries, not marketing-quality tests.

Use the existing current-contract fixture and real validator. Working prototypes
are deliberately outside the Bundle; these tests do not grade agent interviews,
copy quality, or the truth of an arbitrary human-readable prototype.
"""
import copy
import unittest

from test_validate_listing_bundle_v11 import valid_bundle
from validate_listing_bundle_v11 import validate_listing_bundle_v11


class WorkingDraftBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.bundle = valid_bundle()
        self.baseline = validate_listing_bundle_v11(self.bundle)
        self.assertTrue(self.baseline["ok"], self.baseline["errors"])

    def assert_rejected(self, bundle, error_code):
        before = copy.deepcopy(bundle)
        result = validate_listing_bundle_v11(bundle)
        self.assertFalse(result["ok"], result)
        self.assertNotEqual(result["derived_gates"]["package"], "PASS")
        self.assertTrue(
            any(error_code in item for item in result["errors"]), result["errors"]
        )
        self.assertEqual(bundle, before, "Validation must not repair evidence or answers.")
        return result

    def test_working_prototype_stays_outside_schema_and_publication_authority(self):
        workspace = {
            "formal_bundle": self.bundle,
            "working_prototype": {
                "status": "NOT FOR UPLOAD",
                "headline": "A second spatula for the busy cook",
                "unresolved_claim": "Two spatulas may be included; packaging check pending.",
            },
        }
        before = copy.deepcopy(workspace)
        result = validate_listing_bundle_v11(workspace["formal_bundle"])
        self.assertEqual(result, self.baseline)
        self.assertEqual(workspace, before)
        self.assertEqual(self.bundle["schema_version"], "1.1")
        self.assertEqual(self.bundle["enriched_content_handoff"]["contract_version"], "1.1")
        self.assertEqual(self.bundle["execution_boundary"], "read_only")
        self.assertEqual(self.bundle["publish_authorization"]["status"], "NOT_AUTHORIZED")
        self.assertEqual(result["derived_gates"]["publication"], "NOT_RUN")

        promoted = copy.deepcopy(self.bundle)
        promoted["working_prototype"] = workspace["working_prototype"]
        rejected = self.assert_rejected(promoted, "[L11-ROOT-002]")
        self.assertFalse(rejected["schema_valid"])

    def test_blocked_proving_source_cannot_be_replaced_by_existing_copy(self):
        source = next(row for row in self.bundle["sources"] if row["id"] == "SRC-PRODUCT")
        source["status"] = "BLOCKED"
        result = self.assert_rejected(self.bundle, "[L11-FACT-005]")
        self.assertNotEqual(result["derived_gates"]["evidence"], "PASS")
        self.assertEqual(self.bundle["facts"][0]["proving_source_ids"], ["SRC-PRODUCT"])

    def test_open_product_conflict_blocks_formal_package(self):
        self.bundle["conflicts"] = [{
            "id": "CONFLICT-QUANTITY",
            "affected_fact_ids": ["F-1"],
            "affected_claim_ids": ["C-1"],
            "status": "OPEN",
        }]
        self.assert_rejected(self.bundle, "[L11-ANSWER-013]")
        self.assertEqual(self.bundle["conflicts"][0]["status"], "OPEN")

    def test_unknown_skip_is_not_autofilled_from_existing_copy(self):
        response = self.bundle["discovery"]["responses"][0]
        response.update(classification="UNKNOWN_SKIP", status="SKIP", answer="")
        self.assert_rejected(self.bundle, "[L11-DISCOVERY-010]")
        self.assertEqual(response["answer"], "")
        self.assertEqual(response["classification"], "UNKNOWN_SKIP")
        self.assertEqual(self.bundle["discovery"]["evidence_actions"], [])

    def test_scoped_evidence_does_not_transfer_between_variants(self):
        for dimension, other_value in (
            ("child_asins", "B0OTHERCH1"), ("packs", "2PK"), ("colors", "White")
        ):
            with self.subTest(dimension=dimension):
                bundle = copy.deepcopy(self.bundle)
                source = next(row for row in bundle["sources"] if row["id"] == "SRC-PRODUCT")
                source["application_scope"][dimension] = [other_value]
                if dimension == "child_asins":
                    source["child_asins"] = [other_value]
                self.assert_rejected(bundle, "[L11-FACT-005]")

    def test_typed_strategy_payloads_stay_required(self):
        for record_id, field, error_code in (
            ("D-3", "current_choice", "[L11-DISCOVERY-045]"),
            ("D-4", "reversibility_test", "[L11-DISCOVERY-047]"),
        ):
            with self.subTest(record_id=record_id, field=field):
                bundle = copy.deepcopy(self.bundle)
                record = next(row for row in bundle["discovery"]["distillations"]
                              if row["id"] == record_id)
                record["payload"].pop(field)
                self.assert_rejected(bundle, error_code)

    def test_open_one_bet_does_not_admit_formal_candidates(self):
        one_bet = next(row for row in self.bundle["discovery"]["stage_gates"]
                       if row["stage"] == "ONE_BET")
        one_bet.update(status="IN_PROGRESS", result="", record_refs=[], closed_at="")
        self.assert_rejected(self.bundle, "[L11-PHASE-001]")
        self.assertEqual(one_bet["status"], "IN_PROGRESS")
        self.assertEqual(self.bundle["field_candidates"][0]["content_status"], "FINAL")

    def test_item_highlight_limit_uses_current_account_field_resolution(self):
        # Synthetic length stress case; these are fixture limits, not Amazon rules.
        field = self.bundle["field_resolutions"][0]
        field.update(
            semantic_role="ITEM_HIGHLIGHTS", canonical_key="item_highlights",
            ui_label="Item highlights", max_characters=200,
            account_evidence_source_ids=["SRC-SC"],
        )
        candidate = self.bundle["field_candidates"][0]
        candidate.update(
            semantic_role="ITEM_HIGHLIGHTS",
            value=("Includes one black spatula. " * 6).strip(),
        )
        result = validate_listing_bundle_v11(self.bundle)
        self.assertTrue(result["ok"], result["errors"])
        field["max_characters"] = 40
        self.assert_rejected(self.bundle, "[L11-CANDIDATE-006]")
        field["max_characters"] = 200
        field["account_evidence_source_ids"] = []
        self.assert_rejected(self.bundle, "[L11-FIELD-006]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
