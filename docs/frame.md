# Office frames

`config/sources.yaml` selects the frozen frame and public source snapshots for each state. One builder handles legacy classification joins and normalized output. Parser branches correspond to portal formats: Telangana JSON pages, Karnataka table rows, Delhi and Maharashtra dropdown options, and Tamil Nadu's office hierarchy.

Tamil Nadu is reconstructed from the preserved categorized office universe and classification table. Names join by normalized name and occurrence; every row must match once. Original crawl HTML is not present in this repository, so this check does not establish raw-HTML-to-universe reproduction.

Telangana pages contain raw control characters. The parser normalizes those characters before JSON decoding, matching the historical script's permissive decoding and whitespace normalization. Delhi and Maharashtra retain HTML entity spelling from the historical extraction because those labels define the frozen office identities.

`make release` compares reconstructed frames with the frozen frames. Differences fail rather than changing the population silently. New collections require a new source snapshot and reviewed configuration.

The Tamil Nadu collector is available as `Rscript scripts/collect_tn.R data/private/tn_crawl`. It uses shared HTTP retry behavior and saves a resumable checkpoint. Office identities derive from names and parentage rather than the portal's transient encrypted URLs. Parser and checkpoint behavior are tested with fixtures; a fresh live crawl is a separate operation and has not been performed during consolidation.
