#!/usr/bin/env python3
"""Pure publication authorization and authoritative readback phase for Listing v1.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from listing_v11_domains import evaluate_publication
from listing_v11_phase import PhaseDelta, _err, _obj_list


@dataclass(frozen=True)
class PublicationReport:
    delta: PhaseDelta


def validate_publication_readback_domain(
    bundle: dict[str, Any],
    *,
    boundary: Any,
    project: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    field_index: dict[str, dict[str, Any]],
    fact_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
    strict_validator: Callable[..., None],
) -> PublicationReport:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    gates: dict[str, str] = {}
    validate_publication_strict = strict_validator
    authorization = bundle.get("publish_authorization") if isinstance(bundle.get("publish_authorization"), dict) else {}
    if boundary in {"read_only", "local_candidate"}:
        if authorization.get("status") != "NOT_AUTHORIZED":
            _err(errors, "L11-PUBLISH-001", "publish_authorization.status", "read-only/local candidate cannot be authorized")
        if bundle.get("change_set") or bundle.get("rollback") or bundle.get("live_readback"):
            _err(errors, "L11-PUBLISH-002", "$", "read-only/local candidate cannot carry active publication rows")
        gates.update(evaluate_publication(str(boundary), str(authorization.get("status")), set()))
    else:
        if authorization.get("status") != "AUTHORIZED":
            _err(errors, "L11-PUBLISH-003", "publish_authorization.status", "submission boundary requires exact authorization")
        statuses = {row.get("status") for row in _obj_list(bundle.get("live_readback"), "live_readback", errors)}
        gates.update(evaluate_publication(str(boundary), str(authorization.get("status")), statuses))
    if project.get("conclusion") == "LIVE_PASS" and gates["live"] != "PASS":
        _err(errors, "L11-READBACK-001", "project.conclusion", "LIVE_PASS requires per-child LIVE_MATCH")

    strict_publication_errors: list[str] = []
    strict_publication_warnings: list[str] = []
    validate_publication_strict(
        bundle,
        source_index,
        field_index,
        fact_index,
        claim_index,
        strict_publication_errors,
        strict_publication_warnings,
    )
    errors.extend(strict_publication_errors)
    warnings.extend(strict_publication_warnings)
    if strict_publication_errors and boundary in {"authorized_submission", "rollback_only"}:
        gates["publication"] = "BLOCKED"
        gates["backend"] = "NOT_RUN"
        gates["live"] = "NOT_RUN"

    return PublicationReport(
        delta=PhaseDelta.capture(errors, warnings, counts, gates),
    )
