"""Unit tests for Pydantic data models — using real agronomic data."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ikerketa.models.base import BaseEntity, DataSource
from ikerketa.models.crop import (
    ClimaticProfile,
    Crop,
    EdaphicProfile,
    SoilTexture,
)
from ikerketa.models.pest import GDDModel, LifeStage, Pest, PestType
from ikerketa.models.relationship import CompanionRelation, CompanionType


class TestBaseEntity:
    def test_eppo_code_validation_valid(self) -> None:
        """EPPO codes are 5-6 uppercase letters."""
        entity = BaseEntity(
            source_name=DataSource.EPPO,
            eppo_code="SOLTU",
        )
        assert entity.eppo_code == "SOLTU"

    def test_eppo_code_validation_lowercase_normalized(self) -> None:
        """Lowercase EPPO codes are uppercased."""
        entity = BaseEntity(
            source_name=DataSource.EPPO,
            eppo_code="soltu",
        )
        assert entity.eppo_code == "SOLTU"

    def test_eppo_code_validation_invalid_length(self) -> None:
        """EPPO codes must be 4-6 alphanumeric."""
        with pytest.raises(ValidationError, match="EPPO code must be 4-6 alphanumeric"):
            BaseEntity(source_name=DataSource.EPPO, eppo_code="SO")

    def test_eppo_code_validation_alphanumeric(self) -> None:
        """EPPO codes accept alphanumeric for higher taxa (e.g., 1AA0G)."""
        entity = BaseEntity(source_name=DataSource.EPPO, eppo_code="1AA0G")
        assert entity.eppo_code == "1AA0G"

    def test_none_eppo_code_allowed(self) -> None:
        """EPPO code can be None (entity from non-EPPO source)."""
        entity = BaseEntity(source_name=DataSource.AGROVOC)
        assert entity.eppo_code is None

    def test_compute_hash(self) -> None:
        """Hash should be deterministic for same raw_record."""
        entity = BaseEntity(
            source_name=DataSource.EPPO,
            raw_record={"key": "value"},
        )
        h1 = entity.compute_hash()
        h2 = entity.compute_hash()
        assert h1 == h2
        assert len(h1) == 16  # xxh64 hex = 16 chars

    def test_has_any_key(self) -> None:
        """has_any_key returns True if any identifier is set."""
        e1 = BaseEntity(source_name=DataSource.EPPO, eppo_code="SOLTU")
        e2 = BaseEntity(source_name=DataSource.AGROVOC, agrovoc_uri="http://example.org")
        e3 = BaseEntity(source_name=DataSource.EPPO)
        assert e1.has_any_key() is True
        assert e2.has_any_key() is True
        assert e3.has_any_key() is False


class TestCrop:
    def test_crop_creation(self, sample_crop: Crop) -> None:
        """Crop with real EcoCrop data creates successfully."""
        assert sample_crop.scientific_name == "Solanum tuberosum"
        assert sample_crop.eppo_code == "SOLTU"
        assert sample_crop.edaphic_profile.ph_min == 4.2
        assert sample_crop.climatic_profile.t_kill == -3.0

    def test_ph_range_validation(self) -> None:
        """pH values must be in ascending order."""
        with pytest.raises(ValidationError, match="ascending order"):
            EdaphicProfile(ph_min=7.0, ph_optimal_min=5.0, ph_optimal_max=6.0, ph_max=8.0)

    def test_valid_soil_textures(self) -> None:
        """Soil textures accept valid EcoCrop categories."""
        ep = EdaphicProfile(soil_textures=[SoilTexture.HEAVY, SoilTexture.MEDIUM])
        assert len(ep.soil_textures) == 2


class TestPest:
    def test_pest_creation(self, sample_pest: Pest) -> None:
        """Pest with real EPPO/USPEST data creates successfully."""
        assert sample_pest.scientific_name == "Leptinotarsa decemlineata"
        assert sample_pest.eppo_code == "LUFTDE"
        assert sample_pest.gdd_model is not None
        assert sample_pest.gdd_model.t_base_celsius == 10.0
        assert len(sample_pest.gdd_model.stages) == 5

    def test_gdd_model_temperature_validation(self) -> None:
        """GDD model: t_base must be < t_max."""
        with pytest.raises(ValidationError, match="t_base"):
            GDDModel(
                model_name="invalid",
                t_base_celsius=35.0,
                t_max_celsius=10.0,
                stages=[],
            )

    def test_gdd_stages_ascending(self, sample_pest: Pest) -> None:
        """GDD stages should have ascending cumulative GDD."""
        assert sample_pest.gdd_model is not None
        stages = sample_pest.gdd_model.stages
        for i in range(1, len(stages)):
            assert stages[i].gdd_cumulative > stages[i - 1].gdd_cumulative


class TestRelationships:
    def test_companion_relation(self, sample_companion_relation: CompanionRelation) -> None:
        """Companion planting relation with real data."""
        assert sample_companion_relation.companion_type == CompanionType.HELPS
        assert sample_companion_relation.source_eppo_code == "OCIBA"
        assert sample_companion_relation.target_eppo_code == "SOLLY"
