#!/usr/bin/env python3
"""Stable CLI and public API for the versioned Amazon A+ validator."""

from __future__ import annotations

from aplus_contract_orchestrator import (
    canonical_handoff_hash,
    canonical_object_hash,
    main,
    validate_bundle,
)

__all__ = [
    "canonical_handoff_hash",
    "canonical_object_hash",
    "main",
    "validate_bundle",
]


if __name__ == "__main__":
    raise SystemExit(main())
