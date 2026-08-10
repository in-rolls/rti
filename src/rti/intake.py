"""Merge Google Form responses into the committed tables, without ever clobbering.

The two forms only ever append, so a research assistant cannot overwrite what
they recorded last week. This command carries that property across into
`data/tables/`: every submission gets a `source_row_id`, and a submission whose
id is already present is skipped. Loading the same export twice therefore
changes nothing, and a cell a curator fixed by hand survives the next load.

Filing responses update the application row that the sampler already created.
Update responses append an event row. Nothing here creates an application: an
application only exists because an office was sampled.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from .config import due_date, intake_raw_dir, load_state_rules
from .enums import ALL_LABELS, EVENT_TYPES, MEDIUMS, OUTBOUND_EVENT_TYPES, PAYMENT_MODES
from .tables import blank_row, read_table, source_row_id, write_table

FILING_FORM = "filing"
UPDATE_FORM = "update"

# Google Form question -> table column. Questions are worded for a person; the
# columns are worded for the schema. This is the only place the two meet, so a
# reworded question is a one-line change here.
FILING_FIELDS = {
    "timestamp": ("Timestamp",),
    "application_id": ("Application ID", "Application"),
    "filing_outcome": ("Outcome", "Were you able to file it?"),
    "not_filed_reason": ("Reason it could not be filed", "Reason"),
    "filing_date": ("Date filed", "Filing date"),
    "registration_number": ("Registration number", "Registration no"),
    "fee_paid_inr": ("Fee paid", "Fee paid (Rs.)"),
    "payment_mode": ("Payment mode",),
    "payment_reference": ("Payment reference",),
    "evidence_url": ("Evidence", "Upload evidence", "Confirmation screenshot"),
    "screen_recording_url": ("Screen recording",),
    "filed_by": ("Your name", "Email Address", "Filed by"),
    "notes": ("Notes", "Anything else"),
}

UPDATE_FIELDS = {
    "timestamp": ("Timestamp",),
    "application_id": ("Application ID", "Application"),
    "event_type": ("What happened", "What happened?"),
    "event_date": ("Date on the document", "Date"),
    "medium": ("How did it arrive", "Medium"),
    "actor_authority": ("Which office", "Transferred to"),
    "document_url": ("Upload the document", "Document"),
    "recorded_by": ("Your name", "Email Address", "Recorded by"),
    "notes": ("Notes", "Anything else"),
}

# The forms show a sentence ("Transferred to another office under s.6(3)"); the
# table stores a slug (`transfer_6_3`). This maps one back to the other, and also
# accepts the slug itself so a hand-edited CSV loads without translation.
LABEL_TO_VALUE = {v.lower(): v for v in (*EVENT_TYPES, *MEDIUMS, *PAYMENT_MODES)}


def coerce(value: str) -> str:
    """Turn a form label back into the stored value, leaving slugs untouched."""
    text = (value or "").strip()
    if text.lower() in LABEL_TO_VALUE:
        return LABEL_TO_VALUE[text.lower()]
    return LABEL_TO_VALUE.get(_key(text), text)


CONTROLLED_COLUMNS = {
    "payment_mode": PAYMENT_MODES,
    "medium": MEDIUMS,
    "event_type": EVENT_TYPES,
}


def check_controlled(column: str, value: str, app_id: str, problems: list[str]) -> str:
    """Complain here rather than let a bad value reach the table.

    Google Forms option text drifts when a question is edited. Catching it as the
    response is loaded names the form and the answer; catching it later, in the
    validator, only names a row in a CSV.
    """
    allowed = CONTROLLED_COLUMNS.get(column)
    if value and allowed and value not in allowed:
        problems.append(
            f"{app_id}: {column}={value!r} does not match any option this study "
            f"recognises. Either the form's wording changed, or the value was typed "
            f"by hand. Expected one of: {', '.join(allowed)}"
        )
        return ""
    return value


def _key(text: str) -> str:
    """Compare question wording loosely: case, spacing, and punctuation all vary.

    The export's column headings are the questions themselves, so editing a
    question renames a column. Ignoring a trailing '?' or a doubled space means
    a harmless rewording does not silently drop an answer.
    """
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


for _labels in ALL_LABELS:
    for _value, _label in _labels.items():
        LABEL_TO_VALUE[_label.lower()] = _value
        LABEL_TO_VALUE[_key(_label)] = _value


def pick(row: dict, names: tuple[str, ...]) -> str:
    """The first column whose heading matches one of `names`."""
    normalised = {_key(k): v for k, v in row.items() if k}
    for name in names:
        if _key(name) in normalised:
            return (normalised[_key(name)] or "").strip()
    return ""


def read_export(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_filings(rows: list[dict], applications: list[dict], rules: dict) -> tuple[int, list[str]]:
    """Apply filing-form responses to the application rows the sampler created."""
    by_id = {r["application_id"]: r for r in applications}
    seen = {r.get("source_row_id", "") for r in applications if r.get("source_row_id")}
    applied, problems = 0, []

    for raw in rows:
        app_id = pick(raw, FILING_FIELDS["application_id"]).upper()
        timestamp = pick(raw, FILING_FIELDS["timestamp"])
        if not app_id:
            continue
        row_id = source_row_id(FILING_FORM, timestamp, app_id)
        if row_id in seen:
            continue
        target = by_id.get(app_id)
        if target is None:
            problems.append(
                f"{app_id}: no such application. A filing form was submitted for an "
                f"application that was never sampled."
            )
            continue

        values = {
            column: coerce(pick(raw, names))
            for column, names in FILING_FIELDS.items()
            if column not in {"timestamp", "application_id"}
        }
        # Free text must not be coerced; only the pick-lists have labels.
        for free_text in ("notes", "payment_reference", "registration_number", "filed_by"):
            values[free_text] = pick(raw, FILING_FIELDS[free_text])
        values["payment_mode"] = check_controlled(
            "payment_mode", values["payment_mode"], app_id, problems
        )
        outcome = values.get("filing_outcome", "").lower()
        if outcome.startswith("could not") or outcome in {"no", "not filed"}:
            values["filing_outcome"] = "not_filed"
        elif outcome in {"filed", "yes"}:
            values["filing_outcome"] = "filed"

        if values["filing_outcome"] == "filed" and values.get("filing_date"):
            values["due_date"] = due_date(target["state"], values["filing_date"], rules)
        if values["filing_outcome"] == "not_filed":
            # A failure has no filing facts; keeping them blank stops a stray
            # date from making an unfiled application look filed.
            for column in ("filing_date", "registration_number", "payment_reference"):
                values[column] = ""

        target.update({k: v for k, v in values.items() if v != ""})
        target["source_row_id"] = row_id
        seen.add(row_id)
        applied += 1

    return applied, problems


def load_events(
    rows: list[dict], events: list[dict], applications: list[dict]
) -> tuple[int, list[str]]:
    """Append update-form responses as event rows."""
    known = {r["application_id"] for r in applications}
    seen = {r.get("source_row_id", "") for r in events if r.get("source_row_id")}
    next_id = 1 + max(
        (int(r["event_id"]) for r in events if str(r["event_id"]).isdigit()), default=0
    )
    added, problems = 0, []

    for raw in rows:
        app_id = pick(raw, UPDATE_FIELDS["application_id"]).upper()
        timestamp = pick(raw, UPDATE_FIELDS["timestamp"])
        if not app_id:
            continue
        row_id = source_row_id(UPDATE_FORM, timestamp, app_id)
        if row_id in seen:
            continue
        if app_id not in known:
            problems.append(f"{app_id}: no such application. Update form submitted against it.")
            continue

        event_type = check_controlled(
            "event_type", coerce(pick(raw, UPDATE_FIELDS["event_type"])), app_id, problems
        )
        if not event_type:
            continue
        row = blank_row("event")
        row.update(
            {
                "event_id": str(next_id),
                "application_id": app_id,
                "event_date": pick(raw, UPDATE_FIELDS["event_date"]),
                "event_type": event_type,
                "direction": "outbound" if event_type in OUTBOUND_EVENT_TYPES else "inbound",
                "medium": check_controlled(
                    "medium", coerce(pick(raw, UPDATE_FIELDS["medium"])), app_id, problems
                ),
                "actor_authority": pick(raw, UPDATE_FIELDS["actor_authority"]),
                "document_url": pick(raw, UPDATE_FIELDS["document_url"]),
                "notes": pick(raw, UPDATE_FIELDS["notes"]),
                "recorded_by": pick(raw, UPDATE_FIELDS["recorded_by"]),
                "recorded_at": timestamp,
                "source_row_id": row_id,
            }
        )
        events.append(row)
        seen.add(row_id)
        next_id += 1
        added += 1

    return added, problems


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Merge Google Form exports into data/tables/. Safe to re-run."
    )
    ap.add_argument("--filing", type=Path, action="append", help="filing-form CSV export")
    ap.add_argument("--update", type=Path, action="append", help="update-form CSV export")
    ap.add_argument(
        "--all",
        action="store_true",
        help="load every export in data/intake_raw/ (filing_*.csv, update_*.csv)",
    )
    args = ap.parse_args(argv)

    filing_paths = list(args.filing or [])
    update_paths = list(args.update or [])
    if args.all:
        filing_paths += sorted(intake_raw_dir().glob("filing_*.csv"))
        update_paths += sorted(intake_raw_dir().glob("update_*.csv"))
    if not filing_paths and not update_paths:
        sys.exit("nothing to load; pass --filing / --update, or --all")

    rules = load_state_rules()
    applications = read_table("application")
    events = read_table("event")
    if not applications:
        sys.exit("no application rows; run rti-sample before loading intake")

    problems: list[str] = []
    filed = added = 0
    for path in filing_paths:
        n, issues = load_filings(read_export(path), applications, rules)
        filed += n
        problems += [f"{path.name}: {p}" for p in issues]
    for path in update_paths:
        n, issues = load_events(read_export(path), events, applications)
        added += n
        problems += [f"{path.name}: {p}" for p in issues]

    write_table("application", applications)
    write_table("event", events)

    print(f"applied {filed} filing responses, appended {added} events")
    print("run `rti-check` to validate, then `rti-build-db` to rebuild the database")
    if problems:
        print(f"\n{len(problems)} response(s) could not be applied:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
