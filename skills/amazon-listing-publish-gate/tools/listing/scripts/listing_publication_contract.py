#!/usr/bin/env python3
"""Shared strict publication/readback contract for legacy and Listing v1.1."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

DATA_PLANES = {"catalog_contribution", "seller_listing", "relationship", "enriched_content", "external_tool"}
AUTHORIZATION_STATUSES = {"NOT_AUTHORIZED", "AUTHORIZED", "EXPIRED", "REVOKED", "OUT_OF_SCOPE"}
AUTHORIZED_SUBMISSION_ACTIONS = {"submit", "apply", "publish"}
READBACK_STATUSES = {"NOT_SUBMITTED", "SUBMITTED", "ACCEPTED_BACKEND", "REJECTED_BACKEND", "LIVE_MATCH", "LIVE_MISMATCH", "OBSERVATION_BLOCKED", "UNKNOWN"}
LIVE_EVIDENCE_TYPES = {"public_frontend", "frontend_readback", "PUBLIC_OBSERVED"}
AUTHORIZATION_KEYS = {"status", "authorization_id", "authorizer", "authorized_account", "system", "data_planes", "marketplace", "locale", "target_ids", "change_set_ids", "baseline_sha256", "change_set_sha256", "authorized_action", "attempt_limit", "authorized_at", "expires_at", "rollback_scope", "notes"}
BASELINE_ROW_KEYS = {"id", "target_id", "field_resolution_id", "data_plane", "system", "before_value", "captured_at", "source_ids", "row_sha256"}
CHANGE_ROW_KEYS = {"id", "target_id", "field_resolution_id", "data_plane", "system", "after_value", "fact_ids", "claim_ids", "approval_status", "approved_by", "approved_at", "row_sha256"}
ROLLBACK_ROW_KEYS = {"id", "change_set_id", "baseline_id", "target_id", "field_resolution_id", "data_plane", "system", "rollback_value", "trigger_conditions", "owner", "row_sha256"}
READBACK_ROW_KEYS = {"child_asin", "status", "live_pass", "observed_at", "locator", "expected_value", "observed_value", "evidence_ref"}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")

def err(errors: list[str], code: str, path: str, message: str) -> None:
    errors.append(f"[{code}] {path}: {message}")

def warn(warnings: list[str], code: str, path: str, message: str) -> None:
    warnings.append(f"[{code}] {path}: {message}")

def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())

def string_list(value: Any) -> bool:
    return isinstance(value, list) and all(nonempty(x) for x in value)

def unique_strings(value: Any) -> bool:
    return string_list(value) and len(value) == len(set(value))

def isoish(value: Any) -> bool:
    return nonempty(value) and "T" in value and (value.endswith("Z") or "+" in value)

def parse_timestamp(value: Any) -> datetime | None:
    if not isoish(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None

def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

def canonical_row_hash(row: dict[str, Any]) -> str:
    normalized = copy.deepcopy(row)
    normalized["row_sha256"] = ""
    return canonical_sha256(normalized)

def canonical_rows_hash(rows: list[Any]) -> str:
    normalized: list[Any] = []
    for row in rows:
        if isinstance(row, dict):
            item = copy.deepcopy(row)
            item["row_sha256"] = ""
            normalized.append(item)
        else:
            normalized.append(row)
    return canonical_sha256(normalized)

def canonical_child_readback_value(change_rows: list[dict[str, Any]], child_asin: str) -> str:
    """Return the exact live-readback contract for one child.

    A single-field change keeps the human-readable value. Multi-field changes
    use a canonical JSON object so one terminal child readback cannot silently
    omit any authorized field.
    """
    rows = [row for row in change_rows if row.get("target_id") == child_asin]
    rows.sort(key=lambda row: (str(row.get("field_resolution_id", "")), str(row.get("id", ""))))
    if len(rows) == 1:
        value = rows[0].get("after_value")
        return value if isinstance(value, str) else ""
    values = {
        str(row.get("field_resolution_id")): row.get("after_value")
        for row in rows
    }
    return json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def exact_keys(value: dict[str, Any], expected: set[str], path: str, code: str, errors: list[str]) -> None:
    if set(value) != expected:
        err(errors, code, path, f"must contain exactly {sorted(expected)}")

def index_by_id(rows: Iterable[dict[str, Any]], path: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        item_id = row.get("id")
        if not nonempty(item_id) or not ID_RE.match(item_id):
            err(errors, "LST-ID-001", f"{path}[{index}].id", "must be a non-empty stable ID")
            continue
        if item_id in result:
            err(errors, "LST-ID-002", f"{path}[{index}].id", f"duplicate ID {item_id}")
            continue
        result[item_id] = row
    return result

def scope_set(scope: Any, key: str) -> set[str]:
    if not isinstance(scope, dict):
        return set()
    value = scope.get(key, [])
    return set(value) if string_list(value) else set()

def require_refs(
    values: Any,
    known: set[str],
    path: str,
    errors: list[str],
    code: str = "LST-REF-001",
) -> None:
    if not unique_strings(values):
        err(errors, code, path, "must be a unique string array")
        return
    unknown = set(values) - known
    if unknown:
        err(errors, code, path, f"unknown references: {sorted(unknown)}")

def validate_publication(
    bundle: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    field_index: dict[str, dict[str, Any]],
    fact_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    boundary = bundle.get("execution_boundary")
    scope = bundle.get("scope", {})
    intended = scope_set(scope, "intended_child_asins")
    auth = bundle.get("publish_authorization")
    if not isinstance(auth, dict):
        err(errors, "LST-AUTH-010", "publish_authorization", "must be an object")
        auth = {}
    else:
        exact_keys(auth, AUTHORIZATION_KEYS, "publish_authorization", "LST-AUTH-015", errors)
    if auth.get("status") not in AUTHORIZATION_STATUSES:
        err(errors, "LST-AUTH-016", "publish_authorization.status", "unsupported authorization status")

    raw_sections: dict[str, Any] = {
        "baseline": bundle.get("baseline"),
        "change_set": bundle.get("change_set"),
        "rollback": bundle.get("rollback"),
        "live_readback": bundle.get("live_readback"),
    }
    for key, value in raw_sections.items():
        if not isinstance(value, list):
            err(errors, "LST-PUBLISH-001", key, "must be an array")
    baseline_rows = raw_sections["baseline"] if isinstance(raw_sections["baseline"], list) else []
    change_rows = raw_sections["change_set"] if isinstance(raw_sections["change_set"], list) else []
    rollback_rows = raw_sections["rollback"] if isinstance(raw_sections["rollback"], list) else []
    readbacks = raw_sections["live_readback"] if isinstance(raw_sections["live_readback"], list) else []

    baseline_objects = [row for row in baseline_rows if isinstance(row, dict)]
    change_objects = [row for row in change_rows if isinstance(row, dict)]
    rollback_objects = [row for row in rollback_rows if isinstance(row, dict)]
    if len(baseline_objects) != len(baseline_rows):
        err(errors, "LST-PUBLISH-005", "baseline", "every row must be an object")
    if len(change_objects) != len(change_rows):
        err(errors, "LST-PUBLISH-006", "change_set", "every row must be an object")
    if len(rollback_objects) != len(rollback_rows):
        err(errors, "LST-PUBLISH-007", "rollback", "every row must be an object")
    baseline_index = index_by_id(baseline_objects, "baseline", errors)
    change_index = index_by_id(change_objects, "change_set", errors)
    rollback_index = index_by_id(rollback_objects, "rollback", errors)

    candidate_rows = [row for row in bundle.get("field_candidates", []) if isinstance(row, dict)]
    row_planes: set[str] = set()
    row_systems: set[str] = set()
    baseline_bindings: dict[tuple[Any, Any, Any, Any], dict[str, Any]] = {}
    change_bindings: dict[tuple[Any, Any, Any, Any], dict[str, Any]] = {}
    baseline_targets: set[str] = set()
    change_targets: set[str] = set()
    rollback_targets: set[str] = set()

    for index, row in enumerate(baseline_objects):
        path = f"baseline[{index}]"
        exact_keys(row, BASELINE_ROW_KEYS, path, "LST-BASELINE-001", errors)
        if row.get("row_sha256") != canonical_row_hash(row):
            err(errors, "LST-BASELINE-002", f"{path}.row_sha256", "does not match canonical row hash")
        target = row.get("target_id")
        if target not in intended:
            err(errors, "LST-BASELINE-003", f"{path}.target_id", "outside intended child scope")
        field = field_index.get(row.get("field_resolution_id"))
        if field is None:
            err(errors, "LST-BASELINE-004", f"{path}.field_resolution_id", "unknown field resolution")
        elif (
            field.get("status") != "RESOLVED"
            or not all(field.get(key) is True for key in ("exists", "editable", "applicable"))
            or field.get("data_plane") != row.get("data_plane")
            or target not in scope_set(field.get("application_scope"), "child_asins")
        ):
            err(errors, "LST-BASELINE-005", path, "field, data plane, or target is outside the resolved writable scope")
        if row.get("data_plane") not in DATA_PLANES:
            err(errors, "LST-BASELINE-006", f"{path}.data_plane", "unsupported data plane")
        if not nonempty(row.get("system")):
            err(errors, "LST-BASELINE-007", f"{path}.system", "is required")
        if not isinstance(row.get("before_value"), str):
            err(errors, "LST-BASELINE-008", f"{path}.before_value", "must be a string")
        if parse_timestamp(row.get("captured_at")) is None:
            err(errors, "LST-BASELINE-009", f"{path}.captured_at", "must be a timezone-qualified ISO timestamp")
        require_refs(row.get("source_ids", []), set(source_index), f"{path}.source_ids", errors, "LST-BASELINE-010")
        if not row.get("source_ids"):
            err(errors, "LST-BASELINE-011", f"{path}.source_ids", "captured baseline requires evidence")
        for source_id in row.get("source_ids", []):
            if source_index.get(source_id, {}).get("status") != "USABLE":
                err(errors, "LST-BASELINE-012", f"{path}.source_ids", f"source {source_id} is not usable")
        if nonempty(row.get("data_plane")):
            row_planes.add(row.get("data_plane"))
        if nonempty(row.get("system")):
            row_systems.add(row.get("system"))
        binding = tuple(row.get(key) for key in ("target_id", "field_resolution_id", "data_plane", "system"))
        if binding in baseline_bindings:
            err(errors, "LST-BASELINE-013", path, "duplicate target/field/data-plane/system baseline binding")
        else:
            baseline_bindings[binding] = row
        if nonempty(target):
            baseline_targets.add(target)

    for index, row in enumerate(change_objects):
        path = f"change_set[{index}]"
        exact_keys(row, CHANGE_ROW_KEYS, path, "LST-CHANGE-001", errors)
        if row.get("row_sha256") != canonical_row_hash(row):
            err(errors, "LST-CHANGE-002", f"{path}.row_sha256", "does not match canonical row hash")
        target = row.get("target_id")
        if target not in intended:
            err(errors, "LST-CHANGE-003", f"{path}.target_id", "outside intended child scope")
        field = field_index.get(row.get("field_resolution_id"))
        if field is None:
            err(errors, "LST-CHANGE-004", f"{path}.field_resolution_id", "unknown field resolution")
        elif (
            field.get("status") != "RESOLVED"
            or not all(field.get(key) is True for key in ("exists", "editable", "applicable"))
            or field.get("data_plane") != row.get("data_plane")
            or target not in scope_set(field.get("application_scope"), "child_asins")
        ):
            err(errors, "LST-CHANGE-005", path, "field, data plane, or target is outside the resolved writable scope")
        if row.get("data_plane") not in DATA_PLANES:
            err(errors, "LST-CHANGE-006", f"{path}.data_plane", "unsupported data plane")
        if not nonempty(row.get("system")) or not isinstance(row.get("after_value"), str):
            err(errors, "LST-CHANGE-007", path, "system and string after_value are required")
        require_refs(row.get("fact_ids", []), set(fact_index), f"{path}.fact_ids", errors, "LST-CHANGE-008")
        require_refs(row.get("claim_ids", []), set(claim_index), f"{path}.claim_ids", errors, "LST-CHANGE-009")
        for fact_id in row.get("fact_ids", []):
            fact = fact_index.get(fact_id, {})
            if fact.get("verification_status") != "VERIFIED" or fact.get("content_status") != "PUBLISHABLE" or target not in scope_set(fact.get("application_scope"), "child_asins"):
                err(errors, "LST-CHANGE-010", path, f"fact {fact_id} is not publishable for target")
        for claim_id in row.get("claim_ids", []):
            claim = claim_index.get(claim_id, {})
            if claim.get("support_status") != "SUPPORTED" or claim.get("content_status") != "PUBLISHABLE" or target not in scope_set(claim.get("application_scope"), "child_asins"):
                err(errors, "LST-CHANGE-011", path, f"claim {claim_id} is not publishable for target")
        matching_candidates = [
            candidate for candidate in candidate_rows
            if candidate.get("field_resolution_id") == row.get("field_resolution_id")
            and candidate.get("value") == row.get("after_value")
            and target in scope_set(candidate.get("application_scope"), "child_asins")
            and candidate.get("content_status") == "FINAL"
            and candidate.get("qa_status") == "PASS"
            and set(candidate.get("fact_ids", [])) == set(row.get("fact_ids", []))
            and set(candidate.get("claim_ids", [])) == set(row.get("claim_ids", []))
        ]
        if len(matching_candidates) != 1:
            err(errors, "LST-CHANGE-012", path, "after_value must bind exactly one FINAL, QA-passed field candidate with identical evidence refs")
        if row.get("approval_status") != "APPROVED" or not nonempty(row.get("approved_by")):
            err(errors, "LST-CHANGE-013", path, "approved change and approver are required")
        if parse_timestamp(row.get("approved_at")) is None:
            err(errors, "LST-CHANGE-014", f"{path}.approved_at", "must be a timezone-qualified ISO timestamp")
        if nonempty(row.get("data_plane")):
            row_planes.add(row.get("data_plane"))
        if nonempty(row.get("system")):
            row_systems.add(row.get("system"))
        binding = tuple(row.get(key) for key in ("target_id", "field_resolution_id", "data_plane", "system"))
        if binding in change_bindings:
            err(errors, "LST-CHANGE-015", path, "duplicate target/field/data-plane/system change binding")
        else:
            change_bindings[binding] = row
        if nonempty(target):
            change_targets.add(target)

    if baseline_bindings or change_bindings:
        missing_baselines = sorted(set(change_bindings) - set(baseline_bindings), key=str)
        orphan_baselines = sorted(set(baseline_bindings) - set(change_bindings), key=str)
        if missing_baselines or orphan_baselines:
            err(
                errors, "LST-PUBLISH-008", "baseline/change_set",
                f"must form an exact binding closure; missing baselines={missing_baselines!r}, orphan baselines={orphan_baselines!r}",
            )
        for binding in set(baseline_bindings) & set(change_bindings):
            captured_at = parse_timestamp(baseline_bindings[binding].get("captured_at"))
            approved_at = parse_timestamp(change_bindings[binding].get("approved_at"))
            if captured_at is not None and approved_at is not None and captured_at > approved_at:
                err(errors, "LST-PUBLISH-009", "baseline/change_set", f"baseline must precede approval for binding {binding!r}")

    rollback_change_ids: set[str] = set()
    rollback_baseline_ids: set[str] = set()
    for index, row in enumerate(rollback_objects):
        path = f"rollback[{index}]"
        exact_keys(row, ROLLBACK_ROW_KEYS, path, "LST-ROLLBACK-001", errors)
        if row.get("row_sha256") != canonical_row_hash(row):
            err(errors, "LST-ROLLBACK-002", f"{path}.row_sha256", "does not match canonical row hash")
        change = change_index.get(row.get("change_set_id"))
        baseline_row = baseline_index.get(row.get("baseline_id"))
        if change is None:
            err(errors, "LST-ROLLBACK-003", f"{path}.change_set_id", "unknown change-set row")
        if baseline_row is None:
            err(errors, "LST-ROLLBACK-004", f"{path}.baseline_id", "unknown baseline row")
        for key in ("target_id", "field_resolution_id", "data_plane", "system"):
            expected_values = {source.get(key) for source in (change, baseline_row) if isinstance(source, dict)}
            if len(expected_values) != 1 or row.get(key) not in expected_values:
                err(errors, "LST-ROLLBACK-005", f"{path}.{key}", "must exactly match linked baseline and change")
        if baseline_row is not None and row.get("rollback_value") != baseline_row.get("before_value"):
            err(errors, "LST-ROLLBACK-006", f"{path}.rollback_value", "must exactly restore the captured baseline")
        if not unique_strings(row.get("trigger_conditions", [])) or not row.get("trigger_conditions") or not nonempty(row.get("owner")):
            err(errors, "LST-ROLLBACK-007", path, "trigger conditions and owner are required")
        if nonempty(row.get("change_set_id")):
            if row.get("change_set_id") in rollback_change_ids:
                err(errors, "LST-ROLLBACK-009", f"{path}.change_set_id", "each change may have only one rollback row")
            rollback_change_ids.add(row.get("change_set_id"))
        if nonempty(row.get("baseline_id")):
            if row.get("baseline_id") in rollback_baseline_ids:
                err(errors, "LST-ROLLBACK-010", f"{path}.baseline_id", "each baseline may have only one rollback row")
            rollback_baseline_ids.add(row.get("baseline_id"))
        if nonempty(row.get("target_id")):
            rollback_targets.add(row.get("target_id"))
        if nonempty(row.get("data_plane")):
            row_planes.add(row.get("data_plane"))
        if nonempty(row.get("system")):
            row_systems.add(row.get("system"))
    if rollback_objects and rollback_change_ids != set(change_index):
        err(errors, "LST-ROLLBACK-008", "rollback", "must cover every approved change exactly once")
    if rollback_objects and rollback_baseline_ids != set(baseline_index):
        err(errors, "LST-ROLLBACK-011", "rollback", "must cover every captured baseline exactly once")

    if boundary in {"authorized_submission", "rollback_only"}:
        if bundle.get("project", {}).get("mode") != "publish_support":
            err(errors, "LST-AUTH-032", "project.mode", "write-capable boundary requires publish_support mode")
        if boundary == "authorized_submission" and bundle.get("project", {}).get("conclusion") not in {"PASS", "LIVE_PASS"}:
            err(errors, "LST-AUTH-033", "project.conclusion", "submission authority requires a terminal parent PASS")
        if auth.get("status") != "AUTHORIZED":
            err(errors, "LST-AUTH-011", "publish_authorization.status", "authorized boundary requires AUTHORIZED")
        for key in (
            "authorization_id", "authorizer", "authorized_account", "system", "marketplace",
            "locale", "baseline_sha256", "change_set_sha256", "authorized_action",
            "authorized_at", "expires_at",
        ):
            if not nonempty(auth.get(key)):
                err(errors, "LST-AUTH-012", f"publish_authorization.{key}", "is required")
        for key in ("data_planes", "target_ids", "change_set_ids", "rollback_scope"):
            if not unique_strings(auth.get(key, [])) or not auth.get(key):
                err(errors, "LST-AUTH-013", f"publish_authorization.{key}", "must be a non-empty unique array")
        if auth.get("attempt_limit") != 1:
            err(errors, "LST-AUTH-014", "publish_authorization.attempt_limit", "must be exactly 1 for this one-shot change set")
        if not baseline_objects:
            err(errors, "LST-PUBLISH-002", "baseline", "captured baseline is required")
        if not change_objects:
            err(errors, "LST-PUBLISH-003", "change_set", "approved change set is required")
        if not rollback_objects:
            err(errors, "LST-PUBLISH-004", "rollback", "rollback plan is required")
        if auth.get("authorized_account") != scope.get("seller_scope"):
            err(errors, "LST-AUTH-017", "publish_authorization.authorized_account", "must match frozen seller scope")
        if auth.get("marketplace") != scope.get("marketplace") or auth.get("locale") != scope.get("locale"):
            err(errors, "LST-AUTH-018", "publish_authorization", "marketplace/locale must match frozen scope")
        if set(auth.get("target_ids", [])) != intended or set(auth.get("rollback_scope", [])) != intended:
            err(errors, "LST-AUTH-019", "publish_authorization", "target_ids and rollback_scope must exactly match intended children")
        if baseline_targets != intended or change_targets != intended or rollback_targets != intended:
            err(errors, "LST-AUTH-030", "baseline/change_set/rollback", "every authorized target must be present in all three row sets")
        if set(auth.get("change_set_ids", [])) != set(change_index):
            err(errors, "LST-AUTH-020", "publish_authorization.change_set_ids", "must exactly match approved change-set rows")
        if set(auth.get("data_planes", [])) != row_planes or not row_planes.issubset(DATA_PLANES):
            err(errors, "LST-AUTH-021", "publish_authorization.data_planes", "must exactly match row data planes")
        if row_systems != {auth.get("system")}:
            err(errors, "LST-AUTH-022", "publish_authorization.system", "must exactly match every baseline/change/rollback row")
        if auth.get("baseline_sha256") != canonical_rows_hash(baseline_rows):
            err(errors, "LST-AUTH-023", "publish_authorization.baseline_sha256", "does not match canonical baseline hash")
        if auth.get("change_set_sha256") != canonical_rows_hash(change_rows):
            err(errors, "LST-AUTH-024", "publish_authorization.change_set_sha256", "does not match canonical change-set hash")
        action = auth.get("authorized_action")
        if boundary == "authorized_submission" and action not in AUTHORIZED_SUBMISSION_ACTIONS:
            err(errors, "LST-AUTH-025", "publish_authorization.authorized_action", "does not authorize submission")
        if boundary == "rollback_only" and action != "rollback":
            err(errors, "LST-AUTH-026", "publish_authorization.authorized_action", "rollback_only requires rollback authorization")
        authorized_at = parse_timestamp(auth.get("authorized_at"))
        expires_at = parse_timestamp(auth.get("expires_at"))
        now = datetime.now(timezone.utc)
        if authorized_at is None or expires_at is None or authorized_at >= expires_at:
            err(errors, "LST-AUTH-027", "publish_authorization", "authorization timestamps must be valid and ordered")
        elif expires_at <= now:
            err(errors, "LST-AUTH-028", "publish_authorization.expires_at", "authorization is expired")
        elif authorized_at > now:
            err(errors, "LST-AUTH-029", "publish_authorization.authorized_at", "authorization cannot start in the future")
        row_times = [
            parsed
            for parsed in (
                *[parse_timestamp(row.get("captured_at")) for row in baseline_objects],
                *[parse_timestamp(row.get("approved_at")) for row in change_objects],
            )
            if parsed is not None
        ]
        if authorized_at is not None and row_times and authorized_at < max(row_times):
            err(errors, "LST-AUTH-031", "publish_authorization.authorized_at", "must be at or after all captured baselines and approved changes")
    elif auth.get("status") == "AUTHORIZED":
        warn(warnings, "LST-AUTH-W02", "publish_authorization", "authorization record exists but execution boundary does not allow submission")

    seen_children: set[str] = set()
    live_match_children: set[str] = set()
    for index, row in enumerate(readbacks):
        path = f"live_readback[{index}]"
        if not isinstance(row, dict):
            err(errors, "LST-READBACK-001", path, "must be an object")
            continue
        exact_keys(row, READBACK_ROW_KEYS, path, "LST-READBACK-007", errors)
        status = row.get("status")
        if status not in READBACK_STATUSES:
            err(errors, "LST-READBACK-002", f"{path}.status", "unsupported state")
        child = row.get("child_asin")
        if child not in intended:
            err(errors, "LST-READBACK-003", f"{path}.child_asin", "must be an intended child")
        elif child in seen_children:
            err(errors, "LST-READBACK-008", f"{path}.child_asin", "each child may have only one terminal readback row")
        else:
            seen_children.add(child)
        if not isinstance(row.get("live_pass"), bool):
            err(errors, "LST-READBACK-009", f"{path}.live_pass", "must be boolean")
        observed_status = status in READBACK_STATUSES - {"NOT_SUBMITTED"}
        evidence = source_index.get(row.get("evidence_ref"))
        if observed_status:
            if parse_timestamp(row.get("observed_at")) is None or not nonempty(row.get("locator")):
                err(errors, "LST-READBACK-010", path, "observational state requires timestamp and locator")
            if evidence is None or evidence.get("status") != "USABLE":
                err(errors, "LST-READBACK-011", f"{path}.evidence_ref", "must reference usable evidence")
        if status == "LIVE_MATCH":
            for key in ("expected_value", "observed_value"):
                if not nonempty(row.get(key)):
                    err(errors, "LST-READBACK-004", f"{path}.{key}", "required for LIVE_MATCH")
            if row.get("expected_value") != row.get("observed_value"):
                err(errors, "LST-READBACK-012", path, "LIVE_MATCH requires exact expected/observed equality")
            authorized_expected = canonical_child_readback_value(change_objects, child)
            if not authorized_expected or row.get("expected_value") != authorized_expected:
                err(errors, "LST-READBACK-016", f"{path}.expected_value", "must exactly cover the authorized child change set")
            if row.get("live_pass") is not True:
                err(errors, "LST-READBACK-013", f"{path}.live_pass", "LIVE_MATCH must explicitly set live_pass=true")
            if evidence is None or evidence.get("type") not in LIVE_EVIDENCE_TYPES:
                err(errors, "LST-READBACK-014", f"{path}.evidence_ref", "LIVE_MATCH requires public/frontend readback evidence")
            observed_at = parse_timestamp(row.get("observed_at"))
            authorized_at = parse_timestamp(auth.get("authorized_at"))
            if observed_at is not None and authorized_at is not None and observed_at < authorized_at:
                err(errors, "LST-READBACK-017", f"{path}.observed_at", "live evidence cannot predate authorization")
            live_match_children.add(child)
        else:
            if row.get("live_pass") is True:
                err(errors, "LST-READBACK-005", path, "backend accepted/unknown/mismatch cannot be LIVE_PASS")
            if status == "LIVE_MISMATCH" and (
                not nonempty(row.get("expected_value"))
                or not nonempty(row.get("observed_value"))
                or row.get("expected_value") == row.get("observed_value")
            ):
                err(errors, "LST-READBACK-015", path, "LIVE_MISMATCH requires two distinct values")
            if status == "LIVE_MISMATCH":
                authorized_expected = canonical_child_readback_value(change_objects, child)
                if not authorized_expected or row.get("expected_value") != authorized_expected:
                    err(errors, "LST-READBACK-016", f"{path}.expected_value", "must exactly cover the authorized child change set")
    if bundle.get("project", {}).get("conclusion") == "LIVE_PASS":
        if live_match_children != intended or seen_children != intended or len(readbacks) != len(intended):
            err(errors, "LST-READBACK-006", "live_readback", "every intended child needs exactly one independent LIVE_MATCH")
