"""Security utilities: secret validation, API key management, input sanitization.

NEVER log or expose secret values. All API keys are validated at connector
initialization time — fail fast if required credentials are missing.
"""

from __future__ import annotations

import re

from ikerketa.config import settings
from ikerketa.logging_setup import get_logger

_log = get_logger(__name__)

# Characters allowed in SPARQL literal values (defense against injection)
_SPARQL_SAFE_PATTERN = re.compile(r"^[\w\s\-.,;:()/°%'+*#\[\]{}@!?&=<>]+$", re.UNICODE)


class MissingCredentialError(Exception):
    """Raised when a required API credential is not configured."""


def validate_api_token(env_var_name: str, token_value: str) -> None:
    """Validate that an API token is present and non-empty.

    Args:
        env_var_name: Name of the environment variable (for error messages).
        token_value: Actual token value to validate.

    Raises:
        MissingCredentialError: If token is empty or whitespace-only.
    """
    if not token_value or not token_value.strip():
        msg = (
            f"Required API credential '{env_var_name}' is missing or empty. "
            f"Set it in your .env file or as an environment variable."
        )
        _log.error("missing_credential", env_var=env_var_name)
        raise MissingCredentialError(msg)
    # Log that credential is present, NEVER log the value
    _log.debug(
        "credential_validated",
        env_var=env_var_name,
        length=len(token_value),
    )


def get_eppo_token() -> str:
    """Get and validate the EPPO API token."""
    validate_api_token("EPPO_API_TOKEN", settings.eppo_api_token)
    return settings.eppo_api_token


def get_dg_sante_key() -> str:
    """Get and validate the DG SANTE API key."""
    validate_api_token("DG_SANTE_API_KEY", settings.dg_sante_api_key)
    return settings.dg_sante_api_key


def sanitize_sparql_literal(value: str) -> str:
    """Sanitize a string value before embedding it in a SPARQL query.

    Prevents SPARQL injection by rejecting values with suspicious characters.
    Use parameterized queries (VALUES clause) whenever possible instead.

    Args:
        value: The string to sanitize.

    Returns:
        The sanitized string.

    Raises:
        ValueError: If the value contains potentially dangerous characters.
    """
    if not _SPARQL_SAFE_PATTERN.match(value):
        msg = f"Value contains characters not allowed in SPARQL literals: {value!r}"
        _log.warning("sparql_sanitization_failed", value_preview=value[:50])
        raise ValueError(msg)
    # Escape single quotes for SPARQL string literals
    return value.replace("'", "\\'")


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """Mask a secret value for safe logging, showing only the last N chars.

    Args:
        secret: The secret to mask.
        visible_chars: Number of characters to keep visible at the end.

    Returns:
        Masked string like '****ab3f'.
    """
    if len(secret) <= visible_chars:
        return "****"
    return "****" + secret[-visible_chars:]
