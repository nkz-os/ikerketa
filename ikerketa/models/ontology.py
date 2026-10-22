"""Ontology models — semantic concepts and relations from AGROVOC, AgroPortal, C3PO.

Represents SKOS/OWL concepts as structured data, enabling the pipeline
to import and flatten ontological hierarchies for Neo4j ingestion.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from ikerketa.models.base import BaseEntity, BaseRelationship, DataSource


class SemanticRelationType(str, Enum):
    """Types of semantic relationships between ontology concepts."""

    BROADER = "skos:broader"
    NARROWER = "skos:narrower"
    EXACT_MATCH = "skos:exactMatch"
    CLOSE_MATCH = "skos:closeMatch"
    RELATED = "skos:related"
    SUBCLASS_OF = "rdfs:subClassOf"
    PART_OF = "part_of"
    HAS_PART = "has_part"


class SemanticRelation(BaseRelationship):
    """A relationship between two ontology concepts.

    Extends BaseRelationship so it's compatible with ConnectorResult.
    Uses source_agrovoc_uri / target_agrovoc_uri from the base class
    to carry the concept URIs.
    """

    source_uri: str = Field(description="URI of the source concept")
    target_uri: str = Field(description="URI of the target concept")
    relation_type: SemanticRelationType  # type: ignore[assignment]
    source_ontology: str = Field(
        default="",
        description="Ontology that defines this relation (AGROVOC, C3PO, CO, etc.)",
    )


class OntologyConcept(BaseEntity):
    """A concept from an agronomic ontology (AGROVOC, C3PO, CO, AgrO).

    Designed for flattened import into Neo4j while preserving
    enough structure to reconstruct the original hierarchy.
    """

    concept_uri: str = Field(
        description="Full URI of the concept (dereferenceable)",
        examples=["http://aims.fao.org/aos/agrovoc/c_7951"],
    )
    ontology_prefix: str = Field(
        description="Short prefix: AGROVOC, C3PO, CO, AGRO",
    )
    concept_id: str = Field(
        default="",
        description="Local identifier within the ontology (e.g., c_7951)",
    )

    # Labels in multiple languages
    pref_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Preferred labels keyed by ISO 639-1 language code",
        examples=[{"en": "potato", "es": "patata", "fr": "pomme de terre"}],
    )
    alt_labels: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Alternative labels keyed by language code",
    )

    # Hierarchy
    broader_uris: list[str] = Field(
        default_factory=list,
        description="URIs of broader/parent concepts (skos:broader)",
    )
    narrower_uris: list[str] = Field(
        default_factory=list,
        description="URIs of narrower/child concepts (skos:narrower)",
    )
    related_uris: list[str] = Field(
        default_factory=list,
        description="URIs of related concepts (skos:related)",
    )

    # Cross-ontology mappings
    exact_matches: list[str] = Field(
        default_factory=list,
        description="URIs from other ontologies that are exact matches",
    )
    close_matches: list[str] = Field(
        default_factory=list,
        description="URIs from other ontologies that are close matches",
    )

    # Scope and definition
    definition: dict[str, str] = Field(
        default_factory=dict,
        description="Definitions keyed by language code",
    )
    scope_note: dict[str, str] = Field(
        default_factory=dict,
        description="Scope notes keyed by language code",
    )
