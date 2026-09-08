#!/usr/bin/env python3
"""Render a deterministic, read-only Listing Bundle v1.1 staff report."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from validate_listing_bundle import validate_listing_bundle
from validate_listing_bundle_v11 import canonical_parent_hash


HERE = Path(__file__).resolve().parent
SHELL = HERE.parent / "assets" / "listing-staff-entry-shell.html"
RENDERER_VERSION = "1.2"


def esc(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return html.escape(str(value if value is not None else ""), quote=True)


def locator(value: Any) -> str:
    text = str(value or "")
    try:
        parsed = urlsplit(text)
    except ValueError:
        return f"<code>{esc(text)}</code>"
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        safe = esc(text)
        return f'<a href="{safe}" rel="noreferrer noopener">{safe}</a>'
    return f"<code>{esc(text)}</code>"


def _objects(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _sorted(items: Any) -> list[dict[str, Any]]:
    return sorted(_objects(items), key=lambda row: str(row.get("id", "")))


def _table_rows(
    title: str,
    headers: list[str],
    rows: Iterable[Iterable[Any]],
    *,
    caption: str | None = None,
) -> str:
    rendered_rows = [
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>"
        for row in rows
    ]
    if not rendered_rows:
        rendered_rows.append(f'<tr><td colspan="{len(headers)}" class="muted">无记录</td></tr>')
    heads = "".join(f'<th scope="col">{esc(label)}</th>' for label in headers)
    table_label = f"{caption or title}，可横向滚动查看完整表格"
    return (
        f'<article class="card"><h2>{esc(title)}</h2>'
        f'<div class="table-wrap" tabindex="0" role="region" aria-label="{esc(table_label)}"><table>'
        f'<caption>{esc(caption or title)}</caption><thead><tr>{heads}</tr></thead>'
        f"<tbody>{''.join(rendered_rows)}</tbody></table></div></article>"
    )


def _status_card(
    title: str, owner: Any, acceptance: Any, blocker: Any, status: Any,
) -> str:
    return (
        '<article class="card third responsibility">'
        f'<h2>{esc(title)}</h2><dl><dt>Owner</dt><dd>{esc(owner or "UNASSIGNED")}</dd>'
        f'<dt>Acceptance</dt><dd>{esc(acceptance or "UNDEFINED")}</dd>'
        f'<dt>Blocker</dt><dd>{esc(blocker or "NONE RECORDED")}</dd>'
        f'<dt>Machine status</dt><dd><span class="state {esc(status)}">{esc(status)}</span></dd>'
        '</dl></article>'
    )


def _source_table(bundle: dict[str, Any]) -> str:
    body: list[str] = []
    for row in _sorted(bundle.get("sources")):
        body.append(
            "<tr>"
            f"<td>{esc(row.get('id'))}</td><td>{esc(row.get('type'))}</td>"
            f"<td>{locator(row.get('locator'))}</td><td>{esc(row.get('authority'))}</td>"
            f"<td>{esc(row.get('evidence_level'))}</td><td>{esc(row.get('status'))}</td>"
            f"<td>{esc(row.get('proves'))}</td><td>{esc(row.get('cannot_prove'))}</td>"
            f"<td>{esc(row.get('application_scope'))}</td><td>{esc(row.get('retrieved_at'))}</td>"
            f"<td>{esc(row.get('capture_metadata'))}</td></tr>"
        )
    if not body:
        body.append('<tr><td colspan="11" class="muted">无记录</td></tr>')
    headers = ("ID", "类型", "定位", "权威", "等级", "状态", "可证明", "不可证明", "适用范围", "时间", "截图元数据")
    return (
        '<article class="card"><h2>证据与附件读取</h2>'
        '<div class="table-wrap" tabindex="0" role="region" aria-label="证据与附件读取，可横向滚动查看完整表格"><table>'
        '<caption>仅 HTTP(S) 会显示为链接；畸形或其他协议定位符只显示转义文本。</caption>'
        '<thead><tr>' + "".join(f'<th scope="col">{esc(label)}</th>' for label in headers) + '</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table></div></article>"
    )


def render_listing_report(bundle: dict[str, Any]) -> str:
    """Validate internally and render; callers cannot inject a green result."""
    if bundle.get("schema_version") != "1.1":
        raise ValueError("renderer accepts Listing Bundle v1.1 only")
    result = validate_listing_bundle(bundle)
    if not result.get("schema_valid"):
        raise ValueError("structurally invalid bundle: " + "; ".join(result.get("errors", [])))

    project = bundle.get("project") if isinstance(bundle.get("project"), dict) else {}
    scope = bundle.get("scope") if isinstance(bundle.get("scope"), dict) else {}
    discovery = bundle.get("discovery") if isinstance(bundle.get("discovery"), dict) else {}
    closure = discovery.get("closure") if isinstance(discovery.get("closure"), dict) else {}
    ptd = bundle.get("ptd_field_inventory") if isinstance(bundle.get("ptd_field_inventory"), dict) else {}
    handoff = bundle.get("enriched_content_handoff") if isinstance(bundle.get("enriched_content_handoff"), dict) else {}
    authorization = bundle.get("publish_authorization") if isinstance(bundle.get("publish_authorization"), dict) else {}
    derived_gates = result.get("derived_gates") if isinstance(result.get("derived_gates"), dict) else {}
    package_gate = str(derived_gates.get("package", "BLOCKED"))
    errors = [str(row) for row in result.get("errors", [])]
    warnings = [str(row) for row in result.get("warnings", [])]
    machine_pass = result.get("ok") is True and package_gate == "PASS"
    if machine_pass:
        banner_class, banner_title = "pass", "MACHINE PACKAGE GATE: PASS"
    elif package_gate in {"CONDITIONAL", "HOLD"}:
        banner_class, banner_title = "conditional", f"MACHINE PACKAGE GATE: {package_gate}"
    else:
        banner_class, banner_title = "blocked", f"MACHINE PACKAGE GATE: {package_gate}"

    sha = canonical_parent_hash(bundle)
    meta = "".join(
        f'<span class="pill">{esc(label)}：{esc(value)}</span>'
        for label, value in (
            ("Bundle", bundle.get("schema_version")), ("Renderer", RENDERER_VERSION),
            ("Project", project.get("project_id")), ("Boundary", bundle.get("execution_boundary")),
            ("Derived stage", result.get("derived_stage")),
            ("Marketplace/Locale", f"{scope.get('marketplace', '')}/{scope.get('locale', '')}"),
        )
    )

    interview_questions: list[tuple[Any, ...]] = []
    questions_by_response: dict[str, dict[str, Any]] = {}
    for round_row in _sorted(discovery.get("interview_rounds")):
        for question in _objects(round_row.get("questions")):
            response_id = str(question.get("response_id", ""))
            if response_id:
                questions_by_response[response_id] = question
            interview_questions.append((
                round_row.get("id"), round_row.get("round_type"), question.get("id"),
                question.get("question"), response_id,
                question.get("impact_dimensions"),
            ))
    evidence_pass = discovery.get("evidence_pass") if isinstance(discovery.get("evidence_pass"), dict) else {}
    blockers = errors or ["NONE FROM VALIDATOR"]
    acceptance_text = (
        "Package gate PASS；但仍不代表事实真实、规则当前、获准发布或前台 LIVE_MATCH。"
        if machine_pass else "逐项关闭 Validator 阻断并重新验证；人工勾选不能覆盖机器结果。"
    )

    content = "".join((
        _status_card("Listing责任与验收", project.get("owner"), acceptance_text, errors[0] if errors else "NONE", package_gate),
        _status_card(
            "Discovery责任与验收", closure.get("owner"), closure.get("reason"),
            "P0 OPEN evidence action" if any(row.get("status") == "OPEN" for row in _objects(discovery.get("evidence_actions"))) else "NONE",
            closure.get("status", "NOT_STARTED"),
        ),
        _status_card(
            "发布边界与验收", authorization.get("authorizer"),
            "需要独立授权、后台回执和逐 child/locale 前台回读。",
            "本只读报告不能授权或提交。", authorization.get("status", "NOT_AUTHORIZED"),
        ),
        _table_rows("机器派生 Gate", ["Gate", "状态"], ((key, value) for key, value in sorted(derived_gates.items()))),
        _table_rows("执行范围与身份", ["维度", "值"], (
            ("Marketplace", scope.get("marketplace")), ("Locale", scope.get("locale")),
            ("Seller scope", scope.get("seller_scope")), ("Parent ASIN", scope.get("parent_asins")),
            ("Included children", scope.get("intended_child_asins")), ("Excluded children", scope.get("excluded_child_asins")),
            ("Pack", scope.get("packs")), ("Color", scope.get("colors")), ("Size", scope.get("sizes")),
            ("Catalog identity", bundle.get("catalog_context")),
        )),
        _table_rows("当前规则快照", ["ID", "Marketplace/Locale", "Seller scope", "Product Type", "Parentage", "Data plane", "Schema", "Requirements", "Enforced", "证据", "获取时间", "状态", "Checksum", "刷新条件"], (
            (row.get("id"), f"{row.get('marketplace', '')}/{row.get('locale', '')}", row.get("seller_scope"), row.get("product_type"), row.get("parentage_level"), row.get("data_plane"), row.get("schema_version"), row.get("requirements"), row.get("requirements_enforced"), row.get("source_ids"), row.get("retrieved_at"), row.get("status"), row.get("checksum"), row.get("refresh_trigger"))
            for row in _sorted(bundle.get("rule_snapshots"))
        ), caption="CURRENT 是有范围和刷新条件的证据状态，不是永久规则声明。"),
        _table_rows("方法与经验注册表", ["ID", "方法", "分类", "可用于Gate", "证据", "状态", "观察时间", "刷新条件"], (
            (row.get("id"), row.get("name"), row.get("classification"), row.get("gate_eligible"), row.get("source_ids"), row.get("status"), row.get("observed_at"), row.get("refresh_trigger"))
            for row in _sorted(bundle.get("method_registry"))
        ), caption="官方/账户规则、目标商品证据、经验方法与社区假设必须保持分层。"),
        _table_rows("类目调查适配器", ["字段", "值"], (
            ("Name", bundle.get("category_adapter", {}).get("name")),
            ("Version", bundle.get("category_adapter", {}).get("version")),
            ("Status", bundle.get("category_adapter", {}).get("status")),
            ("Question prompts", bundle.get("category_adapter", {}).get("question_prompts")),
            ("Evidence probes", bundle.get("category_adapter", {}).get("evidence_probes")),
            ("Return risks", bundle.get("category_adapter", {}).get("return_risks")),
            ("QA checks", bundle.get("category_adapter", {}).get("qa_checks")),
        ), caption="适配器只提供调查与QA探针，不创建或覆盖Amazon PTD字段。"),
        _source_table(bundle),
        _table_rows("Facts", ["ID", "事实", "证据", "等级", "验证", "发布", "范围", "允许表达", "禁止推导", "Owner"], (
            (row.get("id"), row.get("statement"), row.get("proving_source_ids"), row.get("evidence_level"), row.get("verification_status"), row.get("content_status"), row.get("application_scope"), row.get("allowed_expression"), row.get("prohibited_inferences"), row.get("owner"))
            for row in _sorted(bundle.get("facts"))
        )),
        _table_rows("Claims", ["ID", "Claim", "Fact", "证据", "支持", "发布", "范围", "Owner"], (
            (row.get("id"), row.get("text"), row.get("fact_ids"), row.get("proving_source_ids"), row.get("support_status"), row.get("content_status"), row.get("application_scope"), row.get("owner"))
            for row in _sorted(bundle.get("claims"))
        )),
        _table_rows("Conflict Ledger", ["ID", "描述", "Fact", "Claim", "Child", "状态", "处置", "Owner"], (
            (row.get("id"), row.get("description"), row.get("affected_fact_ids"), row.get("affected_claim_ids"), row.get("affected_child_asins"), row.get("status"), row.get("resolution"), row.get("owner"))
            for row in _sorted(bundle.get("conflicts"))
        )),
        _table_rows("Discovery证据初筛", ["状态", "来源", "观察"], ((evidence_pass.get("status"), evidence_pass.get("source_ids"), evidence_pass.get("observations")),)),
        _table_rows("苏格拉底问题轮次", ["Round", "轮次类型", "Question", "问题", "Response", "影响维度"], interview_questions),
        _table_rows("正式回答", ["ID", "Question", "问题", "回答", "分类", "状态", "P0影响", "证据", "Owner"], (
            (row.get("id"), questions_by_response.get(str(row.get("id", "")), {}).get("id"), questions_by_response.get(str(row.get("id", "")), {}).get("question"), row.get("answer"), row.get("classification"), row.get("status"), row.get("p0_impact"), row.get("source_ids"), row.get("owner"))
            for row in _sorted(discovery.get("responses"))
        )),
        _table_rows("蒸馏与证据行动", ["ID", "类型/状态", "输入", "结论/决定性证据", "Fact/Requirement", "Owner"], (
            (row.get("id"), row.get("result_type", row.get("status")), row.get("response_ids", row.get("trigger_response_ids")), row.get("statement", row.get("decisive_evidence")), row.get("fact_ids", row.get("affected_requirement_ids")), row.get("owner"))
            for row in _sorted(discovery.get("distillations")) + _sorted(discovery.get("evidence_actions"))
        )),
        _table_rows("VOC、竞品与市场结论", ["类型", "记录"], (
            ("Status", bundle.get("market_research", {}).get("status")),
            ("Sources", bundle.get("market_research", {}).get("source_ids")),
            ("VOC", bundle.get("market_research", {}).get("voc_observations")),
            ("Competitors", bundle.get("market_research", {}).get("competitor_observations")),
            ("Conclusions", bundle.get("market_research", {}).get("conclusions")),
        )),
        _table_rows("PTD字段闭合", ["Field", "Resolution", "Requirement", "Trigger", "Closure", "P0", "Evidence", "Owner"], (
            (row.get("id"), row.get("field_resolution_id"), row.get("requirement_status"), row.get("trigger_status"), row.get("closure_status"), row.get("p0_relevant"), row.get("evidence_source_ids"), row.get("owner"))
            for row in _sorted(ptd.get("expected_fields"))
        ), caption=f"Product Type={ptd.get('product_type', '')} · Inventory={ptd.get('status', '')} · declared={ptd.get('declared_field_count', 0)}"),
        _table_rows("真实字段解析", ["ID", "角色", "Key", "UI", "Plane", "Surface", "存在/可编辑/适用", "可见性", "字符限制", "规则", "范围", "状态", "Owner"], (
            (row.get("id"), row.get("semantic_role"), row.get("canonical_key"), row.get("ui_label"), row.get("data_plane"), row.get("surface"), f"{row.get('exists')}/{row.get('editable')}/{row.get('applicable')}", row.get("visibility"), row.get("max_characters"), row.get("rule_snapshot_ids"), row.get("application_scope"), row.get("status"), row.get("owner"))
            for row in _sorted(bundle.get("field_resolutions"))
        )),
        _table_rows("真实变体行", ["Variant", "Parent", "Child", "SKU", "Pack", "Color", "Size", "Included", "证据", "状态"], (
            (row.get("id"), row.get("parent_asin"), row.get("child_asin"), row.get("seller_sku"), row.get("pack"), row.get("color"), row.get("size"), row.get("included_items"), row.get("source_ids"), row.get("status"))
            for row in _sorted(bundle.get("variant_topology"))
        )),
        _table_rows("购物问题与页面分配", ["ID", "问题", "优先级", "范围", "Fact", "Claim", "早披露", "上游Ref", "Surface", "状态"], (
            (row.get("id"), row.get("buyer_question"), row.get("priority"), row.get("application_scope"), row.get("fact_ids"), row.get("claim_ids"), row.get("early_disclosure_required"), row.get("upstream_primary_carrier_ref"), row.get("assigned_surface"), row.get("status"))
            for row in _sorted(bundle.get("decision_map", {}).get("requirements"))
        )),
        _table_rows("P0原子分母", ["Atom", "Requirement", "Variant", "Marketplace", "Locale"], (
            (row.get("id"), row.get("requirement_id"), row.get("variant_row_id"), row.get("marketplace"), row.get("locale"))
            for row in _sorted(bundle.get("decision_denominator_snapshot", {}).get("atoms"))
        )),
        _table_rows("Surface Assignments", ["ID", "Requirement", "Surface", "Carrier", "Field", "Supporting", "范围", "状态", "Owner"], (
            (row.get("id"), row.get("requirement_id"), row.get("primary_surface"), row.get("primary_carrier_kind"), row.get("field_resolution_id"), row.get("supporting_surfaces"), row.get("application_scope"), row.get("status"), row.get("owner"))
            for row in _sorted(bundle.get("surface_assignments"))
        )),
        _table_rows("Canonical Assertions与Locale边界", ["ID", "陈述", "Fact", "Claim", "范围", "状态", "Owner"], (
            (row.get("id"), row.get("statement"), row.get("fact_ids"), row.get("claim_ids"), row.get("application_scope"), row.get("status"), row.get("owner"))
            for row in _sorted(bundle.get("canonical_assertions"))
        )),
        _table_rows("Item name / Item highlights / 五点等候选", ["Candidate", "Field", "角色", "目标值", "范围", "Fact", "Claim", "内容", "QA", "Owner"], (
            (row.get("id"), row.get("field_resolution_id"), row.get("semantic_role"), row.get("value"), row.get("application_scope"), row.get("fact_ids"), row.get("claim_ids"), row.get("content_status"), row.get("qa_status"), row.get("owner"))
            for row in _sorted(bundle.get("field_candidates"))
        )),
        _table_rows("P0 Decision Answer Units", ["Unit", "Atom", "Requirement", "Variant", "原生答案", "Candidate", "Assertion", "Fact", "Claim", "状态", "Owner"], (
            (row.get("id"), row.get("atom_id"), row.get("requirement_id"), row.get("variant_row_id"), row.get("answer_text"), row.get("field_candidate_id"), row.get("canonical_assertion_ids"), row.get("fact_ids"), row.get("claim_ids"), row.get("status"), row.get("owner"))
            for row in _sorted(bundle.get("decision_answer_units"))
        )),
        _table_rows("语义一致性矩阵", ["ID", "Assertion", "Candidates", "状态", "Owner"], (
            (row.get("id"), row.get("canonical_assertion_id"), row.get("field_candidate_ids"), row.get("status"), row.get("owner"))
            for row in _sorted(bundle.get("semantic_consistency_matrix"))
        )),
        _table_rows("A+冻结交接", ["Snapshot", "状态", "合同", "Parent SHA", "范围", "Variants", "Requirements", "Atoms", "Assertions", "Hashes", "禁止动作", "Owner"], ((
            handoff.get("snapshot_id"), handoff.get("status"), handoff.get("contract_version"), handoff.get("parent_bundle_sha256"), handoff.get("application_scope"), handoff.get("variant_row_ids"), handoff.get("decision_requirements"), handoff.get("requirement_atoms"), handoff.get("canonical_assertion_ids"), {key: handoff.get(key) for key in ("discovery_closure_hash", "ptd_inventory_hash", "decision_denominator_hash", "checksum")}, handoff.get("prohibited_actions"), handoff.get("owner"),
        ),), caption="A+ modules/carriers/assets/ALT/locale copy 由匹配此 Snapshot 的 A+ 1.3 报告承载；本报告不伪造子层结果。"),
        _table_rows("Baseline与Change Set", ["类型", "ID", "Target", "Field", "Before/After", "状态", "Owner/Approver", "证据"], (
            (kind, row.get("id"), row.get("target_id"), row.get("field_resolution_id"), row.get("before_value", row.get("after_value")), row.get("status"), row.get("owner", row.get("approver")), row.get("source_ids"))
            for kind, values in (("Baseline", bundle.get("baseline")), ("Change", bundle.get("change_set")))
            for row in _sorted(values)
        )),
        _table_rows("Rollback", ["ID", "Target/范围", "触发条件", "恢复值/步骤", "状态", "Owner", "证据"], (
            (row.get("id"), row.get("target_id", row.get("rollback_scope")), row.get("trigger_conditions"), row.get("restore_value", row.get("verification_steps")), row.get("status"), row.get("owner", row.get("responsible_owner")), row.get("source_ids"))
            for row in _sorted(bundle.get("rollback"))
        )),
        _table_rows("Amazon Readback", ["ID", "Child", "Locale", "系统", "状态", "前台PASS", "期望/实测", "时间", "证据", "Owner"], (
            (row.get("id"), row.get("child_asin"), row.get("locale"), row.get("system"), row.get("status"), row.get("live_pass"), {"expected": row.get("expected_value"), "observed": row.get("observed_value")}, row.get("observed_at"), row.get("source_ids"), row.get("owner"))
            for row in _sorted(bundle.get("live_readback"))
        ), caption="ACCEPTED_BACKEND 不等于 LIVE_MATCH；必须逐 child/locale 回读。"),
        _table_rows("实验与人工审核记录", ["类型", "ID", "目标/内容", "状态", "Owner", "Acceptance"], (
            (kind, row.get("id"), row.get("hypothesis", row.get("review_scope", row.get("qa_checks"))), row.get("status"), row.get("owner"), row.get("acceptance_criteria"))
            for kind, values in (("Experiment", bundle.get("experiment_registry")), ("Gate review", bundle.get("gate_reviews")))
            for row in _sorted(values)
        )),
        _table_rows("机器阻断与警告", ["类型", "记录"], ([("ERROR", row) for row in blockers] + [("WARNING", row) for row in warnings])),
    ))

    shell = SHELL.read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": esc(project.get("title") or "Amazon Listing 全页面只读施工报告"),
        "{{META}}": meta, "{{BANNER_CLASS}}": banner_class,
        "{{BANNER_TITLE}}": banner_title,
        "{{BANNER_BODY}}": esc(
            f"Structural validation: {'PASS' if result.get('ok') is True else 'FAIL'} · "
            f"Package gate: {package_gate} · Derived stage: {result.get('derived_stage')} · "
            f"Errors: {len(errors)} · 本报告不能授权线上写入。"
        ),
        "{{COORDINATION_RECEIPT_VALUE}}": "NOT_INCLUDED_IN_BUNDLE—查看 coordinator/ledger 输出",
        "{{CONTENT}}": content, "{{BUNDLE_SHA}}": esc(sha),
    }
    for token, value in replacements.items():
        shell = shell.replace(token, value)
    return shell


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
    parser = argparse.ArgumentParser(description="Render deterministic read-only Listing v1.1 report")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
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
        rendered = render_listing_report(bundle)
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
    print(json.dumps({"ok": True, "output": str(output.resolve()), "bundle_sha256": canonical_parent_hash(bundle)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
