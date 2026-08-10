"""Build the canonical sampling frame from the scraped and classified sources.

The frame is the study's left table: one row per office that could be written
to. It is generated, never hand-edited, and every departure from the raw source
is written to `data/frame_provenance.json` so a number in a paper can be traced
back to the byte it came from.

The raw files stay exactly as they were collected. Corrections happen here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import data_dir, raw_dir, repo_root, scraper_data_dir
from .ids import authority_id, norm, state_code

FRAME_COLUMNS = (
    "authority_id",
    "state",
    "state_code",
    "department",
    "district",
    "block",
    "portal",
    "relevant",
    "category",
    "quota_source",
    "quota_role",
    "confidence",
    "source",
)

STATE_ALIASES = {
    "Kanataka": "Karnataka",
}
"""Misspellings in the raw frame that silently break every per-state lookup.

`Kanataka` covers 1,699 rows. Because `config/batch.yaml` keys languages by
state name, those rows were falling through to the English default instead of
drawing Kannada.
"""

PORTAL_SLUGS = {
    "rti_online_delhi": "rti_delhi",
    "rti_telangana": "rti_telangana",
    "rti karnataka": "rti_karnataka",
    "rti rajasthan": "rti_rajasthan",
    "rti online_maharashtra": "rti_maharashtra",
    "rti_tamilnadu_online": "rti_tamil_nadu",
}

_WRAPPING_QUOTES = re.compile(r'^"(.*)"$', re.S)
_QUOTE_AS_APOSTROPHE = re.compile(r'(?<=[A-Za-z])"(?=[A-Za-z])')


class Provenance:
    """Every change the builder makes, with an example of each."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.examples: dict[str, list[str]] = {}

    def record(self, kind: str, before: str, after: str) -> None:
        self.counts[kind] += 1
        shown = self.examples.setdefault(kind, [])
        if len(shown) < 5:
            shown.append(f"{before!r} -> {after!r}")

    def as_dict(self) -> dict:
        return {
            "changes": dict(sorted(self.counts.items())),
            "examples": {k: v for k, v in sorted(self.examples.items())},
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_text(value: str | None, prov: Provenance, field: str) -> str:
    """Collapse whitespace and repair quote damage, logging what changed.

    Three defects appear in the raw frame: a department name carrying an
    embedded CRLF, names wrapped in a stray pair of double quotes, and double
    quotes standing in for apostrophes (`ST PAUL"S`).
    """
    original = value or ""
    text = norm(original)
    if original.strip() != text:
        prov.record(f"{field}:whitespace", original, text)

    unwrapped = _WRAPPING_QUOTES.sub(r"\1", text).strip()
    if unwrapped != text:
        prov.record(f"{field}:wrapping_quotes", text, unwrapped)
        text = unwrapped

    fixed = _QUOTE_AS_APOSTROPHE.sub("'", text)
    if fixed != text:
        prov.record(f"{field}:quote_as_apostrophe", text, fixed)
        text = fixed
    return text


def canonical_state(value: str, prov: Provenance) -> str:
    state = norm(value)
    if state in STATE_ALIASES:
        fixed = STATE_ALIASES[state]
        prov.record("state:alias", state, fixed)
        return fixed
    return state


def canonical_portal(value: str, prov: Provenance) -> str:
    portal = norm(value)
    if not portal:
        return ""
    slug = PORTAL_SLUGS.get(portal.lower())
    if slug is None:
        slug = re.sub(r"[^a-z0-9]+", "_", portal.lower()).strip("_")
    if slug != portal:
        prov.record("portal:slug", portal, slug)
    return slug


def _blankish(value: str) -> str:
    return "" if value.upper() in {"NA", "N/A", "NIL", "NONE", "-"} else value


def load_classified(path: Path, prov: Provenance) -> list[dict]:
    """The hand-classified national frame: six states, one row per office."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    rows = []
    for r in raw:
        state = canonical_state(r.get("State", ""), prov)
        department = clean_text(r.get("Department"), prov, "department")
        district = _blankish(clean_text(r.get("District"), prov, "district"))
        block = _blankish(clean_text(r.get("Block"), prov, "block"))
        if not state or not department:
            prov.record("row:dropped_missing_key", str(r)[:120], "")
            continue
        rows.append(
            {
                "authority_id": authority_id(state, department, district, block),
                "state": state,
                "state_code": state_code(state),
                "department": department,
                "district": district,
                "block": block,
                "portal": canonical_portal(r.get("Website", ""), prov),
                "relevant": 1 if norm(r.get("Relevant", "")) == "1" else 0,
                "category": clean_text(r.get("Category"), prov, "category"),
                "quota_source": norm(r.get("Quota_Source", "")),
                "quota_role": norm(r.get("Quota_Role", "")),
                "confidence": norm(r.get("Confidence", "")),
                "source": path.name,
            }
        )
    return rows


def load_scraper_universe(path: Path, state: str, portal: str, prov: Provenance) -> list[dict]:
    """A state universe straight from `rti-parse-*` and `rti-categorize-*`.

    Lets a re-scraped state be merged back into the frame rather than
    hand-patched into the classified file.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    rows = []
    for r in raw:
        department = clean_text(r.get("name"), prov, "department")
        if not department:
            continue
        district = _blankish(clean_text(r.get("parent_name"), prov, "district"))
        rows.append(
            {
                "authority_id": authority_id(state, department, district, ""),
                "state": state,
                "state_code": state_code(state),
                "department": department,
                "district": district,
                "block": "",
                "portal": portal,
                "relevant": 1 if norm(r.get("reservation_relevant", "")).lower() == "true" else 0,
                "category": clean_text(r.get("level_label"), prov, "category"),
                "quota_source": "",
                "quota_role": "",
                "confidence": "",
                "source": path.name,
            }
        )
    return rows


def dedupe(rows: list[dict], prov: Provenance) -> list[dict]:
    """One row per office. Later sources win, so a re-scrape replaces a state."""
    by_id: dict[str, dict] = {}
    for row in rows:
        key = row["authority_id"]
        if key in by_id and by_id[key]["source"] == row["source"]:
            prov.record("row:duplicate_dropped", f'{row["state"]} | {row["department"]}', "")
            continue
        if key in by_id:
            prov.record("row:replaced_by_later_source", by_id[key]["source"], row["source"])
        by_id[key] = row
    return sorted(
        by_id.values(),
        key=lambda r: (r["state"], r["department"], r["district"], r["block"]),
    )


def write_frame(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(FRAME_COLUMNS))
        w.writeheader()
        w.writerows(rows)


def summarise(rows: list[dict]) -> dict:
    by_state = Counter(r["state"] for r in rows)
    relevant = Counter(r["state"] for r in rows if r["relevant"] == 1)
    return {
        "n_rows": len(rows),
        "n_states": len(by_state),
        "by_state": dict(sorted(by_state.items())),
        "relevant_by_state": dict(sorted(relevant.items())),
        "n_relevant": sum(relevant.values()),
    }


def build(sources: list[Path], out_path: Path) -> tuple[list[dict], dict]:
    prov = Provenance()
    rows: list[dict] = []
    source_records = []
    for path in sources:
        if not path.is_file():
            sys.exit(f"source not found: {path}")
        rows.extend(load_classified(path, prov))
        source_records.append(
            {"path": str(path.relative_to(repo_root())), "sha256": sha256_file(path)}
        )
    rows = dedupe(rows, prov)
    write_frame(rows, out_path)

    provenance = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": source_records,
        "output": {"path": str(out_path.relative_to(repo_root())), "sha256": sha256_file(out_path)},
        "summary": summarise(rows),
        **prov.as_dict(),
    }
    return rows, provenance


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Build data/frame.csv from the raw classified sources."
    )
    ap.add_argument(
        "--source",
        action="append",
        type=Path,
        help="raw classified CSV; repeatable (default: the national classified frame)",
    )
    ap.add_argument("--out", type=Path, default=None, help="default: data/frame.csv")
    args = ap.parse_args(argv)

    sources = args.source or [raw_dir() / "state_department_classified_FINAL.csv"]
    out_path = args.out or data_dir() / "frame.csv"
    rows, provenance = build(sources, out_path)

    prov_path = data_dir() / "frame_provenance.json"
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2, ensure_ascii=False)
        f.write("\n")

    summary = provenance["summary"]
    print(f"frame: {summary['n_rows']} offices across {summary['n_states']} states -> {out_path}")
    print(f"relevant: {summary['n_relevant']}")
    for kind, count in sorted(provenance["changes"].items()):
        print(f"  fixed {kind}: {count}")
    print(f"provenance -> {prov_path}")


# Referenced by the docs so a re-scraped state can be merged back in.
__all__ = ["build", "load_classified", "load_scraper_universe", "scraper_data_dir", "FRAME_COLUMNS"]

if __name__ == "__main__":
    main()
