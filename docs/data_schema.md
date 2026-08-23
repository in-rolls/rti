# Data schema

Three tables carry the study: `authority`, `application`, `event`. Everything a
paper reports — response rates, days to reply, transfer chains, attrition — is
computed from them rather than stored.

`schema.sql` is generated from `src/rti/enums.py` by `rti-build-db`. Edit the
enums, not the SQL.

## Why three

The hand-kept log this replaces, `data/rti_filing_evidence_log.csv`, is 32
columns wide because it stacks five kinds of fact in one row.

| Columns | A fact about |
|---|---|
| `state`, `public_authority` | the office |
| `applicant`, `sender_email` | the person filing |
| `rti_id`, `registration_number`, `filing_date`, `fee_paid_inr`, `payment_reference` | the application |
| `response_*`, `first_appeal_*`, `fa_*`, `second_appeal_*`, `sa_*` | things that happened |
| `*_summary`, `current_status` | a judgment about a reply |

Sixteen of those columns are the same three facts — a date, a medium, a document
— repeated five times with a different prefix each. That design has a ceiling: a
second s.6(3) transfer, a remanded second appeal, or a fee demanded twice has
nowhere to go, and there is no transfer column at all.

As rows in `event`, all of it is free. Transfer count is a `COUNT`. The
ping-pong chain is those rows in date order. A fifth thing happening next week
needs no schema change.

The office and the filer split out for a different reason: they outlive the
application. One office receives letters across several batches and joins to
census and election data; one filer files two hundred applications, and a typo
in an email address should not make that look like two people.

## `authority`

One row per office that could be written to. Populated by `rti-sample` from
`data/frame.csv`, which is itself built from the scrapers and the classified
state lists.

For a crawled state, `authority_id` is the state code plus the portal
`node_id`; this is the office identity exposed by the portal tree. For an
uncrawled flat list it is a content hash of state, office name, district, and
block, with an occurrence discriminator when those fields collide. No source
row is discarded merely because its display fields match another row.

## `application`

One row per **planned** letter, written when the office is sampled.

The columns fall in two groups. `rti-sample` writes the design: identifier,
batch, office, topic, language, channel, template version. `rti-load` fills the
execution: outcome, dates, registration number, fee, evidence.

`filing_outcome` has three meaningful states, and the blank one matters:

| Value | Meaning |
|---|---|
| `''` | Nobody has reported on this application yet |
| `filed` | Filed, with a registration number |
| `not_filed` | Attempted and stopped, with `not_filed_reason` |

That third value is the study's attrition record. It only exists because the row
was created at sampling rather than at filing. `v_attrition` reports it per
state.

`application_id` is `KA-014`: two-letter state code, sequential within the
state, continuing across batches. It matches the convention already used in the
evidence log, and it is short enough to read off a receipt and check.
`rti-migrate-log` must therefore run before the first `rti-sample`, so the
sequence continues rather than collides.

`due_date` is computed by the loader from `filing_date` and the state's
statutory clock in `config/state_rules.yaml`, and `rti-check` recomputes it and
fails if the stored value disagrees. It is stored because an RA needs to see it,
and verified because stored derivations rot.

## `event`

One row per thing that happened, append-only. `event_type` is closed and defined
in `enums.py`.

There is deliberately no `deemed_refusal` event. Deemed refusal is the *absence*
of a reply by the deadline, and nobody should be asked to record a non-event; it
falls out of `filing_date`, `due_date`, and the absence of a response row.

## Views

`v_status` — one row per application, with `first_ack_date`, `response_date`,
`n_transfers`, `n_fee_demands`, `last_event`, `days_to_response`, and a derived
`status`.

`v_attrition` — one row per state: sampled, filed, not filed, not yet reported,
and the two most common failure reasons.

## What is deliberately not here

The earlier draft of this document proposed twenty-five tables. Most are good
ideas that need something this study has not committed to. Table count is cheap;
the standing cost is that somebody has to fill each one, and every enum in it
needs a coding protocol behind it.

**Config files instead of tables.** `state_rules` is six rows, so it is
`config/state_rules.yaml`. The four private filer profiles are in
`config/private/filers.yaml`.
Batch metadata is `out/<batch>/batch_meta.json`, and the drawn sample is
`out/<batch>/assignments.csv`, both committed — which is why folding `assignment`
into `application` costs nothing.

**Deferred, and addable without migrating anything.** `pio_contacts` (the PIO as
a person, if the individual becomes a unit of analysis), `request_items` and
`item_outcomes` (per-clause compliance coding), `exemptions_cited`, `appeals` as
its own table, `costs`, `double_coding`, `authority_covariates`,
`substantive_yield`. Each needs a new collection protocol, not a new table.
`event` absorbs the history until then.

**Out of scope while the study is online-only.** `dispatch` and `mail_intake`
are the postal leg. `portals` and `portal_probes` are a separate question about
whether portals work at all.

**Rejected.** `templates` and `clauses` as database tables. Git already versions
the letter text, and `template_version` on `application` gives the same audit
trail. A database copy of files that live in the repository is a second source
of truth.

## Migrating the old log

`rti-migrate-log` splits the three existing rows into the three tables without
altering a recorded value. Two data-quality facts survive as notes rather than
being silently repaired: `sender_email` was marked inferred on two of three
rows, and `public_authority` on TG-001 reads `(not shown on receipt - see
application)`. The second is exactly why `authority_id` is assigned at sampling
rather than read off a receipt.
