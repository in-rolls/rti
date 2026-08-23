"""The sample must be reproducible, and must open a row for every office drawn."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from rti import sample
from rti.config import load_batch
from rti.tables import read_table


def _assignments(repo):
    path = repo / "out" / "test_batch" / "assignments.csv"
    return path.read_bytes(), list(csv.DictReader(path.open(encoding="utf-8")))


def test_two_runs_produce_identical_assignments(repo):
    sample.main([])
    first, _ = _assignments(repo)
    sample.main([])
    second, _ = _assignments(repo)
    assert first == second, "the same config and frame must give the same sample"


def test_draw_is_pure(repo):
    """Same inputs, same output, with no reliance on files or the clock."""
    cfg = load_batch()
    frame = sample.load_frame(repo / "data" / "frame.csv")
    a = sample.draw(cfg, frame, set())
    b = sample.draw(cfg, frame, set())
    assert a == b


def test_row_order_in_the_frame_cannot_change_the_sample(repo):
    cfg = load_batch()
    frame = sample.load_frame(repo / "data" / "frame.csv")
    forward = sample.draw(cfg, frame, set())
    reversed_ = sample.draw(cfg, list(reversed(frame)), set())
    assert [r["authority_id"] for r in forward] == [r["authority_id"] for r in reversed_]


def test_an_application_row_exists_for_every_office_drawn(sampled):
    """The denominator. Rows are written at sampling, not at filing."""
    _, assignments = _assignments(sampled)
    applications = read_table("application")
    assert len(applications) == len(assignments)
    assert {r["application_id"] for r in applications} == {r["application_id"] for r in assignments}


def test_new_rows_start_unreported(sampled):
    """Blank is a real state: nobody has said anything about this application."""
    for row in read_table("application"):
        assert row["filing_outcome"] == ""
        assert row["not_filed_reason"] == ""
        assert row["filing_date"] == ""


def test_only_relevant_offices_are_drawn(sampled):
    drawn = {r["authority_id"] for r in read_table("application")}
    frame = {r["authority_id"]: r for r in sample.load_frame(sampled / "data" / "frame.csv")}
    assert all(frame[a]["relevant"] == 1 for a in drawn)


def test_language_follows_the_state(sampled):
    expected = {"Karnataka": "kn", "Delhi": "hi", "Maharashtra": "mr"}
    for row in read_table("application"):
        assert row["language"] == expected[row["state"]]


def test_channel_is_post_when_no_portal_exists(sampled):
    rows = {r["state"]: r for r in read_table("application")}
    assert rows["Maharashtra"]["channel"] == "post"
    assert rows["Karnataka"]["channel"] == "portal"


def test_rerunning_never_discards_recorded_work(sampled):
    """An RA's answers must survive someone re-running the sampler."""
    from rti.tables import write_table

    applications = read_table("application")
    applications[0]["filing_outcome"] = "filed"
    applications[0]["registration_number"] = "KEEP/ME/001"
    write_table("application", applications)

    sample.main([])

    after = {r["application_id"]: r for r in read_table("application")}
    assert after[applications[0]["application_id"]]["registration_number"] == "KEEP/ME/001"


def test_a_second_batch_does_not_reuse_identifiers(sampled):
    import yaml

    config = sampled / "config" / "batch.yaml"
    cfg = yaml.safe_load(config.read_text())
    first = {r["application_id"] for r in read_table("application")}

    cfg["batch_id"] = "test_batch_2"
    cfg["seed"] = 999
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    sample.main([])

    rows = read_table("application")
    assert len({r["application_id"] for r in rows}) == len(rows), "identifiers collided"
    second = {r["application_id"] for r in rows if r["batch_id"] == "test_batch_2"}
    assert not (first & second)


def test_committed_initial_batch_matches_the_manuscript():
    import yaml

    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "config" / "batch.yaml").read_text(encoding="utf-8"))
    frame = sample.load_frame(root / "data" / "frame.csv")
    rows = sample.draw_initial_batch(cfg, frame)

    assert len(rows) == 1000
    assert len({row["authority_id"] for row in rows}) == 1000
    assert {row["state"] for row in rows} == {"Tamil Nadu"}
    assert Counter(row["tier"] for row in rows) == {
        "Department": 40,
        "Head of Department": 136,
        "Sub Office": 824,
    }
    assert Counter(row["treatment"] for row in rows) == {
        "plain": 700,
        "legal_salience": 300,
    }
    assert Counter(row["assigned_ra"] for row in rows) == {
        "RA1": 250,
        "RA2": 250,
        "RA3": 250,
        "RA4": 250,
    }
    assert len({row["tree_department"] for row in rows}) == 40
    assert rows[0]["application_id"] == "TN-026"
    assert rows[-1]["application_id"] == "TN-1025"

    for ra in cfg["research_assistants"]:
        ra_rows = [row for row in rows if row["assigned_ra"] == ra]
        assert Counter(row["treatment"] for row in ra_rows) == {
            "plain": 175,
            "legal_salience": 75,
        }

    by_stratum = defaultdict(Counter)
    for row in rows:
        by_stratum[(row["tree_department"], row["tier"], row["treatment"])][row["assigned_ra"]] += 1
    for counts in by_stratum.values():
        all_ra_counts = [counts[ra] for ra in cfg["research_assistants"]]
        assert max(all_ra_counts) - min(all_ra_counts) <= 1


def test_initial_batch_is_independent_of_frame_row_order():
    import yaml

    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "config" / "batch.yaml").read_text(encoding="utf-8"))
    frame = sample.load_frame(root / "data" / "frame.csv")
    forward = sample.draw_initial_batch(cfg, frame)
    reversed_rows = sample.draw_initial_batch(cfg, list(reversed(frame)))
    assert forward == reversed_rows
