"""Cross-referencing module — resolving identifiers across data sources.

The core function: given an entity from one source, attempt to resolve
its identifiers in other namespace systems:
  AGROVOC URI ↔ EPPO Code ↔ USDA Symbol

EPPO Code is the preferred primary key for the phytosanitary domain.
AGROVOC URI is the universal fallback for all domains.
If neither is available, scientific name matching is used as last resort.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ikerketa.logging_setup import get_logger
from ikerketa.transform.normalizer import normalize_scientific_name

_log = get_logger(__name__)

# Minimum fuzzy match score to accept a scientific name match (0-100)
_FUZZY_THRESHOLD = 90


@dataclass
class IdentifierRecord:
    """A record in the cross-reference index."""

    scientific_name: str
    agrovoc_uri: str | None = None
    eppo_code: str | None = None
    usda_symbol: str | None = None
    extra_ids: dict[str, str] = field(default_factory=dict)


class CrossReferenceIndex:
    """In-memory index for resolving identifiers across namespaces.

    Build the index by calling add_record() with known mappings,
    then use resolve_*() methods to look up missing identifiers.
    """

    def __init__(self) -> None:
        self._by_eppo: dict[str, IdentifierRecord] = {}
        self._by_agrovoc: dict[str, IdentifierRecord] = {}
        self._by_usda: dict[str, IdentifierRecord] = {}
        self._by_name: dict[str, IdentifierRecord] = {}  # normalized scientific name

    def add_record(self, record: IdentifierRecord) -> None:
        """Add a record to the cross-reference index."""
        normalized_name = normalize_scientific_name(record.scientific_name)

        if record.eppo_code:
            existing = self._by_eppo.get(record.eppo_code)
            if existing:
                # Merge: enrich existing record with new identifiers
                self._merge(existing, record)
            else:
                self._by_eppo[record.eppo_code] = record

        if record.agrovoc_uri:
            self._by_agrovoc[record.agrovoc_uri] = record

        if record.usda_symbol:
            self._by_usda[record.usda_symbol] = record

        if normalized_name:
            self._by_name[normalized_name.lower()] = record

    def _merge(self, existing: IdentifierRecord, new: IdentifierRecord) -> None:
        """Merge identifiers from new record into existing."""
        if not existing.agrovoc_uri and new.agrovoc_uri:
            existing.agrovoc_uri = new.agrovoc_uri
        if not existing.eppo_code and new.eppo_code:
            existing.eppo_code = new.eppo_code
        if not existing.usda_symbol and new.usda_symbol:
            existing.usda_symbol = new.usda_symbol
        existing.extra_ids.update(new.extra_ids)

    def resolve_by_eppo(self, eppo_code: str) -> IdentifierRecord | None:
        """Look up a record by EPPO code."""
        return self._by_eppo.get(eppo_code.upper())

    def resolve_by_agrovoc(self, uri: str) -> IdentifierRecord | None:
        """Look up a record by AGROVOC URI."""
        return self._by_agrovoc.get(uri)

    def resolve_by_usda(self, symbol: str) -> IdentifierRecord | None:
        """Look up a record by USDA PLANTS symbol."""
        return self._by_usda.get(symbol.upper())

    def resolve_by_name(self, scientific_name: str) -> IdentifierRecord | None:
        """Look up a record by scientific name (exact match on normalized form)."""
        normalized = normalize_scientific_name(scientific_name).lower()
        return self._by_name.get(normalized)

    def resolve_by_name_fuzzy(self, scientific_name: str) -> IdentifierRecord | None:
        """Look up a record by scientific name using fuzzy matching.

        Uses Jaro-Winkler similarity. Only returns a match if
        score >= _FUZZY_THRESHOLD.
        """
        normalized = normalize_scientific_name(scientific_name).lower()
        if not normalized:
            return None

        best_score = 0.0
        best_match: IdentifierRecord | None = None

        for name, record in self._by_name.items():
            score = fuzz.WRatio(normalized, name)
            if score > best_score:
                best_score = score
                best_match = record

        if best_score >= _FUZZY_THRESHOLD and best_match is not None:
            _log.debug(
                "fuzzy_match_found",
                query=scientific_name,
                matched=best_match.scientific_name,
                score=best_score,
            )
            return best_match

        return None

    def resolve(
        self,
        *,
        eppo_code: str | None = None,
        agrovoc_uri: str | None = None,
        usda_symbol: str | None = None,
        scientific_name: str | None = None,
    ) -> IdentifierRecord | None:
        """Attempt to resolve identifiers using all available keys.

        Priority order:
        1. EPPO Code (phytosanitary domain PK)
        2. AGROVOC URI (universal PK)
        3. USDA Symbol (enrichment)
        4. Scientific name (exact)
        5. Scientific name (fuzzy)

        Returns the first match found.
        """
        if eppo_code:
            result = self.resolve_by_eppo(eppo_code)
            if result:
                return result

        if agrovoc_uri:
            result = self.resolve_by_agrovoc(agrovoc_uri)
            if result:
                return result

        if usda_symbol:
            result = self.resolve_by_usda(usda_symbol)
            if result:
                return result

        if scientific_name:
            result = self.resolve_by_name(scientific_name)
            if result:
                return result
            result = self.resolve_by_name_fuzzy(scientific_name)
            if result:
                return result

        return None

    @property
    def size(self) -> int:
        """Total unique records in the index (by EPPO code count + unkeyed)."""
        all_records = set()
        for d in (self._by_eppo, self._by_agrovoc, self._by_usda, self._by_name):
            all_records.update(id(v) for v in d.values())
        return len(all_records)
