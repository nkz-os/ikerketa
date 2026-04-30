"""Unit tests for validation rules."""

from __future__ import annotations

from ikerketa.models.base import DataSource
from ikerketa.models.crop import ClimaticProfile, Crop
from ikerketa.models.pest import GDDModel, LifeStage, Pest, PestType
from ikerketa.validate.rules import validate_crop, validate_pest


class TestCropValidation:
    def test_valid_crop(self, sample_crop) -> None:  # type: ignore[no-untyped-def]
        result = validate_crop(sample_crop)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_extreme_temperature(self) -> None:
        """Crop with t_kill below -60°C should fail."""
        crop = Crop(
            source_name=DataSource.ECOCROP,
            scientific_name="Test plant",
            eppo_code="TESPL",
            climatic_profile=ClimaticProfile(t_kill=-100.0, t_max=30.0),
        )
        result = validate_crop(crop)
        assert result.is_valid is False
        assert any("-60" in e for e in result.errors)

    def test_missing_scientific_name(self) -> None:
        crop = Crop(
            source_name=DataSource.ECOCROP,
            scientific_name="",
            eppo_code="TESPL",
        )
        result = validate_crop(crop)
        assert result.is_valid is False


class TestPestValidation:
    def test_valid_pest(self, sample_pest) -> None:  # type: ignore[no-untyped-def]
        result = validate_pest(sample_pest)
        assert result.is_valid is True

    def test_gdd_stages_not_ascending(self) -> None:
        """Pest with non-ascending GDD stages should fail."""
        pest = Pest(
            source_name=DataSource.USPEST,
            scientific_name="Test pest",
            eppo_code="TESPE",
            pest_type=PestType.INSECT,
            gdd_model=GDDModel(
                model_name="test",
                t_base_celsius=10.0,
                stages=[
                    LifeStage(stage_name="egg", gdd_cumulative=200.0),
                    LifeStage(stage_name="larva", gdd_cumulative=100.0),  # Out of order!
                ],
            ),
        )
        result = validate_pest(pest)
        assert result.is_valid is False
        assert any("ascending" in e for e in result.errors)
