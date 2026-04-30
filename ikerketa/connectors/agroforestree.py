"""ICRAF Agroforestree connector — agroforestry tree species database.

Reads agroforestry tree data from local CSV (ICRAF World Agroforestry).
Produces TreeSpecies entities with fodder/timber use and N-fixation data.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource, RawRecord
from ikerketa.models.forestry import EcosystemService, TreeSpecies

_log = get_logger(__name__)


class Connector(AbstractConnector):
    """ICRAF Agroforestree connector (CSV local)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.AGROFORESTREE

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", "data/raw/agroforestree.csv"))
        if not csv_path.exists():
            raise ConnectorError(f"Agroforestree CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.AGROFORESTREE,
                    record_id=row.get("species_name", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data

            # Parse ecosystem services
            services_raw = d.get("ecosystem_services", "")
            services = []
            for s in services_raw.split(";"):
                s = s.strip()
                try:
                    services.append(EcosystemService(s))
                except ValueError:
                    pass

            common_names: dict[str, str] = {}
            if d.get("common_name"):
                common_names["en"] = d["common_name"]

            tree = TreeSpecies(
                source_name=DataSource.AGROFORESTREE,
                source_record_id=d.get("species_name", ""),
                scientific_name=d.get("species_name", ""),
                common_names=common_names,
                family=d.get("family", ""),
                nitrogen_fixing=d.get("nitrogen_fixing", "false").lower() == "true",
                ecosystem_services=services,
                raw_record=d,
            )
            entities.append(tree)

        self._log.info("agroforestree_transform_complete", entities=len(entities))
        return entities, []
