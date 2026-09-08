#!/usr/bin/env python3
"""Render a machine-validated A+ Bundle 1.3 as deterministic read-only HTML."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from aplus_v13_domain import derive_discovery_closure
from validate_bundle import validate_bundle


RENDERER_VERSION = "1.2"
SHELL = Path(__file__).resolve().parents[1] / "assets" / "full-width-report-shell.html"


class SafeCell(str):
    """Marker for renderer-created safe HTML such as an escaped HTTP link."""


def esc(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return html.escape(str(value), quote=True)


def canonical_sha256(bundle: dict[str, Any]) -> str:
    raw = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def safe_link(value: Any) -> SafeCell:
    raw = str(value or "")
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return SafeCell(f"<code>{esc(raw)}</code>")
    if parsed.scheme in {"https", "http"} and parsed.netloc:
        return SafeCell(f'<a href="{esc(raw)}" rel="noreferrer noopener">{esc(raw)}</a>')
    return SafeCell(f"<code>{esc(raw)}</code>")


def _objects(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _sorted(value: Any) -> list[dict[str, Any]]:
    return sorted(_objects(value), key=lambda row: str(row.get("id", "")))


def _cell(value: Any) -> str:
    return str(value) if isinstance(value, SafeCell) else esc(value)


def table(caption: str, headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    body = [
        "<tr>" + "".join(f"<td>{_cell(value)}</td>" for value in row) + "</tr>"
        for row in rows
    ]
    if not body:
        body.append(f'<tr><td colspan="{len(headers)}" class="muted">无记录</td></tr>')
    head = "".join(f'<th scope="col">{esc(label)}</th>' for label in headers)
    table_label = f"{caption}，可横向滚动查看完整表格"
    return (
        f'<div class="table-wrap" tabindex="0" role="region" aria-label="{esc(table_label)}"><table>'
        f"<caption>{esc(caption)}</caption><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def responsibility(title: str, owner: Any, acceptance: Any, blocker: Any, status: Any) -> str:
    return (
        '<article class="responsibility">'
        f'<h3>{esc(title)}</h3><dl><dt>Owner</dt><dd>{esc(owner or "UNASSIGNED")}</dd>'
        f'<dt>Acceptance</dt><dd>{esc(acceptance or "UNDEFINED")}</dd>'
        f'<dt>Blocker</dt><dd>{esc(blocker or "NONE RECORDED")}</dd>'
        f'<dt>Machine status</dt><dd><span class="status" data-status="{esc(status)}">{esc(status)}</span></dd>'
        '</dl></article>'
    )


def _validation_projection(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    return {
        key: result.get(key)
        for key in ("ok", "template_only", "structural_valid", "result_level", "errors", "warnings")
    }


def _render_validated(bundle: dict[str, Any], validation: dict[str, Any]) -> str:
    project = bundle.get("project") if isinstance(bundle.get("project"), dict) else {}
    workflow = bundle.get("workflow_context") if isinstance(bundle.get("workflow_context"), dict) else {}
    component = bundle.get("component_result") if isinstance(bundle.get("component_result"), dict) else {}
    handoff = bundle.get("enriched_content_handoff") if isinstance(bundle.get("enriched_content_handoff"), dict) else {}
    scope = bundle.get("scope") if isinstance(bundle.get("scope"), dict) else {}
    discovery = bundle.get("discovery") if isinstance(bundle.get("discovery"), dict) else {}
    closure = discovery.get("closure") if isinstance(discovery.get("closure"), dict) else {}
    evidence_pass = discovery.get("evidence_pass") if isinstance(discovery.get("evidence_pass"), dict) else {}
    category_adapter = bundle.get("category_adapter") if isinstance(bundle.get("category_adapter"), dict) else {}
    coverage = bundle.get("coverage_summary") if isinstance(bundle.get("coverage_summary"), dict) else {}
    authorization = bundle.get("publish_authorization") if isinstance(bundle.get("publish_authorization"), dict) else {}
    machine_status = str(validation.get("result_level", "INVALID"))
    errors = [str(row) for row in validation.get("errors", [])]
    warnings = [str(row) for row in validation.get("warnings", [])]
    focal = project.get("focal_identity") if isinstance(project.get("focal_identity"), dict) else {}
    bundle_hash = canonical_sha256(bundle)
    workflow_mode = str(workflow.get("mode", ""))
    evidence_pass_valid = not any("[A13-EVIDENCE-" in row for row in errors)
    distillations_valid = not any(
        marker in row
        for row in errors
        for marker in ("[A13-DISCOVERY-020]", "[A13-DISCOVERY-021]", "[A13-DISCOVERY-022]")
    )
    action_map = {
        str(row.get("id")): row
        for row in _objects(discovery.get("evidence_actions"))
        if row.get("id")
    }
    derived_closure = derive_discovery_closure(
        workflow_mode, evidence_pass_valid, distillations_valid, action_map,
    )
    derived_evidence_gate = (
        "PARENT_BOUND" if workflow_mode == "embedded"
        else "PASS" if evidence_pass_valid else "BLOCKED"
    )

    replacements: dict[str, str] = {
        "PROJECT_TITLE": esc(project.get("title") or "Amazon A+ 只读施工报告"),
        "MARKETPLACE": esc(project.get("marketplace", "")),
        "FOCAL_IDENTIFIER": esc(focal.get("identifier", "")),
        "SNAPSHOT_DATE": esc(project.get("snapshot_date", "")),
        "CONCLUSION": esc(machine_status),
        "BUNDLE_HASH": esc(bundle_hash),
        "BUNDLE_VERSION": esc(bundle.get("schema_version", "")),
        "RENDERER_VERSION": esc(RENDERER_VERSION),
    }

    first_blocker = errors[0] if errors else (
        f"OPEN delta: {component.get('open_delta_request_ids')}" if component.get("open_delta_request_ids") else "NONE"
    )
    replacements["EXECUTIVE_CONCLUSION"] = (
        '<div class="responsibility-grid">'
        + responsibility(
            "A+组件", component.get("owner"),
            "Validator推导COMPONENT_PASS且P0原子无缺口；这仍不是整页PASS。",
            first_blocker, machine_status,
        )
        + responsibility(
            "冻结交接", handoff.get("owner"),
            "Snapshot、父Hash、Discovery/PTD/Denominator及范围由Package Coordinator复核。",
            "存在delta时必须回父层重建新Snapshot，禁止原地改写。", handoff.get("status"),
        )
        + responsibility(
            "发布与回读", authorization.get("authorizer"),
            "需要另行授权、后台Accepted证据和逐child/locale前台LIVE_MATCH。",
            "本报告无写入、提交或授权能力。", authorization.get("status", "NOT_AUTHORIZED"),
        )
        + '</div>'
        + '<div class="summary">'
        f'<div class="metric"><span>机器结果</span><strong>{esc(machine_status)}</strong></div>'
        f'<div class="metric"><span>P0 原子覆盖</span><strong>{esc(coverage.get("p0_atoms_pass", 0))}/{esc(coverage.get("p0_atoms_required", 0))}</strong></div>'
        f'<div class="metric"><span>执行边界</span><strong>{esc(workflow.get("execution_boundary"))}</strong></div>'
        '</div><p><strong>边界：</strong>A+ COMPONENT_PASS 不是整页 PASS，也不授予发布权限；跨 Bundle 结论只由 package coordinator 产生。</p>'
        + table("Validator阻断项与警告", ["类型", "记录"], (
            [("ERROR", row) for row in errors] + [("WARNING", row) for row in warnings]
            if errors or warnings else [("INFO", "无机器错误或警告；仍需核验事实、权限与前台状态。")]
        ))
    )

    replacements["COORDINATION_RECEIPT_BOUNDARY"] = (
        table("工作人员操作边界", ["项目", "要求"], (
            ("本报告中的 coordination ledger 值", "NOT_INCLUDED_IN_A_PLUS_BUNDLE—查看 Parent coordinator/ledger 输出；不得从 A+ Bundle、COMPONENT_PASS、人工 Gate 或页面颜色推断 ledger head、receipt 或终态。"),
            ("A+ 责任", "A+ 只交付 COMPONENT_PASS 或 DELTA_REQUIRED；A+ 不生成、不确认 coordination receipt，不读取或写入 JSONL ledger，也不把 receipt 推断进 A+ Bundle。"),
            ("纯检查 / 无 Ledger", "纯 coordinator 最高只形成 PASS_CANDIDATE；无受控 ledger 不会确认终态 PASS。--receipt-ledger <path> 仅读取 current head；只有显式 --record-receipt 才以锁、append 和 fsync 追加本地证据。"),
            ("正常链", "Parent package coordinator 接收 FROZEN + COMPONENT_PASS，用 --receipt-ledger <path> --record-receipt 将 AWAITING_RESULT_ACK 写为 current head；Parent 进入 RESULT_RECEIVED 后，coordinator 用同一 --receipt-ledger <path> 读取 current head，并再次显式使用 --record-receipt 写入终态 PASS receipt。"),
            ("DELTA / refreeze 链", "DELTA_REQUIRED 由 Parent 协调并写为新 head，旧 AWAIT 不可回放 → 旧 Snapshot SUPERSEDED → semantic_revision + 1 → 新 FROZEN → 新 AWAIT 写为 current head → 新 RESULT_RECEIVED 再消费该 current head。"),
            ("多 Locale", "Group manifest 只读确认；每个 member 必须绑定自己的 JSONL ledger，且 current head 已是精确绑定该 Parent、A+ 与 bundled validators 的终态 PASS receipt。"),
            ("HTML 与保存边界", "本 HTML 不创建、保存、编辑或追加 ledger；receipt 由 Parent package coordinator 产生并写入显式 JSONL ledger。请查看 coordinator/ledger 输出，receipt 不进入 A+ Bundle。"),
        ))
        + '<p><strong>本地证据写入：</strong>ledger 是可审计的本地流程证据；<code>--record-receipt</code>是显式 local evidence write，不是 Amazon、Seller Central、ERP、网络或其他外部写入。</p>'
        + '<p><strong>与 Amazon backend/readback receipt 严格区分：</strong>coordination ledger/receipt 不是数字签名、不是可信时间戳、不是 Fact/Claim 或证据真实性证明、不是 Amazon 后台/平台回执、不是发布授权、不是 LIVE_MATCH/LIVE_PASS 证明。若对手可替换整个 ledger、Skill 或 validator，仍需外部可信存储或签名。</p>'
    )

    replacements["SCOPE_AND_EVIDENCE"] = (
        table("范围与执行边界", ["维度", "值"], (
            ("Marketplace", scope.get("marketplaces")), ("Locale", scope.get("locales")),
            ("Parent ASIN", scope.get("parent_asins")), ("Child ASIN", scope.get("intended_child_asins")),
            ("Excluded child", scope.get("excluded_child_asins")), ("Pack", scope.get("packs")),
            ("颜色", scope.get("colors")), ("尺码/容量", scope.get("sizes_or_capacities")),
            ("Workflow", workflow),
        ))
        + table("Listing→A+冻结Handoff", ["Snapshot", "Parent project/hash", "状态", "范围", "Variants", "Requirements", "Atoms", "Assertions", "Evidence", "Hashes", "禁止动作", "Owner"], ((
            handoff.get("snapshot_id"), {"project": handoff.get("parent_project_id"), "sha": handoff.get("parent_bundle_sha256")}, handoff.get("status"), handoff.get("application_scope"), handoff.get("variant_row_ids"), handoff.get("decision_requirements"), handoff.get("requirement_atoms"), handoff.get("canonical_assertion_ids"), {"facts": handoff.get("fact_ids"), "claims": handoff.get("claim_ids"), "blocked_claims": handoff.get("blocked_claim_ids"), "conflicts": handoff.get("conflict_ids"), "sources": handoff.get("source_ids")}, {key: handoff.get(key) for key in ("discovery_closure_hash", "ptd_inventory_hash", "decision_denominator_hash", "checksum")}, handoff.get("prohibited_actions"), handoff.get("owner"),
        ),))
    )

    question_rows: list[tuple[Any, ...]] = []
    for round_row in _sorted(discovery.get("interview_rounds")):
        for question in _objects(round_row.get("questions")):
            question_rows.append((
                round_row.get("id"), round_row.get("phase"), question.get("id"),
                question.get("question"), question.get("response_class"), question.get("answer"),
                question.get("affected_requirement_ids"), question.get("decision_effects"),
                question.get("owner", round_row.get("owner")),
            ))
    replacements["CURRENT_AUDIT"] = (
        table("Discovery状态", ["维度", "值"], (
            ("Mode", discovery.get("mode")),
            ("Evidence pass record", evidence_pass),
            ("Machine evidence gate", derived_evidence_gate),
            ("Machine-derived closure", derived_closure),
            ("Closure record", closure),
        ))
        + table("类目调查适配器", ["字段", "值"], (
            ("ID", category_adapter.get("id")),
            ("Status", category_adapter.get("status")),
            ("Investigation prompts", category_adapter.get("investigation_prompts")),
            ("Evidence probes", category_adapter.get("evidence_probes")),
            ("Return risks", category_adapter.get("return_risks")),
            ("QA checks", category_adapter.get("qa_checks")),
            ("Owner", category_adapter.get("owner")),
        ))
        + table("苏格拉底问题与回答", ["Round", "Phase", "ID", "问题", "分类", "回答", "受影响Requirement", "决策影响", "Owner"], question_rows)
        + table("蒸馏", ["ID", "问题", "类型", "结论", "Fact", "Claim", "证据动作", "Owner"], (
            (row.get("id"), row.get("question_ids"), row.get("result_type"), row.get("statement"), row.get("fact_ids"), row.get("claim_ids"), row.get("evidence_action_ids"), row.get("owner"))
            for row in _sorted(discovery.get("distillations"))
        ))
        + table("证据行动", ["ID", "触发问题", "受影响Requirement", "决定性证据", "状态", "Owner"], (
            (row.get("id"), row.get("trigger_question_ids"), row.get("affected_requirement_ids"), row.get("decisive_evidence"), row.get("status"), row.get("owner"))
            for row in _sorted(discovery.get("evidence_actions"))
        ))
    )

    replacements["PRODUCT_TRUTH_AND_CLAIMS"] = (
        table("Canonical Assertions与Locale表达", ["ID", "陈述", "范围", "Variant", "Fact", "Claim", "Locale表达", "状态", "Owner"], (
            (row.get("id"), row.get("statement"), row.get("application_scope"), row.get("variant_row_ids"), row.get("fact_ids"), row.get("claim_ids"), row.get("locale_expressions"), row.get("publish_status"), row.get("owner"))
            for row in _sorted(bundle.get("canonical_assertions"))
        ))
        + table("Facts", ["ID", "事实", "证据", "强度", "范围", "允许/禁止", "发布", "Owner"], (
            (row.get("id"), row.get("statement"), row.get("proving_source_ids"), row.get("evidence_strength"), row.get("scope"), {"allowed": row.get("allowed_expressions"), "prohibited": row.get("prohibited_inferences")}, row.get("publish_status"), row.get("owner"))
            for row in _sorted(bundle.get("facts"))
        ))
        + table("Claims与冲突", ["类型", "ID", "内容", "Fact", "证据", "范围/Child", "状态", "Owner"], (
            (kind, row.get("id"), row.get("text", row.get("description")), row.get("fact_ids", row.get("affected_fact_ids")), row.get("proving_source_ids", row.get("source_ids")), row.get("scope", row.get("affected_child_asins")), row.get("publish_status", row.get("status")), row.get("owner"))
            for kind, rows in (("Claim", bundle.get("claims")), ("Conflict", bundle.get("conflicts")))
            for row in _sorted(rows)
        ))
    )

    denominator = bundle.get("decision_denominator_snapshot") if isinstance(bundle.get("decision_denominator_snapshot"), dict) else {}
    requirements = bundle.get("decision_map", {}).get("requirements", []) if isinstance(bundle.get("decision_map"), dict) else []
    replacements["CUSTOMER_DECISION_AND_POSITIONING"] = (
        table("购物问题", ["ID", "问题", "优先级", "范围", "Fact", "Claim", "原生答案", "早披露", "上游Ref", "状态"], (
            (row.get("id"), row.get("buyer_question"), row.get("priority"), row.get("application_scope"), row.get("fact_ids"), row.get("claim_ids"), row.get("native_answer_required"), row.get("early_disclosure_required"), row.get("upstream_primary_carrier_ref"), row.get("status"))
            for row in _sorted(requirements)
        ))
        + table("Delegated Requirement atoms", ["Atom", "Requirement", "Variant", "Marketplace", "Locale"], (
            (row.get("id"), row.get("requirement_id"), row.get("variant_row_id"), row.get("marketplace"), row.get("locale"))
            for row in _sorted(denominator.get("atoms"))
        ))
        + table("Denominator lineage", ["状态", "来源", "Parent source hash", "Frozen at", "Requirements", "Variants", "Checksum"], ((
            denominator.get("status"), denominator.get("source"), denominator.get("source_hash"), denominator.get("frozen_at"), denominator.get("requirement_ids"), denominator.get("variant_row_ids"), denominator.get("checksum"),
        ),))
        + table("定位", ["字段", "内容"], ((key, value) for key, value in sorted(bundle.get("positioning", {}).items())))
    )

    replacements["COMPETITOR_AND_VOC"] = table("竞品观察", ["ID", "ASIN", "角色", "证据", "优势", "弱点", "决策缺口", "状态", "Owner"], (
        (row.get("id"), row.get("child_asin"), row.get("competitor_role"), row.get("source_ids"), row.get("strengths"), row.get("weaknesses"), row.get("decision_gaps"), row.get("status"), row.get("owner"))
        for row in _sorted(bundle.get("competitor_insights"))
    ))

    replacements["MODULE_CARDS"] = (
        table("A+模块施工卡", ["ID", "类型", "问题/优先级", "原生标题", "原生正文", "图像Brief/烧字", "移动端", "Fact/Claim", "范围", "验收", "禁止", "内容/证据/QA", "Owner"], (
            (row.get("id"), row.get("module_type"), {"question": row.get("decision_question"), "priority": row.get("decision_priority")}, row.get("native_headline"), row.get("native_body"), {"brief": row.get("image_brief"), "on_image": row.get("on_image_text")}, row.get("mobile_plan"), {"facts": row.get("fact_ids"), "claims": row.get("claim_ids")}, row.get("application_scope"), row.get("acceptance_tests"), {"claims": row.get("prohibited_claims"), "wrong_user": row.get("wrong_user_or_use")}, {"content": row.get("content_status"), "evidence": row.get("evidence_gate_status"), "qa": row.get("qa_status")}, row.get("owner"))
            for row in _sorted(bundle.get("modules"))
        ))
        + table("Carriers", ["ID", "类型/角色", "Module", "Backend field", "DAU", "Requirement", "Variant", "Assertion", "Fact/Claim", "Asset", "移动端", "状态/QA", "Owner"], (
            (row.get("id"), {"type": row.get("carrier_type"), "role": row.get("coverage_role")}, row.get("module_id"), row.get("backend_field_path"), row.get("answer_unit_ids"), row.get("decision_requirement_ids"), row.get("variant_row_ids"), row.get("canonical_assertion_ids"), {"facts": row.get("fact_ids"), "claims": row.get("claim_ids")}, row.get("asset_ids"), row.get("mobile_behavior"), {"content": row.get("content_status"), "qa": row.get("qa_status")}, row.get("owner"))
            for row in _sorted(bundle.get("carriers"))
        ))
        + table("Decision Answer Units", ["ID", "Atom", "Requirement", "Variant", "问题", "答案", "Module/Field", "Carrier", "Assertion", "Fact/Claim", "早披露", "范围", "状态/QA", "Owner"], (
            (row.get("id"), row.get("requirement_atom_id"), row.get("requirement_id"), row.get("variant_row_id"), row.get("buyer_question"), row.get("text"), {"module": row.get("module_id"), "field": row.get("native_field_path")}, row.get("primary_carrier_id"), row.get("canonical_assertion_ids"), {"facts": row.get("fact_ids"), "claims": row.get("claim_ids")}, row.get("early_disclosure_required"), row.get("application_scope"), {"content": row.get("content_status"), "qa": row.get("qa_status")}, row.get("owner"))
            for row in _sorted(bundle.get("decision_answer_units"))
        ))
    )

    replacements["VARIANTS_AND_ASSETS"] = (
        table("真实变体行", ["ID", "Parent", "Child", "SKU", "Pack", "颜色", "尺码", "Included", "范围", "证据", "状态"], (
            (row.get("id"), row.get("parent_asin"), row.get("child_asin"), row.get("seller_sku"), row.get("pack"), row.get("color"), row.get("size_or_capacity"), row.get("included_items"), row.get("application_scope"), row.get("source_ids"), row.get("status"))
            for row in _sorted(bundle.get("variants"))
        ))
        + table("素材与ALT", ["ID", "Module", "角色", "文件/SHA", "Variant", "Assertion", "ALT", "烧字/可见事实", "必须展示/不得改变", "生成/合成", "Fidelity", "AI规则", "范围", "QA"], (
            (row.get("id"), row.get("module_id"), row.get("asset_role"), {"file": row.get("file"), "sha": row.get("sha256")}, row.get("variant_row_ids"), row.get("canonical_assertion_ids"), row.get("alt"), {"facts": row.get("visible_facts"), "claims": row.get("claim_ids")}, {"show": row.get("must_show"), "do_not_change": row.get("must_not_change")}, {"method": row.get("generation_method"), "synthetic_person": row.get("synthetic_person")}, {"owner": row.get("product_fidelity_owner"), "status": row.get("product_fidelity_status"), "evidence": row.get("product_fidelity_evidence")}, {"checked": row.get("ai_rule_checked_at"), "sources": row.get("ai_rule_source_ids")}, row.get("application_scope"), row.get("qa_status"))
            for row in _sorted(bundle.get("assets"))
        ))
        + table("A+能力快照", ["ID", "Marketplace/Locale", "账户范围", "内容类型", "资格", "模块", "Backend fields", "限制", "证据", "时间", "状态", "Owner"], (
            (row.get("id"), f"{row.get('marketplace')}/{row.get('locale')}", row.get("account_scope"), row.get("content_type"), row.get("eligibility_status"), row.get("available_module_types"), row.get("backend_field_paths"), row.get("field_limits"), row.get("source_ids"), row.get("retrieved_at"), row.get("status"), row.get("owner"))
            for row in _sorted(bundle.get("capability_snapshots"))
        ))
    )

    rollback = bundle.get("rollback") if isinstance(bundle.get("rollback"), dict) else {}
    replacements["GATES_QA_ROLLBACK_EXPERIMENTS"] = (
        table("Coverage与Component", ["项目", "值"], (
            ("Coverage", coverage), ("Component", component),
            ("Bundle-declared conclusion（非权威；不能替代整页或发布结论）", project.get("conclusion")),
        ))
        + table("Gates", ["Gate", "状态", "证据", "失败动作", "Owner/Acceptance"], (
            (row.get("id"), row.get("status"), row.get("evidence"), row.get("failure_action"), {"owner": row.get("owner"), "acceptance": row.get("acceptance_criteria")})
            for row in _sorted(bundle.get("gates"))
        ))
        + table("Delta evidence requests", ["ID", "问题", "Requirement", "Fact", "Claim", "Module", "决定性证据", "状态", "Owner"], (
            (row.get("id"), row.get("question"), row.get("affected_requirement_ids"), row.get("affected_fact_ids"), row.get("affected_claim_ids"), row.get("affected_module_ids"), row.get("decisive_evidence"), row.get("status"), row.get("owner"))
            for row in _sorted(bundle.get("delta_evidence_requests"))
        ))
        + table("Baseline与Change Set", ["类型", "ID", "Target", "范围", "Before/After", "证据", "状态", "Owner/Approver"], (
            (kind, row.get("id"), row.get("target_id", row.get("module_id")), row.get("application_scope"), row.get("before_value", row.get("after_value")), row.get("source_ids"), row.get("status"), row.get("owner", row.get("approver")))
            for kind, values in (("Baseline", bundle.get("baseline")), ("Change", bundle.get("change_set")))
            for row in _sorted(values)
        ))
        + table("Rollback", ["状态", "Baseline", "触发条件", "方法", "验证步骤", "保护Fact", "证据", "Owner"], ((
            rollback.get("status"), rollback.get("baseline_id"), rollback.get("trigger_conditions"), rollback.get("method"), rollback.get("verification_steps"), rollback.get("protected_p0_fact_ids"), rollback.get("source_ids"), rollback.get("responsible_owner"),
        ),))
        + table("Readback", ["ID", "Child", "Locale", "状态", "字段状态", "预期/实测", "时间", "证据", "跟进/动作", "Owner"], (
            (row.get("id"), row.get("child_asin"), row.get("locale"), row.get("status"), row.get("field_statuses"), {"expected": row.get("expected_values"), "observed": row.get("observed_values")}, row.get("observed_at"), row.get("source_ids"), {"followup": row.get("followup_required"), "action": row.get("mismatch_action")}, row.get("owner"))
            for row in _sorted(bundle.get("live_readback"))
        ))
        + table("Experiments", ["ID", "假设", "Eligibility", "Variant", "指标", "Guardrail", "状态", "Owner/Acceptance"], (
            (row.get("id"), row.get("hypothesis"), row.get("eligibility_status"), row.get("variant_row_ids"), row.get("metrics"), row.get("guardrails"), row.get("status"), {"owner": row.get("owner"), "acceptance": row.get("acceptance_criteria")})
            for row in _sorted(bundle.get("experiments"))
        ))
    )

    replacements["SOURCE_REGISTER"] = table("来源", ["ID", "类型", "位置", "权威/强度", "可证明/不可证明", "范围", "获取状态", "观察时间", "Owner"], (
        (row.get("id"), row.get("source_type"), safe_link(row.get("path_or_url")), {"authority": row.get("authority"), "strength": row.get("evidence_strength")}, {"proves": row.get("proves"), "cannot_prove": row.get("cannot_prove")}, row.get("application_scope"), row.get("fetch_status"), row.get("observed_at"), row.get("owner"))
        for row in _sorted(bundle.get("sources"))
    ))

    shell = SHELL.read_text(encoding="utf-8")
    for key, value in replacements.items():
        shell = shell.replace("{{" + key + "}}", value)
    return shell


def render_aplus_report(bundle: dict[str, Any], *, source_path: Path | None = None) -> str:
    """Public fail-closed API: always obtains its own machine validation."""
    validation = validate_bundle(bundle, source_path=source_path)
    if not validation.get("structural_valid") or validation.get("template_only"):
        raise ValueError("Only a structurally valid, populated A+ Bundle 1.3 can be rendered.")
    if bundle.get("schema_version") != "1.3":
        raise ValueError("renderer accepts A+ Bundle 1.3 only")
    return _render_validated(bundle, validation)


def render(bundle: dict[str, Any], validation: dict[str, Any] | None = None) -> str:
    """Compatibility API; supplied validation is verified, never trusted."""
    actual = validate_bundle(bundle)
    if validation is not None and _validation_projection(validation) != _validation_projection(actual):
        raise ValueError("supplied validation differs from fresh machine validation")
    if not actual.get("structural_valid") or actual.get("template_only") or bundle.get("schema_version") != "1.3":
        raise ValueError("Only a structurally valid, populated A+ Bundle 1.3 can be rendered.")
    return _render_validated(bundle, actual)


def paths_alias(source: Path, output: Path) -> bool:
    source = source.expanduser()
    output = output.expanduser()
    try:
        if source.exists() and output.exists() and os.path.samefile(source, output):
            return True
    except OSError:
        pass
    return source.resolve(strict=False) == output.resolve(strict=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    args = parser.parse_args()
    source = args.bundle.expanduser()
    output = args.output.expanduser()
    if paths_alias(source, output):
        print(json.dumps({"ok": False, "error": "input and output resolve to the same file"}, ensure_ascii=False, sort_keys=True))
        return 2
    if output.suffix.casefold() not in {".html", ".htm"}:
        print(json.dumps({"ok": False, "error": "output must use .html or .htm; JSON inputs are never overwritten"}, ensure_ascii=False, sort_keys=True))
        return 2
    try:
        bundle = json.loads(source.read_text(encoding="utf-8"))
        rendered = render_aplus_report(bundle, source_path=source.resolve())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    if not output.parent.is_dir():
        print(json.dumps({"ok": False, "error": f"output parent directory does not exist: {output.parent}"}, ensure_ascii=False, sort_keys=True))
        return 2
    try:
        output.write_text(rendered, encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "output": str(output.resolve()), "bundle_sha256": canonical_sha256(bundle)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
