"""Tests for build_where_clause."""

import pytest
from pipeline_common import build_where_clause


# ---------------------------------------------------------------------------
# Mock objects (stand-ins for Django models)
# ---------------------------------------------------------------------------

class MockCounty:
    def __init__(self, field_map=None):
        self.field_map = field_map or {
            "building_value": "BUILDVALUE",
            "calc_acres": "CALCACRES",
            "appraised_value": "APPVALUE",
        }


class MockBuyBox:
    def __init__(self, min_acres=0.3, max_price=80000, county=None):
        self.min_acres = min_acres
        self.max_price = max_price
        self.county = county or MockCounty()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildWhereClause:
    """build_where_clause should produce a SQL-style WHERE clause string."""

    def test_standard_buybox(self):
        bb = MockBuyBox(min_acres=0.3, max_price=80000)
        result = build_where_clause(bb)
        assert "BUILDVALUE = 0" in result
        assert "CALCACRES >= 0.3" in result
        assert "APPVALUE <= 80000" in result
        assert "APPVALUE > 0" in result

    def test_all_clauses_joined_with_and(self):
        bb = MockBuyBox()
        result = build_where_clause(bb)
        # Every clause should be separated by AND
        parts = result.split(" AND ")
        assert len(parts) >= 4

    def test_different_field_names(self):
        """Counties can have different field names in their GIS layer."""
        county = MockCounty(field_map={
            "building_value": "BLDGVAL",
            "calc_acres": "ACRES",
            "appraised_value": "APPR_VAL",
        })
        bb = MockBuyBox(min_acres=1.0, max_price=50000, county=county)
        result = build_where_clause(bb)
        assert "BLDGVAL = 0" in result
        assert "ACRES >= 1.0" in result
        assert "APPR_VAL <= 50000" in result
        assert "APPR_VAL > 0" in result

    def test_uses_exact_buybox_values(self):
        bb = MockBuyBox(min_acres=5.0, max_price=200000)
        result = build_where_clause(bb)
        assert "5.0" in result or "5" in result
        assert "200000" in result
