"""Pipeline orchestrator — runs all connectors, cross-references, deduplicates, exports.

Orchestrates the full IkerKeta ETL pipeline:
  1. Discover and instantiate connectors
  2. Run each connector (fetch → transform → validate)
  3. Build cross-reference index from all results
  4. Deduplicate across sources
  5. Export to JSON-LD and Parquet
  6. Generate quality report
"""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ikerketa.config import load_sources_config, settings
from ikerketa.connectors.base import AbstractConnector
from ikerketa.export.jsonld import export_connector_result as export_jsonld
from ikerketa.export.parquet import export_to_parquet
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import (
    BaseEntity,
    BaseRelationship,
    ConnectorResult,
    DataSource,
)
from ikerketa.transform.crossref import CrossReferenceIndex, IdentifierRecord
from ikerketa.transform.dedup import dedup_by_hash, dedup_by_key, dedup_by_name_fuzzy

_log = get_logger(__name__)


@dataclass
class PipelineResult:
    """Aggregated result from a full pipeline run."""

    connector_results: list[ConnectorResult] = field(default_factory=list)
    all_entities: list[BaseEntity] = field(default_factory=list)
    all_relationships: list[BaseRelationship] = field(default_factory=list)
    deduped_entities: list[BaseEntity] = field(default_factory=list)
    crossref_index: CrossReferenceIndex | None = None
    total_duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    # Stats
    entities_before_dedup: int = 0
    entities_after_dedup: int = 0
    relationships_total: int = 0
    crossref_matches: int = 0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.connector_results if r.error is None)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.connector_results if r.error is not None)


# Mapping from source YAML keys to connector module names
_CONNECTOR_MODULES: dict[str, str] = {
    "agrovoc": "agrovoc",
    "eppo": "eppo",
    "ecocrop": "ecocrop",
    "usda_plants": "usda_plants",
    "uspest": "uspest",
    "companion_planting": "companion_planting",
    "dg_sante": "dg_sante",
    "cabi": "cabi",
    "agroportal": "agroportal",
    "fibl": "fibl",
    # Livestock
    "dadis": "dadis",
    "wahis": "wahis",
    "feedipedia": "feedipedia",
    # Forestry
    "globaltreesearch": "globaltreesearch",
    "euforgen": "euforgen",
    "iucn": "iucn_trees",
    # Agroforestry
    "agroforestree": "agroforestree",
    "forages": "forages",
    "globallometree": "globallometree",
}


def _load_connector(source_key: str) -> AbstractConnector | None:
    """Dynamically import and instantiate a connector."""
    module_name = _CONNECTOR_MODULES.get(source_key, source_key)
    try:
        module = importlib.import_module(f"ikerketa.connectors.{module_name}")
        connector_cls = getattr(module, "Connector", None)
        if connector_cls is None:
            _log.warning("no_connector_class", source=source_key)
            return None
        return connector_cls()
    except ImportError as exc:
        _log.warning("connector_import_failed", source=source_key, error=str(exc))
        return None


def _build_crossref_index(entities: list[BaseEntity]) -> tuple[CrossReferenceIndex, int]:
    """Build a cross-reference index from all entities.

    Returns the index and count of entities that were enriched with
    identifiers from other sources.
    """
    index = CrossReferenceIndex()
    enriched = 0

    # First pass: add all entities to the index
    for entity in entities:
        sci_name = getattr(entity, "scientific_name", "")
        record = IdentifierRecord(
            scientific_name=sci_name or "",
            agrovoc_uri=entity.agrovoc_uri,
            eppo_code=entity.eppo_code,
            usda_symbol=entity.usda_symbol,
        )
        index.add_record(record)

    # Second pass: try to enrich entities with missing identifiers
    for entity in entities:
        sci_name = getattr(entity, "scientific_name", "")
        resolved = index.resolve(
            eppo_code=entity.eppo_code,
            agrovoc_uri=entity.agrovoc_uri,
            usda_symbol=entity.usda_symbol,
            scientific_name=sci_name or None,
        )
        if resolved:
            updated = False
            if not entity.eppo_code and resolved.eppo_code:
                entity.eppo_code = resolved.eppo_code
                updated = True
            if not entity.agrovoc_uri and resolved.agrovoc_uri:
                entity.agrovoc_uri = resolved.agrovoc_uri
                updated = True
            if not entity.usda_symbol and resolved.usda_symbol:
                entity.usda_symbol = resolved.usda_symbol
                updated = True
            if updated:
                enriched += 1

    _log.info(
        "crossref_complete",
        index_size=index.size,
        entities_enriched=enriched,
    )
    return index, enriched


def run_pipeline(
    *,
    sources: list[str] | None = None,
    limit: int | None = None,
    export: bool = True,
    **connector_params: Any,
) -> PipelineResult:
    """Run the full IkerKeta pipeline.

    Args:
        sources: List of source keys to run (None = all enabled).
        limit: Maximum records per connector.
        export: Whether to export results to JSON-LD + Parquet.
        **connector_params: Additional params passed to each connector.

    Returns:
        PipelineResult with aggregated statistics.
    """
    start_time = time.monotonic()
    result = PipelineResult()

    # Load source configuration
    config = load_sources_config()
    source_configs = config.get("sources", {})

    # Determine which sources to run
    if sources:
        run_sources = [s for s in sources if s in source_configs]
    else:
        run_sources = [
            key for key, cfg in source_configs.items()
            if cfg.get("enabled", True)
        ]

    _log.info("pipeline_start", sources=run_sources, limit=limit)

    # Phase 1: Run each connector
    for source_key in run_sources:
        _log.info("connector_run_start", source=source_key)

        connector = _load_connector(source_key)
        if connector is None:
            result.errors.append(f"Failed to load connector: {source_key}")
            continue

        try:
            with connector:
                conn_result = connector.run(limit=limit, **connector_params)

            result.connector_results.append(conn_result)

            if conn_result.error:
                result.errors.append(f"{source_key}: {conn_result.error}")
                _log.warning("connector_error", source=source_key, error=conn_result.error)
            else:
                result.all_entities.extend(conn_result.entities)
                result.all_relationships.extend(conn_result.relationships)
                _log.info(
                    "connector_done",
                    source=source_key,
                    entities=len(conn_result.entities),
                    relationships=len(conn_result.relationships),
                )

        except Exception as exc:
            error_msg = f"{source_key}: {exc}"
            result.errors.append(error_msg)
            _log.error("connector_crash", source=source_key, error=str(exc))

    result.entities_before_dedup = len(result.all_entities)

    # Phase 2: Cross-reference
    if result.all_entities:
        index, enriched = _build_crossref_index(result.all_entities)
        result.crossref_index = index
        result.crossref_matches = enriched

    # Phase 3: Deduplicate
    if result.all_entities:
        # Compute hashes first
        for entity in result.all_entities:
            entity.compute_hash()

        deduped = dedup_by_hash(result.all_entities)
        deduped = dedup_by_key(deduped)
        deduped = dedup_by_name_fuzzy(deduped)
        result.deduped_entities = deduped
    else:
        result.deduped_entities = []

    result.entities_after_dedup = len(result.deduped_entities)
    result.relationships_total = len(result.all_relationships)

    # Phase 4: Export
    if export and result.deduped_entities:
        output_dir = settings.data_processed_dir

        # Create a combined ConnectorResult for export
        combined = ConnectorResult(
            source_name=DataSource.AGROVOC,  # placeholder
            entities=result.deduped_entities,
            relationships=result.all_relationships,
            duration_seconds=time.monotonic() - start_time,
        )

        # Export per source for granular output
        for conn_result in result.connector_results:
            if not conn_result.error and conn_result.entities:
                try:
                    export_jsonld(conn_result, output_dir)
                    export_to_parquet(conn_result, output_dir)
                except Exception as exc:
                    _log.warning("export_error", source=conn_result.source_name.value, error=str(exc))

    result.total_duration_seconds = time.monotonic() - start_time

    _log.info(
        "pipeline_complete",
        duration=f"{result.total_duration_seconds:.2f}s",
        sources_run=len(result.connector_results),
        success=result.success_count,
        failures=result.failure_count,
        entities_before_dedup=result.entities_before_dedup,
        entities_after_dedup=result.entities_after_dedup,
        relationships=result.relationships_total,
        crossref_matches=result.crossref_matches,
    )

    return result
