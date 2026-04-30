"""Parquet export — columnar format for analytics and validation.

Exports entities to Apache Parquet via PyArrow for fast analytical
queries with pandas or DuckDB.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, ConnectorResult

_log = get_logger(__name__)


def entities_to_dataframe(entities: list[BaseEntity]) -> pd.DataFrame:
    """Convert entities to a flat pandas DataFrame.

    Nested structures (profiles, lists, dicts) are serialized as JSON strings
    in individual columns to avoid PyArrow struct inference issues.

    Args:
        entities: List of entities to convert.

    Returns:
        pandas DataFrame with one row per entity.
    """
    import json

    records: list[dict[str, Any]] = []

    for entity in entities:
        row = entity.model_dump(mode="json", exclude={"raw_record"})
        row["entity_type"] = type(entity).__name__

        # Flatten nested dicts/lists to JSON strings for Parquet compatibility
        for key, value in list(row.items()):
            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value, ensure_ascii=False, default=str) if value else None

        records.append(row)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(records)

    _log.debug("dataframe_created", rows=len(df), columns=len(df.columns))
    return df


def export_to_parquet(result: ConnectorResult, output_dir: Path) -> Path | None:
    """Export a ConnectorResult to a Parquet file.

    Args:
        result: The connector result to export.
        output_dir: Directory to write the output file.

    Returns:
        Path to the written file, or None if no entities.
    """
    if not result.entities:
        _log.warning("no_entities_to_export", source=result.source_name.value)
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{result.source_name.value}_entities.parquet"
    output_path = output_dir / filename

    df = entities_to_dataframe(result.entities)
    df.to_parquet(output_path, engine="pyarrow", index=False)

    _log.info(
        "parquet_exported",
        path=str(output_path),
        rows=len(df),
        size_bytes=output_path.stat().st_size,
    )
    return output_path
