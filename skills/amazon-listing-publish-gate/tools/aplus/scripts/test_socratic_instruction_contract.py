"""Executable working-draft/formal-Bundle boundaries, not marketing-quality tests.

Use the existing current-contract fixture and real validator. No instruction
wording is asserted, and no score here represents interview or copy quality.
"""
import copy
import unittest

from test_v13_contract import valid_v13
from validate_bundle import validate_bundle


class WorkingDraftBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.bundle = valid_v13()
        self.baseline = validate_bundle(self.bundle)
        self.assertTrue(self.baseline["ok"], self.baseline["errors"])

    def assert_rejected(self, bundle, error_code):
        before = copy.deepcopy(bundle)
        result = validate_bundle(bundle)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["result_level"], "INVALID")
        self.assertFalse(result["publication_authorized_by_component"])
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
                "headline": "Two devices, one connected routine",
                "unresolved_claim": "A two-device pack is a hypothesis pending evidence.",
            },
        }
        before = copy.deepcopy(workspace)
        result = validate_bundle(workspace["formal_bundle"])
        self.assertEqual(result, self.baseline)
        self.assertEqual(workspace, before)
        self.assertEqual(self.bundle["schema_version"], "1.3")
        self.assertEqual(self.bundle["enriched_content_handoff"]["contract_version"], "1.1")
        self.assertEqual(self.bundle["workflow_context"]["execution_boundary"], "read_only")
        self.assertEqual(self.bundle["publish_authorization"]["status"], "NOT_AUTHORIZED")
        self.assertFalse(result["page_pass_implied"])
        self.assertFalse(result["publication_authorized_by_component"])

        promoted = copy.deepcopy(self.bundle)
        promoted["working_prototype"] = workspace["working_prototype"]
        rejected = self.assert_rejected(promoted, "schema 1.3 has unknown top-level keys")
        self.assertFalse(rejected["structural_valid"])

    def test_blocked_proving_source_cannot_be_replaced_by_existing_copy(self):
        source = next(row for row in self.bundle["sources"] if row["id"] == "SRC-SPEC")
        source.update(fetch_status="blocked", block_reason="Specification unavailable")
        self.assert_rejected(self.bundle, "is not usable")
        self.assertEqual(self.bundle["facts"][0]["proving_source_ids"], ["SRC-SPEC"])

    def test_open_product_conflict_blocks_formal_component(self):
        self.bundle["conflicts"] = [{
            "id": "CONFLICT-QUANTITY",
            "statements": ["One device is included.", "Two devices are included."],
            "source_ids": ["SRC-SPEC"],
            "affected_fact_ids": ["FACT-1"],
            "affected_claim_ids": ["CLAIM-1"],
            "affected_module_ids": ["M01"],
            "affected_asset_ids": [],
            "affected_child_asins": [self.bundle["variants"][0]["child_asin"]],
            "impact": "P0 included quantity may be wrong.",
            "decisive_evidence": "Current packaging specification.",
            "owner": "Product",
            "due_date": "2026-09-05",
            "maximum_work": "strategy_dependency_only",
            "status": "OPEN",
        }]
        self.assert_rejected(self.bundle, "[A13-CONFLICT-001]")
        self.assertEqual(self.bundle["conflicts"][0]["status"], "OPEN")

    def test_unknown_skip_is_not_autofilled_from_existing_copy(self):
        question = self.bundle["discovery"]["interview_rounds"][0]["questions"][0]
        question.update(answer="", response_class="UNKNOWN_SKIP")
        self.assert_rejected(self.bundle, "[A13-DISCOVERY-008]")
        self.assertEqual(question["answer"], "")
        self.assertEqual(question["response_class"], "UNKNOWN_SKIP")
        self.assertEqual(self.bundle["discovery"]["evidence_actions"], [])

    def test_answer_scope_does_not_transfer_between_variants(self):
        for dimension, other_value in (
            ("child_asins", "B0OTHERCH1"), ("packs", "2"), ("colors", "Black")
        ):
            with self.subTest(dimension=dimension):
                bundle = copy.deepcopy(self.bundle)
                bundle["decision_answer_units"][0]["application_scope"][dimension] = [other_value]
                self.assert_rejected(bundle, "[A13-ANSWER-035]")

    def test_typed_strategy_payloads_stay_required(self):
        for record_id, field, error_code in (
            ("D-3", "current_choice", "[A13-STAGE-020]"),
            ("D-4", "reversibility_test", "[A13-STAGE-021]"),
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
        result = self.assert_rejected(self.bundle, "[A13-PHASE-002]")
        self.assertTrue(any("[A13-PHASE-003]" in item for item in result["errors"]))
        self.assertEqual(one_bet["status"], "IN_PROGRESS")
        self.assertEqual(self.bundle["modules"][0]["content_status"], "FINAL_CANDIDATE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
