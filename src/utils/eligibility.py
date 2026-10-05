"""Política compartida de elegibilidad para recomendaciones de ofertas."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Mapping

logger = logging.getLogger(__name__)

HARD_BLOCK_CODES = frozenset({"requisito_imposible", "practicas"})
REVIEW_BLOCK_CODES = frozenset({"otro"})
APPLY_BLOCK_CODES = HARD_BLOCK_CODES | REVIEW_BLOCK_CODES


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    REVIEW = "review"
    BLOCKED = "blocked"


def _normalized_block(value: Any) -> str | None:
    if value is None:
        return None
    block = str(value).strip()
    if not block or block.lower() in {"none", "null"}:
        return None
    return block.lower()


def eligibility_status(row: Mapping[str, Any]) -> EligibilityStatus:
    """Return the single policy status for a scored offer.

    Hard blockers are never sendable. Any other non-empty blocker, including
    an unknown future code, is sendable only as a review item.
    """
    block = _normalized_block(row.get("apply_block"))
    if block is None:
        return EligibilityStatus.ELIGIBLE
    if block in HARD_BLOCK_CODES:
        return EligibilityStatus.BLOCKED
    if block not in REVIEW_BLOCK_CODES:
        logger.warning(
            "Código apply_block desconocido %r (offer_id=%s); requiere revisión",
            block,
            row.get("id", row.get("offer_id", "desconocido")),
        )
    return EligibilityStatus.REVIEW


def is_eligible(row: Mapping[str, Any], status: EligibilityStatus | None = None) -> bool:
    """Whether the offer may be sent; review items are sendable as REVISAR."""
    resolved = status or eligibility_status(row)
    return resolved is not EligibilityStatus.BLOCKED


def sendable_sql_predicate(alias: str = "e") -> tuple[str, tuple[str, ...]]:
    """Return the SQL filter equivalent of :func:`is_eligible`.

    Hard-block codes are bound from the same constant set used by the Python
    policy, so a new code cannot silently diverge between the two paths.
    """
    expression = (
        f"LOWER(TRIM(COALESCE({alias}.apply_block, ''))) "
        f"NOT IN ({', '.join('?' for _ in HARD_BLOCK_CODES)})"
    )
    return expression, tuple(sorted(HARD_BLOCK_CODES))


def recommendation_label(row: Mapping[str, Any]) -> str:
    """User-facing action label without changing the underlying match rating."""
    status_value = row.get("eligibility_status")
    status = (
        EligibilityStatus(status_value)
        if status_value in {item.value for item in EligibilityStatus}
        else eligibility_status(row)
    )
    if status is EligibilityStatus.BLOCKED:
        return "NO ELEGIBLE"
    if status is EligibilityStatus.REVIEW:
        return "REVISAR"
    return str(row.get("recommendation") or "")


def eligibility_order_sql(alias: str = "e") -> tuple[str, tuple[str, ...]]:
    """SQL sort expression matching :func:`eligibility_status`.

    Eligible offers rank first, review offers second, and hard-blocked offers
    last. The caller must bind the returned hard-block codes after its WHERE
    parameters because the CASE expression appears in ORDER BY.
    """
    expression = (
        f"CASE "
        f"WHEN {alias}.apply_block IS NULL "
        f"OR TRIM({alias}.apply_block) = '' "
        f"OR LOWER(TRIM({alias}.apply_block)) IN ('none', 'null') THEN 0 "
        f"WHEN LOWER(TRIM({alias}.apply_block)) IN ({', '.join('?' for _ in HARD_BLOCK_CODES)}) "
        f"THEN 2 ELSE 1 END"
    )
    return expression, tuple(sorted(HARD_BLOCK_CODES))
