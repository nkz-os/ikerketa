"""JSON-LD export — produces Neo4j-compatible linked data output.

Generates JSON-LD documents that can be directly ingested by
Neo4j's neosemantics (n10s) plugin or via apoc.load.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, BaseRelationship, ConnectorResult

_log = get_logger(__name__)

# JSON-LD context for NKZ-BioOrchestrator
_CONTEXT = {
    "@context": {
        "nkz": "https://nkz.nekazari.eus/ontology/",
        "agrovoc": "http://aims.fao.org/aos/agrovoc/",
        "eppo": "https://gd.eppo.int/taxon/",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "schema": "http://schema.org/",
        "scientific_name": "nkz:scientificName",
        "eppo_code": "nkz:eppoCode",
        "agrovoc_uri": "nkz:agrovocURI",
        "source_name": "nkz:dataSource",
        "ingestion_timestamp": {
            "@id": "nkz:ingestedAt",
            "@type": "schema:DateTime",
        },
    }
}


def entity_to_jsonld(entity: BaseEntity) -> dict[str, Any]:
    """Convert a single entity to a JSON-LD node.

    Args:
        entity: The entity to convert.

    Returns:
        JSON-LD compatible dict.
    """
    # Build the @id from the best available identifier
    node_id = (
        entity.agrovoc_uri
        or (f"eppo:{entity.eppo_code}" if entity.eppo_code else None)
        or (f"usda:{entity.usda_symbol}" if entity.usda_symbol else None)
        or f"nkz:unknown_{entity.data_hash[:8]}" if entity.data_hash else "nkz:unknown"
    )

    # Determine @type from the entity class
    type_name = type(entity).__name__

    # Serialize all non-None, non-empty fields
    data = entity.model_dump(
        exclude_none=True,
        exclude_defaults=False,
        mode="json",
    )

    # Remove raw_record from export (keep it for audit, but don't ship it to Neo4j)
    data.pop("raw_record", None)

    node: dict[str, Any] = {
        "@id": node_id,
        "@type": f"nkz:{type_name}",
        **data,
    }

    return node


def relationship_to_jsonld(rel: BaseRelationship) -> dict[str, Any]:
    """Convert a relationship to a JSON-LD edge representation."""
    return {
        "@type": f"nkz:{rel.relationship_type}",
        "nkz:source": rel.source_eppo_code or rel.source_agrovoc_uri or "unknown",
        "nkz:target": rel.target_eppo_code or rel.target_agrovoc_uri or "unknown",
        **rel.model_dump(
            exclude_none=True,
            exclude={"raw_record", "source_agrovoc_uri", "source_eppo_code",
                     "target_agrovoc_uri", "target_eppo_code"},
            mode="json",
        ),
    }


def export_connector_result(result: ConnectorResult, output_dir: Path) -> Path:
    """Export a ConnectorResult to a JSON-LD file.

    Args:
        result: The connector result to export.
        output_dir: Directory to write the output file.

    Returns:
        Path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{result.source_name.value}_entities.jsonld"
    output_path = output_dir / filename

    document: dict[str, Any] = {
        **_CONTEXT,
        "@graph": [
            entity_to_jsonld(e) for e in result.entities
        ],
    }

    # Also include relationships if present
    if result.relationships:
        rel_filename = f"{result.source_name.value}_relationships.jsonld"
        rel_path = output_dir / rel_filename
        rel_doc: dict[str, Any] = {
            **_CONTEXT,
            "@graph": [
                relationship_to_jsonld(r) for r in result.relationships
            ],
        }
        with rel_path.open("w", encoding="utf-8") as f:
            json.dump(rel_doc, f, ensure_ascii=False, indent=2, default=str)
        _log.info("jsonld_relationships_exported", path=str(rel_path), count=len(result.relationships))

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=2, default=str)

    _log.info("jsonld_exported", path=str(output_path), entity_count=len(result.entities))
    return output_path
