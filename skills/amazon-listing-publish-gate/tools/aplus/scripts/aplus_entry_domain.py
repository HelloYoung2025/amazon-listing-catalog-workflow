#!/usr/bin/env python3
"""Pure A+ entry, legacy-reference, and publication decisions.

These helpers perform no file or network I/O and do not mutate inputs.  The
CLI and local-reference adapters own operating-system interaction.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def local_parent_reference_issue(reference: str) -> str | None:
    """Return a deterministic issue for a non-local or malformed reference."""
    if not isinstance(reference, str) or not reference.strip():
        return "parent_bundle_ref must name a local JSON file"
    try:
        parsed = urlsplit(reference)
    except ValueError as exc:
        return f"[A-IO-REF-001] parent_bundle_ref is malformed: {exc}"
    if parsed.scheme or parsed.netloc:
        return "parent_bundle_ref must name a local JSON file, not a URL"
    return None


def required_pass_gate_ids(mode: str, has_experiments: bool) -> tuple[str, ...]:
    """Return the ordered gate denominator for a project conclusion."""
    gate_ids = ["G0", "G1", "G2", "G3", "G4"]
    if mode == "publish_support":
        gate_ids.append("G5")
    if has_experiments:
        gate_ids.append("G6")
    return tuple(gate_ids)


def publication_entry_issues(
    *,
    mode: str,
    write_scope: str,
    identity_status: str,
    scope_status: str,
    authorization_status: str,
) -> tuple[str, ...]:
    """Return publication-entry blockers without inspecting mutable bundle state."""
    if mode != "publish_support":
        return ()
    issues: list[str] = []
    if write_scope != "explicit_write":
        issues.append("$.project.write_scope: publish_support requires explicit_write")
    if identity_status != "VERIFIED_CHILD" or scope_status != "FROZEN":
        issues.append("$.project: publish_support requires VERIFIED_CHILD identity and FROZEN scope")
    if authorization_status != "AUTHORIZED":
        issues.append("$.publish_authorization.status: publish_support requires AUTHORIZED")
    return tuple(issues)


def authorization_time_issues(
    *,
    authorized_at: datetime | None,
    expires_at: datetime | None,
    snapshot_at: datetime | None,
    validation_at: datetime,
) -> tuple[str, ...]:
    """Evaluate the closed authorization time window using an injected clock."""
    issues: list[str] = []
    if authorized_at is not None and expires_at is not None and expires_at <= authorized_at:
        issues.append("[A-AUTH-001] $.publish_authorization.expires_at: must be later than authorized_at")
    if expires_at is not None and snapshot_at is not None and expires_at < snapshot_at:
        issues.append("[A-AUTH-002] $.publish_authorization.expires_at: authorization is expired at the project snapshot")
    if expires_at is not None and expires_at <= validation_at:
        issues.append("[A-AUTH-004] $.publish_authorization.expires_at: authorization has expired at validation time")
    return tuple(issues)


def authorization_target_issue(
    *,
    marketplaces: set[str],
    locales: set[str],
    content_ids: set[str],
    child_asins: set[str],
    expected_marketplace: str,
    expected_locale: str,
    expected_content_ids: set[str],
    expected_child_asins: set[str],
) -> str | None:
    """Require exact authorized targets; no child, locale, or content expansion."""
    if (
        marketplaces != {expected_marketplace}
        or locales != {expected_locale}
        or content_ids != expected_content_ids
        or child_asins != expected_child_asins
    ):
        return "$.publish_authorization: marketplace/locale/content/child targets must exactly match intended publish scope"
    return None


def authorization_action_issues(
    actions: set[str],
    allowed_actions: set[str],
) -> tuple[str, ...]:
    """Validate the explicit closed action set for a publication envelope."""
    issues: list[str] = []
    unsupported = actions - allowed_actions
    if unsupported:
        issues.append(f"$.publish_authorization.allowed_actions: unsupported values {sorted(unsupported)!r}")
    if not {"submit", "apply"}.issubset(actions):
        issues.append("$.publish_authorization.allowed_actions: explicit submit and apply authority required")
    return tuple(issues)


def derive_result_level(
    *,
    schema_version: str,
    has_errors: bool,
    mode: str,
    conclusion: str,
    component_result: Any,
) -> str:
    """Derive the non-authorizing validator result without trusting the bundle."""
    if has_errors:
        return "INVALID"
    if schema_version in {"1.1", "1.2"}:
        return "LEGACY_LOCAL_CONTRACT"
    if schema_version == "1.3" and mode == "publish_support" and conclusion == "PASS":
        return "LIVE_VERIFIED"
    if schema_version == "1.3":
        return str(component_result or "LOCAL_CONTRACT_PASS")
    return "LOCAL_CONTRACT_PASS"


def validator_exit_code(result: Any) -> int:
    """Map a validator result to the stable contract-valid/invalid exit code."""
    if isinstance(result, dict) and any(
        "[A-IO-REF-001]" in str(issue) for issue in result.get("errors", [])
    ):
        return 2
    return 0 if isinstance(result, dict) and result.get("ok") is True else 1


def migration_path_issue(source: Path, output: Path, report: Path) -> str | None:
    """Return the precise collision reason before any migration write occurs."""
    if output == source:
        return "migration output must not overwrite the input bundle"
    if report == source:
        return "migration report must not overwrite the input bundle"
    if output == report:
        return "migration output and report must be different files"
    return None
