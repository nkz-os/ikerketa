"""AgroPortal connector — SPARQL/REST access to agronomic ontologies.

AgroPortal hosts C3PO (Crop Ontology), CO (Crop Ontology), AgrO
(Agronomy Ontology), and other semantic resources for agriculture.

Endpoint: https://agroportal.lirmm.fr/
API docs: https://data.agroportal.lirmm.fr/documentation

Uses the AgroPortal REST API v1 (no auth required for public ontologies).
"""

from __future__ import annotations

import time
from typing import Any

from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import (
    BaseEntity,
    BaseRelationship,
    DataSource,
    RawRecord,
)
from ikerketa.models.ontology import OntologyConcept, SemanticRelation, SemanticRelationType

_log = get_logger(__name__)

# AgroPortal REST API base
BASE_URL = "https://data.agroportal.lirmm.fr"

# Target ontology acronyms
TARGET_ONTOLOGIES = ["CO_330", "AGRO", "C3PO"]

# Rate limit: 1 req/s
REQUEST_INTERVAL = 1.0

# Max classes per ontology
DEFAULT_PAGE_SIZE = 100


class Connector(AbstractConnector):
    """AgroPortal REST API connector for agronomic ontologies."""

    @property
    def source_name(self) -> DataSource:
        return DataSource.AGROPORTAL

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Fetch ontology classes from AgroPortal REST API.

        Args:
            limit: Maximum concepts per ontology.
            **params:
                ontologies: List of ontology acronyms (default: CO_330, AGRO, C3PO)
                api_key: AgroPortal API key (optional, for higher rate limits)
        """
        ontologies = params.get("ontologies", TARGET_ONTOLOGIES)
        api_key = params.get("api_key", "")

        self._log.info("agroportal_fetch_start", ontologies=ontologies, limit=limit)
        records: list[RawRecord] = []

        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"apikey token={api_key}"

        for ontology in ontologies:
            page = 1
            ontology_count = 0

            while True:
                if limit and ontology_count >= limit:
                    break

                try:
                    time.sleep(REQUEST_INTERVAL)
                    response = self._http_get(
                        f"{BASE_URL}/ontologies/{ontology}/classes",
                        params={
                            "page": page,
                            "pagesize": DEFAULT_PAGE_SIZE,
                            "display": "prefLabel,synonym,definition,subClassOf",
                        },
                        headers=headers,
                    )
                    data = response.json()
                except Exception as exc:
                    self._log.warning(
                        "agroportal_fetch_error",
                        ontology=ontology,
                        page=page,
                        error=str(exc),
                    )
                    break

                # Extract class list
                classes = data.get("collection", data) if isinstance(data, dict) else data
                if not isinstance(classes, list) or not classes:
                    break

                for cls_data in classes:
                    if not isinstance(cls_data, dict):
                        continue

                    class_id = cls_data.get("@id", cls_data.get("id", ""))
                    if not class_id:
                        continue

                    records.append(RawRecord(
                        source_name=DataSource.AGROPORTAL,
                        record_id=class_id,
                        data={
                            "class_id": class_id,
                            "ontology": ontology,
                            "pref_label": cls_data.get("prefLabel", ""),
                            "synonyms": cls_data.get("synonym", []),
                            "definition": cls_data.get("definition", []),
                            "sub_class_of": cls_data.get("subClassOf", []),
                            "raw": cls_data,
                        },
                    ))
                    ontology_count += 1

                # Pagination
                next_page = data.get("nextPage") if isinstance(data, dict) else None
                if not next_page or len(classes) < DEFAULT_PAGE_SIZE:
                    break
                page += 1

            self._log.info("agroportal_ontology_done", ontology=ontology, concepts=ontology_count)

        self._log.info("agroportal_fetch_complete", total=len(records))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform AgroPortal classes into OntologyConcept entities."""
        entities: list[BaseEntity] = []
        relationships: list[BaseRelationship] = []

        for record in raw_records:
            d = record.data
            class_id = d.get("class_id", "")
            ontology = d.get("ontology", "")
            pref_label = d.get("pref_label", "")

            if not class_id or not pref_label:
                continue

            # Build labels dict — AgroPortal returns labels as string or list
            pref_labels: dict[str, str] = {}
            if isinstance(pref_label, str):
                pref_labels["en"] = pref_label
            elif isinstance(pref_label, dict):
                pref_labels = pref_label

            # Extract concept ID from URI
            concept_id = class_id.rsplit("/", maxsplit=1)[-1] if "/" in class_id else class_id

            # Parse synonyms
            synonyms = d.get("synonyms", [])
            alt_labels: dict[str, list[str]] = {}
            if isinstance(synonyms, list) and synonyms:
                alt_labels["en"] = [str(s) for s in synonyms if s]

            entity = OntologyConcept(
                source_name=DataSource.AGROPORTAL,
                source_record_id=class_id,
                concept_uri=class_id,
                ontology_prefix=ontology,
                concept_id=concept_id,
                pref_labels=pref_labels,
                alt_labels=alt_labels,
                agrovoc_uri=class_id if "agrovoc" in class_id.lower() else None,
                raw_record=d,
            )
            entities.append(entity)

            # Create subClassOf relationships
            sub_class_of = d.get("sub_class_of", [])
            if isinstance(sub_class_of, list):
                for parent_uri in sub_class_of:
                    if isinstance(parent_uri, str) and parent_uri:
                        rel = SemanticRelation(
                            source_name=DataSource.AGROPORTAL,
                            relationship_type=SemanticRelationType.BROADER.value,
                            source_uri=class_id,
                            target_uri=parent_uri,
                            source_agrovoc_uri=class_id,
                            target_agrovoc_uri=parent_uri,
                            relation_type=SemanticRelationType.SUBCLASS_OF,
                            source_ontology=ontology,
                        )
                        relationships.append(rel)

        self._log.info("agroportal_transform_complete", entities=len(entities), relationships=len(relationships))
        return entities, relationships
