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
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from .config import data_dir, raw_dir, repo_root, scraper_data_dir
from .ids import authority_id, crawled_authority_id, norm, norm_key, state_code

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
    "node_id",
    "parent_id",
    "parent_name",
    "tree_department",
    "level",
    "level_label",
    "path",
    "is_leaf",
    "has_children",
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
    occurrences: Counter[tuple[str, str, str, str]] = Counter()
    for source_row, r in enumerate(raw, start=2):
        state = canonical_state(r.get("State", ""), prov)
        department = clean_text(r.get("Department"), prov, "department")
        district = _blankish(clean_text(r.get("District"), prov, "district"))
        block = _blankish(clean_text(r.get("Block"), prov, "block"))
        if not state or not department:
            prov.record("row:dropped_missing_key", str(r)[:120], "")
            continue
        flat_key = tuple(norm_key(v) for v in (state, department, district, block))
        occurrences[flat_key] += 1
        occurrence = occurrences[flat_key]
        if occurrence > 1:
            prov.record(
                "row:flat_key_disambiguated",
                f"{state} | {department} | source row {source_row}",
                f"occurrence {occurrence}",
            )
        rows.append(
            {
                "authority_id": authority_id(
                    state, department, district, block, occurrence=occurrence
                ),
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
                "node_id": "",
                "parent_id": "",
                "parent_name": "",
                "tree_department": "",
                "level": "",
                "level_label": "",
                "path": "",
                "is_leaf": "",
                "has_children": "",
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
        office_name = clean_text(r.get("name"), prov, "department")
        node_id = norm(r.get("node_id", ""))
        if not office_name or not node_id:
            continue
        rows.append(
            {
                "authority_id": crawled_authority_id(state, node_id),
                "state": state,
                "state_code": state_code(state),
                "department": office_name,
                "district": "",
                "block": "",
                "portal": portal,
                "relevant": 1 if norm(r.get("reservation_relevant", "")).lower() == "true" else 0,
                "category": "",
                "quota_source": "",
                "quota_role": "",
                "confidence": "",
                "node_id": node_id,
                "parent_id": norm(r.get("parent_id", "")),
                "parent_name": clean_text(r.get("parent_name"), prov, "parent_name"),
                "tree_department": clean_text(r.get("department"), prov, "tree_department"),
                "level": norm(r.get("level", "")),
                "level_label": clean_text(r.get("level_label"), prov, "level_label"),
                "path": clean_text(r.get("path"), prov, "path"),
                "is_leaf": norm(r.get("is_leaf", "")),
                "has_children": norm(r.get("has_children", "")),
                "source": path.name,
            }
        )
    return rows


def replace_state_with_scraper(
    rows: list[dict], scraper_rows: list[dict], state: str, prov: Provenance
) -> list[dict]:
    """Replace a flat state slice with its portal crawl without losing coding.

    The classified national file is a flattened export of the same Tamil Nadu
    crawl. Office names have the same multiset but not the same row order, so
    classification fields are joined by normalized name and occurrence. The
    tree remains the left table: every portal node survives exactly once.
    """
    flat = [row for row in rows if row["state"] == state]
    rest = [row for row in rows if row["state"] != state]
    by_name: dict[str, deque[dict]] = defaultdict(deque)
    for row in flat:
        by_name[norm_key(row["department"])].append(row)

    unmatched = []
    for row in scraper_rows:
        candidates = by_name[norm_key(row["department"])]
        if not candidates:
            unmatched.append(row["department"])
            continue
        classified = candidates.popleft()
        for field in ("district", "block", "category", "quota_source", "quota_role", "confidence"):
            row[field] = classified[field]

    unused = [row["department"] for candidates in by_name.values() for row in candidates]
    if unmatched or unused:
        raise ValueError(
            f"{state} scraper/classified join is not 1:1: "
            f"{len(unmatched)} unmatched scraper rows, {len(unused)} unused classified rows"
        )
    prov.record(
        "row:state_replaced_by_scraper",
        f"{state}: {len(flat)} flat rows",
        f"{len(scraper_rows)} portal nodes",
    )
    return rest + scraper_rows


def dedupe(rows: list[dict], prov: Provenance) -> list[dict]:
    """Assert the declared office identifiers are unique; never collapse rows."""
    by_id: dict[str, dict] = {}
    for row in rows:
        key = row["authority_id"]
        if key in by_id:
            raise ValueError(
                f"authority_id collision {key}: "
                f"{by_id[key]['state']} | {by_id[key]['department']} and "
                f"{row['state']} | {row['department']}"
            )
        by_id[key] = row
    return sorted(
        by_id.values(),
        key=lambda r: (
            r["state"],
            r["tree_department"],
            int(r["level"] or 999),
            r["department"],
            r["node_id"],
            r["district"],
            r["block"],
            r["authority_id"],
        ),
    )


def write_frame(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(FRAME_COLUMNS), lineterminator="\n")
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


def build(
    sources: list[Path],
    out_path: Path,
    scraper_sources: list[tuple[Path, str, str]] | None = None,
) -> tuple[list[dict], dict]:
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
    for path, state, portal in scraper_sources or []:
        if not path.is_file():
            sys.exit(f"source not found: {path}")
        scraper_rows = load_scraper_universe(path, state, portal, prov)
        rows = replace_state_with_scraper(rows, scraper_rows, state, prov)
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
    ap.add_argument(
        "--without-tamil-nadu-tree",
        action="store_true",
        help="do not replace the flat Tamil Nadu slice with its committed crawl",
    )
    args = ap.parse_args(argv)

    sources = args.source or [raw_dir() / "state_department_classified_FINAL.csv"]
    out_path = args.out or data_dir() / "frame.csv"
    scraper_sources = []
    tn_tree = scraper_data_dir("tamil_nadu") / "universe_categorized.csv"
    if not args.without_tamil_nadu_tree and tn_tree.is_file():
        scraper_sources.append((tn_tree, "Tamil Nadu", "rti_tamil_nadu"))
    rows, provenance = build(sources, out_path, scraper_sources)

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
__all__ = [
    "build",
    "load_classified",
    "load_scraper_universe",
    "replace_state_with_scraper",
    "scraper_data_dir",
    "FRAME_COLUMNS",
]

if __name__ == "__main__":
    main()
