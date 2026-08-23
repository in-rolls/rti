"""The frame builder repairs known defects and records every repair."""

from __future__ import annotations

import csv
import json

from rti.frame import (
    Provenance,
    build,
    canonical_portal,
    canonical_state,
    clean_text,
    load_classified,
    load_scraper_universe,
    replace_state_with_scraper,
)

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


def test_build_repairs_and_preserves_colliding_flat_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("RTI_ROOT", str(tmp_path))
    raw = _write_raw(tmp_path)
    out = tmp_path / "frame.csv"
    rows, provenance = build([raw], out)

    states = {r["state"] for r in rows}
    assert "Kanataka" not in states
    assert "Karnataka" in states

    assert len(rows) == 4, "a flat list cannot prove that identical labels are one office"
    assert len({row["authority_id"] for row in rows}) == 4
    assert provenance["changes"]["row:flat_key_disambiguated"] == 1
    assert provenance["summary"]["n_relevant"] == 2

    # Provenance must be serialisable; it is committed alongside the frame.
    json.dumps(provenance)


def test_raw_file_is_never_modified(tmp_path, monkeypatch):
    monkeypatch.setenv("RTI_ROOT", str(tmp_path))
    raw = _write_raw(tmp_path)
    before = raw.read_bytes()
    build([raw], tmp_path / "frame.csv")
    assert raw.read_bytes() == before


def test_scraper_tree_replaces_flat_state_and_uses_node_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("RTI_ROOT", str(tmp_path))
    raw = tmp_path / "raw.csv"
    with open(raw, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(RAW_HEADER)
        w.writerow(
            ["Tamil Nadu", "Same office", "TN portal", "Chennai", "", 1, "School", "", "", "", ""]
        )
        w.writerow(
            ["Tamil Nadu", "Same office", "TN portal", "Chennai", "", 1, "School", "", "", "", ""]
        )
        w.writerow(RAW_ROWS[0])

    universe = tmp_path / "universe.csv"
    fields = [
        "node_id",
        "level",
        "level_label",
        "name",
        "address",
        "is_leaf",
        "has_children",
        "parent_id",
        "parent_name",
        "department",
        "path",
        "reservation_relevant",
    ]
    with open(universe, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for node_id in ("node-a", "node-b"):
            w.writerow(
                {
                    "node_id": node_id,
                    "level": 3,
                    "level_label": "Sub Office",
                    "name": "Same office",
                    "address": f"Address {node_id}",
                    "is_leaf": "True",
                    "has_children": 0,
                    "parent_id": "parent",
                    "parent_name": "Parent office",
                    "department": "Top department",
                    "path": f"Top department > Parent office > {node_id}",
                    "reservation_relevant": "True",
                }
            )

    prov = Provenance()
    flat = load_classified(raw, prov)
    tree = load_scraper_universe(universe, "Tamil Nadu", "rti_tamil_nadu", prov)
    rows = replace_state_with_scraper(flat, tree, "Tamil Nadu", prov)

    tn = [row for row in rows if row["state"] == "Tamil Nadu"]
    assert {row["authority_id"] for row in tn} == {"TN-node-a", "TN-node-b"}
    assert {row["node_id"] for row in tn} == {"node-a", "node-b"}
    assert all(row["tree_department"] == "Top department" for row in tn)
    assert all(row["category"] == "School" for row in tn)
