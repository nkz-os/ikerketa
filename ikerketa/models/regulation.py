"""Regulation models — EU regulatory compliance for organic agriculture.

Covers active substances (DG SANTE), MRL data, and EU regulation
references for filtering organic-compatible inputs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ikerketa.models.base import BaseEntity


class MRLEntry(BaseModel):
    """Maximum Residue Level for a substance-crop combination."""

    crop_eppo_code: str = Field(description="EPPO code of the crop")
    crop_name: str = Field(default="")
    mrl_mg_kg: float = Field(ge=0, description="MRL in mg/kg")
    notes: str = Field(default="")


class ActiveSubstance(BaseEntity):
    """An active substance in the EU pesticides database (DG SANTE).

    The organic_compatible flag is the hard boolean filter that
    the NKZ-BioOrchestrator uses to suppress non-organic pathways
    in the knowledge graph.
    """

    substance_name: str = Field(description="Common name of the active substance")
    eu_substance_id: str = Field(
        default="",
        description="EU-internal identifier for this substance",
    )

    # Approval status
    is_approved_eu: bool = Field(
        description="Whether the substance is currently approved in the EU",
    )
    approval_start_date: str = Field(default="", description="ISO date of approval start")
    approval_end_date: str = Field(default="", description="ISO date of approval expiry")

    # Organic compatibility
    organic_compatible: bool = Field(
        default=False,
        description="Whether this substance is permitted under EU organic regulation",
    )
    substance_category: str = Field(
        default="",
        description="Category: low_risk, basic_substance, candidate_substitution, etc.",
    )

    # Risk profile
    bee_toxicity: str = Field(
        default="",
        description="Bee toxicity classification: none, low, moderate, high",
    )
    aquatic_toxicity: str = Field(
        default="",
        description="Aquatic organism toxicity: none, low, moderate, high",
    )

    # MRL data
    mrl_entries: list[MRLEntry] = Field(
        default_factory=list,
        description="Maximum Residue Levels per crop",
    )


class Regulation(BaseModel):
    """A regulatory framework node (e.g., EU 2021/1165).

    Serves as the anchor node in the knowledge graph for
    compliance auditing.
    """

    regulation_id: str = Field(
        description="Regulation identifier, e.g., EU_2021_1165",
    )
    title: str = Field(description="Full title of the regulation")
    context: str = Field(
        default="organic_production",
        description="Regulatory context: organic_production, plant_protection, etc.",
    )
    url: str = Field(default="", description="Official publication URL")

    # Substances linked to this regulation
    approved_substance_ids: list[str] = Field(
        default_factory=list,
        description="EU substance IDs or EPPO codes approved under this regulation",
    )
