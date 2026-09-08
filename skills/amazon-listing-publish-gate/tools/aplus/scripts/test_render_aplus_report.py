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

from render_aplus_report import render, render_aplus_report
from validate_bundle import validate_bundle


HERE = Path(__file__).resolve().parent
RENDERER = HERE / "render_aplus_report.py"
FIXTURE = HERE / "fixtures" / "aplus-v1.3-embedded-pass.json"


class APlusRendererHardeningTests(unittest.TestCase):
    def load_bundle(self) -> dict:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def run_cli(self, source: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RENDERER), str(source), "--output", str(output)],
            cwd=HERE, text=True, capture_output=True, check=False,
        )

    def test_report_is_deterministic_detailed_responsive_printable_and_read_only(self):
        bundle = self.load_bundle()
        first = render_aplus_report(bundle)
        second = render_aplus_report(copy.deepcopy(bundle))
        self.assertEqual(first, second)
        self.assertIn(
            "Bundle-declared conclusion（非权威；不能替代整页或发布结论）",
            first,
        )
        self.assertNotIn("Project conclusion（仅记录）", first)
        for receipt_marker in (
            "跨 Bundle 协调回执 Ledger",
            "NOT_INCLUDED_IN_A_PLUS_BUNDLE—查看 Parent coordinator/ledger 输出",
            "A+ 只交付 COMPONENT_PASS 或 DELTA_REQUIRED",
            "A+ 不生成、不确认 coordination receipt",
            "不读取或写入 JSONL ledger",
            "纯 coordinator 最高只形成 PASS_CANDIDATE",
            "--receipt-ledger &lt;path&gt;",
            "--record-receipt",
            "锁、append 和 fsync",
            "FROZEN + COMPONENT_PASS",
            "AWAITING_RESULT_ACK 写为 current head",
            "RESULT_RECEIVED",
            "读取 current head",
            "再次显式使用 --record-receipt",
            "DELTA_REQUIRED 由 Parent 协调并写为新 head",
            "旧 AWAIT 不可回放",
            "SUPERSEDED",
            "semantic_revision + 1",
            "Group manifest 只读确认",
            "每个 member 必须绑定自己的 JSONL ledger",
            "本 HTML 不创建、保存、编辑或追加 ledger",
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
        self.assertNotIn("{{COORDINATION_RECEIPT_BOUNDARY}}", first)
        for marker in (
            "机器结果", "Owner", "Acceptance", "Blocker", 'scope="col"',
            "苏格拉底问题与回答", "Canonical Assertions与Locale表达", "A+模块施工卡",
            "Carriers", "Decision Answer Units", "素材与ALT", "Rollback", "Readback",
            "@media (max-width: 390px)", "@media (max-width: 640px)", "@media print",
            ".table-wrap:focus-visible",
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

    def test_report_shows_category_adapter_and_machine_derived_discovery_state(self):
        rendered = render_aplus_report(self.load_bundle())
        for value in (
            "Machine evidence gate", "PARENT_BOUND", "Machine-derived closure",
            "NOT_REQUIRED_WITH_REASON", "类目调查适配器", "generic",
            "Verify the included item.", "Inspect the scoped product evidence.",
            "Wrong included-item expectation.", "Answer and image match the selected child.",
            "Renderer v1.2",
        ):
            self.assertIn(value, rendered)
        self.assertNotIn("<td>Status</td><td></td>", rendered)

    def test_public_render_api_revalidates_and_rejects_fake_green_validation(self):
        bundle = self.load_bundle()
        actual = validate_bundle(bundle)
        fake = copy.deepcopy(actual)
        fake["result_level"] = "PASS"
        with self.assertRaisesRegex(ValueError, "fresh machine validation"):
            render(bundle, fake)

        invalid_business = self.load_bundle()
        invalid_business["decision_answer_units"][0]["text"] = "Answer absent from native field."
        validation = validate_bundle(invalid_business)
        self.assertTrue(validation["structural_valid"])
        self.assertEqual(validation["result_level"], "INVALID")
        rendered = render_aplus_report(invalid_business)
        self.assertIn('data-status="INVALID"', rendered)
        self.assertNotIn('<strong>COMPONENT_PASS</strong>', rendered)

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
            malformed.write_text('{"schema_version":"1.3"}', encoding="utf-8")
            absent = root / "absent.html"
            failed = self.run_cli(malformed, absent)
            self.assertEqual(failed.returncode, 2)
            self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
