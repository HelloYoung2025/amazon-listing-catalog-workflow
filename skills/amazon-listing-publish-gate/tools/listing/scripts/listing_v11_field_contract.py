#!/usr/bin/env python3
"""Closed P0 field/carrier contract for Listing Bundle v1.1.

The canonical backend key is the authority.  A caller cannot make ALT,
backend terms, or Community Q&A buyer-visible merely by relabelling its
surface or carrier.
"""

from __future__ import annotations

from typing import Any, Mapping


NATIVE_CORE = {
    ("core_copy", "seller_listing", "NATIVE_VISIBLE"),
    ("core_copy", "catalog_contribution", "NATIVE_VISIBLE"),
}
STRUCTURED_ATTRIBUTE = {
    ("catalog_attributes", "seller_listing", "STRUCTURED_VISIBLE"),
    ("catalog_attributes", "catalog_contribution", "STRUCTURED_VISIBLE"),
    ("product_details", "seller_listing", "STRUCTURED_VISIBLE"),
    ("product_details", "catalog_contribution", "STRUCTURED_VISIBLE"),
}
STRUCTURED_SIZE = STRUCTURED_ATTRIBUTE | {
    ("size_chart", "seller_listing", "STRUCTURED_VISIBLE"),
    ("size_chart", "catalog_contribution", "STRUCTURED_VISIBLE"),
    ("size_chart", "relationship", "STRUCTURED_VISIBLE"),
}


# Unknown PTD keys may still be represented as Field Resolutions, but they
# cannot become a P0 primary carrier until this closed contract is extended
# from current account/rule evidence.
P0_FIELD_CONTRACTS: dict[str, tuple[str, set[tuple[str, str, str]]]] = {
    "item_name": ("ITEM_NAME", NATIVE_CORE),
    "item_highlights": ("ITEM_HIGHLIGHTS", NATIVE_CORE),
    "bullet_point": ("BULLET", NATIVE_CORE),
    "product_description": ("DESCRIPTION", NATIVE_CORE),
    "size_chart": ("SIZE_CHART", STRUCTURED_SIZE),
    "size_name": ("SIZE", STRUCTURED_SIZE),
    "color_name": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "material": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "fabric_type": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "fit_type": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "brand": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "model_name": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "number_of_items": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "item_package_quantity": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "unit_count": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "special_feature": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
    "product_dimensions": ("ATTRIBUTE", STRUCTURED_ATTRIBUTE),
}

PROHIBITED_P0_ROLES = {
    "ALT_METADATA",
    "BACKEND_TERMS",
    "COMMUNITY_QA",
    "COMMUNITY_Q_AND_A",
}
PROHIBITED_P0_KEYS = {
    "image_alt_text",
    "alt_text",
    "generic_keyword",
    "generic_keywords",
    "search_terms",
    "customer_questions",
    "customer_questions_and_answers",
    "community_qa",
}
COMMUNITY_QA_ROLES = {"COMMUNITY_QA", "COMMUNITY_Q_AND_A"}
COMMUNITY_QA_KEYS = {
    "customer_questions",
    "customer_questions_and_answers",
    "community_qa",
}


def _role(value: Any) -> str:
    return str(value or "").strip().replace("-", "_").replace(" ", "_").upper()


def _key(value: Any) -> str:
    return str(value or "").strip().replace("-", "_").replace(" ", "_").lower()


def is_community_qa_field(field: Mapping[str, Any]) -> bool:
    return _role(field.get("semantic_role")) in COMMUNITY_QA_ROLES or _key(
        field.get("canonical_key")
    ) in COMMUNITY_QA_KEYS


def p0_field_contract_allows(field: Mapping[str, Any], carrier: Any) -> bool:
    """Return whether one resolved field is a legitimate P0 primary carrier."""
    canonical_key = _key(field.get("canonical_key"))
    semantic_role = _role(field.get("semantic_role"))
    carrier_name = str(carrier or "").strip()
    if semantic_role in PROHIBITED_P0_ROLES or canonical_key in PROHIBITED_P0_KEYS:
        return False
    contract = P0_FIELD_CONTRACTS.get(canonical_key)
    if contract is None:
        return False
    expected_role, allowed_bindings = contract
    binding = (
        str(field.get("surface", "")),
        str(field.get("data_plane", "")),
        carrier_name,
    )
    return semantic_role == expected_role and binding in allowed_bindings
