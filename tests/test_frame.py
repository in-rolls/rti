"""The frame builder repairs known defects and records every repair."""

from __future__ import annotations

import csv
import json

from rti.frame import Provenance, build, canonical_portal, canonical_state, clean_text

RAW_HEADER = [
    "State",
    "Department",
    "Website",
    "District",
    "Block",
    "Relevant",
    "Category",
    "Confidence",
    "Verify_Note",
    "Quota_Source",
    "Quota_Role",
]

RAW_ROWS = [
    # The misspelling that silently broke the per-state language lookup.
    [
        "Kanataka",
        "Zilla Panchayat Belagavi",
        "RTI Karnataka",
        "Belagavi",
        "NA",
        "1",
        "",
        "",
        "",
        "Yes",
        "Subject (own notification)",
    ],
    # An embedded newline in a department name.
    [
        "Maharashtra",
        "Dept of Animal Husbandry\r\nGovernment of Maharashtra",
        "RTI Online_Maharashtra",
        "NA",
        "NA",
        "0",
        "",
        "",
        "",
        "",
        "",
    ],
    # A double quote standing in for an apostrophe.
    [
        "Tamil Nadu",
        'ST PAUL"S HIGHER SECONDARY SCHOOL',
        "RTI_Tamilnadu_Online",
        "Chennai",
        "School",
        "0",
        "",
        "",
        "",
        "",
        "",
    ],
    # An exact duplicate of the first row.
    [
        "Kanataka",
        "Zilla Panchayat Belagavi",
        "RTI Karnataka",
        "Belagavi",
        "NA",
        "1",
        "",
        "",
        "",
        "Yes",
        "Subject (own notification)",
    ],
]


def _write_raw(tmp_path):
    path = tmp_path / "raw.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(RAW_HEADER)
        w.writerows(RAW_ROWS)
    return path


def test_state_misspelling_is_corrected():
    prov = Provenance()
    assert canonical_state("Kanataka", prov) == "Karnataka"
    assert prov.counts["state:alias"] == 1


def test_portal_names_become_consistent_slugs():
    prov = Provenance()
    assert canonical_portal("RTI Karnataka", prov) == "rti_karnataka"
    assert canonical_portal("RTI_Online_Delhi", prov) == "rti_delhi"
    assert canonical_portal("", prov) == ""


def test_text_defects_are_repaired_and_logged():
    prov = Provenance()
    assert clean_text("a\r\nb", prov, "department") == "a b"
    assert clean_text('ST PAUL"S SCHOOL', prov, "department") == "ST PAUL'S SCHOOL"
    assert clean_text('"WRAPPED NAME"', prov, "department") == "WRAPPED NAME"
    assert prov.counts["department:whitespace"] == 1
    assert prov.counts["department:quote_as_apostrophe"] == 1
    assert prov.counts["department:wrapping_quotes"] == 1


def test_build_repairs_deduplicates_and_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("RTI_ROOT", str(tmp_path))
    raw = _write_raw(tmp_path)
    out = tmp_path / "frame.csv"
    rows, provenance = build([raw], out)

    states = {r["state"] for r in rows}
    assert "Kanataka" not in states
    assert "Karnataka" in states

    assert len(rows) == 3, "the duplicated row should have been dropped"
    assert provenance["changes"]["row:duplicate_dropped"] == 1
    assert provenance["summary"]["n_relevant"] == 1

    # Provenance must be serialisable; it is committed alongside the frame.
    json.dumps(provenance)


def test_raw_file_is_never_modified(tmp_path, monkeypatch):
    monkeypatch.setenv("RTI_ROOT", str(tmp_path))
    raw = _write_raw(tmp_path)
    before = raw.read_bytes()
    build([raw], tmp_path / "frame.csv")
    assert raw.read_bytes() == before
