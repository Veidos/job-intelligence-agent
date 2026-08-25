"""Capa bronze pura: archivo inmutable del HTML original (ADR-023).

Guarda cada respuesta HTTP del scraper comprimida con gzip ANTES de
parsearla. Si el parser se rompe o InfoJobs cambia su DOM, el histórico
completo puede re-parsearse sin gastar un solo request nuevo.

Lección histórica que motiva esta capa:
- jun-2026: 21 ofertas con descripción vacía tuvieron que RE-SCRAPEARSE
  porque solo existía el dato ya parseado.
- El backfill de published_at exigió un script complejo por la misma causa.
"""

from __future__ import annotations

import gzip
import hashlib
import logging
from typing import Literal

log = logging.getLogger(__name__)

RawKind = Literal["search", "detail"]


def compress_html(html: str) -> tuple[bytes, str]:
    """Comprime HTML y calcula el hash SHA-256 del contenido SIN comprimir.

    Returns:
        (html_gz, content_hash)
    """
    raw = html.encode("utf-8")
    return gzip.compress(raw, compresslevel=9), hashlib.sha256(raw).hexdigest()


def persist_raw_html(
    run_id: str,
    kind: RawKind,
    url: str,
    http_status: int | None,
    html: str,
    conn,
    offer_id: str | None = None,
) -> bool:
    """Inserta una respuesta cruda en scraper_raw_html (append-only).

    Args:
        run_id: Identificador del run del pipeline.
        kind: 'search' o 'detail'.
        url: URL exacta de la petición.
        http_status: Código de respuesta HTTP (None si no hubo respuesta).
        html: HTML original SIN comprimir.
        conn: Conexión SQLite abierta (no hace commit — el caller decide).
        offer_id: ID de la oferta (None en páginas de búsqueda).

    Returns:
        True si se insertó, False si falló (error ya loggeado).
    """
    try:
        html_gz, content_hash = compress_html(html)
        conn.execute(
            """
            INSERT INTO scraper_raw_html
                (run_id, kind, offer_id, url, http_status, html_gz, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, kind, offer_id, url, http_status, html_gz, content_hash),
        )
        return True
    except Exception as e:
        log.warning(
            "No se pudo archivar HTML (%s url=%s): %s",
            kind,
            url[:80],
            e,
        )
        return False


def decompress_raw_html(html_gz: bytes) -> str:
    """Recupera el HTML original desde su forma comprimida."""
    return gzip.decompress(html_gz).decode("utf-8")
