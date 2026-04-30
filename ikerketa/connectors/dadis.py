"""DAD-IS connector — FAO Domestic Animal Diversity Information System.

Reads livestock breed data from local CSV (pending FAO API bulk access).
Produces Breed entities with conservation status and population data.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource, RawRecord
from ikerketa.models.livestock import Breed, BreedUseType, ConservationStatus, LivestockSpecies

_log = get_logger(__name__)


class Connector(AbstractConnector):
    """FAO DAD-IS connector (CSV local)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.DADIS

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", "data/raw/dadis.csv"))
        if not csv_path.exists():
            raise ConnectorError(f"DAD-IS CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.DADIS,
                    record_id=row.get("dad_is_id", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data
            species_val = d.get("species", "other").lower()
            try:
                species = LivestockSpecies(species_val)
            except ValueError:
                species = LivestockSpecies.OTHER

            use_val = d.get("use_type", "multi").lower()
            try:
                use_type = BreedUseType(use_val)
            except ValueError:
                use_type = BreedUseType.MULTI

            status_val = d.get("conservation_status", "unknown").lower()
            try:
                conservation = ConservationStatus(status_val)
            except ValueError:
                conservation = ConservationStatus.UNKNOWN

            pop = d.get("population_size", "")
            population = int(pop) if pop and pop.isdigit() else None

            breed = Breed(
                source_name=DataSource.DADIS,
                source_record_id=d.get("dad_is_id", ""),
                breed_name=d.get("breed_name", ""),
                species=species,
                country_origin=d.get("country_origin", ""),
                use_type=use_type,
                conservation_status=conservation,
                population_size=population,
                dad_is_id=d.get("dad_is_id", ""),
                transboundary=d.get("transboundary", "false").lower() == "true",
                raw_record=d,
            )
            entities.append(breed)

        self._log.info("dadis_transform_complete", entities=len(entities))
        return entities, []
