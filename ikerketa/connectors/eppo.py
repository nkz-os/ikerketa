"""EPPO connector — REST API v2 for phytosanitary data ingestion.

Uses the EPPO Global Database REST API v2 (api.eppo.int/gd/v2)
with X-Api-Key authentication.

Rate limit: 60 requests per 10-second sliding window.
Strategy:
  - /taxons/list for paginated bulk discovery (EPPO codes + metadata)
  - /taxons/taxon/{EPPOCODE}/overview for detailed taxon info
  - /taxons/taxon/{EPPOCODE}/names for multilingual names
  - /taxons/taxon/{EPPOCODE}/taxonomy for classification hierarchy
  - /taxons/taxon/{EPPOCODE}/hosts for host-plant associations
  - /taxons/taxon/{EPPOCODE}/pests for pest associations
  - /taxons/taxon/{EPPOCODE}/categorization for quarantine status
  - /taxons/taxon/{EPPOCODE}/distribution for geographical distribution
  - /taxons/taxon/{EPPOCODE}/bca for biological control agents
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from ikerketa.config import settings
from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import (
    BaseEntity,
    BaseRelationship,
    DataSource,
    RawRecord,
)
from ikerketa.models.pest import Pest, PestType, QuarantineStatus
from ikerketa.models.relationship import HostAssociation
from ikerketa.models.taxonomy import Taxon, TaxonSynonym
from ikerketa.security import mask_secret, validate_api_token

_log = get_logger(__name__)

# ── EPPO v2 API constants ───────────────────────────────────────────
EPPO_BASE_URL = "https://api.eppo.int/gd/v2"

# Rate limit: 60 requests per 10-second sliding window
# We enforce a conservative 6 req/s to stay well within limits
REQUEST_INTERVAL = 0.18  # ~5.5 requests per second

# Pagination defaults
DEFAULT_PAGE_SIZE = 100  # API max is 1000, 100 is safe default

# EPPO datatype codes → our domain types
DATATYPE_MAP = {
    "PFL": "plant",        # Plant / Flora
    "IN": "insect",        # Insect
    "BA": "bacterium",     # Bacterium
    "VI": "virus",         # Virus
    "FU": "fungus",        # Fungus
    "NE": "nematode",      # Nematode
    "AC": "mite",          # Acari (mite)
    "WE": "weed",          # Weed
    "MO": "mollusk",       # Mollusk
    "PP": "phytoplasma",   # Phytoplasma
    "VD": "viroid",        # Viroid
    "PR": "protozoa",      # Protozoa
    "OO": "oomycete",      # Oomycete
}

# Map EPPO datatypes to our PestType enum
PEST_TYPE_MAP = {
    "IN": PestType.INSECT,
    "BA": PestType.BACTERIUM,
    "VI": PestType.VIRUS,
    "FU": PestType.FUNGUS,
    "NE": PestType.NEMATODE,
    "AC": PestType.MITE,
    "WE": PestType.WEED,
    "MO": PestType.OTHER,
    "PP": PestType.BACTERIUM,  # Phytoplasma → closest
    "VD": PestType.VIRUS,      # Viroid → closest
    "PR": PestType.OTHER,
    "OO": PestType.FUNGUS,     # Oomycete → closest
}


class Connector(AbstractConnector):
    """EPPO Global Database v2 REST API connector.

    Fetches taxon data with rate-limited pagination.
    Enriches each taxon with names, taxonomy, hosts/pests,
    categorization, and distribution.
    """

    def __init__(self) -> None:
        super().__init__()
        self._api_key = settings.eppo_api_token
        validate_api_token(self._api_key, "EPPO_API_TOKEN")
        self._request_count = 0
        self._window_start = time.monotonic()

    @property
    def source_name(self) -> DataSource:
        return DataSource.EPPO

    def _rate_limit(self) -> None:
        """Enforce rate limit: 60 requests per 10-second sliding window."""
        now = time.monotonic()
        elapsed = now - self._window_start

        if elapsed >= 10.0:
            # Reset window
            self._request_count = 0
            self._window_start = now
        elif self._request_count >= 55:  # Conservative: 55/60 threshold
            wait = 10.0 - elapsed
            self._log.debug("rate_limit_wait", seconds=f"{wait:.2f}")
            time.sleep(wait)
            self._request_count = 0
            self._window_start = time.monotonic()

        self._request_count += 1
        time.sleep(REQUEST_INTERVAL)

    def _api_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a rate-limited GET request to the EPPO v2 API.

        Args:
            path: API path (e.g., '/taxons/list')
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        self._rate_limit()
        url = f"{EPPO_BASE_URL}{path}"
        response = self._http_get(
            url,
            params=params,
            headers={
                "X-Api-Key": self._api_key,
                "Accept": "application/json",
            },
        )
        return response.json()

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Fetch taxon records from EPPO v2 API.

        Strategy:
        1. Use /taxons/list to paginate through all EPPO codes
        2. For each code, enrich with detail endpoints (names, taxonomy, etc.)

        Args:
            limit: Maximum taxons to fetch. None = 100 default.
            **params:
                enrich: bool = True — whether to fetch detail endpoints per taxon
                datatypes: list[str] — filter by EPPO datatype codes (PFL, IN, etc.)
                updated_from: str — ISO date, only fetch codes updated since this date

        Returns:
            List of RawRecord with enriched taxon data.
        """
        effective_limit = limit or 100
        enrich = params.get("enrich", True)
        datatypes_filter = params.get("datatypes", None)
        updated_from = params.get("updated_from", None)

        self._log.info(
            "eppo_fetch_start",
            limit=effective_limit,
            enrich=enrich,
            datatypes_filter=datatypes_filter,
        )

        # Step 1: Paginate through /taxons/list
        all_records: list[RawRecord] = []
        offset = 0
        page_size = min(DEFAULT_PAGE_SIZE, effective_limit)

        while len(all_records) < effective_limit:
            list_params: dict[str, Any] = {
                "limit": page_size,
                "offset": offset,
                "orderBy": "eppocode",
            }
            if updated_from:
                list_params["updatedFromDate"] = updated_from

            try:
                data = self._api_get("/taxons/list", params=list_params)
            except ConnectorError as exc:
                self._log.error("taxons_list_failed", offset=offset, error=str(exc))
                break

            pagination = data.get("pagination", {})
            items = data.get("data", [])

            if not items:
                break

            for item in items:
                if len(all_records) >= effective_limit:
                    break

                eppo_code = item.get("eppocode", "")
                datatype = item.get("datatype", "")

                # Filter by datatype if specified
                if datatypes_filter and datatype not in datatypes_filter:
                    continue

                # Skip inactive codes
                if not item.get("is_active", True):
                    continue

                record_data: dict[str, Any] = {
                    "eppocode": eppo_code,
                    "datatype": datatype,
                    "is_active": item.get("is_active", True),
                    "datecreate": item.get("datecreate"),
                    "dateupdate": item.get("dateupdate"),
                    "replacedby": item.get("replacedby"),
                }

                # Step 2: Enrich with detail endpoints
                if enrich and eppo_code:
                    record_data.update(self._enrich_taxon(eppo_code))

                all_records.append(RawRecord(
                    source_name=DataSource.EPPO,
                    record_id=eppo_code,
                    data=record_data,
                ))

            self._log.debug(
                "page_fetched",
                offset=offset,
                items=len(items),
                total=len(all_records),
                api_total=pagination.get("total", "?"),
            )

            offset += page_size

            # Check if we've exhausted the API
            total_available = pagination.get("total", float("inf"))
            if offset >= total_available:
                break

        self._log.info("eppo_fetch_complete", total_records=len(all_records))
        return all_records

    def _enrich_taxon(self, eppo_code: str) -> dict[str, Any]:
        """Fetch detail endpoints for a single EPPO code.

        Fetches: overview, names, taxonomy, hosts, pests, categorization, distribution, bca.

        Args:
            eppo_code: EPPO code to enrich.

        Returns:
            Dict with enrichment data.
        """
        enrichment: dict[str, Any] = {}
        base_path = f"/taxons/taxon/{eppo_code}"

        # Overview
        try:
            enrichment["overview"] = self._api_get(f"{base_path}/overview")
        except ConnectorError as exc:
            self._log.warning("enrich_overview_failed", eppo_code=eppo_code, error=str(exc))

        # Names (multilingual)
        try:
            enrichment["names"] = self._api_get(f"{base_path}/names")
        except ConnectorError as exc:
            self._log.warning("enrich_names_failed", eppo_code=eppo_code, error=str(exc))

        # Taxonomy hierarchy
        try:
            enrichment["taxonomy"] = self._api_get(f"{base_path}/taxonomy")
        except ConnectorError as exc:
            self._log.warning("enrich_taxonomy_failed", eppo_code=eppo_code, error=str(exc))

        # Hosts (for pest-type organisms)
        try:
            enrichment["hosts"] = self._api_get(f"{base_path}/hosts")
        except ConnectorError as exc:
            self._log.debug("enrich_hosts_failed", eppo_code=eppo_code, error=str(exc))

        # Pests (for plant-type organisms)
        try:
            enrichment["pests"] = self._api_get(f"{base_path}/pests")
        except ConnectorError as exc:
            self._log.debug("enrich_pests_failed", eppo_code=eppo_code, error=str(exc))

        # Categorization (quarantine lists)
        try:
            enrichment["categorization"] = self._api_get(f"{base_path}/categorization")
        except ConnectorError as exc:
            self._log.debug("enrich_categorization_failed", eppo_code=eppo_code, error=str(exc))

        # Distribution
        try:
            enrichment["distribution"] = self._api_get(f"{base_path}/distribution")
        except ConnectorError as exc:
            self._log.debug("enrich_distribution_failed", eppo_code=eppo_code, error=str(exc))

        # Biological Control Agents
        try:
            enrichment["bca"] = self._api_get(f"{base_path}/bca")
        except ConnectorError as exc:
            self._log.debug("enrich_bca_failed", eppo_code=eppo_code, error=str(exc))

        return enrichment

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform EPPO raw records into domain entities.

        Plants → Taxon entities
        Pests/Pathogens → Pest entities
        Host associations → HostAssociation relationships
        """
        entities: list[BaseEntity] = []
        relationships: list[BaseRelationship] = []

        for record in raw_records:
            data = record.data
            eppo_code = data.get("eppocode", "")
            datatype = data.get("datatype", "")

            # Extract common fields
            overview = data.get("overview", {})
            prefname = overview.get("prefname", "")
            names_data = data.get("names", {})
            taxonomy_data = data.get("taxonomy", {})

            # Parse names into multilingual dict
            common_names = self._parse_names(names_data)
            synonyms = self._parse_synonyms(names_data)

            # Parse taxonomy
            family, genus, kingdom = self._parse_taxonomy(taxonomy_data)

            if datatype == "PFL":
                # Plant — create Taxon entity
                entity = Taxon(
                    source_name=DataSource.EPPO,
                    source_record_id=eppo_code,
                    eppo_code=eppo_code,
                    scientific_name=prefname,
                    common_names=common_names,
                    family=family,
                    genus=genus,
                    kingdom=kingdom,
                    synonyms=synonyms,
                    raw_record=data,
                )
                entities.append(entity)

                # Create pest relationships for this plant
                pests_data = data.get("pests", [])
                if isinstance(pests_data, list):
                    for pest_entry in pests_data:
                        pest_eppo = pest_entry.get("eppocode", "")
                        if pest_eppo:
                            rel = HostAssociation(
                                source_name=DataSource.EPPO,
                                source_eppo_code=pest_eppo,  # pest
                                target_eppo_code=eppo_code,   # host plant
                                host_class=pest_entry.get("class_label", ""),
                                citation=pest_entry.get("bibref", ""),
                                raw_record=pest_entry,
                            )
                            relationships.append(rel)

            elif datatype in PEST_TYPE_MAP:
                # Pest/Pathogen — create Pest entity
                pest_type = PEST_TYPE_MAP.get(datatype, PestType.OTHER)

                # Parse quarantine status from categorization
                quarantine_status = self._parse_quarantine_status(
                    data.get("categorization", [])
                )

                # Parse distribution
                distribution = self._parse_distribution(data.get("distribution", []))

                # Parse host EPPO codes
                hosts_data = data.get("hosts", [])
                host_eppo_codes: list[str] = []
                if isinstance(hosts_data, list):
                    host_eppo_codes = [
                        h.get("eppocode", "") for h in hosts_data
                        if h.get("eppocode")
                    ]

                entity = Pest(
                    source_name=DataSource.EPPO,
                    source_record_id=eppo_code,
                    eppo_code=eppo_code,
                    scientific_name=prefname,
                    common_names=common_names,
                    family=family,
                    genus=genus,
                    kingdom=kingdom,
                    pest_type=pest_type,
                    quarantine_status=quarantine_status,
                    host_eppo_codes=host_eppo_codes,
                    distribution=distribution,
                    synonyms=synonyms,
                    raw_record=data,
                )
                entities.append(entity)

                # Create host association relationships
                for host in hosts_data if isinstance(hosts_data, list) else []:
                    host_eppo = host.get("eppocode", "")
                    if host_eppo:
                        rel = HostAssociation(
                            source_name=DataSource.EPPO,
                            source_eppo_code=eppo_code,   # pest
                            target_eppo_code=host_eppo,    # host
                            host_class=host.get("class_label", ""),
                            citation=host.get("bibref", ""),
                            raw_record=host,
                        )
                        relationships.append(rel)

            else:
                # Unknown datatype — generic Taxon
                entity = Taxon(
                    source_name=DataSource.EPPO,
                    source_record_id=eppo_code,
                    eppo_code=eppo_code,
                    scientific_name=prefname,
                    common_names=common_names,
                    family=family,
                    genus=genus,
                    kingdom=kingdom,
                    synonyms=synonyms,
                    raw_record=data,
                )
                entities.append(entity)

        self._log.info(
            "eppo_transform_complete",
            entities=len(entities),
            relationships=len(relationships),
        )
        return entities, relationships

    @staticmethod
    def _parse_names(names_data: Any) -> dict[str, list[str]]:
        """Parse EPPO names response into multilingual common names dict."""
        common_names: dict[str, list[str]] = {}
        if not isinstance(names_data, list):
            return common_names

        for entry in names_data:
            lang = entry.get("lang", "")
            name = entry.get("name", "")
            name_type = entry.get("nametype", "")

            # Only extract common names (not scientific synonyms)
            if name_type in ("common", "other") and lang and name:
                lang_lower = lang.lower()[:2]
                if lang_lower not in common_names:
                    common_names[lang_lower] = []
                if name not in common_names[lang_lower]:
                    common_names[lang_lower].append(name)

        return common_names

    @staticmethod
    def _parse_synonyms(names_data: Any) -> list[TaxonSynonym]:
        """Extract scientific synonyms from EPPO names response."""
        synonyms: list[TaxonSynonym] = []
        if not isinstance(names_data, list):
            return synonyms

        for entry in names_data:
            name_type = entry.get("nametype", "")
            name = entry.get("name", "")

            if name_type == "synonym" and name:
                synonyms.append(TaxonSynonym(
                    synonym_name=name,
                    synonym_type="scientific",
                ))

        return synonyms

    @staticmethod
    def _parse_taxonomy(taxonomy_data: Any) -> tuple[str, str, str]:
        """Extract family, genus, kingdom from EPPO taxonomy response.

        EPPO v2 taxonomy response format:
        [{"eppocode": "1PLAK", "prefname": "Plantae", "level": 1, "type": "Kingdom"}, ...]

        Returns:
            Tuple of (family, genus, kingdom).
        """
        family = ""
        genus = ""
        kingdom = ""

        if not isinstance(taxonomy_data, list):
            return family, genus, kingdom

        for entry in taxonomy_data:
            if not isinstance(entry, dict):
                continue
            taxon_type = str(entry.get("type", "")).lower()
            prefname = entry.get("prefname", "")

            if taxon_type == "family":
                family = prefname
            elif taxon_type == "genus":
                genus = prefname
            elif taxon_type == "kingdom":
                kingdom = prefname

        return family, genus, kingdom

    @staticmethod
    def _parse_quarantine_status(categorization: Any) -> QuarantineStatus | None:
        """Derive quarantine status from EPPO categorization data.

        Checks for EPPO A1/A2 list membership.
        """
        if not isinstance(categorization, list):
            return None

        for entry in categorization:
            qlist = entry.get("qlist", "")
            qlist_label = entry.get("qlist_label", "").lower()

            if "a1" in qlist_label or qlist == "1":
                return QuarantineStatus.A1
            if "a2" in qlist_label or qlist == "2":
                return QuarantineStatus.A2

        return None

    @staticmethod
    def _parse_distribution(distribution_data: Any) -> dict[str, str]:
        """Parse EPPO distribution response into country→status dict."""
        result: dict[str, str] = {}
        if not isinstance(distribution_data, list):
            return result

        for entry in distribution_data:
            country_iso = entry.get("country_iso", "")
            status = entry.get("peststatus", "present")
            if country_iso:
                result[country_iso] = status

        return result
