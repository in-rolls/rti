"""Every topic renders in every language, with no number hardcoded in the prose."""

from __future__ import annotations

import re

import pytest

from rti.enums import LANGUAGES, REVIEWED_LANGUAGES, TOPICS
from rti.letters import BODIES, render, render_bilingual
from rti.letters.blocks import STRINGS

CONTEXT = {
    "authority": "Zilla Panchayat, Belagavi, Karnataka",
    "period_start": "01-08-2025",
    "period_end": "31-07-2026",
    "attendance_date": "31-07-2026",
    "fy1": "2024-25",
    "fy2": "2025-26",
    "fee": 10,
    "statutory_days": 30,
    "filer_name": "Test Filer",
    "filer_address": "1 Test Road",
    "filer_phone": "+91 90000 00000",
    "filer_email": "test@example.org",
    "filing_date": "10-08-2026",
}

COMBOS = [(t, lang) for t in TOPICS for lang in LANGUAGES]


@pytest.mark.parametrize(("topic", "language"), COMBOS)
def test_every_combination_renders(topic, language):
    text = render(topic, language, CONTEXT)
    assert text.strip()
    assert "{" not in text and "}" not in text, "an unfilled placeholder survived"


@pytest.mark.parametrize(("topic", "language"), COMBOS)
def test_every_combination_carries_the_filer_and_the_asks(topic, language):
    text = render(topic, language, CONTEXT)
    assert CONTEXT["filer_name"] in text
    assert CONTEXT["filer_email"] in text
    expected = len(BODIES[topic][language]["items"]) if language in BODIES[topic] else 0
    if expected:
        assert re.search(rf"^{expected}\. ", text, re.M), "the last numbered ask is missing"


def test_every_language_defines_every_block():
    """A half-translated language would silently fall back mid-letter."""
    expected = set(STRINGS["en"])
    for language in LANGUAGES:
        assert set(STRINGS[language]) == expected, f"{language} is missing shared text"


def test_every_topic_is_translated_into_every_language():
    for topic in TOPICS:
        assert set(BODIES[topic]) == set(LANGUAGES), f"{topic} is not fully translated"


@pytest.mark.parametrize("language", LANGUAGES)
def test_fee_and_deadline_come_from_config_not_prose(language):
    """The old templates said "Rs. 10" and "30 days" in the text itself, so a
    state on a different fee or clock got a letter that contradicted the config."""
    context = {**CONTEXT, "fee": 20, "statutory_days": 45}
    text = render("rti_meta", language, context)
    assert "20" in text and "45" in text
    assert "Rs. 10" not in text


def test_unreviewed_languages_carry_a_hold_banner():
    text = render_bilingual("rti_meta", "kn", CONTEXT)
    assert "DO NOT FILE YET" in text
    assert "Kannada" in text


def test_reviewed_languages_do_not_carry_a_banner():
    text = render_bilingual("rti_meta", "hi", CONTEXT)
    assert "DO NOT FILE YET" not in text
    assert "hi" in REVIEWED_LANGUAGES


def test_bilingual_output_contains_both_languages():
    text = render_bilingual("rti_meta", "ta", CONTEXT)
    assert "ENGLISH COPY" in text
    assert "Respected Sir/Madam," in text, "the English copy is missing"
    assert "ஐயா/அம்மையீர்," in text, "the Tamil letter is missing"


def test_english_is_not_duplicated():
    text = render_bilingual("rti_meta", "en", CONTEXT)
    assert "ENGLISH COPY" not in text
    assert text.count("Respected Sir/Madam,") == 1


def test_unknown_topic_is_refused():
    with pytest.raises(KeyError):
        render("no_such_topic", "en", CONTEXT)


def test_lines_stay_within_a_pasteable_width():
    for topic, language in COMBOS:
        for line in render(topic, language, CONTEXT).splitlines():
            assert len(line) <= 90, f"{topic}/{language}: {line!r}"
