"""Tests for parse_owner_name and parse_address."""

import pytest
from pipeline_common import parse_owner_name, parse_address


# ===========================================================================
# parse_owner_name
# ===========================================================================

class TestParseOwnerName:
    """
    Expected format: "LAST FIRST MIDDLE ..." → (first, last).
    For couples ("& SECOND"), take first person only.
    """

    def test_standard_name(self):
        first, last = parse_owner_name("SMITH JOHN W")
        assert first == "JOHN"
        assert last == "SMITH"

    def test_couple_takes_first_person(self):
        first, last = parse_owner_name("BROOME BRADLEY MATTHEW & NINA")
        assert first == "BRADLEY"
        assert last == "BROOME"

    def test_two_word_last_name(self):
        """Two-word last names split on first space — known limitation."""
        first, last = parse_owner_name("MC KAMEY ALISA LOVE")
        assert first == "KAMEY"
        assert last == "MC"

    def test_simple_two_part(self):
        first, last = parse_owner_name("WANG AMY")
        assert first == "AMY"
        assert last == "WANG"

    def test_empty_string(self):
        first, last = parse_owner_name("")
        assert first == ""
        assert last == ""

    def test_single_word(self):
        first, last = parse_owner_name("SMITH")
        assert first == ""
        assert last == "SMITH"


# ===========================================================================
# parse_address
# ===========================================================================

class TestParseAddress:
    """
    Input:  "STREET, CITY, STATE ZIP"
    Output: dict with keys street, city, state, zip.
    """

    def test_standard_address(self):
        result = parse_address("377 HENSON GAP RD, SODDY DAISY, TN 37379")
        assert result["street"] == "377 HENSON GAP RD"
        assert result["city"] == "SODDY DAISY"
        assert result["state"] == "TN"
        assert result["zip"] == "37379"

    def test_po_box(self):
        result = parse_address("PO BOX 7, OOLTEWAH, TN 37363")
        assert result["street"] == "PO BOX 7"
        assert result["city"] == "OOLTEWAH"
        assert result["state"] == "TN"
        assert result["zip"] == "37363"

    def test_another_address(self):
        result = parse_address("5615 PEARL ST, OOLTEWAH, TN 37363")
        assert result["street"] == "5615 PEARL ST"
        assert result["city"] == "OOLTEWAH"
        assert result["state"] == "TN"
        assert result["zip"] == "37363"

    def test_empty_string(self):
        result = parse_address("")
        assert result["street"] == ""
        assert result["city"] == ""
        assert result["state"] == ""
        assert result["zip"] == ""
