"""Forages connector — CIAT/ILRI Tropical Forages database.

Reads forage species data from local CSV.
Produces FeedResource entities with pasture-specific metrics.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource, RawRecord
from ikerketa.models.livestock import FeedResource

_log = get_logger(__name__)


def _float_or_none(val: str) -> float | None:
    try:
        return float(val) if val.strip() else None
    except ValueError:
        return None


class Connector(AbstractConnector):
    """CIAT/ILRI Tropical Forages connector (CSV local)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.FORAGES

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", "data/raw/forages.csv"))
        if not csv_path.exists():
            raise ConnectorError(f"Forages CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.FORAGES,
                    record_id=row.get("species_name", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data
            suitable = [s.strip() for s in d.get("suitable_livestock", "").split(";") if s.strip()]

            # Map dry matter yield to a note field
            dm_yield = d.get("dry_matter_yield_t_ha", "")
            toxicity = ""
            if d.get("nitrogen_fixing", "false").lower() == "true":
                toxicity = "N-fixing legume"

            feed = FeedResource(
                source_name=DataSource.FORAGES,
                source_record_id=d.get("species_name", ""),
                feed_name=d.get("common_name", d.get("species_name", "")),
                scientific_name=d.get("species_name", ""),
                crude_protein_pct=_float_or_none(d.get("crude_protein_pct", "")),
                organic_compatible=True,  # All tropical forages are organic-compatible
                toxicity_notes=toxicity,
                suitable_species=suitable,
                raw_record=d,
            )
            entities.append(feed)

        self._log.info("forages_transform_complete", entities=len(entities))
        return entities, []
