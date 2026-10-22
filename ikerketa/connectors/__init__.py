"""Connectors package — one module per data source."""

from ikerketa.connectors.base import (
    AbstractConnector,
    AuthenticationError,
    ConnectorError,
    RateLimitError,
)

__all__ = [
    "AbstractConnector",
    "AuthenticationError",
    "ConnectorError",
    "RateLimitError",
]
