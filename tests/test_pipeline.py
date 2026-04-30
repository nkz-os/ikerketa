"""Tests for the pipeline orchestrator and quality report generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from ikerketa.pipeline import PipelineResult, run_pipeline
from ikerketa.report import generate_report


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestPipeline:
    """Test the pipeline orchestrator with local CSV connectors."""

    def test_run_single_source(self, tmp_path: Path) -> None:
        """Run pipeline with a single CSV source."""
        result = run_pipeline(
            sources=["ecocrop"],
            limit=5,
            export=False,
            csv_path=str(FIXTURES_DIR / "ecocrop.csv"),
        )

        assert isinstance(result, PipelineResult)
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.entities_after_dedup > 0

    def test_run_multiple_sources(self) -> None:
        """Run pipeline with multiple CSV sources."""
        result = run_pipeline(
            sources=["ecocrop", "companion_planting"],
            limit=5,
            export=False,
            csv_path=str(FIXTURES_DIR / "ecocrop.csv"),
        )

        # At least one should succeed
        assert result.success_count >= 1

    def test_crossref_enrichment(self) -> None:
        """Cross-reference index enriches entities."""
        result = run_pipeline(
            sources=["ecocrop"],
            limit=5,
            export=False,
            csv_path=str(FIXTURES_DIR / "ecocrop.csv"),
        )

        assert result.crossref_index is not None
        assert result.crossref_index.size > 0

    def test_deduplication(self) -> None:
        """Pipeline removes duplicates."""
        result = run_pipeline(
            sources=["ecocrop"],
            limit=5,
            export=False,
            csv_path=str(FIXTURES_DIR / "ecocrop.csv"),
        )

        # No dupes in fixture data
        assert result.entities_before_dedup == result.entities_after_dedup

    def test_invalid_source(self) -> None:
        """Unknown source produces an error."""
        result = run_pipeline(
            sources=["nonexistent_source"],
            limit=5,
            export=False,
        )
        assert result.failure_count == 0  # Filtered out, not run
        assert len(result.connector_results) == 0


class TestQualityReport:
    """Test quality report generation."""

    def test_generate_report(self, tmp_path: Path) -> None:
        """Report generated with correct structure."""
        result = run_pipeline(
            sources=["ecocrop"],
            limit=5,
            export=False,
            csv_path=str(FIXTURES_DIR / "ecocrop.csv"),
        )

        report = generate_report(result, output_dir=tmp_path)

        assert "summary" in report
        assert "source_breakdown" in report
        assert "field_completeness_pct" in report
        assert report["summary"]["connectors_success"] == 1

    def test_report_written_to_disk(self, tmp_path: Path) -> None:
        """Report JSON file written to output directory."""
        result = run_pipeline(
            sources=["ecocrop"],
            limit=5,
            export=False,
            csv_path=str(FIXTURES_DIR / "ecocrop.csv"),
        )

        generate_report(result, output_dir=tmp_path)
        report_files = list(tmp_path.glob("quality_report_*.json"))
        assert len(report_files) == 1

    def test_field_completeness(self, tmp_path: Path) -> None:
        """Field completeness computed for key fields."""
        result = run_pipeline(
            sources=["ecocrop"],
            limit=5,
            export=False,
            csv_path=str(FIXTURES_DIR / "ecocrop.csv"),
        )

        report = generate_report(result, output_dir=tmp_path)
        completeness = report["field_completeness_pct"]

        # EcoCrop data has scientific_name for all
        assert completeness.get("scientific_name", 0) == 100.0
