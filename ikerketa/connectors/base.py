"""Abstract connector base — the reusable interface for ALL data domains.

Every data source connector (agronomic, livestock, forestry, etc.)
implements this interface. The base class provides:
- Standardized fetch → transform → validate → export pipeline
- Automatic retry with exponential backoff
- Rate limiting compliance
- Structured logging of every operation
- Data integrity hashing
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ikerketa.config import settings
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import (
    BaseEntity,
    BaseRelationship,
    ConnectorResult,
    DataSource,
    RawRecord,
    ValidationReport,
    ValidationResult,
)

_log = get_logger(__name__)


class ConnectorError(Exception):
    """Base exception for connector failures."""


class RateLimitError(ConnectorError):
    """Raised when an API rate limit is hit."""


class AuthenticationError(ConnectorError):
    """Raised when API authentication fails."""


class AbstractConnector(ABC):
    """Base class for all data source connectors.

    Subclasses MUST implement:
    - source_name: DataSource property
    - fetch(): Retrieve raw records from the source
    - transform(): Convert raw records to domain entities

    Subclasses MAY override:
    - validate(): Apply domain-specific validation rules
    - get_http_client(): Customize HTTP client configuration
    """

    def __init__(self) -> None:
        self._log = get_logger(f"connector.{self.source_name.value}")
        self._http_client: httpx.Client | None = None

    @property
    @abstractmethod
    def source_name(self) -> DataSource:
        """Canonical name of this data source."""
        ...

    @abstractmethod
    def fetch(self, *, limit: int | None = None, **params: Any) -> list[RawRecord]:
        """Fetch raw records from the data source.

        Args:
            limit: Maximum number of records to fetch (None = all).
            **params: Source-specific parameters.

        Returns:
            List of raw records as received from the source.

        Raises:
            ConnectorError: On fetch failure.
        """
        ...

    @abstractmethod
    def transform(self, raw_records: list[RawRecord]) -> tuple[list[BaseEntity], list[BaseRelationship]]:
        """Transform raw records into domain entities and relationships.

        Args:
            raw_records: Raw records from fetch().

        Returns:
            Tuple of (entities, relationships).
        """
        ...

    def validate(self, entities: list[BaseEntity]) -> ValidationReport:
        """Validate transformed entities against quality rules.

        Default implementation checks for:
        - Presence of at least one identifier key
        - Non-empty source_name
        - Valid data_hash

        Subclasses can override for domain-specific validation.

        Args:
            entities: Transformed entities to validate.

        Returns:
            ValidationReport with per-record results.
        """
        results: list[ValidationResult] = []
        valid_count = 0

        for entity in entities:
            errors: list[str] = []
            warnings: list[str] = []

            # Must have at least one resolvable key
            if not entity.has_any_key():
                errors.append("Entity has no resolvable identifier (agrovoc_uri, eppo_code, or usda_symbol)")

            # Must have a data hash
            if not entity.data_hash:
                warnings.append("Missing data_hash — integrity verification disabled")

            # Must have raw_record for audit trail
            if not entity.raw_record:
                warnings.append("Missing raw_record — audit trail incomplete")

            is_valid = len(errors) == 0
            if is_valid:
                valid_count += 1

            entity_id = entity.eppo_code or entity.agrovoc_uri or entity.usda_symbol or "unknown"
            results.append(ValidationResult(
                is_valid=is_valid,
                entity_id=entity_id,
                errors=errors,
                warnings=warnings,
            ))

        report = ValidationReport(
            source_name=self.source_name,
            total_records=len(entities),
            valid_records=valid_count,
            invalid_records=len(entities) - valid_count,
            results=results,
        )

        self._log.info(
            "validation_complete",
            total=report.total_records,
            valid=report.valid_records,
            invalid=report.invalid_records,
            success_rate=f"{report.success_rate:.1%}",
        )
        return report

    def run(self, *, limit: int | None = None, **params: Any) -> ConnectorResult:
        """Execute the full pipeline: fetch → transform → validate.

        This is the main entry point for running a connector.

        Args:
            limit: Maximum records to fetch.
            **params: Source-specific parameters.

        Returns:
            ConnectorResult with entities, relationships, and validation report.
        """
        start_time = time.monotonic()
        self._log.info("connector_start", source=self.source_name.value, limit=limit)

        try:
            # Fetch
            raw_records = self.fetch(limit=limit, **params)
            self._log.info("fetch_complete", record_count=len(raw_records))

            # Transform
            entities, relationships = self.transform(raw_records)
            self._log.info(
                "transform_complete",
                entity_count=len(entities),
                relationship_count=len(relationships),
            )

            # Compute integrity hashes
            for entity in entities:
                entity.compute_hash()

            # Validate
            report = self.validate(entities)

            duration = time.monotonic() - start_time
            self._log.info("connector_complete", duration_seconds=f"{duration:.2f}")

            return ConnectorResult(
                source_name=self.source_name,
                entities=entities,
                relationships=relationships,
                validation=report,
                duration_seconds=duration,
            )

        except Exception as exc:
            duration = time.monotonic() - start_time
            self._log.error(
                "connector_failed",
                error=str(exc),
                duration_seconds=f"{duration:.2f}",
            )
            return ConnectorResult(
                source_name=self.source_name,
                duration_seconds=duration,
                error=str(exc),
            )

    def get_http_client(self) -> httpx.Client:
        """Get or create a configured HTTP client with timeouts.

        Reuses the client across calls for connection pooling.
        """
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.Client(
                timeout=httpx.Timeout(settings.http_timeout_seconds),
                follow_redirects=True,
                headers={"User-Agent": "IkerKeta/0.1.0 (NKZ-BioOrchestrator data pipeline)"},
            )
        return self._http_client

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, RateLimitError)),
        stop=stop_after_attempt(settings.http_max_retries),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=60,
        ),
        reraise=True,
    )
    def _http_get(self, url: str, *, params: dict[str, Any] | None = None,
                  headers: dict[str, str] | None = None) -> httpx.Response:
        """HTTP GET with automatic retry and rate limit handling.

        Respects Retry-After headers from API responses.

        Args:
            url: Target URL.
            params: Query parameters.
            headers: Additional headers.

        Returns:
            httpx.Response

        Raises:
            RateLimitError: On 429 status (will be retried).
            AuthenticationError: On 401/403 status.
            ConnectorError: On other HTTP errors.
        """
        client = self.get_http_client()
        self._log.debug("http_get", url=url, params=params)

        response = client.get(url, params=params, headers=headers)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "5")
            wait_seconds = int(retry_after) if retry_after.isdigit() else 5
            self._log.warning("rate_limited", url=url, retry_after=wait_seconds)
            time.sleep(wait_seconds)
            raise RateLimitError(f"Rate limited by {url}, retry after {wait_seconds}s")

        if response.status_code in (401, 403):
            raise AuthenticationError(
                f"Authentication failed for {url}: {response.status_code}"
            )

        if response.status_code >= 400:
            raise ConnectorError(
                f"HTTP {response.status_code} from {url}: {response.text[:200]}"
            )

        return response

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._http_client and not self._http_client.is_closed:
            self._http_client.close()
            self._log.debug("http_client_closed")

    def __enter__(self) -> AbstractConnector:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
