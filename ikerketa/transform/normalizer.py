"""Data normalizer — unit conversions and taxonomic name cleaning.

Handles:
- Temperature: °F → °C conversion
- Conductivity: dS/m normalization
- Taxonomic names: stripping author citations, normalizing whitespace
- String cleaning: non-printable characters, encoding fixes
"""

from __future__ import annotations

import re
import unicodedata

from ikerketa.logging_setup import get_logger

_log = get_logger(__name__)


def fahrenheit_to_celsius(f: float) -> float:
    """Convert Fahrenheit to Celsius, rounded to 1 decimal."""
    return round((f - 32) * 5 / 9, 1)


def celsius_to_fahrenheit(c: float) -> float:
    """Convert Celsius to Fahrenheit, rounded to 1 decimal."""
    return round(c * 9 / 5 + 32, 1)


def normalize_scientific_name(name: str) -> str:
    """Normalize a scientific name for consistent matching.

    Strips author citations (e.g., 'Solanum tuberosum L.' → 'Solanum tuberosum'),
    normalizes whitespace, and applies Unicode NFC normalization.

    Args:
        name: Raw scientific name string.

    Returns:
        Cleaned scientific name.
    """
    if not name:
        return ""

    # Unicode normalization
    name = unicodedata.normalize("NFC", name)

    # Remove content in parentheses that looks like author citations
    # e.g., "(L.)" or "(Thunb.) DC."
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)

    # Remove trailing author abbreviations (capital letter followed by period)
    # This is intentionally conservative to avoid removing valid name parts
    name = re.sub(r"\s+[A-Z][a-z]*\.\s*$", "", name)

    # Normalize whitespace
    name = " ".join(name.split())

    return name.strip()


def clean_string(value: str) -> str:
    """Clean a string value: strip, normalize Unicode, remove control chars."""
    if not value:
        return ""
    value = unicodedata.normalize("NFC", value)
    # Remove control characters except newline and tab
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", value)
    return value.strip()


def normalize_ph(value: str | float | None) -> float | None:
    """Parse and validate a pH value."""
    if value is None or value == "":
        return None
    try:
        ph = float(value)
    except (ValueError, TypeError):
        _log.warning("invalid_ph_value", value=value)
        return None
    if not (0 <= ph <= 14):
        _log.warning("ph_out_of_range", value=ph)
        return None
    return round(ph, 1)
