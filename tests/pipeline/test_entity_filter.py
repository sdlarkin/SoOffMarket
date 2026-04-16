"""Tests for is_excluded_entity."""

import pytest
from pipeline_common import is_excluded_entity


# ---------------------------------------------------------------------------
# Government entities
# ---------------------------------------------------------------------------

class TestGovernment:
    def test_city(self):
        assert is_excluded_entity("CITY OF CHATTANOOGA") is True

    def test_county(self):
        # "HAMILTON COUNTY" is county-specific, needs county_keywords
        assert is_excluded_entity("HAMILTON COUNTY GOVERNMENT", county_keywords=["HAMILTON COUNTY"]) is True
        # "COUNTY OF" is universal
        assert is_excluded_entity("COUNTY OF HAMILTON") is True

    def test_state(self):
        assert is_excluded_entity("STATE OF TENNESSEE") is True


# ---------------------------------------------------------------------------
# Religious organizations
# ---------------------------------------------------------------------------

class TestChurch:
    def test_baptist_church(self):
        assert is_excluded_entity("FIRST BAPTIST CHURCH") is True

    def test_church_of(self):
        assert is_excluded_entity("CHURCH OF GOD") is True


# ---------------------------------------------------------------------------
# HOAs
# ---------------------------------------------------------------------------

class TestHOA:
    def test_homeowners_assoc(self):
        assert is_excluded_entity("LAKEWOOD HOMEOWNERS ASSOC INC") is True

    def test_hoa_abbreviation(self):
        assert is_excluded_entity("RIVERFRONT HOA") is True


# ---------------------------------------------------------------------------
# LLCs and corporate entities
# ---------------------------------------------------------------------------

class TestLLC:
    def test_llc(self):
        assert is_excluded_entity("THRASHER PIKE LLC") is True

    def test_inc(self):
        assert is_excluded_entity("ACME HOLDINGS INC") is True


# ---------------------------------------------------------------------------
# Individuals (should NOT be excluded)
# ---------------------------------------------------------------------------

class TestIndividuals:
    def test_single_person(self):
        assert is_excluded_entity("SMITH JOHN W") is False

    def test_couple(self):
        assert is_excluded_entity("JONES ALAN R & HANNAH E") is False

    def test_simple_name(self):
        assert is_excluded_entity("WANG AMY") is False


# ---------------------------------------------------------------------------
# County-specific keywords
# ---------------------------------------------------------------------------

class TestCountyKeywords:
    def test_county_keyword_match(self):
        assert is_excluded_entity("CHATT CITY", county_keywords=["CHATT CITY"]) is True

    def test_county_keyword_no_match_without_list(self):
        """Without county_keywords, 'CHATT CITY' is not in the universal list."""
        assert is_excluded_entity("CHATT CITY") is False

    def test_county_keyword_no_match_different(self):
        assert is_excluded_entity("SMITH JOHN", county_keywords=["CHATT CITY"]) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string(self):
        assert is_excluded_entity("") is False

    def test_case_insensitive(self):
        assert is_excluded_entity("first baptist church") is True

    def test_none_county_keywords(self):
        assert is_excluded_entity("SMITH JOHN W", county_keywords=None) is False
