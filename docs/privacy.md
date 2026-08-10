# What stays on this machine

Real data lives in two gitignored directories and never leaves them. Everything
committed is derived from it and safe to publish.

```
data/private/                    real. gitignored.
  tables/*.csv                     the true rows
  rti_filing_evidence_log.csv      the original hand-kept log
  intake_raw/                      Google Form exports
config/private/                  real. gitignored.
  filer.yaml                       the filer's name, address, phone, email
  pseudonyms.yaml                  real name -> RA-01, and the redact list
rti.db                           built from the real rows. gitignored.

data/tables/*.csv                redacted. committed.
config/filer.example.yaml        placeholders. committed.
```

## The boundary is one function

`tables.write_table()` writes the real rows to `data/private/tables/`, then
derives the published copy and writes that to `data/tables/`. Both, every time.

There is no anonymise-before-pushing step, because a step you have to remember
is a step you will eventually forget. `read_table()` reads the private copy when
it exists and the public one otherwise, so a fresh clone still runs the pipeline
and passes the checks.

## Replace the value, keep the fact

| Column | Published as |
|---|---|
| `filed_by`, `recorded_by`, `applicant` | `RA-01` |
| `sender_email` | `ra-01@redacted.invalid` |
| `evidence_url`, `screen_recording_url`, `document_url` | `[document recorded]` |
| `payment_reference` | `[redacted]` |
| `notes` | `[notes withheld]` |
| dates, enums, ids, registration numbers | unchanged |

An empty field stays empty. That distinction is the point: blanking
`evidence_url` would make the public data assert that no evidence was captured,
which is false, and worse than publishing nothing.

Pseudonyms come from `config/private/pseudonyms.yaml`, extended automatically
the first time a name appears. The same person is `RA-01` in every table, so
grouping by filer still works publicly. Labels are safe to rename by hand.

Free-text notes are withheld rather than scrubbed. A regex removes an email
address or a phone number; it does not remove "spoke to Ramesh at the counter",
and free text is rarely load-bearing for the analysis.

## Scraped records

`data/scrapers/*/universe_categorized.csv` is committed and holds office
addresses, including institutional emails and phone numbers. Those are published
deliberately: they come from a public government portal and postal filing needs
them.

Named individuals are removed, by literal match against the `redact` list in
`config/private/pseudonyms.yaml`. Add a name there and re-run `rti-categorize-tn`.

An honorific regex was tried for this first and abandoned. Across 17,417 Tamil
Nadu addresses it matched 34 times, of which one was a person. The rest were
institutions: `Dr. M.G.R. Educational and Research Institute`, `Sri Ramakrishna
Mission`, and `Thiru.Vi.Ka Industrial Estate`, which is a place in Chennai named
after a writer. Indian institutions are overwhelmingly named after people, so an
honorific marks a building far more often than an officer, and scrubbing on it
corrupts real postal addresses. It also missed the surname of the one real
person it found.

## The guard

```bash
rti-scrub --check     # or: make privacy
```

Reads every file `git ls-files` reports and fails on an email address, an Indian
phone number, a Drive or SharePoint link, or **any name in the pseudonym map**.
That last check is why the map matters beyond redaction: patterns find shapes,
and a name in a sentence has no shape.

Two false-positive traps it is built to avoid. `authority_id` is twelve hex
characters and roughly one in a hundred opens with ten digits that look exactly
like a mobile number, so a match must have a non-alphanumeric on both sides. And
a name is matched on word boundaries, so `vasanthi` does not fire inside
`vasanthipuram`, a town in Tirupur.

It runs in two places:

**A pre-push hook**, installed by `make hooks` and by `make install`. This is
the one that matters, because it fires before anything leaves the machine. A
push cannot be taken back: even a forced rewrite leaves the objects retrievable
from GitHub.

**CI**, on every branch. A backstop only. By the time it runs, the push has
already happened.

To push past the hook in a genuine emergency: `git push --no-verify`.

## Setting up a new machine

```bash
make install                                   # installs the hook
mkdir -p config/private data/private/tables
cp config/filer.example.yaml config/private/filer.yaml   # then fill it in
```

Copy `data/private/` and `config/private/pseudonyms.yaml` from the machine that
holds them, over a channel you would be willing to send the raw data over,
because that is what it is. Without the pseudonym map the published labels
cannot be resolved back to people, which is the intended property.
