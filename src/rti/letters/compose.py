"""Assemble a letter from shared blocks and a topic body.

`render` builds one letter in one language. `render_bilingual` builds the file
that is actually handed to a research assistant: the local-language application
first, because that is what gets pasted into the portal, with an English copy
below it so anyone reviewing the batch can read what was sent.
"""

from __future__ import annotations

import textwrap

from ..enums import LANGUAGE_NAMES, REVIEWED_LANGUAGES
from .blocks import DRAFT_BANNER, ENGLISH_COPY_HEADER, strings
from .bodies import BODIES, body

WIDTH = 78
_RULE = "=" * WIDTH


def _wrap(text: str, indent: str = "") -> str:
    return textwrap.fill(text, width=WIDTH, initial_indent=indent, subsequent_indent=indent)


def _numbered(items: tuple[str, ...], context: dict) -> str:
    out = []
    for n, item in enumerate(items, 1):
        marker = f"{n}. "
        out.append(
            textwrap.fill(
                item.format(**context),
                width=WIDTH,
                initial_indent=marker,
                subsequent_indent=" " * len(marker),
            )
        )
    return "\n\n".join(out)


def render(topic: str, language: str, context: dict) -> str:
    """One application, in one language.

    `context` supplies the authority, the dates, the filer, and the two numbers
    that used to be hardcoded in the letter text: `fee` and `statutory_days`.
    """
    if topic not in BODIES:
        raise KeyError(f"unknown topic {topic!r}; expected one of {sorted(BODIES)}")
    s = strings(language)
    b = body(topic, language)

    parts = [
        s["to_line"],
        _wrap(context["authority"]),
        "",
        f'{s["date_label"]}: {context["filing_date"]}',
        "",
        _wrap(f'{s["subject_label"]}: {s["subject"]}'),
        "",
        s["salutation"],
        "",
        _wrap(b["lead_in"].format(**context)),
        "",
        _numbered(b["items"], context),
        "",
        _wrap(s["fee_clause"].format(**context)),
        "",
        _wrap(s["transfer_clause"]),
        "",
        _wrap(s["clarify_clause"]),
        "",
        _wrap(s["deadline_clause"].format(**context)),
        "",
        s["thanks"],
        "",
        s["sign_off"],
        context["filer_name"],
        context["filer_address"],
        f'{s["phone_label"]}: {context["filer_phone"]}',
        f'{s["email_label"]}: {context["filer_email"]}',
    ]
    return "\n".join(parts).rstrip() + "\n"


def render_bilingual(topic: str, language: str, context: dict) -> str:
    """The file an RA works from: local-language application, English copy below.

    A language nobody has reviewed gets a banner telling the RA not to file it.
    English-language states get a single letter, since a second English copy
    would be the same text twice.
    """
    local = render(topic, language, context)
    if language == "en":
        return local

    sections = []
    if language not in REVIEWED_LANGUAGES:
        sections.append(
            DRAFT_BANNER.format(rule=_RULE, language=LANGUAGE_NAMES.get(language, language))
        )
        sections.append("")
    sections.append(local)
    sections.append(_RULE)
    sections.append(ENGLISH_COPY_HEADER)
    sections.append(_RULE)
    sections.append("")
    sections.append(render(topic, "en", context))
    return "\n".join(sections)
