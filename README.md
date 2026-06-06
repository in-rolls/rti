# RTI public-authority universe scrapers

Scrapers that build the **universe of public authorities** registered on Indian
state RTI (Right to Information) portals — every department, head of department,
and sub-office down to each leaf — so the offices can be screened (e.g. for
relevance to reservation data) and used to file RTI applications.

Most states' lists can be assembled by hand. Some portals (e.g. Tamil Nadu) nest
authorities by level with a separate link per node and run into the thousands, so
they need automation. This repo collects one self-contained scraper per state.

## Layout

```
rti/
├── README.md            # this file
├── requirements.txt     # shared dependencies for all states
└── states/
    └── tamil_nadu/      # one self-contained scraper per state
        ├── README.md    # state-specific docs (site quirks, usage)
        ├── scrape.py    # Stage 1: crawl the portal, save raw HTML + manifest
        ├── parse.py     # Stage 2: rebuild the tree offline, write CSVs
        ├── categorize.py# Stage 3: keyword-screen offices for relevance
        ├── common.py    # shared identity + HTML-parsing helpers
        └── data/        # outputs (mostly gitignored — see below)
```

Each state directory follows the same three-stage shape: **scrape → parse →
categorize**. See [`states/tamil_nadu/README.md`](states/tamil_nadu/README.md)
for the worked example.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Then `cd` into a state directory and follow its README.

## Adding a new state

Copy `states/tamil_nadu/` to `states/<state>/` and adapt the portal-specific
knobs — the per-state logic is concentrated in a few constants:

- **`common.py`** — `BASE` / `ENTRY` / `INDEX` URLs, the page-title prefixes
  (`_TITLE_PREFIXES`), the leaf-detection regex (`_LEAF_RE`), and the row/HTML
  selectors in `parse_rows`.
- **`scrape.py`** — the root office name (e.g. `"TAMIL NADU (ROOT)"`) and any
  geo-fencing / preflight checks specific to the portal.
- **`parse.py`** — `LEVEL_LABELS` for the state's organizational hierarchy.
- **`categorize.py`** — the `KEYWORDS` list for that state's social categories.

## Data in git

Only the final deliverable, `data/universe_categorized.csv`, is committed. The
large regenerable artifacts (raw HTML, `manifest.jsonl`, intermediate CSVs, logs)
are gitignored — re-run the scrapers to reproduce them.
