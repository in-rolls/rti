#!/usr/bin/env python3
"""Stage 2: parse the crawled artifacts into analysis-ready CSVs (offline).

Internal (clickable) offices come from the crawl manifest -- each has a saved
page in ``data/raw/``. Leaf offices ("No Suboffices Currently Onboarded") have no
page of their own, so they are derived here by parsing the table rows of every
saved page. A leaf is identified by (parent, name, address), which keeps
same-named-but-distinct siblings (e.g. several TANGEDCO branch offices) apart
while collapsing exact-duplicate rows.

Outputs:
  data/nodes.csv     one row per office: id, level, name, address, parent, path
  data/edges.csv     parent_id -> child_id
  data/universe.csv  denormalized RTI-target list (every office + department + path)

No network access. Idempotent and re-runnable.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict

from common import (
    DATA,
    MANIFEST,
    RAW,
    ROOT_ID,
    clean,
    node_id_for,
    norm,
    parse_rows,
)

LEVEL_LABELS = {0: "State (root)", 1: "Department", 2: "Head of Department"}


def level_label(depth: int) -> str:
    return LEVEL_LABELS.get(depth, "Sub Office")


def load_pages() -> dict[str, dict]:
    """Internal offices = manifest records that have a saved page (root + fetched)."""
    if not MANIFEST.exists():
        sys.exit(f"No manifest at {MANIFEST}. Run scrape.py first.")
    pages: dict[str, dict] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("file") and (RAW / rec["file"]).exists():
                pages[rec["node_id"]] = rec
    return pages


def derive_leaves(pages: dict[str, dict]) -> dict[str, dict]:
    """Leaf offices, parsed from the rows of every saved page."""
    leaves: dict[str, dict] = {}
    for p in pages.values():
        for row in parse_rows((RAW / p["file"]).read_text(encoding="utf-8")):
            if not (row["is_leaf"] or row["token"] is None):
                continue  # links are internal nodes, already in `pages`
            if not norm(row["name"]):
                continue
            key = node_id_for(f"{p['node_id']}|{norm(row['name'])}|{norm(row['address'])}")
            if key in leaves or key in pages:
                continue  # collapse exact-duplicate listings
            leaves[key] = {
                "node_id": key,
                "parent_id": p["node_id"],
                "depth": p["depth"] + 1,
                "name": row["name"],
                "address": row["address"],
                "is_leaf": True,
            }
    return leaves


def human_path(node_id: str, nodes: dict[str, dict]) -> list[str]:
    """Original-case names from the first department down to this node."""
    chain, cur, guard = [], node_id, 0
    while cur and cur in nodes and cur != ROOT_ID and guard < 50:
        chain.append(nodes[cur]["name"])
        cur = nodes[cur].get("parent_id")
        guard += 1
    return list(reversed(chain))


def validate(pages: dict[str, dict], nodes: dict[str, dict]) -> None:
    """Confirm every clickable link on every page resolved to a fetched page."""
    child_names = defaultdict(set)
    for n in nodes.values():
        if n["parent_id"]:
            child_names[n["parent_id"]].add(norm(n["name"]))
    link_rows = link_missing = 0
    for p in pages.values():
        for row in parse_rows((RAW / p["file"]).read_text(encoding="utf-8")):
            if row["is_leaf"] or row["token"] is None:
                continue
            link_rows += 1
            if norm(row["name"]) not in child_names.get(p["node_id"], set()):
                link_missing += 1
    by_level = Counter(level_label(n["depth"]) for n in nodes.values())
    print(f"Offices: {len(nodes)} | departments: "
          f"{sum(1 for n in nodes.values() if n['depth'] == 1)} | "
          f"leaves: {sum(1 for n in nodes.values() if n['is_leaf'])}")
    print("By level:", dict(by_level))
    verdict = "OK -- every clickable link resolved" if link_missing == 0 \
        else f"{link_missing}/{link_rows} links unresolved (crawl incomplete)"
    print(f"Completeness: {link_rows} internal links checked -> {verdict}")


def write_outputs(nodes: dict[str, dict]) -> None:
    children = defaultdict(int)
    for n in nodes.values():
        if n["parent_id"]:
            children[n["parent_id"]] += 1

    rows = []
    for nid, n in nodes.items():
        if nid == ROOT_ID:
            continue
        path = human_path(nid, nodes)
        rows.append(
            {
                "node_id": nid,
                "level": n["depth"],
                "level_label": level_label(n["depth"]),
                "name": n["name"],
                "address": n["address"],
                "is_leaf": n["is_leaf"],
                "has_children": children.get(nid, 0),
                "parent_id": n["parent_id"],
                "parent_name": nodes.get(n["parent_id"], {}).get("name", ""),
                "department": path[0] if path else "",
                "path": " > ".join(path),
            }
        )
    rows.sort(key=lambda r: (r["department"], r["level"], r["name"]))

    cols = ["node_id", "level", "level_label", "name", "address", "is_leaf",
            "has_children", "parent_id", "parent_name", "department", "path"]
    DATA.mkdir(exist_ok=True)
    for fname in ("nodes.csv", "universe.csv"):
        with (DATA / fname).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    with (DATA / "edges.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["parent_id", "parent_name", "child_id", "child_name"])
        for nid, n in nodes.items():
            if n["parent_id"] and n["parent_id"] != ROOT_ID:
                w.writerow([n["parent_id"], nodes.get(n["parent_id"], {}).get("name", ""),
                            nid, n["name"]])
    print(f"Wrote {len(rows)} offices to data/nodes.csv, data/universe.csv, data/edges.csv")


def main() -> None:
    pages = load_pages()
    leaves = derive_leaves(pages)
    nodes = {**pages, **leaves}
    for n in nodes.values():  # internal names come from the manifest unnormalized
        n["name"] = clean(n.get("name", ""))
        n["address"] = clean(n.get("address", ""))
    validate(pages, nodes)
    write_outputs(nodes)


if __name__ == "__main__":
    main()
