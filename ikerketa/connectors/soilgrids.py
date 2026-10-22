"""SoilGrids 2.0 Connector — ISRIC soil property data.

Queries the SoilGrids REST API for soil properties at a given point.
Returns a SoilProfile entity with physical and chemical properties.

API: https://rest.isric.org/soilgrids/v2.0/properties/query
License: CC-BY 4.0 — compatible with NKZ-OS SaaS commercial use.

Properties queried (0-5cm, 5-15cm, 15-30cm depths):
  - phh2o (pH in water) — mapped to ph
  - sand, silt, clay (texture fractions) — mapped to texture class
  - soc (soil organic carbon) — mapped to organic_matter_pct
  - nitrogen (total nitrogen) — mapped to n_total_pct
  - cec (cation exchange capacity) — mapped to cec_cmol_kg
  - bdod (bulk density) — mapped to bulk_density_g_cm3
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ikerketa.connectors.base import AbstractConnector, ConnectorResult
from ikerketa.models.base import DataSource

logger = logging.getLogger(__name__)

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# SoilGrids property → our internal name + depth layers
SOIL_PROPERTIES = {
    "phh2o": {"name": "ph_h2o", "unit": "pH", "depths": ["0-5cm", "5-15cm", "15-30cm"]},
    "sand": {"name": "sand_pct", "unit": "%", "depths": ["0-5cm", "5-15cm", "15-30cm"]},
    "silt": {"name": "silt_pct", "unit": "%", "depths": ["0-5cm", "5-15cm", "15-30cm"]},
    "clay": {"name": "clay_pct", "unit": "%", "depths": ["0-5cm", "5-15cm", "15-30cm"]},
    "soc": {"name": "soc_dg_kg", "unit": "dg/kg", "depths": ["0-5cm", "5-15cm", "15-30cm"]},
    "nitrogen": {"name": "nitrogen_cg_kg", "unit": "cg/kg", "depths": ["0-5cm", "5-15cm", "15-30cm"]},
    "cec": {"name": "cec_cmol_kg", "unit": "cmol(c)/kg", "depths": ["0-5cm", "5-15cm", "15-30cm"]},
    "bdod": {"name": "bdod_cg_cm3", "unit": "cg/cm³", "depths": ["0-5cm", "5-15cm", "15-30cm"]},
}

# Texture classification from sand/silt/clay (USDA simplified)
def _classify_texture(sand: float, silt: float, clay: float) -> str:
    if clay >= 40:
        return "clay"
    elif clay >= 28:
        return "clay_loam"
    elif silt >= 50:
        return "silt_loam"
    elif sand >= 85:
        return "sand"
    elif sand >= 70:
        return "sandy_loam"
    elif clay >= 20:
        return "loam"
    elif silt >= 40:
        return "silt_loam"
    return "loam"


class SoilGridsConnector(AbstractConnector):
    """Fetch soil properties from ISRIC SoilGrids 2.0 for a geographic point."""

    source = DataSource.SOILGRIDS

    def __init__(self):
        super().__init__()
        self.base_url = SOILGRIDS_URL

    def fetch(self, lat: float, lon: float, limit: int | None = None) -> ConnectorResult:
        """Query SoilGrids for a single point.

        Args:
            lat: Latitude (WGS84)
            lon: Longitude (WGS84)
            limit: Not used (point query)

        Returns:
            ConnectorResult with SoilProfile entity
        """
        properties = list(SOIL_PROPERTIES.keys())
        depths = ["0-5cm", "5-15cm", "15-30cm"]

        body: dict[str, Any] = {
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": properties,
            "depths": depths,
            "values": ["mean"],
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/query",
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            return self._transform(data, lat, lon)
        except httpx.HTTPError as e:
            logger.error("SoilGrids query failed for (%.4f, %.4f): %s", lat, lon, e)
            return ConnectorResult(
                source=self.source, entities=[], errors=[str(e)]
            )
        except Exception as e:
            logger.error("SoilGrids unexpected error: %s", e)
            return ConnectorResult(
                source=self.source, entities=[], errors=[str(e)]
            )

    def _transform(self, data: dict, lat: float, lon: float) -> ConnectorResult:
        """Transform SoilGrids JSON response into a SoilProfile entity."""
        try:
            layers = data.get("properties", {}).get("layers", [])
            if not layers:
                return ConnectorResult(
                    source=self.source, entities=[],
                    errors=["No soil data for this location"]
                )

            # Extract mean values per property per depth
            props: dict[str, dict[str, float]] = {}
            for layer in layers:
                prop_name = layer.get("name", "")
                depths_list = layer.get("depths", [])
                for d in depths_list:
                    depth_label = d.get("label", "")
                    mean_val = d.get("values", {}).get("mean")
                    if mean_val is not None and prop_name in SOIL_PROPERTIES:
                        internal = SOIL_PROPERTIES[prop_name]["name"]
                        if internal not in props:
                            props[internal] = {}
                        props[internal][depth_label] = float(mean_val)

            # Get topsoil values (0-5cm)
            top = "0-5cm"
            ph = props.get("ph_h2o", {}).get(top)
            sand = props.get("sand_pct", {}).get(top)
            silt = props.get("silt_pct", {}).get(top)
            clay = props.get("clay_pct", {}).get(top)
            soc = props.get("soc_dg_kg", {}).get(top)
            nitrogen = props.get("nitrogen_cg_kg", {}).get(top)
            cec = props.get("cec_cmol_kg", {}).get(top)
            bdod = props.get("bdod_cg_cm3", {}).get(top)

            texture = None
            if sand is not None and silt is not None and clay is not None:
                texture = _classify_texture(sand, silt, clay)

            entity = {
                "type": "SoilProfile",
                "latitude": lat,
                "longitude": lon,
                "ph": round(ph, 1) if ph else None,
                "texture_class": texture,
                "sand_pct": round(sand, 1) if sand else None,
                "silt_pct": round(silt, 1) if silt else None,
                "clay_pct": round(clay, 1) if clay else None,
                "organic_carbon_dg_kg": round(soc, 1) if soc else None,
                "nitrogen_cg_kg": round(nitrogen, 2) if nitrogen else None,
                "cec_cmol_kg": round(cec, 1) if cec else None,
                "bulk_density_cg_cm3": round(bdod, 2) if bdod else None,
                "source": "SoilGrids 2.0 (ISRIC) — CC-BY 4.0",
                "data_fidelity": "modeled_opendata",
            }

            return ConnectorResult(
                source=self.source,
                entities=[entity],
                metadata={"query_lat": lat, "query_lon": lon},
            )
        except Exception as e:
            logger.error("SoilGrids transform error: %s", e)
            return ConnectorResult(
                source=self.source, entities=[], errors=[str(e)]
            )
