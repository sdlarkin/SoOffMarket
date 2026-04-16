"""Tests for compute_acres_from_rings."""

import pytest
from pipeline_common import compute_acres_from_rings


SQFT_PER_ACRE = 43560


# ---------------------------------------------------------------------------
# State-plane coordinate tests (units = feet, WKID != 4326)
# ---------------------------------------------------------------------------

class TestAcresStatePlane:
    """Rings in state-plane feet — straightforward area / 43560."""

    def test_100x100_square(self):
        ring = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
        result = compute_acres_from_rings([ring], wkid=2274)
        expected = 100 * 100 / SQFT_PER_ACRE  # 0.2296
        assert result == pytest.approx(expected, abs=0.001)

    def test_200x200_square(self):
        ring = [(0, 0), (200, 0), (200, 200), (0, 200), (0, 0)]
        result = compute_acres_from_rings([ring], wkid=2274)
        expected = 200 * 200 / SQFT_PER_ACRE  # 0.9183
        assert result == pytest.approx(expected, abs=0.001)

    def test_one_acre_square(self):
        """208.71 x 208.71 ft ≈ 1 acre."""
        side = 208.71
        ring = [(0, 0), (side, 0), (side, side), (0, side), (0, 0)]
        result = compute_acres_from_rings([ring], wkid=2274)
        assert result == pytest.approx(1.0, abs=0.01)


class TestAcresEmpty:
    """Empty or degenerate rings should return 0."""

    def test_empty_rings(self):
        result = compute_acres_from_rings([], wkid=2274)
        assert result == 0

    def test_empty_inner_ring(self):
        result = compute_acres_from_rings([[]], wkid=2274)
        assert result == 0


# ---------------------------------------------------------------------------
# WKID 4326 (lat/lon) tests
# ---------------------------------------------------------------------------

class TestAcresLatLon:
    """
    WKID 4326 means coordinates are in degrees.  The function should convert
    to approximate feet using lat_scale and lon_scale factors before computing
    area.  We test near latitude 35 N where:
        lat_scale ≈ 364,000 ft/degree
        lon_scale ≈ 298,000 ft/degree
    """

    def test_small_square_near_35n(self):
        """
        A tiny square in lat/lon: 0.001 deg x 0.001 deg near lat 35 N.
        Width  = 0.001 * 298,000 = 298 ft
        Height = 0.001 * 364,000 = 364 ft
        Area   = 298 * 364 = 108,472 sq ft ≈ 2.49 acres
        """
        lat0 = 35.0
        lon0 = -85.0
        d = 0.001
        ring = [
            (lon0, lat0),
            (lon0 + d, lat0),
            (lon0 + d, lat0 + d),
            (lon0, lat0 + d),
            (lon0, lat0),
        ]
        result = compute_acres_from_rings([ring], wkid=4326)
        # Allow generous tolerance because scale factors are approximate
        assert result == pytest.approx(2.49, abs=0.5)
