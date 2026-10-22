"""Tests for EcoCrop, USDA PLANTS, and USPEST CSV connectors.

Uses real agronomic data fixtures in tests/fixtures/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ikerketa.connectors.ecocrop import Connector as EcoCropConnector
from ikerketa.connectors.usda_plants import Connector as USDAConnector
from ikerketa.connectors.uspest import Connector as USPESTConnector
from ikerketa.models.base import DataSource
from ikerketa.models.crop import Crop
from ikerketa.models.pest import Pest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ── EcoCrop Tests ────────────────────────────────────────────────────


class TestEcoCropConnector:
    """Tests for EcoCrop local CSV connector."""

    def test_fetch_all(self) -> None:
        """Fetch all rows from fixture CSV."""
        conn = EcoCropConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "ecocrop.csv"))
        assert len(records) == 5

    def test_fetch_with_limit(self) -> None:
        """Fetch with limit."""
        conn = EcoCropConnector()
        records = conn.fetch(limit=2, csv_path=str(FIXTURES_DIR / "ecocrop.csv"))
        assert len(records) == 2

    def test_transform_crop_entities(self) -> None:
        """Transform produces Crop entities with profiles."""
        conn = EcoCropConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "ecocrop.csv"))
        entities, rels = conn.transform(records)

        assert len(entities) == 5
        assert all(isinstance(e, Crop) for e in entities)
        assert len(rels) == 0

    def test_potato_edaphic_profile(self) -> None:
        """Potato edaphic profile has correct pH range."""
        conn = EcoCropConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "ecocrop.csv"))
        entities, _ = conn.transform(records)

        potato = next(e for e in entities if "tuberosum" in e.scientific_name)
        assert isinstance(potato, Crop)
        assert potato.edaphic_profile.ph_min == 4.5
        assert potato.edaphic_profile.ph_max == 8.0
        assert potato.family == "Solanaceae"

    def test_potato_climatic_profile(self) -> None:
        """Potato climatic profile has real temperature and rainfall bounds."""
        conn = EcoCropConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "ecocrop.csv"))
        entities, _ = conn.transform(records)

        potato = next(e for e in entities if "tuberosum" in e.scientific_name)
        assert isinstance(potato, Crop)
        assert potato.climatic_profile.t_kill == -2.0
        assert potato.climatic_profile.t_max == 30.0
        assert potato.climatic_profile.precip_min == 250.0
        assert potato.climatic_profile.growing_cycle_days_min == 90
        assert potato.climatic_profile.growing_cycle_days_max == 160

    def test_full_pipeline(self) -> None:
        """Full pipeline run."""
        conn = EcoCropConnector()
        result = conn.run(csv_path=str(FIXTURES_DIR / "ecocrop.csv"))
        assert result.error is None
        assert len(result.entities) == 5
        assert result.source_name == DataSource.ECOCROP

    def test_missing_file_error(self) -> None:
        """ConnectorError when CSV not found."""
        from ikerketa.connectors.base import ConnectorError

        conn = EcoCropConnector()
        with pytest.raises(ConnectorError, match="not found"):
            conn.fetch(csv_path="/nonexistent/ecocrop.csv")


# ── USDA PLANTS Tests ───────────────────────────────────────────────


class TestUSDAConnector:
    """Tests for USDA PLANTS checklist connector."""

    def test_fetch_all(self) -> None:
        """Fetch all rows from fixture."""
        conn = USDAConnector()
        records = conn.fetch(file_path=str(FIXTURES_DIR / "plantlst.txt"))
        assert len(records) == 7

    def test_usda_symbol_as_key(self) -> None:
        """USDA symbol used as record_id and entity key."""
        conn = USDAConnector()
        records = conn.fetch(file_path=str(FIXTURES_DIR / "plantlst.txt"))
        entities, _ = conn.transform(records)

        symbols = [e.usda_symbol for e in entities]
        assert "SOTU" in symbols
        assert "ZEAM" in symbols

    def test_author_stripped(self) -> None:
        """Scientific name has author citation stripped."""
        conn = USDAConnector()
        records = conn.fetch(file_path=str(FIXTURES_DIR / "plantlst.txt"))
        entities, _ = conn.transform(records)

        potato = next(e for e in entities if e.usda_symbol == "SOTU")
        # Author "L." should be stripped
        assert "L." not in potato.scientific_name
        assert "Solanum tuberosum" == potato.scientific_name

    def test_full_pipeline(self) -> None:
        """Full pipeline run."""
        conn = USDAConnector()
        result = conn.run(file_path=str(FIXTURES_DIR / "plantlst.txt"))
        assert result.error is None
        assert len(result.entities) == 7
        assert result.source_name == DataSource.USDA_PLANTS


# ── USPEST.org Tests ─────────────────────────────────────────────────


class TestUSPESTConnector:
    """Tests for USPEST.org GDD model connector."""

    def test_fetch_groups_by_species(self) -> None:
        """Rows grouped by species name."""
        conn = USPESTConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "uspest_gdd_models.csv"))
        assert len(records) == 3  # 3 species

    def test_transform_pest_entities(self) -> None:
        """Transform produces Pest entities."""
        conn = USPESTConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "uspest_gdd_models.csv"))
        entities, _ = conn.transform(records)

        assert len(entities) == 3
        assert all(isinstance(e, Pest) for e in entities)

    def test_gdd_model_fahrenheit_to_celsius(self) -> None:
        """Base temperatures converted from °F to °C."""
        conn = USPESTConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "uspest_gdd_models.csv"))
        entities, _ = conn.transform(records)

        cpb = next(e for e in entities if "decemlineata" in e.scientific_name)
        assert isinstance(cpb, Pest)
        assert cpb.gdd_model is not None
        # 52°F = 11.11°C
        assert abs(cpb.gdd_model.t_base_celsius - 11.11) < 0.1
        # 95°F = 35.0°C
        assert abs(cpb.gdd_model.t_max_celsius - 35.0) < 0.1

    def test_gdd_stages_ordered(self) -> None:
        """GDD stages are ordered by cumulative degree-days."""
        conn = USPESTConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "uspest_gdd_models.csv"))
        entities, _ = conn.transform(records)

        cpb = next(e for e in entities if "decemlineata" in e.scientific_name)
        stages = cpb.gdd_model.stages
        assert len(stages) == 5
        for i in range(len(stages) - 1):
            assert stages[i].gdd_cumulative <= stages[i + 1].gdd_cumulative

    def test_full_pipeline(self) -> None:
        """Full pipeline run."""
        conn = USPESTConnector()
        result = conn.run(csv_path=str(FIXTURES_DIR / "uspest_gdd_models.csv"))
        assert result.error is None
        assert len(result.entities) == 3
        assert result.source_name == DataSource.USPEST
