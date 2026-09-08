#!/usr/bin/env python3
"""Deterministic Handoff v1.1 semantic-refreeze lineage primitives."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping


LIFECYCLE_FIELDS = {"status", "parent_bundle_sha256", "checksum"}
LINEAGE_RECORD_KEYS = {
    "snapshot_id",
    "handoff_checksum",
    "parent_bundle_sha256",
    "status",
    "successor_snapshot_id",
    "semantic_revision",
    "created_at",
    "superseded_at",
    "immutable_handoff",
    "record_checksum",
}
SNAPSHOT_RE = re.compile(r"^HO-[0-9a-f]{20}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ACTIVE_STATES = {"FROZEN", "RESULT_RECEIVED", "RECONCILIATION_REQUIRED", "SUPERSEDED"}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    try:
        encoded = payload.encode("utf-8")
    except UnicodeEncodeError:
        encoded = payload.encode("utf-8", errors="backslashreplace")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def immutable_handoff_projection(handoff: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in handoff.items()
        if key not in LIFECYCLE_FIELDS
    }


def _snapshot_projection(handoff: Mapping[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(dict(handoff))
    normalized["snapshot_id"] = ""
    normalized["parent_bundle_sha256"] = ""
    normalized["checksum"] = ""
    if normalized.get("status") in ACTIVE_STATES:
        normalized["status"] = "FROZEN"
    # The predecessor record points forward to this snapshot.  Blank only the
    # direct records' forward links/checksums to avoid a self-referential hash;
    # the immutable predecessor payload remains fully committed.
    records = normalized.get("lineage_registry")
    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict):
                record["successor_snapshot_id"] = ""
                record["record_checksum"] = ""
    return normalized


def canonical_handoff_snapshot_id(handoff: Mapping[str, Any]) -> str:
    digest = canonical_sha256(_snapshot_projection(handoff)).removeprefix("sha256:")
    return "HO-" + digest[:20]


def canonical_handoff_hash(handoff: Mapping[str, Any]) -> str:
    normalized = copy.deepcopy(dict(handoff))
    normalized["parent_bundle_sha256"] = ""
    normalized["checksum"] = ""
    if normalized.get("status") in ACTIVE_STATES:
        normalized["status"] = "FROZEN"
    return canonical_sha256(normalized)


def canonical_lineage_record_hash(record: Mapping[str, Any]) -> str:
    normalized = copy.deepcopy(dict(record))
    normalized["record_checksum"] = ""
    return canonical_sha256(normalized)


def build_lineage_record(
    previous_handoff: Mapping[str, Any],
    *,
    successor_snapshot_id: str,
    superseded_at: str,
) -> dict[str, Any]:
    record = {
        "snapshot_id": str(previous_handoff.get("snapshot_id", "")),
        "handoff_checksum": str(previous_handoff.get("checksum", "")),
        "parent_bundle_sha256": str(previous_handoff.get("parent_bundle_sha256", "")),
        "status": "SUPERSEDED",
        "successor_snapshot_id": successor_snapshot_id,
        "semantic_revision": previous_handoff.get("semantic_revision"),
        "created_at": str(previous_handoff.get("created_at", "")),
        "superseded_at": superseded_at,
        "immutable_handoff": immutable_handoff_projection(previous_handoff),
        "record_checksum": "",
    }
    record["record_checksum"] = canonical_lineage_record_hash(record)
    return record


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def validate_lineage_registry(
    handoff: Mapping[str, Any],
    handoff_keys: set[str],
) -> list[tuple[str, str]]:
    """Validate the immediate predecessor and its recursively committed chain."""
    issues: list[tuple[str, str]] = []
    revision = handoff.get("semantic_revision")
    registry = handoff.get("lineage_registry")
    if not isinstance(registry, list):
        return [("REGISTRY_TYPE", "lineage_registry must be an array")]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        return [("REVISION", "semantic_revision must be a non-negative integer")]
    predecessor = handoff.get("predecessor_snapshot_id")
    reason = handoff.get("refreeze_reason")
    if revision <= 1:
        if registry:
            issues.append(("INITIAL_REGISTRY", "revision 0/1 cannot carry predecessor records"))
        if predecessor or reason:
            issues.append(("INITIAL_LINEAGE", "revision 0/1 cannot claim a predecessor or refreeze reason"))
        return issues
    if len(registry) != 1:
        return [("REGISTRY_CARDINALITY", "semantic refreeze requires exactly one immediate predecessor record")]
    record = registry[0]
    if not isinstance(record, dict) or set(record) != LINEAGE_RECORD_KEYS:
        return [("RECORD_SHAPE", f"lineage record must contain exactly {sorted(LINEAGE_RECORD_KEYS)}")]
    snapshot_id = str(record.get("snapshot_id", ""))
    current_snapshot_id = str(handoff.get("snapshot_id", ""))
    if predecessor != snapshot_id or not SNAPSHOT_RE.fullmatch(snapshot_id):
        issues.append(("PREDECESSOR", "predecessor_snapshot_id must resolve to the recorded content-addressed snapshot"))
    if record.get("status") != "SUPERSEDED":
        issues.append(("SUPERSEDED", "predecessor record status must be SUPERSEDED"))
    if record.get("successor_snapshot_id") != current_snapshot_id:
        issues.append(("SUCCESSOR", "predecessor successor_snapshot_id must equal the current snapshot"))
    if record.get("semantic_revision") != revision - 1:
        issues.append(("REVISION_CHAIN", "predecessor semantic_revision must be exactly current revision minus one"))
    if not SHA256_RE.fullmatch(str(record.get("handoff_checksum", ""))):
        issues.append(("OLD_CHECKSUM", "predecessor handoff_checksum must be canonical SHA-256"))
    if not SHA256_RE.fullmatch(str(record.get("parent_bundle_sha256", ""))):
        issues.append(("OLD_PARENT_HASH", "predecessor parent_bundle_sha256 must be canonical SHA-256"))
    created_at = _parse_time(record.get("created_at"))
    superseded_at = _parse_time(record.get("superseded_at"))
    current_created_at = _parse_time(handoff.get("created_at"))
    if created_at is None or superseded_at is None or superseded_at < created_at:
        issues.append(("TIME", "predecessor timestamps must be valid and superseded_at must not predate created_at"))
    if current_created_at is None:
        issues.append(("TIME", "successor created_at must be a timezone-aware ISO timestamp"))
    if superseded_at is not None and current_created_at is not None and superseded_at > current_created_at:
        issues.append(("TIME", "predecessor cannot be superseded after the successor was created"))
    if record.get("record_checksum") != canonical_lineage_record_hash(record):
        issues.append(("RECORD_CHECKSUM", "predecessor lineage record checksum mismatch"))

    immutable = record.get("immutable_handoff")
    immutable_keys = handoff_keys - LIFECYCLE_FIELDS
    if not isinstance(immutable, dict) or set(immutable) != immutable_keys:
        issues.append(("IMMUTABLE_SHAPE", "predecessor immutable_handoff does not match the closed Handoff projection"))
        return issues
    old_handoff = copy.deepcopy(immutable)
    old_handoff.update({
        "status": "FROZEN",
        "parent_bundle_sha256": record.get("parent_bundle_sha256"),
        "checksum": record.get("handoff_checksum"),
    })
    if old_handoff.get("snapshot_id") != snapshot_id:
        issues.append(("OLD_SNAPSHOT", "predecessor immutable payload snapshot ID differs from its record"))
    if old_handoff.get("semantic_revision") != record.get("semantic_revision"):
        issues.append(("OLD_REVISION", "predecessor immutable payload revision differs from its record"))
    if old_handoff.get("created_at") != record.get("created_at"):
        issues.append(("OLD_TIME", "predecessor immutable payload created_at differs from its record"))
    if canonical_handoff_snapshot_id(old_handoff) != snapshot_id:
        issues.append(("OLD_SNAPSHOT_HASH", "predecessor snapshot ID does not match its immutable payload"))
    if canonical_handoff_hash(old_handoff) != record.get("handoff_checksum"):
        issues.append(("OLD_HANDOFF_HASH", "predecessor handoff checksum does not match its immutable payload"))
    nested = validate_lineage_registry(old_handoff, handoff_keys)
    issues.extend((f"PREVIOUS_{code}", message) for code, message in nested)
    if not isinstance(reason, str) or not reason.strip():
        issues.append(("REASON", "semantic refreeze requires a non-empty reason"))
    return issues
