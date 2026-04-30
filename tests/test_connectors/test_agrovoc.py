"""Integration tests for AGROVOC connector — live SPARQL queries.

These tests hit the real AGROVOC SPARQL endpoint.
They are marked slow and will be skipped in CI unless explicitly enabled.
"""

from __future__ import annotations

import pytest

from ikerketa.connectors.agrovoc import Connector, ROOT_CONCEPTS, AGROVOC_BASE
from ikerketa.models.base import DataSource
from ikerketa.models.ontology import OntologyConcept


@pytest.fixture
def agrovoc_connector() -> Connector:
    return Connector()


class TestAgrovocConnector:
    """Integration tests hitting the real AGROVOC SPARQL endpoint."""

    @pytest.mark.slow
    def test_fetch_plants_small(self, agrovoc_connector: Connector) -> None:
        """Fetch a small batch of concepts from the plants subtree."""
        records = agrovoc_connector.fetch(limit=5, roots=["c_5993"], page_size=5)

        assert len(records) > 0
        assert len(records) <= 5

        for record in records:
            assert record.source_name == DataSource.AGROVOC
            assert record.record_id.startswith("http://aims.fao.org/aos/agrovoc/")
            assert "pref_labels" in record.data
            assert isinstance(record.data["pref_labels"], dict)

    @pytest.mark.slow
    def test_fetch_and_transform(self, agrovoc_connector: Connector) -> None:
        """Fetch and transform a small batch → OntologyConcept entities."""
        records = agrovoc_connector.fetch(limit=3, roots=["c_5993"], page_size=3)
        entities, relationships = agrovoc_connector.transform(records)

        assert len(entities) > 0
        for entity in entities:
            assert isinstance(entity, OntologyConcept)
            assert entity.source_name == DataSource.AGROVOC
            assert entity.agrovoc_uri is not None
            assert entity.concept_uri.startswith("http://")
            assert entity.ontology_prefix == "AGROVOC"
            assert len(entity.pref_labels) > 0

    @pytest.mark.slow
    def test_multilingual_labels(self, agrovoc_connector: Connector) -> None:
        """Verify that concepts have labels in multiple languages."""
        records = agrovoc_connector.fetch(limit=10, roots=["c_5993"], page_size=10)

        has_multilingual = False
        for record in records:
            pref_labels = record.data.get("pref_labels", {})
            if len(pref_labels) > 1:
                has_multilingual = True
                break

        assert has_multilingual, "No concept had labels in more than 1 language"

    @pytest.mark.slow
    def test_full_pipeline_run(self, agrovoc_connector: Connector) -> None:
        """Run the full pipeline: fetch → transform → validate."""
        result = agrovoc_connector.run(limit=5, roots=["c_5993"], page_size=5)

        assert result.source_name == DataSource.AGROVOC
        assert result.error is None
        assert len(result.entities) > 0
        assert result.duration_seconds > 0
        assert result.validation is not None
