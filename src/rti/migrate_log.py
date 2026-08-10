"""Move the hand-kept filing log into the three tables.

`data/rti_filing_evidence_log.csv` is 32 columns wide because it stacks five
kinds of fact in one row: the office, the filer, the application, the things that
happened, and the judgment about the reply. Sixteen of those columns are a date,
a medium, and a document URL repeated five times with different prefixes, which
is why a second transfer or a remanded appeal has nowhere to go.

This splits the rows apart without changing a single recorded value. Run it
before `rti-sample`, so the sampler continues the identifier sequence from the
applications that already exist rather than colliding with them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import data_dir, due_date, load_state_rules
from .ids import authority_id, norm, parse_application_id, state_code
from .tables import blank_row, read_table, source_row_id, write_table

LEGACY_BATCH = "legacy_2026q2"

# Each pair of legacy columns that means "something happened on a date", and the
# event it becomes. The five prefixes collapse into rows of one table.
EVENT_MAP = (
    ("response_date", "response_medium", "response_url", "response_received"),
    ("first_appeal_date", None, "first_appeal_url", "first_appeal_filed"),
    ("fa_response_date", "fa_response_medium", "fa_url", "first_appeal_decided"),
    ("second_appeal_date", None, "second_appeal_url", "second_appeal_filed"),
    ("sa_decision_date", "sa_decision_medium", "sa_url", "second_appeal_decided"),
)

MEDIUM_ALIASES = {
    "email": "email",
    "e-mail": "email",
    "post": "post",
    "speed post": "speed_post",
    "registered post": "speed_post",
    "portal": "portal",
    "online": "portal",
    "phone": "phone",
    "in person": "in_person",
}


def medium(value: str) -> str:
    return MEDIUM_ALIASES.get(norm(value).lower(), "")


def migrate(rows: list[dict], rules: dict) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    authorities, applications, events = [], [], []
    notes: list[str] = []
    next_event = 1

    for raw in rows:
        rti_id = norm(raw.get("rti_id", "")).upper()
        state = norm(raw.get("state", ""))
        department = norm(raw.get("public_authority", ""))
        if not rti_id or not state:
            continue
        if parse_application_id(rti_id) is None:
            notes.append(f"{rti_id}: identifier is not in the ST-NNN form; kept as it is")

        if department.startswith("(") or not department:
            notes.append(
                f"{rti_id}: public_authority is {department!r}, so the office cannot be "
                f"matched to the frame. authority_id is derived from what was recorded."
            )
        aid = authority_id(state, department or "(unrecorded)", "", "")

        authority = blank_row("authority")
        authority.update(
            {
                "authority_id": aid,
                "state": state,
                "state_code": state_code(state),
                "department": department or "(unrecorded)",
                "portal": "",
                "relevant": "",
                "first_sampled_batch": LEGACY_BATCH,
            }
        )
        authorities.append(authority)

        filing_date = norm(raw.get("filing_date", ""))
        application = blank_row("application")
        application.update(
            {
                "application_id": rti_id,
                "batch_id": LEGACY_BATCH,
                "authority_id": aid,
                "state": state,
                "department": department or "(unrecorded)",
                "topic": "",
                "language": "",
                "channel": "portal",
                "template_version": "legacy",
                "filing_outcome": "filed" if filing_date else "",
                "filing_date": filing_date,
                "registration_number": norm(raw.get("registration_number", "")),
                "fee_paid_inr": norm(raw.get("fee_paid_inr", "")),
                "payment_mode": "online" if norm(raw.get("payment_reference", "")) else "",
                "payment_reference": norm(raw.get("payment_reference", "")),
                "evidence_url": norm(raw.get("filed_evidence_url", "")),
                "screen_recording_url": norm(raw.get("screen_recording_url", "")),
                "due_date": due_date(state, filing_date, rules),
                "filed_by": norm(raw.get("applicant", "")),
                "notes": norm(raw.get("notes", "")),
                "source_row_id": source_row_id("legacy_log", rti_id, rti_id),
            }
        )
        recorded_due = norm(raw.get("response_due_date", ""))
        if recorded_due and recorded_due != application["due_date"]:
            notes.append(
                f"{rti_id}: the log recorded a due date of {recorded_due}; "
                f"{state}'s statutory clock gives {application['due_date']}. "
                f"The computed date is stored."
            )
        applications.append(application)

        if norm(raw.get("email_received_on_filing", "")).lower() in {"yes", "y", "true"}:
            event = blank_row("event")
            event.update(
                {
                    "event_id": str(next_event),
                    "application_id": rti_id,
                    "event_date": filing_date,
                    "event_type": "acknowledgment",
                    "direction": "inbound",
                    "medium": "email",
                    "notes": "Acknowledgement on filing. Date taken from the filing date; "
                    "the log did not record it separately.",
                    "recorded_by": norm(raw.get("applicant", "")),
                    "source_row_id": source_row_id("legacy_log", rti_id, f"{rti_id}-ack"),
                }
            )
            events.append(event)
            next_event += 1

        for date_col, medium_col, url_col, event_type in EVENT_MAP:
            when = norm(raw.get(date_col, ""))
            if not when:
                continue
            event = blank_row("event")
            event.update(
                {
                    "event_id": str(next_event),
                    "application_id": rti_id,
                    "event_date": when,
                    "event_type": event_type,
                    "direction": (
                        "outbound"
                        if event_type in {"first_appeal_filed", "second_appeal_filed"}
                        else "inbound"
                    ),
                    "medium": medium(raw.get(medium_col, "")) if medium_col else "",
                    "document_url": norm(raw.get(url_col, "")),
                    "recorded_by": norm(raw.get("applicant", "")),
                    "source_row_id": source_row_id("legacy_log", rti_id, f"{rti_id}-{event_type}"),
                }
            )
            events.append(event)
            next_event += 1

    return authorities, applications, events, notes


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Load data/rti_filing_evidence_log.csv into the three tables."
    )
    ap.add_argument("--log", type=Path, default=None)
    args = ap.parse_args(argv)

    import csv

    path = args.log or data_dir() / "rti_filing_evidence_log.csv"
    if not path.is_file():
        sys.exit(f"log not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    authorities, applications, events, notes = migrate(rows, load_state_rules())

    existing_apps = {r["application_id"] for r in read_table("application")}
    clash = existing_apps & {r["application_id"] for r in applications}
    if clash:
        sys.exit(
            f"application id(s) {sorted(clash)} already exist. Migrate the legacy log "
            f"before drawing a batch, so the sampler continues the sequence."
        )

    def merge(name: str, new: list[dict], key: str) -> int:
        index = {r[key]: r for r in read_table(name)}
        added = 0
        for row in new:
            if row[key] not in index:
                index[row[key]] = row
                added += 1
        write_table(name, list(index.values()))
        return added

    print(f"authority:   +{merge('authority', authorities, 'authority_id')}")
    print(f"application: +{merge('application', applications, 'application_id')}")
    print(f"event:       +{merge('event', events, 'event_id')}")
    for note in notes:
        print(f"  note: {note}", file=sys.stderr)


if __name__ == "__main__":
    main()
