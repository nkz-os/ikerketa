"""GlobAllomeTree connector — FAO/CIRAD allometric equations database.

Reads allometric equations for biomass/carbon estimation from local CSV.
Pending: REST API integration via globallometree.org Swagger endpoint.
Produces AllometricEquation entities for carbon sequestration calculations.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource, RawRecord
from ikerketa.models.forestry import AllometricEquation, DependentVariable

_log = get_logger(__name__)

# Fixture path for local CSV (API integration pending)
DEFAULT_CSV = "data/raw/globallometree.csv"


def _float_or_none(val: str) -> float | None:
    try:
        return float(val) if val.strip() else None
    except ValueError:
        return None


class Connector(AbstractConnector):
    """GlobAllomeTree connector (CSV local, REST API pending)."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.GLOBALLOMETREE

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        csv_path = Path(params.get("csv_path", DEFAULT_CSV))
        if not csv_path.exists():
            raise ConnectorError(f"GlobAllomeTree CSV not found: {csv_path}")

        records: list[RawRecord] = []
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                records.append(RawRecord(
                    source_name=DataSource.GLOBALLOMETREE,
                    record_id=row.get("equation_id", str(i)),
                    data=dict(row),
                ))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        entities: list[BaseEntity] = []
        for record in raw_records:
            d = record.data

            # Parse dependent variable
            dep_val = d.get("dependent_var", "biomass").lower()
            try:
                dep_var = DependentVariable(dep_val)
            except ValueError:
                dep_var = DependentVariable.BIOMASS

            # Parse independent variables
            indep_raw = d.get("independent_vars", "")
            indep_vars = [v.strip() for v in indep_raw.split(";") if v.strip()]

            # Parse coefficients from JSON string or semicolon-separated
            coeff_raw = d.get("coefficients", "{}")
            try:
                coefficients = json.loads(coeff_raw)
            except (json.JSONDecodeError, TypeError):
                coefficients = {}

            eq = AllometricEquation(
                source_name=DataSource.GLOBALLOMETREE,
                source_record_id=d.get("equation_id", ""),
                equation_id=d.get("equation_id", ""),
                species_name=d.get("species_name", ""),
                equation_form=d.get("equation_form", ""),
                dependent_var=dep_var,
                independent_vars=indep_vars,
                coefficients=coefficients,
                r_squared=_float_or_none(d.get("r_squared", "")),
                sample_size=int(d["sample_size"]) if d.get("sample_size", "").isdigit() else None,
                climate_zone=d.get("climate_zone", ""),
                country=d.get("country", ""),
                raw_record=d,
            )
            entities.append(eq)

        self._log.info("globallometree_transform_complete", entities=len(entities))
        return entities, []
