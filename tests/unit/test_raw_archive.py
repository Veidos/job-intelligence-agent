"""Tests de la capa bronze scraper_raw_html (ADR-023)."""

from __future__ import annotations

import gzip
import hashlib

import pytest

from src.pipeline.raw_archive import (
    compress_html,
    decompress_raw_html,
    persist_raw_html,
)

HTML_SAMPLE = "<html><body><h1>Analista de datos</h1>" + "x" * 500 + "</body></html>"


@pytest.fixture()
def archive_conn(test_engine):
    """Conexión directa al engine con schema aplicado (tabla bronze incluida)."""
    conn = test_engine
    yield conn
    conn.execute("DELETE FROM scraper_raw_html")
    conn.rollback()


class TestCompressHtml:
    def test_roundtrip_sin_perdida(self):
        gz, digest = compress_html(HTML_SAMPLE)
        assert decompress_raw_html(gz) == HTML_SAMPLE

    def test_compresion_reduccion_significativa(self):
        # HTML repetitivo debe comprimirse bien (>50%)
        gz, _ = compress_html(HTML_SAMPLE)
        assert len(gz) < len(HTML_SAMPLE.encode()) / 2

    def test_hash_sha256_sobre_contenido_sin_comprimir(self):
        gz, digest = compress_html(HTML_SAMPLE)
        expected = hashlib.sha256(HTML_SAMPLE.encode("utf-8")).hexdigest()
        assert digest == expected
        assert isinstance(gz, bytes)


class TestPersistRawHtml:
    def test_insert_detail_y_recupera_original(self, archive_conn, test_engine):
        ok = persist_raw_html(
            run_id="run-test",
            kind="detail",
            url="https://www.infojobs.net/oferta/x",
            http_status=200,
            html=HTML_SAMPLE,
            conn=archive_conn,
            offer_id="of-123",
        )
        archive_conn.commit()
        assert ok is True

        row = test_engine.execute(
            "SELECT run_id, kind, offer_id, url, http_status, html_gz, content_hash "
            "FROM scraper_raw_html WHERE run_id='run-test'"
        ).fetchone()
        assert row[0] == "run-test"
        assert row[1] == "detail"
        assert row[2] == "of-123"
        assert row[4] == 200
        assert gzip.decompress(row[5]).decode("utf-8") == HTML_SAMPLE

    def test_insert_search_con_offer_id_null(self, archive_conn, test_engine):
        ok = persist_raw_html(
            run_id="run-s",
            kind="search",
            url="https://www.infojobs.net/jobsearch/...",
            http_status=200,
            html=HTML_SAMPLE,
            conn=archive_conn,
            offer_id=None,
        )
        archive_conn.commit()
        assert ok is True
        row = test_engine.execute(
            "SELECT kind, offer_id FROM scraper_raw_html WHERE run_id='run-s'"
        ).fetchone()
        # Acceso por índice: el row_factory del engine compartido puede variar
        # según qué tests de integración lo hayan configurado antes
        assert (row[0], row[1]) == ("search", None)

    def test_kind_invalido_rechazado_por_check(self, archive_conn):
        ok = persist_raw_html(
            run_id="r",
            kind="otro",  # viola CHECK(kind IN ('search','detail'))
            url="https://x",
            http_status=200,
            html=HTML_SAMPLE,
            conn=archive_conn,
        )
        assert ok is False  # error capturado y loggeado, no propagado

    def test_append_only_permite_multiples_filas_mismo_run(self, archive_conn, test_engine):
        for i in range(3):
            persist_raw_html(
                run_id="r-multi",
                kind="search",
                url=f"https://x/{i}",
                http_status=200,
                html=HTML_SAMPLE,
                conn=archive_conn,
            )
        archive_conn.commit()
        count = test_engine.execute(
            "SELECT COUNT(*) FROM scraper_raw_html WHERE run_id='r-multi'"
        ).fetchone()[0]
        assert count == 3
