# Data dictionary

`make release` generates two UTF-8 CSVs with blank strings for unavailable text. IDs are strings. Literal `NA` values in historical state sources remain literal source values; they are not interpreted as R missing values when reading the snapshots.

## Public release

`authorities.csv` has one row per office and a unique `authority_id`. Tamil Nadu retains its original `TN-<node_id>` identifiers. Other states use a hash of normalized state, office, district, and block, with occurrence suffixes for repeated normalized keys. The input snapshots fix occurrence order.

| Column | Meaning |
| --- | --- |
| `authority_id` | Stable office key within the frozen frame |
| `state`, `state_code` | Full state name and TN, TG, KA, DL, or MH |
| `office_name` | Office label used to identify the authority on its portal |
| `district`, `block` | Location fields from the historical classification |
| `portal` | Historical portal label |
| `node_id`, `tree_department`, `tier` | Tamil Nadu hierarchy; blank elsewhere |
| `dept_group` | Department grouping used for sampling |

`assignments.csv` has one row per issued application and a unique `application_id`. Its `authority_id` is a many-to-one foreign key to authorities (currently each selected office occurs once). The join must preserve every assignment. Flat state batches match the frame by exact state and office label, with no fuzzy fallback. Tamil Nadu already supplies the authority ID.

Additional assignment columns are `batch_id`, `treatment` (`plain` or `legal_salience`), `assigned_ra`, `randomization_stratum`, `template_version`, `language`, and `channel`. An assignment does not establish that a request was filed. Source metadata and original assignment columns remain available in `data/reference/analysis_inputs/`.

`checksums.csv` records the SHA-256 digest of each release CSV. `docs/source_manifest.csv` maps each imported file to its source repository, commit, original path, destination path, and SHA-256 digest. Generated release files are reproducible views; frozen files are evidence and must not be edited.

## Private intake

`data/private/intake.rds` is one R list containing `applications`, `events`, and `submissions`, saved atomically after validation. Keeping the ledger and records in one file prevents an interrupted import from saving one without the other. Run a single intake writer at a time.

Applications retain all assigned offices, including unreported and failed filings. `filing_outcome` is blank, `filed`, or `not_filed`. A successful filing requires an ISO date; a failed filing requires a controlled reason. A failure clears registration, dates, payment reference, fee, and payment mode. A subsequent successful filing clears the failure reason. Private fields include filer identity, registration, payment details, evidence URLs, and free-text notes.

Events are append-only and may repeat a type for one application. Each has an event ID, application ID, event type, date, direction, medium, document link, and recording metadata. The allowed values and human-readable labels live in `config/vocabularies.json`; form aliases live in `config/forms.yaml`.

Submissions record the form, application ID, timestamp, source-row hash, and payload hash. A previously seen source ID with a different payload requires explicit review. The submission ledger is never inferred from the latest application row.
