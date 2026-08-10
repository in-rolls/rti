#!/usr/bin/env python3
"""Stage 3 (optional): flag offices likely relevant to reservation data.

Adds a ``reservation_relevant`` flag and the matched keywords to each office in
``data/universe.csv``, writing ``data/universe_categorized.csv``. This is a
first-pass screen to shrink the manual-review set -- not a final filter. Review
the flagged rows by hand before filing.
"""

from __future__ import annotations

import csv

from ...scrub import scrub_person_names
from .common import DATA

# Keywords that mark a department/office as plausibly holding reservation data.
# Matched case-insensitively against the office name, its department, and path.
KEYWORDS = [
    "backward class",
    "most backward",
    "denotified",
    "adi dravidar",
    "adidravidar",
    "tribal",
    "scheduled caste",
    "scheduled tribe",
    "minorit",
    "reservation",
    "social welfare",
    "vanniyakula",
    "welfare board",
]


def matches(text: str) -> list[str]:
    low = text.lower()
    return [kw for kw in KEYWORDS if kw in low]


def main() -> None:
    src = DATA / "universe.csv"
    if not src.exists():
        raise SystemExit(f"{src} not found. Run parse.py first.")
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    out_cols = list(rows[0].keys()) + ["reservation_relevant", "matched_keywords"]
    flagged = 0
    with (DATA / "universe_categorized.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=out_cols)
        w.writeheader()
        scrubbed = 0
        for r in rows:
            hits = matches(f"{r['name']} {r['department']} {r['path']}")
            r["reservation_relevant"] = bool(hits)
            r["matched_keywords"] = "; ".join(sorted(set(hits)))
            flagged += bool(hits)
            # This file is committed. A handful of scraped addresses name the
            # officer sitting in the office; the office itself stays intact.
            address = scrub_person_names(r.get("address", ""))
            scrubbed += address != r.get("address", "")
            r["address"] = address
            w.writerow(r)
    print(
        f"Flagged {flagged}/{len(rows)} offices as reservation-relevant "
        f"-> {DATA}/universe_categorized.csv"
    )
    if scrubbed:
        print(f"Removed a named individual from {scrubbed} address(es) before writing")


if __name__ == "__main__":
    main()
