#!/usr/bin/env python3
"""Pure publication-envelope and frontend-readback reports for A+ bundles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from aplus_entry_domain import (
    authorization_action_issues,
    authorization_target_issue,
    authorization_time_issues,
    publication_entry_issues,
)


AMAZON_SUFFIXES = {
    "com", "ca", "de", "fr", "it", "es", "nl", "pl", "se", "sg", "in",
    "ae", "sa", "be", "co.uk", "co.jp", "com.au", "com.br", "com.mx", "com.tr",
}
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2}))?$"
)


@dataclass(frozen=True)
class PublicationReport:
    errors: tuple[str, ...]


@dataclass(frozen=True)
class ReadbackRowReport:
    errors: tuple[str, ...]
    key: tuple[str, str, str]
    is_first_readback: bool
    declares_pass: bool


@dataclass(frozen=True)
class ReadbackCoverageReport:
    errors: tuple[str, ...]


def build_publication_report(
    *,
    mode: str,
    write_scope: str,
    identity_status: str,
    scope_status: str,
    authorization_status: str,
    authorized_at: datetime | None,
    expires_at: datetime | None,
    snapshot_at: datetime | None,
    validation_at: datetime,
    systems: set[str],
    marketplaces: set[str],
    locales: set[str],
    content_ids: set[str],
    child_asins: set[str],
    actions: set[str],
    expected_marketplace: str,
    expected_locale: str,
    expected_content_ids: set[str],
    expected_child_asins: set[str],
    allowed_actions: set[str],
) -> PublicationReport:
    """Derive publication-envelope blockers using an explicitly injected clock."""
    issues: list[str] = []
    issues.extend(publication_entry_issues(
        mode=mode,
        write_scope=write_scope,
        identity_status=identity_status,
        scope_status=scope_status,
        authorization_status=authorization_status,
    ))
    issues.extend(authorization_time_issues(
        authorized_at=authorized_at,
        expires_at=expires_at,
        snapshot_at=snapshot_at,
        validation_at=validation_at,
    ))
    if not any(system.casefold() == "seller central" for system in systems):
        issues.append(
            "[A-AUTH-003] $.publish_authorization.systems: publish_support requires explicit Seller Central authority"
        )
    target_issue = authorization_target_issue(
        marketplaces=marketplaces,
        locales=locales,
        content_ids=content_ids,
        child_asins=child_asins,
        expected_marketplace=expected_marketplace,
        expected_locale=expected_locale,
        expected_content_ids=expected_content_ids,
        expected_child_asins=expected_child_asins,
    )
    if target_issue:
        issues.append(target_issue)
    issues.extend(authorization_action_issues(actions, allowed_actions))
    return PublicationReport(tuple(sorted(issues)))


def _parse_iso_moment(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value or not ISO_RE.fullmatch(value):
        return None
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc)
        parsed_date = date.fromisoformat(value)
        return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
    except ValueError:
        return None


def _amazon_product_asin(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    host = parsed.hostname.lower().rstrip(".")
    retail_suffix = ""
    for prefix in ("www.amazon.", "amazon."):
        if host.startswith(prefix):
            retail_suffix = host[len(prefix):]
            break
    if retail_suffix not in AMAZON_SUFFIXES:
        return ""
    path = parsed.path.rstrip("/")
    if "/dp/" not in path and "/gp/product/" not in path:
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    for marker in ("dp", "product"):
        for index, part in enumerate(parts[:-1]):
            if part.casefold() == marker:
                candidate = parts[index + 1].upper()
                return candidate if ASIN_RE.fullmatch(candidate) else ""
    return ""


def build_readback_row_report(
    *,
    path: str,
    phase: str,
    child_asin: str,
    marketplace: str,
    locale: str,
    expected_content_id: str,
    observed_content_id: str,
    checked_at: datetime | None,
    fetch_status: str,
    field_statuses: set[str],
    evidence_source_ids: set[str],
    status: str,
    mismatch_action: str,
    followup_required: bool,
    expected_content_by_key: Mapping[tuple[str, str, str], str],
    source_map: Mapping[str, Mapping[str, Any]],
    source_scopes: Mapping[str, Mapping[str, Any]],
) -> ReadbackRowReport:
    """Evaluate one observed child/locale row without reading the frontend."""
    issues: list[str] = []
    key = (child_asin, marketplace, locale)
    if key not in expected_content_by_key:
        issues.append(f"{path}: readback target outside intended variants")
    if key in expected_content_by_key and expected_content_id != expected_content_by_key[key]:
        issues.append(f"{path}.expected_content_id: does not match intended A+ content ID")

    if status == "PASS":
        if fetch_status != "ok" or not evidence_source_ids or field_statuses - {"PASS", "NOT_APPLICABLE"}:
            issues.append(
                f"{path}: PASS requires readable evidence and all field checks PASS/NOT_APPLICABLE"
            )
        live_sources = []
        for source_id in evidence_source_ids:
            source = source_map.get(source_id, {})
            source_scope = source_scopes.get(source_id, {})
            observed_at = _parse_iso_moment(source.get("observed_at"))
            source_url = str(source.get("path_or_url", ""))
            if (
                source.get("source_type") == "PUBLIC_OBSERVED"
                and source.get("fetch_status") == "ok"
                and _amazon_product_asin(source_url) == child_asin
                and child_asin in source_scope.get("child_asins", set())
                and marketplace in source_scope.get("marketplaces", set())
                and locale in source_scope.get("locales", set())
                and checked_at is not None
                and observed_at == checked_at
            ):
                live_sources.append(source)
        if not live_sources:
            issues.append(
                f"[A-READBACK-001] {path}.evidence_source_ids: PASS requires same-child, "
                "same-check-time Amazon PDP evidence; local, stale, or cross-child "
                "PUBLIC_OBSERVED evidence is insufficient"
            )
        if observed_content_id != expected_content_id or followup_required:
            issues.append(f"{path}: PASS requires matching content ID and no follow-up")
    if fetch_status != "ok" or field_statuses & {"MISMATCH", "NOT_VISIBLE", "FETCH_BLOCKED"}:
        if (
            not followup_required
            or not mismatch_action
            or status not in {"MISMATCH", "BLOCKED", "FOLLOWUP_REQUIRED", "PARTIAL"}
        ):
            issues.append(
                f"{path}: blocked/mismatched observation requires follow-up, action, and non-PASS status"
            )
    return ReadbackRowReport(
        tuple(sorted(issues)), key, phase == "FIRST_READBACK", status == "PASS",
    )


def build_readback_coverage_report(
    *,
    intended_keys: set[tuple[str, str, str]],
    first_readback_keys: set[tuple[str, str, str]],
    pass_keys: set[tuple[str, str, str]],
    conclusion: str,
) -> ReadbackCoverageReport:
    """Require complete first-readback and terminal PASS coverage."""
    issues: list[str] = []
    if first_readback_keys != intended_keys:
        issues.append(
            "$.live_readback: FIRST_READBACK must exactly cover every intended child/locale"
        )
    if conclusion == "PASS" and pass_keys != intended_keys:
        issues.append(
            "$.live_readback: project PASS requires resolved PASS readback for every child/locale"
        )
    return ReadbackCoverageReport(tuple(issues))
