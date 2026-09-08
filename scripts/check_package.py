#!/usr/bin/env python3
"""Verify the complete distribution or three installed sibling skills (stdlib only)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "amazon-listing-catalog-workflow",
    "amazon-premium-aplus-planner",
    "amazon-listing-publish-gate",
)


def verify(skill_root: Path, manifest_path: Path = ROOT / "package-manifest.json") -> list[str]:
    errors = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if set(manifest["skills"]) != set(NAMES):
        return ["Manifest must contain exactly the three companion skills."]
    for name in NAMES:
        directory = skill_root / name
        expected = manifest["skills"][name]
        if "SKILL.md" not in expected:
            errors.append(f"{name}: missing entry in manifest")
        actual = set()
        if directory.is_symlink():
            errors.append(f"{name}: symlinked skill root is not a self-contained package")
            continue
        for file in directory.rglob("*"):
            relative = file.relative_to(directory).as_posix()
            if "__pycache__" in file.parts or file.suffix == ".pyc":
                continue
            if file.is_symlink():
                errors.append(f"{name}/{relative}: symlink is not allowed")
            elif file.is_file():
                actual.add(relative)
        for missing in sorted(set(expected) - actual):
            errors.append(f"Missing: {name}/{missing}")
        for extra in sorted(actual - set(expected)):
            errors.append(f"Unexpected: {name}/{extra}")
        for relative in sorted(actual & set(expected)):
            file = directory / relative
            if hashlib.sha256(file.read_bytes()).hexdigest() != expected[relative]:
                errors.append(f"SHA-256 mismatch: {name}/{relative}")
            if file.suffix != ".md":
                continue
            text = file.read_text(encoding="utf-8")
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                link = unquote(link.strip("<>").split("#", 1)[0])
                if not link or re.match(r"[a-zA-Z]+:", link):
                    continue
                resolved = (file.parent / link).resolve()
                if not resolved.is_relative_to(skill_root.resolve()) or not resolved.exists():
                    errors.append(f"Broken local link: {name}/{relative} -> {link}")
            for dependency, resource in re.findall(
                r"\$(amazon-[a-z0-9-]+)(/[^\s`，。；）]*[a-zA-Z0-9])?", text
            ):
                target = skill_root / dependency / (resource or "/SKILL.md").lstrip("/")
                if dependency not in NAMES or not target.is_file():
                    errors.append(f"Missing companion resource: {name}/{relative} -> {dependency}{resource}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-root", type=Path, help="Skill root containing the three siblings")
    args = parser.parse_args()
    skill_root = args.installed_root or ROOT / "skills"
    errors = verify(skill_root)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: 3 skills, 91 files, hashes and references verified at {skill_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
