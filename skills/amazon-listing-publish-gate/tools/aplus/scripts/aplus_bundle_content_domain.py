#!/usr/bin/env python3
"""Pure decision, variant, module, and asset phase for the A+ validator."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class ContentReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    decision_map: dict[str, Any]
    decision_status: str
    competitor_map: dict[str, dict[str, Any]]
    positioning: dict[str, Any]
    conflicts: dict[str, dict[str, Any]]
    variants_raw: list[Any]
    variant_rows: list[dict[str, str]]
    child_asins: set[str]
    content_ids: set[str]
    unresolved_target: bool
    modules_raw: list[Any]
    module_map: dict[str, dict[str, Any]]
    module_scopes: dict[str, dict[str, Any]]
    assets_raw: list[Any]
    asset_map: dict[str, dict[str, Any]]


def validate_content(
    root: dict[str, Any], *, schema_version: str, marketplace: str, locale: str,
    target_type: str, identity_status: str, verified_child: str, mode: str,
    conclusion: str, write_scope: str, scope_status: str, conditional_status: str,
    maximum_work: str, blocked_outputs: set[str], envelope: dict[str, Any],
    source_map: dict[str, dict[str, Any]], fact_map: dict[str, dict[str, Any]],
    fact_scopes: dict[str, dict[str, Any]], claim_map: dict[str, dict[str, Any]],
    claim_scopes: dict[str, dict[str, Any]], limits: dict[str, Any],
    alt_max: int | None, available_module_types: set[str],
    content_eligibility: str, ops: Mapping[str, Any],
) -> ContentReport:
    errors: list[str] = []
    warnings: list[str] = []
    require_mapping=ops["require_mapping"]; require_enum=ops["require_enum"]
    require_text=ops["require_text"]; require_string=ops["require_string"]
    require_list=ops["require_list"]; unique_rows=ops["unique_rows"]
    string_set=ops["string_set"]; check_iso=ops["check_iso"]
    check_asin=ops["check_asin"]; validate_app_scope=ops["validate_app_scope"]
    ensure_scope_subset=ops["ensure_scope_subset"]
    require_complete_scope=ops["require_complete_scope"]
    is_community_qa_label=ops["is_community_qa_label"]
    DECISION_STATUSES=ops["DECISION_STATUSES"]
    COMPETITOR_ROLES=ops["COMPETITOR_ROLES"]; FETCH_STATUSES=ops["FETCH_STATUSES"]
    COMPETITOR_STATUSES=ops["COMPETITOR_STATUSES"]
    CONFLICT_STATUSES=ops["CONFLICT_STATUSES"]; MAXIMUM_WORK=ops["MAXIMUM_WORK"]
    VARIANT_STATUSES=ops["VARIANT_STATUSES"]; PRIORITIES=ops["PRIORITIES"]
    CONTENT_STATUSES=ops["CONTENT_STATUSES"]
    FINAL_CONTENT_STATUSES=ops["FINAL_CONTENT_STATUSES"]
    QA_STATUSES=ops["QA_STATUSES"]; SYNTHETIC_PERSON=ops["SYNTHETIC_PERSON"]
    GENERATION_METHODS=ops["GENERATION_METHODS"]; SHA256_RE=ops["SHA256_RE"]

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
    decision_map = require_mapping(root.get("decision_map"), "$.decision_map", errors)
    decision_status = require_enum(decision_map, "status", "$.decision_map", DECISION_STATUSES, errors)
    require_text(decision_map, "owner", "$.decision_map", errors)
    dimensions = unique_rows(require_list(decision_map, "dimensions", "$.decision_map", errors), "$.decision_map.dimensions", errors)
    for dimension_id, row in dimensions.items():
        path = f"$.decision_map.dimensions[{dimension_id}]"
        status = require_enum(row, "status", path, DECISION_STATUSES, errors)
        answer = require_string(row, "answer", path, errors)
        fact_ids = string_set(require_list(row, "fact_ids", path, errors), f"{path}.fact_ids", errors)
        source_ids = string_set(require_list(row, "source_ids", path, errors), f"{path}.source_ids", errors)
        for fact_id in fact_ids:
            if fact_id not in fact_map:
                errors.append(f"{path}.fact_ids: unknown fact id {fact_id!r}")
        check_refs(source_ids, f"{path}.source_ids")
        if status == "SUPPORTED" and (not answer or not (fact_ids or source_ids)):
            errors.append(f"{path}: SUPPORTED answer requires text and evidence references")

    competitor_map = unique_rows(require_list(root, "competitor_insights", "$", errors), "$.competitor_insights", errors)
    for insight_id, insight in competitor_map.items():
        path = f"$.competitor_insights[{insight_id}]"
        require_enum(insight, "competitor_role", path, COMPETITOR_ROLES, errors)
        require_text(insight, "marketplace", path, errors)
        require_text(insight, "locale", path, errors)
        competitor_child = require_text(insight, "child_asin", path, errors)
        check_asin(competitor_child, f"{path}.child_asin", errors)
        observed = require_text(insight, "observed_at", path, errors)
        check_iso(observed, f"{path}.observed_at", errors)
        require_enum(insight, "fetch_status", path, FETCH_STATUSES, errors)
        require_enum(insight, "status", path, COMPETITOR_STATUSES, errors)
        if insight.get("copying_prohibited") is not True:
            errors.append(f"{path}.copying_prohibited: must be true")
        source_ids = string_set(require_list(insight, "source_ids", path, errors), f"{path}.source_ids", errors, nonempty=True)
        check_refs(source_ids, f"{path}.source_ids")
        difference_ids = string_set(require_list(insight, "target_verified_difference_fact_ids", path, errors), f"{path}.target_verified_difference_fact_ids", errors)
        for fact_id in difference_ids:
            if fact_id not in fact_map:
                errors.append(f"{path}.target_verified_difference_fact_ids: unknown fact id {fact_id!r}")
        for key in ("category_parity", "decision_gaps", "claim_risks", "borrowable_structural_patterns"):
            string_set(require_list(insight, key, path, errors), f"{path}.{key}", errors)

    positioning = require_mapping(root.get("positioning"), "$.positioning", errors)
    require_enum(positioning, "status", "$.positioning", DECISION_STATUSES, errors)
    for key in ("core_audience", "high_value_situation", "job", "category", "primary_benefit", "statement", "owner"):
        require_string(positioning, key, "$.positioning", errors)
    mechanism_ids = string_set(require_list(positioning, "mechanism_fact_ids", "$.positioning", errors), "$.positioning.mechanism_fact_ids", errors)
    limit_ids = string_set(require_list(positioning, "important_limit_claim_ids", "$.positioning", errors), "$.positioning.important_limit_claim_ids", errors)
    for fact_id in mechanism_ids:
        if fact_id not in fact_map:
            errors.append(f"$.positioning.mechanism_fact_ids: unknown fact id {fact_id!r}")
    for claim_id in limit_ids:
        if claim_id not in claim_map:
            errors.append(f"$.positioning.important_limit_claim_ids: unknown claim id {claim_id!r}")

    conflicts = unique_rows(require_list(root, "conflicts", "$", errors), "$.conflicts", errors)
    for conflict_id, conflict in conflicts.items():
        path = f"$.conflicts[{conflict_id}]"
        require_enum(conflict, "status", path, CONFLICT_STATUSES, errors)
        require_enum(conflict, "maximum_work", path, MAXIMUM_WORK, errors)
        for key in ("impact", "decisive_evidence", "owner"):
            require_text(conflict, key, path, errors)
        due = require_text(conflict, "due_date", path, errors)
        check_iso(due, f"{path}.due_date", errors)
        string_set(require_list(conflict, "statements", path, errors), f"{path}.statements", errors, nonempty=True)
        check_refs(string_set(require_list(conflict, "source_ids", path, errors), f"{path}.source_ids", errors, nonempty=True), f"{path}.source_ids")
        for key, known in (("affected_fact_ids", fact_map), ("affected_claim_ids", claim_map)):
            for value in string_set(require_list(conflict, key, path, errors), f"{path}.{key}", errors):
                if value not in known:
                    errors.append(f"{path}.{key}: unknown id {value!r}")
    if conclusion == "PASS":
        open_conflicts = [
            conflict_id for conflict_id, conflict in conflicts.items()
            if conflict.get("status") in {"OPEN", "EVIDENCE_REQUESTED", "BLOCKED"}
        ]
        if open_conflicts:
            version_code = "A13" if schema_version == "1.3" else "A12" if schema_version == "1.2" else "A11"
            errors.append(f"[{version_code}-CONFLICT-001] $.project.conclusion: PASS cannot retain open conflicts {open_conflicts!r}")

    variants_raw = require_list(root, "variants", "$", errors)
    variant_keys: set[tuple[str, str, str]] = set()
    child_asins: set[str] = set()
    variant_rows: list[dict[str, str]] = []
    content_ids: set[str] = set()
    for index, raw in enumerate(variants_raw):
        path = f"$.variants[{index}]"
        row = require_mapping(raw, path, errors)
        child = require_text(row, "child_asin", path, errors)
        parent = require_text(row, "parent_asin", path, errors)
        check_asin(child, f"{path}.child_asin", errors)
        check_asin(parent, f"{path}.parent_asin", errors)
        row_marketplace = require_text(row, "marketplace", path, errors)
        row_locale = require_text(row, "locale", path, errors)
        if row_marketplace != marketplace:
            errors.append(f"{path}.marketplace: must match project")
        if row_locale != locale:
            errors.append(f"{path}.locale: must match project")
        dimensions_row = {key: require_text(row, key, path, errors) for key in ("pack", "color", "size_or_capacity", "other_variant")}
        status = require_enum(row, "status", path, VARIANT_STATUSES, errors)
        require_text(row, "owner", path, errors)
        source_ids = string_set(require_list(row, "source_ids", path, errors), f"{path}.source_ids", errors)
        check_refs(source_ids, f"{path}.source_ids", usable=status in {"VERIFIED", "APPLIED", "LIVE_PASS"})
        if status in {"VERIFIED", "APPLIED", "LIVE_PASS"} and not source_ids:
            errors.append(f"{path}.source_ids: verified/applied variant requires evidence")
        row_content_ids: list[str] = []
        for key in ("aplus_content_id", "brand_story_id"):
            value = require_string(row, key, path, errors)
            if value:
                content_ids.add(value)
                row_content_ids.append(value)
            if schema_version == "1.1" and mode == "publish_support" and not value:
                errors.append(f"{path}.{key}: required for publish_support")
        if schema_version in {"1.2", "1.3"} and mode == "publish_support" and not row_content_ids:
            errors.append(f"{path}: publish_support requires at least one authorized A+ or Brand Story content ID")
        key = (child, row_marketplace, row_locale)
        if key in variant_keys:
            errors.append(f"{path}: duplicate child/marketplace/locale row")
        variant_keys.add(key)
        child_asins.add(child)
        variant_rows.append({
            "child_asin": child, "parent_asin": parent, "marketplace": row_marketplace,
            "locale": row_locale, **dimensions_row, "status": status,
            "aplus_content_id": str(row.get("aplus_content_id", "")).strip(),
            "brand_story_id": str(row.get("brand_story_id", "")).strip(),
        })

    if variants_raw and envelope["child_asins"] != child_asins:
        errors.append("$.scope.intended_child_asins: must exactly match variant matrix")
    if verified_child and variants_raw and verified_child not in child_asins:
        errors.append("$.project.focal_identity.verified_focal_child: not present in variant matrix")
    if conclusion == "PASS" and scope_status != "FROZEN":
        errors.append("$.scope.status: PASS requires FROZEN")
    if conclusion == "PASS" and not variants_raw:
        errors.append("$.variants: PASS requires intended variants")
    if mode in {"preflight_qa", "publish_support"} and not variants_raw:
        errors.append(f"$.variants: {mode} requires intended variants")
    if mode == "publish_support" and target_type != "live_asin":
        errors.append("$.project.target_type: publish_support requires live_asin")

    unresolved_target = target_type != "live_asin" or identity_status != "VERIFIED_CHILD" or not variants_raw
    required_blocks = {"consumer_final_copy", "final_product_imagery", "publishing"}
    if mode == "rebuild" and unresolved_target:
        if conclusion not in {"CONDITIONAL_PASS", "BLOCKED", "NO_VALID_CONCLUSION"}:
            errors.append("$.project.conclusion: unresolved rebuild cannot PASS")
        if write_scope != "read_only":
            errors.append("$.project.write_scope: unresolved rebuild must remain read_only")
        if conditional_status not in {"ACTIVE", "BLOCKED"}:
            errors.append("$.project.conditional_draft.status: unresolved rebuild requires ACTIVE or BLOCKED")
        if maximum_work == "full_production":
            errors.append("$.project.conditional_draft.maximum_work: unresolved rebuild cannot allow full_production")
        if not required_blocks.issubset(blocked_outputs):
            errors.append("$.project.conditional_draft.blocked_outputs: must block final copy, final imagery, and publishing")
    if conclusion == "PASS":
        if conditional_status != "CLEARED" or maximum_work != "full_production" or blocked_outputs:
            errors.append("$.project.conditional_draft: PASS requires CLEARED/full_production/no blocked outputs")

    def scope_against_variants(scope: dict[str, Any], path: str) -> None:
        if not variants_raw or not scope["child_asins"]:
            return
        for child in scope["child_asins"]:
            candidates = [row for row in variant_rows if row["child_asin"] == child and row["marketplace"] in scope["marketplaces"] and row["locale"] in scope["locales"]]
            if not candidates:
                errors.append(f"{path}: no intended variant row for child {child!r}")
                continue
            mapping = {"packs": "pack", "colors": "color", "sizes_or_capacities": "size_or_capacity"}
            if not any(all(not scope[key] or row[row_key] in scope[key] for key, row_key in mapping.items()) for row in candidates):
                errors.append(f"{path}: dimensions do not match child {child!r}")

    modules_raw = require_list(root, "modules", "$", errors)
    if schema_version == "1.3" and maximum_work != "full_production":
        premature_sections = {
            section: len([row for row in root.get(section, []) if isinstance(row, dict)])
            for section in ("modules", "assets", "decision_answer_units", "carriers")
        }
        premature_sections = {name: count for name, count in premature_sections.items() if count}
        if premature_sections:
            errors.append(
                "[A13-PHASE-001] $.project.conditional_draft.maximum_work: "
                f"{maximum_work!r} is pre-production and cannot carry consumer copy, module/wireframe, "
                f"image/ALT, answer-unit, or carrier rows; populated sections={premature_sections!r}"
            )
    module_map = unique_rows(modules_raw, "$.modules", errors)
    module_scopes: dict[str, dict[str, Any]] = {}
    for module_id, module in module_map.items():
        path = f"$.modules[{module_id}]"
        require_enum(module, "decision_priority", path, PRIORITIES, errors)
        for key in ("decision_question", "wrong_user_or_use", "native_headline", "native_body", "image_brief", "mobile_plan", "owner"):
            require_text(module, key, path, errors)
        module_type = require_text(module, "module_type", path, errors)
        if is_community_qa_label(module_type):
            errors.append(f"[A-QA-003] {path}.module_type: Community Q&A is read-only and cannot be a brand-authored module")
        require_string(module, "on_image_text", path, errors)
        verified = require_text(module, "module_type_verified_at", path, errors)
        check_iso(verified, f"{path}.module_type_verified_at", errors)
        eligibility_ids = string_set(require_list(module, "eligibility_source_ids", path, errors), f"{path}.eligibility_source_ids", errors, nonempty=True)
        check_refs(eligibility_ids, f"{path}.eligibility_source_ids", usable=True, allowed_types={"OFFICIAL_PLATFORM_RULE", "BACKEND_OBSERVED", "VERIFIED_ACCOUNT_DATA"})
        content_status = require_enum(module, "content_status", path, CONTENT_STATUSES, errors)
        evidence_status = require_enum(module, "evidence_gate_status", path, QA_STATUSES, errors)
        qa_status = require_enum(module, "qa_status", path, QA_STATUSES, errors)
        if module.get("experiment_eligible") not in {True, False}:
            errors.append(f"{path}.experiment_eligible: required boolean")
        module_scope = validate_app_scope(module.get("application_scope"), f"{path}.application_scope", errors)
        module_scopes[module_id] = module_scope
        ensure_scope_subset(module_scope, envelope, f"{path}.application_scope", "top-level envelope", errors)
        scope_against_variants(module_scope, f"{path}.application_scope")
        fact_ids = string_set(require_list(module, "fact_ids", path, errors), f"{path}.fact_ids", errors)
        claim_ids = string_set(require_list(module, "claim_ids", path, errors), f"{path}.claim_ids", errors)
        hold_ids = string_set(require_list(module, "hold_claim_ids", path, errors), f"{path}.hold_claim_ids", errors)
        if claim_ids & hold_ids:
            errors.append(f"{path}: claim_ids and hold_claim_ids must be disjoint")
        for fact_id in fact_ids:
            fact = fact_map.get(fact_id)
            if fact is None:
                errors.append(f"{path}.fact_ids: unknown fact id {fact_id!r}")
            else:
                ensure_scope_subset(module_scope, fact_scopes[fact_id], f"{path}.application_scope", f"fact {fact_id!r}", errors)
                if content_status in FINAL_CONTENT_STATUSES and fact.get("publish_status") != "PUBLISHABLE":
                    errors.append(f"{path}: final module references non-publishable fact {fact_id!r}")
        for claim_id in claim_ids:
            claim = claim_map.get(claim_id)
            if claim is None:
                errors.append(f"{path}.claim_ids: unknown claim id {claim_id!r}")
            else:
                ensure_scope_subset(module_scope, claim_scopes[claim_id], f"{path}.application_scope", f"claim {claim_id!r}", errors)
                if claim.get("publish_status") != "PUBLISHABLE" or claim.get("consumer_facing") is not True:
                    errors.append(f"{path}: module claim {claim_id!r} must be publishable and consumer_facing=true")
        for claim_id in hold_ids:
            if claim_id not in claim_map:
                errors.append(f"{path}.hold_claim_ids: unknown claim id {claim_id!r}")
            elif claim_map[claim_id].get("publish_status") == "PUBLISHABLE":
                errors.append(f"{path}.hold_claim_ids: claim {claim_id!r} is not on hold")
        if hold_ids and content_status in FINAL_CONTENT_STATUSES:
            errors.append(f"{path}.content_status: module with hold claims cannot be final")
        visible_ids = string_set(require_list(module, "visible_proof_fact_ids", path, errors), f"{path}.visible_proof_fact_ids", errors)
        for fact_id in visible_ids:
            if fact_id not in fact_map:
                errors.append(f"{path}.visible_proof_fact_ids: unknown fact id {fact_id!r}")
            else:
                ensure_scope_subset(module_scope, fact_scopes[fact_id], f"{path}.application_scope", f"visible fact {fact_id!r}", errors)
        applied = string_set(require_list(module, "applied_child_asins", path, errors), f"{path}.applied_child_asins", errors)
        if applied != module_scope["child_asins"]:
            errors.append(f"{path}.applied_child_asins: must exactly equal application_scope.child_asins")
        if not applied.issubset(child_asins):
            errors.append(f"{path}.applied_child_asins: contains child outside variant matrix")
        for key in ("prohibited_claims", "acceptance_tests"):
            string_set(require_list(module, key, path, errors), f"{path}.{key}", errors, nonempty=key == "acceptance_tests")
        if module_type not in available_module_types:
            errors.append(f"{path}.module_type: not in current available_module_types")
        if content_status in FINAL_CONTENT_STATUSES:
            require_complete_scope(module_scope, envelope, f"{path}.application_scope", errors, require_child=True)
        if unresolved_target and mode == "rebuild" and (content_status != "CONDITIONAL_DRAFT" or applied):
            errors.append(f"{path}: unresolved rebuild module must remain CONDITIONAL_DRAFT and unapplied")
        if conclusion == "PASS" and (content_status not in FINAL_CONTENT_STATUSES or evidence_status != "PASS" or qa_status != "PASS"):
            errors.append(f"{path}: project PASS requires final content, evidence PASS, and QA PASS")

    module_limit = limits.get("premium_max_modules") if content_eligibility == "PREMIUM" else limits.get("basic_max_modules")
    if isinstance(module_limit, int) and len(module_map) > module_limit:
        errors.append(f"$.modules: {len(module_map)} exceeds verified {content_eligibility} limit {module_limit}")

    assets_raw = require_list(root, "assets", "$", errors)
    asset_map = unique_rows(assets_raw, "$.assets", errors)
    seen_alt: dict[str, str] = {}
    for asset_id, asset in asset_map.items():
        path = f"$.assets[{asset_id}]"
        module_id = require_text(asset, "module_id", path, errors)
        if module_id not in module_map:
            errors.append(f"{path}.module_id: unknown module id {module_id!r}")
        require_text(asset, "asset_role", path, errors)
        content_status = require_enum(asset, "content_status", path, CONTENT_STATUSES, errors)
        require_text(asset, "file", path, errors)
        sha256 = require_string(asset, "sha256", path, errors)
        if content_status in FINAL_CONTENT_STATUSES and not SHA256_RE.fullmatch(sha256):
            errors.append(f"{path}.sha256: final asset requires a 64-character SHA-256")
        alt = require_text(asset, "alt", path, errors)
        if alt_max is not None and len(alt) > alt_max:
            errors.append(f"{path}.alt: exceeds verified limit {alt_max}")
        normalized_alt = " ".join(alt.casefold().split())
        if normalized_alt in seen_alt:
            errors.append(f"{path}.alt: duplicates asset {seen_alt[normalized_alt]!r}")
        elif normalized_alt:
            seen_alt[normalized_alt] = asset_id
        asset_scope = validate_app_scope(asset.get("application_scope"), f"{path}.application_scope", errors)
        ensure_scope_subset(asset_scope, envelope, f"{path}.application_scope", "top-level envelope", errors)
        scope_against_variants(asset_scope, f"{path}.application_scope")
        if module_id in module_scopes:
            ensure_scope_subset(asset_scope, module_scopes[module_id], f"{path}.application_scope", f"module {module_id!r}", errors)
        applied = string_set(require_list(asset, "applied_child_asins", path, errors), f"{path}.applied_child_asins", errors)
        if applied != asset_scope["child_asins"]:
            errors.append(f"{path}.applied_child_asins: must exactly equal application_scope.child_asins")
        if not applied.issubset(child_asins):
            errors.append(f"{path}.applied_child_asins: contains child outside variant matrix")
        claim_ids = string_set(require_list(asset, "claim_ids", path, errors), f"{path}.claim_ids", errors)
        visible_ids = string_set(require_list(asset, "visible_facts", path, errors), f"{path}.visible_facts", errors)
        for claim_id in claim_ids:
            claim = claim_map.get(claim_id)
            if claim is None:
                errors.append(f"{path}.claim_ids: unknown claim id {claim_id!r}")
            else:
                ensure_scope_subset(asset_scope, claim_scopes[claim_id], f"{path}.application_scope", f"claim {claim_id!r}", errors)
                if claim.get("publish_status") != "PUBLISHABLE" or claim.get("consumer_facing") is not True:
                    errors.append(f"{path}: asset claim {claim_id!r} must be publishable and consumer_facing=true")
        for fact_id in visible_ids:
            fact = fact_map.get(fact_id)
            if fact is None:
                errors.append(f"{path}.visible_facts: unknown fact id {fact_id!r}")
            else:
                ensure_scope_subset(asset_scope, fact_scopes[fact_id], f"{path}.application_scope", f"visible fact {fact_id!r}", errors)
                if content_status in FINAL_CONTENT_STATUSES and fact.get("publish_status") != "PUBLISHABLE":
                    errors.append(f"{path}: final asset references non-publishable fact {fact_id!r}")
        synthetic = require_enum(asset, "synthetic_person", path, SYNTHETIC_PERSON, errors, lower=True)
        generation = require_enum(asset, "generation_method", path, GENERATION_METHODS, errors)
        references = string_set(require_list(asset, "product_reference_files", path, errors), f"{path}.product_reference_files", errors)
        string_set(require_list(asset, "must_show", path, errors), f"{path}.must_show", errors)
        string_set(require_list(asset, "must_not_change", path, errors), f"{path}.must_not_change", errors)
        fidelity_owner = require_string(asset, "product_fidelity_owner", path, errors)
        fidelity_status = require_enum(asset, "product_fidelity_status", path, QA_STATUSES, errors)
        fidelity_evidence = string_set(require_list(asset, "product_fidelity_evidence", path, errors), f"{path}.product_fidelity_evidence", errors)
        ai_checked = require_string(asset, "ai_rule_checked_at", path, errors)
        if ai_checked:
            check_iso(ai_checked, f"{path}.ai_rule_checked_at", errors)
        ai_source_ids = string_set(require_list(asset, "ai_rule_source_ids", path, errors), f"{path}.ai_rule_source_ids", errors)
        qa_status = require_enum(asset, "qa_status", path, QA_STATUSES, errors)
        ai_or_composite = generation in {"composite_with_real_product", "ai_generated_person_or_setting", "ai_assisted_edit"} or synthetic == "yes"
        if ai_or_composite:
            if not references:
                errors.append(f"{path}.product_reference_files: AI/composite asset requires controlled product references")
            if not fidelity_owner or not fidelity_evidence:
                errors.append(f"{path}: AI/composite asset requires fidelity owner and evidence")
            if not ai_checked or not ai_source_ids:
                errors.append(f"{path}: AI/composite asset requires current AI rule date and sources")
            check_refs(ai_source_ids, f"{path}.ai_rule_source_ids", usable=True, allowed_types={"OFFICIAL_PLATFORM_RULE"})
        if content_status in FINAL_CONTENT_STATUSES:
            require_complete_scope(asset_scope, envelope, f"{path}.application_scope", errors, require_child=True)
            if synthetic == "unknown" or generation == "unknown":
                errors.append(f"{path}: final asset cannot retain unknown generation/synthetic status")
            if (claim_ids or visible_ids) and (fidelity_status != "PASS" or not fidelity_owner or not fidelity_evidence):
                errors.append(f"{path}: final product-depicting asset requires fidelity PASS, owner, and evidence")
        if unresolved_target and mode == "rebuild" and (content_status != "CONDITIONAL_DRAFT" or applied):
            errors.append(f"{path}: unresolved rebuild asset must remain CONDITIONAL_DRAFT and unapplied")
        if conclusion == "PASS" and (content_status not in FINAL_CONTENT_STATUSES or qa_status != "PASS"):
            errors.append(f"{path}: project PASS requires final content and QA PASS")

    return ContentReport(
        tuple(errors), tuple(warnings), decision_map, decision_status, competitor_map,
        positioning, conflicts, variants_raw, variant_rows, child_asins, content_ids,
        unresolved_target, modules_raw, module_map, module_scopes, assets_raw, asset_map,
    )
