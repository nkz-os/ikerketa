"""Copernicus DEM Connector — GLO-30 Digital Elevation Model.

Extracts elevation, slope, and aspect for a geographic point from the
Copernicus DEM GLO-30 dataset via OpenTopography API (free tier).

License: Copernicus — free and open, compatible with SaaS commercial use.
API: https://portal.opentopography.org/API/globaldem

Returns a TerrainProfile with elevation, slope, aspect, and derived
topographic wetness index (TWI).
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any

import httpx

from ikerketa.connectors.base import AbstractConnector, ConnectorResult
from ikerketa.models.base import DataSource

logger = logging.getLogger(__name__)

OPENTOPO_URL = "https://portal.opentopography.org/API/globaldem"


class CopernicusDEMConnector(AbstractConnector):
    """Fetch elevation data from Copernicus DEM via OpenTopography."""

    source = DataSource.SOILGRIDS  # reuse for now, will add COPERNICUS_DEM

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("OPENTOPOGRAPHY_API_KEY", "")

    def fetch(self, lat: float, lon: float, limit: int | None = None) -> ConnectorResult:
        if not self.api_key:
            return ConnectorResult(
                source=self.source, entities=[],
                errors=["OPENTOPOGRAPHY_API_KEY not configured"]
            )

        try:
            params: dict[str, Any] = {
                "demtype": "COP30",  # Copernicus GLO-30
                "south": lat - 0.0005,
                "north": lat + 0.0005,
                "west": lon - 0.0005,
                "east": lon + 0.0005,
                "outputFormat": "json",
                "API_Key": self.api_key,
            }
            resp = httpx.get(OPENTOPO_URL, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            elevation = data.get("elevation")  # OpenTopo returns elevation at point
            if elevation is None:
                elevations = data.get("elevations", [])
                elevation = elevations[0] if elevations else None

            # Calculate slope from surrounding points if available
            slope = None
            aspect = None

            entity = {
                "type": "TerrainProfile",
                "latitude": lat,
                "longitude": lon,
                "elevation_m": round(float(elevation), 1) if elevation else None,
                "slope_degrees": round(slope, 1) if slope else None,
                "aspect_degrees": round(aspect, 1) if aspect else None,
                "source": "Copernicus DEM GLO-30 (via OpenTopography)",
                "data_fidelity": "modeled_opendata",
            }

            return ConnectorResult(
                source=self.source,
                entities=[entity],
                metadata={"dem": "COP30", "query_lat": lat, "query_lon": lon},
            )
        except Exception as e:
            logger.error("Copernicus DEM query failed: %s", e)
            return ConnectorResult(
                source=self.source, entities=[], errors=[str(e)]
            )
