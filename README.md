# RTI Karnataka

Reproducible sampling, RA assignments, and a tracking dashboard for filing
RTI applications to Karnataka public authorities. Sibling of
[rti-telangana](https://github.com/in-rolls/rti-telangana) and, like
it, an extension of the Tamil Nadu pipeline in
[in-rolls/rti](https://github.com/in-rolls/rti): scrape the portal's own
universe, freeze the frame, one seeded draw, randomized treatment
assignment, balanced RA worklists, and a static GitHub Pages viewer.

**Dashboard:** https://in-rolls.github.io/rti-karnataka/

## The universe

Karnataka's portal ([rtionline.karnataka.gov.in](https://rtionline.karnataka.gov.in))
gates its filing form behind email verification, OTP, and CAPTCHA, but
publishes the complete roster of onboarded public authorities on an
unauthenticated page, `NodalOfficerDetails.php`. On 2026-09-07 we saved
that page raw (committed unmodified under
`data/raw/portal_scrape_2026-09-07/`); `scripts/build_frame.py` parses it
into `data/frame_karnataka.csv` and writes `data/frame_provenance.json`.

- **1,800 distinct public authorities** (no duplicates in the roster).
- 1,695 match the project's earlier `state_department` classification file
  (which had 1,699 Karnataka rows); 105 have been onboarded since, 4
  delisted. District and block are joined from the legacy file where
  matched; otherwise the district is read off the office name's leading
  segment.
- Office names are kept **portal-verbatim** so RAs can match them against
  the portal's Public Authority dropdown.

## The batch

Batch `ka2026q3_01`, seed `20260907`, draws **180** of the 1,800 offices —
a 10% sampling rate. The frame's SHA-256 is frozen in
`out/ka2026q3_01/batch_meta.json`.

Karnataka office names lead with the district and end with the department
(`Bagalkot-Mudhol-Rural Development and Panchayat Raj - RDPR(T.P)`), so
stratification is by **department group** taken from the name's trailing
segment. Allocation across strata is proportional to stratum size with a
floor of 1 and a cap of 15; groups with fewer than 5 offices are pooled
into a single OTHER stratum.

Within the draw:

- **Treatment:** 126 plain letters, 54 legal-salience (70/30), assigned by
  seeded shuffle. The legal-salience letter is byte-identical to the plain
  one except for the pre-specified Section 7(1)/20 paragraph.
- **RAs:** RA1–RA4, exactly 45 each, balanced within treatment arm.

Re-running `python3 scripts/sample.py` reproduces the batch byte-for-byte.
A new wave means a new `batch_id` **and** a new seed.

## What RAs do

1. Open the dashboard, download your worklist (`out/ka2026q3_01/worklists/`).
2. File each row on [rtionline.karnataka.gov.in](https://rtionline.karnataka.gov.in)
   (reachable only from India). The flow needs your email, an OTP, and
   three CAPTCHAs; the fee is ₹10, payable online.
3. Pick the row's `office_name` in the Public Authority dropdown, then
   paste the letter matching the row's `treatment` from
   `out/ka2026q3_01/templates/` (fill only the `[FILER ...]` placeholders;
   filer details are private and never committed here).
4. Record every attempt in the filing form — including offices that could
   not be filed to. The "could not file" rows preserve the denominator.

## Repository layout

```
config/batch.yaml         frozen batch design
data/raw/                 portal roster page + legacy district file, never modified
data/frame_karnataka.csv  the 1,800-office frame (generated)
data/frame_provenance.json how the frame was built
scripts/build_frame.py    raw roster -> frame
scripts/sample.py         the seeded draw (stdlib only, no dependencies)
out/ka2026q3_01/          assignments.csv, batch_meta.json, worklists/, templates/
docs/                     the GitHub Pages dashboard (copies of the above)
```

## Privacy

No filer names, addresses, emails, phone numbers, or evidence links are
committed. Letters contain placeholders. The raw roster page is a public
government directory of nodal officers, committed as-is for provenance.
Filing records with personal details live outside this repository.
