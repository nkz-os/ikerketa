"""Tests for companion planting, DG SANTE, CABI, AgroPortal and FiBL connectors."""

from __future__ import annotations

from pathlib import Path

import pytest

from ikerketa.connectors.companion_planting import Connector as CompanionConnector
from ikerketa.connectors.dg_sante import Connector as DGSanteConnector
from ikerketa.connectors.cabi import Connector as CABIConnector
from ikerketa.connectors.fibl import Connector as FiBLConnector
from ikerketa.models.base import DataSource
from ikerketa.models.regulation import ActiveSubstance
from ikerketa.models.relationship import CompanionRelation, CompanionType, NaturalEnemy

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ── Companion Planting Tests ────────────────────────────────────────


class TestCompanionConnector:
    """Tests for companion planting CSV connector."""

    def test_fetch_all(self) -> None:
        conn = CompanionConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "companion_planting.csv"))
        assert len(records) == 6

    def test_transform_relationships_only(self) -> None:
        """Connector produces relationships, no standalone entities."""
        conn = CompanionConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "companion_planting.csv"))
        entities, rels = conn.transform(records)
        assert len(entities) == 0
        assert len(rels) == 6

    def test_companion_type_mapping(self) -> None:
        """Interaction types correctly mapped to CompanionType enum."""
        conn = CompanionConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "companion_planting.csv"))
        _, rels = conn.transform(records)

        types = [r.companion_type for r in rels if isinstance(r, CompanionRelation)]
        assert CompanionType.HELPS in types
        assert CompanionType.HURTS in types
        assert CompanionType.ATTRACTS in types
        assert CompanionType.TRAP_CROP in types

    def test_full_pipeline(self) -> None:
        conn = CompanionConnector()
        result = conn.run(csv_path=str(FIXTURES_DIR / "companion_planting.csv"))
        assert result.error is None
        assert result.source_name == DataSource.COMPANION_PLANTING


# ── DG SANTE Tests ──────────────────────────────────────────────────


class TestDGSanteConnector:
    """Tests for DG SANTE connector (CSV fallback mode)."""

    def test_fetch_csv_fallback(self) -> None:
        conn = DGSanteConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "dg_sante.csv"))
        assert len(records) == 5

    def test_transform_active_substances(self) -> None:
        conn = DGSanteConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "dg_sante.csv"))
        entities, _ = conn.transform(records)
        assert len(entities) == 5
        assert all(isinstance(e, ActiveSubstance) for e in entities)

    def test_organic_flag(self) -> None:
        """Organic compatibility correctly parsed."""
        conn = DGSanteConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "dg_sante.csv"))
        entities, _ = conn.transform(records)

        organic = [e for e in entities if e.organic_compatible]
        non_organic = [e for e in entities if not e.organic_compatible]
        assert len(organic) == 3  # Copper, Spinosad, Bt
        assert len(non_organic) == 2  # Glyphosate, Chlorpyrifos

    def test_approval_status(self) -> None:
        """Approval status correctly determined."""
        conn = DGSanteConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "dg_sante.csv"))
        entities, _ = conn.transform(records)

        chlorpyrifos = next(e for e in entities if "Chlorpyrifos" in e.substance_name)
        assert chlorpyrifos.is_approved_eu is False

    def test_full_pipeline(self) -> None:
        conn = DGSanteConnector()
        result = conn.run(csv_path=str(FIXTURES_DIR / "dg_sante.csv"))
        assert result.error is None
        assert result.source_name == DataSource.DG_SANTE


# ── CABI Tests ──────────────────────────────────────────────────────


class TestCABIConnector:
    """Tests for CABI CPC stub connector."""

    def test_fetch_all(self) -> None:
        conn = CABIConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "cabi_natural_enemies.csv"))
        assert len(records) == 4

    def test_transform_natural_enemies(self) -> None:
        """Produces NaturalEnemy relationships."""
        conn = CABIConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "cabi_natural_enemies.csv"))
        entities, rels = conn.transform(records)
        assert len(entities) == 0
        assert len(rels) == 4
        assert all(isinstance(r, NaturalEnemy) for r in rels)

    def test_enemy_details(self) -> None:
        """Natural enemy details correctly parsed."""
        conn = CABIConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "cabi_natural_enemies.csv"))
        _, rels = conn.transform(records)

        podisus = next(r for r in rels if isinstance(r, NaturalEnemy) and "Podisus" in r.enemy_scientific_name)
        assert podisus.control_type == "predator"
        assert podisus.efficacy_rating == "high"
        assert podisus.target_life_stage == "larva"

    def test_full_pipeline(self) -> None:
        conn = CABIConnector()
        result = conn.run(csv_path=str(FIXTURES_DIR / "cabi_natural_enemies.csv"))
        assert result.error is None
        assert result.source_name == DataSource.CABI


# ── FiBL Tests ──────────────────────────────────────────────────────


class TestFiBLConnector:
    """Tests for FiBL organic input list connector."""

    def test_fetch_all(self) -> None:
        conn = FiBLConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "fibl_inputs.csv"))
        assert len(records) == 4

    def test_transform_substances(self) -> None:
        conn = FiBLConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "fibl_inputs.csv"))
        entities, _ = conn.transform(records)
        assert len(entities) == 4
        assert all(isinstance(e, ActiveSubstance) for e in entities)

    def test_all_organic(self) -> None:
        """FiBL products are all organic-compatible."""
        conn = FiBLConnector()
        records = conn.fetch(csv_path=str(FIXTURES_DIR / "fibl_inputs.csv"))
        entities, _ = conn.transform(records)
        assert all(e.organic_compatible for e in entities)

    def test_full_pipeline(self) -> None:
        conn = FiBLConnector()
        result = conn.run(csv_path=str(FIXTURES_DIR / "fibl_inputs.csv"))
        assert result.error is None
        assert result.source_name == DataSource.FIBL
