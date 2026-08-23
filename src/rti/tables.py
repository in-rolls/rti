"""The three tables: their columns, and how to read and write them.

The tables exist in two forms. `data/private/tables/*.csv` holds the real rows
and is gitignored. `data/tables/*.csv` holds the redacted copy and is committed,
so `git log` remains the audit trail for everything except the few columns that
name a person. Both are plain CSV, so a curator can open either in a spreadsheet
and fix a cell without needing SQL. `rti.db` is rebuilt from the real rows and
is never edited, which is what stops it drifting.

`write_table` writes both in one call. That is the entire anonymisation
boundary: there is no separate step to remember before pushing, and the public
copy cannot fall behind the private one.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from .config import private_tables_dir, tables_dir

AUTHORITY_COLUMNS = (
    "authority_id",
    "state",
    "state_code",
    "department",
    "office_name",
    "tree_department",
    "node_id",
    "parent_id",
    "level",
    "tier",
    "path",
    "district",
    "block",
    "portal",
    "relevant",
    "category",
    "first_sampled_batch",
)

APPLICATION_COLUMNS = (
    # Written by `rti-sample`, at sampling time, for every office drawn.
    "application_id",
    "batch_id",
    "authority_id",
    "state",
    "department",
    "topic",
    "language",
    "channel",
    "template_version",
    "treatment",
    "assigned_ra",
    "randomization_stratum",
    # Filled by `rti-load` from the filing form. Blank means nobody has
    # reported on this application yet, which is itself a state worth seeing.
    "filing_outcome",
    "not_filed_reason",
    "filing_date",
    "registration_number",
    "fee_paid_inr",
    "payment_mode",
    "payment_reference",
    "evidence_url",
    "screen_recording_url",
    "due_date",
    "filed_by",
    "notes",
    "source_row_id",
)

EVENT_COLUMNS = (
    "event_id",
    "application_id",
    "event_date",
    "event_type",
    "direction",
    "medium",
    "actor_authority",
    "document_url",
    "notes",
    "recorded_by",
    "recorded_at",
    "source_row_id",
)

TABLES = {
    "authority": AUTHORITY_COLUMNS,
    "application": APPLICATION_COLUMNS,
    "event": EVENT_COLUMNS,
}

KEYS = {
    "authority": "authority_id",
    "application": "application_id",
    "event": "event_id",
}


def table_path(name: str) -> Path:
    """The published, redacted copy."""
    return tables_dir() / f"{name}.csv"


def private_table_path(name: str) -> Path:
    """The real rows. Gitignored."""
    return private_tables_dir() / f"{name}.csv"


def read_table(name: str) -> list[dict]:
    """Rows of a table: the real ones when they exist, else the published copy.

    A fresh clone has no private directory and reads the redacted tables, which
    is enough to run the pipeline, inspect the schema, and pass the checks. The
    machine that collected the data reads the truth.
    """
    for path in (private_table_path(name), table_path(name)):
        if path.is_file():
            with open(path, newline="", encoding="utf-8-sig") as f:
                return list(csv.DictReader(f))
    return []


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=list(columns),
            extrasaction="ignore",
            lineterminator="\n",
        )
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in columns})
    return path


def write_table(name: str, rows: list[dict]) -> Path:
    """Write the real table, then derive the published copy from it.

    Both are written every time, so the committed CSV can never lag behind the
    real one and nobody has to remember to redact before pushing.

    Rows are sorted by key first, which keeps the git diff readable: a new
    application appears as one added line rather than as a reshuffle of the
    whole file.
    """
    from .scrub import public_rows

    columns = TABLES[name]
    key = KEYS[name]
    ordered = sorted(rows, key=lambda r: str(r.get(key, "")))

    _write_csv(private_table_path(name), columns, ordered)
    return _write_csv(table_path(name), columns, public_rows(ordered))


def blank_row(name: str) -> dict[str, str]:
    return {c: "" for c in TABLES[name]}


def source_row_id(form: str, timestamp: str, application_id: str) -> str:
    """Stable identifier for one Google Form submission.

    Forms give no response id in the exported sheet, so this stands in for one.
    It is what makes `rti-load` idempotent: loading the same export twice adds
    nothing the second time, and a hand-corrected cell is never overwritten.
    """
    key = "|".join((form, timestamp.strip(), application_id.strip().upper()))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
