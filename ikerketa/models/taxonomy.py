"""Taxonomy models — species identification and nomenclature."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ikerketa.models.base import BaseEntity


class TaxonSynonym(BaseModel):
    """A taxonomic synonym for a species."""

    synonym_name: str = Field(description="Full scientific name of the synonym")
    synonym_type: str = Field(
        default="scientific",
        description="Type: scientific, common, trade, etc.",
    )
    language: str = Field(
        default="la",
        description="ISO 639-1 language code",
    )


class Taxon(BaseEntity):
    """A biological taxon (species, subspecies, variety).

    This is the foundational taxonomic node. Crop and Pest extend it
    with domain-specific attributes.
    """

    scientific_name: str = Field(
        description="Accepted scientific name (binomial nomenclature)",
        examples=["Solanum tuberosum"],
    )
    scientific_name_authorship: str = Field(
        default="",
        description="Author citation (e.g., 'L.' for Linnaeus)",
    )
    common_names: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Common names keyed by ISO 639-1 language code",
        examples=[{"en": ["potato"], "es": ["patata", "papa"], "eu": ["patata"]}],
    )
    family: str = Field(
        default="",
        description="Botanical family (e.g., Solanaceae)",
    )
    genus: str = Field(default="", description="Genus name")
    kingdom: str = Field(default="Plantae", description="Taxonomic kingdom")
    synonyms: list[TaxonSynonym] = Field(
        default_factory=list,
        description="Accepted synonyms for this taxon",
    )
    life_form: str = Field(
        default="",
        description="Life form: tree, shrub, herb, climber, etc.",
    )
    growth_habit: str = Field(
        default="",
        description="Growth habit: erect, prostrate, climbing, etc.",
    )
    life_cycle: str = Field(
        default="",
        description="Life cycle: annual, biennial, perennial",
    )
