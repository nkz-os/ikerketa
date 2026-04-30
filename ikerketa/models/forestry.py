"""Forestry models — tree species and allometric equations.

Domain models for forestry (silvicultura) covering tree species
characteristics, conservation status, and biomass/carbon
estimation equations for agroforestry systems.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from ikerketa.models.base import BaseEntity


class IUCNStatus(str, Enum):
    """IUCN Red List conservation status categories."""

    NOT_EVALUATED = "NE"
    DATA_DEFICIENT = "DD"
    LEAST_CONCERN = "LC"
    NEAR_THREATENED = "NT"
    VULNERABLE = "VU"
    ENDANGERED = "EN"
    CRITICALLY_ENDANGERED = "CR"
    EXTINCT_IN_WILD = "EW"
    EXTINCT = "EX"


class GrowthRate(str, Enum):
    """Tree growth rate classification."""

    SLOW = "slow"         # < 30 cm/year
    MODERATE = "moderate"  # 30-60 cm/year
    FAST = "fast"          # > 60 cm/year


class EcosystemService(str, Enum):
    """Ecosystem services provided by tree species."""

    CARBON_SEQUESTRATION = "carbon_sequestration"
    NITROGEN_FIXATION = "nitrogen_fixation"
    SOIL_STABILIZATION = "soil_stabilization"
    WINDBREAK = "windbreak"
    SHADE = "shade"
    POLLINATOR_HABITAT = "pollinator_habitat"
    WATER_REGULATION = "water_regulation"
    BIODIVERSITY_CORRIDOR = "biodiversity_corridor"
    EROSION_CONTROL = "erosion_control"
    FODDER = "fodder"


class TreeSpecies(BaseEntity):
    """A tree species from GlobalTreeSearch / EUFORGEN / ICRAF.

    Covers taxonomy, distribution, conservation, and
    functional traits relevant to agroforestry.
    """

    scientific_name: str = Field(description="Binomial scientific name")
    common_names: dict[str, str] = Field(
        default_factory=dict,
        description="Common names by language code",
    )
    family: str = Field(default="", description="Botanical family")
    native_range: list[str] = Field(
        default_factory=list,
        description="ISO country codes of native range",
    )
    iucn_status: IUCNStatus = Field(
        default=IUCNStatus.NOT_EVALUATED,
        description="IUCN Red List category",
    )
    wood_density_kg_m3: float | None = Field(
        default=None, ge=0,
        description="Mean wood density (kg/m³)",
    )
    growth_rate: GrowthRate | None = Field(
        default=None,
        description="Growth rate classification",
    )
    max_height_m: float | None = Field(
        default=None, ge=0,
        description="Maximum height (m)",
    )
    max_dbh_cm: float | None = Field(
        default=None, ge=0,
        description="Maximum diameter at breast height (cm)",
    )
    nitrogen_fixing: bool = Field(
        default=False,
        description="Whether the species fixes atmospheric nitrogen",
    )
    ecosystem_services: list[EcosystemService] = Field(
        default_factory=list,
        description="Ecosystem services provided",
    )
    deciduous: bool | None = Field(
        default=None,
        description="True=deciduous, False=evergreen, None=unknown",
    )


class DependentVariable(str, Enum):
    """What the allometric equation estimates."""

    VOLUME = "volume"
    BIOMASS = "biomass"
    ABOVE_GROUND_BIOMASS = "above_ground_biomass"
    BELOW_GROUND_BIOMASS = "below_ground_biomass"
    CARBON = "carbon"
    LEAF_AREA = "leaf_area"


class AllometricEquation(BaseEntity):
    """An allometric equation from GlobAllomeTree.

    Mathematical models for estimating tree volume, biomass,
    or carbon stock from measurable parameters (DBH, height).
    Used in carbon sequestration calculations.
    """

    equation_id: str = Field(description="GlobAllomeTree equation ID")
    species_name: str = Field(
        default="",
        description="Species the equation was developed for",
    )
    equation_form: str = Field(
        description="Mathematical expression (e.g., 'a * DBH^b * H^c')",
    )
    dependent_var: DependentVariable = Field(
        description="Variable being estimated",
    )
    independent_vars: list[str] = Field(
        default_factory=list,
        description="Predictor variables: DBH, H, crown_diameter, etc.",
    )
    coefficients: dict[str, float] = Field(
        default_factory=dict,
        description="Equation coefficients (a, b, c, ...)",
    )
    r_squared: float | None = Field(
        default=None, ge=0, le=1,
        description="Coefficient of determination",
    )
    sample_size: int | None = Field(
        default=None, ge=0,
        description="Number of trees in the sample",
    )
    climate_zone: str = Field(
        default="",
        description="Climate zone: tropical, subtropical, temperate, boreal",
    )
    country: str = Field(
        default="",
        description="Country where equation was developed",
    )

    @model_validator(mode="after")
    def _validate_r_squared(self) -> AllometricEquation:
        if self.r_squared is not None and self.r_squared < 0.5:
            # Low R² is suspicious but not invalid — log warning
            pass
        return self
