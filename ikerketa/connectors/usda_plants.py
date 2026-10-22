"""USDA PLANTS connector — local CSV parser for USDA Complete PLANTS Checklist.

The USDA PLANTS database contains 100k+ plant species with taxonomy,
common names, symbols, and family information.

Download instructions:
  1. Visit https://plants.usda.gov/home/plantProfile (search → export)
     or download the Complete PLANTS Checklist from USDA directly
  2. Save as data/raw/plantlst.txt (or .csv)

Expected columns (USDA PLANTS Checklist format):
  "Symbol","Synonym Symbol","Scientific Name with Author","National Common Name","Family"
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
from ikerketa.models.taxonomy import Taxon, TaxonSynonym
from ikerketa.transform.normalizer import normalize_scientific_name

_log = get_logger(__name__)

DEFAULT_FILE_PATH = "data/raw/plantlst.txt"


class Connector(AbstractConnector):
    """USDA Complete PLANTS Checklist connector.

    Parses the locally downloaded USDA checklist file (CSV/TXT)
    into Taxon entities with USDA symbols and common names.
    """

    @property
    def source_name(self) -> DataSource:
        return DataSource.USDA_PLANTS

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Read USDA PLANTS checklist from local file.

        Args:
            limit: Maximum rows to read.
            **params:
                file_path: Override file path (default: data/raw/plantlst.txt)

        Returns:
            List of RawRecord.
        """
        file_path_str = params.get("file_path", DEFAULT_FILE_PATH)
        file_path = Path(file_path_str)

        if not file_path.is_absolute():
            file_path = settings.data_raw_dir.parent.parent / file_path_str

        if not file_path.exists():
            raise ConnectorError(
                f"USDA PLANTS file not found at {file_path}. "
                "Download the Complete PLANTS Checklist from "
                "https://plants.usda.gov and place in data/raw/plantlst.txt"
            )

        self._log.info("usda_plants_fetch_start", path=str(file_path))
        records: list[RawRecord] = []

        with file_path.open("r", encoding="utf-8", errors="replace") as f:
            # USDA file uses comma delimiter with double-quote enclosure
            reader = csv.DictReader(f)

            if not reader.fieldnames:
                raise ConnectorError("USDA PLANTS file has no header row")

            # Normalize field names to lowercase
            field_map = {col: col.strip().lower().replace(" ", "_") for col in reader.fieldnames}

            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break

                normalized: dict[str, str] = {}
                for orig_col, value in row.items():
                    key = field_map.get(orig_col, orig_col.strip().lower())
                    normalized[key] = value.strip() if value else ""

                # Extract USDA symbol as record ID
                symbol = normalized.get("symbol", "")
                if not symbol:
                    continue

                records.append(RawRecord(
                    source_name=DataSource.USDA_PLANTS,
                    record_id=symbol,
                    data=normalized,
                ))

        self._log.info("usda_plants_fetch_complete", total_records=len(records))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform USDA PLANTS rows into Taxon entities."""
        entities: list[BaseEntity] = []

        for record in raw_records:
            d = record.data
            symbol = d.get("symbol", "")
            synonym_symbol = d.get("synonym_symbol", "")
            sci_name_raw = d.get("scientific_name_with_author", "")
            common_name = d.get("national_common_name", "")
            family = d.get("family", "")

            # Clean scientific name (strip author citation)
            sci_name = normalize_scientific_name(sci_name_raw) if sci_name_raw else ""

            if not sci_name:
                continue

            # Build common names dict
            common_names: dict[str, list[str]] = {}
            if common_name:
                common_names["en"] = [common_name]

            # Build synonyms list
            synonyms: list[TaxonSynonym] = []
            if synonym_symbol:
                synonyms.append(TaxonSynonym(
                    synonym_name=synonym_symbol,
                    synonym_type="usda_symbol",
                ))

            # Extract genus from scientific name
            parts = sci_name.split()
            genus = parts[0] if parts else ""

            taxon = Taxon(
                source_name=DataSource.USDA_PLANTS,
                source_record_id=symbol,
                usda_symbol=symbol,
                scientific_name=sci_name,
                common_names=common_names,
                family=family,
                genus=genus,
                kingdom="Plantae",
                synonyms=synonyms,
                raw_record=d,
            )
            entities.append(taxon)

        self._log.info("usda_plants_transform_complete", entities=len(entities))
        return entities, []
