"""Identifiers, and the text normalisation they depend on.

Two identifiers do different jobs and must not be conflated. ``authority_id`` is
a content hash: stable, collision-resistant, and unreadable, which is fine
because only code ever looks at it. ``application_id`` is read aloud off a
receipt and picked from a dropdown by a person, so it is short, sequential, and
checkable at a glance.
"""

from __future__ import annotations

import hashlib
import re

STATE_CODES = {
    "Andhra Pradesh": "AP",
    "Assam": "AS",
    "Bihar": "BR",
    "Chhattisgarh": "CG",
    "Delhi": "DL",
    "Goa": "GA",
    "Gujarat": "GJ",
    "Haryana": "HR",
    "Himachal Pradesh": "HP",
    "Jharkhand": "JH",
    "Karnataka": "KA",
    "Kerala": "KL",
    "Madhya Pradesh": "MP",
    "Maharashtra": "MH",
    "Odisha": "OD",
    "Punjab": "PB",
    "Rajasthan": "RJ",
    "Tamil Nadu": "TN",
    "Telangana": "TG",
    "Uttar Pradesh": "UP",
    "Uttarakhand": "UK",
    "West Bengal": "WB",
}
"""Standard two-letter codes. `TG` for Telangana and `DL` for Delhi match the
identifiers already used in `data/rti_filing_evidence_log.csv`."""


def norm(s: str | None) -> str:
    """Collapse whitespace and strip. Case is preserved; this is display text."""
    return " ".join((s or "").strip().split())


def norm_key(s: str | None) -> str:
    """Normalise for comparison and hashing: whitespace collapsed, lowercased."""
    return norm(s).lower()


def authority_id(state: str, department: str, district: str = "", block: str = "") -> str:
    """Stable content hash for an office, independent of row order in the frame."""
    key = "|".join(norm_key(v) for v in (state, department, district, block))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def state_code(state: str) -> str:
    """Two-letter code for a state, deriving one if the state is unlisted."""
    state = norm(state)
    if state in STATE_CODES:
        return STATE_CODES[state]
    letters = re.sub(r"[^A-Za-z]", "", state).upper()
    return (letters[:2] or "XX").ljust(2, "X")


def application_id(code: str, sequence: int) -> str:
    """``KA-014``. Sequential per state and continuing across batches, so an RA
    can read it off a receipt and spot a transposed digit."""
    return f"{code}-{sequence:03d}"


_APP_ID_RE = re.compile(r"^([A-Z]{2})-(\d+)$")


def parse_application_id(value: str) -> tuple[str, int] | None:
    m = _APP_ID_RE.match(norm(value))
    return (m.group(1), int(m.group(2))) if m else None


def next_sequence(existing_ids: list[str] | set[str], code: str) -> int:
    """One past the highest sequence already issued for a state.

    Reading this from the committed application table is what keeps identifiers
    unique across batches without a database or a counter file.
    """
    highest = 0
    for value in existing_ids:
        parsed = parse_application_id(value)
        if parsed and parsed[0] == code:
            highest = max(highest, parsed[1])
    return highest + 1
