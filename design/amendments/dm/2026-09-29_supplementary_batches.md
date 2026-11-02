# Design note: supplementary batches (2026-09-29)

**Trigger.** RA report received 2026-09-29: "Can we please sample more
departments from Telangana, Maharashtra and Delhi? Karnataka and Tamil
Nadu portals are being very unreliable." Karnataka filing (batch
ka2026q3_01) is stalled by portal unavailability; those rows remain live
and every failed attempt is recorded as not_filed with a reason — portal
unreliability is an outcome, not a design revision.

**Rule (fixed before drawing).** RA capacity freed by the unreliable
portals is reallocated by OVERSAMPLING the states with smaller
online-filable universes, so each reachable state supports credible
within-state estimates:

- Delhi: 10% -> 20% (22 -> 44 of 223)
- Maharashtra: 10% -> 20% (33 -> 66 of 328)
- Telangana: +125, half its original batch (250 -> 375 of 3,401; 7.4% -> 11%)

**Method.** New batch_id and new seed; drawn from the SAME frozen frame
(SHA-256 verified against the prior batch before drawing); offices
already sampled are excluded. Allocation is a top-up: proportional
targets are computed for the UNION at the new rate, with each stratum
floored at what wave 1 already drew, so the union matches what a single
larger proportional draw would have targeted. The per-stratum cap scales
with the union size and applies only to named department groups — the
pooled OTHER stratum is a residual, not a department, and is uncapped.
Treatment stays 70/30 within batch (and within state), assigned by
seeded shuffle exactly as in wave 1. Prior batches are byte-identical
to their committed versions.

**Analysis implication.** Wave now varies within these states; analyses
pool waves with a batch indicator (or batch fixed effects). Cross-state
comparisons remain confounded with portal, as they always were.

---

## Addendum 2026-10-04: Maharashtra instrument v5_mh150

Offices phoned RAs asking which internal division the request targets
(e.g. Police Commissioner Office, Navi Mumbai: "which specific division's
information do you need, won't get it for all of Navi Mumbai"). v5 adds
one scope sentence — "This request covers only the register of your own
office, not subordinate divisions." — and, to stay inside the portal's
150-word cap (plain 122 / legal 148), drops the Section 6(3) transfer
request sentence and tightens phrasing. Wave-2 Maharashtra rows
(MH-034...MH-066) carry template_version v5_mh150; wave-1 rows keep
v4_mh150, the instrument they were actually filed with. Unfiled wave-1
Maharashtra rows should also be filed with v5, with the version noted in
the tracking sheet. Analyses treat template_version as filed, by row.

**Same-day revision to v6_mh150 (2026-10-04).** v5 was superseded within
hours, before any filing used it. v6 replaces the bare exclusion with a
fallback: "This request covers your own office register only. If none is
maintained, kindly provide the registers of your subordinate divisions."
(plain 121 / legal 147 words). Wave-2 Maharashtra rows carry v6_mh150;
v5 files remain in the repository for the record.
