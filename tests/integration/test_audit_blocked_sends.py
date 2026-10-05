"""Synthetic SQLite tests for the read-only blocked-send audit."""

from __future__ import annotations

from datetime import date
from io import StringIO


def _insert_blocked_offer(cursor, source_id, block, score, sent, sent_at=None):
    cursor.execute(
        """INSERT INTO offers
           (source_id, title, company_name, fetched_at, is_active, relevance_flag)
           VALUES (?, ?, ?, '2026-10-01 12:00:00', 1, 'core')""",
        (source_id, f"Role {source_id}", "Audit Co"),
    )
    offer_id = cursor.execute("SELECT last_insert_rowid()").fetchone()[0]
    cursor.execute(
        """INSERT INTO offer_evaluations
           (offer_id, match_score, recommendation, apply_block,
            sent_via_telegram, sent_at)
           VALUES (?, ?, 'Aplicar', ?, ?, ?)""",
        (offer_id, score, block, int(sent), sent_at),
    )


def test_audit_lists_high_score_blocks_and_only_fails_for_post_fix_hard_send(test_db):
    _insert_blocked_offer(
        test_db, "AUDIT-HIST", "requisito_imposible", 80, True, "2026-10-04 10:00:00"
    )
    _insert_blocked_offer(test_db, "AUDIT-PENDING", "practicas", 90, False)
    _insert_blocked_offer(test_db, "AUDIT-REVIEW", "otro", 95, True, "2026-10-06 10:00:00")

    from src.pipeline.audit_blocked_sends import audit_records

    report = audit_records(test_db.connection, fix_date=date(2026, 10, 5))

    assert report["failed"] is False
    assert len(report["sent_blockers"]) == 2
    assert len(report["over_threshold"]) == 3
    assert len(report["unsent_hard"]) == 1
    assert report["selectable_hard"] == []

    from src.pipeline.audit_blocked_sends import print_audit

    output = StringIO()
    print_audit(report, output=output)
    assert "histórico previo al fix" in output.getvalue()
    assert "bloqueadas correctamente" in output.getvalue()


def test_audit_fails_for_hard_block_sent_on_or_after_fix(test_db):
    _insert_blocked_offer(
        test_db, "AUDIT-POST-FIX", "requisito_imposible", 90, True, "2026-10-05 00:00:00"
    )

    from src.pipeline.audit_blocked_sends import audit_records

    report = audit_records(test_db.connection, fix_date=date(2026, 10, 5))

    assert report["failed"] is True
    assert len(report["hard_sent_after_fix"]) == 1


def test_audit_fails_if_send_candidate_query_returns_hard_block(test_db, monkeypatch):
    from src.pipeline import audit_blocked_sends

    monkeypatch.setattr(
        audit_blocked_sends,
        "get_send_candidates",
        lambda **kwargs: [{"id": 999, "apply_block": "practicas"}],
    )

    report = audit_blocked_sends.audit_records(test_db.connection)

    assert report["failed"] is True
    assert report["selectable_hard"][0]["id"] == 999
