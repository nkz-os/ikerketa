"""EU Pesticides Database Connector.

Queries the EU Pesticides Database for active substances authorized
for a given crop, with Maximum Residue Limits (MRLs) and regulatory status.

License: European Commission — public regulatory data, commercial OK.
Source: https://ec.europa.eu/food/plant/pesticides/eu-pesticides-database/

This connector reads from a cached CSV export of the EU Pesticides Database,
updated periodically. The live API requires interactive queries; the CSV
approach is more reliable for batch processing.

CSV expected at: data/raw/eu_pesticides_active_substances.csv
Format: substance, crop, mrl_mg_kg, status (approved/not_approved/withdrawn)
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorResult
from ikerketa.models.base import DataSource

logger = logging.getLogger(__name__)

CSV_PATH = Path(os.getenv("DATA_RAW_DIR", "data/raw")) / "eu_pesticides_active_substances.csv"


class EUPesticidesConnector(AbstractConnector):
    """Read EU Pesticides Database from cached CSV export."""

    source = DataSource.SOILGRIDS

    def fetch(self, lat: float = 0, lon: float = 0, limit: int | None = None) -> ConnectorResult:
        """Return authorized substances for all crops.

        The CSV-based connector returns the full catalogue. Filter by crop
        downstream in BioOrchestrator.
        """
        if not CSV_PATH.exists():
            return ConnectorResult(
                source=self.source, entities=[],
                errors=[f"EU Pesticides CSV not found at {CSV_PATH}. "
                        "Download from https://ec.europa.eu/food/plant/pesticides/eu-pesticides-database/"]
            )

        try:
            entities: list[dict[str, Any]] = []
            with CSV_PATH.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    if limit and count >= limit:
                        break
                    entities.append({
                        "type": "ActiveSubstance",
                        "substance": row.get("substance", ""),
                        "crop": row.get("crop", ""),
                        "mrl_mg_kg": float(row["mrl_mg_kg"]) if row.get("mrl_mg_kg") else None,
                        "status": row.get("status", "unknown"),
                        "source": "EU Pesticides Database (ec.europa.eu) — public data",
                        "data_fidelity": "modeled_opendata",
                    })
                    count += 1

            return ConnectorResult(source=self.source, entities=entities)
        except Exception as e:
            logger.error("EU Pesticides CSV read failed: %s", e)
            return ConnectorResult(source=self.source, entities=[], errors=[str(e)])
