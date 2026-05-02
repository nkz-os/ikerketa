"""CPVO Plant Variety Database Connector.

Queries the Community Plant Variety Office (CPVO) database for registered
varieties of agricultural and vegetable species in the EU.

License: CPVO data — public, commercial OK.
API: https://cpvo.europa.eu/en/applications-and-examinations/variety-database

Uses the CPVO Variety Finder REST-like interface.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ikerketa.connectors.base import AbstractConnector, ConnectorResult
from ikerketa.models.base import DataSource

logger = logging.getLogger(__name__)

CPVO_URL = "https://cpvo.europa.eu/api/variety-finder"


class CPVOVarietiesConnector(AbstractConnector):
    """Query CPVO for registered varieties of a crop species."""

    source = DataSource.SOILGRIDS

    def fetch(self, lat: float = 0, lon: float = 0, limit: int | None = 50) -> ConnectorResult:
        """Return registered varieties. Species filter via `species` param if needed."""
        try:
            params: dict[str, Any] = {"limit": limit or 50, "format": "json"}
            # Note: CPVO API may require species_code; use generic search if not provided
            resp = httpx.get(f"{CPVO_URL}/search", params=params, timeout=20)

            if resp.status_code != 200:
                return ConnectorResult(
                    source=self.source, entities=[],
                    errors=[f"CPVO returned {resp.status_code}"]
                )

            data = resp.json()
            varieties = data.get("varieties", data.get("results", data if isinstance(data, list) else []))

            entities: list[dict[str, Any]] = []
            for v in varieties[:limit]:
                if isinstance(v, dict):
                    entities.append({
                        "type": "CropVariety",
                        "variety_name": v.get("varietyName", v.get("denomination", "")),
                        "species": v.get("species", v.get("commonName", "")),
                        "species_code": v.get("speciesCode", ""),
                        "registration_year": v.get("registrationYear", v.get("grantYear", "")),
                        "maintainer": v.get("maintainer", v.get("applicant", "")),
                        "status": v.get("status", "registered"),
                        "source": "CPVO Variety Database (cpvo.europa.eu) — public data",
                        "data_fidelity": "modeled_opendata",
                    })

            return ConnectorResult(source=self.source, entities=entities)
        except Exception as e:
            logger.error("CPVO query failed: %s", e)
            return ConnectorResult(source=self.source, entities=[], errors=[str(e)])
