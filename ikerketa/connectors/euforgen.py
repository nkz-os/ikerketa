"""EUFORGEN connector — European Forest Genetic Resources.

Reads European tree species data from local CSV.
Produces TreeSpecies entities focused on European forestry context.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource, RawRecord
from ikerketa.models.forestry import TreeSpecies

_log = get_logger(__name__)


class Connector(AbstractConnector):
    """EUFORGEN connector (CSV local)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.EUFORGEN

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", "data/raw/euforgen.csv"))
        if not csv_path.exists():
            raise ConnectorError(f"EUFORGEN CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.EUFORGEN,
                    record_id=row.get("scientific_name", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data
            native_range = [c.strip() for c in d.get("native_range", "").split(";") if c.strip()]
            common_names: dict[str, str] = {}
            if d.get("common_name_en"):
                common_names["en"] = d["common_name_en"]

            tree = TreeSpecies(
                source_name=DataSource.EUFORGEN,
                source_record_id=d.get("scientific_name", ""),
                scientific_name=d.get("scientific_name", ""),
                common_names=common_names,
                family=d.get("family", ""),
                native_range=native_range,
                raw_record=d,
            )
            entities.append(tree)

        self._log.info("euforgen_transform_complete", entities=len(entities))
        return entities, []
