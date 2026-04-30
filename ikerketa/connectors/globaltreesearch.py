"""GlobalTreeSearch connector — BGCI world tree species database.

Reads tree species data from local DwC-A/CSV.
Produces TreeSpecies entities with IUCN status and ecosystem services.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource, RawRecord
from ikerketa.models.forestry import EcosystemService, GrowthRate, IUCNStatus, TreeSpecies

_log = get_logger(__name__)


def _float_or_none(val: str) -> float | None:
    try:
        return float(val) if val.strip() else None
    except ValueError:
        return None


class Connector(AbstractConnector):
    """GlobalTreeSearch connector (DwC-A / CSV local)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.GLOBALTREESEARCH

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", "data/raw/globaltreesearch.csv"))
        if not csv_path.exists():
            raise ConnectorError(f"GlobalTreeSearch CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.GLOBALTREESEARCH,
                    record_id=row.get("scientific_name", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data

            # Parse IUCN status
            iucn_val = d.get("iucn_status", "NE")
            try:
                iucn = IUCNStatus(iucn_val)
            except ValueError:
                iucn = IUCNStatus.NOT_EVALUATED

            # Parse growth rate
            growth_val = d.get("growth_rate", "")
            try:
                growth = GrowthRate(growth_val) if growth_val else None
            except ValueError:
                growth = None

            # Parse ecosystem services
            services_raw = d.get("ecosystem_services", "")
            services = []
            for s in services_raw.split(";"):
                s = s.strip()
                try:
                    services.append(EcosystemService(s))
                except ValueError:
                    pass

            # Parse native range
            native_range = [c.strip() for c in d.get("native_range", "").split(";") if c.strip()]

            # Common names
            common_names: dict[str, str] = {}
            if d.get("common_name_en"):
                common_names["en"] = d["common_name_en"]
            if d.get("common_name_es"):
                common_names["es"] = d["common_name_es"]

            # Deciduous
            dec_val = d.get("deciduous", "")
            deciduous = None
            if dec_val.lower() == "true":
                deciduous = True
            elif dec_val.lower() == "false":
                deciduous = False

            tree = TreeSpecies(
                source_name=DataSource.GLOBALTREESEARCH,
                source_record_id=d.get("scientific_name", ""),
                scientific_name=d.get("scientific_name", ""),
                common_names=common_names,
                family=d.get("family", ""),
                native_range=native_range,
                iucn_status=iucn,
                wood_density_kg_m3=_float_or_none(d.get("wood_density_kg_m3", "")),
                growth_rate=growth,
                max_height_m=_float_or_none(d.get("max_height_m", "")),
                nitrogen_fixing=d.get("nitrogen_fixing", "false").lower() == "true",
                ecosystem_services=services,
                deciduous=deciduous,
                raw_record=d,
            )
            entities.append(tree)

        self._log.info("globaltreesearch_transform_complete", entities=len(entities))
        return entities, []
