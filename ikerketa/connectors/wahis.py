"""WAHIS connector — WOAH World Animal Health Information System.

Reads animal disease incident data from local CSV (Kaggle export).
Produces AnimalDisease entities with zoonotic and notification flags.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource, RawRecord
from ikerketa.models.livestock import AnimalDisease, PathogenType

_log = get_logger(__name__)


class Connector(AbstractConnector):
    """WOAH/WAHIS connector (CSV local)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.WAHIS

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", "data/raw/wahis.csv"))
        if not csv_path.exists():
            raise ConnectorError(f"WAHIS CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.WAHIS,
                    record_id=row.get("disease_name", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data
            pathogen_val = d.get("pathogen_type", "unknown").lower()
            try:
                pathogen = PathogenType(pathogen_val)
            except ValueError:
                pathogen = PathogenType.UNKNOWN

            affected = [s.strip() for s in d.get("affected_species", "").split(";") if s.strip()]

            disease = AnimalDisease(
                source_name=DataSource.WAHIS,
                source_record_id=d.get("disease_name", ""),
                disease_name=d.get("disease_name", ""),
                pathogen_type=pathogen,
                scientific_name=d.get("scientific_name", ""),
                woah_listed=d.get("woah_listed", "false").lower() == "true",
                zoonotic=d.get("zoonotic", "false").lower() == "true",
                affected_species=affected,
                notifiable_eu=d.get("notifiable_eu", "false").lower() == "true",
                raw_record=d,
            )
            entities.append(disease)

        self._log.info("wahis_transform_complete", entities=len(entities))
        return entities, []
