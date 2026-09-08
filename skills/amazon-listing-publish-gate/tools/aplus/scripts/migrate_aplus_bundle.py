#!/usr/bin/env python3
"""Migrate an A+ bundle v1.1/v1.2 to a non-escalating v1.3 candidate.

The input is never overwritten. Migration preserves source/fact evidence but
discards legacy consumer-facing candidates, invalidates historical
authorization/live/handoff state, and leaves all new discovery,
denominator, and assertion gates unclosed.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from aplus_entry_domain import migration_path_issue
from aplus_io import read_json_document


TARGET_VERSION = "1.3"


def load_template() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "assets" / "aplus-project-bundle-template.json"
    return json.loads(path.read_text(encoding="utf-8"))


def reset_publication_state(bundle: dict[str, Any]) -> list[str]:
    changes: list[str] = []
    project = bundle.setdefault("project", {})
    if project.get("conclusion") != "NO_VALID_CONCLUSION":
        changes.append("project.conclusion invalidated")
    project["conclusion"] = "NO_VALID_CONCLUSION"
    project["write_scope"] = "read_only"
    if project.get("status") == "SCAFFOLD" or not str(project.get("status", "")).strip():
        project["status"] = "MIGRATED_NEEDS_REVIEW"
        changes.append("template/scaffold status converted to MIGRATED_NEEDS_REVIEW")
    for row in bundle.get("variants", []):
        if isinstance(row, dict) and row.get("status") in {"APPLIED", "LIVE_PASS"}:
            row["status"] = "VERIFIED"
            changes.append(f"variant {row.get('id') or row.get('child_asin')} live state invalidated")
    for section in ("modules", "assets", "carriers", "decision_answer_units"):
        for row in bundle.get(section, []):
            if isinstance(row, dict) and row.get("content_status") in {"APPROVED", "PUBLISHED"}:
                row["content_status"] = "FINAL_CANDIDATE"
                changes.append(f"{section} {row.get('id', '')} publication state invalidated")
    bundle["publish_authorization"] = copy.deepcopy(load_template()["publish_authorization"])
    bundle["baseline"] = copy.deepcopy(load_template()["baseline"])
    bundle["change_set"] = []
    bundle["rollback"] = copy.deepcopy(load_template()["rollback"])
    bundle["live_readback"] = []
    for gate in bundle.get("gates", []):
        if isinstance(gate, dict):
            gate["status"] = "NOT_STARTED"
            gate["evidence"] = []
    return changes


def migrate(payload: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("input bundle must be a JSON object")
    source_version = str(payload.get("schema_version", ""))
    if source_version not in {"1.1", "1.2"}:
        raise ValueError("migration accepts only A+ Bundle 1.1 or 1.2")
    template = load_template()
    migrated = copy.deepcopy(payload)
    unrecognized_root_keys = sorted(set(migrated) - set(template))
    added_root_keys: list[str] = []
    for key, value in template.items():
        if key not in migrated:
            migrated[key] = copy.deepcopy(value)
            added_root_keys.append(key)
    changes = reset_publication_state(migrated)
    migrated["schema_version"] = TARGET_VERSION

    discarded_candidate_counts = {
        section: len(migrated.get(section, []))
        for section in ("modules", "assets", "carriers", "decision_answer_units", "canonical_assertions")
        if isinstance(migrated.get(section), list)
    }
    for section in ("modules", "assets", "carriers", "decision_answer_units", "canonical_assertions"):
        migrated[section] = []
    if any(discarded_candidate_counts.values()):
        changes.append(
            "legacy consumer-facing candidates discarded until governed discovery stages close"
        )

    workflow = copy.deepcopy(migrated.get("workflow_context", template["workflow_context"]))
    source_mode = workflow.get("mode", "standalone")
    workflow["execution_boundary"] = "read_only"
    workflow["accepted_handoff_snapshot_id"] = ""
    workflow["accepted_at"] = ""
    workflow["accepted_by"] = ""
    migrated["workflow_context"] = workflow

    handoff = copy.deepcopy(migrated.get("enriched_content_handoff", template["enriched_content_handoff"]))
    handoff["contract_version"] = "1.1"
    handoff["maximum_output"] = "strategy_dependency_only"
    handoff["status"] = "RECONCILIATION_REQUIRED" if source_mode == "embedded" else "NOT_APPLICABLE"
    handoff["parent_bundle_sha256"] = ""
    handoff["discovery_closure_hash"] = ""
    handoff["ptd_inventory_hash"] = ""
    handoff["decision_denominator_hash"] = ""
    handoff["canonical_assertion_ids"] = []
    handoff["requirement_atoms"] = []
    handoff.setdefault("predecessor_snapshot_id", "")
    handoff["semantic_revision"] = 0
    handoff.setdefault("refreeze_reason", "")
    handoff["lineage_registry"] = []
    handoff["checksum"] = ""
    migrated["enriched_content_handoff"] = handoff
    if source_mode == "embedded":
        changes.append("legacy embedded handoff requires parent v1.1 refreeze")

    migrated["discovery"] = copy.deepcopy(template["discovery"])
    conditional = migrated.setdefault("project", {}).setdefault("conditional_draft", {})
    conditional["status"] = "BLOCKED"
    conditional["maximum_work"] = "strategy_dependency_only"
    conditional["blocked_outputs"] = sorted(set(conditional.get("blocked_outputs", [])) | {
        "consumer_final_copy", "final_product_imagery", "module_wireframes", "image_alt_concepts", "publishing",
    })
    migrated["category_adapter"] = copy.deepcopy(template["category_adapter"])
    if source_mode == "embedded":
        migrated["discovery"]["mode"] = "parent_bound"
        migrated["discovery"]["closure"].update({
            "status": "NOT_REQUIRED_WITH_REASON",
            "reason": "Legacy parent discovery must be rebound by a new frozen handoff.",
        })
        migrated["category_adapter"]["status"] = "PARENT_BOUND"
    migrated["decision_denominator_snapshot"] = copy.deepcopy(template["decision_denominator_snapshot"])
    legacy_decision_map = migrated.get("decision_map") if isinstance(migrated.get("decision_map"), dict) else {}
    legacy_positioning = migrated.get("positioning") if isinstance(migrated.get("positioning"), dict) else {}
    migrated["decision_map"] = copy.deepcopy(template["decision_map"])
    migrated["decision_map"]["owner"] = str(legacy_decision_map.get("owner", "")).strip() or "Unassigned"
    migrated["positioning"] = copy.deepcopy(template["positioning"])
    migrated["positioning"]["owner"] = str(legacy_positioning.get("owner", "")).strip() or "Unassigned"
    if legacy_decision_map.get("status") == "SUPPORTED" or legacy_positioning.get("status") == "SUPPORTED":
        changes.append("legacy decision map and positioning reset pending governed Round 2 and One-Bet closure")
    migrated["canonical_assertions"] = []
    migrated["coverage_summary"] = copy.deepcopy(template["coverage_summary"])
    migrated["component_result"] = copy.deepcopy(template["component_result"])

    variant_ids: set[str] = set()
    for index, row in enumerate(migrated.get("variants", []), start=1):
        if not isinstance(row, dict):
            continue
        candidate = str(row.get("id", "")).strip() or f"MIGRATED-VARIANT-{index}"
        while candidate in variant_ids:
            candidate += "-DUP"
        row["id"] = candidate
        variant_ids.add(candidate)
    for row in migrated.get("assets", []):
        if isinstance(row, dict):
            row.setdefault("variant_row_ids", [])
            row.setdefault("canonical_assertion_ids", [])
    for row in migrated.get("carriers", []):
        if isinstance(row, dict):
            row.setdefault("variant_row_ids", [])
            row.setdefault("canonical_assertion_ids", [])
    for row in migrated.get("decision_answer_units", []):
        if isinstance(row, dict):
            row.setdefault("requirement_atom_id", "")
            row.setdefault("variant_row_id", "")
            row.setdefault("canonical_assertion_ids", [])
    for row in migrated.get("facts", []):
        if isinstance(row, dict):
            row["fact_class"] = "UNCLASSIFIED"
    for row in migrated.get("delta_evidence_requests", []):
        if isinstance(row, dict):
            row.setdefault("affected_atom_ids", [])
            row.setdefault("gap_type", "PARENT_EVIDENCE" if source_mode == "embedded" else "STANDALONE_EVIDENCE")
            row.setdefault("handoff_lineage", copy.deepcopy(template["record_templates"]["delta_evidence_request"]["handoff_lineage"]))
    migrated["record_templates"] = copy.deepcopy(template["record_templates"])

    report = {
        "migration": "aplus",
        "source_version": source_version,
        "target_version": TARGET_VERSION,
        "input_overwritten": False,
        "authority_escalated": False,
        "live_state_preserved": False,
        "handoff_requires_refreeze": source_mode == "embedded",
        "new_contract_ready": False,
        "added_root_keys": added_root_keys,
        "unrecognized_root_keys_preserved": unrecognized_root_keys,
        "discarded_candidate_counts": discarded_candidate_counts,
        "changes": changes,
        "required_next_actions": [
            "Complete or bind discovery closure.",
            "Freeze a real-variant decision denominator.",
            "Create evidence-bound canonical assertions and atom answers.",
            "Run validate_bundle.py before rendering or package coordination.",
        ],
    }
    return migrated, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    source = args.bundle.expanduser().resolve()
    output = (args.output or source.with_name(source.stem + ".v1.3.json")).expanduser().resolve()
    report_path = (args.report or source.with_name(source.stem + ".v1.3.migration.json")).expanduser().resolve()
    collision_issue = migration_path_issue(source, output, report_path)
    if collision_issue:
        print(json.dumps({"ok": False, "error": collision_issue}, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    if output.exists() or report_path.exists():
        print(json.dumps({"ok": False, "error": "migration refuses to overwrite an existing output or report"}, ensure_ascii=False, indent=2))
        return 2
    if not output.parent.is_dir() or not report_path.parent.is_dir():
        print(json.dumps({"ok": False, "error": "output and report parent directories must already exist"}, ensure_ascii=False, indent=2))
        return 2
    payload, io_issue = read_json_document(source)
    if io_issue:
        print(json.dumps({"ok": False, "error": io_issue}, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    try:
        migrated, report = migrate(payload)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    try:
        output.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"ok": True, "output": str(output), "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
