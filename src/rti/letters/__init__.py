"""Application text: shared blocks, per-topic bodies, and the composer.

The split exists because the six original templates carried six copies of the
same salutation, fee sentence, and signature block, so any change to the fee
wording meant six edits. Now the furniture is written once per language in
`blocks.py`, the numbered asks once per topic and language in `bodies.py`, and
`compose.py` puts them together.
"""

from .blocks import STRINGS, strings
from .bodies import BODIES, body
from .compose import render, render_bilingual
from .wave1 import LEGAL_SALIENCE, render_wave1_information

__all__ = [
    "STRINGS",
    "strings",
    "BODIES",
    "body",
    "render",
    "render_bilingual",
    "LEGAL_SALIENCE",
    "render_wave1_information",
]
