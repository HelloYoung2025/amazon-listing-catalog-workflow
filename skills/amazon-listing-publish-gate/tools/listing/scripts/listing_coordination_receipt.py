#!/usr/bin/env python3
"""Deterministic, content-addressed receipts for Listing/A+ coordination.

The receipt chain is a local audit and accidental-deletion control.  It is not
an external signature, trusted timestamp, or proof that the underlying facts
are true.  The cross-bundle coordinator remains read-only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping


RECEIPT_VERSION = "listing-coordination-receipt/1.1"
RECEIPT_RESULTS = {"AWAITING_RESULT_ACK", "DELTA_REQUIRED", "PASS"}
RECEIPT_KEYS = {
    "contract_version", "receipt_id", "project_id", "chain_id",
    "parent_full_sha256", "aplus_full_sha256",
    "parent_validator_sha256", "aplus_validator_sha256",
    "handoff_snapshot_id", "semantic_revision", "result", "delta_fingerprint",
    "previous_receipt_hash", "issued_at_basis", "receipt_sha256",
}
SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
RECEIPT_ID_RE = re.compile(r"CR-[0-9a-f]{20}")
CHAIN_ID_RE = re.compile(r"LC-[0-9a-f]{20}")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def full_input_hash(value: Any) -> str:
    """Hash the exact parsed JSON input without lifecycle normalization."""
    return canonical_sha256(value)


def coordination_chain_id(parent: Mapping[str, Any]) -> str:
    """Return the stable project/marketplace/locale coordination-chain ID."""
    project = parent.get("project") if isinstance(parent.get("project"), Mapping) else {}
    scope = parent.get("scope") if isinstance(parent.get("scope"), Mapping) else {}
    projection = {
        "project_id": str(project.get("project_id", "")),
        "marketplace": str(scope.get("marketplace", "")),
        "locale": str(scope.get("locale", "")),
    }
    return "LC-" + canonical_sha256(projection).removeprefix("sha256:")[:20]


def delta_fingerprint(aplus: Any) -> str:
    root = aplus if isinstance(aplus, dict) else {}
    component = root.get("component_result") if isinstance(root.get("component_result"), dict) else {}
    rows = [
        copy.deepcopy(row) for row in root.get("delta_evidence_requests", [])
        if isinstance(row, dict) and row.get("status") == "OPEN"
    ] if isinstance(root.get("delta_evidence_requests"), list) else []
    rows.sort(key=lambda row: str(row.get("id", "")))
    projection = {
        "component_status": str(component.get("status", "")),
        "gap_atom_ids": sorted({
            str(item) for item in component.get("gap_atom_ids", [])
            if isinstance(item, str) and item
        }) if isinstance(component.get("gap_atom_ids"), list) else [],
        "open_delta_request_ids": sorted({
            str(item) for item in component.get("open_delta_request_ids", [])
            if isinstance(item, str) and item
        }) if isinstance(component.get("open_delta_request_ids"), list) else [],
        "open_delta_requests": rows,
    }
    return canonical_sha256(projection)


def _identity_projection(receipt: Mapping[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(dict(receipt))
    normalized["receipt_id"] = ""
    normalized["receipt_sha256"] = ""
    return normalized


def canonical_receipt_id(receipt: Mapping[str, Any]) -> str:
    return "CR-" + canonical_sha256(_identity_projection(receipt)).removeprefix("sha256:")[:20]


def canonical_receipt_hash(receipt: Mapping[str, Any]) -> str:
    normalized = copy.deepcopy(dict(receipt))
    normalized["receipt_sha256"] = ""
    return canonical_sha256(normalized)


def build_coordination_receipt(
    *,
    parent: Mapping[str, Any],
    aplus: Mapping[str, Any],
    handoff_snapshot_id: str,
    semantic_revision: int,
    result: str,
    parent_validator_sha256: str,
    aplus_validator_sha256: str,
    previous_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    handoff = parent.get("enriched_content_handoff")
    issued_at_basis = str(handoff.get("created_at", "")) if isinstance(handoff, dict) else ""
    project = parent.get("project") if isinstance(parent.get("project"), Mapping) else {}
    receipt: dict[str, Any] = {
        "contract_version": RECEIPT_VERSION,
        "receipt_id": "",
        "project_id": str(project.get("project_id", "")),
        "chain_id": coordination_chain_id(parent),
        "parent_full_sha256": full_input_hash(parent),
        "aplus_full_sha256": full_input_hash(aplus),
        "parent_validator_sha256": parent_validator_sha256,
        "aplus_validator_sha256": aplus_validator_sha256,
        "handoff_snapshot_id": handoff_snapshot_id,
        "semantic_revision": semantic_revision,
        "result": result,
        "delta_fingerprint": delta_fingerprint(aplus),
        "previous_receipt_hash": (
            str(previous_receipt.get("receipt_sha256", ""))
            if isinstance(previous_receipt, Mapping) else ""
        ),
        "issued_at_basis": issued_at_basis,
        "receipt_sha256": "",
    }
    receipt["receipt_id"] = canonical_receipt_id(receipt)
    receipt["receipt_sha256"] = canonical_receipt_hash(receipt)
    return receipt


def validate_coordination_receipt(receipt: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(receipt, dict):
        return ["receipt must be an object"]
    if set(receipt) != RECEIPT_KEYS:
        issues.append(f"receipt keys must equal {sorted(RECEIPT_KEYS)!r}")
    if receipt.get("contract_version") != RECEIPT_VERSION:
        issues.append(f"contract_version must equal {RECEIPT_VERSION}")
    if not RECEIPT_ID_RE.fullmatch(str(receipt.get("receipt_id", ""))):
        issues.append("receipt_id must be a canonical CR identifier")
    if not isinstance(receipt.get("project_id"), str) or not receipt.get("project_id"):
        issues.append("project_id must be non-empty text")
    if not CHAIN_ID_RE.fullmatch(str(receipt.get("chain_id", ""))):
        issues.append("chain_id must be a canonical LC identifier")
    for key in (
        "parent_full_sha256", "aplus_full_sha256", "parent_validator_sha256",
        "aplus_validator_sha256", "delta_fingerprint", "receipt_sha256",
    ):
        if not SHA256_RE.fullmatch(str(receipt.get(key, ""))):
            issues.append(f"{key} must be canonical SHA-256")
    previous = str(receipt.get("previous_receipt_hash", ""))
    if previous and not SHA256_RE.fullmatch(previous):
        issues.append("previous_receipt_hash must be empty or canonical SHA-256")
    if receipt.get("result") not in RECEIPT_RESULTS:
        issues.append(f"result must use {sorted(RECEIPT_RESULTS)!r}")
    revision = receipt.get("semantic_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        issues.append("semantic_revision must be a positive integer")
    for key in ("handoff_snapshot_id", "issued_at_basis"):
        if not isinstance(receipt.get(key), str) or not receipt.get(key):
            issues.append(f"{key} must be non-empty text")
    if isinstance(receipt.get("receipt_id"), str) and canonical_receipt_id(receipt) != receipt.get("receipt_id"):
        issues.append("receipt_id does not match the content-addressed receipt")
    if isinstance(receipt.get("receipt_sha256"), str) and canonical_receipt_hash(receipt) != receipt.get("receipt_sha256"):
        issues.append("receipt_sha256 does not match the receipt payload")
    return issues
