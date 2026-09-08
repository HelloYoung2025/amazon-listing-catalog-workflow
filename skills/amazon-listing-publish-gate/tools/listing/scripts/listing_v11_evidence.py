#!/usr/bin/env python3
"""Pure evidence/scope predicates for Listing Bundle v1.1.

No function performs I/O or mutates its inputs.  The validator owns error
formatting; this module owns the reusable decision predicates.
"""

from __future__ import annotations

from typing import Any, Mapping


SCOPE_KEYS = ("parent_asins", "child_asins", "packs", "colors", "sizes")
SELLER_CENTRAL_TYPES = {"seller_central_screenshot", "seller_central_export"}
STRONG_PRODUCT_TYPES = {
    "physical_sample", "physical_measurement", "packaging_label",
    "manufacturer_specification", "authorized_product_record", "lab_test",
    "certification",
}


def scope_values(scope: Any, key: str) -> set[str]:
    if not isinstance(scope, Mapping):
        return set()
    value = scope.get(key, [])
    return {item for item in value if isinstance(item, str) and item} if isinstance(value, list) else set()


def scope_covers(outer: Any, inner: Any) -> bool:
    """Return true only when every asserted inner dimension is in outer.

    An empty inner dimension is non-asserting.  An empty outer dimension cannot
    prove a non-empty inner dimension.
    """
    return all(
        not scope_values(inner, key)
        or scope_values(inner, key).issubset(scope_values(outer, key))
        for key in SCOPE_KEYS
    )


def variant_scope(variant: Mapping[str, Any]) -> dict[str, list[str]]:
    mapping = {
        "parent_asins": variant.get("parent_asin"),
        "child_asins": variant.get("child_asin"),
        "packs": variant.get("pack"),
        "colors": variant.get("color"),
        "sizes": variant.get("size"),
    }
    return {
        key: [str(value)] if isinstance(value, str) and value else []
        for key, value in mapping.items()
    }


def source_context_matches(source: Mapping[str, Any], root_scope: Mapping[str, Any]) -> bool:
    return (
        source.get("status") == "USABLE"
        and source.get("seller_scope") == root_scope.get("seller_scope")
        and source.get("marketplace") == root_scope.get("marketplace")
        and source.get("locale") == root_scope.get("locale")
    )


def source_covers(
    source: Mapping[str, Any],
    root_scope: Mapping[str, Any],
    application_scope: Mapping[str, Any],
) -> bool:
    return (
        source_context_matches(source, root_scope)
        and scope_covers(source.get("application_scope"), application_scope)
    )


def source_can_prove_product(
    source: Mapping[str, Any],
    root_scope: Mapping[str, Any],
    application_scope: Mapping[str, Any],
) -> bool:
    return (
        source.get("type") in STRONG_PRODUCT_TYPES
        and source.get("evidence_level") in {"E3", "E4"}
        and source_covers(source, root_scope, application_scope)
    )


def source_can_prove_account_field(
    source: Mapping[str, Any],
    root_scope: Mapping[str, Any],
    application_scope: Mapping[str, Any],
    *,
    require_complete_capture: bool = False,
) -> bool:
    if not (
        source.get("type") in SELLER_CENTRAL_TYPES
        and source.get("evidence_level") in {"E3", "E4"}
        and source_covers(source, root_scope, application_scope)
    ):
        return False
    metadata = source.get("capture_metadata")
    if not isinstance(metadata, Mapping):
        return False
    return not require_complete_capture or metadata.get("coverage") == "COMPLETE"


def proving_sources_cover(
    source_ids: Any,
    sources: Mapping[str, Mapping[str, Any]],
    root_scope: Mapping[str, Any],
    application_scope: Mapping[str, Any],
) -> bool:
    return (
        isinstance(source_ids, list)
        and bool(source_ids)
        and all(
            source_can_prove_product(sources.get(str(source_id), {}), root_scope, application_scope)
            for source_id in source_ids
        )
    )
