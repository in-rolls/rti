# Intake forms

The filing and update exports are mapped by `config/forms.yaml`. It is the single mapping between question text and stored columns. Harmless punctuation and whitespace differences in headings are normalized; ambiguous headings fail.

Allowed answers and their display labels are in `config/vocabularies.json`. Both labels and stored values are accepted. New wording that does not map to a controlled answer fails rather than silently producing a blank value.

Use ISO dates (`YYYY-MM-DD`) for filing and document dates. The form timestamp and application ID identify a submission. Keep the timestamp unchanged in repeated exports. Use a new submission for a correction supplied through the form; a curator can instead update the saved private state while retaining its submission ledger.

Run `Rscript scripts/intake.R filing EXPORT.csv` or `Rscript scripts/intake.R update EXPORT.csv`. Both commands use the same validation and persistence path. Existing application IDs are required: forms cannot create assignments.
