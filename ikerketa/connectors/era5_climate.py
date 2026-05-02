"""ERA5 Climate Connector — Copernicus Climate Data Store (CDS).

Fetches historical climate reanalysis data for a geographic point:
  - Mean, min, max temperature (daily)
  - Precipitation (daily)
  - Growing Degree Days accumulation
  - Reference evapotranspiration (ETo)

Used for: multi-year climate reference, GDD calibration, yield gap context.

License: Copernicus — free and open, SaaS commercial use OK.
API: https://cds.climate.copernicus.eu/api/v2
Requires CDS API key (free registration at cds.climate.copernicus.eu).

The connector expects the CDS API key in env var CDSAPI_KEY and
CDSAPI_URL (default https://cds.climate.copernicus.eu/api/v2).
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

import httpx

from ikerketa.connectors.base import AbstractConnector, ConnectorResult
from ikerketa.models.base import DataSource

logger = logging.getLogger(__name__)

CDSAPI_URL = os.getenv("CDSAPI_URL", "https://cds.climate.copernicus.eu/api/v2")


class ERA5ClimateConnector(AbstractConnector):
    """Fetch ERA5 climate reanalysis data for a point via CDS API."""

    source = DataSource.SOILGRIDS

    def fetch(self, lat: float, lon: float, limit: int | None = None) -> ConnectorResult:
        """Fetch ERA5-Land daily aggregates for the past 30 days.

        ERA5-Land has 9km resolution — suitable for regional climate reference.
        """
        api_key = os.getenv("CDSAPI_KEY", "")
        if not api_key:
            return ConnectorResult(
                source=self.source, entities=[],
                errors=["CDSAPI_KEY not configured. Register at cds.climate.copernicus.eu"]
            )

        end_date = date.today() - timedelta(days=5)  # CDS has ~5 day lag
        start_date = end_date - timedelta(days=30)

        try:
            # Submit CDS API request for ERA5-Land daily data
            request_body: dict[str, Any] = {
                "product_type": "reanalysis",
                "format": "json",
                "variable": [
                    "2m_temperature", "2m_temperature_min", "2m_temperature_max",
                    "total_precipitation", "2m_dewpoint_temperature",
                    "surface_solar_radiation_downwards",
                ],
                "year": str(end_date.year),
                "month": f"{end_date.month:02d}",
                "day": [f"{d:02d}" for d in range(
                    max(1, end_date.day - 30), end_date.day + 1
                )] if end_date.month == start_date.month else [f"{d:02d}" for d in range(1, 32)],
                "time": ["00:00", "06:00", "12:00", "18:00"],
                "area": [lat + 0.25, lon - 0.25, lat - 0.25, lon + 0.25],
            }

            resp = httpx.post(
                f"{CDSAPI_URL}/resources/reanalysis-era5-land",
                json=request_body,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )

            if resp.status_code == 202:
                # Async job accepted — return job ID for later retrieval
                return ConnectorResult(
                    source=self.source,
                    entities=[{
                        "type": "ClimateReference",
                        "latitude": lat, "longitude": lon,
                        "status": "queued",
                        "job_id": resp.json().get("request_id", ""),
                        "source": "ERA5-Land (Copernicus CDS) — free and open",
                        "data_fidelity": "modeled_opendata",
                    }]
                )
            elif resp.status_code == 200:
                data = resp.json()
                return ConnectorResult(
                    source=self.source,
                    entities=[{
                        "type": "ClimateReference",
                        "latitude": lat, "longitude": lon,
                        "period_days": (end_date - start_date).days,
                        "data": data,
                        "source": "ERA5-Land (Copernicus CDS) — free and open",
                        "data_fidelity": "modeled_opendata",
                    }]
                )
            else:
                return ConnectorResult(
                    source=self.source, entities=[],
                    errors=[f"CDS returned {resp.status_code}: {resp.text[:200]}"]
                )
        except Exception as e:
            logger.error("ERA5 query failed: %s", e)
            return ConnectorResult(source=self.source, entities=[], errors=[str(e)])
