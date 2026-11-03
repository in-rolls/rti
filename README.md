# Right to Information fieldwork

This repository contains the fieldwork pipeline for an audit of India's Right to Information system: office frames, issued assignments, letter templates, intake, and public worklists for five states. The maintained pipeline uses R. [in-rolls/rti-analysis](https://github.com/in-rolls/rti-analysis) contains the analysis and results paper. The two projects exchange versioned files with checksums; neither imports the other's R code.

[Fieldwork viewer](https://in-rolls.github.io/rti/) · [Study design](design/study_plan.tex) · [Data dictionary](docs/data_schema.md) · [Migration record](docs/migration.md)

## Reproduce the public release

Use R 4.6.0 and GNU Make. Package versions are recorded in `renv.lock`.

```sh
make restore
make check
```

The checks verify every imported source against its SHA-256 hash, rebuild the state frames, reconcile all 1,665 issued assignments, build the viewer, run the regression tests, and lint the R code. `make ci-docker` runs the same checks in the standard `rocker/tidyverse:4.6.0` image.

Generated public datasets are in `data/release/`. The site is built in `_site/`; it reads those assignments and serves the preserved instruments. `make hooks` installs the privacy check before pushes.

## Repository layout

| Directory | Contents |
| --- | --- |
| `R/` | Shared frame, sampling, intake, letter, release, and privacy functions |
| `scripts/` | Commands calling those functions |
| `config/` | Source definitions, batch catalog, form fields, and vocabularies |
| `data/raw/` | Unmodified public source snapshots |
| `data/reference/` | Frozen frames, issued batches, and historical records |
| `data/release/` | Generated public authorities and assignments |
| `data/private/` | Local intake state and private inputs; excluded from Git |
| `design/` | Original study plan and amendments |
| `site/` | One viewer for all states and batches |
| `tests/testthat/` | Behavioral and historical-preservation tests |

## Reading the code

Start with `scripts/01_build_release.R`, which verifies the frozen sources and builds the public datasets. `scripts/02_build_site.R` uses those datasets to build the viewer. Other scripts expose the draw, render, register, and intake commands described below; their implementation lives in `R/`.

`R/frames.R` contains the state-specific parsers. `R/sampling.R` supplies one allocation and randomization implementation, selected by configuration. `R/intake.R` owns application updates and the submission ledger. `R/io.R` centralizes identifiers, file access, and source verification; `R/release.R` builds public datasets and worklists. Letter rendering and privacy checks have their own modules. A new state needs a parser and configuration, rather than a copy of the sampler, intake, or viewer.

## Issued and future batches

`config/batches.csv` identifies the six issued batches. Their assignments, treatments, assistant assignments, and instruments are immutable. They were drawn using the historical Python programs; the R pipeline verifies those records instead of attempting to reproduce Python's draws with an R seed.

New batches use one shared sampler, configured explicitly for proportional or department-by-tier selection and batch-wide or blocked treatment assignment. `config/example_batch.yaml` is an example, not an approved design or an issued batch.

```sh
Rscript scripts/draw_batch.R config/example_batch.yaml data/private/example_batch
```

The command creates a proposal for review. It excludes all historically issued and locally registered offices, allocates IDs above the issued sequence, and records configuration, input hashes, R version, RNG settings, and seed. A new output directory is required. After reviewing the proposal, render its letters and register it before filing:

```sh
Rscript scripts/render_batch.R data/private/example_batch config/private/filer.yaml
Rscript scripts/issue_batch.R data/private/example_batch
```

Personalized letters stay under `data/private/letters/`. Registration writes `data/private/batches.rds`; later draws and intake read that same register. Two proposals drawn before registration may overlap, but the second cannot be registered after the first if IDs or offices conflict. Run one registry or intake writer at a time. Publish a new issued batch only after review by adding its complete frozen assignments, instruments, and provenance to the public catalogs. The private registration remains as evidence: subsequent commands use the public copy only when every registered assignment field matches, and reject partial or changed publication. Historical programs remain available under the tags in [the history map](docs/history.csv).

## Filing and follow-up

Export the filing or update form to CSV and keep the export outside Git:

```sh
Rscript scripts/intake.R filing data/private/filing_export.csv
Rscript scripts/intake.R update data/private/update_export.csv
```

Intake stores applications, events, and a submission ledger together in `data/private/intake.rds`. A repeated export has no effect, including after a manual correction. Changed content under an already processed submission ID raises an error. Invalid application IDs, choices, or filing dates stop the import before the saved state changes. Dates must use `YYYY-MM-DD`.

This intake database starts from the assignment register. It does **not** replace the paper's current response reconstruction. Moving that workflow requires comparison against the complete private originals; see the migration record. Public worklists contain no response status or private filing information.

## Attribution

The original fieldwork and state extensions were developed by Gaurav Sood and Priyadarshi Amar. Source revisions, original paths, and destination hashes are recorded in `docs/source_manifest.csv`, including the Delhi–Maharashtra extension. The R consolidation preserves the issued designs and distinguishes them from prospective sampling.
