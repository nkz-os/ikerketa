"""Shared test fixtures and configuration."""

from __future__ import annotations

import pytest

from ikerketa.models.base import DataSource
from ikerketa.models.crop import (
    ClimaticProfile,
    Crop,
    EdaphicProfile,
    SalinityTolerance,
    SoilDrainage,
    SoilFertility,
    SoilTexture,
)
from ikerketa.models.pest import GDDModel, LifeStage, Pest, PestType, QuarantineStatus
from ikerketa.models.relationship import CompanionRelation, CompanionType
from ikerketa.models.taxonomy import Taxon, TaxonSynonym


@pytest.fixture
def sample_taxon() -> Taxon:
    """Real taxon: Solanum tuberosum (potato)."""
    return Taxon(
        source_name=DataSource.USDA_PLANTS,
        scientific_name="Solanum tuberosum",
        scientific_name_authorship="L.",
        common_names={
            "en": ["potato"],
            "es": ["patata", "papa"],
            "eu": ["patata"],
            "fr": ["pomme de terre"],
        },
        family="Solanaceae",
        genus="Solanum",
        kingdom="Plantae",
        life_form="herb",
        life_cycle="annual",
        agrovoc_uri="http://aims.fao.org/aos/agrovoc/c_7951",
        eppo_code="SOLTU",
        usda_symbol="SOTU",
        synonyms=[
            TaxonSynonym(synonym_name="Solanum esculentum", synonym_type="scientific"),
        ],
        raw_record={"symbol": "SOTU", "scientific_name": "Solanum tuberosum L."},
    )


@pytest.fixture
def sample_crop() -> Crop:
    """Real crop: Solanum tuberosum (potato) with EcoCrop data."""
    return Crop(
        source_name=DataSource.ECOCROP,
        scientific_name="Solanum tuberosum",
        common_names={"en": ["potato"], "es": ["patata"]},
        family="Solanaceae",
        genus="Solanum",
        agrovoc_uri="http://aims.fao.org/aos/agrovoc/c_7951",
        eppo_code="SOLTU",
        edaphic_profile=EdaphicProfile(
            ph_min=4.2,
            ph_optimal_min=5.0,
            ph_optimal_max=6.5,
            ph_max=8.2,
            soil_textures=[SoilTexture.MEDIUM, SoilTexture.LIGHT],
            fertility=SoilFertility.HIGH,
            salinity=SalinityTolerance.LOW,
            drainage=SoilDrainage.WELL,
            soil_depth_category="medium",
        ),
        climatic_profile=ClimaticProfile(
            t_kill=-3.0,
            t_min=3.0,
            t_opt_min=15.0,
            t_opt_max=20.0,
            t_max=30.0,
            precip_min=500.0,
            precip_opt_min=1000.0,
            precip_opt_max=1500.0,
            precip_max=2000.0,
            photoperiod_sensitivity="short_day",
            growing_cycle_days_min=90,
            growing_cycle_days_max=150,
        ),
        crop_category="vegetable",
        harvest_parts=["tuber"],
        raw_record={"crop": "potato", "source": "ecocrop"},
    )


@pytest.fixture
def sample_pest() -> Pest:
    """Real pest: Leptinotarsa decemlineata (Colorado potato beetle)."""
    return Pest(
        source_name=DataSource.EPPO,
        scientific_name="Leptinotarsa decemlineata",
        common_names={"en": ["Colorado potato beetle"], "es": ["escarabajo de la patata"]},
        family="Chrysomelidae",
        genus="Leptinotarsa",
        kingdom="Animalia",
        eppo_code="LUFTDE",
        pest_type=PestType.INSECT,
        quarantine_status=QuarantineStatus.A2,
        gdd_model=GDDModel(
            model_name="colorado_potato_beetle",
            t_base_celsius=10.0,
            t_max_celsius=33.0,
            calculation_method="single_sine",
            stages=[
                LifeStage(stage_name="egg", gdd_cumulative=120.0),
                LifeStage(stage_name="larva_L1", gdd_cumulative=180.0),
                LifeStage(stage_name="larva_L4", gdd_cumulative=370.0),
                LifeStage(stage_name="pupa", gdd_cumulative=450.0),
                LifeStage(stage_name="adult", gdd_cumulative=580.0),
            ],
            generations_per_year=2,
            reference="USPEST.org DDRP models",
        ),
        host_eppo_codes=["SOLTU", "SOLME", "SOLLY"],
        distribution={"ES": "present_widespread", "FR": "present_widespread"},
        raw_record={"eppo_code": "LUFTDE", "name": "Leptinotarsa decemlineata"},
    )


@pytest.fixture
def sample_companion_relation() -> CompanionRelation:
    """Real companion planting: basil helps tomato."""
    return CompanionRelation(
        source_name=DataSource.COMPANION_PLANTING,
        source_eppo_code="OCIBA",  # Ocimum basilicum
        target_eppo_code="SOLLY",  # Solanum lycopersicum
        companion_type=CompanionType.HELPS,
        mechanism="Repels aphids and whiteflies; improves flavor",
        citation="companion_planting_dataset (alecsharpie/GitHub)",
        raw_record={"plant": "basil", "companion": "tomato", "type": "helps"},
    )
