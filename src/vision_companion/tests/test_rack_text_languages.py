# =============================================================================
# URTC-VISION-TOOL - vision_companion tests: test_rack_text_languages.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The words of the rack check in the eight languages: the same placeholders in each, no stray spaces, the fallbacks of the lookup, and the register of each language."""
from __future__ import annotations

import re

import pytest

from vision_companion import rack_text

PLACEHOLDER = re.compile(r"\{(\w*)\}")


@pytest.mark.parametrize("lang", rack_text.LANGUAGES)
def test_every_text_has_the_same_placeholders_as_the_english_one(lang):
    for key in rack_text.KEYS:
        assert PLACEHOLDER.findall(rack_text.TEXTS[lang][key]) == PLACEHOLDER.findall(rack_text.TEXTS["en"][key]), (lang, key)


@pytest.mark.parametrize("lang", rack_text.LANGUAGES)
def test_no_text_starts_or_ends_with_a_space_or_holds_a_line_break(lang):
    for key in rack_text.KEYS:
        value = rack_text.TEXTS[lang][key]
        assert value == value.strip() and "\n" not in value and "  " not in value, (lang, key)


@pytest.mark.parametrize("lang", rack_text.LANGUAGES)
def test_every_text_can_be_formatted_with_the_values_of_the_check(lang):
    for key in rack_text.KEYS:
        assert "{" not in rack_text.text(key, lang, s="12.5") and "}" not in rack_text.text(key, lang, s="12.5")


def test_the_tables_hold_exactly_the_languages_and_the_keys_that_are_declared():
    assert set(rack_text.TEXTS) == set(rack_text.LANGUAGES)
    assert len(set(rack_text.KEYS)) == len(rack_text.KEYS)


def test_an_unknown_language_gives_the_english_words_and_an_unknown_key_gives_the_key():
    for lang in ("xx", "", "EN", "english"):
        assert rack_text.text("heating", lang) == "heating"
    assert rack_text.text("no_such_key", "de") == "no_such_key"
    assert rack_text.text("no_such_key", "xx") == "no_such_key"


def test_a_value_that_is_not_used_is_ignored_and_a_missing_one_is_an_error():
    assert rack_text.text("heating", "en", s="1", other="x") == "heating"
    with pytest.raises(KeyError):
        rack_text.text("reached_after", "en")


def test_the_number_is_put_where_each_language_wants_it():
    assert rack_text.text("reached_after", "en", s="4.0") == "reached after 4.0 s"
    assert rack_text.text("reached_after", "ja", s="4.0") == "4.0 秒で到達"
    assert rack_text.text("reached_after", "zh", s="4.0") == "4.0 秒后达到"


@pytest.mark.parametrize("lang, forbidden", [("de", r"\b(du|dein\w*|dir|dich)\b"), ("fr", r"\b(tu|ton|ta|tes|toi)\b"), ("pt", r"\b(tu|teu|tua)\b"), ("zh", "您")])
def test_no_text_slips_into_another_register(lang, forbidden):
    pattern = re.compile(forbidden)
    assert [key for key in rack_text.KEYS if pattern.search(rack_text.TEXTS[lang][key])] == []


def test_a_fault_is_written_in_capitals_where_the_language_has_capitals():
    for lang in ("en", "es", "de", "fr", "it", "pt"):
        word = rack_text.TEXTS[lang]["fault"]
        assert word == word.upper(), lang


def test_the_texts_of_the_languages_are_not_all_the_english_ones():
    english = rack_text.TEXTS["en"]
    for lang in rack_text.LANGUAGES:
        if lang == "en":
            continue
        same = [key for key in rack_text.KEYS if rack_text.TEXTS[lang][key] == english[key]]
        assert len(same) <= 3, (lang, same)      # a few words (slot, no) are the same in some languages
