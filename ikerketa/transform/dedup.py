"""Deduplication module — exact hash and fuzzy name deduplication."""

from __future__ import annotations

from rapidfuzz import fuzz

from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity
from ikerketa.transform.normalizer import normalize_scientific_name

_log = get_logger(__name__)

_FUZZY_DEDUP_THRESHOLD = 95  # Very high threshold for dedup (conservative)


def dedup_by_hash(entities: list[BaseEntity]) -> list[BaseEntity]:
    """Remove exact duplicates based on data_hash.

    Keeps the first occurrence when duplicates are found.

    Args:
        entities: List of entities to deduplicate.

    Returns:
        Deduplicated list.
    """
    seen_hashes: set[str] = set()
    unique: list[BaseEntity] = []
    dup_count = 0

    for entity in entities:
        h = entity.data_hash
        if h and h in seen_hashes:
            dup_count += 1
            continue
        if h:
            seen_hashes.add(h)
        unique.append(entity)

    if dup_count > 0:
        _log.info("hash_dedup_complete", duplicates_removed=dup_count, remaining=len(unique))

    return unique


def dedup_by_key(entities: list[BaseEntity]) -> list[BaseEntity]:
    """Remove duplicates based on composite key (eppo_code, agrovoc_uri).

    Priority: EPPO code > AGROVOC URI > USDA symbol.
    Keeps the first occurrence per key.

    Args:
        entities: List of entities to deduplicate.

    Returns:
        Deduplicated list.
    """
    seen_keys: set[str] = set()
    unique: list[BaseEntity] = []
    dup_count = 0

    for entity in entities:
        key = entity.eppo_code or entity.agrovoc_uri or entity.usda_symbol
        if not key:
            unique.append(entity)  # Can't dedup without a key
            continue
        if key in seen_keys:
            dup_count += 1
            continue
        seen_keys.add(key)
        unique.append(entity)

    if dup_count > 0:
        _log.info("key_dedup_complete", duplicates_removed=dup_count, remaining=len(unique))

    return unique


def dedup_by_name_fuzzy(
    entities: list[BaseEntity],
    threshold: float = _FUZZY_DEDUP_THRESHOLD,
) -> list[BaseEntity]:
    """Remove near-duplicate entities based on fuzzy scientific name matching.

    Only applies to entities that have a scientific_name attribute.
    Uses a conservative threshold to avoid false positive deduplication.

    Args:
        entities: List of entities to deduplicate.
        threshold: Minimum similarity score (0-100) to consider a duplicate.

    Returns:
        Deduplicated list.
    """
    unique: list[BaseEntity] = []
    unique_names: list[str] = []
    dup_count = 0

    for entity in entities:
        sci_name = getattr(entity, "scientific_name", None)
        if not sci_name:
            unique.append(entity)
            continue

        normalized = normalize_scientific_name(sci_name).lower()
        if not normalized:
            unique.append(entity)
            continue

        is_dup = False
        for existing_name in unique_names:
            if fuzz.WRatio(normalized, existing_name) >= threshold:
                is_dup = True
                dup_count += 1
                _log.debug(
                    "fuzzy_dedup_match",
                    new=sci_name,
                    existing=existing_name,
                )
                break

        if not is_dup:
            unique.append(entity)
            unique_names.append(normalized)

    if dup_count > 0:
        _log.info("fuzzy_dedup_complete", duplicates_removed=dup_count, remaining=len(unique))

    return unique
