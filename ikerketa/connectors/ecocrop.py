"""EcoCrop connector — FAO GAEZ EcoCrop local CSV parser.

EcoCrop database contains edaphoclimatic requirements for 2000+ plant species.
Since the FAO GAEZ v5 portal only serves data via a JS web app, this connector
reads from a locally downloaded CSV file placed in data/raw/ecocrop.csv.

Download instructions:
  1. Visit https://gaez.fao.org/pages/ecocrop-find-plant
  2. Search/browse crops → export to CSV (or use a community mirror)
  3. Place as data/raw/ecocrop.csv

Expected columns (FAO EcoCrop schema):
  ScientificName, CommonName, Family, LifeForm,
  PhLow, PhHigh, LightLow, LightHigh,
  TempMinAbs, TempMinOpt, TempMaxOpt, TempMaxAbs,
  RainMinAbs, RainMinOpt, RainMaxOpt, RainMaxAbs,
  TextureClass, FertilityRequirement, DrainageRequirement,
  AltMinAbs, AltMaxAbs, CycleLow, CycleHigh,
  PhotoperiodSensitivity, LatMinAbs, LatMaxAbs
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
from ikerketa.models.crop import (
    ClimaticProfile,
    Crop,
    EdaphicProfile,
)

_log = get_logger(__name__)

# Default file path
DEFAULT_CSV_PATH = "data/raw/ecocrop.csv"

# EcoCrop CSV column mappings (case-insensitive normalization applied)
COLUMN_MAP = {
    "scientificname": "scientific_name",
    "scientific_name": "scientific_name",
    "commonname": "common_name",
    "common_name": "common_name",
    "family": "family",
    "lifeform": "life_form",
    "life_form": "life_form",
    "phlow": "ph_min",
    "ph_low": "ph_min",
    "phhigh": "ph_max",
    "ph_high": "ph_max",
    "lightlow": "light_min",
    "lighthigh": "light_max",
    "tempminabs": "temp_min_abs",
    "tempminopt": "temp_min_opt",
    "tempmaxopt": "temp_max_opt",
    "tempmaxabs": "temp_max_abs",
    "rainminabs": "rain_min_abs",
    "rainminopt": "rain_min_opt",
    "rainmaxopt": "rain_max_opt",
    "rainmaxabs": "rain_max_abs",
    "textureclass": "texture",
    "texture": "texture",
    "fertilityrequirement": "fertility",
    "fertility": "fertility",
    "drainagerequirement": "drainage",
    "drainage": "drainage",
    "altminabs": "alt_min",
    "altmaxabs": "alt_max",
    "cyclelow": "cycle_min",
    "cyclehigh": "cycle_max",
}

# Texture mapping from EcoCrop codes to our model
TEXTURE_MAP = {
    "1": "light",
    "2": "light_medium",
    "3": "medium",
    "4": "medium_heavy",
    "5": "heavy",
    "6": "organic",
    "light": "light",
    "medium": "medium",
    "heavy": "heavy",
}

# Fertility mapping
FERTILITY_MAP = {
    "1": "low",
    "2": "moderate",
    "3": "high",
    "low": "low",
    "moderate": "moderate",
    "high": "high",
}


def _safe_float(val: Any) -> float | None:
    """Convert a value to float, returning None for empty/invalid."""
    if val is None or val == "" or val == "NA" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> int | None:
    """Convert a value to int, returning None for empty/invalid."""
    f = _safe_float(val)
    return int(f) if f is not None else None


class Connector(AbstractConnector):
    """EcoCrop local CSV connector.

    Parses a locally downloaded EcoCrop CSV file and transforms
    each row into a Crop entity with EdaphicProfile and ClimaticProfile.
    """

    @property
    def source_name(self) -> DataSource:
        return DataSource.ECOCROP

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Read EcoCrop CSV from local data directory.

        Args:
            limit: Maximum rows to read (None = all).
            **params:
                csv_path: Override CSV file path (default: data/raw/ecocrop.csv)

        Returns:
            List of RawRecord, one per CSV row.
        """
        csv_path_str = params.get("csv_path", DEFAULT_CSV_PATH)
        csv_path = Path(csv_path_str)

        if not csv_path.is_absolute():
            csv_path = settings.data_raw_dir.parent.parent / csv_path_str

        if not csv_path.exists():
            raise ConnectorError(
                f"EcoCrop CSV not found at {csv_path}. "
                "Download from https://gaez.fao.org/pages/ecocrop-find-plant "
                "and place in data/raw/ecocrop.csv"
            )

        self._log.info("ecocrop_fetch_start", path=str(csv_path))

        records: list[RawRecord] = []

        with csv_path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)

            # Normalize column names
            if reader.fieldnames:
                normalized_fields = {
                    col: COLUMN_MAP.get(col.strip().lower().replace(" ", "_"), col.strip().lower())
                    for col in reader.fieldnames
                }
            else:
                raise ConnectorError("CSV file has no header row")

            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break

                # Apply column normalization
                normalized_row: dict[str, str] = {}
                for orig_col, value in row.items():
                    mapped_col = normalized_fields.get(orig_col, orig_col)
                    normalized_row[mapped_col] = value.strip() if value else ""

                sci_name = normalized_row.get("scientific_name", "")
                record_id = sci_name or f"row_{i}"

                records.append(RawRecord(
                    source_name=DataSource.ECOCROP,
                    record_id=record_id,
                    data=normalized_row,
                ))

        self._log.info("ecocrop_fetch_complete", total_records=len(records))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform EcoCrop CSV rows into Crop entities."""
        entities: list[BaseEntity] = []

        for record in raw_records:
            d = record.data

            sci_name = d.get("scientific_name", "")
            if not sci_name:
                self._log.warning("skip_no_name", record_id=record.record_id)
                continue

            # Build edaphic profile
            edaphic = None
            ph_min = _safe_float(d.get("ph_min"))
            ph_max = _safe_float(d.get("ph_max"))

            if ph_min is not None or ph_max is not None:
                from ikerketa.models.crop import SoilTexture, SoilFertility

                texture_raw = d.get("texture", "").lower()
                texture_mapped = TEXTURE_MAP.get(texture_raw)
                soil_textures: list[SoilTexture] = []
                if texture_mapped:
                    try:
                        soil_textures = [SoilTexture(texture_mapped)]
                    except ValueError:
                        pass

                fertility_raw = d.get("fertility", "").lower()
                fertility_val: SoilFertility | None = None
                mapped_fert = FERTILITY_MAP.get(fertility_raw)
                if mapped_fert:
                    try:
                        fertility_val = SoilFertility(mapped_fert)
                    except ValueError:
                        pass

                edaphic = EdaphicProfile(
                    ph_min=ph_min or 0.0,
                    ph_max=ph_max or 14.0,
                    soil_textures=soil_textures,
                    fertility=fertility_val,
                )

            # Build climatic profile
            climatic = None
            temp_min = _safe_float(d.get("temp_min_abs"))
            temp_max = _safe_float(d.get("temp_max_abs"))
            cycle_min = _safe_int(d.get("cycle_min"))
            cycle_max = _safe_int(d.get("cycle_max"))

            if temp_min is not None or temp_max is not None:
                climatic = ClimaticProfile(
                    t_kill=temp_min,
                    t_min=_safe_float(d.get("temp_min_opt")),
                    t_opt_max=_safe_float(d.get("temp_max_opt")),
                    t_max=temp_max,
                    precip_min=_safe_float(d.get("rain_min_abs")),
                    precip_opt_min=_safe_float(d.get("rain_min_opt")),
                    precip_opt_max=_safe_float(d.get("rain_max_opt")),
                    precip_max=_safe_float(d.get("rain_max_abs")),
                    growing_cycle_days_min=cycle_min,
                    growing_cycle_days_max=cycle_max,
                )

            # Parse common names
            common_name_str = d.get("common_name", "")
            common_names: dict[str, list[str]] = {}
            if common_name_str:
                names = [n.strip() for n in common_name_str.replace(";", ",").split(",") if n.strip()]
                if names:
                    common_names["en"] = names

            # Altitude
            alt_min = _safe_float(d.get("alt_min"))
            alt_max = _safe_float(d.get("alt_max"))

            crop = Crop(
                source_name=DataSource.ECOCROP,
                source_record_id=record.record_id,
                scientific_name=sci_name,
                common_names=common_names,
                family=d.get("family", ""),
                edaphic_profile=edaphic or EdaphicProfile(),
                climatic_profile=climatic or ClimaticProfile(),
                altitude_min_m=alt_min,
                altitude_max_m=alt_max,
                raw_record=d,
            )
            entities.append(crop)

        self._log.info("ecocrop_transform_complete", entities=len(entities))
        return entities, []
