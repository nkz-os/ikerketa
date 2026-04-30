"""Tests for livestock, forestry, and agroforestry domain connectors."""

from __future__ import annotations

from pathlib import Path

import pytest

from ikerketa.models.base import DataSource

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ── Livestock Connectors ─────────────────────────────────────────────


class TestDADISConnector:
    """Tests for FAO DAD-IS breed connector."""

    def test_fetch_all(self) -> None:
        from ikerketa.connectors.dadis import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "dadis.csv"))
        assert len(records) == 5

    def test_transform_breeds(self) -> None:
        from ikerketa.connectors.dadis import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "dadis.csv"))
            entities, rels = conn.transform(records)
        assert len(entities) == 5
        assert all(e.source_name == DataSource.DADIS for e in entities)

    def test_conservation_status(self) -> None:
        from ikerketa.connectors.dadis import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "dadis.csv"))
            entities, _ = conn.transform(records)
        latxa = next(e for e in entities if "Latxa" in e.breed_name)
        assert latxa.conservation_status.value == "vulnerable"

    def test_full_pipeline(self) -> None:
        from ikerketa.connectors.dadis import Connector
        with Connector() as conn:
            result = conn.run(csv_path=str(FIXTURES_DIR / "dadis.csv"))
        assert result.error is None
        assert len(result.entities) == 5


class TestWAHISConnector:
    """Tests for WOAH/WAHIS animal disease connector."""

    def test_fetch_all(self) -> None:
        from ikerketa.connectors.wahis import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "wahis.csv"))
        assert len(records) == 5

    def test_transform_diseases(self) -> None:
        from ikerketa.connectors.wahis import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "wahis.csv"))
            entities, _ = conn.transform(records)
        assert len(entities) == 5
        # All are WOAH-listed
        assert all(e.woah_listed for e in entities)

    def test_zoonotic_flag(self) -> None:
        from ikerketa.connectors.wahis import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "wahis.csv"))
            entities, _ = conn.transform(records)
        fmd = next(e for e in entities if "Foot-and-mouth" in e.disease_name)
        assert fmd.zoonotic is False
        brucella = next(e for e in entities if "Brucellosis" in e.disease_name)
        assert brucella.zoonotic is True

    def test_full_pipeline(self) -> None:
        from ikerketa.connectors.wahis import Connector
        with Connector() as conn:
            result = conn.run(csv_path=str(FIXTURES_DIR / "wahis.csv"))
        assert result.error is None


class TestFeedipediaConnector:
    """Tests for Feedipedia connector."""

    def test_fetch_all(self) -> None:
        from ikerketa.connectors.feedipedia import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "feedipedia.csv"))
        assert len(records) == 5

    def test_nutritional_values(self) -> None:
        from ikerketa.connectors.feedipedia import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "feedipedia.csv"))
            entities, _ = conn.transform(records)
        alfalfa = next(e for e in entities if "Alfalfa" in e.feed_name)
        assert alfalfa.crude_protein_pct == pytest.approx(17.2)
        assert alfalfa.organic_compatible is True

    def test_acorn_for_pigs(self) -> None:
        from ikerketa.connectors.feedipedia import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "feedipedia.csv"))
            entities, _ = conn.transform(records)
        acorn = next(e for e in entities if "Acorn" in e.feed_name)
        assert "porcine" in acorn.suitable_species
        assert "Tannins" in acorn.toxicity_notes

    def test_full_pipeline(self) -> None:
        from ikerketa.connectors.feedipedia import Connector
        with Connector() as conn:
            result = conn.run(csv_path=str(FIXTURES_DIR / "feedipedia.csv"))
        assert result.error is None


# ── Forestry Connectors ──────────────────────────────────────────────


class TestGlobalTreeSearchConnector:
    """Tests for GlobalTreeSearch connector."""

    def test_fetch_all(self) -> None:
        from ikerketa.connectors.globaltreesearch import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "globaltreesearch.csv"))
        assert len(records) == 5

    def test_tree_species(self) -> None:
        from ikerketa.connectors.globaltreesearch import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "globaltreesearch.csv"))
            entities, _ = conn.transform(records)
        encina = next(e for e in entities if "Quercus ilex" in e.scientific_name)
        assert encina.iucn_status.value == "LC"
        assert encina.wood_density_kg_m3 == 900
        assert encina.nitrogen_fixing is False
        assert encina.deciduous is False

    def test_nitrogen_fixer(self) -> None:
        from ikerketa.connectors.globaltreesearch import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "globaltreesearch.csv"))
            entities, _ = conn.transform(records)
        robinia = next(e for e in entities if "Robinia" in e.scientific_name)
        assert robinia.nitrogen_fixing is True

    def test_full_pipeline(self) -> None:
        from ikerketa.connectors.globaltreesearch import Connector
        with Connector() as conn:
            result = conn.run(csv_path=str(FIXTURES_DIR / "globaltreesearch.csv"))
        assert result.error is None


# ── Agroforestry Connectors ──────────────────────────────────────────


class TestAgroforestreeConnector:
    """Tests for ICRAF Agroforestree connector."""

    def test_fetch_all(self) -> None:
        from ikerketa.connectors.agroforestree import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "agroforestree.csv"))
        assert len(records) == 5

    def test_nitrogen_fixers(self) -> None:
        from ikerketa.connectors.agroforestree import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "agroforestree.csv"))
            entities, _ = conn.transform(records)
        n_fixers = [e for e in entities if e.nitrogen_fixing]
        assert len(n_fixers) >= 4  # Most ICRAF species are N-fixers

    def test_full_pipeline(self) -> None:
        from ikerketa.connectors.agroforestree import Connector
        with Connector() as conn:
            result = conn.run(csv_path=str(FIXTURES_DIR / "agroforestree.csv"))
        assert result.error is None


class TestForagesConnector:
    """Tests for CIAT/ILRI Tropical Forages connector."""

    def test_fetch_all(self) -> None:
        from ikerketa.connectors.forages import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "forages.csv"))
        assert len(records) == 5

    def test_crude_protein(self) -> None:
        from ikerketa.connectors.forages import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "forages.csv"))
            entities, _ = conn.transform(records)
        stylo = next(e for e in entities if "Stylo" in e.feed_name)
        assert stylo.crude_protein_pct == pytest.approx(16.0)
        assert stylo.organic_compatible is True

    def test_full_pipeline(self) -> None:
        from ikerketa.connectors.forages import Connector
        with Connector() as conn:
            result = conn.run(csv_path=str(FIXTURES_DIR / "forages.csv"))
        assert result.error is None


class TestGlobAllomeTreeConnector:
    """Tests for GlobAllomeTree connector."""

    def test_fetch_all(self) -> None:
        from ikerketa.connectors.globallometree import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "globallometree.csv"))
        assert len(records) == 5

    def test_equation_coefficients(self) -> None:
        from ikerketa.connectors.globallometree import Connector
        with Connector() as conn:
            records = conn.fetch(csv_path=str(FIXTURES_DIR / "globallometree.csv"))
            entities, _ = conn.transform(records)
        encina_eq = next(e for e in entities if "Quercus ilex" in e.species_name)
        assert encina_eq.r_squared == pytest.approx(0.94)
        assert "a" in encina_eq.coefficients
        assert encina_eq.coefficients["a"] == pytest.approx(0.0284)

    def test_full_pipeline(self) -> None:
        from ikerketa.connectors.globallometree import Connector
        with Connector() as conn:
            result = conn.run(csv_path=str(FIXTURES_DIR / "globallometree.csv"))
        assert result.error is None


# ── Inter-domain Relationship Models ─────────────────────────────────


class TestInterDomainRelationships:
    """Test inter-domain relationship models."""

    def test_fodder_suitability(self) -> None:
        from ikerketa.models.relationship import FodderSuitability, Palatability, Season
        rel = FodderSuitability(
            source_name=DataSource.FEEDIPEDIA,
            relationship_type="FODDER_FOR",
            source_agrovoc_uri="http://aims.fao.org/aos/agrovoc/c_6254",  # Quercus ilex
            target_agrovoc_uri="http://aims.fao.org/aos/agrovoc/c_7266",  # Sus domesticus
            palatability=Palatability.HIGH,
            season=Season.AUTUMN,
            plant_part="fruit",
            livestock_species="porcine",
        )
        assert rel.relationship_type == "FODDER_FOR"
        assert rel.palatability == Palatability.HIGH
        assert rel.season == Season.AUTUMN

    def test_agroforestry_association(self) -> None:
        from ikerketa.models.relationship import (
            AgroforestryAssociation,
            AgroforestryCompatibility,
            LightInteraction,
        )
        rel = AgroforestryAssociation(
            source_name=DataSource.AGROFORESTREE,
            relationship_type="AGROFORESTRY_COMPATIBLE",
            source_agrovoc_uri="http://aims.fao.org/aos/agrovoc/c_4060",  # Juglans regia
            target_agrovoc_uri="http://aims.fao.org/aos/agrovoc/c_7832",  # Trifolium repens
            compatibility=AgroforestryCompatibility.SYNERGISTIC,
            light_interaction=LightInteraction.SHADE_TOLERANT,
            nitrogen_fixation=True,
        )
        assert rel.compatibility == AgroforestryCompatibility.SYNERGISTIC
        assert rel.nitrogen_fixation is True
