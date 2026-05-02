"""Natura 2000 Connector — EEA European protected areas network.

Queries the EEA Natura 2000 spatial data via the EEA Discomap REST API
to detect if a geographic point falls within a protected area.

License: EEA standard reuse policy — free, commercial OK.
API: https://bio.discomap.eea.europa.eu/arcgis/rest/services/ProtectedSites/Natura2000/MapServer

Returns a ProtectedArea entity with site name, type (SAC/SPA), and distance.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ikerketa.connectors.base import AbstractConnector, ConnectorResult
from ikerketa.models.base import DataSource

logger = logging.getLogger(__name__)

EEA_DISCOMAP_URL = (
    "https://bio.discomap.eea.europa.eu/arcgis/rest/services/"
    "ProtectedSites/Natura2000/MapServer"
)

# Agricultural restrictions by Natura 2000 habitat type
# Simplified from EU Habitats Directive 92/43/EEC and Birds Directive 2009/147/EC
SAC_RESTRICTIONS = {
    "default": "Requiere evaluación de impacto ambiental para cambios de uso del suelo. "
               "Restricciones en aplicación de fitosanitarios cerca de masas de agua.",
}
SPA_RESTRICTIONS = {
    "default": "Zona de especial protección para aves. Restricciones en fechas de "
               "laboreo y cosecha durante periodos de nidificación.",
}


class Natura2000Connector(AbstractConnector):
    """Check if a geographic point is within or near a Natura 2000 protected area."""

    source = DataSource.SOILGRIDS  # reuse temporarily

    def fetch(self, lat: float, lon: float, limit: int | None = None) -> ConnectorResult:
        try:
            # Query EEA Discomap Identify service at the point
            params: dict[str, Any] = {
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "layers": "all",
                "tolerance": 500,  # 500m buffer
                "mapExtent": f"{lon-0.5},{lat-0.5},{lon+0.5},{lat+0.5}",
                "imageDisplay": "800,600,96",
                "returnGeometry": "false",
                "f": "json",
            }
            resp = httpx.get(f"{EEA_DISCOMAP_URL}/identify", params=params, timeout=15)

            if resp.status_code != 200:
                return ConnectorResult(source=self.source, entities=[])

            data = resp.json()
            results = data.get("results", [])

            if not results:
                return ConnectorResult(
                    source=self.source,
                    entities=[{
                        "type": "ProtectedArea",
                        "latitude": lat, "longitude": lon,
                        "in_protected_area": False,
                        "source": "EEA Natura 2000 — EEA reuse policy",
                        "data_fidelity": "modeled_opendata",
                    }]
                )

            entities = []
            for r in results:
                attrs = r.get("attributes", {})
                site_name = attrs.get("SITENAME", attrs.get("SITE_NAME", "Unknown"))
                site_type = attrs.get("SITETYPE", "")
                site_code = attrs.get("SITECODE", "")

                restrictions = []
                if "A" in site_type or "B" in site_type:  # SPA
                    restrictions.append(SPA_RESTRICTIONS["default"])
                if "C" in site_type or "SCI" in site_type or "SAC" in site_type:
                    restrictions.append(SAC_RESTRICTIONS["default"])

                entities.append({
                    "type": "ProtectedArea",
                    "latitude": lat, "longitude": lon,
                    "in_protected_area": True,
                    "site_name": site_name,
                    "site_code": site_code,
                    "site_type": site_type,
                    "restrictions": " | ".join(restrictions) if restrictions else "",
                    "source": "EEA Natura 2000 — EEA reuse policy",
                    "data_fidelity": "modeled_opendata",
                })

            return ConnectorResult(source=self.source, entities=entities)

        except Exception as e:
            logger.error("Natura 2000 query failed: %s", e)
            return ConnectorResult(source=self.source, entities=[], errors=[str(e)])
