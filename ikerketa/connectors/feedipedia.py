"""Feedipedia connector — animal feed resource database.

Reads feed composition data from local CSV (curated from Feedipedia).
Produces FeedResource entities with nutritional metrics.
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
    """Feedipedia connector (CSV local)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.FEEDIPEDIA

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", "data/raw/feedipedia.csv"))
        if not csv_path.exists():
            raise ConnectorError(f"Feedipedia CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.FEEDIPEDIA,
                    record_id=row.get("feed_name", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data
            suitable = [s.strip() for s in d.get("suitable_species", "").split(";") if s.strip()]

            feed = FeedResource(
                source_name=DataSource.FEEDIPEDIA,
                source_record_id=d.get("feed_name", ""),
                feed_name=d.get("feed_name", ""),
                scientific_name=d.get("scientific_name", ""),
                dry_matter_pct=_float_or_none(d.get("dry_matter_pct", "")),
                crude_protein_pct=_float_or_none(d.get("crude_protein_pct", "")),
                crude_fiber_pct=_float_or_none(d.get("crude_fiber_pct", "")),
                metabolizable_energy_mj=_float_or_none(d.get("metabolizable_energy_mj", "")),
                organic_compatible=d.get("organic_compatible", "false").lower() == "true",
                toxicity_notes=d.get("toxicity_notes", ""),
                suitable_species=suitable,
                raw_record=d,
            )
            entities.append(feed)

        self._log.info("feedipedia_transform_complete", entities=len(entities))
        return entities, []
