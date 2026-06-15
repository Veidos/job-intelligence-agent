"""Constantes compartidas del proyecto."""

MONTH_NAMES: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "ene": 1,
    "abr": 4,
    "ago": 8,
    "dic": 12,
}


def month_from_name(name: str) -> int | None:
    return MONTH_NAMES.get(name.lower().strip()[:3])
