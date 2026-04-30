"""Integration tests for EPPO v2 connector — live API calls.

These tests hit the real EPPO API and require EPPO_API_TOKEN to be set.
They are marked slow and will be skipped in CI unless explicitly enabled.
"""

from __future__ import annotations

import pytest

from ikerketa.config import settings
from ikerketa.connectors.eppo import Connector
from ikerketa.models.base import DataSource
from ikerketa.models.pest import Pest
from ikerketa.models.taxonomy import Taxon


@pytest.fixture
def eppo_connector() -> Connector:
    if not settings.eppo_api_token:
        pytest.skip("EPPO_API_TOKEN not set")
    return Connector()


class TestEppoConnector:
    """Integration tests hitting the real EPPO v2 API."""

    @pytest.mark.slow
    def test_fetch_small_batch(self, eppo_connector: Connector) -> None:
        """Fetch a small batch of EPPO codes."""
        records = eppo_connector.fetch(limit=3, enrich=False)

        assert len(records) > 0
        assert len(records) <= 3

        for record in records:
            assert record.source_name == DataSource.EPPO
            assert "eppocode" in record.data
            assert "datatype" in record.data
            assert len(record.data["eppocode"]) >= 4

    @pytest.mark.slow
    def test_fetch_with_enrichment(self, eppo_connector: Connector) -> None:
        """Fetch a single taxon with full enrichment."""
        records = eppo_connector.fetch(limit=1, enrich=True)

        assert len(records) == 1
        record = records[0]

        # Should have enrichment data
        assert "overview" in record.data
        assert "names" in record.data
        assert "taxonomy" in record.data

    @pytest.mark.slow
    def test_fetch_and_transform(self, eppo_connector: Connector) -> None:
        """Fetch and transform into domain entities."""
        records = eppo_connector.fetch(limit=3, enrich=True)
        entities, relationships = eppo_connector.transform(records)

        assert len(entities) > 0
        for entity in entities:
            assert isinstance(entity, (Taxon, Pest))
            assert entity.source_name == DataSource.EPPO
            assert entity.eppo_code is not None
            assert len(entity.eppo_code) >= 4

    @pytest.mark.slow
    def test_fetch_plants_only(self, eppo_connector: Connector) -> None:
        """Fetch only plant-type organisms."""
        records = eppo_connector.fetch(limit=3, enrich=True, datatypes=["PFL"])

        for record in records:
            assert record.data.get("datatype") == "PFL"

        entities, _ = eppo_connector.transform(records)
        for entity in entities:
            assert isinstance(entity, Taxon)

    @pytest.mark.slow
    def test_full_pipeline_run(self, eppo_connector: Connector) -> None:
        """Run the full pipeline: fetch → transform → validate."""
        result = eppo_connector.run(limit=2, enrich=True)

        assert result.source_name == DataSource.EPPO
        assert result.error is None
        assert len(result.entities) > 0
        assert result.duration_seconds > 0
        assert result.validation is not None
