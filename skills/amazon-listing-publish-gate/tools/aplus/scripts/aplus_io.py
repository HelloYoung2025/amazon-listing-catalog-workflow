#!/usr/bin/env python3
"""Fail-closed local JSON I/O adapters for the A+ validator and migrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aplus_entry_domain import local_parent_reference_issue


def read_json_document(path: Path) -> tuple[Any | None, str | None]:
    """Read one UTF-8 JSON document without leaking filesystem exceptions."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"file not found: {path}"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"cannot read JSON: {exc}"


def read_local_parent_bundle(
    reference: str,
    bundle_source_path: Path | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve and read a local parent JSON object for legacy embedded mode."""
    syntax_issue = local_parent_reference_issue(reference)
    if syntax_issue:
        return None, syntax_issue
    parent_path = Path(reference).expanduser()
    if not parent_path.is_absolute():
        base = bundle_source_path.parent if bundle_source_path is not None else Path.cwd()
        parent_path = base / parent_path
    try:
        parent_path = parent_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return None, f"cannot resolve local parent bundle: {exc}"
    if not parent_path.is_file():
        return None, f"parent bundle is not a regular file: {parent_path}"
    payload, issue = read_json_document(parent_path)
    if issue:
        if issue.startswith("cannot read JSON: "):
            issue = "cannot read local parent bundle JSON: " + issue.removeprefix("cannot read JSON: ")
        return None, issue
    if not isinstance(payload, dict):
        return None, "local parent bundle must be a JSON object"
    return payload, None
