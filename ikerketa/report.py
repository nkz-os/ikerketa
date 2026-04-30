"""Quality report generator — data quality metrics and diagnostics.

Generates comprehensive quality reports for pipeline runs, covering:
  - Per-source statistics (entities, relationships, duration)
  - Cross-reference coverage
  - Deduplication metrics
  - Data completeness analysis
  - Validation summaries
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ikerketa.config import settings
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import ConnectorResult

_log = get_logger(__name__)


def _compute_completeness(entities: list) -> dict[str, float]:
    """Compute field completeness rates across entities."""
    if not entities:
        return {}

    # Key fields to check
    key_fields = [
        "scientific_name", "eppo_code", "agrovoc_uri", "usda_symbol",
        "common_names", "family", "genus",
    ]

    completeness: dict[str, float] = {}
    total = len(entities)

    for field_name in key_fields:
        filled = sum(
            1 for e in entities
            if getattr(e, field_name, None) not in (None, "", {}, [])
        )
        completeness[field_name] = round(filled / total * 100, 1)

    return completeness


def generate_report(pipeline_result: Any, output_dir: Path | None = None) -> dict[str, Any]:
    """Generate a comprehensive quality report from a pipeline run.

    Args:
        pipeline_result: PipelineResult from pipeline.run_pipeline().
        output_dir: Directory to write the report (default: data/reports/).

    Returns:
        Report as a dict (also written to disk as JSON).
    """
    if output_dir is None:
        output_dir = settings.data_reports_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    # Per-source breakdown
    source_stats: list[dict[str, Any]] = []
    for cr in pipeline_result.connector_results:
        stat: dict[str, Any] = {
            "source": cr.source_name.value,
            "entities": len(cr.entities),
            "relationships": len(cr.relationships),
            "duration_seconds": round(cr.duration_seconds, 2),
            "error": cr.error,
        }
        if cr.validation:
            stat["validation"] = {
                "total": cr.validation.total_records,
                "valid": cr.validation.valid_records,
                "invalid": cr.validation.invalid_records,
                "success_rate": round(cr.validation.success_rate * 100, 1),
            }
        source_stats.append(stat)

    # Data completeness across all deduped entities
    completeness = _compute_completeness(pipeline_result.deduped_entities)

    # Entity type distribution
    type_dist: dict[str, int] = {}
    for e in pipeline_result.deduped_entities:
        etype = type(e).__name__
        type_dist[etype] = type_dist.get(etype, 0) + 1

    # Source distribution among deduped entities
    source_dist: dict[str, int] = {}
    for e in pipeline_result.deduped_entities:
        src = e.source_name.value if hasattr(e.source_name, "value") else str(e.source_name)
        source_dist[src] = source_dist.get(src, 0) + 1

    report: dict[str, Any] = {
        "report_timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_version": "0.1.0",
        "summary": {
            "connectors_run": len(pipeline_result.connector_results),
            "connectors_success": pipeline_result.success_count,
            "connectors_failed": pipeline_result.failure_count,
            "total_duration_seconds": round(pipeline_result.total_duration_seconds, 2),
            "entities_before_dedup": pipeline_result.entities_before_dedup,
            "entities_after_dedup": pipeline_result.entities_after_dedup,
            "dedup_removed": pipeline_result.entities_before_dedup - pipeline_result.entities_after_dedup,
            "relationships_total": pipeline_result.relationships_total,
            "crossref_enriched": pipeline_result.crossref_matches,
        },
        "source_breakdown": source_stats,
        "entity_type_distribution": type_dist,
        "source_distribution": source_dist,
        "field_completeness_pct": completeness,
        "errors": pipeline_result.errors,
    }

    # Write report
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"quality_report_{timestamp}.json"

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    _log.info(
        "quality_report_generated",
        path=str(report_path),
        entities=pipeline_result.entities_after_dedup,
        sources=pipeline_result.success_count,
    )

    return report
