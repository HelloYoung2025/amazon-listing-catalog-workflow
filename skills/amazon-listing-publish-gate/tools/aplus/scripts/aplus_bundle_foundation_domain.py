#!/usr/bin/env python3
"""Pure foundation/evidence phase for the A+ bundle validator."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class FoundationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    source_map: dict[str, dict[str, Any]]
    source_scopes: dict[str, dict[str, Any]]
    limits: dict[str, Any]
    alt_max: int | None
    available_module_types: set[str]
    content_eligibility: str
    facts_raw: list[Any]
    fact_map: dict[str, dict[str, Any]]
    fact_scopes: dict[str, dict[str, Any]]
    claims_raw: list[Any]
    claim_map: dict[str, dict[str, Any]]
    claim_scopes: dict[str, dict[str, Any]]


def validate_foundation(
    root: dict[str, Any], *, schema_version: str, marketplace: str, locale: str,
    target_type: str, identity_status: str, verified_child: str, conclusion: str,
    focal_source_ids: set[str], scope_source_ids: set[str], scope_status: str,
    envelope: dict[str, Any], ops: Mapping[str, Any],
) -> FoundationReport:
    errors: list[str] = []
    warnings: list[str] = []
    require_mapping=ops["require_mapping"]
    require_list=ops["require_list"]; unique_rows=ops["unique_rows"]
    require_enum=ops["require_enum"]; require_text=ops["require_text"]
    validate_app_scope=ops["validate_app_scope"]; is_text=ops["is_text"]
    require_string=ops["require_string"]; string_set=ops["string_set"]
    check_iso=ops["check_iso"]; ensure_scope_subset=ops["ensure_scope_subset"]
    require_complete_scope=ops["require_complete_scope"]
    is_official_amazon_url=ops["is_official_amazon_url"]
    build_fact_evidence_report=ops["build_fact_evidence_report"]
    SOURCE_TYPES=ops["SOURCE_TYPES"]; FETCH_STATUSES=ops["FETCH_STATUSES"]
    MIRROR_SOURCE_TYPES=ops["MIRROR_SOURCE_TYPES"]
    CONTENT_ELIGIBILITY=ops["CONTENT_ELIGIBILITY"]
    EVIDENCE_TYPES=ops["EVIDENCE_TYPES"]; FACT_CLASSES=ops["FACT_CLASSES"]
    EVIDENCE_STRENGTHS=ops["EVIDENCE_STRENGTHS"]
    PUBLISH_STATUSES=ops["PUBLISH_STATUSES"]; RISK_TYPES=ops["RISK_TYPES"]
    CONTENT_STATUSES=ops["CONTENT_STATUSES"]
    FINAL_CONTENT_STATUSES=ops["FINAL_CONTENT_STATUSES"]
    UNSUPPORTED_CONSUMER_EVIDENCE=ops["UNSUPPORTED_CONSUMER_EVIDENCE"]
    HIGH_RISK_TYPES=ops["HIGH_RISK_TYPES"]
    sources_raw = require_list(root, "sources", "$", errors)
    source_map = unique_rows(sources_raw, "$.sources", errors)
    source_scopes: dict[str, dict[str, Any]] = {}
    for source_id, source in source_map.items():
        path = f"$.sources[{source_id}]"
        source_type = require_enum(source, "source_type", path, SOURCE_TYPES, errors)
        require_text(source, "path_or_url", path, errors)
        source_scope = validate_app_scope(source.get("scope"), f"{path}.scope", errors)
        source_scopes[source_id] = source_scope
        if source_scope["marketplaces"] and not source_scope["marketplaces"].issubset(envelope["marketplaces"]):
            errors.append(f"{path}.scope.marketplace: outside task marketplace")
        if source_scope["locales"] and not source_scope["locales"].issubset(envelope["locales"]):
            errors.append(f"{path}.scope.locale: outside task locale")
        observed = require_text(source, "observed_at", path, errors)
        check_iso(observed, f"{path}.observed_at", errors)
        fetch_status = require_enum(source, "fetch_status", path, FETCH_STATUSES, errors)
        if fetch_status in {"blocked", "missing_attachment", "described_not_available", "skipped_by_scope"} and not is_text(source.get("block_reason")):
            warnings.append(f"{path}.block_reason: explain why the source was unavailable or omitted")
        require_string(source, "block_reason", path, errors)
        string_set(require_list(source, "can_establish", path, errors), f"{path}.can_establish", errors)
        string_set(require_list(source, "cannot_establish", path, errors), f"{path}.cannot_establish", errors)
        require_text(source, "owner", path, errors)
        if schema_version == "1.3" and source_type in MIRROR_SOURCE_TYPES:
            require_text(source, "mirror_system", path, errors)
            require_text(source, "mirror_snapshot_id", path, errors)
            string_set(
                require_list(source, "mirror_limitations", path, errors),
                f"{path}.mirror_limitations", errors, nonempty=True,
            )

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

    check_refs(scope_source_ids, "$.scope.source_ids", usable=scope_status == "FROZEN")
    check_refs(focal_source_ids, "$.project.focal_identity.verification_source_ids", usable=identity_status in {"VERIFIED_PARENT", "VERIFIED_CHILD"})
    if identity_status == "VERIFIED_CHILD":
        if not verified_child:
            errors.append("$.project.focal_identity.verified_focal_child: required for VERIFIED_CHILD")
        if not focal_source_ids:
            errors.append("$.project.focal_identity.verification_source_ids: verified identity requires evidence")
    elif verified_child:
        errors.append("$.project.focal_identity.verified_focal_child: cannot be populated unless identity_status=VERIFIED_CHILD")
    if target_type != "live_asin" and verified_child:
        errors.append("$.project.focal_identity.verified_focal_child: non-ASIN target cannot claim a verified child")
    if conclusion == "PASS" and (target_type != "live_asin" or identity_status != "VERIFIED_CHILD"):
        errors.append("$.project.conclusion: PASS requires a live target with VERIFIED_CHILD identity")

    limits = require_mapping(root.get("platform_limits"), "$.platform_limits", errors)
    alt_max = limits.get("alt_max_chars")
    if not isinstance(alt_max, int) or isinstance(alt_max, bool) or alt_max <= 0:
        errors.append("$.platform_limits.alt_max_chars: required positive integer")
        alt_max = None
    for key in ("basic_max_modules", "premium_max_modules"):
        value = limits.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(f"$.platform_limits.{key}: required positive integer")
    available_module_types = string_set(require_list(limits, "available_module_types", "$.platform_limits", errors), "$.platform_limits.available_module_types", errors)
    content_eligibility = require_enum(limits, "content_type_eligibility", "$.platform_limits", CONTENT_ELIGIBILITY, errors)
    verified_at = require_text(limits, "last_verified_at", "$.platform_limits", errors)
    check_iso(verified_at, "$.platform_limits.last_verified_at", errors)
    limit_source_ids = string_set(require_list(limits, "source_ids", "$.platform_limits", errors), "$.platform_limits.source_ids", errors, nonempty=True)
    legacy_limit_source = require_string(limits, "source_id", "$.platform_limits", errors)
    if legacy_limit_source and legacy_limit_source not in limit_source_ids:
        errors.append("$.platform_limits.source_id: legacy source_id must also appear in source_ids")
    check_refs(limit_source_ids, "$.platform_limits.source_ids", usable=True, allowed_types={"OFFICIAL_PLATFORM_RULE"})
    for source_id in limit_source_ids:
        source = source_map.get(source_id)
        if source and not is_official_amazon_url(str(source.get("path_or_url", ""))):
            errors.append(f"$.platform_limits.source_ids: source {source_id!r} is not an official Amazon HTTPS rule URL")

    facts_raw = require_list(root, "facts", "$", errors)
    fact_map = unique_rows(facts_raw, "$.facts", errors)
    fact_scopes: dict[str, dict[str, Any]] = {}
    for fact_id, fact in fact_map.items():
        path = f"$.facts[{fact_id}]"
        require_text(fact, "statement", path, errors)
        fact_scope = validate_app_scope(fact.get("scope"), f"{path}.scope", errors)
        fact_scopes[fact_id] = fact_scope
        ensure_scope_subset(fact_scope, envelope, f"{path}.scope", "top-level envelope", errors)
        evidence_type = require_enum(fact, "evidence_type", path, EVIDENCE_TYPES, errors)
        fact_class = require_enum(fact, "fact_class", path, FACT_CLASSES, errors) if schema_version == "1.3" else "UNCLASSIFIED"
        strength = require_enum(fact, "evidence_strength", path, EVIDENCE_STRENGTHS, errors)
        publish_status = require_enum(fact, "publish_status", path, PUBLISH_STATUSES, errors)
        observed = require_text(fact, "observed_at", path, errors)
        check_iso(observed, f"{path}.observed_at", errors)
        require_text(fact, "owner", path, errors)
        source_ids = string_set(require_list(fact, "source_ids", path, errors), f"{path}.source_ids", errors, nonempty=True)
        proving_ids = string_set(require_list(fact, "proving_source_ids", path, errors), f"{path}.proving_source_ids", errors)
        check_refs(source_ids, f"{path}.source_ids")
        if not proving_ids.issubset(source_ids):
            errors.append(f"{path}.proving_source_ids: must be a subset of source_ids")
        if publish_status == "PUBLISHABLE":
            require_complete_scope(fact_scope, envelope, f"{path}.scope", errors, require_child=target_type == "live_asin")
            if strength not in {"E3", "E4"}:
                errors.append(f"{path}: publishable fact requires E3 or E4")
            if not proving_ids:
                errors.append(f"{path}.proving_source_ids: publishable fact requires at least one proving source")
        for source_id in proving_ids:
            source = source_map.get(source_id)
            if source is None:
                errors.append(f"{path}.proving_source_ids: unknown source id {source_id!r}")
                continue
            if source.get("fetch_status") != "ok":
                errors.append(f"{path}.proving_source_ids: source {source_id!r} is not usable")
            if source.get("source_type") != evidence_type:
                errors.append(f"{path}.proving_source_ids: source {source_id!r} type does not match evidence_type")
            ensure_scope_subset(fact_scope, source_scopes[source_id], f"{path}.scope", f"proving source {source_id!r}", errors)
        proving_types = {
            str(source_map[source_id].get("source_type", ""))
            for source_id in proving_ids if source_id in source_map
        }
        evidence_report = build_fact_evidence_report(
            schema_version=schema_version,
            fact_id=fact_id,
            fact_class=fact_class,
            publish_status=publish_status,
            proving_types=proving_types,
        )
        errors.extend(evidence_report.errors)

    claims_raw = require_list(root, "claims", "$", errors)
    claim_map = unique_rows(claims_raw, "$.claims", errors)
    claim_scopes: dict[str, dict[str, Any]] = {}
    for claim_id, claim in claim_map.items():
        path = f"$.claims[{claim_id}]"
        require_text(claim, "text", path, errors)
        claim_scope = validate_app_scope(claim.get("scope"), f"{path}.scope", errors)
        claim_scopes[claim_id] = claim_scope
        ensure_scope_subset(claim_scope, envelope, f"{path}.scope", "top-level envelope", errors)
        risk_type = require_enum(claim, "risk_type", path, RISK_TYPES, errors, lower=True)
        publish_status = require_enum(claim, "publish_status", path, PUBLISH_STATUSES, errors)
        content_status = require_enum(claim, "content_status", path, CONTENT_STATUSES, errors)
        require_text(claim, "owner", path, errors)
        consumer_facing = claim.get("consumer_facing")
        if not isinstance(consumer_facing, bool):
            errors.append(f"{path}.consumer_facing: required boolean")
            consumer_facing = False
        fact_ids = string_set(require_list(claim, "fact_ids", path, errors), f"{path}.fact_ids", errors)
        facts: list[dict[str, Any]] = []
        for fact_id in fact_ids:
            fact = fact_map.get(fact_id)
            if fact is None:
                errors.append(f"{path}.fact_ids: unknown fact id {fact_id!r}")
                continue
            facts.append(fact)
            ensure_scope_subset(claim_scope, fact_scopes[fact_id], f"{path}.scope", f"fact {fact_id!r}", errors)
        if consumer_facing:
            require_complete_scope(claim_scope, envelope, f"{path}.scope", errors, require_child=target_type == "live_asin")
            if publish_status != "PUBLISHABLE":
                errors.append(f"{path}: consumer-facing claim must be PUBLISHABLE")
            if not fact_ids:
                errors.append(f"{path}.fact_ids: consumer-facing claim requires facts")
            for fact in facts:
                if fact.get("publish_status") != "PUBLISHABLE":
                    errors.append(f"{path}: references non-publishable fact {fact.get('id')!r}")
                if fact.get("evidence_type") in UNSUPPORTED_CONSUMER_EVIDENCE:
                    errors.append(f"{path}: unsupported consumer evidence {fact.get('evidence_type')!r}")
            if risk_type in HIGH_RISK_TYPES and not any(fact.get("evidence_strength") == "E4" for fact in facts):
                errors.append(f"{path}: high-risk consumer claim requires applicable E4 evidence")
        if content_status in FINAL_CONTENT_STATUSES and publish_status != "PUBLISHABLE":
            errors.append(f"{path}.content_status: final content cannot carry a non-publishable claim")

    return FoundationReport(
        tuple(errors), tuple(warnings), source_map, source_scopes, limits, alt_max,
        available_module_types, content_eligibility, facts_raw, fact_map,
        fact_scopes, claims_raw, claim_map, claim_scopes,
    )
