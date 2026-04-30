"""CABI CPC connector — stub with local fixtures.

CABI Crop Protection Compendium requires commercial/institutional license.
This connector reads from local CSV fixtures for biocontrol agent data
(natural enemy relationships).

When institutional access is available, this connector can be extended
to use the CABI API (https://api.cabi.org).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ikerketa.config import settings
from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import (
    BaseEntity,
    BaseRelationship,
    DataSource,
    RawRecord,
)
from ikerketa.models.pest import Pest, PestType
from ikerketa.models.relationship import NaturalEnemy

_log = get_logger(__name__)

DEFAULT_CSV_PATH = "data/raw/cabi_natural_enemies.csv"


class Connector(AbstractConnector):
    """CABI CPC connector (stub — local CSV only).

    Produces Pest entities and NaturalEnemy relationships from
    locally curated data.
    """

    @property
    def source_name(self) -> DataSource:
        return DataSource.CABI

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Read CABI data from local CSV fixture."""
        csv_path_str = params.get("csv_path", DEFAULT_CSV_PATH)
        csv_path = Path(csv_path_str)

        if not csv_path.is_absolute():
            csv_path = settings.data_raw_dir.parent.parent / csv_path_str

        if not csv_path.exists():
            raise ConnectorError(
                f"CABI fixture file not found at {csv_path}. "
                "CABI CPC requires institutional license. "
                "Place curated data in data/raw/cabi_natural_enemies.csv"
            )

        self._log.info("cabi_fetch_start", path=str(csv_path))
        records: list[RawRecord] = []

        with csv_path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ConnectorError("CSV file has no header row")

            field_map = {c: c.strip().lower().replace(" ", "_") for c in reader.fieldnames}

            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break

                normalized = {field_map.get(k, k.strip().lower()): v.strip() for k, v in row.items() if v}

                pest_name = normalized.get("pest_name", "")
                enemy_name = normalized.get("enemy_name", "")
                if not pest_name or not enemy_name:
                    continue

                records.append(RawRecord(
                    source_name=DataSource.CABI,
                    record_id=f"{pest_name}→{enemy_name}",
                    data=normalized,
                ))

        self._log.info("cabi_fetch_complete", total=len(records))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform CABI data into NaturalEnemy relationships."""
        relationships: list[BaseRelationship] = []

        for record in raw_records:
            d = record.data

            enemy = NaturalEnemy(
                source_name=DataSource.CABI,
                relationship_type="CONTROLS",
                control_type=d.get("control_type", "predator"),
                efficacy_rating=d.get("efficacy", ""),
                target_life_stage=d.get("target_stage", ""),
                enemy_scientific_name=d.get("enemy_name", ""),
                enemy_eppo_code=d.get("enemy_eppo_code") or None,
                evidence_source="CABI CPC",
                raw_record=d,
            )
            relationships.append(enemy)

        self._log.info("cabi_transform_complete", relationships=len(relationships))
        return [], relationships
