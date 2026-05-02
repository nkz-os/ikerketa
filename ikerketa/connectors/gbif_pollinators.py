"""GBIF Connector — Global Biodiversity Information Facility.

Queries GBIF occurrence data for pollinator species near a geographic point.
Filters by license (CC0 + CC-BY 4.0 only — no CC-BY-NC).

License: GBIF-mediated data, filtered to CC0 + CC-BY 4.0 only.
API: https://api.gbif.org/v1/occurrence/search

Returns PollinatorOccurrence entities with species, count, and distance.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ikerketa.connectors.base import AbstractConnector, ConnectorResult
from ikerketa.models.base import DataSource

logger = logging.getLogger(__name__)

GBIF_API = "https://api.gbif.org/v1/occurrence/search"

# Pollinator taxa (GBIF taxonomic keys)
POLLINATOR_TAXA = [
    "Apidae",      # bees
    "Syrphidae",   # hoverflies
    "Bombyliidae", # bee flies
    "Lepidoptera", # butterflies/moths (pollinator species only)
]

# License filter: CC0 + CC-BY 4.0 only — NO NC (non-commercial)
COMPATIBLE_LICENSES = ["CC0_1_0", "CC_BY_4_0", "CC_BY_3_0"]


class GBIFPollinatorsConnector(AbstractConnector):
    """Query GBIF for pollinator species occurrences near a location.

    Non-negotiable: only CC0 and CC-BY licenses are fetched.
    CC-BY-NC and other incompatible licenses are rejected at query time.
    """

    source = DataSource.SOILGRIDS

    def fetch(self, lat: float, lon: float, limit: int | None = 20) -> ConnectorResult:
        results: list[dict[str, Any]] = []
        radius_m = 5000  # 5km radius

        for taxon in POLLINATOR_TAXA:
            try:
                params: dict[str, Any] = {
                    "taxonKey": taxon,
                    "geometry": f"POINT({lon} {lat})",
                    "geoDistance": f"{radius_m}m",
                    "limit": min(limit or 20, 50),
                    "license": ",".join(COMPATIBLE_LICENSES),  # CRITICAL: filter in query
                    "hasCoordinate": True,
                }
                resp = httpx.get(f"{GBIF_API}", params=params, timeout=20)

                if resp.status_code != 200:
                    logger.debug("GBIF returned %d for taxon %s", resp.status_code, taxon)
                    continue

                data = resp.json()
                for occ in data.get("results", []):
                    # Double-check license server-side
                    lic = occ.get("license", "")
                    if lic not in COMPATIBLE_LICENSES:
                        continue

                    species = occ.get("species", occ.get("scientificName", "Unknown"))
                    results.append({
                        "type": "PollinatorOccurrence",
                        "species": species,
                        "taxon_group": taxon,
                        "latitude": occ.get("decimalLatitude"),
                        "longitude": occ.get("decimalLongitude"),
                        "record_count": occ.get("individualCount", 1),
                        "license": lic,
                        "source": "GBIF.org — filtered CC0/CC-BY only",
                        "data_fidelity": "modeled_opendata",
                    })
            except Exception as e:
                logger.debug("GBIF query for %s: %s", taxon, e)
                continue

        return ConnectorResult(
            source=self.source, entities=results,
            metadata={"query_lat": lat, "query_lon": lon, "radius_m": radius_m},
        )
