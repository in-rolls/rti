#!/usr/bin/env python3
"""Supplementary Telangana batch tg2026q3_03: +125 offices on top of the
250 in tg2026q3_02, drawn from the SAME frozen frame, excluding offices
already sampled.

Design note: docs/design_notes/2026-09-29_supplementary_batches.md.
The allocation is a TOP-UP: proportional allocation (floor 1, cap scaled
to the union size) is computed for the 375-office UNION, with each
stratum's floor set to what tg2026q3_02 already drew there; the new batch
takes only the difference, from unsampled offices. The union is therefore
what one 375-office proportional draw would have targeted.

Frozen batch tg2026q3_02 is untouched. Same seeded-reproducibility
discipline as scripts/sample.py.

Usage: python3 scripts/sample_supplement.py   (from the repository root)
"""

import csv
import hashlib
import json
import random
import re
from pathlib import Path

from sample import dept_group, largest_remainder  # same rules as wave 1

BATCH_ID = "tg2026q3_03"
PRIOR_BATCH = "tg2026q3_02"
SEED = 20260929          # new batch, new seed; never reuse a seed
N_NEW = 125
N_UNION = 375
N_LEGAL_NEW = 38         # 30% of 125, rounded up (union: 113/375 = 30.1%)
RAS = ["RA1", "RA2", "RA3", "RA4"]
CAP_UNION = 23           # wave-1 cap 15 scaled by 375/250
MIN_STRATUM_SIZE = 5
ID_START = 251
STATE = "Telangana"

ROOT = Path(__file__).resolve().parent.parent
FRAME = ROOT / "data" / "frame_telangana.csv"
OUT = ROOT / "out" / BATCH_ID


def main():
    rows = list(csv.DictReader(open(FRAME, encoding="utf-8")))
    frame_sha = hashlib.sha256(FRAME.read_bytes()).hexdigest()
    prior = list(csv.DictReader(open(ROOT / "out" / PRIOR_BATCH / "assignments.csv",
                                     encoding="utf-8")))
    prior_meta = json.load(open(ROOT / "out" / PRIOR_BATCH / "batch_meta.json"))
    if prior_meta["frame_sha256"] != frame_sha:
        raise SystemExit("frame changed since the prior batch; refuse to draw")
    taken = {p["office_name"] for p in prior}

    for r in rows:
        r["dept_group"] = dept_group(r["Department"])
    rows.sort(key=lambda r: (r["dept_group"], r["Department"], r["District"]))

    strata = {}
    for r in rows:
        strata.setdefault(r["dept_group"], []).append(r)
    pooled = {}
    for g, members in strata.items():
        key = g if len(members) >= MIN_STRATUM_SIZE else "OTHER (POOLED SMALL OFFICES)"
        pooled.setdefault(key, []).extend(members)
    strata = pooled

    group_of = {}
    for g, members in strata.items():
        for m in members:
            group_of[m["Department"]] = g
    existing = {g: 0 for g in strata}
    for p in prior:
        existing[group_of[p["office_name"]]] += 1

    weights = {g: len(m) for g, m in strata.items()}
    # the cap stops any single department dominating; the pooled OTHER
    # stratum is not a department, so it is uncapped
    caps = {g: len(m) if g.startswith("OTHER") else min(CAP_UNION, len(m))
            for g, m in strata.items()}
    floors = dict(existing)  # the union keeps everything wave 1 drew
    alloc_union = largest_remainder(weights, N_UNION, caps, floors)
    need = {g: alloc_union[g] - existing[g] for g in strata}
    assert sum(need.values()) == N_NEW and all(v >= 0 for v in need.values())

    rng = random.Random(SEED)
    sampled = []
    for g in sorted(strata):
        avail = [m for m in strata[g] if m["Department"] not in taken]
        if need[g] > len(avail):
            raise SystemExit(f"stratum {g}: need {need[g]} but only {len(avail)} unsampled")
        sampled.extend(rng.sample(avail, need[g]))

    sampled.sort(key=lambda r: (r["dept_group"], r["Department"], r["District"]))
    rng.shuffle(sampled)
    for i, r in enumerate(sampled):
        r["treatment"] = "legal_salience" if i < N_LEGAL_NEW else "plain"
    offset = 0
    for arm in ("legal_salience", "plain"):
        arm_rows = [r for r in sampled if r["treatment"] == arm]
        rng.shuffle(arm_rows)
        for i, r in enumerate(arm_rows):
            r["assigned_ra"] = RAS[(offset + i) % len(RAS)]
        offset = (offset + len(arm_rows)) % len(RAS)

    sampled.sort(key=lambda r: (r["dept_group"], r["Department"], r["District"]))
    for i, r in enumerate(sampled, start=ID_START):
        r["application_id"] = f"TG-{i:03d}"

    fields = list(prior[0].keys())

    def to_row(r):
        base = {k: "" for k in fields}
        base.update({
            "application_id": r["application_id"], "batch_id": BATCH_ID,
            "state": STATE, "office_name": r["Department"],
            "dept_group": r["dept_group"], "district": r["District"],
            "block": r["Block"], "portal": r["Website"],
            "treatment": r["treatment"], "assigned_ra": r["assigned_ra"],
            "template_version": "v3", "language": "en", "channel": "portal",
        })
        return base

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "worklists").mkdir(exist_ok=True)
    with open(OUT / "assignments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sampled:
            w.writerow(to_row(r))
    for ra in RAS:
        with open(OUT / "worklists" / f"{ra}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in sampled:
                if r["assigned_ra"] == ra:
                    w.writerow(to_row(r))

    meta = {
        "batch_id": BATCH_ID, "seed": SEED, "state": STATE,
        "n_new": N_NEW, "n_union": N_UNION, "n_legal_new": N_LEGAL_NEW,
        "prior_batch": PRIOR_BATCH, "cap_union": CAP_UNION,
        "min_stratum_size": MIN_STRATUM_SIZE, "ras": RAS,
        "frame_csv": str(FRAME.relative_to(ROOT)), "frame_sha256": frame_sha,
        "design_note": "docs/design_notes/2026-09-29_supplementary_batches.md",
        "rationale": "oversample states with smaller online-filable universes "
                     "for credible within-state estimates; KA/TN portals "
                     "unreliable, RA capacity reallocated",
        "templates": prior_meta["templates"],
    }
    with open(OUT / "batch_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    from collections import Counter
    print(f"{len(sampled)} new | treatment {dict(Counter(r['treatment'] for r in sampled))} | "
          f"RA {dict(sorted(Counter(r['assigned_ra'] for r in sampled).items()))}")


if __name__ == "__main__":
    main()
