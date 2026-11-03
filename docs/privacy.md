# Privacy boundary

Raw emails, response documents, filer identities, registration numbers, payment references, evidence links, and free-text intake notes remain outside Git, under `data/private/` or another private location. Keep filer configuration under `config/private/`.

Public assignment exports use an explicit column allowlist in `R/privacy.R`. Adding a column to intake therefore does not expose it in the release or viewer. The viewer reports issued assignments, not response outcomes.

`make privacy` checks tracked and unignored files for private paths, populated private CSV columns, contact details in free text, and registration patterns. Unchanged, hashed historical public sources are allowed as provenance; changing one removes that exemption. This automated check is a backstop, not proof that arbitrary free text is safe to publish. Review new public source material before adding it.

The private research compendium retains its existing access boundary. Moving extraction code does not authorize publishing its inputs or outcomes.
