"""Configuration loading and path resolution, in one place.

Every command needs the repo root, a YAML file, and a ``--config`` flag. Before
this module each script rebuilt all three, hardcoded ``out/`` relative to the
current working directory, and so only ran correctly from the repo root.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml

_MARKER = Path("config") / "batch.yaml"


def repo_root() -> Path:
    """The project root, found in the order most likely to be right.

    An explicit ``RTI_ROOT`` wins. Otherwise walk up from the working directory
    looking for ``config/batch.yaml``, which lets commands run from any
    subdirectory. Falling back to the installed package's location keeps an
    editable install working when the working directory is elsewhere entirely.
    """
    env = os.environ.get("RTI_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / _MARKER).is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    return repo_root() / "config"


def data_dir() -> Path:
    return repo_root() / "data"


def raw_dir() -> Path:
    return data_dir() / "raw"


def tables_dir() -> Path:
    """The committed, redacted copy. One CSV per table, safe to publish."""
    return data_dir() / "tables"


def private_dir() -> Path:
    """Real data, gitignored. Never leaves the machine it was collected on."""
    return data_dir() / "private"


def private_tables_dir() -> Path:
    """The true tables. `data/tables/` is derived from these by `rti.scrub`."""
    return private_dir() / "tables"


def private_config_dir() -> Path:
    return config_dir() / "private"


def pseudonyms_path() -> Path:
    """Real name to pseudonym. Gitignored, and the only way back."""
    return private_config_dir() / "pseudonyms.yaml"


def evidence_log_path() -> Path:
    """The hand-kept log this study started from. Superseded by the tables."""
    return private_dir() / "rti_filing_evidence_log.csv"


def intake_raw_dir() -> Path:
    """Immutable dumps of what the Google Forms recorded. Never edited.

    These carry whatever the forms collected, including respondent email
    addresses, so they are gitignored rather than committed.
    """
    return private_dir() / "intake_raw"


def scraper_data_dir(state_slug: str) -> Path:
    return data_dir() / "scrapers" / state_slug


def out_dir(batch_id: str) -> Path:
    return repo_root() / "out" / batch_id


def db_path() -> Path:
    return repo_root() / "rti.db"


def load_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_batch(path: str | Path | None = None) -> dict:
    """The batch definition: seed, sampling rules, topics, languages."""
    return load_yaml(path or config_dir() / "batch.yaml")


def load_state_rules() -> dict[str, dict]:
    """Per-state fee and statutory clock, keyed by state name.

    Keeping this out of the letter text is what stops "30 days" and "Rs. 10"
    from being asserted in prose for states where neither is true.
    """
    raw = load_yaml(config_dir() / "state_rules.yaml")
    return {state: dict(rules) for state, rules in (raw.get("states") or {}).items()}


def state_rule(state: str, rules: dict[str, dict] | None = None) -> dict:
    """Rules for one state, falling back to the documented national default."""
    rules = load_state_rules() if rules is None else rules
    if state in rules:
        return rules[state]
    return rules.get("_default", {"fee_inr": 10, "statutory_days": 30})


def due_date(state: str, filing_date: str, rules: dict[str, dict] | None = None) -> str:
    """When a reply is due, from the filing date and the state's statutory clock.

    Derived rather than typed. An RA asked to compute this by hand gets it wrong
    for any state that is not on 30 days, and the error is invisible afterwards.
    """
    from datetime import date, timedelta

    if not filing_date:
        return ""
    try:
        filed = date.fromisoformat(filing_date)
    except ValueError:
        return ""
    days = int(state_rule(state, rules).get("statutory_days", 30))
    return (filed + timedelta(days=days)).isoformat()


def load_filer() -> dict:
    """Who is filing. Stamped into every letter so no RA ever types an address.

    Reads the gitignored `config/private/filer.yaml`, falling back to the
    committed example so a fresh clone renders letters with placeholders rather
    than failing.
    """
    real = private_config_dir() / "filer.yaml"
    if real.is_file():
        return load_yaml(real)
    return load_yaml(config_dir() / "filer.example.yaml")


def config_arg(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """The ``--config`` flag every command shares."""
    parser.add_argument(
        "--config",
        default=None,
        help="batch config YAML (default: config/batch.yaml)",
    )
    return parser
