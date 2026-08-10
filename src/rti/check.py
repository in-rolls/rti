"""Validate the committed tables, so a hand edit fails the build instead of the study.

`data/tables/*.csv` is deliberately editable: a curator fixes a mistyped date in
a spreadsheet and commits, and `git diff` is the audit trail. The cost of that
convenience is that nothing stops a bad edit. This is what stops it. It runs in
CI, so a typo is caught in a pull request rather than in a regression six months
later.

Every message names the file, the row, the column, and what would fix it.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date

from .config import due_date, load_state_rules
from .enums import (
    CHANNELS,
    DIRECTIONS,
    EVENT_TYPES,
    FILING_OUTCOMES,
    LANGUAGES,
    MEDIUMS,
    NOT_FILED_REASONS,
    PAYMENT_MODES,
    TOPICS,
)
from .tables import TABLES, read_table, table_path

VOCABULARIES = {
    "application": {
        "topic": TOPICS,
        "language": LANGUAGES,
        "channel": CHANNELS,
        "filing_outcome": FILING_OUTCOMES,
        "not_filed_reason": NOT_FILED_REASONS,
        "payment_mode": PAYMENT_MODES,
    },
    "event": {
        "event_type": EVENT_TYPES,
        "direction": DIRECTIONS,
        "medium": MEDIUMS,
    },
}

DATE_COLUMNS = {
    "application": ("filing_date", "due_date"),
    "event": ("event_date",),
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, table: str, line: int, message: str) -> None:
        self.errors.append(f"{table}.csv line {line}: {message}")

    def warn(self, table: str, line: int, message: str) -> None:
        self.warnings.append(f"{table}.csv line {line}: {message}")


def _line(index: int) -> int:
    """Spreadsheet line number: one for the header, one because rows are 1-based."""
    return index + 2


def check_columns(report: Report) -> dict[str, list[dict]]:
    loaded = {}
    for table, columns in TABLES.items():
        path = table_path(table)
        if not path.is_file():
            report.warn(table, 0, "table does not exist yet")
            loaded[table] = []
            continue
        rows = read_table(table)
        loaded[table] = rows
        if rows:
            missing = set(columns) - set(rows[0])
            extra = set(rows[0]) - set(columns)
            if missing:
                report.error(table, 1, f"missing column(s) {sorted(missing)}")
            if extra:
                report.error(table, 1, f"unexpected column(s) {sorted(extra)}")
    return loaded


def check_vocabularies(table: str, rows: list[dict], report: Report) -> None:
    for i, row in enumerate(rows):
        for column, allowed in VOCABULARIES.get(table, {}).items():
            value = (row.get(column) or "").strip()
            if value and value not in allowed:
                report.error(
                    table,
                    _line(i),
                    f"{column}={value!r} is not a recognised value. "
                    f"Expected one of: {', '.join(allowed)}",
                )


def check_dates(table: str, rows: list[dict], report: Report) -> None:
    for i, row in enumerate(rows):
        for column in DATE_COLUMNS.get(table, ()):
            value = (row.get(column) or "").strip()
            if not value:
                continue
            try:
                date.fromisoformat(value)
            except ValueError:
                report.error(
                    table,
                    _line(i),
                    f"{column}={value!r} is not a date. Use YYYY-MM-DD, e.g. 2026-06-15",
                )


def check_keys(loaded: dict[str, list[dict]], report: Report) -> None:
    for table, key in (
        ("authority", "authority_id"),
        ("application", "application_id"),
        ("event", "event_id"),
    ):
        counts = Counter((r.get(key) or "").strip() for r in loaded[table])
        for value, n in counts.items():
            if not value:
                report.error(table, 0, f"{n} row(s) have a blank {key}")
            elif n > 1:
                report.error(table, 0, f"{key}={value!r} appears {n} times; it must be unique")

    known_authorities = {r["authority_id"] for r in loaded["authority"]}
    for i, row in enumerate(loaded["application"]):
        aid = (row.get("authority_id") or "").strip()
        if aid and aid not in known_authorities:
            report.error(
                "application",
                _line(i),
                f"authority_id={aid!r} is not in authority.csv",
            )

    known_applications = {r["application_id"] for r in loaded["application"]}
    for i, row in enumerate(loaded["event"]):
        app = (row.get("application_id") or "").strip()
        if app not in known_applications:
            report.error(
                "event",
                _line(i),
                f"application_id={app!r} is not in application.csv. An event cannot "
                f"exist without the application it happened to.",
            )


def check_source_rows(loaded: dict[str, list[dict]], report: Report) -> None:
    """A repeated source_row_id means one form submission was loaded twice."""
    for table in ("application", "event"):
        counts = Counter(
            (r.get("source_row_id") or "").strip()
            for r in loaded[table]
            if (r.get("source_row_id") or "").strip()
        )
        for value, n in counts.items():
            if n > 1:
                report.error(
                    table,
                    0,
                    f"source_row_id={value!r} appears {n} times; one form response was "
                    f"loaded more than once",
                )


def check_filing_logic(loaded: dict[str, list[dict]], report: Report) -> None:
    """The rules that make the attrition record trustworthy."""
    rules = load_state_rules()
    for i, row in enumerate(loaded["application"]):
        outcome = (row.get("filing_outcome") or "").strip()
        reason = (row.get("not_filed_reason") or "").strip()
        filing_date = (row.get("filing_date") or "").strip()
        registration = (row.get("registration_number") or "").strip()

        if outcome == "not_filed" and not reason:
            report.error(
                "application",
                _line(i),
                "filing_outcome is 'not_filed' but not_filed_reason is blank. Why it "
                "could not be filed is the point of recording it.",
            )
        if outcome == "filed" and reason:
            report.error(
                "application",
                _line(i),
                f"filing_outcome is 'filed' but not_filed_reason={reason!r} is set",
            )
        if outcome == "filed" and not filing_date:
            report.warn("application", _line(i), "filed, but no filing_date recorded")
        if outcome == "filed" and not registration:
            report.warn("application", _line(i), "filed on a portal, but no registration_number")
        if outcome != "filed" and filing_date:
            report.error(
                "application",
                _line(i),
                f"filing_date={filing_date!r} is set but filing_outcome is {outcome!r}",
            )

        expected = due_date(row.get("state", ""), filing_date, rules)
        actual = (row.get("due_date") or "").strip()
        if expected and actual and expected != actual:
            report.error(
                "application",
                _line(i),
                f"due_date={actual!r} but {row.get('state')} allows "
                f"{rules.get(row.get('state', ''), {}).get('statutory_days', 30)} days "
                f"from {filing_date}, which is {expected}",
            )


def run() -> Report:
    report = Report()
    loaded = check_columns(report)
    for table, rows in loaded.items():
        check_vocabularies(table, rows, report)
        check_dates(table, rows, report)
    check_keys(loaded, report)
    check_source_rows(loaded, report)
    check_filing_logic(loaded, report)
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Validate data/tables/*.csv.")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures too")
    args = ap.parse_args(argv)

    report = run()
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)

    if report.errors or (args.strict and report.warnings):
        print(
            f"\nFAILED: {len(report.errors)} error(s), {len(report.warnings)} warning(s)",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"tables are valid ({len(report.warnings)} warning(s))")


if __name__ == "__main__":
    main()
