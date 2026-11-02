# Consolidation record

The migration brings the state fieldwork repositories into `in-rolls/rti` and retains the private research repository as the analysis boundary. The maintained fieldwork code uses R, with shared allocation, treatment assignment, assistant allocation, intake, validation, letters, and worklists. Portal parsing and batch design remain explicit differences.

## Preserved evidence

`docs/source_manifest.csv` records original repository, commit, path, destination, and SHA-256 for every imported file. It includes the original study design, state amendments, portal snapshots, frames, issued batches, worklists, and instruments. Files are verified before building a release. Identically named amendments from different states are kept in separate state directories.

The six batches contain 1,665 assignments: 1,000 Tamil Nadu, 375 Telangana, 180 Karnataka, 44 Delhi, and 66 Maharashtra. Every original assignment column is compared against its source snapshot. The shared frame contains 23,169 offices. Tamil Nadu's 17,417 offices are rebuilt from its categorized universe and classified table; the other four states are rebuilt from their public portal snapshots and legacy location tables.

Historical batch YAML files are preserved under `config/batches/` as source evidence. They are not executable R configurations, and their original paths remain unchanged within the files. `config/batches.csv` is the authoritative catalog for issued assignments. `config/example_batch.yaml` demonstrates the prospective R sampler. Future specifications must describe actual selection and randomization explicitly, rather than relying on historical comments that disagree with the original code.

Python source is preserved in Git history and the source repositories at the recorded commits. It is not part of the maintained pipeline. Original random draws are preserved as immutable assignments; the R sampler is for new batches and does not claim seed compatibility with Python.

The maintained instrument text and controlled vocabularies were extracted from `in-rolls/rti` at `e795a6d1f78b385e1960dac5db28337ad0ac6cf7`, from `src/rti/letters/wave1.py` and `src/rti/enums.py`. These are transformed text/configuration assets rather than byte-identical source files. Issued templates remain separately frozen and hashed.

## Behavior changes

Intake now keeps a persistent submission ledger. Replaying multiple submissions for an application cannot overwrite a later manual correction. A changed payload for a processed source ID raises an error. Switching a filing to `not_filed` clears incompatible filing dates, registration, and payment fields; switching back clears the failure reason. Invalid exports leave the saved state unchanged.

Private intake is saved in one RDS file, with applications, events, and submission ledger committed together. The former SQLite database was a derived convenience, not an independent data source; it is replaced by these directly inspectable R tables. Public exports use a column allowlist and exclude response status and private filing fields.

## Remaining cutover work

Private-original verification is in progress before response extraction and event matching move out of the paper repository. The three frozen configuration files and 18 frozen sheet exports were recovered through the connected Drive and match the manifest. The local ZIP supplies 472 matching originals. The currently accessible Drive listing and ZIP together still lack 131 pinned receipt or response-document paths; the remaining parts of the original download are needed to resolve these gaps. The existing frozen analysis inputs remain authoritative; the old 135-row application table is retained only as historical evidence.

The replacement viewer must be deployed and checked before the redundant organization forks are archived. Priyadarshi's upstream repositories and Pages sites are separate and remain intact. No original repository is deleted.

Our analysis fork was renamed to `in-rolls/rti-paper` on November 2, 2026, preserving its private visibility and PR. Priyadarshi intends to transfer the original to `in-rolls/rti-analysis`; subsequent paper changes should be proposed against that repository. GitHub's documented transfer restrictions may require resolving the existing fork in the destination account before his transfer succeeds. The fork remains in `in-rolls` at the user's direction.
