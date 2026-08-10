"""Turn a drawn batch into bilingual, paste-ready applications and an RA worklist.

This is where the pipeline stops. It does not submit anything: portals want a
login, a CAPTCHA, and an SMS OTP, and the act of filing produces study data (the
payment reference, the confirmation screenshot, the minutes it took) that only
the person filing can capture. What comes out is text to paste and a sheet to
work through.

Given the same batch and the same `--as-of`, the output is byte-identical.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

from .config import config_arg, load_batch, load_filer, load_state_rules, out_dir, state_rule
from .enums import LANGUAGE_NAMES, REVIEWED_LANGUAGES
from .letters import render_bilingual

DATE_FORMAT = "%d-%m-%Y"


def indian_fy(d: date) -> tuple[str, str]:
    """The last complete financial year and the current one, as ('2024-25', '2025-26')."""
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start - 1}-{str(start)[-2:]}", f"{start}-{str(start + 1)[-2:]}"


def reference_period(as_of: date, months: int) -> tuple[date, date]:
    """A whole-month window ending with the last complete month before `as_of`.

    Asking about complete months avoids a PIO refusing on the ground that the
    current month's register is still open.
    """
    end = as_of.replace(day=1) - timedelta(days=1)
    total = end.year * 12 + (end.month - 1) - (months - 1)
    return date(total // 12, total % 12 + 1, 1), end


def build_context(row: dict, as_of: date, cfg: dict, rules: dict, filer: dict) -> dict:
    rule = state_rule(row["state"], rules)
    start, end = reference_period(as_of, cfg["filing"]["reference_period_months"])
    fy1, fy2 = indian_fy(as_of)
    authority = ", ".join(
        part for part in (row["department"], row.get("district", ""), row["state"]) if part
    )
    return {
        "authority": authority,
        "period_start": start.strftime(DATE_FORMAT),
        "period_end": end.strftime(DATE_FORMAT),
        "attendance_date": end.strftime(DATE_FORMAT),
        "fy1": fy1,
        "fy2": fy2,
        "fee": rule.get("fee_inr", 10),
        "statutory_days": rule.get("statutory_days", 30),
        "filer_name": filer.get("name", "[FILER NAME]"),
        "filer_address": filer.get("address", "[FILER ADDRESS]"),
        "filer_phone": filer.get("phone", "[FILER PHONE]"),
        "filer_email": filer.get("email", "[FILER EMAIL]"),
        "filing_date": "[DATE OF FILING]",
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Render a batch into applications and a worklist.")
    config_arg(ap)
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD; default today")
    args = ap.parse_args(argv)

    cfg = load_batch(args.config)
    rules = load_state_rules()
    filer = load_filer()
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()

    outdir = out_dir(cfg["batch_id"])
    assignments_path = outdir / "assignments.csv"
    if not assignments_path.is_file():
        sys.exit(f"no assignments for batch {cfg['batch_id']}; run rti-sample first")
    with open(assignments_path, newline="", encoding="utf-8-sig") as f:
        assignments = list(csv.DictReader(f))

    appdir = outdir / "applications"
    appdir.mkdir(parents=True, exist_ok=True)
    for stale in appdir.glob("*.txt"):
        stale.unlink()

    unreviewed: dict[str, int] = {}
    worklist = []
    for row in assignments:
        context = build_context(row, as_of, cfg, rules, filer)
        text = render_bilingual(row["topic"], row["language"], context)
        path = appdir / f"{row['application_id']}.txt"
        path.write_text(text, encoding="utf-8")

        if row["language"] not in REVIEWED_LANGUAGES:
            unreviewed[row["language"]] = unreviewed.get(row["language"], 0) + 1

        worklist.append(
            {
                "application_id": row["application_id"],
                "state": row["state"],
                "department": row["department"],
                "portal": row["channel"],
                "topic": row["topic"],
                "language": row["language"],
                "needs_translation_review": (
                    "yes" if row["language"] not in REVIEWED_LANGUAGES else "no"
                ),
                "letter_file": str(Path("applications") / path.name),
                "fee_inr": context["fee"],
                "reply_due_days": context["statutory_days"],
            }
        )

    sheet = outdir / "filing_sheet.csv"
    with open(sheet, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(worklist[0].keys()))
        w.writeheader()
        w.writerows(worklist)

    print(f"rendered {len(worklist)} applications -> {appdir}")
    print(f"worklist -> {sheet}")
    if unreviewed:
        named = ", ".join(
            f"{LANGUAGE_NAMES.get(k, k)} ({v})" for k, v in sorted(unreviewed.items())
        )
        print(
            f"HOLD: {sum(unreviewed.values())} applications are in a language no native "
            f"speaker has signed off: {named}. They carry a banner and must not be filed "
            f"until reviewed.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
