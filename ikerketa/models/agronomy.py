"""AgriKnowledge model — structured agronomic knowledge for regenerative agriculture.

Represents validated, parameterized knowledge about cover crops and
protein crops for the NKZ regenerative sequence engine. Each record
is a single data point (species × climate × parameter) with full
provenance tracking suitable for Neo4j :AgriKnowledge nodes.

Data sources: INTIA Navarra, JRC MARS Bulletins, Legumes Translated (H2020),
DiverIMPACTS (H2020), ITACyL, IFAPA, and published European agronomic research.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from ikerketa.models.base import BaseEntity


class ClimateClass(str, Enum):
    """Köppen-Geiger climate classes relevant to European cover crops."""

    Csa = "Csa"  # Hot-summer Mediterranean (S Spain, S France, Italy, Portugal coast)
    BSk = "BSk"  # Cold semi-arid (Interior Spain, Castilla y León, Aragón)
    Cfb = "Cfb"  # Oceanic (N Spain, France, Germany, UK)
    BSh = "BSh"  # Hot semi-arid (Andalusia interior)
    Csb = "Csb"  # Warm-summer Mediterranean (Portugal, Galicia coast)
    Dfb = "Dfb"  # Warm-summer continental (Bavaria, E Europe)


class AgriKnowledgeParameter(str, Enum):
    """Validated parameters for cover crop and protein crop knowledge."""

    BIOMASS_T_HA = "biomass_t_ha"
    C_N_RATIO = "c_n_ratio"
    GDD_TO_TERMINATION = "gdd_to_termination"
    FROST_TOLERANCE_C = "frost_tolerance_c"
    N_FIXATION_KG_HA = "n_fixation_kg_ha"
    N_CONTENT_PCT = "n_content_pct"


class AgriKnowledge(BaseEntity):
    """A single validated agronomic knowledge data point.

    Represents one parameter value for one species in one climate class,
    sourced from European research. Designed for direct mapping to Neo4j
    :AgriKnowledge nodes in the BioOrchestrator knowledge graph.

    Neo4j mapping:
        (:AgriKnowledge {
            speciesEppo: 'VICSA',
            climateClass: 'Csa',
            parameter: 'biomass_t_ha',
            value: 4.2,
            unit: 't/ha',
            sourceDoi: '10.xxx/...',
            sourceUrl: 'https://...',
            confidence: 0.85
        })
    """

    # ── Core Knowledge Keys ──────────────────────────────────────────────
    species_eppo: str = Field(
        description="EPPO 5-letter code of the species",
        min_length=5, max_length=5,
        examples=["VICSA", "VICVI", "SECCE"],
    )
    climate_class: str = Field(
        description="Köppen-Geiger climate class",
        examples=["Csa", "BSk", "Cfb"],
    )
    parameter: str = Field(
        description="Parameter name from AgriKnowledgeParameter enum",
        examples=["biomass_t_ha", "c_n_ratio", "gdd_to_termination"],
    )
    value: float = Field(
        description="Numeric value of the parameter (mean or best estimate)",
    )

    # ── Value Metadata ───────────────────────────────────────────────────
    unit: str = Field(
        description="Unit of measurement (UCUM-compatible)",
        examples=["t/ha", "kg N/ha", "°C", "GDD"],
    )
    value_min: float | None = Field(
        default=None,
        description="Minimum observed value (for range data)",
    )
    value_max: float | None = Field(
        default=None,
        description="Maximum observed value (for range data)",
    )

    # ── Provenance ───────────────────────────────────────────────────────
    source_doi: str | None = Field(
        default=None,
        description="DOI of the primary publication supporting this value",
    )
    source_url: str | None = Field(
        default=None,
        description="URL to the source document or dataset",
    )
    source_institution: str | None = Field(
        default=None,
        description="Institution that produced the data",
        examples=["INTIA Navarra", "JRC MARS", "Legumes Translated (H2020)"],
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="Confidence score based on data quality and peer-review status",
    )
    data_gap: bool = Field(
        default=False,
        description="True if this value is an estimate (gap-filled) rather than measured",
    )
    notes: str | None = Field(
        default=None,
        description="Additional context: methodology, experimental conditions, caveats",
    )

    # ── Related Taxonomy (for merging across sources) ────────────────────
    species_scientific_name: str | None = Field(
        default=None,
        description="Full scientific name (genus + species)",
        examples=["Vicia sativa", "Secale cereale"],
    )
    species_common_names: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Common names by language code",
        examples=[{"en": ["common vetch"], "es": ["veza"], "fr": ["vesce commune"]}],
    )
    crop_category: str | None = Field(
        default=None,
        description="cover_crop_winter, protein_crop, forage_legume, etc.",
    )

    def has_any_key(self) -> bool:
        """AgriKnowledge uses species_eppo as its primary identifier."""
        return bool(self.species_eppo) or super().has_any_key()
