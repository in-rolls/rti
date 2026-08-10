# The two Google Forms

Run `rti-forms` to print the current specification, with option lists and the
application-id dropdown generated from `src/rti/enums.py`. Build the forms from
that output rather than from this page: this explains the design, that gives the
exact text.

```bash
rti-forms                      # full specification
rti-forms --ids-only           # just the dropdown values
rti-forms --out /tmp/spec.txt
```

## Why two forms rather than a spreadsheet

A Google Form appends. It cannot overwrite, two people cannot collide on a cell,
and every submission is timestamped for free. That matches an append-only event
table exactly, and it removes the failure a shared spreadsheet invites, where
someone sorts a column and quietly destroys the row alignment.

It also removes typing. Both forms open with a dropdown of that batch's
application ids, so nobody transcribes an identifier. The filer's name, address,
and email are never asked for; they come from `config/filer.yaml`. Due dates are
never asked for; they are computed from the filing date and the state's rules.

## Form 1 — File an application

One submission per application, **whether or not it was filed**.

The branch on "Could not file" is the part that carries the study. It records
attrition: an office missing from its own portal's dropdown, a payment gateway
that fails, an office that has been abolished. Without it, response rate is
computed over applications that happened to succeed, and the twelve that did not
leave no trace at all.

Settings: collect email addresses, allow file upload, do **not** limit to one
response per person, and turn edit-after-submit off.

## Form 2 — Update an application

One submission per thing that happens; submit again for the next thing. Never
edit an earlier submission, because the sequence is the data.

The `What happened?` list is `EVENT_TYPES`. A transfer asks which office it went
to, which is what turns a chain of transfers into something analysable.

## Loading responses

Export each form's responses as CSV into `data/intake_raw/`, named
`filing_*.csv` and `update_*.csv`, then:

```bash
rti-load --all
rti-check
rti-build-db
```

`rti-load` is idempotent. Each submission gets a `source_row_id` derived from the
form, the timestamp, and the application id, and a submission already present is
skipped. Loading the same export twice changes nothing, and a cell a curator
fixed by hand survives the next load.

## When a question gets reworded

Editing a question renames its column in the export. `rti-load` matches column
headings loosely, ignoring case, spacing, and punctuation, and it accepts a few
known alternative wordings per field. If a rewording still breaks the match, add
it to `FILING_FIELDS` or `UPDATE_FIELDS` in `src/rti/intake.py`.

Changing an *option*, though, is a schema change. The option lists come from
`enums.py`, and a value the enums do not know is rejected at load time with a
message naming the answer and the alternatives, rather than being written into
the table where it would fail later and less legibly.

## Corrections

There is no correction form. An RA who notices a mistake tells the curator,
who edits `data/tables/*.csv` directly and commits. The commit is the audit
trail, `rti-check` runs in CI, and a bad edit fails the pull request.
