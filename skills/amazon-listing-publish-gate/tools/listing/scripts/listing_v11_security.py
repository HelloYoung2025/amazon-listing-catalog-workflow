#!/usr/bin/env python3
"""Deterministic Unicode safety checks for JSON Listing contracts."""

from __future__ import annotations

import unicodedata
from typing import Any


def _unsafe_reason(text: str) -> str | None:
    if unicodedata.normalize("NFC", text) != text:
        return "text is not NFC-normalized"
    for char in text:
        code = ord(char)
        category = unicodedata.category(char)
        if category in {"Cf", "Cs", "Co", "Cn"}:
            return f"contains disallowed Unicode category {category} at U+{code:04X}"
        if category == "Cc" and char not in {"\n", "\r", "\t"}:
            return f"contains control character U+{code:04X}"
        if 0xFDD0 <= code <= 0xFDEF or code & 0xFFFF in {0xFFFE, 0xFFFF}:
            return f"contains Unicode noncharacter U+{code:04X}"
    return None


def unicode_issues(value: Any, path: str = "$") -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if isinstance(value, str):
        reason = _unsafe_reason(value)
        if reason:
            issues.append((path, reason))
    elif isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            safe_key = ascii(key_text)[1:-1]
            reason = _unsafe_reason(key_text)
            if reason:
                issues.append((f"{path}.<key>", reason))
            issues.extend(unicode_issues(child, f"{path}.{safe_key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(unicode_issues(child, f"{path}[{index}]"))
    return issues
