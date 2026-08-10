"""Draw a batch from the frame, and open an application row for every office drawn.

The row is written now, before anyone tries to file, and that is the point. An
office that turns out to be missing from its portal in three weeks already has a
row waiting to record the failure. A filing log that only gains rows on success
cannot represent the same fact, and the reason is unrecoverable by the time
anyone notices.

Reproducibility: all randomness comes from one `random.Random(seed)`, and rows
are sorted by a stable key before every draw, so neither CSV row order nor dict
iteration order can leak into the sample.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone

from .config import config_arg, load_batch, out_dir, repo_root
from .enums import TOPICS
from .frame import FRAME_COLUMNS, sha256_file
from .ids import application_id, next_sequence, norm, state_code
from .tables import blank_row, read_table, write_table

TEMPLATE_VERSION = "v2"


def load_frame(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"frame is empty: {path}")
    missing = set(FRAME_COLUMNS) - set(rows[0])
    if missing:
        sys.exit(f"frame is missing columns {sorted(missing)}; rebuild it with rti-build-frame")
    for r in rows:
        r["relevant"] = int(norm(r["relevant"]) or 0)
    return rows


def dedupe_one_per_department(rows: list[dict]) -> list[dict]:
    """One candidate per (state, department), preferring a relevant office.

    Sorting before the scan is what makes the choice reproducible rather than
    dependent on the order the frame happened to be written in.
    """
    rows = sorted(
        rows,
        key=lambda r: (
            r["state"],
            r["department"],
            -r["relevant"],
            r["district"],
            r["block"],
        ),
    )
    seen: set[tuple[str, str]] = set()
    out = []
    for r in rows:
        key = (r["state"].lower(), r["department"].lower())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def pick_topic(rng: random.Random, cfg: dict, row: dict) -> str:
    t = cfg["topics"]
    strategy = t.get("strategy", "fixed")
    if strategy == "fixed":
        return t["fixed_topic"]
    if strategy == "by_category":
        return t.get("category_map", {}).get(row["category"], t["fixed_topic"])
    names = sorted(t["weights"])
    return rng.choices(names, weights=[t["weights"][n] for n in names], k=1)[0]


def pick_language(cfg: dict, state: str, warned: set[str]) -> str:
    languages = cfg["languages"]
    lang = languages.get("by_state", {}).get(state)
    if lang is None:
        if state not in warned:
            warned.add(state)
            print(
                f"WARNING: no language configured for '{state}'; using "
                f"'{languages['default']}'",
                file=sys.stderr,
            )
        return languages["default"]
    return lang


def draw(
    cfg: dict,
    frame: list[dict],
    existing_ids: set[str] | None = None,
    already_in_batch: dict[str, str] | None = None,
) -> list[dict]:
    """The sample itself. Pure: same inputs, same output, every time.

    `existing_ids` are identifiers already issued by earlier batches, so a new
    batch continues the sequence instead of colliding. `already_in_batch` maps an
    office to the identifier THIS batch previously gave it, so re-running the
    sampler for a batch reproduces it rather than renumbering it.
    """
    existing_ids = existing_ids or set()
    already_in_batch = already_in_batch or {}
    rng = random.Random(cfg["seed"])
    rows = frame
    if cfg["sampling"]["one_per_department"]:
        rows = dedupe_one_per_department(rows)
    if cfg["sampling"]["relevant_only"]:
        kept = [r for r in rows if r["relevant"] == 1]
        if kept:
            rows = kept
        else:
            print(
                "WARNING: relevant_only is set but no office is marked relevant; "
                "drawing from the full frame",
                file=sys.stderr,
            )

    warned: set[str] = set()
    issued = set(existing_ids)
    out: list[dict] = []

    for state in sorted({r["state"] for r in rows}):
        pool = sorted(
            (r for r in rows if r["state"] == state),
            key=lambda r: (r["department"], r["district"], r["block"]),
        )
        n = min(cfg["sampling"]["n_per_state"], len(pool))
        picked = sorted(rng.sample(pool, n), key=lambda r: r["department"])
        code = state_code(state)
        language = pick_language(cfg, state, warned)
        for row in picked:
            app_id = already_in_batch.get(row["authority_id"])
            if app_id is None:
                app_id = application_id(code, next_sequence(issued, code))
            issued.add(app_id)
            record = blank_row("application")
            record.update(
                {
                    "application_id": app_id,
                    "batch_id": cfg["batch_id"],
                    "authority_id": row["authority_id"],
                    "state": state,
                    "department": row["department"],
                    "topic": pick_topic(rng, cfg, row),
                    "language": language,
                    "channel": "portal" if row["portal"] else "post",
                    "template_version": TEMPLATE_VERSION,
                }
            )
            out.append(record)
    return out


def authority_rows(applications: list[dict], frame: list[dict], batch_id: str) -> list[dict]:
    """The offices this batch touched, copied out of the frame.

    The frame has 23,140 rows and most will never be written to. The authority
    table holds only what a batch actually drew, so it stays small enough to read.
    """
    by_id = {r["authority_id"]: r for r in frame}
    rows = []
    for app in applications:
        src = by_id.get(app["authority_id"])
        if src is None:
            continue
        row = blank_row("authority")
        row.update({k: src.get(k, "") for k in row if k in src})
        row["first_sampled_batch"] = batch_id
        rows.append(row)
    return rows


def merge_by_key(existing: list[dict], new: list[dict], key: str) -> list[dict]:
    """Add rows that are not there yet; never overwrite one that is.

    Re-running the sampler for an existing batch is a no-op rather than a way to
    silently discard what an RA already recorded against those applications.
    """
    index = {r[key]: r for r in existing}
    for row in new:
        index.setdefault(row[key], row)
    return list(index.values())


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Draw a batch and open its application rows.")
    config_arg(ap)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="write out/<batch>/ but leave data/tables/ untouched",
    )
    args = ap.parse_args(argv)

    cfg = load_batch(args.config)
    for topic in cfg["topics"]["weights"]:
        if topic not in TOPICS:
            sys.exit(f"unknown topic {topic!r} in config; expected one of {list(TOPICS)}")

    frame_path = repo_root() / cfg["frame_csv"]
    frame = load_frame(frame_path)

    existing_apps = read_table("application")
    already = {r["application_id"] for r in existing_apps}
    in_batch = {
        r["authority_id"]: r["application_id"]
        for r in existing_apps
        if r["batch_id"] == cfg["batch_id"]
    }
    if in_batch:
        print(
            f"NOTE: batch {cfg['batch_id']} was already drawn; reproducing it. "
            f"Existing rows and their identifiers are kept.",
            file=sys.stderr,
        )

    applications = draw(cfg, frame, already, in_batch)
    if not applications:
        sys.exit("no offices drawn; check sampling.relevant_only and the frame")

    outdir = out_dir(cfg["batch_id"])
    outdir.mkdir(parents=True, exist_ok=True)
    assignments = outdir / "assignments.csv"
    with open(assignments, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(applications[0].keys()))
        w.writeheader()
        w.writerows(applications)

    frozen = {k: v for k, v in cfg.items() if not k.startswith("_")}
    meta = {
        "batch_id": cfg["batch_id"],
        "seed": cfg["seed"],
        "frame_path": str(frame_path.relative_to(repo_root())),
        "frame_sha256": sha256_file(frame_path),
        "template_version": TEMPLATE_VERSION,
        "n_applications": len(applications),
        "config": frozen,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(outdir / "batch_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if not args.dry_run:
        write_table("application", merge_by_key(existing_apps, applications, "application_id"))
        write_table(
            "authority",
            merge_by_key(
                read_table("authority"),
                authority_rows(applications, frame, cfg["batch_id"]),
                "authority_id",
            ),
        )

    print(f"drew {len(applications)} applications -> {assignments}")
    by_state: dict[str, int] = {}
    by_topic: dict[str, int] = {}
    for r in applications:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
        by_topic[r["topic"]] = by_topic.get(r["topic"], 0) + 1
    print("by state:", dict(sorted(by_state.items())))
    print("by topic:", dict(sorted(by_topic.items())))
    if args.dry_run:
        print("dry run: data/tables/ not written")


if __name__ == "__main__":
    main()
