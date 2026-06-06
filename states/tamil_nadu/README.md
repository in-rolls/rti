# Tamil Nadu RTI — public-authority universe scraper

Builds the full list of public authorities (departments → heads of department →
sub-offices, to every leaf office) registered on the Tamil Nadu RTI portal
<https://rtionline.tn.gov.in/>, so they can be categorized (e.g. by relevance to
reservation data) and used to file RTI applications.

The other states' lists were built by hand; TN is too large because it nests
authorities by level with a **separate link per node**. This automates that.

## Two hard facts about the site (why the code looks the way it does)

1. **Geo-fenced to Indian IPs.** Requests from outside India are silently
   dropped (verified: Mumbai/Delhi connect in <1s; US/EU time out). **You must run
   the crawler from an Indian egress** — e.g. with **ProtonVPN set to India**
   connected. The crawler does a preflight check and exits with a clear message if
   the site is unreachable. (The server is also flaky — intermittent HTTP 500s and
   resets — so the crawler throttles, retries, and is resumable.)
2. **Link tokens are randomized per request.** Each `show_sub_office.php` link
   carries an encrypted `min_code` that changes on every fetch, so the same office
   has a different token each time. Tokens therefore can't be used as identity —
   **an office is identified by its name and its path in the tree.**

## Architecture — scraping and parsing are separate

- **`scrape.py` (Stage 1, network).** Crawls the tree from `displayPa.php`,
  saving each authority page verbatim to `data/raw/<node_id>.html` and appending one
  record per office to `data/manifest.jsonl`. Leaf offices ("No Suboffices Currently
  Onboarded") have no page and are recorded straight to the manifest.
- **`parse.py` (Stage 2, offline).** Rebuilds the tree from the manifest,
  derives each office's level and full ancestor path, cross-checks the manifest
  against the saved HTML for completeness, and writes the CSVs below.
- **`categorize.py` (Stage 3, optional).** Flags offices likely relevant to
  reservation data by keyword, as a first-pass screen for manual review.
- **`common.py`.** Shared identity + HTML-parsing helpers used by all stages.

## Usage

Set up the environment once at the repo root, then run the scripts from this
directory (each script resolves its own `data/`, so `cd` here first):

```bash
# From the repo root:
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cd states/tamil_nadu

# 1. Connect ProtonVPN (India), then crawl (resumable; rerun to continue):
python scrape.py                 # full tree
python scrape.py --max-depth 1   # just the departments (quick check)
python scrape.py --limit 20      # stop after 20 new pages (dry run)

# 2. Parse the saved pages into CSVs (no network needed):
python parse.py

# 3. Optional: flag reservation-relevant offices:
python categorize.py
```

### Crawler options

| Flag | Default | Meaning |
|------|---------|---------|
| `--max-depth N` | full tree | stop expanding past depth N (root=0, dept=1, …) |
| `--limit N` | 0 (none) | stop after fetching N new pages |
| `--throttle S` | 1.2 | base delay (s) between requests; jitter + backoff added |
| `--timeout S` | 40 | per-request timeout |
| `--retries N` | 4 | retries with exponential backoff |

## Outputs (in `data/`)

- **`manifest.jsonl`** — crawl log: one record per office
  (`node_id, parent_id, depth, name, address, path, file, is_leaf, …`).
- **`raw/<node_id>.html`** — saved pages (the authoritative source for re-parsing).
- **`nodes.csv` / `universe.csv`** — one row per office: `node_id, level,
  level_label, name, address, is_leaf, has_children, parent_id, parent_name,
  department, path`. This is the RTI-target universe.
- **`edges.csv`** — `parent_id, parent_name, child_id, child_name`.
- **`universe_categorized.csv`** (Stage 3) — adds `reservation_relevant` +
  `matched_keywords`.

## Notes

- **Resumability:** rerun `scrape.py` to continue; offices already in the
  manifest are not refetched, and the crawl re-expands saved pages so it converges
  even though tokens change between runs.
- The crawl only enumerates public authorities (no captcha needed). The captcha and
  PIO lookup only appear at actual RTI submission — out of scope here.
