"""IUCN Red List connector — Species conservation status.

REST API integration (pending API key from user).
Stub implementation reading from local CSV for testing.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource, RawRecord
from ikerketa.models.forestry import IUCNStatus, TreeSpecies

_log = get_logger(__name__)


class Connector(AbstractConnector):
    """IUCN Red List connector (CSV stub, REST pending API key)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.IUCN

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", "data/raw/iucn_trees.csv"))
        if not csv_path.exists():
            raise ConnectorError(f"IUCN CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.IUCN,
                    record_id=row.get("scientific_name", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data
            iucn_val = d.get("iucn_status", "NE")
            try:
                iucn = IUCNStatus(iucn_val)
            except ValueError:
                iucn = IUCNStatus.NOT_EVALUATED

            tree = TreeSpecies(
                source_name=DataSource.IUCN,
                source_record_id=d.get("scientific_name", ""),
                scientific_name=d.get("scientific_name", ""),
                family=d.get("family", ""),
                iucn_status=iucn,
                raw_record=d,
            )
            entities.append(tree)

        self._log.info("iucn_transform_complete", entities=len(entities))
        return entities, []
