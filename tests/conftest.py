"""A throwaway repo for each test, so nothing touches the real study data.

`RTI_ROOT` is what `rti.config.repo_root` honours first, which is the seam that
lets a test build a five-office frame and a two-state rulebook and run the whole
pipeline against them in a temporary directory.
"""

from __future__ import annotations

import csv
import os

import pytest
import yaml

FRAME_ROWS = [
    # state, department, district, relevant, portal
    ("Karnataka", "Zilla Panchayat Belagavi", "Belagavi", 1, "rti_karnataka"),
    ("Karnataka", "Zilla Panchayat Bidar", "Bidar", 1, "rti_karnataka"),
    ("Karnataka", "Directorate of Municipal Administration", "", 1, "rti_karnataka"),
    ("Karnataka", "Some Irrelevant College", "", 0, "rti_karnataka"),
    ("Delhi", "East Delhi Municipal Corporation", "", 1, "rti_delhi"),
    ("Delhi", "Chief Electoral Office", "", 1, "rti_delhi"),
    ("Maharashtra", "Zilla Parishad Pune", "Pune", 1, ""),
]

BATCH = {
    "batch_id": "test_batch",
    "seed": 12345,
    "frame_csv": "data/frame.csv",
    "sampling": {"relevant_only": True, "n_per_state": 2, "one_per_department": True},
    "topics": {
        "strategy": "fixed",
        "fixed_topic": "rti_meta",
        "weights": {"rti_meta": 0.4, "attendance": 0.3, "financial": 0.3},
        "category_map": {},
    },
    "languages": {
        "default": "en",
        "by_state": {"Karnataka": "kn", "Delhi": "hi", "Maharashtra": "mr"},
    },
    "filing": {"reference_period_months": 12},
}

STATE_RULES = {
    "states": {
        "_default": {"fee_inr": 10, "statutory_days": 30},
        "Karnataka": {"fee_inr": 10, "statutory_days": 30},
        # Deliberately not 30, so a test can prove the clock is not hardcoded.
        "Delhi": {"fee_inr": 20, "statutory_days": 45},
        "Maharashtra": {"fee_inr": 10, "statutory_days": 30},
    }
}

FILER = {
    "name": "Test Filer",
    "address": "1 Test Road, Testville 000001",
    "phone": "+91 90000 00000",
    "email": "test@example.org",
}


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A complete miniature repo, with RTI_ROOT pointed at it."""
    from rti.ids import authority_id, state_code

    (tmp_path / "config").mkdir()
    (tmp_path / "data" / "tables").mkdir(parents=True)
    (tmp_path / "data" / "intake_raw").mkdir(parents=True)

    (tmp_path / "config" / "batch.yaml").write_text(yaml.safe_dump(BATCH), encoding="utf-8")
    (tmp_path / "config" / "state_rules.yaml").write_text(
        yaml.safe_dump(STATE_RULES), encoding="utf-8"
    )
    (tmp_path / "config" / "filer.yaml").write_text(yaml.safe_dump(FILER), encoding="utf-8")

    from rti.frame import FRAME_COLUMNS

    with open(tmp_path / "data" / "frame.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(FRAME_COLUMNS))
        w.writeheader()
        for state, dept, district, relevant, portal in FRAME_ROWS:
            w.writerow(
                {
                    "authority_id": authority_id(state, dept, district, ""),
                    "state": state,
                    "state_code": state_code(state),
                    "department": dept,
                    "district": district,
                    "block": "",
                    "portal": portal,
                    "relevant": relevant,
                    "category": "",
                    "quota_source": "",
                    "quota_role": "",
                    "confidence": "",
                    "source": "test",
                }
            )

    monkeypatch.setenv("RTI_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def sampled(repo):
    """A repo with a batch already drawn."""
    from rti import sample

    sample.main([])
    return repo


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.fixture(autouse=True)
def _no_stray_root(monkeypatch):
    """Fail loudly rather than silently reading the developer's own repo."""
    monkeypatch.delenv("RTI_ROOT", raising=False)
    yield
    os.environ.pop("RTI_ROOT", None)
