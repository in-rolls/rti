# RTI audit pipeline

Sample public authorities from a 23,167-office frame, generate a courteous RTI
application for each in English and the local language, file it, and track what
comes back — reproducibly, and in a form a research assistant can keep current
from a phone.

```
scrape ──► frame ──► sample ──► render ──► file ──► monitor
portal     23,167    seeded     assigned    RA on   two Google
by state   offices   draw       letters     portal  Forms
                        │                              │
                        └──────────► 3 tables ◄─────────┘
                                  real on disk,
                                redacted in git
                                       │
                                    rti.db
```

## Quick start

```bash
make install          # .venv with the package and dev tools
make frame            # data/raw/*.csv  -> data/frame.csv (+ provenance)
make sample           # frame -> out/<batch>/assignments.csv, opens application rows
make render           # -> out/<batch>/applications/*.txt and filing_sheet.csv
make forms            # the Google Form spec to build, generated from the enums
make load             # merge form exports from data/private/intake_raw/
make check            # validate the tables
make privacy          # fail if git is tracking anything personal
make db               # rebuild schema.sql and rti.db
```

Every step is a console script too (`rti-sample`, `rti-render`, …). `--help` on
any of them.

## Batch viewer

The reproducible initial batch has a filterable GitHub Pages viewer at
[`https://in-rolls.github.io/rti/`](https://in-rolls.github.io/rti/) once the
`main` branch is published. It includes the 1,000-row assignment table,
per-RA worklists, downloadable CSVs, and links to each generated letter. The
site is assembled by [`.github/workflows/pages.yml`](.github/workflows/pages.yml)
from the committed `out/b2026q3_02/` artifacts.

## What the letters ask for

The primary request is the authority's **own RTI register** for the last twelve
months: applications received by month, how many were disposed of inside the
statutory deadline, the subject categories as recorded, and the split between
individual and institutional applicants. Two fallback topics exist for batches
that vary the request: sanctioned strength against attendance on a fixed date,
and budget allocated against expenditure over two financial years.

Each asks only for something the authority is already obliged to hold as a
record, phrased "as recorded", so refusing it as a demand to create or collate
new information under s.2(f) or s.2(j) does not work. None names an individual,
which keeps the amended s.8(1)(j) out of play.

Wave 1 uses the single English instrument frozen in `ms/ms.tex`. Its legal-
salience treatment inserts only the pre-specified Section 7(1)/20 paragraph;
the remaining text is byte-for-byte identical to the plain arm. The older
robustness-wave templates support English, Hindi, Tamil, Telugu, Kannada, and Marathi. Each
application renders as one file: the local-language letter first, because that
is what gets pasted into the portal, with an English copy below it so anyone
reviewing the batch can read what was sent.

Only English and Hindi have been checked by a native speaker. The other four
render with a banner telling the RA not to file until someone reviews them. To
sign a language off, add it to `REVIEWED_LANGUAGES` in `src/rti/enums.py`.

Letter text lives in `src/rti/letters/`: shared blocks once per language in
`blocks.py`, the numbered asks per topic in `bodies.py`, assembly in
`compose.py`. The fee and the statutory deadline come from
`config/state_rules.yaml`, never from the prose, so a state on a different clock
gets a letter that says so.

## The three tables

The tables are plain CSV, so a curator fixes a cell in a spreadsheet without
touching SQL, and `rti-check` runs in CI, so a bad edit fails a pull request
instead of quietly entering the analysis.

| Table | One row per | Written by |
|---|---|---|
| `authority` | office that could be written to | `rti-sample`, from the frame |
| `application` | **planned** letter | `rti-sample`; filled in by `rti-load` |
| `event` | thing that happened afterwards | `rti-load`, append-only |

Four layers, and only the third is edited by hand:

```
data/private/intake_raw/    what the Forms recorded.  Immutable, gitignored.
data/private/tables/*.csv   the real rows.            Gitignored.
data/tables/*.csv           the redacted copy.        Committed, hand-editable.
rti.db                      derived from the real.    Rebuilt on demand.
```

`write_table()` writes the real rows and derives the published copy in one call,
so there is no anonymise-before-pushing step to forget, and a pre-push hook
refuses to push if git is tracking a name, an email, a phone number, or an
evidence link. See [`docs/privacy.md`](docs/privacy.md).

### Why an application row exists before anything is filed

`rti-sample` writes an `application` row for every office it draws, weeks before
anyone opens a portal. When an office turns out to be missing from its portal's
dropdown, the row is already there to record it, and `filing_outcome` becomes
`not_filed` with a reason.

A log that only gains a row on success cannot represent that. You would finish
the study knowing 138 were filed out of 150 sampled, able to work out *which*
twelve are missing but never *why* — the reason existed only in the RA's head on
the afternoon it happened. Response rate then quietly becomes 47/138 when the
number a citizen actually experiences is 47/150.

`SELECT * FROM v_attrition` gives sampled, filed, not filed, and not yet
reported, per state.

### Why events are rows

An application collects an acknowledgement, a s.6(3) transfer, a fee demand, a
reply, an appeal, and an order, in any order and any number. Columns cannot hold
that: a second transfer or a remanded appeal has nowhere to go. Days to
response, current status, and transfer count are computed in `v_status`, so
nothing is stored that could go stale.

## How research assistants use it

Two Google Forms, roughly six fields each. `rti-forms` prints both, with the
option lists and the application-id dropdown generated from the same enums the
schema and the validator use, so they cannot drift apart.

**Form 1, "File an application"** — one submission per application, *whether or
not it was filed*. The "could not file" branch is what preserves the
denominator.

**Form 2, "Update an application"** — one submission per thing that happens.
Submit it again for the next thing; never edit an old submission, because the
sequence is the data.

Nobody types an identifier: `application_id` is short and readable (`KA-014`,
matching the convention already in the evidence log) and is always picked from a
list. Nobody types the filer's name or address either; those come from
`config/private/filers.yaml`. Due dates are computed, never entered.

`docs/ra_handbook.md` is the page to hand an RA.

## Reproducibility

- One `random.Random(seed)` drives every draw, and rows are sorted by a stable
  key first, so neither CSV row order nor dict iteration order can leak in.
- `out/<batch>/batch_meta.json` freezes the seed, the full config, and the
  SHA-256 of the frame. `assignments.csv` and `batch_meta.json` are committed.
- Re-running `rti-sample` on a batch reproduces it rather than renumbering it,
  and never overwrites anything an RA has recorded.
- `rti-load` is keyed on a per-submission id, so loading the same export twice
  changes nothing and a hand correction survives the next load.
- A new wave means a new `batch_id` **and** a new seed. Never reuse a seed.

`make test` covers all of the above.

## Building the frame

`rti-build-frame` turns the raw sources into `data/frame.csv` and writes every
change it made to `data/frame_provenance.json`. Raw files are never modified.
The current run corrects 1,699 rows misspelling Karnataka as `Kanataka`, repairs
damaged text, and normalises six portal identifiers. It preserves all 23,167
source rows. Tamil Nadu is keyed by its 17,417 portal `node_id` values; the 27
collisions in the flat fields (16 Tamil Nadu and 11 Telangana) are no longer
collapsed.

Scrapers are stage zero of this same pipeline: a state's portal becomes a
universe of offices, which becomes part of the frame. Tamil Nadu's 17,417-row
tree comes from `src/rti/scrapers/tamil_nadu/`; the other five states remain
flat portal-derived lists until their crawls are added. See
[`docs/frame.md`](docs/frame.md) for the frame dictionary and join contract.

The frozen initial draw is batch `b2026q3_02` with seed `20260817`. It uses only
the crawled Tamil Nadu universe, takes every department node, samples up to four
Head-of-Department and twenty sub-office nodes per department, refills quota
shortfalls from pooled unsampled sub-offices, assigns exactly 700 plain and 300
legal-salience letters within department-by-tier blocks, and gives RA1--RA4
exactly 250 applications each (175 plain and 75 legal-salience).

`topics.strategy: by_category` does not currently work. `Category` is empty on
88.6% of the frame and the values it does carry are administrative types
("Urban body: Town Panchayat"), not the subject areas the config maps. The
default is `fixed`.

## Adding a state scraper

Copy `src/rti/scrapers/tamil_nadu/` to `src/rti/scrapers/<state>/`. The
per-state logic sits in a few constants:

- `common.py` — `BASE` / `ENTRY` / `INDEX` URLs, page-title prefixes, the
  leaf-detection regex, and the row selectors in `parse_rows`.
- `scrape.py` — the root office name and any geo-fencing or preflight checks.
- `parse.py` — `LEVEL_LABELS` for that state's hierarchy.
- `categorize.py` — the `KEYWORDS` screen.

Then add an entry point in `pyproject.toml` and merge the result with
`rti.frame.load_scraper_universe`. See
[`src/rti/scrapers/tamil_nadu/README.md`](src/rti/scrapers/tamil_nadu/README.md)
for a worked example, including two portal quirks worth reading before writing a
crawler for any Indian state site.

## What this does not do

It does not submit applications. Portals want a login, a CAPTCHA, and an SMS
OTP, and the act of filing produces study data — the payment reference, the
confirmation screenshot, the minutes it took — that only the person filing can
capture. The pipeline ends at text to paste and a sheet to work through.

## Repository layout

```
config/          batch.yaml, state_rules.yaml, filer.example.yaml
  private/       filers.yaml, pseudonyms.yaml         GITIGNORED
data/
  raw/           sources, never modified
  frame.csv      generated, with frame_provenance.json
  tables/        the three tables, redacted. Committed.
  private/       the real tables, the evidence log,
                 and the Form exports                 GITIGNORED
  scrapers/      per-state universes
docs/            data_schema.md, privacy.md, ra_handbook.md, forms.md
hooks/           the pre-push guard, installed by `make hooks`
letters/archive/ hand-written reservation-roster letters (a different study)
out/<batch>/     assignments, letters, worklist
src/rti/         the package
schema.sql       generated from src/rti/enums.py
```

`letters/archive/` holds an earlier corpus asking for historical seat and ward
reservation rosters. It is a different research question, kept for reference and
not generated by this pipeline.
