"""Tests for shared offer eligibility and effective scoring weights."""

from __future__ import annotations

import sqlite3


def test_hard_blocks_are_not_eligible_for_send():
    from src.utils.eligibility import EligibilityStatus, eligibility_status, is_eligible

    for code in ("requisito_imposible", "practicas"):
        row = {"id": 10, "apply_block": code}
        assert eligibility_status(row) is EligibilityStatus.BLOCKED
        assert not is_eligible(row)


def test_other_and_unknown_blocks_require_review(caplog):
    from src.utils.eligibility import EligibilityStatus, eligibility_status, is_eligible

    other = {"id": 11, "apply_block": "otro", "llm_apply_signal": "maybe"}
    assert eligibility_status(other) is EligibilityStatus.REVIEW
    assert is_eligible(other)

    unknown = {"id": 12, "apply_block": "future_block_code"}
    with caplog.at_level("WARNING"):
        assert eligibility_status(unknown) is EligibilityStatus.REVIEW
    assert "future_block_code" in caplog.text


def test_unblocked_offer_remains_eligible():
    from src.utils.eligibility import EligibilityStatus, eligibility_status, is_eligible

    row = {"id": 13, "apply_block": None, "llm_apply_signal": "no"}
    assert eligibility_status(row) is EligibilityStatus.ELIGIBLE
    assert is_eligible(row)


def test_send_sql_filter_matches_python_eligibility_for_same_rows():
    from src.utils.eligibility import is_eligible, sendable_sql_predicate

    rows = [
        (1, None),
        (2, ""),
        (3, "requisito_imposible"),
        (4, "practicas"),
        (5, "otro"),
        (6, "future_block_code"),
        (7, "null"),
    ]
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE evaluations (id INTEGER, apply_block TEXT)")
    conn.executemany("INSERT INTO evaluations VALUES (?, ?)", rows)

    predicate, params = sendable_sql_predicate("evaluations")
    sql_ids = [
        row[0]
        for row in conn.execute(f"SELECT id FROM evaluations WHERE {predicate} ORDER BY id", params)
    ]
    python_ids = [row_id for row_id, block in rows if is_eligible({"apply_block": block})]

    assert sql_ids == python_ids
    conn.close()


def test_sql_eligibility_order_uses_integer_precedence():
    from src.utils.eligibility import eligibility_order_sql

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE evaluations (id INTEGER, apply_block TEXT, recommendation_rank INTEGER)"
    )
    conn.executemany(
        "INSERT INTO evaluations VALUES (?, ?, ?)",
        [
            (1, "otro", 0),  # Review would win recommendation-only order.
            (2, None, 2),
            (3, "practicas", 0),
        ],
    )
    order_sql, params = eligibility_order_sql("evaluations")
    ids = [
        row[0]
        for row in conn.execute(
            f"SELECT id FROM evaluations ORDER BY {order_sql}, recommendation_rank", params
        )
    ]

    assert ids == [2, 1, 3]
    conn.close()
