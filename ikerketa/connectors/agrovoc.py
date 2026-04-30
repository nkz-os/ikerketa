"""AGROVOC connector — SPARQL-based extraction from FAO AGROVOC thesaurus.

Extracts taxonomic hierarchy for plants, pests, and plant diseases
using the AGROVOC SPARQL endpoint. Filtered to 6 languages (en, es, eu, ca, fr, pt)
and scoped to agronomically relevant concept trees.

Rate limiting: Respects FAO endpoint limits by using pagination (LIMIT/OFFSET)
and avoiding massive unrestricted queries.
"""

from __future__ import annotations

import time
from typing import Any

from SPARQLWrapper import JSON, SPARQLWrapper

from ikerketa.config import settings
from ikerketa.connectors.base import AbstractConnector, ConnectorError
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import (
    BaseEntity,
    BaseRelationship,
    DataSource,
    RawRecord,
)
from ikerketa.models.ontology import OntologyConcept, SemanticRelation, SemanticRelationType
from ikerketa.models.taxonomy import Taxon

_log = get_logger(__name__)

# ── AGROVOC root concept URIs (verified via SPARQL) ─────────────────
ROOT_CONCEPTS = {
    # Agriculture
    "c_5993": "plants",
    "c_5741": "pests",
    "c_5962": "plant diseases",
    "c_16196": "plant pests",
    "c_8347": "weeds",
    "c_8dcb26c2": "insects",
    "c_918": "biological control",
    "c_920": "biological control agents",
    "c_7156": "soil",
    "c_2867": "fertilizers",
    # Livestock (ganadería)
    "c_4225": "livestock",
    "c_331": "animal breeds",
    "c_157": "animal diseases",
    "c_380": "animal feeding",
    "c_2847": "feed crops",
    # Forestry (silvicultura)
    "c_3055": "forestry",
    "c_3104": "forest trees",
    "c_3116": "forest products",
    "c_28947": "agroforestry",
    # Integrated systems (sistemas integrados)
    "c_12040": "silvopastoral systems",
    "c_12039": "agrisilvicultural systems",
}

AGROVOC_BASE = "http://aims.fao.org/aos/agrovoc/"

# Languages to extract (strategic requirement)
LANGUAGES = ("en", "es", "eu", "ca", "fr", "pt")

# Pagination defaults (avoid overloading FAO endpoint)
DEFAULT_PAGE_SIZE = 200
MAX_PAGES = 500  # Safety: 500 * 200 = 100,000 max concepts

# Delay between paginated queries (seconds)
QUERY_DELAY = 0.5


def _build_narrower_query(root_uri: str, langs: tuple[str, ...], limit: int, offset: int) -> str:
    """Build SPARQL query to fetch concepts narrower than a root concept.

    Uses skos:broader transitively to walk down from the root.
    Fetches prefLabel and altLabel in the specified languages.
    """
    lang_filter = " || ".join(f'lang(?prefLabel) = "{lang}"' for lang in langs)
    alt_lang_filter = " || ".join(f'lang(?altLabel) = "{lang}"' for lang in langs)

    return f"""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX skosxl: <http://www.w3.org/2008/05/skos-xl#>

    SELECT DISTINCT ?concept ?prefLabel ?altLabel ?broader
    WHERE {{
        ?concept skos:broader+ <{root_uri}> .
        ?concept skos:prefLabel ?prefLabel .
        FILTER({lang_filter})
        OPTIONAL {{
            ?concept skos:altLabel ?altLabel .
            FILTER({alt_lang_filter})
        }}
        OPTIONAL {{
            ?concept skos:broader ?broader .
        }}
    }}
    ORDER BY ?concept
    LIMIT {limit}
    OFFSET {offset}
    """


class Connector(AbstractConnector):
    """AGROVOC SPARQL connector.

    Fetches ontology concepts from AGROVOC using paginated SPARQL queries,
    scoped to agronomically relevant concept subtrees.
    """

    def __init__(self) -> None:
        super().__init__()
        self._sparql = SPARQLWrapper(settings.agrovoc_sparql_endpoint)
        self._sparql.setReturnFormat(JSON)
        self._sparql.addCustomHttpHeader("User-Agent", "IkerKeta/0.1.0")

    @property
    def source_name(self) -> DataSource:
        return DataSource.AGROVOC

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Fetch concepts from AGROVOC SPARQL endpoint.

        Args:
            limit: Maximum total concepts to fetch across all root concepts.
                   None = fetch all (capped by MAX_PAGES safety).
            **params:
                roots: list of root concept IDs to crawl (default: all ROOT_CONCEPTS)
                page_size: SPARQL LIMIT per query (default: DEFAULT_PAGE_SIZE)

        Returns:
            List of RawRecord, one per unique concept.
        """
        roots = params.get("roots", list(ROOT_CONCEPTS.keys()))
        page_size = params.get("page_size", DEFAULT_PAGE_SIZE)
        all_records: dict[str, RawRecord] = {}  # keyed by concept URI to dedup
        total_limit = limit or (MAX_PAGES * page_size)

        self._log.info(
            "agrovoc_fetch_start",
            roots=roots,
            languages=LANGUAGES,
            page_size=page_size,
            total_limit=total_limit,
        )

        for root_id in roots:
            root_uri = f"{AGROVOC_BASE}{root_id}"
            root_label = ROOT_CONCEPTS.get(root_id, root_id)
            self._log.info("crawling_root", root_id=root_id, label=root_label)

            offset = 0
            page = 0

            while page < MAX_PAGES and len(all_records) < total_limit:
                query = _build_narrower_query(root_uri, LANGUAGES, page_size, offset)

                try:
                    self._sparql.setQuery(query)
                    results = self._sparql.query().convert()
                except Exception as exc:
                    self._log.error(
                        "sparql_query_failed",
                        root=root_id,
                        offset=offset,
                        error=str(exc),
                    )
                    raise ConnectorError(f"SPARQL query failed for {root_id} at offset {offset}: {exc}") from exc

                bindings = results.get("results", {}).get("bindings", [])
                if not bindings:
                    self._log.debug("root_exhausted", root=root_id, total_fetched=len(all_records))
                    break

                # Group bindings by concept URI (one concept can appear in multiple rows
                # due to multiple labels/languages)
                for b in bindings:
                    concept_uri = b["concept"]["value"]

                    if concept_uri not in all_records:
                        all_records[concept_uri] = RawRecord(
                            source_name=DataSource.AGROVOC,
                            record_id=concept_uri,
                            data={
                                "uri": concept_uri,
                                "pref_labels": {},
                                "alt_labels": {},
                                "broader_uris": set(),
                                "root": root_id,
                            },
                        )

                    record_data = all_records[concept_uri].data

                    # Collect prefLabel
                    if "prefLabel" in b:
                        lang = b["prefLabel"].get("xml:lang", "")
                        label = b["prefLabel"]["value"]
                        if lang:
                            record_data["pref_labels"][lang] = label

                    # Collect altLabel
                    if "altLabel" in b and b["altLabel"]["value"]:
                        lang = b["altLabel"].get("xml:lang", "")
                        label = b["altLabel"]["value"]
                        if lang:
                            if lang not in record_data["alt_labels"]:
                                record_data["alt_labels"][lang] = []
                            if label not in record_data["alt_labels"][lang]:
                                record_data["alt_labels"][lang].append(label)

                    # Collect broader
                    if "broader" in b and b["broader"]["value"]:
                        record_data["broader_uris"].add(b["broader"]["value"])

                page += 1
                offset += page_size

                self._log.debug(
                    "page_fetched",
                    root=root_id,
                    page=page,
                    bindings=len(bindings),
                    total_concepts=len(all_records),
                )

                # Rate limiting: small delay between queries
                if bindings:
                    time.sleep(QUERY_DELAY)

                if len(all_records) >= total_limit:
                    break

        # Convert sets to lists for serialization
        for record in all_records.values():
            record.data["broader_uris"] = list(record.data["broader_uris"])

        self._log.info("agrovoc_fetch_complete", total_concepts=len(all_records))
        return list(all_records.values())

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform AGROVOC raw records into OntologyConcept entities.

        Also generates SemanticRelation relationships for broader/narrower links.
        """
        entities: list[BaseEntity] = []
        relationships: list[BaseRelationship] = []

        for record in raw_records:
            uri = record.data["uri"]
            pref_labels = record.data.get("pref_labels", {})
            alt_labels = record.data.get("alt_labels", {})
            broader_uris = record.data.get("broader_uris", [])

            # Extract local concept ID from URI
            concept_id = uri.split("/")[-1] if "/" in uri else uri

            # Determine scientific name from English prefLabel
            en_label = pref_labels.get("en", pref_labels.get("es", ""))

            concept = OntologyConcept(
                source_name=DataSource.AGROVOC,
                source_record_id=concept_id,
                agrovoc_uri=uri,
                concept_uri=uri,
                ontology_prefix="AGROVOC",
                concept_id=concept_id,
                pref_labels=pref_labels,
                alt_labels=alt_labels,
                broader_uris=broader_uris,
                raw_record={
                    "uri": uri,
                    "pref_labels": pref_labels,
                    "alt_labels": alt_labels,
                    "broader_uris": broader_uris,
                    "root": record.data.get("root", ""),
                },
            )
            entities.append(concept)

            # Create broader relationships
            for broader_uri in broader_uris:
                rel = SemanticRelation(
                    source_name=DataSource.AGROVOC,
                    relationship_type=SemanticRelationType.BROADER.value,
                    source_uri=uri,
                    target_uri=broader_uri,
                    source_agrovoc_uri=uri,
                    target_agrovoc_uri=broader_uri,
                    relation_type=SemanticRelationType.BROADER,
                    source_ontology="AGROVOC",
                )
                relationships.append(rel)

        self._log.info(
            "agrovoc_transform_complete",
            entities=len(entities),
            relationships=len(relationships),
        )
        return entities, relationships
