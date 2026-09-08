#!/usr/bin/env python3
"""Append-only local receipt ledger for Listing/A+ coordination.

The ledger prevents ordinary stale-head replay, accidental deletion, forks and
rollback inside the controlled local workflow.  It is not an external
signature, trusted storage, proof of operator identity, or Amazon evidence.  A
party able to replace the entire ledger, Skill, or validator can replace this
local evidence and therefore still needs an external signature or trusted
store for an adversarial security boundary.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from listing_coordination_receipt import validate_coordination_receipt


LEDGER_VERSION = "listing-coordination-ledger/1.0"


class LedgerError(RuntimeError):
    """A structured local-ledger integrity or I/O failure."""


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _transition_issues(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if previous is None:
        if current.get("previous_receipt_hash"):
            issues.append("[PKG-RECEIPT-016] first ledger receipt must start a new chain")
        if current.get("result") not in {"AWAITING_RESULT_ACK", "DELTA_REQUIRED"}:
            issues.append("[PKG-RECEIPT-016] a ledger chain cannot start at terminal PASS")
        return issues

    if current.get("project_id") != previous.get("project_id") or current.get("chain_id") != previous.get("chain_id"):
        issues.append("[PKG-RECEIPT-016] project/chain fork or rollback detected")
    if current.get("previous_receipt_hash") != previous.get("receipt_sha256"):
        issues.append("[PKG-RECEIPT-016] receipt does not consume the current ledger head")

    before = str(previous.get("result", ""))
    after = str(current.get("result", ""))
    old_revision = previous.get("semantic_revision")
    new_revision = current.get("semantic_revision")
    old_snapshot = previous.get("handoff_snapshot_id")
    new_snapshot = current.get("handoff_snapshot_id")
    if before == "AWAITING_RESULT_ACK" and after in {"PASS", "DELTA_REQUIRED"}:
        if old_revision != new_revision or old_snapshot != new_snapshot:
            issues.append("[PKG-RECEIPT-016] AWAIT must be consumed on its exact snapshot/revision")
        if after == "PASS" and previous.get("aplus_full_sha256") != current.get("aplus_full_sha256"):
            issues.append("[PKG-RECEIPT-016] terminal PASS changed the A+ input after AWAIT")
    elif before == "PASS" and after == "DELTA_REQUIRED":
        if old_revision != new_revision or old_snapshot != new_snapshot:
            issues.append("[PKG-RECEIPT-016] reopening PASS requires a DELTA on the same snapshot/revision")
    elif before == "DELTA_REQUIRED" and after == "AWAITING_RESULT_ACK":
        if not isinstance(old_revision, int) or new_revision != old_revision + 1 or old_snapshot == new_snapshot:
            issues.append("[PKG-RECEIPT-017] DELTA must advance to revision + 1 and a new FROZEN snapshot")
    else:
        issues.append(f"[PKG-RECEIPT-016] illegal or repeated ledger transition {before!r} -> {after!r}")
    return issues


def validate_receipt_chain(receipts: Any) -> list[str]:
    """Validate the complete ordered chain; never accept only a claimed head."""
    if not isinstance(receipts, list):
        return ["[PKG-LEDGER-001] ledger receipts must be an array"]
    issues: list[str] = []
    previous: Mapping[str, Any] | None = None
    seen_hashes: set[str] = set()
    for index, receipt in enumerate(receipts, start=1):
        for issue in validate_coordination_receipt(receipt):
            issues.append(f"[PKG-LEDGER-001] line {index}: {issue}")
        if not isinstance(receipt, dict):
            previous = None
            continue
        receipt_hash = str(receipt.get("receipt_sha256", ""))
        if receipt_hash in seen_hashes:
            issues.append(f"[PKG-RECEIPT-016] line {index}: duplicate receipt or rollback detected")
        seen_hashes.add(receipt_hash)
        issues.extend(f"line {index}: {issue}" for issue in _transition_issues(previous, receipt))
        previous = receipt
    return issues


def parse_ledger_bytes(payload: bytes) -> dict[str, Any]:
    if not payload:
        receipts: list[dict[str, Any]] = []
    else:
        if not payload.endswith(b"\n"):
            raise LedgerError("[PKG-LEDGER-001] ledger has a partial or crash-truncated final line")
        receipts = []
        for index, raw in enumerate(payload.splitlines(), start=1):
            if not raw:
                raise LedgerError(f"[PKG-LEDGER-001] blank ledger line {index} is invalid")
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise LedgerError(f"[PKG-LEDGER-001] invalid ledger line {index}: {exc}") from exc
            receipts.append(value)
    issues = validate_receipt_chain(receipts)
    if issues:
        raise LedgerError("; ".join(issues))
    return {
        "contract_version": LEDGER_VERSION,
        "receipts": copy.deepcopy(receipts),
        "entry_count": len(receipts),
        "head": copy.deepcopy(receipts[-1]) if receipts else None,
        "ledger_sha256": _sha256_bytes(payload),
    }


def load_receipt_ledger(path: Path, *, allow_missing: bool) -> dict[str, Any]:
    if path.is_symlink():
        raise LedgerError("[PKG-LEDGER-001] receipt ledger cannot be a symlink")
    if not path.exists():
        if allow_missing:
            return parse_ledger_bytes(b"")
        raise LedgerError("[PKG-LEDGER-001] receipt ledger does not exist")
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode):
        raise LedgerError("[PKG-LEDGER-001] receipt ledger must be a regular file")
    try:
        return parse_ledger_bytes(path.read_bytes())
    except OSError as exc:
        raise LedgerError(f"[PKG-LEDGER-001] cannot read receipt ledger: {exc}") from exc


def append_receipt(path: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Lock, revalidate the full chain, append one canonical line and fsync."""
    if path.is_symlink():
        raise LedgerError("[PKG-LEDGER-001] receipt ledger cannot be a symlink")
    if not path.parent.exists() or not path.parent.is_dir():
        raise LedgerError("[PKG-LEDGER-001] receipt ledger parent directory does not exist")
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        mode = os.fstat(descriptor).st_mode
        if not stat.S_ISREG(mode):
            raise LedgerError("[PKG-LEDGER-001] receipt ledger must be a regular file")
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        before = parse_ledger_bytes(b"".join(chunks))
        combined = before["receipts"] + [copy.deepcopy(dict(receipt))]
        issues = validate_receipt_chain(combined)
        if issues:
            raise LedgerError("; ".join(issues))
        encoded = (
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise OSError("short append write")
            offset += written
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return parse_ledger_bytes(b"".join(chunks))
    except LedgerError:
        raise
    except OSError as exc:
        raise LedgerError(f"[PKG-LEDGER-001] receipt ledger append/fsync failed: {exc}") from exc
    finally:
        if descriptor is not None:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
