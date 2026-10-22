"""Crop models — edaphoclimatic requirements and physiological profiles.

Based on EcoCrop/GAEZ parametric structure with strict numerical bounds
for temperature, precipitation, soil characteristics, and light.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from ikerketa.models.taxonomy import Taxon


class SoilTexture(str, Enum):
    """Soil texture categories (EcoCrop classification)."""

    HEAVY = "heavy"       # Clay-rich
    MEDIUM = "medium"     # Loam
    LIGHT = "light"       # Sandy
    ORGANIC = "organic"


class SoilFertility(str, Enum):
    """Soil fertility requirements."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class SoilDrainage(str, Enum):
    """Soil drainage categories."""

    POOR = "poor"
    MODERATE = "moderate"
    WELL = "well"
    EXCESSIVE = "excessive"


class SalinityTolerance(str, Enum):
    """Salinity tolerance levels (dS/m ranges from EcoCrop)."""

    NONE = "none"           # 0 dS/m
    LOW = "low"             # < 4 dS/m
    MEDIUM = "medium"       # 4-10 dS/m
    HIGH = "high"           # > 10 dS/m


class EdaphicProfile(BaseModel):
    """Soil requirements for a crop (EcoCrop parametric model).

    All numerical ranges use the pattern: absolute_min, optimal_min,
    optimal_max, absolute_max — matching EcoCrop's data structure.
    """

    ph_min: float | None = Field(default=None, ge=0, le=14)
    ph_optimal_min: float | None = Field(default=None, ge=0, le=14)
    ph_optimal_max: float | None = Field(default=None, ge=0, le=14)
    ph_max: float | None = Field(default=None, ge=0, le=14)

    soil_depth_category: str = Field(
        default="",
        description="Depth: very_shallow (<20cm), shallow (20-50), medium (50-150), deep (>150)",
    )
    soil_textures: list[SoilTexture] = Field(
        default_factory=list,
        description="Tolerated soil textures",
    )
    fertility: SoilFertility | None = None
    salinity: SalinityTolerance | None = None
    drainage: SoilDrainage | None = None

    @model_validator(mode="after")
    def validate_ph_ranges(self) -> EdaphicProfile:
        """Ensure pH values form a valid range: min ≤ opt_min ≤ opt_max ≤ max."""
        vals = [
            v for v in [self.ph_min, self.ph_optimal_min, self.ph_optimal_max, self.ph_max]
            if v is not None
        ]
        if len(vals) >= 2 and vals != sorted(vals):
            msg = f"pH values must be in ascending order, got: {vals}"
            raise ValueError(msg)
        return self


class ClimaticProfile(BaseModel):
    """Climate requirements for a crop (EcoCrop parametric model).

    Temperature in °C, precipitation in mm/year.
    All values use the EcoCrop 5-point system where applicable.
    """

    # Temperature bounds (°C)
    t_kill: float | None = Field(
        default=None, description="Absolute minimum temperature (lethal, °C)",
    )
    t_min: float | None = Field(
        default=None, description="Minimum growth temperature (°C)",
    )
    t_opt_min: float | None = Field(
        default=None, description="Optimal minimum temperature (°C)",
    )
    t_opt_max: float | None = Field(
        default=None, description="Optimal maximum temperature (°C)",
    )
    t_max: float | None = Field(
        default=None, description="Absolute maximum temperature (°C)",
    )

    # Precipitation bounds (mm/year)
    precip_min: float | None = Field(default=None, ge=0)
    precip_opt_min: float | None = Field(default=None, ge=0)
    precip_opt_max: float | None = Field(default=None, ge=0)
    precip_max: float | None = Field(default=None, ge=0)

    # Light
    photoperiod_sensitivity: str = Field(
        default="",
        description="short_day, long_day, day_neutral",
    )
    light_intensity: str = Field(
        default="",
        description="Shade tolerance: very_bright, bright, cloudy, heavy_shade",
    )

    # Köppen zones
    koppen_zones: list[str] = Field(
        default_factory=list,
        description="Compatible Köppen climate zones",
    )

    # Growing season
    growing_cycle_days_min: int | None = Field(default=None, ge=0)
    growing_cycle_days_max: int | None = Field(default=None, ge=0)


class Crop(Taxon):
    """A cultivated plant species with edaphoclimatic requirements.

    Extends Taxon with EcoCrop-derived parametric profiles for soil
    and climate, enabling algorithmic suitability evaluation.
    """

    edaphic_profile: EdaphicProfile = Field(default_factory=EdaphicProfile)
    climatic_profile: ClimaticProfile = Field(default_factory=ClimaticProfile)

    # Crop-specific metadata
    crop_category: str = Field(
        default="",
        description="Category: cereal, legume, vegetable, fruit, oil, fiber, etc.",
    )
    harvest_parts: list[str] = Field(
        default_factory=list,
        description="Parts harvested: seed, fruit, leaf, root, tuber, stem",
    )
    altitude_min_m: float | None = Field(default=None, ge=0)
    altitude_max_m: float | None = Field(default=None, ge=0)
