"""Reproducible sampling, letter generation, and monitoring for an RTI audit study.

The pipeline runs in five stages:

    scrape -> frame -> sample -> render -> monitor

`scrape` builds the universe of filable offices from a state RTI portal.
`frame` merges those universes into one canonical sampling frame.
`sample` draws a seeded batch and writes one application row per planned letter.
`render` turns each row into a bilingual, paste-ready application.
`monitor` loads what research assistants record back into three tables.
"""

__version__ = "0.1.0"
