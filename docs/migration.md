# Consolidation record

The project has two maintained repositories: `in-rolls/rti` for fieldwork and `in-rolls/rti_analysis` for analysis and the paper. Both are intended to be public; private source documents and intake state stay outside Git. The maintained fieldwork code uses R, with shared allocation, treatment assignment, assistant allocation, intake, validation, letters, and worklists. Portal parsing and batch design remain explicit differences.

## Preserved evidence

`docs/source_manifest.csv` records original repository, commit, path, destination, and SHA-256 for every imported file. It includes the original study design, state amendments, portal snapshots, frames, issued batches, worklists, and instruments. Files are verified before building a release. Identically named amendments from different states are kept in separate state directories.

The six batches contain 1,665 assignments: 1,000 Tamil Nadu, 375 Telangana, 180 Karnataka, 44 Delhi, and 66 Maharashtra. Every original assignment column is compared against its source snapshot. The shared frame contains 23,169 offices. Tamil Nadu's 17,417 offices are rebuilt from its categorized universe and classified table; the other four states are rebuilt from their public portal snapshots and legacy location tables.

Historical batch YAML files are preserved under `config/batches/` as source evidence. They are not executable R configurations, and their original paths remain unchanged within the files. `config/batches.csv` is the authoritative catalog for issued assignments. `config/example_batch.yaml` demonstrates the prospective R sampler. Future specifications must describe actual selection and randomization explicitly, rather than relying on historical comments that disagree with the original code.

Python source is preserved in Git history. `docs/history.csv` records the state histories imported under `history/` tags in this repository, including the merged address-update PRs after transfer. These tags preserve complete commit ancestry and original trees, including code, environment files, dashboards, and documentation that are not part of the maintained R tree. For example, `git show history/rti-karnataka:README.md` reads the original Karnataka README. Original random draws are preserved as immutable assignments; the R sampler is for new batches and does not claim seed compatibility with Python.

The maintained instrument text and controlled vocabularies were extracted from `in-rolls/rti` at `e795a6d1f78b385e1960dac5db28337ad0ac6cf7`, from `src/rti/letters/wave1.py` and `src/rti/enums.py`. These are transformed text/configuration assets rather than byte-identical source files. Issued templates remain separately frozen and hashed.

## Behavior changes

Intake now keeps a persistent submission ledger. Replaying multiple submissions for an application cannot overwrite a later manual correction. A changed payload for a processed source ID raises an error. Switching a filing to `not_filed` clears incompatible filing dates, registration, and payment fields; switching back clears the failure reason. Invalid exports leave the saved state unchanged.

Private intake is saved in one RDS file, with applications, events, and submission ledger committed together. The former SQLite database was a derived convenience, not an independent data source; it is replaced by these directly inspectable R tables. Public exports use a column allowlist and exclude response status and private filing fields.

## Remaining cutover work

Private-original verification is in progress before response extraction and event matching move out of the paper repository. The three frozen configuration files and 18 frozen sheet exports were recovered through the connected Drive and match the manifest. The local ZIP supplies 472 matching originals. The currently accessible Drive listing and ZIP together still lack 131 pinned receipt or response-document paths; the remaining parts of the original download are needed to resolve these gaps. The existing frozen analysis inputs remain authoritative; the old 135-row application table is retained only as historical evidence.

The replacement viewer must be deployed and checked before the transferred state repositories are retired. Their full histories are preserved here, but deleting a repository also removes its Pages address. An archived repository can keep serving its old address. No source history or original document should be discarded to reduce the number of active repositories.

Priyadarshi transferred the original analysis repository to `in-rolls/rti-analysis`. The development fork, `in-rolls/rti-paper`, will be deleted after its paper branch is merged into the original and every unique commit is verified there. The fork is not a third deliverable.

## Verification results

The locked R environment was restored locally. All 80 fieldwork test assertions, lint, privacy checks, actionlint, and the GitHub Actions check pass. The Linux workflow also reproduces the committed public release without differences. An isolated draw–render–register smoke test and viewer filtering/link checks pass. Local Docker and visual browser rendering were unavailable.

Recovered private inputs reproduce the paper's email audit, RA filing summary, and matched-event CSVs exactly. The paper passes 212 assertions with one full-originals check skipped; its analysis CSV and four result CSVs are unchanged. Full receipt/response-document verification and deployment remain pending.

On 2026-11-05 the repositories were renamed to snake case, matching the other in-rolls study repositories: `rti-analysis` → `rti_analysis`, `rti-telangana` → `rti_telangana`, `rti-karnataka` → `rti_karnataka`, `rti-delhi-maharashtra` → `rti_delhi_maharashtra`. GitHub redirects the old repository addresses; it does not redirect GitHub Pages, so the state dashboards moved to `https://in-rolls.github.io/rti_<state>/`. The `history/rti-*` tags keep their names.
