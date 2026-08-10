"""Print the two Google Forms, ready to build, generated from the enums.

Building the forms by hand invites the one failure this design cannot survive:
an option list in a form drifting away from the values the schema accepts. So
the option lists are generated. Run this, follow what it prints, and the forms
match the tables by construction.

It also emits the application-id list for the batch, which is what turns the
riskiest field on either form into a dropdown nobody can mistype.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_batch, out_dir
from .enums import (
    EVENT_TYPE_LABELS,
    EVENT_TYPES,
    MEDIUM_LABELS,
    MEDIUMS,
    NOT_FILED_REASON_LABELS,
    NOT_FILED_REASONS,
    PAYMENT_MODE_LABELS,
    PAYMENT_MODES,
)
from .tables import read_table


def _options(values: tuple[str, ...], labels: dict[str, str]) -> str:
    return "\n".join(f"      - {labels.get(v, v)}" for v in values)


def filing_form(app_ids: list[str]) -> str:
    shown = app_ids[:5]
    more = (
        f"      ... and {len(app_ids) - len(shown)} more (full list below)"
        if len(app_ids) > 5
        else ""
    )
    return f"""\
FORM 1 - "File an application"
{'=' * 74}
One submission per application, whether or not it was filed. Submitting a
failure is not an admission of anything; it is the study's attrition record and
it cannot be reconstructed later.

Settings: collect email addresses, allow file upload, one response per
submission (do NOT limit to one response per person), edit-after-submit OFF.

  1. Application ID                                   [Dropdown, required]
{chr(10).join(f'      - {a}' for a in shown)}
{more}

  2. Were you able to file it?                        [Multiple choice, required]
      - Filed
      - Could not file

  3. Reason it could not be filed        [Multiple choice, show if Q2 = Could not file]
{_options(NOT_FILED_REASONS, NOT_FILED_REASON_LABELS)}

  4. Date filed                                       [Date, show if Q2 = Filed]
  5. Registration number                              [Short answer, show if Q2 = Filed]
  6. Fee paid (Rs.)                                   [Short answer, show if Q2 = Filed]
  7. Payment mode                                     [Multiple choice, show if Q2 = Filed]
{_options(PAYMENT_MODES, PAYMENT_MODE_LABELS)}

  8. Payment reference                                [Short answer, show if Q2 = Filed]
  9. Evidence                                         [File upload, show if Q2 = Filed]
       Confirmation screen and payment receipt.
 10. Screen recording                                 [File upload, optional]
 11. Notes                                            [Paragraph, optional]
"""


def update_form(app_ids: list[str]) -> str:
    shown = app_ids[:5]
    more = (
        f"      ... and {len(app_ids) - len(shown)} more (full list below)"
        if len(app_ids) > 5
        else ""
    )
    return f"""\
FORM 2 - "Update an application"
{'=' * 74}
One submission per thing that happens. Submit it again for the next thing.
Never edit an old submission: the sequence is the data.

  1. Application ID                                   [Dropdown, required]
{chr(10).join(f'      - {a}' for a in shown)}
{more}

  2. What happened?                                   [Dropdown, required]
{_options(EVENT_TYPES, EVENT_TYPE_LABELS)}

  3. Date on the document                             [Date, required]
       The date printed on the letter or email, not the date you saw it.

  4. How did it arrive?                               [Multiple choice, required]
{_options(MEDIUMS, MEDIUM_LABELS)}

  5. Which office was it transferred to?  [Short answer, show if Q2 = Transferred]
  6. Upload the document                              [File upload]
  7. Notes                                            [Paragraph, optional]
"""


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Print the Google Form specification for a batch.")
    ap.add_argument("--config", default=None)
    ap.add_argument(
        "--ids-only",
        action="store_true",
        help="print just the application IDs, for pasting into a dropdown",
    )
    ap.add_argument("--out", type=Path, default=None, help="write to a file instead of stdout")
    args = ap.parse_args(argv)

    cfg = load_batch(args.config)
    batch = cfg["batch_id"]
    rows = [r for r in read_table("application") if r.get("batch_id") == batch]
    if not rows:
        sys.exit(f"no applications for batch {batch}; run rti-sample first")
    app_ids = sorted(r["application_id"] for r in rows)

    if args.ids_only:
        print("\n".join(app_ids))
        return

    labelled = [
        f'{r["application_id"]}  {r["state"]} - {r["department"]}'
        for r in sorted(rows, key=lambda r: r["application_id"])
    ]
    text = "\n".join(
        [
            f"Google Forms for batch {batch} ({len(app_ids)} applications)",
            f"Letters and worklist: {out_dir(batch)}",
            "",
            filing_form(app_ids),
            "",
            update_form(app_ids),
            "",
            "APPLICATION ID DROPDOWN - paste into Q1 of both forms",
            "=" * 74,
            *labelled,
            "",
        ]
    )
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"form specification -> {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
