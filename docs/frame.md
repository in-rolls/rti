# Sampling frame contract

`data/frame.csv` has one row per portal-listed office. The frame is the left
table: a build must preserve the source row count, and `authority_id` must be
unique before any sample is drawn.

## Sources and join

The national classified file contains 23,167 rows across six states. Tamil
Nadu's 17,417-row slice is replaced by the committed crawl, using normalized
office name plus occurrence to carry the flat classification fields onto the
tree. The office-name multisets and row counts must match exactly; otherwise the
build fails. The crawl is the left side of this 1:1 join, so all portal nodes
survive. The other five states remain flat and their tree fields are blank.

Current row-count contract:

| State | Rows | Tree available |
|---|---:|---|
| Tamil Nadu | 17,417 | Yes |
| Telangana | 3,325 | No |
| Karnataka | 1,699 | No |
| Rajasthan | 290 | No |
| Delhi | 221 | No |
| Maharashtra | 215 | No |
| **Total** | **23,167** | |

## Column dictionary

| Column | Unit and meaning | Missingness | Provenance |
|---|---|---|---|
| `authority_id` | Unique office key | Never | `TN-<node_id>` for crawled Tamil Nadu; flat-field hash otherwise |
| `state`, `state_code` | State name and two-letter code | Never | Classified source, with aliases normalized |
| `department` | Portal office name used in the application | Never | Crawl `name` or flat `Department` |
| `district`, `block` | Geographic coding from the flat source | May be blank or not applicable | Classified source |
| `portal` | Normalized portal slug | May be blank in future sources | Classified source or scraper configuration |
| `relevant` | Legacy reservation-keyword screen | Never; 0/1 | Crawl flag for Tamil Nadu, classified source otherwise; ignored by wave 1 |
| `category`, `quota_source`, `quota_role`, `confidence` | Legacy classification fields | Often blank | Classified source |
| `node_id` | Portal-tree node identity | Blank for uncrawled states | Crawl |
| `parent_id`, `parent_name` | Immediate parent node | Blank for uncrawled states | Crawl |
| `tree_department` | Level-1 ancestor used as the sampling stratum | Blank for uncrawled states | Crawl `department` |
| `level`, `level_label` | Portal depth and tier label | Blank for uncrawled states | Crawl |
| `path` | Full root-to-office authority path | Blank for uncrawled states | Crawl |
| `is_leaf`, `has_children` | Tree-frontier indicators | Blank for uncrawled states | Crawl |
| `source` | File supplying office identity | Never | Frame builder |

The flat classifications cannot distinguish structural missingness from fields
that were simply not coded. They are retained for later waves but are not used
to construct the initial sample.

## Initial-batch eligibility

Batch `b2026q3_02` requires nonblank `node_id`, `tree_department`, `level`,
`level_label`, and `path`, and filters to Tamil Nadu. Consequently all six state
lists remain in the canonical frame while only the crawled Tamil Nadu universe
is eligible for wave 1. `out/b2026q3_02/batch_meta.json` records hashes for both
the full frame and this eligible projection.
