"""DG SANTE connector — EU Pesticides Database REST API.

Fetches active substance approval data and MRL information from
the European Commission DG SANTE pesticides database.

API: https://ec.europa.eu/food/plant/pesticides/eu-pesticides-database/
Docs: Pesticides-APIs-V3.0.pdf on DG SANTE Developer Portal

No authentication required — public API.
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
from ikerketa.models.regulation import ActiveSubstance, MRLEntry

_log = get_logger(__name__)

# DG SANTE API base URL
BASE_URL = "https://ec.europa.eu/food/plant/pesticides/eu-pesticides-database/rest"

# Conservative rate limit: 2 req/s
REQUEST_INTERVAL = 0.5

# Substance category mapping
CATEGORY_MAP = {
    "APPROVED": "approved",
    "NOT_APPROVED": "not_approved",
    "LOW_RISK": "low_risk",
    "BASIC": "basic_substance",
    "CANDIDATE_FOR_SUBSTITUTION": "candidate_substitution",
}


class Connector(AbstractConnector):
    """DG SANTE EU Pesticides Database REST connector.

    Fetches active substance data from the public API.
    Falls back to local CSV if API is unavailable.
    """

    @property
    def source_name(self) -> DataSource:
        return DataSource.DG_SANTE

    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Fetch active substance data from DG SANTE API or local CSV.

        Args:
            limit: Maximum substances to fetch.
            **params:
                csv_path: If provided, read from local CSV instead of API.
        """
        csv_path = params.get("csv_path")
        if csv_path:
            return self._fetch_csv(csv_path, limit=limit)
        return self._fetch_api(limit=limit)

    def _fetch_api(self, *, limit: int | None = None) -> list[RawRecord]:
        """Fetch from DG SANTE REST API."""
        self._log.info("dg_sante_fetch_start", mode="api", limit=limit)

        records: list[RawRecord] = []
        page = 0
        page_size = min(limit or 100, 100)

        while True:
            if limit and len(records) >= limit:
                records = records[:limit]
                break

            try:
                time.sleep(REQUEST_INTERVAL)
                response = self._http_get(
                    f"{BASE_URL}/active-substance",
                    params={
                        "pageSize": page_size,
                        "pageNumber": page,
                    },
                )
                data = response.json()
            except Exception as exc:
                if not records:
                    raise ConnectorError(
                        f"DG SANTE API unavailable: {exc}. "
                        "Download CSV from the EU Pesticides Database "
                        "and use csv_path parameter."
                    ) from exc
                self._log.warning("api_fetch_partial", error=str(exc), records_so_far=len(records))
                break

            # Handle both array and paginated object responses
            items = data if isinstance(data, list) else data.get("content", data.get("items", []))

            if not items:
                break

            for item in items:
                substance_id = str(item.get("id", item.get("substanceId", "")))
                records.append(RawRecord(
                    source_name=DataSource.DG_SANTE,
                    record_id=substance_id,
                    data=item if isinstance(item, dict) else {"raw": item},
                ))

            page += 1

            # Check if we've exhausted pages
            total_pages = data.get("totalPages") if isinstance(data, dict) else None
            if total_pages is not None and page >= total_pages:
                break
            if len(items) < page_size:
                break

        self._log.info("dg_sante_fetch_complete", total=len(records))
        return records

    def _fetch_csv(self, csv_path: str, *, limit: int | None = None) -> list[RawRecord]:
        """Fallback: read from local CSV."""
        import csv
        from pathlib import Path

        path = Path(csv_path)
        if not path.exists():
            raise ConnectorError(f"DG SANTE CSV not found at {path}")

        self._log.info("dg_sante_fetch_start", mode="csv", path=str(path))
        records: list[RawRecord] = []

        with path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                substance_id = row.get("id", row.get("substance_id", f"row_{i}"))
                records.append(RawRecord(
                    source_name=DataSource.DG_SANTE,
                    record_id=str(substance_id),
                    data={k.strip().lower(): v.strip() for k, v in row.items() if v},
                ))

        self._log.info("dg_sante_fetch_complete", total=len(records))
        return records

    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform DG SANTE data into ActiveSubstance entities."""
        entities: list[BaseEntity] = []

        for record in raw_records:
            d = record.data

            # Extract substance name (API may use different field names)
            substance_name = (
                d.get("substanceName", "")
                or d.get("substance_name", "")
                or d.get("name", "")
            )
            if not substance_name:
                continue

            # Approval status
            status = d.get("approvalStatus", d.get("status", "")).upper()
            is_approved = status in ("APPROVED", "LOW_RISK", "BASIC")

            # Category
            category = CATEGORY_MAP.get(status, status.lower() if status else "")

            # Dates
            approval_start = d.get("approvalStartDate", d.get("approval_start", ""))
            approval_end = d.get("approvalEndDate", d.get("approval_end", ""))

            # Organic compatibility
            organic = d.get("organicCompatible", d.get("organic_compatible", d.get("organic", "")))
            is_organic = str(organic).lower() in ("true", "1", "yes", "y")

            # EU substance ID
            eu_id = d.get("substanceId", d.get("eu_substance_id", record.record_id))

            entity = ActiveSubstance(
                source_name=DataSource.DG_SANTE,
                source_record_id=record.record_id,
                substance_name=substance_name,
                eu_substance_id=str(eu_id),
                is_approved_eu=is_approved,
                approval_start_date=str(approval_start),
                approval_end_date=str(approval_end),
                organic_compatible=is_organic,
                substance_category=category,
                raw_record=d,
            )
            entities.append(entity)

        self._log.info("dg_sante_transform_complete", entities=len(entities))
        return entities, []
