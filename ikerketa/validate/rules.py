"""Domain-specific validation rules for data quality control.

These rules go beyond Pydantic schema validation to check
semantic consistency and domain constraints.
"""

from __future__ import annotations

from ikerketa.logging_setup import get_logger
from ikerketa.models.base import BaseEntity, ValidationResult
from ikerketa.models.crop import Crop
from ikerketa.models.pest import Pest

_log = get_logger(__name__)


def validate_crop(crop: Crop) -> ValidationResult:
    """Validate a Crop entity beyond schema constraints.

    Checks:
    - Temperature ranges are physically plausible
    - pH ranges are within soil science norms
    - Growing cycle days are reasonable
    """
    errors: list[str] = []
    warnings: list[str] = []
    entity_id = crop.eppo_code or crop.agrovoc_uri or crop.scientific_name

    cp = crop.climatic_profile
    # Temperature sanity
    if cp.t_kill is not None and cp.t_kill < -60:
        errors.append(f"t_kill ({cp.t_kill}°C) below physical minimum (-60°C)")
    if cp.t_max is not None and cp.t_max > 60:
        errors.append(f"t_max ({cp.t_max}°C) above physical maximum (60°C)")
    if cp.t_kill is not None and cp.t_max is not None and cp.t_kill >= cp.t_max:
        errors.append(f"t_kill ({cp.t_kill}) >= t_max ({cp.t_max})")

    # Growing cycle
    if cp.growing_cycle_days_max is not None and cp.growing_cycle_days_max > 730:
        warnings.append(f"Growing cycle > 2 years ({cp.growing_cycle_days_max} days) — unusual")

    # Edaphic sanity
    ep = crop.edaphic_profile
    if ep.ph_min is not None and ep.ph_max is not None:
        if ep.ph_max - ep.ph_min > 8:
            warnings.append(f"Very wide pH range ({ep.ph_min}-{ep.ph_max}) — verify data")

    # Must have scientific name
    if not crop.scientific_name:
        errors.append("Crop missing scientific_name")

    return ValidationResult(
        is_valid=len(errors) == 0,
        entity_id=str(entity_id),
        errors=errors,
        warnings=warnings,
    )


def validate_pest(pest: Pest) -> ValidationResult:
    """Validate a Pest entity beyond schema constraints.

    Checks:
    - GDD model temperature thresholds are realistic
    - Life stages are in ascending GDD order
    - Host plant references exist
    """
    errors: list[str] = []
    warnings: list[str] = []
    entity_id = pest.eppo_code or pest.agrovoc_uri or pest.scientific_name

    # Must have scientific name
    if not pest.scientific_name:
        errors.append("Pest missing scientific_name")

    # GDD model validation
    gdd = pest.gdd_model
    if gdd is not None:
        if gdd.t_base_celsius < -10:
            warnings.append(f"Unusually low t_base ({gdd.t_base_celsius}°C)")
        if gdd.t_base_celsius > 25:
            warnings.append(f"Unusually high t_base ({gdd.t_base_celsius}°C)")

        # Life stages must be in ascending GDD order
        if len(gdd.stages) >= 2:
            for i in range(1, len(gdd.stages)):
                prev = gdd.stages[i - 1].gdd_cumulative
                curr = gdd.stages[i].gdd_cumulative
                if curr < prev:
                    errors.append(
                        f"GDD stages not in ascending order: "
                        f"{gdd.stages[i-1].stage_name} ({prev}) > "
                        f"{gdd.stages[i].stage_name} ({curr})"
                    )

    # Warn if no host plants
    if not pest.host_eppo_codes and not pest.host_agrovoc_uris:
        warnings.append("No host plants referenced — orphan pest record")

    return ValidationResult(
        is_valid=len(errors) == 0,
        entity_id=str(entity_id),
        errors=errors,
        warnings=warnings,
    )


def validate_entity(entity: BaseEntity) -> ValidationResult:
    """Route an entity to its domain-specific validator."""
    if isinstance(entity, Crop):
        return validate_crop(entity)
    if isinstance(entity, Pest):
        return validate_pest(entity)

    # Generic validation for other entity types
    errors: list[str] = []
    warnings: list[str] = []

    if not entity.has_any_key():
        errors.append("Entity has no resolvable identifier")

    return ValidationResult(
        is_valid=len(errors) == 0,
        entity_id=entity.eppo_code or entity.agrovoc_uri or "unknown",
        errors=errors,
        warnings=warnings,
    )
