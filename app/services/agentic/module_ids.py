"""
Canonical module ID resolution via app.module_id_aliases.

Legacy engagement IDs (e.g. breathing_box) map to catalog IDs (breathing).
"""

from __future__ import annotations

import logging
from typing import Optional

from supabase import Client

logger = logging.getLogger("zenu.module_ids")

# Fallback if DB aliases cannot be loaded (matches known migrated rows).
_STATIC_ALIASES: dict[str, str] = {
    "breathing_box": "breathing",
    "meditation_jpmr": "mindfulness",
    "arts_mandala": "doodle_dreams",
    "bubble_simulation": "bubble_canvas",
    "arts_scribble": "scribble_pad",
}

_cache: Optional[dict[str, str]] = None


def load_alias_map(sb: Client) -> dict[str, str]:
    """Load alias → canonical_id from app.module_id_aliases (cached process-wide)."""
    global _cache
    if _cache is not None:
        return _cache
    mapping = dict(_STATIC_ALIASES)
    try:
        res = sb.table("module_id_aliases").select("legacy_module_id,canonical_module_id").execute()
        for row in res.data or []:
            alias = row.get("legacy_module_id")
            canonical = row.get("canonical_module_id")
            if alias and canonical:
                mapping[str(alias)] = str(canonical)
    except Exception as e:
        logger.warning("Failed to load module_id_aliases; using static map: %s", e)
    _cache = mapping
    return mapping


def resolve_canonical_module_id(sb: Client, module_id: str) -> str:
    """Return canonical module_id; passthrough if already canonical / unknown."""
    if not module_id:
        return module_id
    aliases = load_alias_map(sb)
    return aliases.get(module_id, module_id)


def clear_alias_cache() -> None:
    global _cache
    _cache = None
