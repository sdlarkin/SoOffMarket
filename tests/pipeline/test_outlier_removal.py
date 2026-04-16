"""Tests for remove_outliers."""

import pytest
from pipeline_common import remove_outliers


PRICE_KEY = "SALE1CONSD"
ACRES_KEY = "CALCACRES"


def _comp(price, acres=1.0):
    """Helper to build a comp dict."""
    return {PRICE_KEY: price, ACRES_KEY: acres}


# ---------------------------------------------------------------------------
# Basic IQR filtering
# ---------------------------------------------------------------------------

class TestIQRFiltering:
    """Standard IQR-based outlier removal on price."""

    def test_high_outlier_removed(self):
        """500K is a clear outlier in this set."""
        comps = [_comp(p) for p in [10000, 20000, 30000, 40000, 50000, 100000, 500000]]
        result = remove_outliers(comps, PRICE_KEY, ACRES_KEY, is_land=False)
        prices = [c[PRICE_KEY] for c in result]
        assert 500000 not in prices

    def test_normal_values_retained(self):
        """Values within IQR bounds and above $5K floor should be kept."""
        comps = [_comp(p) for p in [10000, 20000, 30000, 40000, 50000, 100000, 500000]]
        result = remove_outliers(comps, PRICE_KEY, ACRES_KEY, is_land=False)
        prices = [c[PRICE_KEY] for c in result]
        for v in [10000, 20000, 30000, 40000, 50000, 100000]:
            assert v in prices


# ---------------------------------------------------------------------------
# Floor enforcement ($5K minimum)
# ---------------------------------------------------------------------------

class TestFloorEnforcement:
    """Sales under $5,000 should be removed regardless of IQR."""

    def test_below_5k_removed(self):
        comps = [_comp(p) for p in [1000, 2000, 50000, 55000, 60000, 65000]]
        result = remove_outliers(comps, PRICE_KEY, ACRES_KEY, is_land=False)
        prices = [c[PRICE_KEY] for c in result]
        assert 1000 not in prices
        assert 2000 not in prices

    def test_above_5k_kept(self):
        comps = [_comp(p) for p in [1000, 2000, 50000, 55000, 60000, 65000]]
        result = remove_outliers(comps, PRICE_KEY, ACRES_KEY, is_land=False)
        prices = [c[PRICE_KEY] for c in result]
        assert 50000 in prices


# ---------------------------------------------------------------------------
# Land PPA (price per acre) cap
# ---------------------------------------------------------------------------

class TestLandPPACap:
    """With is_land=True, comps exceeding the PPA cap should be removed."""

    def test_ppa_cap_filters_expensive(self):
        """$200K on 0.5 acres = $400K/acre → exceeds 100K cap."""
        comps = [
            _comp(200000, acres=0.5),
            _comp(50000, acres=1.0),
            _comp(60000, acres=1.0),
            _comp(55000, acres=1.0),
            _comp(45000, acres=1.0),
        ]
        result = remove_outliers(
            comps, PRICE_KEY, ACRES_KEY,
            is_land=True, ppa_cap=100000,
        )
        prices = [c[PRICE_KEY] for c in result]
        assert 200000 not in prices

    def test_ppa_under_cap_kept(self):
        """$50K on 1 acre = $50K/acre → under 100K cap."""
        comps = [
            _comp(200000, acres=0.5),
            _comp(50000, acres=1.0),
            _comp(60000, acres=1.0),
            _comp(55000, acres=1.0),
            _comp(45000, acres=1.0),
        ]
        result = remove_outliers(
            comps, PRICE_KEY, ACRES_KEY,
            is_land=True, ppa_cap=100000,
        )
        prices = [c[PRICE_KEY] for c in result]
        assert 50000 in prices


# ---------------------------------------------------------------------------
# Land PPA floor
# ---------------------------------------------------------------------------

class TestLandPPAFloor:
    """With is_land=True, comps below the PPA floor should be removed."""

    def test_ppa_floor_filters_cheap(self):
        """$5K on 1 acre = $5K/acre → below 10K floor."""
        comps = [
            _comp(5000, acres=1.0),
            _comp(50000, acres=1.0),
            _comp(60000, acres=1.0),
            _comp(55000, acres=1.0),
            _comp(45000, acres=1.0),
        ]
        result = remove_outliers(
            comps, PRICE_KEY, ACRES_KEY,
            is_land=True, ppa_floor=10000,
        )
        prices = [c[PRICE_KEY] for c in result]
        assert 5000 not in prices


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Small lists and empty lists."""

    def test_fewer_than_4_comps_only_applies_floor(self):
        """With < 4 comps, IQR should be skipped; only $5K floor applies."""
        comps = [_comp(3000), _comp(50000), _comp(60000)]
        result = remove_outliers(comps, PRICE_KEY, ACRES_KEY, is_land=False)
        prices = [c[PRICE_KEY] for c in result]
        assert 3000 not in prices
        assert 50000 in prices
        assert 60000 in prices

    def test_empty_list(self):
        result = remove_outliers([], PRICE_KEY, ACRES_KEY, is_land=False)
        assert result == []

    def test_all_below_floor(self):
        comps = [_comp(1000), _comp(2000), _comp(3000)]
        result = remove_outliers(comps, PRICE_KEY, ACRES_KEY, is_land=False)
        assert result == []
