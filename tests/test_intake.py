"""Loading form responses must be repeatable and must never overwrite a correction."""

from __future__ import annotations

from rti import intake
from rti.config import load_state_rules
from rti.tables import read_table, write_table

from .conftest import write_csv

FILING_HEADER = [
    "Timestamp",
    "Email Address",
    "Application ID",
    "Were you able to file it?",
    "Reason it could not be filed",
    "Date filed",
    "Registration number",
    "Fee paid (Rs.)",
    "Payment mode",
    "Payment reference",
    "Evidence",
    "Notes",
]

UPDATE_HEADER = [
    "Timestamp",
    "Email Address",
    "Application ID",
    "What happened?",
    "Date on the document",
    "How did it arrive?",
    "Which office was it transferred to?",
    "Upload the document",
    "Notes",
]


def _ids():
    return sorted(r["application_id"] for r in read_table("application"))


def _filing_export(tmp_path, app_id, **overrides):
    row = {
        "Timestamp": "2026-08-20 10:14:03",
        "Email Address": "ra1@example.org",
        "Application ID": app_id,
        "Were you able to file it?": "Filed",
        "Reason it could not be filed": "",
        "Date filed": "2026-08-20",
        "Registration number": "REG/2026/001",
        "Fee paid (Rs.)": "10",
        "Payment mode": "Online (net banking, UPI, card)",
        "Payment reference": "UPI-1",
        "Evidence": "https://drive.example/x",
        "Notes": "",
    }
    row.update(overrides)
    return write_csv(tmp_path / "filing.csv", FILING_HEADER, [[row[c] for c in FILING_HEADER]])


def _update_export(tmp_path, app_id, what="Acknowledgement received", when="2026-08-21"):
    row = [
        "2026-08-22 09:00:00",
        "ra1@example.org",
        app_id,
        what,
        when,
        "By email",
        "",
        "https://drive.example/ack",
        "",
    ]
    return write_csv(tmp_path / "update.csv", UPDATE_HEADER, [row])


def test_a_filing_updates_the_row_the_sampler_created(sampled, tmp_path):
    app_id = _ids()[0]
    export = _filing_export(tmp_path, app_id)
    applications = read_table("application")
    applied, problems = intake.load_filings(
        intake.read_export(export), applications, load_state_rules()
    )
    assert (applied, problems) == (1, [])
    row = next(r for r in applications if r["application_id"] == app_id)
    assert row["filing_outcome"] == "filed"
    assert row["registration_number"] == "REG/2026/001"
    assert row["payment_mode"] == "online", "the form label was not mapped back"


def test_loading_the_same_export_twice_changes_nothing(sampled, tmp_path):
    app_id = _ids()[0]
    export = _filing_export(tmp_path, app_id)
    applications = read_table("application")
    intake.load_filings(intake.read_export(export), applications, load_state_rules())
    applied, _ = intake.load_filings(intake.read_export(export), applications, load_state_rules())
    assert applied == 0


def test_a_hand_correction_survives_a_reload(sampled, tmp_path):
    """The whole point of a CSV source of truth: a curator can fix a cell."""
    app_id = _ids()[0]
    export = _filing_export(tmp_path, app_id)
    applications = read_table("application")
    intake.load_filings(intake.read_export(export), applications, load_state_rules())

    for row in applications:
        if row["application_id"] == app_id:
            row["registration_number"] = "CORRECTED/BY/HAND"
    write_table("application", applications)

    applications = read_table("application")
    intake.load_filings(intake.read_export(export), applications, load_state_rules())
    row = next(r for r in applications if r["application_id"] == app_id)
    assert row["registration_number"] == "CORRECTED/BY/HAND"


def test_due_date_uses_the_state_clock_not_a_hardcoded_thirty(sampled, tmp_path):
    """Delhi is set to 45 days in the test rules; the answer must follow."""
    delhi = next(r for r in read_table("application") if r["state"] == "Delhi")
    export = _filing_export(tmp_path, delhi["application_id"], **{"Date filed": "2026-08-01"})
    applications = read_table("application")
    intake.load_filings(intake.read_export(export), applications, load_state_rules())
    row = next(r for r in applications if r["application_id"] == delhi["application_id"])
    assert row["due_date"] == "2026-09-15"


def test_a_failure_to_file_is_recorded_with_its_reason(sampled, tmp_path):
    app_id = _ids()[0]
    export = _filing_export(
        tmp_path,
        app_id,
        **{
            "Were you able to file it?": "Could not file",
            "Reason it could not be filed": "The office is not in the portal's dropdown",
            "Date filed": "",
            "Registration number": "",
        },
    )
    applications = read_table("application")
    intake.load_filings(intake.read_export(export), applications, load_state_rules())
    row = next(r for r in applications if r["application_id"] == app_id)
    assert row["filing_outcome"] == "not_filed"
    assert row["not_filed_reason"] == "authority_not_listed"
    assert row["filing_date"] == ""


def test_an_unknown_application_is_reported_not_invented(sampled, tmp_path):
    export = _filing_export(tmp_path, "ZZ-999")
    applications = read_table("application")
    applied, problems = intake.load_filings(
        intake.read_export(export), applications, load_state_rules()
    )
    assert applied == 0
    assert problems and "ZZ-999" in problems[0]
    assert not any(r["application_id"] == "ZZ-999" for r in applications)


def test_events_append_and_do_not_duplicate(sampled, tmp_path):
    app_id = _ids()[0]
    export = _update_export(tmp_path, app_id)
    events = []
    applications = read_table("application")
    added, problems = intake.load_events(intake.read_export(export), events, applications)
    assert (added, problems) == (1, [])
    assert events[0]["event_type"] == "acknowledgment"
    assert events[0]["medium"] == "email"
    assert events[0]["direction"] == "inbound"

    added, _ = intake.load_events(intake.read_export(export), events, applications)
    assert added == 0
    assert len(events) == 1


def test_several_events_can_attach_to_one_application(sampled, tmp_path):
    """What the 32-column log could not do: two transfers, in order."""
    app_id = _ids()[0]
    events, applications = [], read_table("application")
    for i, when in enumerate(("2026-09-02", "2026-09-20"), start=1):
        export = write_csv(
            tmp_path / f"u{i}.csv",
            UPDATE_HEADER,
            [
                [
                    f"2026-09-0{i} 09:00:00",
                    "ra@example.org",
                    app_id,
                    "Transferred to another office under s.6(3)",
                    when,
                    "On the RTI portal",
                    f"Office {i}",
                    "",
                    "",
                ]
            ],
        )
        intake.load_events(intake.read_export(export), events, applications)
    assert len(events) == 2
    assert [e["event_type"] for e in events] == ["transfer_6_3", "transfer_6_3"]
    assert [e["event_id"] for e in events] == ["1", "2"]


def test_an_unrecognised_option_is_rejected_at_load_time(sampled, tmp_path):
    """A reworded form option must fail loudly, not enter the table."""
    app_id = _ids()[0]
    export = _filing_export(tmp_path, app_id, **{"Payment mode": "Paid somehow"})
    applications = read_table("application")
    _, problems = intake.load_filings(intake.read_export(export), applications, load_state_rules())
    assert problems and "payment_mode" in problems[0]
    row = next(r for r in applications if r["application_id"] == app_id)
    assert row["payment_mode"] == ""
