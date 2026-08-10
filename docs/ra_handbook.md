# Filing and tracking: what to do

You have a worklist and two forms. Everything you need is on the worklist;
everything you observe goes into a form. You never type an identifier, a name,
an address, or a due date.

## Before you start

Open your batch's worklist, `out/<batch>/filing_sheet.csv`. One row per
application, with the office, the portal, the fee, and the file holding the
letter.

Check the `needs_translation_review` column first. A `yes` means the letter is
in a language nobody has proofread. **Do not file those.** They carry a banner
saying so at the top of the file. Set them aside until a reviewer signs off.

## Filing one application

1. Open `applications/<application_id>.txt` from the worklist.
2. If there is a review banner, stop and set it aside.
3. Copy the letter above the `ENGLISH COPY` divider. That is the one to file.
   The English text below it is there so the team can read what was sent.
4. File on the portal named in the worklist. Pay the fee shown.
5. Screenshot the confirmation and the payment receipt.
6. Fill in **Form 1**.

If anything stops you — the office is not in the dropdown, the payment fails,
the portal is down after three tries — that is a normal outcome, not a failure
on your part. Fill in Form 1 and choose "Could not file", with the reason.

**Recording why you could not file matters as much as recording a success.** The
study reports how many offices a citizen can actually reach. An office missing
from its own portal's dropdown is a finding. If it is not recorded on the day,
nobody can reconstruct it later.

## Form 1 — File an application

One submission per application, whether or not it was filed.

| Field | What to put |
|---|---|
| Application ID | Pick from the dropdown. Never type it. |
| Were you able to file it? | Filed, or Could not file |
| Reason | Only if you could not file. Pick the closest; use Notes for detail. |
| Date filed | The date the portal accepted it |
| Registration number | Exactly as shown on the receipt, including slashes |
| Fee paid | The amount actually charged |
| Payment mode and reference | From the receipt |
| Evidence | Confirmation screen and payment receipt |
| Notes | Anything odd |

Nothing asks you to work out a due date. That is computed from the filing date
and the state's own rules, which are not the same everywhere.

## Form 2 — Update an application

One submission per thing that happens. If three things happen, submit three
times. Never go back and edit an earlier submission: the order things happened
in is itself the data, and editing destroys it.

Submit an update when any of these arrive:

- an acknowledgement
- a transfer to another office under s.6(3) — record which office
- a demand for more fee, for clarification, or for proof of identity
- a phone call from the PIO, or a request that you come in person
- an interim or holding reply
- a substantive reply, or a refusal
- anything to do with an appeal: filed, hearing notice, decided
- the letter coming back undelivered

Use the date **printed on the document**, not the date you opened it. If they
differ and it matters, say so in Notes.

Nothing needs recording when nothing happens. Silence past the deadline is
computed from the dates already stored; there is no "no reply yet" to submit.

## If you make a mistake

Do not submit a correction through the form. Tell whoever curates the data,
naming the application and what is wrong. They fix the cell directly, and the
change is recorded in the project's history with who made it and when.

## Questions worth asking

- A reply arrived but it is not what was asked for → still `Substantive reply
  received`. Whether it answered the question is coded later, by someone else.
- A reply covering two applications → submit an update for each.
- Two transfers in a row → two submissions. That is exactly what the form is
  built for.
- The office says to email instead of using the portal → record it as a `note`
  with what they said, and ask before changing channel.
