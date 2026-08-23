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
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

from .config import config_arg, load_batch, out_dir, repo_root
from .enums import TOPICS
from .frame import FRAME_COLUMNS, sha256_file
from .ids import application_id, next_sequence, norm, state_code
from .tables import blank_row, read_table, write_table

TEMPLATE_VERSION = "v2"
INITIAL_BATCH_TEMPLATE_VERSION = "wave1-rti-information-v1"


def hash_frame_rows(rows: list[dict]) -> str:
    """Hash a canonical projection of frame rows, independent of CSV order."""
    projected = [{column: row.get(column, "") for column in FRAME_COLUMNS} for row in rows]
    payload = json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def stable_office_key(row: dict) -> tuple:
    """Stable order for all sampling and assignment operations."""
    try:
        level = int(norm(row.get("level", "")) or 999)
    except ValueError:
        level = 999
    return (
        norm(row.get("tree_department", "")),
        level,
        norm(row.get("department", "")),
        norm(row.get("node_id", "")),
        row["authority_id"],
    )


def eligible_initial_frame(cfg: dict, frame: list[dict]) -> list[dict]:
    """The crawled state universe eligible for the manuscript's first draw."""
    state = cfg["sampling"]["state"]
    rows = [row for row in frame if row["state"] == state and norm(row.get("node_id", ""))]
    if not rows:
        sys.exit(f"no crawled portal nodes for {state!r} in the frame")
    required = ("tree_department", "level", "level_label", "path")
    incomplete = [
        row["authority_id"] for row in rows if any(not norm(row.get(k, "")) for k in required)
    ]
    if incomplete:
        sys.exit(
            f"{len(incomplete)} eligible rows lack tree columns; rebuild the frame "
            "from the portal universe"
        )
    return sorted(rows, key=stable_office_key)


def _sample_up_to(rng: random.Random, rows: list[dict], n: int) -> list[dict]:
    rows = sorted(rows, key=stable_office_key)
    if len(rows) <= n:
        return rows
    return rng.sample(rows, n)


def _assign_research_assistants(
    rng: random.Random,
    rows: list[dict],
    treatment_by_authority: dict[str, str],
    research_assistants: list[str],
) -> dict[str, str]:
    """Shuffle within department x tier x treatment and assign round-robin.

    A separate pointer per treatment gives every RA the same treatment totals
    when each arm is divisible by the number of RAs. Within every operational
    stratum, RA counts differ by at most one.
    """
    if not research_assistants:
        raise ValueError("at least one research assistant is required")
    strata: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        treatment = treatment_by_authority[row["authority_id"]]
        strata[(row["tree_department"], row["level_label"], treatment)].append(row)

    assigned: dict[str, str] = {}
    pointers: Counter[str] = Counter()
    for stratum in sorted(strata):
        group = sorted(strata[stratum], key=stable_office_key)
        rng.shuffle(group)
        treatment = stratum[2]
        for row in group:
            pointer = pointers[treatment]
            assigned[row["authority_id"]] = research_assistants[pointer % len(research_assistants)]
            pointers[treatment] += 1
    return assigned


def _assign_treatment(rng: random.Random, rows: list[dict], legal_n: int) -> dict[str, str]:
    """Block the exact legal allocation by department x tier.

    Integer arm counts use Hamilton allocation: floor each stratum's share,
    then give the remaining slots to the largest fractional remainders. The
    offices receiving those slots are sampled within stratum.
    """
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        strata[(row["tree_department"], row["level_label"])].append(row)

    total = len(rows)
    legal_by_stratum = {stratum: len(group) * legal_n // total for stratum, group in strata.items()}
    remaining = legal_n - sum(legal_by_stratum.values())
    remainder_order = sorted(
        strata,
        key=lambda stratum: (-(len(strata[stratum]) * legal_n % total), stratum),
    )
    for stratum in remainder_order[:remaining]:
        legal_by_stratum[stratum] += 1

    treatment = {row["authority_id"]: "plain" for row in rows}
    for stratum in sorted(strata):
        group = sorted(strata[stratum], key=stable_office_key)
        for row in rng.sample(group, legal_by_stratum[stratum]):
            treatment[row["authority_id"]] = "legal_salience"
    return treatment


def _initial_batch_record(
    cfg: dict,
    row: dict,
    sequence: int,
    treatment: str,
    research_assistant: str,
) -> dict:
    record = blank_row("application")
    record.update(
        {
            "application_id": application_id(row["state_code"], sequence),
            "batch_id": cfg["batch_id"],
            "authority_id": row["authority_id"],
            "state": row["state"],
            "department": row["department"],
            "office_name": row["department"],
            "tree_department": row["tree_department"],
            "node_id": row["node_id"],
            "parent_id": row["parent_id"],
            "level": row["level"],
            "tier": row["level_label"],
            "path": row["path"],
            "portal": row["portal"],
            "topic": cfg["topics"]["fixed_topic"],
            "language": cfg["languages"]["by_state"].get(row["state"], cfg["languages"]["default"]),
            "channel": "portal",
            "template_version": INITIAL_BATCH_TEMPLATE_VERSION,
            "treatment": treatment,
            "assigned_ra": research_assistant,
            "randomization_stratum": f"{row['tree_department']} | {row['level_label']}",
        }
    )
    return record


def draw_initial_batch(
    cfg: dict, frame: list[dict], existing_ids: set[str] | None = None
) -> list[dict]:
    """Implement the manuscript's department-stratified initial-batch draw."""
    sampling = cfg["sampling"]
    rng = random.Random(cfg["seed"])
    eligible = eligible_initial_frame(cfg, frame)
    departments = sorted({row["tree_department"] for row in eligible})
    by_department: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        by_department[row["tree_department"]].append(row)

    selected: list[dict] = []
    hq_n = int(sampling["department_hq_per_department"])
    hod_n = int(sampling["head_of_department_per_department"])
    sub_n = int(sampling["sub_office_per_department"])
    for department in departments:
        rows = by_department[department]
        hq = [row for row in rows if row["level_label"] == "Department"]
        if len(hq) != hq_n:
            raise ValueError(
                f"{department!r} has {len(hq)} Department nodes; expected exactly {hq_n}"
            )
        selected.extend(sorted(hq, key=stable_office_key))
        selected.extend(
            _sample_up_to(
                rng,
                [row for row in rows if row["level_label"] == "Head of Department"],
                hod_n,
            )
        )
        selected.extend(
            _sample_up_to(
                rng,
                [row for row in rows if row["level_label"] == "Sub Office"],
                sub_n,
            )
        )

    target_n = int(sampling["n"])
    if len(selected) > target_n:
        raise ValueError(f"tier quotas select {len(selected)} offices, above target N={target_n}")
    selected_ids = {row["authority_id"] for row in selected}
    refill_pool = sorted(
        (
            row
            for row in eligible
            if row["level_label"] == "Sub Office" and row["authority_id"] not in selected_ids
        ),
        key=stable_office_key,
    )
    deficit = target_n - len(selected)
    if deficit > len(refill_pool):
        raise ValueError(f"cannot refill deficit of {deficit} from {len(refill_pool)} sub-offices")
    selected.extend(rng.sample(refill_pool, deficit))
    selected = sorted(selected, key=stable_office_key)

    treatment_cfg = cfg["treatments"]["legal_salience"]
    legal_n = int(treatment_cfg["n_legal"])
    plain_n = int(treatment_cfg["n_plain"])
    if legal_n + plain_n != len(selected):
        raise ValueError(
            f"treatment allocation is {plain_n} plain + {legal_n} legal, " f"but N={len(selected)}"
        )
    if legal_n > len(selected):
        raise ValueError(f"legal-salience allocation {legal_n} exceeds N={len(selected)}")
    treatment_by_authority = _assign_treatment(rng, selected, legal_n)
    ra_by_authority = _assign_research_assistants(
        rng, selected, treatment_by_authority, cfg["research_assistants"]
    )

    start = int(cfg["application_sequence_start"])
    sequences = range(start, start + len(selected))
    issued = existing_ids or set()
    records = []
    for row, sequence in zip(selected, sequences, strict=True):
        treatment = treatment_by_authority[row["authority_id"]]
        record = _initial_batch_record(
            cfg, row, sequence, treatment, ra_by_authority[row["authority_id"]]
        )
        if record["application_id"] in issued:
            raise ValueError(
                f"configured application sequence collides with existing id "
                f"{record['application_id']}"
            )
        records.append(record)
    return records


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
    if cfg["sampling"].get("strategy") == "department_tier_quotas":
        return draw_initial_batch(cfg, frame, existing_ids)

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

    The frame has 23,167 rows and most will never be written to. The authority
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
        row["office_name"] = src.get("department", "")
        row["tree_department"] = src.get("tree_department", "")
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
    for topic in cfg["topics"].get("weights", {}):
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
        w = csv.DictWriter(f, fieldnames=list(applications[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(applications)

    frozen = {k: v for k, v in cfg.items() if not k.startswith("_")}
    meta = {
        "batch_id": cfg["batch_id"],
        "seed": cfg["seed"],
        "frame_path": str(frame_path.relative_to(repo_root())),
        "frame_sha256": sha256_file(frame_path),
        "eligible_frame_n": (
            len(eligible_initial_frame(cfg, frame))
            if cfg["sampling"].get("strategy") == "department_tier_quotas"
            else len(frame)
        ),
        "eligible_frame_sha256": (
            hash_frame_rows(eligible_initial_frame(cfg, frame))
            if cfg["sampling"].get("strategy") == "department_tier_quotas"
            else hash_frame_rows(sorted(frame, key=lambda row: row["authority_id"]))
        ),
        "assignments_sha256": sha256_file(assignments),
        "template_version": applications[0]["template_version"],
        "n_applications": len(applications),
        "realized": {
            "by_tier": dict(sorted(Counter(row.get("tier", "") for row in applications).items())),
            "by_treatment": dict(
                sorted(Counter(row.get("treatment", "") for row in applications).items())
            ),
            "by_research_assistant": dict(
                sorted(Counter(row.get("assigned_ra", "") for row in applications).items())
            ),
            "by_research_assistant_and_treatment": {
                ra: dict(
                    sorted(
                        Counter(
                            row.get("treatment", "")
                            for row in applications
                            if row.get("assigned_ra", "") == ra
                        ).items()
                    )
                )
                for ra in sorted({row.get("assigned_ra", "") for row in applications})
            },
            "n_departments": len({row.get("tree_department", "") for row in applications}),
        },
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
    if cfg["sampling"].get("strategy") == "department_tier_quotas":
        print("by tier:", meta["realized"]["by_tier"])
        print("by treatment:", meta["realized"]["by_treatment"])
        print("by research assistant:", meta["realized"]["by_research_assistant"])
    if args.dry_run:
        print("dry run: data/tables/ not written")


if __name__ == "__main__":
    main()
