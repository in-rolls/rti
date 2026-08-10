"""The published copy must be safe, faithful, and stable; the guard must bite."""

from __future__ import annotations

import subprocess
import sys

import pytest

from rti.check import run as check_run
from rti.scrub import (
    DOCUMENT_TOKEN,
    NAME_TOKEN,
    OPAQUE_TOKEN,
    WITHHELD_TOKEN,
    Pseudonyms,
    public_rows,
    redact_row,
    scan_file,
    scrub_person_names,
    scrub_text,
)
from rti.tables import private_table_path, read_table, table_path, write_table

REAL = {
    "application_id": "KA-001",
    "filed_by": "Meera Nair",
    "payment_reference": "9000000000111",
    "evidence_url": "https://drive.google.com/file/d/AbCdEf123/view",
    "screen_recording_url": "",
    "notes": "PIO 9800000123 / pio@example.gov.in. Paid via UPI.",
    "filing_date": "2026-06-15",
    "registration_number": "XYZAB/R/2026/00001",
}


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------


def test_a_person_becomes_a_stable_label():
    p = Pseudonyms()
    assert p.label("Meera Nair") == "RA-01"
    assert p.label("meera  nair") == "RA-01", "spacing and case must not matter"
    assert p.label("Someone Else") == "RA-02"


def test_an_email_maps_to_the_same_person():
    p = Pseudonyms()
    p.label("A Filer")
    assert p.email("A Filer") == "ra-01@redacted.invalid"


def test_the_same_person_is_the_same_label_in_every_table():
    p = Pseudonyms()
    application = redact_row({"filed_by": "Meera Nair"}, p)
    event = redact_row({"recorded_by": "Meera Nair"}, p)
    assert application["filed_by"] == event["recorded_by"] == "RA-01"


def test_the_real_value_never_survives():
    public = redact_row(REAL, Pseudonyms())
    joined = " ".join(public.values())
    for secret in ("Meera", "Nair", "9000000000111", "drive.google", "9800000123"):
        assert secret not in joined


def test_presence_is_preserved_because_absence_is_data():
    """Blanking a URL would assert that no evidence was captured."""
    public = redact_row(REAL, Pseudonyms())
    assert public["evidence_url"] == DOCUMENT_TOKEN
    assert public["screen_recording_url"] == "", "an empty field must stay empty"
    assert public["payment_reference"] == OPAQUE_TOKEN
    assert public["notes"] == WITHHELD_TOKEN


def test_analysable_columns_are_untouched():
    public = redact_row(REAL, Pseudonyms())
    assert public["filing_date"] == REAL["filing_date"]
    assert public["registration_number"] == REAL["registration_number"]
    assert public["application_id"] == REAL["application_id"]


def test_redaction_is_idempotent():
    p = Pseudonyms()
    once = redact_row(REAL, p)
    assert redact_row(once, p) == once


def test_public_rows_extends_the_map_for_new_people(tmp_path, monkeypatch):
    monkeypatch.setenv("RTI_ROOT", str(tmp_path))
    rows = [{"filed_by": "First Person"}, {"filed_by": "Second Person"}]
    assert [r["filed_by"] for r in public_rows(rows)] == ["RA-01", "RA-02"]
    assert len(Pseudonyms.load().people) == 2, "the map must have been saved"


# --------------------------------------------------------------------------
# Free text
# --------------------------------------------------------------------------


def test_contact_details_are_stripped_from_free_text():
    scrubbed = scrub_text("Call 9800000123 or pio@dept.gov.in, see drive.google.com/file/d/x")
    assert "9800000123" not in scrubbed
    assert "pio@dept.gov.in" not in scrubbed


def test_names_are_matched_literally_not_by_honorific():
    """An honorific regex flagged 33 institutions for every 1 person."""
    names = ["thirumathi k.vasanthi"]
    assert scrub_person_names("O/o.thirumathi k.vasanthi, assistant engineer", names) == (
        f"O/o.{NAME_TOKEN}, assistant engineer"
    )
    for institution in (
        "Thiru.Vi.Ka Industrial Estate, Guindy",
        "Dr. M.G.R. Educational and Research Institute",
        "Sri Ramakrishna Mission Vidyalaya",
    ):
        assert scrub_person_names(institution, names) == institution


def test_a_name_does_not_match_inside_a_place_name():
    """`vasanthipuram` is a town in Tirupur."""
    text = "Municipal school, vasanthipuram gandhi nagar tirupur641603"
    assert scrub_person_names(text, ["vasanthi"]) == text


# --------------------------------------------------------------------------
# The private/public boundary
# --------------------------------------------------------------------------


def test_write_table_writes_both_copies(sampled):
    rows = read_table("application")
    rows[0].update({"filed_by": "Meera Nair", "notes": "called the PIO"})
    write_table("application", rows)

    private = private_table_path("application").read_text(encoding="utf-8")
    public = table_path("application").read_text(encoding="utf-8")
    assert "Meera Nair" in private
    assert "Meera Nair" not in public
    assert "RA-01" in public


def test_read_table_prefers_the_real_rows(sampled):
    rows = read_table("application")
    rows[0]["filed_by"] = "Meera Nair"
    write_table("application", rows)
    assert read_table("application")[0]["filed_by"] == "Meera Nair"


def test_a_clone_without_private_data_still_works(sampled):
    """A fresh checkout has only the public tables and must round-trip."""
    rows = read_table("application")
    rows[0]["filed_by"] = "Meera Nair"
    write_table("application", rows)

    private_table_path("application").unlink()
    public = read_table("application")
    assert public[0]["filed_by"] == "RA-01"
    write_table("application", public)
    assert read_table("application")[0]["filed_by"] == "RA-01"


def test_the_public_tables_still_pass_validation(sampled):
    rows = read_table("application")
    rows[0].update(
        {
            "filed_by": "Meera Nair",
            "filing_outcome": "filed",
            "filing_date": "2026-08-01",
            "notes": "anything at all",
        }
    )
    rows[0]["due_date"] = ""
    write_table("application", rows)
    private_table_path("application").unlink()
    assert [e for e in check_run().errors if "due_date" not in e] == []


# --------------------------------------------------------------------------
# The guard
# --------------------------------------------------------------------------


def _scan(tmp_path, text, name="notes.csv", names=("meera nair",)):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return scan_file(path, tmp_path, list(names))


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("filed by Meera Nair on Tuesday", "name"),
        ("write to someone@gmail.com", "email"),
        ("evidence at https://drive.google.com/file/d/abc/view", "document url"),
        ("PIO 9800000123 answered", "phone"),
    ],
)
def test_the_guard_catches_what_it_should(tmp_path, text, kind):
    findings = _scan(tmp_path, text)
    assert [f.kind for f in findings] == [kind]


def test_the_guard_catches_a_name_no_pattern_would_find(tmp_path):
    """The reason the map is searched literally, not just matched by shape."""
    findings = _scan(tmp_path, "spoke to Meera Nair at the counter")
    assert findings and findings[0].kind == "name"


@pytest.mark.parametrize(
    "text",
    [
        "authority_id 7163813153ab is twelve hex characters",
        "authority_id 916522566674 is not a phone number",
        "contact test@example.org",
        "reach us at ra-01@redacted.invalid",
    ],
)
def test_the_guard_does_not_cry_wolf(tmp_path, text):
    assert _scan(tmp_path, text) == []


def test_a_finding_names_the_file_and_line(tmp_path):
    finding = _scan(tmp_path, "ok\nMeera Nair\n")[0]
    assert finding.line == 2
    assert finding.path == "notes.csv"


def test_the_repository_itself_is_clean():
    """The check CI runs, run here so a bad commit fails before it is pushed."""
    result = subprocess.run(
        [sys.executable, "-m", "rti.scrub", "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
