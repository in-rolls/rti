"""Identifiers must be stable across runs and unique across batches."""

from __future__ import annotations

from rti.ids import (
    application_id,
    authority_id,
    crawled_authority_id,
    next_sequence,
    norm,
    parse_application_id,
    state_code,
)


def test_authority_id_ignores_whitespace_and_case():
    a = authority_id("Karnataka", "Zilla  Panchayat Belagavi", "Belagavi", "")
    b = authority_id("karnataka", "zilla panchayat belagavi ", " Belagavi", "")
    assert a == b


def test_authority_id_separates_different_offices():
    belagavi = authority_id("Karnataka", "Zilla Panchayat", "Belagavi", "")
    bidar = authority_id("Karnataka", "Zilla Panchayat", "Bidar", "")
    assert belagavi != bidar


def test_flat_collisions_are_disambiguated_without_changing_the_first_id():
    first = authority_id("Telangana", "Same office", "Same district", "")
    explicit_first = authority_id("Telangana", "Same office", "Same district", "", occurrence=1)
    second = authority_id("Telangana", "Same office", "Same district", "", occurrence=2)
    assert first == explicit_first
    assert second != first


def test_crawled_authority_id_is_the_namespaced_node_id():
    assert crawled_authority_id("Tamil Nadu", "ABC123") == "TN-abc123"


def test_state_codes_match_the_existing_log():
    # The legacy evidence log already used these; changing them would orphan it.
    assert state_code("Karnataka") == "KA"
    assert state_code("Telangana") == "TG"
    assert state_code("Delhi") == "DL"


def test_unlisted_state_still_gets_a_code():
    assert state_code("Some New State") == "SO"


def test_application_ids_are_short_and_readable():
    assert application_id("KA", 14) == "KA-014"
    assert parse_application_id("KA-014") == ("KA", 14)
    assert parse_application_id("not an id") is None


def test_sequence_continues_past_existing_ids():
    """A second batch must not reissue an identifier the first batch used."""
    existing = {"KA-001", "KA-014", "DL-003"}
    assert next_sequence(existing, "KA") == 15
    assert next_sequence(existing, "DL") == 4
    assert next_sequence(existing, "TN") == 1


def test_norm_collapses_whitespace():
    assert norm("  a   b \n c ") == "a b c"
    assert norm(None) == ""
