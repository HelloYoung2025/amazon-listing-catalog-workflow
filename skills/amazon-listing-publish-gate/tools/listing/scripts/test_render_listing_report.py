#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from render_listing_report import locator, render_listing_report


HERE = Path(__file__).resolve().parent
RENDERER = HERE / "render_listing_report.py"
FIXTURE = HERE / "integration_fixtures" / "listing-v1.1-result-received-pass.json"


class ListingRendererHardeningTests(unittest.TestCase):
    def load_bundle(self) -> dict:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def run_cli(self, source: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RENDERER), str(source), "--output", str(output)],
            cwd=HERE, text=True, capture_output=True, check=False,
        )

    def test_report_is_deterministic_machine_statused_detailed_and_read_only(self):
        bundle = self.load_bundle()
        first = render_listing_report(bundle)
        second = render_listing_report(copy.deepcopy(bundle))
        self.assertEqual(first, second)
        self.assertIn("MACHINE PACKAGE GATE: BLOCKED", first)
        self.assertIn(
            "Structural validation: PASS · Package gate: BLOCKED · "
            "Derived stage: HANDOFF_READY · Errors: 0",
            first,
        )
        self.assertNotIn("Machine result: True", first)
        self.assertNotIn('class="banner pass"', first)
        for receipt_marker in (
            "跨 Bundle 协调回执 Ledger（本地，只读）",
            "NOT_INCLUDED_IN_BUNDLE—查看 coordinator/ledger 输出",
            "纯 coordinator 最高只形成",
            "PASS_CANDIDATE",
            "--receipt-ledger &lt;path&gt;",
            "--record-receipt",
            "锁、append 和 fsync",
            "FROZEN + COMPONENT_PASS",
            "AWAITING_RESULT_ACK",
            "RESULT_RECEIVED",
            "读取 current head",
            "再次显式使用",
            "RECONCILIATION_REQUIRED + DELTA_REQUIRED",
            "旧 AWAIT 不可回放",
            "SUPERSEDED",
            "semantic_revision + 1",
            "Group manifest 只读确认",
            "每个 member 必须绑定自己的 JSONL ledger",
            "本页不创建、保存、编辑或追加 ledger",
            "显式 local evidence write",
            "不是 Amazon、Seller Central、ERP、网络或其他外部写入",
            "不是数字签名",
            "不是可信时间戳",
            "不是 Fact/Claim 或证据真实性证明",
            "不是 Amazon 后台/平台回执",
            "不是发布授权",
            "不是 LIVE_MATCH/LIVE_PASS 证明",
            "替换整个 ledger、Skill 或 validator",
            "外部可信存储或签名",
        ):
            self.assertIn(receipt_marker, first)
        for obsolete in ("--prior-receipt", "coordinator JSON sidecar"):
            self.assertNotIn(obsolete, first)
        self.assertNotIn("{{COORDINATION_RECEIPT_VALUE}}", first)
        for marker in (
            "Owner", "Acceptance", "Blocker", 'scope="col"', "PTD字段闭合",
            "Surface Assignments", "P0 Decision Answer Units", "A+冻结交接",
            "Rollback", "Amazon Readback", "@media print", "@media(max-width:390px)",
            "@media(max-width:768px)", ".table-wrap:focus-visible",
        ):
            self.assertIn(marker, first)
        for forbidden in ("<script", "<form", "<input", "<button", "localStorage", "fetch("):
            self.assertNotIn(forbidden, first)

        wraps = re.findall(r'<div class="table-wrap"([^>]*)>', first)
        self.assertTrue(wraps)
        self.assertEqual(len(wraps), first.count("<table>"))
        for attributes in wraps:
            self.assertIn('tabindex="0"', attributes)
            self.assertIn('role="region"', attributes)
            self.assertRegex(attributes, r'aria-label="[^"]+"')

    def test_report_uses_contracted_discovery_values_and_shows_governance(self):
        rendered = render_listing_report(self.load_bundle())
        for value in (
            "TRUTH", "Q-1", "What is included?", "R-1", "One spatula",
            "FACT_LEAD", "SRC-PRODUCT", "Current account field mapping",
            "OFFICIAL_CURRENT", "Who-Scenario-Problem", "MULTI_SOURCE_HEURISTIC",
            "RS-1", "account-2026-08-28", "CURRENT 是有范围和刷新条件的证据状态",
            "类目调查适配器", "generic", "READY", "Renderer：1.2",
        ):
            self.assertIn(value, rendered)
        self.assertIn(
            "<td>R-1</td><td>Q-1</td><td>What is included?</td>"
            "<td>One spatula</td><td>FACT_LEAD</td>",
            rendered,
        )
        self.assertNotIn("<td>R-1</td><td></td><td>One spatula</td>", rendered)

    def test_malformed_and_unsafe_locator_is_escaped_text(self):
        for raw in ("http://[broken", "javascript:alert(1)", "file:///tmp/private"):
            rendered = locator(raw)
            self.assertTrue(rendered.startswith("<code>"))
            self.assertNotIn("<a ", rendered)
        bundle = self.load_bundle()
        bundle["sources"][0]["locator"] = "http://[broken"
        rendered = render_listing_report(bundle)
        self.assertIn("http://[broken", rendered)
        self.assertNotIn('href="http://[broken', rendered)

    def test_cli_rejects_input_output_alias_symlink_and_json_output_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "unique-bundle.json"
            original = FIXTURE.read_bytes()
            source.write_bytes(original)

            same = self.run_cli(source, source)
            self.assertEqual(same.returncode, 2)
            self.assertEqual(source.read_bytes(), original)

            alias = root / "alias.html"
            alias.symlink_to(source)
            linked = self.run_cli(source, alias)
            self.assertEqual(linked.returncode, 2)
            self.assertEqual(source.read_bytes(), original)

            json_output = root / "do-not-overwrite.json"
            json_output.write_text("UNIQUE SENTINEL", encoding="utf-8")
            rejected = self.run_cli(source, json_output)
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(json_output.read_text(encoding="utf-8"), "UNIQUE SENTINEL")

    def test_true_cli_is_deterministic_and_structural_failure_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.html"
            second = root / "second.html"
            one = self.run_cli(FIXTURE, first)
            two = self.run_cli(FIXTURE, second)
            self.assertEqual(one.returncode, 0, one.stdout + one.stderr)
            self.assertEqual(two.returncode, 0, two.stdout + two.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            malformed = root / "malformed.json"
            malformed.write_text('{"schema_version":"1.1"}', encoding="utf-8")
            absent = root / "absent.html"
            failed = self.run_cli(malformed, absent)
            self.assertEqual(failed.returncode, 2)
            self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
