"""Relationship models — inter-entity associations.

Covers host-pest associations, companion planting (HELPS/HURTS),
and natural enemy (biocontrol) relationships.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from ikerketa.models.base import BaseRelationship


class CompanionType(str, Enum):
    """Type of companion planting interaction."""

    HELPS = "helps"                  # Mutualism / beneficial
    HURTS = "hurts"                  # Allelopathy / antagonism
    ATTRACTS = "attracts"            # Attracts beneficial insects
    REPELS = "repels"                # Repels pest insects
    TRAP_CROP = "trap_crop"          # Lures pests away from main crop
    NITROGEN_FIXER = "nitrogen_fixer"  # Provides nitrogen fixation


class HostAssociation(BaseRelationship):
    """Pest-to-host-plant relationship (from EPPO / CABI).

    The source is the pest, the target is the host plant.
    """

    relationship_type: str = "HOSTS_ON"

    host_status: str = Field(
        default="major",
        description="Host importance: major, minor, experimental, wild",
    )
    affected_plant_part: str = Field(
        default="",
        description="Plant part affected: leaves, fruit, roots, stem, etc.",
    )


class CompanionRelation(BaseRelationship):
    """Companion planting relationship between two crop species.

    From curated GitHub datasets (alecsharpie, GenevieveMilliken).
    """

    relationship_type: str = "COMPANION"

    companion_type: CompanionType = Field(
        description="Nature of the companion interaction",
    )
    mechanism: str = Field(
        default="",
        description="Biological mechanism: allelopathy, nitrogen_fixation, trap_cropping, etc.",
    )
    citation: str = Field(
        default="",
        description="Scientific or reference citation for this relationship",
    )


class NaturalEnemy(BaseRelationship):
    """Natural enemy (biocontrol agent) relationship.

    From CABI CPC: predator/parasitoid → target pest.
    """

    relationship_type: str = "CONTROLS"

    control_type: str = Field(
        default="predator",
        description="Control type: predator, parasitoid, pathogen, competitor",
    )
    efficacy_rating: str = Field(
        default="",
        description="Efficacy: high, moderate, low, unknown",
    )
    target_life_stage: str = Field(
        default="",
        description="Life stage of pest that is targeted (egg, larva, adult, etc.)",
    )
    # The natural enemy itself
    enemy_scientific_name: str = Field(
        default="",
        description="Scientific name of the biocontrol agent",
    )
    enemy_eppo_code: str | None = Field(
        default=None,
        description="EPPO code of the biocontrol agent, if available",
    )


# ── Inter-domain relationships (regenerative agriculture) ────────────


class Palatability(str, Enum):
    """Palatability of a plant resource as livestock feed."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNPALATABLE = "unpalatable"


class ToxicityRisk(str, Enum):
    """Toxicity risk of a plant resource for livestock."""

    NONE = "none"
    CONDITIONAL = "conditional"  # toxic under certain conditions
    LOW = "low"
    MODERATE = "moderate"
    TOXIC = "toxic"


class Season(str, Enum):
    """Season of availability or suitability."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    YEAR_ROUND = "year_round"


class FodderSuitability(BaseRelationship):
    """Tree/Crop → Livestock species: fodder aptitude.

    Relates a plant (tree or crop) to a livestock species
    with metrics on palatability, toxicity, and seasonal availability.

    Example: Quercus ilex (bellota) → Sus scrofa domesticus
    """

    relationship_type: str = "FODDER_FOR"

    palatability: Palatability = Field(
        default=Palatability.MODERATE,
        description="Palatability for the target livestock species",
    )
    toxicity_risk: ToxicityRisk = Field(
        default=ToxicityRisk.NONE,
        description="Level of toxicity risk",
    )
    season: Season = Field(
        default=Season.YEAR_ROUND,
        description="Season when this fodder resource is available",
    )
    plant_part: str = Field(
        default="whole_plant",
        description="Part used as feed: fruit, leaf, bark, pod, pasture, whole_plant",
    )
    dry_matter_intake_pct: float | None = Field(
        default=None, ge=0, le=100,
        description="Recommended dry matter intake (% of live weight)",
    )
    livestock_species: str = Field(
        default="",
        description="Target livestock species (e.g., bovine, ovine, porcine)",
    )


class AgroforestryCompatibility(str, Enum):
    """Level of agroforestry compatibility."""

    SYNERGISTIC = "synergistic"
    NEUTRAL = "neutral"
    COMPETITIVE = "competitive"


class LightInteraction(str, Enum):
    """How the understory crop/pasture tolerates light competition."""

    SHADE_TOLERANT = "shade_tolerant"
    PARTIAL_SHADE = "partial_shade"
    FULL_SUN = "full_sun"


class RootInteraction(str, Enum):
    """Root zone interaction between tree and understory."""

    COMPLEMENTARY = "complementary"
    COMPETITIVE = "competitive"
    NEUTRAL = "neutral"


class WaterCompetition(str, Enum):
    """Level of competition for water resources."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class AgroforestryAssociation(BaseRelationship):
    """Tree → Crop/Pasture: agroforestry compatibility.

    Defines interactions in silvopastoral and agrisilvicultural systems
    including competition for light, water, and root zone resources.

    Example: Juglans regia → Trifolium repens (synergistic, shade_tolerant)
    """

    relationship_type: str = "AGROFORESTRY_COMPATIBLE"

    compatibility: AgroforestryCompatibility = Field(
        default=AgroforestryCompatibility.NEUTRAL,
        description="Overall compatibility assessment",
    )
    light_interaction: LightInteraction = Field(
        default=LightInteraction.PARTIAL_SHADE,
        description="Light competition dynamics",
    )
    root_interaction: RootInteraction = Field(
        default=RootInteraction.NEUTRAL,
        description="Root zone interaction",
    )
    nitrogen_fixation: bool = Field(
        default=False,
        description="Whether the association involves N-fixation benefit",
    )
    water_competition: WaterCompetition = Field(
        default=WaterCompetition.MODERATE,
        description="Level of water competition",
    )
    tree_spacing_m: float | None = Field(
        default=None, ge=0,
        description="Recommended minimum tree spacing (m)",
    )
    evidence_level: str = Field(
        default="anecdotal",
        description="Evidence: experimental, observational, anecdotal",
    )
