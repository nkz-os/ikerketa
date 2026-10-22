"""USPEST.org connector — Degree-day / GDD phenological model data.

USPEST.org provides degree-day models for pest phenology prediction.
The DDRP (Degree-Day, establishment Risk, and Pest event) maps spatial
models for invasive species lifecycle stages.

Since USPEST lacks a public API, this connector works with:
  1. Local tabular data files (data/raw/uspest_gdd_models.csv)
  2. Future: HTML scraping of station-based degree-day tables

Expected CSV format (consolidated from USPEST.org model database):
  species_name, common_name, tbase_f, tmax_f, method,
  biofix_event, biofix_doy,
  stage_name, stage_dd_low, stage_dd_high,
  generation, notes

The degree-day values can be in °F (USPEST default) or °C.
"""

from __future__ import annotations

import csv
from collections import defaultdict
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
from ikerketa.models.pest import GDDModel, LifeStage, Pest, PestType
from ikerketa.transform.normalizer import fahrenheit_to_celsius

_log = get_logger(__name__)

DEFAULT_CSV_PATH = "data/raw/uspest_gdd_models.csv"


def _safe_float(val: Any) -> float | None:
    """Convert to float, None for empty/invalid."""
    if val is None or val == "" or val == "NA":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class Connector(AbstractConnector):
    """USPEST.org GDD model connector.

    Reads consolidated degree-day model data from a local CSV.
    Groups rows by species to build GDDModel with lifecycle stages.
    """

    @property
    def source_name(self) -> DataSource:
        return DataSource.USPEST

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Read USPEST GDD model data from local CSV.

        Args:
            limit: Maximum species to return.
            **params:
                csv_path: Override file path.

        Returns:
            List of RawRecord, one per species (grouped from rows).
        """
        csv_path_str = params.get("csv_path", DEFAULT_CSV_PATH)
        csv_path = Path(csv_path_str)

        if not csv_path.is_absolute():
            csv_path = settings.data_raw_dir.parent.parent / csv_path_str

        if not csv_path.exists():
            raise ConnectorError(
                f"USPEST GDD models file not found at {csv_path}. "
                "Create a consolidated CSV from USPEST.org model tables "
                "and place in data/raw/uspest_gdd_models.csv"
            )

        self._log.info("uspest_fetch_start", path=str(csv_path))

        # Read all rows and group by species
        species_data: dict[str, list[dict[str, str]]] = defaultdict(list)

        with csv_path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames:
                raise ConnectorError("CSV file has no header row")

            # Normalize field names
            field_map = {col: col.strip().lower().replace(" ", "_") for col in reader.fieldnames}

            for row in reader:
                normalized: dict[str, str] = {}
                for orig_col, value in row.items():
                    key = field_map.get(orig_col, orig_col.strip().lower())
                    normalized[key] = value.strip() if value else ""

                species_key = normalized.get("species_name", "")
                if species_key:
                    species_data[species_key].append(normalized)

        # Build one RawRecord per species
        records: list[RawRecord] = []
        for i, (species_name, rows) in enumerate(species_data.items()):
            if limit and i >= limit:
                break

            records.append(RawRecord(
                source_name=DataSource.USPEST,
                record_id=species_name,
                data={
                    "species_name": species_name,
                    "common_name": rows[0].get("common_name", ""),
                    "tbase_f": rows[0].get("tbase_f", ""),
                    "tmax_f": rows[0].get("tmax_f", ""),
                    "method": rows[0].get("method", ""),
                    "stages": rows,
                },
            ))

        self._log.info("uspest_fetch_complete", total_species=len(records))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform USPEST data into Pest entities with GDD models."""
        entities: list[BaseEntity] = []

        for record in raw_records:
            d = record.data
            species_name = d.get("species_name", "")
            common_name = d.get("common_name", "")

            # Convert base temperatures from °F to °C
            tbase_f = _safe_float(d.get("tbase_f"))
            tmax_f = _safe_float(d.get("tmax_f"))

            tbase_c: float | None = None
            tmax_c: float | None = None

            if tbase_f is not None:
                tbase_c = fahrenheit_to_celsius(tbase_f)
            if tmax_f is not None:
                tmax_c = fahrenheit_to_celsius(tmax_f)

            # Build GDD stages from rows
            stages: list[LifeStage] = []
            stage_rows = d.get("stages", [])

            if isinstance(stage_rows, list):
                for row in stage_rows:
                    stage_name = row.get("stage_name", "")
                    dd_low = _safe_float(row.get("stage_dd_low"))
                    dd_high = _safe_float(row.get("stage_dd_high"))

                    if stage_name and dd_low is not None:
                        stages.append(LifeStage(
                            stage_name=stage_name,
                            gdd_cumulative=dd_low,
                            gdd_range_high=dd_high,
                        ))

            # Sort stages by cumulative degree-days
            stages.sort(key=lambda s: s.gdd_cumulative)

            # Build GDD model
            gdd_model: GDDModel | None = None
            if tbase_c is not None and stages:
                # Generate model name from species
                model_name = species_name.lower().replace(" ", "_") + "_gdd"
                method = d.get("method", "simple_avg")

                gdd_model = GDDModel(
                    model_name=model_name,
                    t_base_celsius=tbase_c,
                    t_max_celsius=tmax_c,
                    calculation_method=method,
                    stages=stages,
                )

            # Common names
            common_names: dict[str, list[str]] = {}
            if common_name:
                common_names["en"] = [common_name]

            # Extract genus from scientific name
            parts = species_name.split()
            genus = parts[0] if parts else ""

            pest = Pest(
                source_name=DataSource.USPEST,
                source_record_id=record.record_id,
                scientific_name=species_name,
                common_names=common_names,
                genus=genus,
                pest_type=PestType.INSECT,
                gdd_model=gdd_model,
                raw_record=d,
            )
            entities.append(pest)

        self._log.info("uspest_transform_complete", entities=len(entities))
        return entities, []
