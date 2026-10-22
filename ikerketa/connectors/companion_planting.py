"""Companion planting connector — curated CSV datasets from GitHub.

Parses companion planting data from local CSV files containing
crop-to-crop relationships (HELPS, HURTS, ATTRACTS, REPELS, etc.).

Expected CSV format:
  plant_a, plant_b, interaction_type, mechanism, citation
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
from ikerketa.models.relationship import CompanionRelation, CompanionType

_log = get_logger(__name__)

DEFAULT_CSV_PATH = "data/raw/companion_planting.csv"

# Map raw interaction strings to CompanionType enum
INTERACTION_MAP: dict[str, CompanionType] = {
    "helps": CompanionType.HELPS,
    "beneficial": CompanionType.HELPS,
    "good": CompanionType.HELPS,
    "companion": CompanionType.HELPS,
    "hurts": CompanionType.HURTS,
    "bad": CompanionType.HURTS,
    "antagonist": CompanionType.HURTS,
    "incompatible": CompanionType.HURTS,
    "attracts": CompanionType.ATTRACTS,
    "repels": CompanionType.REPELS,
    "trap_crop": CompanionType.TRAP_CROP,
    "trap": CompanionType.TRAP_CROP,
    "nitrogen_fixer": CompanionType.NITROGEN_FIXER,
    "nitrogen": CompanionType.NITROGEN_FIXER,
}


class Connector(AbstractConnector):
    """Companion planting local CSV connector."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.COMPANION_PLANTING

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Read companion planting data from local CSV."""
        csv_path_str = params.get("csv_path", DEFAULT_CSV_PATH)
        csv_path = Path(csv_path_str)

        if not csv_path.is_absolute():
            csv_path = settings.data_raw_dir.parent.parent / csv_path_str

        if not csv_path.exists():
            raise ConnectorError(
                f"Companion planting CSV not found at {csv_path}. "
                "Place your companion planting dataset in data/raw/companion_planting.csv"
            )

        self._log.info("companion_fetch_start", path=str(csv_path))
        records: list[RawRecord] = []

        with csv_path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ConnectorError("CSV file has no header row")

            field_map = {col: col.strip().lower().replace(" ", "_") for col in reader.fieldnames}

            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break

                normalized: dict[str, str] = {}
                for orig, val in row.items():
                    key = field_map.get(orig, orig.strip().lower())
                    normalized[key] = val.strip() if val else ""

                plant_a = normalized.get("plant_a", "")
                plant_b = normalized.get("plant_b", "")
                if not plant_a or not plant_b:
                    continue

                records.append(RawRecord(
                    source_name=DataSource.COMPANION_PLANTING,
                    record_id=f"{plant_a}→{plant_b}",
                    data=normalized,
                ))

        self._log.info("companion_fetch_complete", total=len(records))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform companion planting rows into CompanionRelation relationships.

        This connector produces only relationships (no standalone entities).
        """
        relationships: list[BaseRelationship] = []

        for record in raw_records:
            d = record.data
            plant_a = d.get("plant_a", "")
            plant_b = d.get("plant_b", "")
            interaction_raw = d.get("interaction_type", "helps").lower()
            mechanism = d.get("mechanism", "")
            citation = d.get("citation", "")

            companion_type = INTERACTION_MAP.get(interaction_raw, CompanionType.HELPS)

            rel = CompanionRelation(
                source_name=DataSource.COMPANION_PLANTING,
                relationship_type="COMPANION",
                companion_type=companion_type,
                mechanism=mechanism,
                citation=citation,
                evidence_source=citation,
                raw_record=d,
            )
            relationships.append(rel)

        self._log.info("companion_transform_complete", relationships=len(relationships))
        return [], relationships
