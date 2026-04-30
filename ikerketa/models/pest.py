"""Pest models — GDD phenological models and quarantine status.

Models for arthropods, pathogens, and weeds with their degree-day
development parameters as defined by USPEST.org/DDRP models.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from ikerketa.models.taxonomy import Taxon


class PestType(str, Enum):
    """Classification of pest organisms."""

    INSECT = "insect"
    INVASIVE_INSECT = "invasive_insect"
    MITE = "mite"
    NEMATODE = "nematode"
    FUNGUS = "fungus"
    BACTERIUM = "bacterium"
    VIRUS = "virus"
    WEED = "weed"
    OTHER = "other"


class QuarantineStatus(str, Enum):
    """EPPO quarantine status categories."""

    A1 = "A1"       # Absent, recommended for regulation
    A2 = "A2"       # Present, recommended for regulation
    ALERT = "alert"  # EPPO Alert List
    NONE = "none"    # Not regulated


class DistributionStatus(str, Enum):
    """Geographic distribution status (EPPO categories)."""

    PRESENT = "present"
    PRESENT_RESTRICTED = "present_restricted"
    PRESENT_WIDESPREAD = "present_widespread"
    ABSENT = "absent"
    ABSENT_ERADICATED = "absent_eradicated"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"


class LifeStage(BaseModel):
    """A single life stage within a GDD model.

    Each stage has a name and the cumulative GDD required to reach
    it from the biofix date (first activity/emergence).
    """

    stage_name: str = Field(
        description="Stage name: egg, larva_L1, larva_L2, pupa, adult, etc.",
    )
    gdd_cumulative: float = Field(
        ge=0,
        description="Cumulative GDD required from biofix to reach this stage",
    )
    gdd_range_low: float | None = Field(
        default=None, ge=0,
        description="Lower bound of GDD range (if uncertainty exists)",
    )
    gdd_range_high: float | None = Field(
        default=None, ge=0,
        description="Upper bound of GDD range (if uncertainty exists)",
    )
    notes: str = Field(default="")


class GDDModel(BaseModel):
    """Growing Degree Day development model for a pest.

    Based on USPEST.org/DDRP parametric structure.
    Temperature units always in °C (converted from °F if needed).
    """

    model_name: str = Field(description="Model identifier (e.g., 'codling_moth_gdd')")
    t_base_celsius: float = Field(
        description="Lower developmental threshold (°C). Development ceases below this.",
    )
    t_max_celsius: float | None = Field(
        default=None,
        description="Upper developmental threshold (°C). Development ceases/decreases above this.",
    )
    calculation_method: str = Field(
        default="single_sine",
        description="GDD calculation: simple_average, single_sine, double_sine, modified_sine",
    )
    cutoff_method: str = Field(
        default="horizontal",
        description="Cutoff when T > Tmax: horizontal, vertical, intermediate",
    )
    stages: list[LifeStage] = Field(
        default_factory=list,
        description="Ordered list of life stages with GDD thresholds",
    )
    generations_per_year: int | None = Field(
        default=None, ge=1,
        description="Typical number of generations per year (voltinism)",
    )
    biofix_description: str = Field(
        default="",
        description="How to determine the biofix date (e.g., 'first sustained trap catch')",
    )
    reference: str = Field(default="", description="Publication or data source reference")

    @model_validator(mode="after")
    def validate_temperature_bounds(self) -> GDDModel:
        if self.t_max_celsius is not None and self.t_base_celsius >= self.t_max_celsius:
            msg = f"t_base ({self.t_base_celsius}) must be < t_max ({self.t_max_celsius})"
            raise ValueError(msg)
        return self


class Pest(Taxon):
    """A pest organism (insect, pathogen, weed) with phenological model.

    Extends Taxon with GDD development model, quarantine status,
    and host plant associations.
    """

    pest_type: PestType = Field(description="Classification of this pest")

    # GDD Development model
    gdd_model: GDDModel | None = Field(
        default=None,
        description="Degree-day development model (from USPEST/DDRP)",
    )

    # Regulatory status
    quarantine_status: QuarantineStatus = Field(
        default=QuarantineStatus.NONE,
        description="EPPO quarantine classification",
    )
    distribution: dict[str, DistributionStatus] = Field(
        default_factory=dict,
        description="Geographic distribution keyed by ISO 3166-1 alpha-2 country code",
    )

    # Host range (EPPO codes of host plants)
    host_eppo_codes: list[str] = Field(
        default_factory=list,
        description="EPPO codes of known host plants",
    )
    host_agrovoc_uris: list[str] = Field(
        default_factory=list,
        description="AGROVOC URIs of known host plants",
    )

    # Damage
    damage_type: str = Field(
        default="",
        description="Primary damage mechanism: feeding, vectoring, competition, etc.",
    )
