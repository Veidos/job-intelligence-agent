"""No-network tests for Telegram selection and eligibility labels."""

from __future__ import annotations

from unittest.mock import patch


def _insert_offer_and_evaluation(
    cursor,
    source_id: str,
    score: int,
    recommendation: str,
    apply_block: str | None,
    signal: str = "yes",
) -> int:
    cursor.execute(
        """INSERT INTO offers
           (source_id, title, company_name, fetched_at, is_active, relevance_flag)
           VALUES (?, ?, ?, datetime('now'), 1, 'core')""",
        (source_id, f"Role {source_id}", "Test company"),
    )
    offer_id = cursor.execute("SELECT last_insert_rowid()").fetchone()[0]
    cursor.execute(
        """INSERT INTO offer_evaluations
           (offer_id, match_score, recommendation, apply_block,
            llm_apply_signal, sent_via_telegram)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (offer_id, score, recommendation, apply_block, signal),
    )
    return offer_id


def test_hard_block_with_high_score_is_not_selected(test_db, test_conn):
    _insert_offer_and_evaluation(test_db, "HARD-001", 92, "Prioritario", "requisito_imposible")
    with patch("src.telegram.send.get_connection", return_value=test_conn):
        from src.telegram.send import get_top_offers

        selected = get_top_offers(max_offers=3, date_scope="all", min_score=35)

    assert selected == []


def test_real_unsent_hard_block_above_threshold_is_not_selected(test_db, test_conn):
    # Synthetic row matching the real local audit case: offer_id=103, score=44,
    # requisito_imposible, sent_via_telegram=0.
    _insert_offer_and_evaluation(
        test_db, "REAL-AUDIT-103", 44, "Con expectativas bajas", "requisito_imposible"
    )
    with patch("src.telegram.send.get_connection", return_value=test_conn):
        from src.telegram.send import get_top_offers

        selected = get_top_offers(max_offers=3, date_scope="all", min_score=35)

    assert selected == []


def test_review_block_is_selected_and_never_labelled_apply(test_db, test_conn):
    _insert_offer_and_evaluation(test_db, "REVIEW-001", 90, "Prioritario", "otro", signal="maybe")
    with patch("src.telegram.send.get_connection", return_value=test_conn):
        from src.telegram.send import format_offer, get_top_offers

        selected = get_top_offers(max_offers=3, date_scope="all", min_score=35)

    assert len(selected) == 1
    assert selected[0]["eligibility_status"] == "review"
    message = format_offer(selected[0], 1)
    assert "REVISAR" in message
    assert "— Prioritario" not in message
    assert "— Aplicar" not in message


def test_unblocked_offer_keeps_existing_selection_and_label(test_db, test_conn):
    _insert_offer_and_evaluation(test_db, "OPEN-001", 62, "Aplicar", None)
    with patch("src.telegram.send.get_connection", return_value=test_conn):
        from src.telegram.send import format_offer, get_top_offers

        selected = get_top_offers(max_offers=3, date_scope="all", min_score=35)

    assert len(selected) == 1
    assert selected[0]["eligibility_status"] == "eligible"
    assert "— Aplicar" in format_offer(selected[0], 1)


def test_eligible_offers_sort_before_review_even_with_lower_recommendation(test_db, test_conn):
    _insert_offer_and_evaluation(test_db, "REVIEW-002", 95, "Prioritario", "otro")
    _insert_offer_and_evaluation(test_db, "OPEN-002", 55, "Con expectativas bajas", None)
    with patch("src.telegram.send.get_connection", return_value=test_conn):
        from src.telegram.send import get_top_offers

        selected = get_top_offers(max_offers=1, date_scope="all", min_score=35)

    assert len(selected) == 1
    assert selected[0]["title"] == "Role OPEN-002"


def test_send_uses_min_score_from_user_settings_when_not_overridden(test_db, test_conn):
    _insert_offer_and_evaluation(test_db, "SETTING-001", 60, "Aplicar", None)
    test_db.execute("INSERT INTO user_settings (min_score_send) VALUES (70)")
    try:
        with patch("src.telegram.send.get_connection", return_value=test_conn):
            from src.telegram.send import get_top_offers

            selected = get_top_offers(max_offers=3, date_scope="all")
    finally:
        test_db.execute("DELETE FROM user_settings")

    assert selected == []


def test_user_settings_preserves_zero_send_threshold(test_db, test_conn):
    test_db.execute("INSERT INTO user_settings (min_score_send) VALUES (0)")
    try:
        with patch("src.db.models.get_connection", return_value=test_conn):
            from src.db.models import get_user_settings

            settings = get_user_settings()
    finally:
        test_db.execute("DELETE FROM user_settings")

    assert settings.min_score_send == 0
