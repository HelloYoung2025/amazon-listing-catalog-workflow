#!/usr/bin/env python3
"""Run legacy and v1.1 forward-test groups in fresh Python processes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT_TEST = HERE / "test_validate_listing_bundle.py"
PARENT_V11_TEST = HERE / "test_validate_listing_bundle_v11.py"
PACKAGE_TEST = HERE / "test_validate_listing_package.py"
SKILLS_ROOT = HERE.parent.parent
APLUS_TEST = SKILLS_ROOT / "aplus" / "scripts" / "test_validate_bundle.py"

GROUPS = [
    ("FT-01", "HX02 multi-pack apparel", PARENT_TEST, [
        "ListingBundleValidatorTests.test_forward_hx02_pack_fact_cannot_expand",
        "ListingBundleValidatorTests.test_forward_hx02_corrected_child_pack_scope_passes",
    ]),
    ("FT-02", "multi-spec pet camera", PARENT_TEST, [
        "ListingBundleValidatorTests.test_forward_pet_camera_compatibility_cannot_expand",
        "ListingBundleValidatorTests.test_forward_pet_camera_corrected_child_compatibility_scope_passes",
    ]),
    ("FT-03", "simple kitchen item", PARENT_TEST, ["ListingBundleValidatorTests.test_forward_simple_kitchen_item_needs_no_optional_carrier"]),
    ("FT-04", "short-complete versus long-missing-P0 A+", APLUS_TEST, [
        "BundleValidatorTests.test_v12_short_complete_copy_passes_without_500_word_rule",
        "BundleValidatorTests.test_v12_static_visual_or_alt_cannot_satisfy_p0",
        "BundleValidatorTests.test_v12_long_copy_missing_p0_fails",
        "BundleValidatorTests.test_v12_long_copy_cannot_fake_coverage_when_p0_is_image_or_alt_only",
    ]),
    ("FT-05", "v1.1 backward compatibility", APLUS_TEST, [
        "BundleValidatorTests.test_v11_remains_compatible_without_native_coverage_claim",
        "BundleValidatorTests.test_v11_cannot_carry_v12_blocks",
        "BundleValidatorTests.test_v11_validation_does_not_mutate_input",
    ]),
    ("FT-06", "backend accepted/frontend mismatch", PARENT_TEST, ["ListingBundleValidatorTests.test_forward_backend_accepted_frontend_mismatch_blocks_live"]),
    ("FT-07", "v1.1 evidence, Socratic and PTD closure", PARENT_V11_TEST, [
        "ListingV11Tests.test_evidence_strength_rule_freshness_and_conflict_are_fail_closed",
        "ListingV11Tests.test_unknown_p0_response_requires_evidence_action",
        "ListingV11Tests.test_seller_central_metadata_and_ptd_conditional",
    ]),
    ("FT-08", "Item Highlights real-field capability", PARENT_V11_TEST, [
        "ListingV11Tests.test_item_highlights_is_first_class_and_fake_subtitle_is_rejected",
    ]),
    ("FT-09", "atomic variant coverage and coordinator boundary", PARENT_V11_TEST, [
        "ListingV11Tests.test_duplicate_final_and_partial_variant_coverage_fail",
        "ListingV11Tests.test_result_received_needs_coordinator_and_project_pass_cannot_outrun",
    ]),
    ("FT-10", "legacy migration and deterministic read-only report", PARENT_V11_TEST, [
        "ListingV11Tests.test_migration_invalidates_legacy_authority_handoff_and_live",
        "ListingV11Tests.test_renderer_is_deterministic_read_only_and_escapes_untrusted_text",
    ]),
    ("FT-11", "v1.1 HX02 real 2-pack/3-pack atom coverage", PARENT_V11_TEST, [
        "ListingV11Tests.test_v11_hx02_two_and_three_pack_use_real_variant_atoms_only",
    ]),
    ("FT-12", "P1 category adapters including regulated beauty", PARENT_V11_TEST, [
        "ListingV11Tests.test_category_adapter_closed_set_and_no_ptd_override",
    ]),
    ("FT-13", "controlled receipt ledger from HANDOFF_READY to terminal package PASS", PACKAGE_TEST, [
        "ListingPackageCoordinatorTests.test_forward_handoff_ready_frozen_to_component_pass_to_package_pass_no_cycle",
        "ListingPackageCoordinatorTests.test_pair_cli_requires_controlled_ledger_for_terminal_pass",
        "ListingPackageCoordinatorTests.test_pure_api_never_returns_terminal_pass",
        "ListingPackageCoordinatorTests.test_no_record_does_not_create_ledger_and_concurrent_record_has_one_winner",
        "ListingPackageCoordinatorTests.test_ledger_validates_genesis_to_head_not_only_claimed_pass",
        "ListingPackageCoordinatorTests.test_controlled_ledger_rejects_nonbundled_validator_identity",
        "ListingPackageCoordinatorTests.test_result_received_requires_exact_receipt_and_delta_cannot_be_erased",
        "ListingPackageCoordinatorTests.test_component_reports_must_bind_exact_full_inputs",
    ]),
    ("FT-14", "monotonic DELTA reconciliation, stale replay rejection, and semantic refreeze", PACKAGE_TEST, [
        "ListingPackageCoordinatorTests.test_forward_delta_reconciliation_supersede_and_refreeze",
        "ListingPackageCoordinatorTests.test_refreeze_receipt_chain_is_content_addressed_and_deterministic",
        "ListingPackageCoordinatorTests.test_ledger_head_blocks_old_await_replay_after_delta",
        "ListingPackageCoordinatorTests.test_delta_head_requires_exact_superseded_refreeze_lineage",
        "ListingPackageCoordinatorTests.test_ledger_partial_line_is_structured_exit_two_and_never_repaired",
    ]),
    ("FT-15", "multi-locale GROUP_PASS requires each exact current PASS ledger head", PACKAGE_TEST, [
        "ListingPackageCoordinatorTests.test_real_group_cli_runs_both_component_validators_and_pair_per_locale",
        "ListingPackageCoordinatorTests.test_controlled_group_rejects_stale_or_cross_member_receipt",
        "ListingPackageCoordinatorTests.test_pure_group_layer_never_trusts_pair_result_or_grants_group_pass",
        "ListingPackageCoordinatorTests.test_runtime_multi_locale_rejects_canonical_truth_drift",
        "ListingPackageCoordinatorTests.test_runtime_multi_locale_rejects_fact_or_claim_content_drift",
        "ListingPackageCoordinatorTests.test_runtime_multi_locale_rejects_nonlocale_scope_or_variant_drift",
    ]),
    ("FT-16", "backend accepted frontend mismatch is not LIVE_PASS", PACKAGE_TEST, [
        "ListingPackageCoordinatorTests.test_forward_backend_accepted_frontend_mismatch_is_not_live_pass",
    ]),
]


def main() -> int:
    results = []
    for test_id, scenario, script, tests in GROUPS:
        command = [sys.executable, str(script), *tests]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        results.append({
            "id": test_id,
            "scenario": scenario,
            "isolated_process": True,
            "passed": completed.returncode == 0,
            "exit_code": completed.returncode,
            "tests": tests,
            "output": (completed.stdout + completed.stderr).strip(),
        })
    payload = {
        "ok": all(row["passed"] for row in results),
        "groups_passed": sum(1 for row in results if row["passed"]),
        "groups_total": len(results),
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
