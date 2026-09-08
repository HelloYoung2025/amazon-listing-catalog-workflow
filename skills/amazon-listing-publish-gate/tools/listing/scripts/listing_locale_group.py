#!/usr/bin/env python3
"""Pure multi-locale semantic checks for the sole Listing package coordinator."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any


GROUP_CONTRACT_VERSION = "listing-locale-group/1.1"
GROUP_MANIFEST_KEYS = {"contract_version", "group_id", "marketplace", "members"}
GROUP_MEMBER_KEYS = {"locale", "parent_bundle", "aplus_bundle", "coordination_ledger"}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _objects(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _index(value: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _objects(value):
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id:
            result[row_id] = row
    return result


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str) and item})


def _text(value: Any) -> str:
    return unicodedata.normalize("NFC", str(value if value is not None else ""))


def _semantic_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _semantic_value(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        normalized = [_semantic_value(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, str):
        return _text(value)
    return value


def _scope_values(scope: Any, key: str) -> list[str]:
    if not isinstance(scope, dict):
        return []
    aliases = {
        "sizes": ("sizes", "sizes_or_capacities"),
        "child_asins": ("child_asins", "intended_child_asins"),
        "parent_asins": ("parent_asins", "parent_asin"),
        "marketplaces": ("marketplaces", "marketplace"),
        "locales": ("locales", "locale"),
    }
    for candidate in aliases.get(key, (key,)):
        value = scope.get(candidate)
        if isinstance(value, list):
            return sorted({_text(item) for item in value if _text(item)})
        if isinstance(value, str) and value:
            return [_text(value)]
    return []


def _other_variants(scope: Any) -> dict[str, list[str]]:
    if not isinstance(scope, dict):
        return {}
    raw_dimensions = scope.get("other_variants")
    if not isinstance(raw_dimensions, dict):
        raw_dimensions = scope.get("other_dimensions")
    if not isinstance(raw_dimensions, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, raw in sorted(raw_dimensions.items()):
        values = raw if isinstance(raw, list) else [raw]
        normalized = sorted({
            _text(item).strip() for item in values
            if _text(item).strip().casefold() not in {"", "n/a", "not applicable", "none"}
        })
        if normalized:
            result[str(key)] = normalized
    return result


def _scope_projection(scope: Any, marketplace: str) -> dict[str, Any]:
    """Project semantic scope while intentionally removing only locale identity."""
    return {
        "marketplaces": _scope_values(scope, "marketplaces") or [_text(marketplace)],
        "parent_asins": _scope_values(scope, "parent_asins"),
        "child_asins": _scope_values(scope, "child_asins"),
        "packs": _scope_values(scope, "packs"),
        "colors": _scope_values(scope, "colors"),
        "sizes": _scope_values(scope, "sizes"),
        "other_variants": _other_variants(scope),
    }


def _record_projection(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _semantic_value(row.get(field)) for field in fields}


def _variant_projection(rows: Any, marketplace: str) -> list[dict[str, str]]:
    projected: list[dict[str, str]] = []
    for row in _objects(rows):
        projected.append({
            "id": _text(row.get("id")),
            "marketplace": _text(row.get("marketplace") or marketplace),
            "parent_asin": _text(row.get("parent_asin")),
            "child_asin": _text(row.get("child_asin")),
            "pack": _text(row.get("pack")),
            "color": _text(row.get("color")),
            "size": _text(row.get("size_or_capacity", row.get("size"))),
            "other_variant": _text(row.get("other_variant")),
        })
    return sorted(projected, key=lambda row: row["id"])


def _requirement_scope_projection(rows: Any, marketplace: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in _objects(rows):
        result.append({
            "id": _text(row.get("id")),
            "priority": _text(row.get("priority")),
            "scope": _scope_projection(row.get("application_scope"), marketplace),
        })
    return sorted(result, key=lambda row: row["id"])


def _atom_projection(rows: Any, marketplace: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for row in _objects(rows):
        result.append({
            "id": _text(row.get("id")),
            "requirement_id": _text(row.get("requirement_id")),
            "marketplace": _text(row.get("marketplace") or marketplace),
            "variant_row_id": _text(row.get("variant_row_id")),
        })
    return sorted(result, key=lambda row: (row["id"], row["requirement_id"], row["variant_row_id"]))


def _member_scope_projection(
    parent: dict[str, Any], aplus: dict[str, Any], marketplace: str,
) -> dict[str, Any]:
    parent_handoff = parent.get("enriched_content_handoff") if isinstance(parent.get("enriched_content_handoff"), dict) else {}
    child_handoff = aplus.get("enriched_content_handoff") if isinstance(aplus.get("enriched_content_handoff"), dict) else {}
    parent_map = parent.get("decision_map") if isinstance(parent.get("decision_map"), dict) else {}
    child_map = aplus.get("decision_map") if isinstance(aplus.get("decision_map"), dict) else {}
    parent_denominator = parent.get("decision_denominator_snapshot") if isinstance(parent.get("decision_denominator_snapshot"), dict) else {}
    child_denominator = aplus.get("decision_denominator_snapshot") if isinstance(aplus.get("decision_denominator_snapshot"), dict) else {}
    return {
        "parent_scope": _scope_projection(parent.get("scope"), marketplace),
        "parent_handoff_scope": _scope_projection(parent_handoff.get("application_scope"), marketplace),
        "aplus_scope": _scope_projection(aplus.get("scope"), marketplace),
        "aplus_handoff_scope": _scope_projection(child_handoff.get("application_scope"), marketplace),
        "parent_variants": _variant_projection(parent.get("variant_topology"), marketplace),
        "aplus_variants": _variant_projection(aplus.get("variants"), marketplace),
        "parent_requirement_scopes": _requirement_scope_projection(parent_map.get("requirements"), marketplace),
        "aplus_requirement_scopes": _requirement_scope_projection(child_map.get("requirements"), marketplace),
        "parent_atoms": _atom_projection(parent_denominator.get("atoms"), marketplace),
        "aplus_atoms": _atom_projection(child_denominator.get("atoms"), marketplace),
    }


PARENT_FACT_FIELDS = (
    "statement", "verification_status", "content_status", "evidence_level",
    "can_prove", "cannot_prove", "allowed_expression", "prohibited_inferences",
    "refresh_trigger",
)
PARENT_CLAIM_FIELDS = (
    "text", "fact_ids", "support_status", "content_status", "evidence_level",
    "can_prove", "cannot_prove", "allowed_expression", "prohibited_inferences",
    "refresh_trigger",
)
APLUS_FACT_FIELDS = (
    "statement", "fact_class", "evidence_type", "evidence_strength", "publish_status",
)
APLUS_CLAIM_FIELDS = (
    "text", "fact_ids", "risk_type", "consumer_facing", "content_status", "publish_status",
)


def validate_group_manifest(manifest: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {
            "valid": False,
            "errors": ["[PKG-GROUP-MANIFEST-001] manifest must be a JSON object"],
            "members": [],
        }
    if set(manifest) != GROUP_MANIFEST_KEYS:
        errors.append(
            "[PKG-GROUP-MANIFEST-001] manifest must contain exactly "
            f"{sorted(GROUP_MANIFEST_KEYS)!r}; hashes, PASS flags, and other self-attestations are forbidden"
        )
    if manifest.get("contract_version") != GROUP_CONTRACT_VERSION:
        errors.append(
            f"[PKG-GROUP-MANIFEST-002] contract_version must be {GROUP_CONTRACT_VERSION!r}"
        )
    if not isinstance(manifest.get("group_id"), str) or not manifest.get("group_id", "").strip():
        errors.append("[PKG-GROUP-MANIFEST-003] group_id must be a non-empty string")
    if not isinstance(manifest.get("marketplace"), str) or not manifest.get("marketplace", "").strip():
        errors.append("[PKG-GROUP-MANIFEST-004] marketplace must be a non-empty string")
    raw_members = manifest.get("members")
    if not isinstance(raw_members, list) or len(raw_members) < 2:
        errors.append("[PKG-GROUP-MANIFEST-005] at least two locale members are required")
        raw_members = raw_members if isinstance(raw_members, list) else []
    members: list[dict[str, str]] = []
    locales: list[str] = []
    path_tokens: list[str] = []
    for index, raw in enumerate(raw_members):
        path = f"members[{index}]"
        if not isinstance(raw, dict) or set(raw) != GROUP_MEMBER_KEYS:
            errors.append(
                f"[PKG-GROUP-MANIFEST-006] {path} must contain exactly {sorted(GROUP_MEMBER_KEYS)!r}"
            )
            continue
        normalized: dict[str, str] = {}
        for key in sorted(GROUP_MEMBER_KEYS):
            value = raw.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"[PKG-GROUP-MANIFEST-006] {path}.{key} must be a non-empty string")
                normalized[key] = ""
            else:
                normalized[key] = value.strip()
        members.append(normalized)
        if normalized.get("locale"):
            locales.append(normalized["locale"])
        for key in ("parent_bundle", "aplus_bundle", "coordination_ledger"):
            if normalized.get(key):
                path_tokens.append(normalized[key])
    if len(set(locales)) != len(locales) or len(set(locales)) < 2:
        errors.append("[PKG-GROUP-MANIFEST-007] members require at least two unique locales")
    if len(set(path_tokens)) != len(path_tokens):
        errors.append("[PKG-GROUP-MANIFEST-008] manifest bundle path strings must be unique")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "members": sorted(members, key=lambda row: row.get("locale", "")),
    }


def _context_errors(
    locale: str,
    marketplace: str,
    parent: dict[str, Any],
    aplus: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    parent_scope = parent.get("scope") if isinstance(parent.get("scope"), dict) else {}
    parent_handoff = parent.get("enriched_content_handoff") if isinstance(parent.get("enriched_content_handoff"), dict) else {}
    child_handoff = aplus.get("enriched_content_handoff") if isinstance(aplus.get("enriched_content_handoff"), dict) else {}
    project = aplus.get("project") if isinstance(aplus.get("project"), dict) else {}
    workflow = aplus.get("workflow_context") if isinstance(aplus.get("workflow_context"), dict) else {}
    child_scope = aplus.get("scope") if isinstance(aplus.get("scope"), dict) else {}
    expected_locale = [locale]
    expected_marketplace = [marketplace]
    checks = (
        ("parent.scope.locale", _scope_values(parent_scope, "locales"), expected_locale),
        ("parent.scope.marketplace", _scope_values(parent_scope, "marketplaces"), expected_marketplace),
        ("parent.handoff.locale", _scope_values(parent_handoff, "locales"), expected_locale),
        ("parent.handoff.marketplace", _scope_values(parent_handoff, "marketplaces"), expected_marketplace),
        ("aplus.handoff.locale", _scope_values(child_handoff, "locales"), expected_locale),
        ("aplus.handoff.marketplace", _scope_values(child_handoff, "marketplaces"), expected_marketplace),
        ("aplus.project.locale", _scope_values(project, "locales"), expected_locale),
        ("aplus.project.marketplace", _scope_values(project, "marketplaces"), expected_marketplace),
        ("aplus.scope.locales", _scope_values(child_scope, "locales"), expected_locale),
        ("aplus.scope.marketplaces", _scope_values(child_scope, "marketplaces"), expected_marketplace),
    )
    for label, actual, expected in checks:
        if actual != expected:
            errors.append(
                f"[PKG-GROUP-CONTEXT-001] {locale}: {label}={actual!r}, expected {expected!r}"
            )
    atom_sets = (
        _objects(
            parent.get("decision_denominator_snapshot", {}).get("atoms")
            if isinstance(parent.get("decision_denominator_snapshot"), dict) else []
        ),
        _objects(parent_handoff.get("requirement_atoms")),
        _objects(
            aplus.get("decision_denominator_snapshot", {}).get("atoms")
            if isinstance(aplus.get("decision_denominator_snapshot"), dict) else []
        ),
        _objects(child_handoff.get("requirement_atoms")),
    )
    variants = _objects(aplus.get("variants"))
    if any(
        not rows or any(
            _text(row.get("locale")) != locale or _text(row.get("marketplace")) != marketplace
            for row in rows
        )
        for rows in atom_sets
    ):
        errors.append(f"[PKG-GROUP-CONTEXT-001] {locale}: every parent/delegated atom must match manifest context")
    if not variants or any(
        _text(row.get("locale")) != locale or _text(row.get("marketplace")) != marketplace
        for row in variants
    ):
        errors.append(f"[PKG-GROUP-CONTEXT-001] {locale}: every A+ variant must match manifest context")
    if parent.get("execution_boundary") != "read_only" or workflow.get("execution_boundary") != "read_only" or project.get("write_scope") != "read_only":
        errors.append(f"[PKG-GROUP-AUTH-001] {locale}: locale-group coordination is read_only only")
    return errors


def _family_projection(
    locale: str,
    marketplace: str,
    family_id: str,
    parent: dict[str, Any],
    aplus: dict[str, Any],
) -> tuple[dict[str, Any], str, list[str]]:
    errors: list[str] = []
    parent_assertions = _index(parent.get("canonical_assertions"))
    child_assertions = _index(aplus.get("canonical_assertions"))
    parent_facts = _index(parent.get("facts"))
    parent_claims = _index(parent.get("claims"))
    child_facts = _index(aplus.get("facts"))
    child_claims = _index(aplus.get("claims"))
    variants = _index(aplus.get("variants"))
    parent_assertion = parent_assertions.get(family_id)
    child_assertion = child_assertions.get(family_id)
    if parent_assertion is None or child_assertion is None:
        return {}, "", [f"[PKG-GROUP-FAMILY-001] {locale}: assertion family {family_id!r} is missing"]
    fact_ids = _ids(parent_assertion.get("fact_ids"))
    claim_ids = _ids(parent_assertion.get("claim_ids"))
    if fact_ids != _ids(child_assertion.get("fact_ids")):
        errors.append(f"[PKG-GROUP-FACT-001] {locale}/{family_id}: parent and A+ Fact IDs differ")
    if claim_ids != _ids(child_assertion.get("claim_ids")):
        errors.append(f"[PKG-GROUP-CLAIM-001] {locale}/{family_id}: parent and A+ Claim IDs differ")
    locale_rows = _objects(child_assertion.get("locale_expressions"))
    localized_text = ""
    locale_refs: dict[str, Any] = {}
    if len(locale_rows) != 1 or _text(locale_rows[0].get("locale")) != locale:
        errors.append(
            f"[PKG-GROUP-LOCALE-001] {locale}/{family_id}: exactly one matching locale expression is required"
        )
    else:
        locale_row = locale_rows[0]
        localized_text = _text(locale_row.get("text"))
        locale_refs = {
            "fact_ids": _ids(locale_row.get("fact_ids")),
            "claim_ids": _ids(locale_row.get("claim_ids")),
        }
        if locale_refs != {"fact_ids": fact_ids, "claim_ids": claim_ids}:
            errors.append(
                f"[PKG-GROUP-LOCALE-001] {locale}/{family_id}: locale expression evidence chain differs"
            )
    variant_rows: list[dict[str, Any]] = []
    for variant_id in _ids(child_assertion.get("variant_row_ids")):
        variant = variants.get(variant_id)
        if variant is None:
            errors.append(f"[PKG-GROUP-SCOPE-001] {locale}/{family_id}: missing variant {variant_id!r}")
            continue
        variant_rows.append({
            "id": variant_id,
            "marketplace": _text(variant.get("marketplace") or marketplace),
            "parent_asin": _text(variant.get("parent_asin")),
            "child_asin": _text(variant.get("child_asin")),
            "pack": _text(variant.get("pack")),
            "color": _text(variant.get("color")),
            "size": _text(variant.get("size_or_capacity", variant.get("size"))),
            "other_variant": _text(variant.get("other_variant")),
        })
    parent_fact_projection = []
    child_fact_projection = []
    for fact_id in fact_ids:
        parent_row = parent_facts.get(fact_id)
        child_row = child_facts.get(fact_id)
        if parent_row is None or child_row is None:
            errors.append(f"[PKG-GROUP-FACT-001] {locale}/{family_id}: missing Fact {fact_id!r}")
            continue
        parent_fact_projection.append({
            "id": fact_id,
            "content": _record_projection(parent_row, PARENT_FACT_FIELDS),
            "scope": _scope_projection(parent_row.get("application_scope"), marketplace),
        })
        child_fact_projection.append({
            "id": fact_id,
            "content": _record_projection(child_row, APLUS_FACT_FIELDS),
            "scope": _scope_projection(child_row.get("scope"), marketplace),
        })
    parent_claim_projection = []
    child_claim_projection = []
    for claim_id in claim_ids:
        parent_row = parent_claims.get(claim_id)
        child_row = child_claims.get(claim_id)
        if parent_row is None or child_row is None:
            errors.append(f"[PKG-GROUP-CLAIM-001] {locale}/{family_id}: missing Claim {claim_id!r}")
            continue
        parent_claim_projection.append({
            "id": claim_id,
            "content": _record_projection(parent_row, PARENT_CLAIM_FIELDS),
            "scope": _scope_projection(parent_row.get("application_scope"), marketplace),
        })
        child_claim_projection.append({
            "id": claim_id,
            "content": _record_projection(child_row, APLUS_CLAIM_FIELDS),
            "scope": _scope_projection(child_row.get("scope"), marketplace),
        })
    projection = {
        "family_id": family_id,
        "canonical_statement": _text(parent_assertion.get("statement")),
        "aplus_canonical_statement": _text(child_assertion.get("statement")),
        "fact_ids": fact_ids,
        "claim_ids": claim_ids,
        "parent_assertion_scope": _scope_projection(parent_assertion.get("application_scope"), marketplace),
        "aplus_assertion_scope": _scope_projection(child_assertion.get("application_scope"), marketplace),
        "variant_rows": sorted(variant_rows, key=lambda row: row["id"]),
        "parent_facts": parent_fact_projection,
        "aplus_facts": child_fact_projection,
        "parent_claims": parent_claim_projection,
        "aplus_claims": child_claim_projection,
        "locale_expression_refs": locale_refs,
        "assertion_status": _text(parent_assertion.get("status")),
        "aplus_publish_status": _text(child_assertion.get("publish_status")),
    }
    return projection, canonical_sha256({"locale": locale, "text": localized_text}), errors


def validate_listing_locale_group(manifest: Any, members: Any) -> dict[str, Any]:
    """Compare locale semantics only; this pure layer can never grant GROUP_PASS."""
    shape = validate_group_manifest(manifest)
    errors = list(shape["errors"])
    warnings: list[str] = []
    if not shape["valid"]:
        return {
            "ok": False,
            "structural_valid": False,
            "component_valid": False,
            "semantic_match": False,
            "package_result": "SEMANTIC_INVALID",
            "group_contract_version": GROUP_CONTRACT_VERSION,
            "group_id": manifest.get("group_id", "") if isinstance(manifest, dict) else "",
            "marketplace": manifest.get("marketplace", "") if isinstance(manifest, dict) else "",
            "locales": sorted(
                row.get("locale", "") for row in shape["members"] if row.get("locale")
            ),
            "member_results": [],
            "assertion_families": [],
            "hashes": {},
            "publication_boundary": {
                "execution_boundary": "read_only",
                "coordinator_grants_authority": False,
                "publication_authorized": False,
                "live_pass": False,
            },
            "errors": errors,
            "warnings": warnings,
        }
    member_results: list[dict[str, Any]] = []
    manifest_members = {row["locale"]: row for row in shape["members"] if row.get("locale")}
    internal_rows = _objects(members)
    internal_by_locale = {
        str(row.get("locale", "")): row for row in internal_rows
        if isinstance(row.get("locale"), str) and row.get("locale")
    }
    if shape["valid"] and (set(internal_by_locale) != set(manifest_members) or len(internal_rows) != len(internal_by_locale)):
        errors.append("[PKG-GROUP-MANIFEST-010] loaded members do not exactly match manifest locales")
    for locale in sorted(manifest_members):
        row = internal_by_locale.get(locale, {})
        parent = row.get("parent") if isinstance(row.get("parent"), dict) else {}
        aplus = row.get("aplus") if isinstance(row.get("aplus"), dict) else {}
        member_results.append({
            "locale": locale,
            "parent_bundle_sha256": canonical_sha256(parent),
            "aplus_bundle_sha256": canonical_sha256(aplus),
        })
    base_result = {
        "group_contract_version": GROUP_CONTRACT_VERSION,
        "group_id": manifest.get("group_id", "") if isinstance(manifest, dict) else "",
        "marketplace": manifest.get("marketplace", "") if isinstance(manifest, dict) else "",
        "locales": sorted(manifest_members),
        "member_results": member_results,
        "assertion_families": [],
        "hashes": {},
        "publication_boundary": {
            "execution_boundary": "read_only",
            "coordinator_grants_authority": False,
            "publication_authorized": False,
            "live_pass": False,
        },
        "warnings": warnings,
    }
    if errors:
        base_result.update({
            "ok": False,
            "structural_valid": shape["valid"],
            "component_valid": False,
            "semantic_match": False,
            "package_result": "SEMANTIC_INVALID",
            "errors": sorted(set(errors)),
        })
        return base_result

    marketplace = str(manifest["marketplace"])
    for locale in sorted(manifest_members):
        row = internal_by_locale[locale]
        errors.extend(_context_errors(locale, marketplace, row["parent"], row["aplus"]))
    if errors:
        base_result.update({
            "ok": False,
            "structural_valid": False,
            "component_valid": False,
            "semantic_match": False,
            "package_result": "SEMANTIC_FAIL",
            "errors": sorted(set(errors)),
        })
        return base_result

    baseline_locale = sorted(manifest_members)[0]
    member_scope_projections = {
        locale: _member_scope_projection(
            internal_by_locale[locale]["parent"],
            internal_by_locale[locale]["aplus"],
            marketplace,
        )
        for locale in sorted(manifest_members)
    }
    baseline_scope = member_scope_projections[baseline_locale]
    for locale, projection in sorted(member_scope_projections.items()):
        if locale != baseline_locale and projection != baseline_scope:
            errors.append(
                f"[PKG-GROUP-SCOPE-001] {locale}: whole-package non-locale scope/variant topology differs from {baseline_locale}"
            )

    family_sets: dict[str, set[str]] = {}
    for locale in sorted(manifest_members):
        aplus = internal_by_locale[locale]["aplus"]
        handoff = aplus.get("enriched_content_handoff") if isinstance(aplus.get("enriched_content_handoff"), dict) else {}
        family_sets[locale] = set(_ids(handoff.get("canonical_assertion_ids")))
    baseline_locale = sorted(family_sets)[0]
    baseline_family_ids = family_sets[baseline_locale]
    if not baseline_family_ids or any(values != baseline_family_ids for values in family_sets.values()):
        errors.append(
            "[PKG-GROUP-FAMILY-001] every locale must contain the same non-empty frozen assertion family set"
        )
    family_output: list[dict[str, Any]] = []
    group_projection: dict[str, Any] = {}
    for family_id in sorted(set().union(*family_sets.values()) if family_sets else set()):
        projections: dict[str, dict[str, Any]] = {}
        text_hashes: dict[str, str] = {}
        for locale in sorted(manifest_members):
            row = internal_by_locale[locale]
            projection, text_hash, issues = _family_projection(
                locale, marketplace, family_id, row["parent"], row["aplus"],
            )
            projections[locale] = projection
            text_hashes[locale] = text_hash
            errors.extend(issues)
        baseline = projections.get(baseline_locale, {})
        for locale, projection in sorted(projections.items()):
            if locale == baseline_locale or not baseline or not projection:
                continue
            if projection.get("canonical_statement") != baseline.get("canonical_statement") or projection.get("aplus_canonical_statement") != baseline.get("aplus_canonical_statement"):
                errors.append(f"[PKG-GROUP-ASSERT-001] {locale}/{family_id}: canonical statement differs from {baseline_locale}")
            if projection.get("fact_ids") != baseline.get("fact_ids"):
                errors.append(f"[PKG-GROUP-FACT-001] {locale}/{family_id}: Fact IDs differ from {baseline_locale}")
            if projection.get("claim_ids") != baseline.get("claim_ids"):
                errors.append(f"[PKG-GROUP-CLAIM-001] {locale}/{family_id}: Claim IDs differ from {baseline_locale}")
            if projection.get("parent_facts") != baseline.get("parent_facts") or projection.get("aplus_facts") != baseline.get("aplus_facts"):
                errors.append(f"[PKG-GROUP-FACT-002] {locale}/{family_id}: Fact content differs from {baseline_locale}")
            if projection.get("parent_claims") != baseline.get("parent_claims") or projection.get("aplus_claims") != baseline.get("aplus_claims"):
                errors.append(f"[PKG-GROUP-CLAIM-002] {locale}/{family_id}: Claim content differs from {baseline_locale}")
            scope_keys = (
                "parent_assertion_scope", "aplus_assertion_scope", "variant_rows",
            )
            if any(projection.get(key) != baseline.get(key) for key in scope_keys):
                errors.append(f"[PKG-GROUP-SCOPE-001] {locale}/{family_id}: non-locale scope differs from {baseline_locale}")
            if projection.get("locale_expression_refs") != baseline.get("locale_expression_refs"):
                errors.append(f"[PKG-GROUP-LOCALE-001] {locale}/{family_id}: locale expression chain differs from {baseline_locale}")
            if projection.get("assertion_status") != baseline.get("assertion_status") or projection.get("aplus_publish_status") != baseline.get("aplus_publish_status"):
                errors.append(f"[PKG-GROUP-ASSERT-002] {locale}/{family_id}: assertion status differs from {baseline_locale}")
        if baseline:
            group_projection[family_id] = baseline
        family_output.append({
            "family_id": family_id,
            "baseline_locale": baseline_locale,
            "semantic_projection_sha256_by_locale": {
                locale: canonical_sha256(projection) for locale, projection in sorted(projections.items())
            },
            "localized_text_sha256_by_locale": text_hashes,
        })
    base_result["assertion_families"] = family_output
    base_result["hashes"] = {
        "semantic_projection_sha256": canonical_sha256(group_projection) if group_projection else "",
        "nonlocale_scope_sha256_by_locale": {
            locale: canonical_sha256(projection)
            for locale, projection in sorted(member_scope_projections.items())
        },
        "member_bundle_set_sha256": canonical_sha256(member_results),
    }
    base_result.update({
        "ok": False,
        "structural_valid": not errors,
        "component_valid": False,
        "semantic_match": not errors,
        "package_result": "SEMANTIC_MATCH" if not errors else "SEMANTIC_FAIL",
        "errors": sorted(set(errors)),
    })
    return base_result
