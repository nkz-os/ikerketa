"""Base entity and relationship models with provenance tracking.

Every data record in the pipeline inherits from BaseEntity, ensuring
full traceability (source, timestamp, hash) and a composite key system
with AGROVOC URI as universal PK and EPPO Code as phytosanitary PK.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import xxhash
from pydantic import BaseModel, Field, field_validator


class DataSource(str, Enum):
    """Canonical names for data sources."""

    AGROVOC = "agrovoc"
    EPPO = "eppo"
    ECOCROP = "ecocrop"
    USDA_PLANTS = "usda_plants"
    USPEST = "uspest"
    USA_NPN = "usa_npn"
    COMPANION_PLANTING = "companion_planting"
    DG_SANTE = "dg_sante"
    CABI = "cabi"
    AGROPORTAL = "agroportal"
    FIBL = "fibl"
    # Livestock
    DADIS = "dadis"
    WAHIS = "wahis"
    FEEDIPEDIA = "feedipedia"
    # Forestry
    GLOBALTREESEARCH = "globaltreesearch"
    EUFORGEN = "euforgen"
    # IUCN removed — license incompatible with SaaS commercial use.
    # Conservation status now sourced from GBIF (CC0/CC-BY filtered) and
    # GlobalTreeSearch (BGCI, open data). The IUCNStatus enum in forestry.py
    # is renamed to ConservationStatus for the general concept.
    # Soils
    SOILGRIDS = "soilgrids"
    CPVO_VARIETIES = "cpvo_varieties"
    # Agroforestry
    AGROFORESTREE = "agroforestree"
    FORAGES = "forages"
    GLOBALLOMETREE = "globallometree"
    # EU Cover Crops & Regenerative Agriculture
    INTIA_COVER_CROPS = "intia_cover_crops"
    JRC_MARS_PHENOLOGY = "jrc_mars_phenology"
    LEGUMES_TRANSLATED = "legumes_translated"
    DIVERIMPACTS = "diverimpacts"
    ITACYL = "itacyl"
    IFAPA = "ifapa"
    COVER_CROP_KNOWLEDGE = "cover_crop_knowledge"


class BaseEntity(BaseModel):
    """Base for all domain entities.

    Provides:
    - Composite key system (agrovoc_uri, eppo_code, usda_symbol)
    - Full provenance tracking (source, timestamp, hash)
    - Raw record preservation for auditability
    """

    # ── Composite Key System ────────────────────────────────────────────
    # AGROVOC URI = Universal PK (semántico, cross-dominio)
    agrovoc_uri: str | None = Field(
        default=None,
        description="AGROVOC concept URI — universal primary key",
        examples=["http://aims.fao.org/aos/agrovoc/c_7951"],
    )
    # EPPO Code = Fitosanitario PK (strongly-typed, indexed)
    eppo_code: str | None = Field(
        default=None,
        description="EPPO 5-6 letter code — primary key for phytosanitary domain",
        examples=["SOLTU", "LYCADE"],
    )
    # USDA Symbol = Secondary enrichment key
    usda_symbol: str | None = Field(
        default=None,
        description="USDA PLANTS symbol — secondary enrichment key",
        examples=["SOTU"],
    )

    # ── Provenance Tracking ─────────────────────────────────────────────
    source_name: DataSource = Field(
        description="Canonical source that produced this record",
    )
    source_record_id: str = Field(
        default="",
        description="Original record ID within the source system",
    )
    ingestion_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of data ingestion",
    )
    data_hash: str = Field(
        default="",
        description="xxHash of the raw record for integrity verification",
    )
    raw_record: dict[str, Any] = Field(
        default_factory=dict,
        description="Original raw record as received from source (audit trail)",
    )

    @field_validator("eppo_code")
    @classmethod
    def validate_eppo_code(cls, v: str | None) -> str | None:
        """EPPO codes are 4-6 uppercase alphanumeric characters.

        Species: 5-6 letters (SOLTU, LUFTDE)
        Higher taxa: 4-6 alphanumeric with numeric prefix (1AA0G, 1SOLF)
        """
        if v is None:
            return None
        v = v.strip().upper()
        if not v.isalnum() or not (4 <= len(v) <= 6):
            msg = f"EPPO code must be 4-6 alphanumeric characters, got: {v!r}"
            raise ValueError(msg)
        return v

    def compute_hash(self) -> str:
        """Compute xxHash of the raw_record for integrity checks."""
        import json

        serialized = json.dumps(self.raw_record, sort_keys=True, default=str)
        self.data_hash = xxhash.xxh64(serialized.encode()).hexdigest()
        return self.data_hash

    def has_any_key(self) -> bool:
        """Check if this entity has at least one resolvable identifier."""
        return bool(self.agrovoc_uri or self.eppo_code or self.usda_symbol)


class BaseRelationship(BaseModel):
    """Base for all inter-entity relationships.

    Relationships connect two entities via their composite keys
    and carry provenance metadata.
    """

    # Source entity keys
    source_agrovoc_uri: str | None = None
    source_eppo_code: str | None = None

    # Target entity keys
    target_agrovoc_uri: str | None = None
    target_eppo_code: str | None = None

    # Relationship metadata
    relationship_type: str = Field(description="Semantic type of this relationship")
    evidence_source: str = Field(
        default="",
        description="Citation or URL supporting this relationship",
    )

    # Provenance
    source_name: DataSource
    ingestion_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    data_hash: str = ""
    raw_record: dict[str, Any] = Field(default_factory=dict)


class RawRecord(BaseModel):
    """A raw record as fetched from a source connector, before transformation."""

    source_name: DataSource
    record_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class ValidationResult(BaseModel):
    """Result of validating a single entity."""

    is_valid: bool
    entity_id: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """Aggregated validation report for a batch of entities."""

    source_name: DataSource
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    results: list[ValidationResult] = Field(default_factory=list)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @property
    def success_rate(self) -> float:
        if self.total_records == 0:
            return 0.0
        return self.valid_records / self.total_records


class ConnectorResult(BaseModel):
    """Output of a full connector run (fetch → transform → validate)."""

    source_name: DataSource
    entities: list[BaseEntity] = Field(default_factory=list)
    relationships: list[BaseRelationship] = Field(default_factory=list)
    validation: ValidationReport | None = None
    duration_seconds: float = 0.0
    error: str | None = None
