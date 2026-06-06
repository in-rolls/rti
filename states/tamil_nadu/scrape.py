#!/usr/bin/env python3
"""Stage 1: crawl the Tamil Nadu RTI public-authority tree and save raw HTML.

Walks the recursive tree of ``show_sub_office.php`` pages rooted at
``displayPa.php``. Because the link tokens are randomized per request (see
common), node **identity is the normalized path of office names**, not the
token. For each office with a sub-office page we save the raw HTML to
``data/raw/<node_id>.html``; for every office (including leaves that have no page)
we append a record to ``data/manifest.jsonl``.

The site is geo-fenced to Indian IPs, so run it with an Indian egress (e.g.
ProtonVPN India connected). It throttles, retries with backoff, and is resumable
(rerunning skips offices already in the manifest).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import deque

import requests

from common import (
    ENTRY,
    INDEX,
    MANIFEST,
    PATH_SEP,
    RAW,
    ROOT_ID,
    UA,
    BASE,
    node_id_for,
    norm,
    parse_rows,
)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


def fetch(session, url, referer, *, timeout, retries, throttle):
    """GET with backoff. Returns (status, text) or (status, None) on failure.

    The server emits HTTP 500 with a valid body on these pages, so any response
    carrying a non-trivial body is treated as success regardless of status.
    """
    status: object = None
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, headers={"Referer": referer}, timeout=timeout)
            if r.text and len(r.text) > 500:
                return r.status_code, r.text
            status = r.status_code
        except requests.RequestException as exc:
            status = f"ERR:{type(exc).__name__}"
        if attempt < retries:
            wait = throttle * (2 ** (attempt - 1)) + random.uniform(0, 1)
            print(f"    retry {attempt}/{retries} ({status}) in {wait:.1f}s", flush=True)
            time.sleep(wait)
    return status, None


def preflight(session, timeout):
    """Confirm Indian egress and return the root page HTML (fetched once)."""
    print(f"Preflight: GET {ENTRY}", flush=True)
    try:
        session.get(INDEX, timeout=timeout)  # prime cookies
        r = session.get(ENTRY, headers={"Referer": INDEX}, timeout=timeout)
    except requests.RequestException as exc:
        sys.exit(
            f"\n  Could not reach {BASE} ({type(exc).__name__}).\n"
            "  The TN RTI site is geo-fenced to Indian IPs -- is ProtonVPN India connected?\n"
        )
    if not (r.text and len(r.text) > 500):
        sys.exit(f"\n  {ENTRY} returned no usable body (status {r.status_code}).\n"
                 "  Is ProtonVPN India connected?\n")
    print(f"  OK ({len(r.text)} bytes). Indian egress confirmed.", flush=True)
    return r.text


def load_done() -> dict[str, dict]:
    """Resume support: node_id -> manifest record for offices already recorded."""
    done: dict[str, dict] = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["node_id"]] = rec
    return done


def crawl(*, max_depth, limit, timeout, retries, throttle):
    RAW.mkdir(parents=True, exist_ok=True)
    session = make_session()
    root_html = preflight(session, timeout)

    done = load_done()
    visited: set[str] = set(done)
    print(f"Resuming: {len(done)} offices already recorded.", flush=True)

    manifest_fh = MANIFEST.open("a", encoding="utf-8")

    def record(rec, html=None):
        if html is not None:
            (RAW / rec["file"]).write_text(html, encoding="utf-8")
        manifest_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        manifest_fh.flush()
        done[rec["node_id"]] = rec
        visited.add(rec["node_id"])

    # Save/record the root, then enqueue its department rows.
    (RAW / "displayPa.html").write_text(root_html, encoding="utf-8")
    if ROOT_ID not in done:
        record(
            {
                "node_id": ROOT_ID, "parent_id": None, "depth": 0, "name": "TAMIL NADU (ROOT)",
                "address": "", "path": "", "file": "displayPa.html", "is_leaf": False,
                "http_status": 200, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )

    frontier = deque()

    def enqueue_children(page_html, page_url, parent_id, parent_path, depth):
        """Enqueue a page's clickable (sub-office) links for fetching.

        Leaf offices ("No Suboffices Currently Onboarded") are NOT recorded here --
        they have no page of their own and are derived by the parser from the saved
        HTML. Only recursable links become internal nodes.
        """
        for row in parse_rows(page_html, page_url):
            if row["is_leaf"] or row["token"] is None:
                continue
            nname = norm(row["name"])
            if not nname:
                continue
            # Cycle guard applies only to links (a fetch we'd recurse into): skip a
            # link whose office name already appears in its own ancestor path.
            if parent_path and nname in parent_path.split(PATH_SEP):
                continue
            path_key = (parent_path + PATH_SEP + nname) if parent_path else nname
            nid = node_id_for(path_key)
            if nid in visited:
                continue
            frontier.append(
                {
                    "nid": nid, "url": row["url"], "name": row["name"],
                    "address": row["address"], "parent_id": parent_id,
                    "path": path_key, "depth": depth,
                }
            )

    # Seed from the root, and re-expand every already-saved page so resume is
    # robust even though tokens (and thus saved pages) change between runs.
    enqueue_children(root_html, ENTRY, ROOT_ID, "", 1)
    for rec in list(done.values()):
        if rec.get("file") and rec["file"] != "displayPa.html" and (RAW / rec["file"]).exists():
            html = (RAW / rec["file"]).read_text(encoding="utf-8")
            enqueue_children(html, ENTRY, rec["node_id"], rec["path"], rec["depth"] + 1)

    fetched = 0
    while frontier:
        item = frontier.popleft()
        nid, depth = item["nid"], item["depth"]
        if nid in done and (RAW / f"{nid}.html").exists():
            html = (RAW / f"{nid}.html").read_text(encoding="utf-8")
        else:
            if limit and fetched >= limit:
                print(f"Reached --limit {limit}; stopping.", flush=True)
                break
            time.sleep(throttle + random.uniform(0, 0.5))
            status, html = fetch(session, item["url"], ENTRY,
                                 timeout=timeout, retries=retries, throttle=throttle)
            if html is None:
                print(f"  FAILED depth={depth} {item['name'][:40]!r} ({status})", flush=True)
                continue
            record(
                {
                    "node_id": nid, "parent_id": item["parent_id"], "depth": depth,
                    "name": item["name"], "address": item["address"], "path": item["path"],
                    "file": f"{nid}.html", "is_leaf": False,
                    "http_status": status if isinstance(status, int) else None,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                },
                html,
            )
            fetched += 1
            print(f"  saved d{depth} #{len(done)} {item['name'][:48]!r}", flush=True)

        if max_depth is None or depth < max_depth:
            enqueue_children(html, ENTRY, nid, item["path"], depth + 1)

    manifest_fh.close()
    print(f"\nDone. {len(done)} offices in manifest; {fetched} pages fetched this run.", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-depth", type=int, default=None,
                    help="Stop expanding past this depth (root=0). Default: full tree.")
    ap.add_argument("--limit", type=int, default=0,
                    help="Stop after fetching this many new pages (0 = no limit).")
    ap.add_argument("--timeout", type=float, default=40.0)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--throttle", type=float, default=1.2,
                    help="Base delay (s) between requests; jitter and backoff added.")
    args = ap.parse_args()
    crawl(max_depth=args.max_depth, limit=args.limit, timeout=args.timeout,
          retries=args.retries, throttle=args.throttle)


if __name__ == "__main__":
    main()
