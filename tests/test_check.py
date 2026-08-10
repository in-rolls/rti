"""The validator has to catch a bad hand edit, because hand editing is the plan."""

from __future__ import annotations

import pytest

from rti.check import run
from rti.tables import read_table, write_table


def _first(sampled):
    return read_table("application")[0]


def _corrupt(column, value):
    rows = read_table("application")
    rows[0][column] = value
    write_table("application", rows)
    return rows[0]


def test_a_clean_batch_passes(sampled):
    assert run().errors == []


def test_an_invented_enum_value_is_caught(sampled):
    _corrupt("topic", "reservation_rosters")
    errors = run().errors
    assert any("topic" in e and "not a recognised value" in e for e in errors)


def test_a_mistyped_date_is_caught(sampled):
    _corrupt("filing_outcome", "filed")
    _corrupt("filing_date", "20th August 2026")
    errors = run().errors
    assert any("is not a date" in e and "YYYY-MM-DD" in e for e in errors)


def test_not_filed_without_a_reason_is_caught(sampled):
    """The reason is the entire value of recording the failure."""
    _corrupt("filing_outcome", "not_filed")
    errors = run().errors
    assert any("not_filed_reason is blank" in e for e in errors)


def test_a_filing_date_without_a_filing_is_caught(sampled):
    _corrupt("filing_date", "2026-08-20")
    errors = run().errors
    assert any("filing_date" in e and "filing_outcome" in e for e in errors)


def test_a_wrong_due_date_is_caught(sampled):
    """Delhi is on 45 days here; a 30-day answer is wrong and must not pass."""
    rows = read_table("application")
    delhi = next(r for r in rows if r["state"] == "Delhi")
    delhi.update({"filing_outcome": "filed", "filing_date": "2026-08-01", "due_date": "2026-08-31"})
    write_table("application", rows)
    errors = run().errors
    assert any("due_date" in e and "2026-09-15" in e for e in errors)


def test_a_duplicate_identifier_is_caught(sampled):
    rows = read_table("application")
    rows[1]["application_id"] = rows[0]["application_id"]
    write_table("application", rows)
    assert any("must be unique" in e for e in run().errors)


def test_an_event_without_its_application_is_caught(sampled):
    from rti.tables import blank_row

    orphan = blank_row("event")
    orphan.update(
        {
            "event_id": "1",
            "application_id": "ZZ-999",
            "event_date": "2026-08-21",
            "event_type": "acknowledgment",
        }
    )
    write_table("event", [orphan])
    errors = run().errors
    assert any("ZZ-999" in e and "cannot exist without" in e for e in errors)


def test_a_response_loaded_twice_is_caught(sampled):
    rows = read_table("application")
    rows[0]["source_row_id"] = "abc123"
    rows[1]["source_row_id"] = "abc123"
    write_table("application", rows)
    assert any("loaded more than once" in e for e in run().errors)


@pytest.mark.parametrize("column", ["topic", "language", "channel"])
def test_every_constrained_column_is_actually_constrained(sampled, column):
    _corrupt(column, "nonsense")
    assert any(column in e for e in run().errors)
