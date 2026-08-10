"""The database is derived, and the views compute what nobody should type by hand."""

from __future__ import annotations

import sqlite3

from rti import db
from rti.tables import blank_row, read_table, write_table


def _connect(sampled):
    target, counts = db.build(sampled / "rti.db")
    return sqlite3.connect(target), counts


def test_schema_is_generated_from_the_enums():
    from rti.enums import EVENT_TYPES, NOT_FILED_REASONS

    sql = db.ddl()
    for value in (*EVENT_TYPES, *NOT_FILED_REASONS):
        assert f"'{value}'" in sql, f"{value} is not constrained in the schema"


def test_build_loads_every_table(sampled):
    conn, counts = _connect(sampled)
    assert counts["application"] == len(read_table("application"))
    assert conn.execute("SELECT COUNT(*) FROM application").fetchone()[0] == counts["application"]


def test_the_database_refuses_a_value_the_validator_would_reject(sampled):
    rows = read_table("application")
    rows[0]["topic"] = "not_a_topic"
    write_table("application", rows)
    try:
        db.build(sampled / "rti.db")
    except sqlite3.IntegrityError:
        return
    raise AssertionError("the schema accepted a value outside the vocabulary")


def test_rebuilding_is_idempotent(sampled):
    first, _ = db.build(sampled / "rti.db")
    before = first.read_bytes()
    second, _ = db.build(sampled / "rti.db")
    assert second.read_bytes() == before


def _record(app_id, event_id, event_type, when):
    row = blank_row("event")
    row.update(
        {
            "event_id": str(event_id),
            "application_id": app_id,
            "event_date": when,
            "event_type": event_type,
            "direction": "inbound",
            "medium": "email",
        }
    )
    return row


def test_status_and_counts_are_derived_from_events(sampled):
    rows = read_table("application")
    app_id = rows[0]["application_id"]
    rows[0].update(
        {"filing_outcome": "filed", "filing_date": "2026-08-01", "due_date": "2026-08-31"}
    )
    write_table("application", rows)
    write_table(
        "event",
        [
            _record(app_id, 1, "acknowledgment", "2026-08-02"),
            _record(app_id, 2, "transfer_6_3", "2026-08-09"),
            _record(app_id, 3, "transfer_6_3", "2026-08-16"),
            _record(app_id, 4, "response_received", "2026-08-25"),
        ],
    )
    conn, _ = _connect(sampled)
    row = conn.execute(
        "SELECT status, n_transfers, days_to_response, first_ack_date, last_event "
        "FROM v_status WHERE application_id = ?",
        (app_id,),
    ).fetchone()
    assert row == ("replied", 2, 24, "2026-08-02", "response_received")


def test_attrition_view_separates_the_three_real_states(sampled):
    """Sampled, filed, could-not-file, and nobody-has-said-yet are four numbers."""
    rows = read_table("application")
    karnataka = [r for r in rows if r["state"] == "Karnataka"]
    karnataka[0].update(
        {"filing_outcome": "filed", "filing_date": "2026-08-01", "due_date": "2026-08-31"}
    )
    karnataka[1].update({"filing_outcome": "not_filed", "not_filed_reason": "authority_not_listed"})
    write_table("application", rows)

    conn, _ = _connect(sampled)
    sampled_n, filed, not_filed, pending, not_listed = conn.execute(
        "SELECT sampled, filed, not_filed, not_yet_reported, not_listed_on_portal "
        "FROM v_attrition WHERE state = 'Karnataka'"
    ).fetchone()
    assert sampled_n == len(karnataka)
    assert (filed, not_filed, not_listed) == (1, 1, 1)
    assert filed + not_filed + pending == sampled_n
