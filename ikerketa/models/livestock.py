"""Livestock models — breeds, animal diseases, and feed resources.

Domain models for livestock (ganado) covering breed diversity,
animal health, and feed composition for organic/regenerative farming.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from ikerketa.models.base import BaseEntity


class LivestockSpecies(str, Enum):
    """Major livestock species categories."""

    BOVINE = "bovine"
    OVINE = "ovine"
    CAPRINE = "caprine"
    PORCINE = "porcine"
    EQUINE = "equine"
    POULTRY = "poultry"
    RABBIT = "rabbit"
    CAMELID = "camelid"
    BUBALINE = "bubaline"  # water buffalo
    OTHER = "other"


class BreedUseType(str, Enum):
    """Primary use of the breed."""

    MEAT = "meat"
    DAIRY = "dairy"
    DUAL = "dual"
    WOOL = "wool"
    DRAFT = "draft"
    EGG = "egg"
    COMPANION = "companion"
    MULTI = "multi"


class ConservationStatus(str, Enum):
    """FAO risk status classification for breeds."""

    NOT_AT_RISK = "not_at_risk"
    VULNERABLE = "vulnerable"
    ENDANGERED = "endangered"
    CRITICAL = "critical"
    EXTINCT = "extinct"
    UNKNOWN = "unknown"


class Breed(BaseEntity):
    """A livestock breed from FAO DAD-IS.

    Covers breed characteristics, conservation status,
    population, and geographic distribution.
    """

    breed_name: str = Field(description="Local breed name")
    species: LivestockSpecies = Field(description="Livestock species category")
    country_origin: str = Field(default="", description="ISO country code of origin")
    use_type: BreedUseType = Field(
        default=BreedUseType.MULTI, description="Primary breed use"
    )
    conservation_status: ConservationStatus = Field(
        default=ConservationStatus.UNKNOWN,
        description="FAO risk status",
    )
    population_size: int | None = Field(
        default=None, ge=0,
        description="Estimated population size",
    )
    dad_is_id: str = Field(default="", description="DAD-IS breed identifier")
    transboundary: bool = Field(
        default=False,
        description="Whether the breed is found across multiple countries",
    )


class PathogenType(str, Enum):
    """Type of pathogen causing disease."""

    VIRUS = "virus"
    BACTERIA = "bacteria"
    PARASITE = "parasite"
    FUNGUS = "fungus"
    PRION = "prion"
    UNKNOWN = "unknown"


class AnimalDisease(BaseEntity):
    """An animal disease from WOAH/WAHIS.

    Covers disease classification, zoonotic risk,
    and regulatory notification status.
    """

    disease_name: str = Field(description="Common disease name")
    pathogen_type: PathogenType = Field(
        default=PathogenType.UNKNOWN,
        description="Type of causative pathogen",
    )
    scientific_name: str = Field(
        default="", description="Scientific name of the pathogen"
    )
    woah_listed: bool = Field(
        default=False,
        description="Listed by WOAH (notifiable)",
    )
    zoonotic: bool = Field(
        default=False,
        description="Transmissible to humans",
    )
    affected_species: list[str] = Field(
        default_factory=list,
        description="Livestock species affected",
    )
    notifiable_eu: bool = Field(
        default=False,
        description="Notifiable under EU regulation",
    )


class FeedResource(BaseEntity):
    """A feed resource from Feedipedia.

    Nutritional composition and suitability data for
    livestock feed ingredients.
    """

    feed_name: str = Field(description="Common name of the feed resource")
    scientific_name: str = Field(
        default="", description="Scientific name if a plant-based feed"
    )
    dry_matter_pct: float | None = Field(
        default=None, ge=0, le=100,
        description="Dry matter content (%)",
    )
    crude_protein_pct: float | None = Field(
        default=None, ge=0, le=100,
        description="Crude protein content (% DM)",
    )
    crude_fiber_pct: float | None = Field(
        default=None, ge=0, le=100,
        description="Crude fiber content (% DM)",
    )
    metabolizable_energy_mj: float | None = Field(
        default=None, ge=0,
        description="Metabolizable energy (MJ/kg DM)",
    )
    organic_compatible: bool = Field(
        default=False,
        description="Suitable for organic livestock production",
    )
    toxicity_notes: str = Field(
        default="",
        description="Known toxicity or anti-nutritional factors",
    )
    suitable_species: list[str] = Field(
        default_factory=list,
        description="Livestock species for which this feed is suitable",
    )
