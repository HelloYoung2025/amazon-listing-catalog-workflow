#!/usr/bin/env python3
"""Pure version, gates, publication, and readback phase for the A+ validator."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

@dataclass(frozen=True)
class GovernanceReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    parent_bundle_verified: bool | None
    version_counts: dict[str, Any]
    gate_map: dict[str, dict[str, Any]]
    experiments: dict[str, dict[str, Any]]


def validate_governance(
    root: dict[str, Any], *, schema_version: str, project: dict[str, Any],
    mode: str, conclusion: str, marketplace: str, locale: str,
    identity_status: str,
    write_scope: str, snapshot_date: str, scope_status: str,
    envelope: dict[str, Any], source_map: dict[str, dict[str, Any]],
    source_scopes: dict[str, dict[str, Any]], fact_map: dict[str, dict[str, Any]],
    fact_scopes: dict[str, dict[str, Any]], claim_map: dict[str, dict[str, Any]],
    claim_scopes: dict[str, dict[str, Any]], conflicts: dict[str, dict[str, Any]],
    module_map: dict[str, dict[str, Any]], module_scopes: dict[str, dict[str, Any]],
    asset_map: dict[str, dict[str, Any]], child_asins: set[str],
    content_ids: set[str], variant_rows: list[dict[str, str]],
    source_path: Path | None, ops: Mapping[str, Any],
) -> GovernanceReport:
    errors: list[str] = []
    warnings: list[str] = []
    validate_v12_contract=ops["validate_v12_contract"]
    validate_v13_contract=ops["validate_v13_contract"]; is_text=ops["is_text"]
    require_list=ops["require_list"]; unique_rows=ops["unique_rows"]
    require_enum=ops["require_enum"]; require_text=ops["require_text"]
    string_set=ops["string_set"]; required_pass_gate_ids=ops["required_pass_gate_ids"]
    require_mapping=ops["require_mapping"]; check_iso=ops["check_iso"]
    parse_iso_moment=ops["parse_iso_moment"]
    build_publication_report=ops["build_publication_report"]
    ensure_scope_subset=ops["ensure_scope_subset"]
    require_string=ops["require_string"]
    build_readback_row_report=ops["build_readback_row_report"]
    build_readback_coverage_report=ops["build_readback_coverage_report"]
    GATE_STATUSES=ops["GATE_STATUSES"]; EXPERIMENT_TYPES=ops["EXPERIMENT_TYPES"]
    EXPERIMENT_ELIGIBILITY=ops["EXPERIMENT_ELIGIBILITY"]
    ATTRIBUTION_BOUNDARIES=ops["ATTRIBUTION_BOUNDARIES"]
    EXPERIMENT_STATUSES=ops["EXPERIMENT_STATUSES"]; CONCLUSIONS=ops["CONCLUSIONS"]
    AUTHORIZATION_STATUSES=ops["AUTHORIZATION_STATUSES"]
    AUTHORIZED_ACTIONS=ops["AUTHORIZED_ACTIONS"]; BASELINE_STATUSES=ops["BASELINE_STATUSES"]
    CONCURRENT_EDIT_STATUSES=ops["CONCURRENT_EDIT_STATUSES"]
    CHANGE_APPROVAL_STATUSES=ops["CHANGE_APPROVAL_STATUSES"]
    CHANGE_STATUSES=ops["CHANGE_STATUSES"]; ROLLBACK_STATUSES=ops["ROLLBACK_STATUSES"]
    READBACK_PHASES=ops["READBACK_PHASES"]; FETCH_STATUSES=ops["FETCH_STATUSES"]
    READBACK_FIELDS=ops["READBACK_FIELDS"]
    READBACK_FIELD_STATUSES=ops["READBACK_FIELD_STATUSES"]
    READBACK_STATUSES=ops["READBACK_STATUSES"]

    def check_refs(ids: set[str], path: str, *, usable: bool = False, allowed_types: set[str] | None = None) -> None:
        for source_id in ids:
            source = source_map.get(source_id)
            if source is None:
                errors.append(f"{path}: unknown source id {source_id!r}")
                continue
            if usable and source.get("fetch_status") != "ok":
                errors.append(f"{path}: source {source_id!r} is not usable")
            if allowed_types is not None and source.get("source_type") not in allowed_types:
                errors.append(f"{path}: source {source_id!r} has inapplicable type {source.get('source_type')!r}")
    parent_bundle_verified: bool | None = None
    v12_counts: dict[str, Any] = {}
    if schema_version in {"1.2", "1.3"}:
        v12_counts = validate_v12_contract(
            root, schema_version, project, mode, conclusion, marketplace, locale, envelope,
            source_map, fact_map, fact_scopes, claim_map, claim_scopes,
            conflicts, module_map, module_scopes, asset_map, child_asins,
            source_path, errors, warnings,
        )
        parent_bundle_verified = v12_counts.pop("parent_bundle_verified", None)
        if schema_version == "1.3":
            v13_counts = validate_v13_contract(
                root, project, conclusion, marketplace, locale, envelope,
                source_map, source_scopes, fact_map, fact_scopes, claim_map, claim_scopes,
                {
                    str(row.get("id")): row for row in root.get("competitor_insights", [])
                    if isinstance(row, dict) and is_text(row.get("id"))
                },
                module_map,
                {
                    str(row.get("id")): row for row in root.get("carriers", [])
                    if isinstance(row, dict) and is_text(row.get("id"))
                },
                {
                    str(row.get("id")): row for row in root.get("decision_answer_units", [])
                    if isinstance(row, dict) and is_text(row.get("id"))
                },
                {
                    str(row.get("id")): row for row in root.get("delta_evidence_requests", [])
                    if isinstance(row, dict) and is_text(row.get("id"))
                },
                errors,
            )
            v12_counts.update(v13_counts)
    else:
        warnings.append("Bundle v1.1 legacy compatibility mode: no v1.3 atom coverage PASS is implied.")
    if schema_version == "1.2":
        warnings.append("Bundle v1.2 legacy compatibility mode: requirement-level coverage is not v1.3 atom coverage.")

    gates_raw = require_list(root, "gates", "$", errors)
    gate_map = unique_rows(gates_raw, "$.gates", errors)
    for gate_id, gate in gate_map.items():
        path = f"$.gates[{gate_id}]"
        status = require_enum(gate, "status", path, GATE_STATUSES, errors)
        require_text(gate, "owner", path, errors)
        evidence = string_set(require_list(gate, "evidence", path, errors), f"{path}.evidence", errors)
        if status == "PASS" and not evidence:
            errors.append(f"{path}.evidence: PASS gate requires non-empty evidence")
        require_text(gate, "failure_action", path, errors)
    for gate_id in ("G0", "G1", "G2", "G3", "G4"):
        if gate_id not in gate_map:
            errors.append(f"$.gates: missing required gate {gate_id}")

    experiments = unique_rows(require_list(root, "experiments", "$", errors), "$.experiments", errors)
    for experiment_id, experiment in experiments.items():
        path = f"$.experiments[{experiment_id}]"
        experiment_type = require_enum(experiment, "experiment_type", path, EXPERIMENT_TYPES, errors)
        for key in ("hypothesis", "version_difference", "primary_metric", "run_rule", "stop_rule", "owner"):
            require_text(experiment, key, path, errors)
        components = string_set(require_list(experiment, "treatment_components", path, errors), f"{path}.treatment_components", errors, nonempty=True)
        string_set(require_list(experiment, "guardrails", path, errors), f"{path}.guardrails", errors, nonempty=True)
        eligibility = require_enum(experiment, "eligibility_status", path, EXPERIMENT_ELIGIBILITY, errors)
        eligibility_ids = string_set(require_list(experiment, "eligibility_source_ids", path, errors), f"{path}.eligibility_source_ids", errors)
        attribution = require_enum(experiment, "attribution_boundary", path, ATTRIBUTION_BOUNDARIES, errors)
        status = require_enum(experiment, "status", path, EXPERIMENT_STATUSES, errors)
        result_ids = string_set(require_list(experiment, "result_source_ids", path, errors), f"{path}.result_source_ids", errors)
        experiment_conclusion = require_enum(experiment, "conclusion", path, CONCLUSIONS, errors)
        if experiment_type == "single_variable":
            if len(components) != 1 or attribution != "ELEMENT_LEVEL":
                errors.append(f"{path}: single_variable requires one component and ELEMENT_LEVEL attribution")
        elif experiment_type == "multi_attribute_package":
            if len(components) < 2 or attribution != "PACKAGE_LEVEL":
                errors.append(f"{path}: multi_attribute_package requires multiple components and PACKAGE_LEVEL attribution")
        elif experiment_type == "descriptive_before_after" and attribution != "DESCRIPTIVE_ONLY":
            errors.append(f"{path}: descriptive_before_after must be DESCRIPTIVE_ONLY")
        if experiment_type != "descriptive_before_after" and status in {"READY", "RUNNING", "COMPLETE"}:
            if eligibility != "ELIGIBLE" or not eligibility_ids:
                errors.append(f"{path}: active MYE requires ELIGIBLE status and eligibility sources")
            check_refs(eligibility_ids, f"{path}.eligibility_source_ids", usable=True, allowed_types={"OFFICIAL_PLATFORM_RULE", "BACKEND_OBSERVED", "VERIFIED_ACCOUNT_DATA"})
        if status == "COMPLETE":
            if not result_ids:
                errors.append(f"{path}.result_source_ids: COMPLETE experiment requires results")
            check_refs(result_ids, f"{path}.result_source_ids", usable=True)
        elif schema_version in {"1.2", "1.3"} and experiment_conclusion in {"PASS", "ROLLBACK"}:
            code = "A13" if schema_version == "1.3" else "A12"
            errors.append(f"[{code}-EXPERIMENT-001] {path}.conclusion: non-COMPLETE experiment cannot claim {experiment_conclusion}")
    if experiments and "G6" not in gate_map:
        errors.append("$.gates: experiments require G6")

    required_pass_gates = required_pass_gate_ids(mode, bool(experiments))
    if conclusion == "PASS":
        for gate_id in required_pass_gates:
            if gate_map.get(gate_id, {}).get("status") != "PASS":
                errors.append(f"$.project.conclusion: PASS requires {gate_id}=PASS")

    if mode == "publish_support":
        authorization = require_mapping(root.get("publish_authorization"), "$.publish_authorization", errors)
        auth_status = require_enum(authorization, "status", "$.publish_authorization", AUTHORIZATION_STATUSES, errors)
        authorization_id = require_text(authorization, "authorization_id", "$.publish_authorization", errors)
        require_text(authorization, "authorized_by", "$.publish_authorization", errors)
        authorized_at = require_text(authorization, "authorized_at", "$.publish_authorization", errors)
        expires_at = require_text(authorization, "expires_at", "$.publish_authorization", errors)
        check_iso(authorized_at, "$.publish_authorization.authorized_at", errors)
        check_iso(expires_at, "$.publish_authorization.expires_at", errors)
        authorized_moment = parse_iso_moment(authorized_at)
        expires_moment = parse_iso_moment(expires_at)
        snapshot_moment = parse_iso_moment(snapshot_date)
        validation_moment = datetime.now(timezone.utc)
        systems = string_set(require_list(authorization, "systems", "$.publish_authorization", errors), "$.publish_authorization.systems", errors, nonempty=True)
        auth_marketplaces = string_set(require_list(authorization, "marketplaces", "$.publish_authorization", errors), "$.publish_authorization.marketplaces", errors, nonempty=True)
        auth_locales = string_set(require_list(authorization, "locales", "$.publish_authorization", errors), "$.publish_authorization.locales", errors, nonempty=True)
        auth_contents = string_set(require_list(authorization, "content_ids", "$.publish_authorization", errors), "$.publish_authorization.content_ids", errors, nonempty=True)
        auth_children = string_set(require_list(authorization, "child_asins", "$.publish_authorization", errors), "$.publish_authorization.child_asins", errors, nonempty=True)
        actions = string_set(require_list(authorization, "allowed_actions", "$.publish_authorization", errors), "$.publish_authorization.allowed_actions", errors, nonempty=True)
        publication_report = build_publication_report(
            mode=mode,
            write_scope=write_scope,
            identity_status=identity_status,
            scope_status=scope_status,
            authorization_status=auth_status,
            authorized_at=authorized_moment,
            expires_at=expires_moment,
            snapshot_at=snapshot_moment,
            validation_at=validation_moment,
            systems=systems,
            marketplaces=auth_marketplaces,
            locales=auth_locales,
            content_ids=auth_contents,
            child_asins=auth_children,
            actions=actions,
            expected_marketplace=marketplace,
            expected_locale=locale,
            expected_content_ids=content_ids,
            expected_child_asins=child_asins,
            allowed_actions=AUTHORIZED_ACTIONS,
        )
        errors.extend(publication_report.errors)
        string_set(require_list(authorization, "prohibited_actions", "$.publish_authorization", errors), "$.publish_authorization.prohibited_actions", errors, nonempty=True)
        authorized_change_ids = string_set(require_list(authorization, "change_set_ids", "$.publish_authorization", errors), "$.publish_authorization.change_set_ids", errors, nonempty=True)
        authorization_sources = string_set(require_list(authorization, "source_ids", "$.publish_authorization", errors), "$.publish_authorization.source_ids", errors, nonempty=True)
        check_refs(authorization_sources, "$.publish_authorization.source_ids", usable=True, allowed_types={"VERIFIED_ACCOUNT_DATA"})
        for source_id in authorization_sources & set(source_scopes):
            ensure_scope_subset(envelope, source_scopes[source_id], "$.scope", f"authorization source {source_id!r}", errors)

        baseline = require_mapping(root.get("baseline"), "$.baseline", errors)
        baseline_id = require_text(baseline, "id", "$.baseline", errors)
        if require_enum(baseline, "status", "$.baseline", BASELINE_STATUSES, errors) != "FROZEN":
            errors.append("$.baseline.status: publish_support requires FROZEN")
        captured_at = require_text(baseline, "captured_at", "$.baseline", errors)
        check_iso(captured_at, "$.baseline.captured_at", errors)
        baseline_contents = string_set(require_list(baseline, "content_ids", "$.baseline", errors), "$.baseline.content_ids", errors, nonempty=True)
        if baseline_contents != content_ids:
            errors.append("$.baseline.content_ids: must exactly match intended content IDs")
        for key in ("application_state_ref", "copy_snapshot_ref", "asset_snapshot_ref", "alt_snapshot_ref", "owner"):
            require_text(baseline, key, "$.baseline", errors)
        frontend_sources = string_set(require_list(baseline, "frontend_source_ids", "$.baseline", errors), "$.baseline.frontend_source_ids", errors, nonempty=True)
        check_refs(frontend_sources, "$.baseline.frontend_source_ids", usable=True, allowed_types={"PUBLIC_OBSERVED"})
        concurrent_status = require_enum(baseline, "concurrent_edit_status", "$.baseline", CONCURRENT_EDIT_STATUSES, errors)
        if concurrent_status not in {"FROZEN", "COORDINATED"}:
            errors.append("$.baseline.concurrent_edit_status: must be FROZEN or COORDINATED")

        change_rows = require_list(root, "change_set", "$", errors)
        change_map = unique_rows(change_rows, "$.change_set", errors)
        if not change_map:
            errors.append("$.change_set: publish_support requires approved changes")
        if set(change_map) != authorized_change_ids:
            errors.append("$.publish_authorization.change_set_ids: must exactly match change_set IDs")
        for change_id, change in change_map.items():
            path = f"$.change_set[{change_id}]"
            change_system = require_text(change, "system", path, errors)
            if change_system and change_system.casefold() not in {system.casefold() for system in systems}:
                errors.append(f"[A-AUTH-005] {path}.system: outside the explicitly authorized systems")
            content_id = require_text(change, "content_id", path, errors)
            if content_id not in auth_contents:
                errors.append(f"{path}.content_id: outside authorization")
            if require_text(change, "marketplace", path, errors) != marketplace or require_text(change, "locale", path, errors) != locale:
                errors.append(f"{path}: marketplace/locale outside authorization")
            change_children = string_set(require_list(change, "child_asins", path, errors), f"{path}.child_asins", errors, nonempty=True)
            if not change_children.issubset(auth_children):
                errors.append(f"{path}.child_asins: outside authorization")
            require_text(change, "field_or_module", path, errors)
            before_ref = require_text(change, "before_value_ref", path, errors)
            after_ref = require_text(change, "after_value_ref", path, errors)
            if before_ref == after_ref:
                errors.append(f"{path}: before_value_ref and after_value_ref must differ")
            for key, known in (("fact_ids", fact_map), ("claim_ids", claim_map), ("asset_ids", asset_map)):
                for value in string_set(require_list(change, key, path, errors), f"{path}.{key}", errors):
                    if value not in known:
                        errors.append(f"{path}.{key}: unknown id {value!r}")
            require_text(change, "owner", path, errors)
            if require_enum(change, "approval_status", path, CHANGE_APPROVAL_STATUSES, errors) != "APPROVED":
                errors.append(f"{path}.approval_status: publish_support requires APPROVED")
            change_status = require_enum(change, "status", path, CHANGE_STATUSES, errors)
            applied_at = require_string(change, "applied_at", path, errors)
            if change_status in {"APPLIED", "VERIFIED"}:
                if not applied_at:
                    errors.append(f"{path}.applied_at: required after application")
                else:
                    check_iso(applied_at, f"{path}.applied_at", errors)
            elif applied_at:
                check_iso(applied_at, f"{path}.applied_at", errors)
            if conclusion == "PASS" and change_status != "VERIFIED":
                errors.append(f"{path}.status: project PASS requires VERIFIED")

        rollback = require_mapping(root.get("rollback"), "$.rollback", errors)
        rollback_status = require_enum(rollback, "status", "$.rollback", ROLLBACK_STATUSES, errors)
        if rollback_status not in {"READY", "TRIGGERED", "COMPLETED"}:
            errors.append("$.rollback.status: publish_support requires a ready rollback")
        if require_text(rollback, "baseline_id", "$.rollback", errors) != baseline_id:
            errors.append("$.rollback.baseline_id: must reference frozen baseline")
        string_set(require_list(rollback, "trigger_conditions", "$.rollback", errors), "$.rollback.trigger_conditions", errors, nonempty=True)
        require_text(rollback, "method", "$.rollback", errors)
        require_text(rollback, "responsible_owner", "$.rollback", errors)
        protected_ids = string_set(require_list(rollback, "protected_p0_fact_ids", "$.rollback", errors), "$.rollback.protected_p0_fact_ids", errors, nonempty=True)
        for fact_id in protected_ids:
            if fact_id not in fact_map:
                errors.append(f"$.rollback.protected_p0_fact_ids: unknown fact id {fact_id!r}")
        string_set(require_list(rollback, "verification_steps", "$.rollback", errors), "$.rollback.verification_steps", errors, nonempty=True)
        rollback_sources = string_set(require_list(rollback, "source_ids", "$.rollback", errors), "$.rollback.source_ids", errors, nonempty=True)
        check_refs(rollback_sources, "$.rollback.source_ids", usable=True)

        readback_rows = require_list(root, "live_readback", "$", errors)
        readback_map = unique_rows(readback_rows, "$.live_readback", errors)
        first_keys: set[tuple[str, str, str]] = set()
        pass_keys: set[tuple[str, str, str]] = set()
        expected_aplus = {
            (row["child_asin"], row["marketplace"], row["locale"]):
            (row["aplus_content_id"] or row.get("brand_story_id", ""))
            for row in variant_rows
        }
        for readback_id, readback in readback_map.items():
            path = f"$.live_readback[{readback_id}]"
            phase = require_enum(readback, "readback_phase", path, READBACK_PHASES, errors)
            child = require_text(readback, "child_asin", path, errors)
            rb_marketplace = require_text(readback, "marketplace", path, errors)
            rb_locale = require_text(readback, "locale", path, errors)
            expected_content = require_text(readback, "expected_content_id", path, errors)
            observed_content = require_string(readback, "observed_content_id", path, errors)
            checked_at = require_text(readback, "checked_at", path, errors)
            check_iso(checked_at, f"{path}.checked_at", errors)
            checked_moment = parse_iso_moment(checked_at)
            require_text(readback, "device", path, errors)
            require_text(readback, "viewport", path, errors)
            fetch_status = require_enum(readback, "fetch_status", path, FETCH_STATUSES, errors)
            field_checks = require_mapping(readback.get("field_checks"), f"{path}.field_checks", errors)
            if set(field_checks) != READBACK_FIELDS:
                errors.append(f"{path}.field_checks: must contain exactly {sorted(READBACK_FIELDS)!r}")
            field_statuses = {require_enum(field_checks, field, f"{path}.field_checks", READBACK_FIELD_STATUSES, errors) for field in READBACK_FIELDS}
            evidence_ids = string_set(require_list(readback, "evidence_source_ids", path, errors), f"{path}.evidence_source_ids", errors)
            check_refs(evidence_ids, f"{path}.evidence_source_ids", usable=fetch_status == "ok", allowed_types={"PUBLIC_OBSERVED"})
            status = require_enum(readback, "status", path, READBACK_STATUSES, errors)
            mismatch_action = require_string(readback, "mismatch_action", path, errors)
            followup = readback.get("followup_required")
            if not isinstance(followup, bool):
                errors.append(f"{path}.followup_required: required boolean")
                followup = False
            require_text(readback, "owner", path, errors)
            row_report = build_readback_row_report(
                path=path,
                phase=phase,
                child_asin=child,
                marketplace=rb_marketplace,
                locale=rb_locale,
                expected_content_id=expected_content,
                observed_content_id=observed_content,
                checked_at=checked_moment,
                fetch_status=fetch_status,
                field_statuses=field_statuses,
                evidence_source_ids=evidence_ids,
                status=status,
                mismatch_action=mismatch_action,
                followup_required=followup,
                expected_content_by_key=expected_aplus,
                source_map=source_map,
                source_scopes=source_scopes,
            )
            errors.extend(row_report.errors)
            if row_report.is_first_readback:
                first_keys.add(row_report.key)
            if row_report.declares_pass:
                pass_keys.add(row_report.key)
        intended_keys = set(expected_aplus)
        coverage_report = build_readback_coverage_report(
            intended_keys=intended_keys,
            first_readback_keys=first_keys,
            pass_keys=pass_keys,
            conclusion=conclusion,
        )
        errors.extend(coverage_report.errors)

    return GovernanceReport(
        tuple(errors), tuple(warnings), parent_bundle_verified, v12_counts,
        gate_map, experiments,
    )
