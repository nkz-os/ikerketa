"""Models __init__ — re-exports all domain models for convenient import."""

from ikerketa.models.base import (
    BaseEntity,
    BaseRelationship,
    ConnectorResult,
    DataSource,
    RawRecord,
    ValidationReport,
    ValidationResult,
)
from ikerketa.models.crop import ClimaticProfile, Crop, EdaphicProfile
from ikerketa.models.ontology import OntologyConcept, SemanticRelation
from ikerketa.models.pest import GDDModel, LifeStage, Pest
from ikerketa.models.regulation import ActiveSubstance, Regulation
from ikerketa.models.relationship import CompanionRelation, HostAssociation, NaturalEnemy
from ikerketa.models.taxonomy import Taxon, TaxonSynonym

__all__ = [
    # Base
    "BaseEntity",
    "BaseRelationship",
    "ConnectorResult",
    "DataSource",
    "RawRecord",
    "ValidationReport",
    "ValidationResult",
    # Taxonomy
    "Taxon",
    "TaxonSynonym",
    # Crop
    "ClimaticProfile",
    "Crop",
    "EdaphicProfile",
    # Pest
    "GDDModel",
    "LifeStage",
    "Pest",
    # Relationships
    "CompanionRelation",
    "HostAssociation",
    "NaturalEnemy",
    # Regulation
    "ActiveSubstance",
    "Regulation",
    # Ontology
    "OntologyConcept",
    "SemanticRelation",
]
