# RTI Delhi + Maharashtra

Reproducible sampling, RA assignments, and a tracking dashboard for filing
RTI applications to Delhi and Maharashtra public authorities — one
combined batch, sampled at 10% within each state. Sibling of
[rti-telangana](https://github.com/in-rolls/rti-telangana) and
[rti-karnataka](https://github.com/in-rolls/rti-karnataka), and
like them an extension of the Tamil Nadu pipeline in
[in-rolls/rti](https://github.com/in-rolls/rti).

**Dashboard:** https://in-rolls.github.io/rti-delhi-maharashtra/

## The universe

Delhi ([rtionline.delhi.gov.in](https://rtionline.delhi.gov.in)) and
Maharashtra ([rtionline.maharashtra.gov.in](https://rtionline.maharashtra.gov.in))
both run the central "RTI Online" software, whose public PIO-lookup page
(`pio_app_details.php`) carries the complete Public Authority dropdown
with no login, consent gate, or CAPTCHA. On 2026-09-07 we saved both
pages raw (committed unmodified under `data/raw/portal_scrape_2026-09-07/`);
`scripts/build_frame.py` parses the dropdowns into `data/frame_dl_mh.csv`
and writes `data/frame_provenance.json`.

- **Delhi: 223 public authorities** (the project's earlier
  `state_department` classification had 221).
- **Maharashtra: 328 public authorities** (the earlier file had 215 — the
  portal has grown by more than half since that capture).
- Office names are kept **portal-verbatim**; `portal_value_id` preserves
  each dropdown option's value for provenance. District/block join from
  the legacy file where matched (302 of 551).

## The batch

Batch `dm2026q3_01`, seed `20260908`: a **10% draw within each state** —
22 Delhi + 33 Maharashtra = 55 assignments. The frame's SHA-256 is frozen
in `out/dm2026q3_01/batch_meta.json`.

Stratification is by department group (leading segment of the office
name), proportional with a floor of 1 and cap of 15, small groups pooled
into OTHER — separately within each state. Within the draw:

- **Treatment (70/30 within each state):** Delhi 15 plain / 7
  legal-salience; Maharashtra 23 plain / 10 legal-salience. In each
  instrument pair the legal-salience letter is the plain one plus a single
  pre-specified Section 7(1)/20 paragraph, nothing else changed.
- **Instruments:** Delhi files the shared v3 letters. Maharashtra's portal
  caps the request text at **150 words**, so its rows carry
  `template_version: v4_mh150` — condensed letters (plain 123 words,
  legal-salience 149; ASCII punctuation only — the portal rejects semicolons and apostrophes, so clauses are comma-separated) that keep every load-bearing element (register
  extract with all recorded fields, period-totals fallback, s.25 return,
  no-new-compilation language, personal-details disclaimer, s.2(j)(iv)/7(9)
  electronic supply, s.6(3) transfer) and drop only the indicative
  category lists and the Format A/B/C labelling. Cross-state comparisons
  of the salience effect should note the instrument-version difference.
- **RAs:** RA1–RA4 at 14/14/14/13, the round-robin continuing across
  state × treatment cells so loads stay even.
- **IDs:** `DL-001…DL-022` and `MH-001…MH-033`.

Re-running `python3 scripts/sample.py` reproduces the batch byte-for-byte.
A new wave means a new `batch_id` **and** a new seed.

## Supplementary batch dm2026q3_02 (2026-09-29)

Batch `dm2026q3_02`, seed `20260930`, doubles each state's rate to
**20%**: +22 Delhi (DL-023…DL-044, 15 plain / 7 legal) and +33
Maharashtra (MH-034…MH-066, 23 plain / 10 legal, v4_mh150 letters).
Drawn by `scripts/sample_supplement.py` from the same frozen frame,
excluding wave-1 offices, with top-up allocation so each state's union
matches proportional targets (union cap 30; the pooled OTHER stratum is
uncapped). Rationale and the pre-stated rule:
[docs/design_notes/2026-09-29_supplementary_batches.md](docs/design_notes/2026-09-29_supplementary_batches.md).
The dashboard and worklists show both batches; analyses should include
a batch indicator.

## What RAs do

1. Open the dashboard, download your worklist
   (`out/dm2026q3_01/worklists/`).
2. File Delhi rows on rtionline.delhi.gov.in and Maharashtra rows on
   rtionline.maharashtra.gov.in (₹10 fee, CAPTCHA at submission; the
   portals are reachable only from India). Pick the row's `office_name`
   in the Public Authority dropdown.
3. Paste the letter matching the row's `treatment` from
   `out/dm2026q3_01/templates/` (fill only the `[FILER ...]`
   placeholders; filer details are private and never committed here).
4. Record every attempt — including offices that could not be filed to.
   The "could not file" rows preserve the denominator. Use RA codes, not
   real names, in `filed_by`.

## Repository layout

```
config/batch.yaml         frozen batch design
data/raw/                 both portals' dropdown pages + legacy district file
data/frame_dl_mh.csv      the combined 551-office frame (generated)
data/frame_provenance.json how the frame was built
scripts/build_frame.py    raw dropdown pages -> frame
scripts/sample.py         the seeded two-state draw (stdlib only)
out/dm2026q3_01/          assignments.csv, batch_meta.json, worklists/, templates/
docs/                     the GitHub Pages dashboard (copies of the above)
```

## Privacy

No filer names, addresses, emails, phone numbers, or evidence links are
committed. Letters contain placeholders. Filing records with personal
details live outside this repository.
