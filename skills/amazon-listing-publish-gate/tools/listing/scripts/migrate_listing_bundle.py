#!/usr/bin/env python3
"""Migrate Listing Bundle v1.0 to an explicitly unclosed v1.1 candidate.

Migration never overwrites the input, never carries authorization/LIVE status,
and never upgrades legacy facts, handoffs, or gates to a v1.1 PASS.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "listing-project-bundle-template.json"


def _scope(value: Any) -> dict[str, list[str]]:
    source = value if isinstance(value, dict) else {}
    return {
        key: list(source.get(key, [])) if isinstance(source.get(key, []), list) else []
        for key in ("parent_asins", "child_asins", "packs", "colors", "sizes")
    }


def _source(row: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    source_type = str(row.get("type", "legacy_source"))
    level = "E2" if source_type in {"authorized_backend", "public_frontend", "frontend_readback"} else "E1"
    return {
        "id": row.get("id", ""),
        "type": source_type,
        "locator": row.get("locator", "legacy:unresolved"),
        "authority": row.get("authority", "legacy_unresolved"),
        "evidence_level": level,
        "seller_scope": scope.get("seller_scope", ""),
        "marketplace": scope.get("marketplace", ""),
        "locale": scope.get("locale", ""),
        "child_asins": list(scope.get("intended_child_asins", [])),
        "application_scope": {
            "parent_asins": list(scope.get("parent_asins", [])),
            "child_asins": list(scope.get("intended_child_asins", [])),
            "packs": list(scope.get("packs", [])),
            "colors": list(scope.get("colors", [])),
            "sizes": list(scope.get("sizes", [])),
        },
        "retrieved_at": row.get("retrieved_at") or "1970-01-01T00:00:00Z",
        "status": "STALE",
        "proves": [],
        "cannot_prove": ["v1.1 evidence strength", "current PTD completeness", "live publication"],
    }


def migrate_bundle(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if source.get("schema_version") != "1.0":
        raise ValueError("only Listing Bundle v1.0 can be migrated")
    target = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    old_project = source.get("project") if isinstance(source.get("project"), dict) else {}
    old_scope = source.get("scope") if isinstance(source.get("scope"), dict) else {}
    target["project"].update({
        "project_id": old_project.get("project_id", ""),
        "title": old_project.get("title", ""),
        "mode": old_project.get("mode", "plan"),
        "status": "MIGRATED_NEEDS_REVIEW",
        "snapshot_date": old_project.get("snapshot_date", ""),
        "target_stage": "AUTHORITY",
        "conclusion": "NO_VALID_CONCLUSION",
        "owner": old_project.get("owner", ""),
        "notes": "Migrated from v1.0; all v1.1 discovery, PTD, assertion, authorization, handoff, and LIVE gates require fresh closure.",
    })
    target["execution_boundary"] = "read_only"
    target["scope"] = copy.deepcopy(old_scope)
    target["sources"] = [_source(row, old_scope) for row in source.get("sources", []) if isinstance(row, dict)]
    source_ids = {row.get("id") for row in target["sources"]}

    old_context = source.get("catalog_context") if isinstance(source.get("catalog_context"), dict) else {}
    target["catalog_context"] = {
        "identity_status": "NOT_STARTED",
        "identifier": old_context.get("identifier", ""),
        "identifier_type": old_context.get("identifier_type", ""),
        "parentage_level": old_context.get("parentage_level", ""),
        "product_type": old_context.get("product_type", ""),
        "source_ids": [item for item in old_context.get("source_ids", []) if item in source_ids],
        "owner": old_context.get("owner", ""),
    }
    target["rule_snapshots"] = []
    for row in source.get("rule_snapshots", []):
        if not isinstance(row, dict):
            continue
        migrated = copy.deepcopy(row)
        migrated["status"] = "STALE"
        migrated["source_ids"] = [item for item in row.get("source_ids", []) if item in source_ids]
        target["rule_snapshots"].append(migrated)
    rule_ids = {row.get("id") for row in target["rule_snapshots"]}

    target["field_resolutions"] = []
    for row in source.get("field_resolutions", []):
        if not isinstance(row, dict):
            continue
        migrated = copy.deepcopy(row)
        migrated["status"] = "HOLD"
        migrated["rule_snapshot_ids"] = [item for item in row.get("rule_snapshot_ids", []) if item in rule_ids]
        migrated.setdefault("max_characters", None)
        target["field_resolutions"].append(migrated)

    target["facts"] = []
    for row in source.get("facts", []):
        if not isinstance(row, dict):
            continue
        refs = [item for item in row.get("source_ids", []) if item in source_ids]
        target["facts"].append({
            **copy.deepcopy(row),
            "source_ids": refs,
            "proving_source_ids": [],
            "verification_status": "UNVERIFIED",
            "content_status": "HOLD",
            "evidence_level": "E0",
            "can_prove": [],
            "cannot_prove": ["v1.1 publication claim"],
            "allowed_expression": "HOLD pending fresh evidence closure",
            "prohibited_inferences": ["legacy PASS implies v1.1 proof"],
            "refresh_trigger": "complete v1.1 evidence and Socratic closure",
        })
    fact_ids = {row.get("id") for row in target["facts"]}
    target["claims"] = []
    for row in source.get("claims", []):
        if not isinstance(row, dict):
            continue
        refs = [item for item in row.get("source_ids", []) if item in source_ids]
        target["claims"].append({
            **copy.deepcopy(row),
            "source_ids": refs,
            "proving_source_ids": [],
            "fact_ids": [item for item in row.get("fact_ids", []) if item in fact_ids],
            "support_status": "UNSUPPORTED",
            "content_status": "HOLD",
            "evidence_level": "E0",
            "can_prove": [],
            "cannot_prove": ["v1.1 consumer claim"],
            "allowed_expression": "HOLD pending fresh evidence closure",
            "prohibited_inferences": ["legacy PASS implies v1.1 support"],
            "refresh_trigger": "complete v1.1 evidence and Socratic closure",
        })
    target["conflicts"] = copy.deepcopy(source.get("conflicts", []))
    for row in target["conflicts"]:
        if isinstance(row, dict) and row.get("status") == "ACCEPTED_RISK":
            row["status"] = "OPEN"
    target["variant_topology"] = copy.deepcopy(source.get("variant_topology", []))
    for row in target["variant_topology"]:
        if isinstance(row, dict):
            row["status"] = "UNVERIFIED"

    target["discovery"]["status"] = "MIGRATION_REQUIRED"
    target["discovery"]["evidence_pass"] = {
        "status": "PARTIAL",
        "source_ids": sorted(item for item in source_ids if item),
        "observations": [],
    }
    target["discovery"]["stage_gates"] = []
    target["market_research"]["status"] = "NOT_STARTED"
    target["ptd_field_inventory"].update({
        "status": "PARTIAL",
        "product_type": old_context.get("product_type", ""),
        "rule_snapshot_ids": sorted(item for item in rule_ids if item),
        "evidence_source_ids": [],
        "declared_field_count": len(target["field_resolutions"]),
        "expected_fields": [],
        "checksum": "",
    })
    old_map = source.get("decision_map") if isinstance(source.get("decision_map"), dict) else {"requirements": []}
    target["decision_map"] = {"status": "MIGRATED_NEEDS_REFREEZE", "requirements": copy.deepcopy(old_map.get("requirements", []))}
    discarded_candidate_counts = {
        key: len([row for row in source.get(key, []) if isinstance(row, dict)])
        for key in (
            "canonical_assertions", "decision_answer_units", "surface_assignments",
            "field_candidates", "semantic_consistency_matrix",
        )
    }
    for key in discarded_candidate_counts:
        target[key] = []

    old_handoff = source.get("enriched_content_handoff") if isinstance(source.get("enriched_content_handoff"), dict) else {}
    target["enriched_content_handoff"]["status"] = "DRAFT" if old_handoff.get("status") != "NOT_APPLICABLE" else "NOT_APPLICABLE"
    target["enriched_content_handoff"]["requested_content_types"] = list(old_handoff.get("requested_content_types", []))
    target["publish_authorization"]["status"] = "NOT_AUTHORIZED"
    target["baseline"] = []
    target["change_set"] = []
    target["rollback"] = []
    target["live_readback"] = []

    report = {
        "migration": "Listing Bundle 1.0 -> 1.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project_id": old_project.get("project_id", ""),
        "source_conclusion_invalidated": old_project.get("conclusion", ""),
        "authorization_invalidated": bool(source.get("publish_authorization", {}).get("status") == "AUTHORIZED"),
        "handoff_invalidated": old_handoff.get("status", "NOT_APPLICABLE"),
        "live_rows_discarded": len(source.get("live_readback", [])),
        "change_rows_discarded": len(source.get("change_set", [])),
        "preclosure_candidate_rows_discarded": discarded_candidate_counts,
        "required_fresh_closures": [
            "identity", "current rules/PTD", "evidence strength", "Socratic discovery",
            "decision denominator", "canonical assertions", "answer units", "handoff",
        ],
    }
    return target, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Listing Bundle v1.0 to unclosed v1.1")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    report_path = (args.report or args.output.with_suffix(args.output.suffix + ".migration-report.json")).resolve()
    if input_path == output_path:
        parser.error("migration output must not overwrite the input")
    if output_path == report_path:
        parser.error("migration output and report must be different files")
    if output_path.exists() or report_path.exists():
        parser.error("migration output/report already exists")
    try:
        source = json.loads(input_path.read_text(encoding="utf-8"))
        migrated, report = migrate_bundle(source)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({
            "ok": False,
            "errors": [f"[LST-MIGRATION-IO-001] {exc}"],
            "output": str(output_path),
            "report": str(report_path),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "report": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
