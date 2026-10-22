"""FiBL connector — organic input products from local curated CSV.

FiBL (Research Institute of Organic Agriculture) maintains the European
Input List of authorized organic farming products. Since FiBL doesn't
expose a public API, this connector reads from a locally maintained CSV.

Expected CSV format:
  product_name, active_substance, manufacturer,
  eu_regulation, organic_compatible, category,
  target_pests, target_crops, notes
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
from ikerketa.models.regulation import ActiveSubstance

_log = get_logger(__name__)

DEFAULT_CSV_PATH = "data/raw/fibl_inputs.csv"


class Connector(AbstractConnector):
    """FiBL European Input List local CSV connector."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.FIBL

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Read FiBL input list from local CSV."""
        csv_path_str = params.get("csv_path", DEFAULT_CSV_PATH)
        csv_path = Path(csv_path_str)

        if not csv_path.is_absolute():
            csv_path = settings.data_raw_dir.parent.parent / csv_path_str

        if not csv_path.exists():
            raise ConnectorError(
                f"FiBL input list not found at {csv_path}. "
                "Curate from https://www.inputs.eu and place in data/raw/fibl_inputs.csv"
            )

        self._log.info("fibl_fetch_start", path=str(csv_path))
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
                product_name = normalized.get("product_name", "")
                if not product_name:
                    continue

                records.append(RawRecord(
                    source_name=DataSource.FIBL,
                    record_id=product_name,
                    data=normalized,
                ))

        self._log.info("fibl_fetch_complete", total=len(records))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform FiBL data into ActiveSubstance entities."""
        entities: list[BaseEntity] = []

        for record in raw_records:
            d = record.data

            substance_name = d.get("active_substance", d.get("product_name", ""))
            if not substance_name:
                continue

            organic = d.get("organic_compatible", "true").lower()
            is_organic = organic in ("true", "1", "yes", "y")

            entity = ActiveSubstance(
                source_name=DataSource.FIBL,
                source_record_id=record.record_id,
                substance_name=substance_name,
                is_approved_eu=True,  # FiBL only lists approved products
                organic_compatible=is_organic,
                substance_category=d.get("category", "organic_input"),
                raw_record=d,
            )
            entities.append(entity)

        self._log.info("fibl_transform_complete", entities=len(entities))
        return entities, []
