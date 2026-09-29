# RTI Telangana

Reproducible sampling, RA assignments, and a tracking dashboard for filing
RTI applications to Telangana public authorities. This is the Telangana
extension of the Tamil Nadu pipeline in
[in-rolls/rti](https://github.com/in-rolls/rti) (branch
`restructure-pipeline`), whose design it follows: scrape the portal's own
universe, freeze the frame, one seeded draw, randomized treatment
assignment, balanced RA worklists, and a static GitHub Pages viewer.

**Dashboard:** https://priyadarshiamar.github.io/rti-telangana/

## The universe

Like the Tamil Nadu pipeline, the frame comes from the portal itself. On
2026-09-02 we enumerated the public-authority list served by
[rti.telangana.gov.in](https://rti.telangana.gov.in) (its own search
endpoint, `GET /Homepage/Home/GetDepartments?term=&page=N`, 30 names per
page, 117 pages). The raw page responses are committed unmodified under
`data/raw/portal_scrape_2026-09-02/`; `scripts/build_frame.py` turns them
into `data/frame_telangana.csv` and writes `data/frame_provenance.json`.

- 3,500 raw registrations (matching the portal's own "3500 public
  authorities" counter), deduplicating to **3,401 distinct offices**.
- Completeness was cross-checked: an independent sweep of the same endpoint
  with a search term added zero names.
- Office names are kept **portal-verbatim** — including the portal's own
  typos (962 offices spell "Husbadry") — because RAs must match them
  against the portal dropdown. District and block are joined from the
  project's earlier `state_department` classification for the 3,317
  offices present in both; the 84 offices onboarded since have no district
  yet.

## The batch

Batch `tg2026q3_02`, seed `20260903`, draws **250** of the 3,401 offices.
The frame's SHA-256 is frozen in `out/tg2026q3_02/batch_meta.json`.

The Telangana list is flat — no department/tier tree like Tamil Nadu's —
so stratification is by **department group**, derived from the office name
(text before the first comma or parenthesis, normalised). Allocation across
strata is proportional to stratum size with a floor of 1 and a cap of 15,
so every substantial department is represented and none dominates. Groups
with fewer than 5 offices are pooled into a single OTHER stratum.

Within the draw:

- **Treatment:** 175 plain letters, 75 legal-salience (70/30), assigned by
  seeded shuffle. The legal-salience letter is byte-identical to the plain
  one except for the pre-specified Section 7(1)/20 paragraph.
- **RAs:** RA1–RA4, balanced within treatment arm (63/63/62/62 overall,
  legal split 19/19/19/18).

Re-running `python3 scripts/sample.py` reproduces the batch byte-for-byte.
A new wave means a new `batch_id` **and** a new seed.

## Supplementary batch tg2026q3_03 (2026-09-29)

Batch `tg2026q3_03`, seed `20260929`, adds **125** offices (87 plain /
38 legal-salience; IDs TG-251…TG-375), bringing Telangana to 375 of
3,401 (11%). Drawn by `scripts/sample_supplement.py` from the same
frozen frame, excluding wave-1 offices, with top-up allocation so the
375-office union matches proportional targets (union cap 23; the pooled
OTHER stratum is uncapped). Rationale and the pre-stated rule are in
[docs/design_notes/2026-09-29_supplementary_batches.md](docs/design_notes/2026-09-29_supplementary_batches.md).
The dashboard and worklists show both batches; `batch_id` distinguishes
them, and analyses should include a batch indicator.

An earlier batch `tg2026q3_01` (seed 20260902) was drawn from the older
classification file before the portal scrape existed. No application from
it was ever filed; it is superseded by `tg2026q3_02` and survives only in
git history.

## What RAs do

1. Open the dashboard, download your worklist (`out/tg2026q3_02/worklists/`).
2. File each row on [rti.telangana.gov.in](https://rti.telangana.gov.in),
   choosing the row's `office_name` in the portal's Public Authority
   dropdown (the portal is reachable only from India).
3. Paste the letter matching the row's `treatment` from
   `out/tg2026q3_02/templates/` (fill only the `[FILER ...]` placeholders;
   filer details are private and never committed here).
4. Record every attempt in the filing form — including offices that could
   not be filed to. The "could not file" rows preserve the denominator.

## Repository layout

```
config/batch.yaml         frozen batch design
data/raw/                 portal scrape pages + legacy district file, never modified
data/frame_telangana.csv  the 3,401-office frame (generated)
data/frame_provenance.json how the frame was built
scripts/build_frame.py    raw scrape -> frame
scripts/sample.py         the seeded draw (stdlib only, no dependencies)
out/tg2026q3_02/          assignments.csv, batch_meta.json, worklists/, templates/
docs/                     the GitHub Pages dashboard (copies of the above)
```

## Privacy

No filer names, addresses, emails, phone numbers, or evidence links are
committed. Letters contain placeholders. Filing records with personal
details live outside this repository.
