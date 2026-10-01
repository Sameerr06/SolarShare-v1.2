import pytest

from app.services.solar_generation import estimate_generation_kwh


class _FakePVConfig:
    """
    Minimal stand-in exposing the attributes the formula reads.

    MODEL B: `efficiency` is intentionally accepted/stored here (mirroring
    the real PVConfig) but is NOT read by estimate_generation_kwh — it's
    descriptive metadata only. See app/services/solar_generation.py.
    """
    def __init__(self, capacity_kw=500.0, efficiency=0.20, performance_ratio=0.80):
        self.capacity_kw = capacity_kw
        self.efficiency = efficiency  # metadata only, not used in the formula
        self.performance_ratio = performance_ratio


LOCKED_PV_CONFIG = _FakePVConfig(capacity_kw=500.0, efficiency=0.20, performance_ratio=0.80)


def test_full_stc_irradiance_gives_expected_generation():
    # MODEL B: at exactly 1000 W/m^2 (STC reference), ghi_kwh_per_m2 = 1.0.
    # estimated_kwh = 1.0 * 500 * 0.80 = 400.0  (efficiency NOT multiplied in)
    result = estimate_generation_kwh(1000.0, LOCKED_PV_CONFIG)
    assert result == pytest.approx(400.0)


def test_zero_irradiance_gives_zero_generation():
    result = estimate_generation_kwh(0.0, LOCKED_PV_CONFIG)
    assert result == 0.0


def test_half_stc_irradiance_gives_half_generation():
    # ghi_kwh_per_m2 = 0.5; estimated_kwh = 0.5 * 500 * 0.80 = 200.0
    result = estimate_generation_kwh(500.0, LOCKED_PV_CONFIG)
    assert result == pytest.approx(200.0)


def test_quarter_stc_irradiance_gives_quarter_generation():
    # ghi_kwh_per_m2 = 0.25; estimated_kwh = 0.25 * 500 * 0.80 = 100.0
    result = estimate_generation_kwh(250.0, LOCKED_PV_CONFIG)
    assert result == pytest.approx(100.0)


def test_typical_midday_irradiance():
    # A plausible midday Coimbatore GHI reading, e.g. 750 W/m^2
    # ghi_kwh_per_m2 = 0.75; estimated_kwh = 0.75 * 500 * 0.80 = 300.0
    result = estimate_generation_kwh(750.0, LOCKED_PV_CONFIG)
    assert result == pytest.approx(300.0)


def test_low_morning_irradiance():
    # A plausible early-morning/low-sun GHI reading, e.g. 100 W/m^2
    # ghi_kwh_per_m2 = 0.10; estimated_kwh = 0.10 * 500 * 0.80 = 40.0
    result = estimate_generation_kwh(100.0, LOCKED_PV_CONFIG)
    assert result == pytest.approx(40.0)


def test_generation_scales_proportionally_with_irradiance():
    # Model B is strictly linear in GHI: doubling irradiance should double
    # generation (all else held constant).
    low = estimate_generation_kwh(200.0, LOCKED_PV_CONFIG)
    high = estimate_generation_kwh(400.0, LOCKED_PV_CONFIG)
    assert high == pytest.approx(low * 2)


def test_negative_irradiance_rejected():
    with pytest.raises(ValueError):
        estimate_generation_kwh(-10.0, LOCKED_PV_CONFIG)


def test_formula_scales_linearly_with_capacity():
    small = _FakePVConfig(capacity_kw=100.0, efficiency=0.20, performance_ratio=0.80)
    large = _FakePVConfig(capacity_kw=500.0, efficiency=0.20, performance_ratio=0.80)
    small_result = estimate_generation_kwh(800.0, small)
    large_result = estimate_generation_kwh(800.0, large)
    assert large_result == pytest.approx(small_result * 5)


def test_efficiency_value_does_not_affect_generation_result():
    """
    MODEL B regression guard: changing `efficiency` on the config must NOT
    change the calculated generation. This is the explicit test that would
    catch a regression back to the old (double-counting) Model A behavior.
    """
    low_efficiency = _FakePVConfig(capacity_kw=500.0, efficiency=0.10, performance_ratio=0.80)
    high_efficiency = _FakePVConfig(capacity_kw=500.0, efficiency=0.35, performance_ratio=0.80)

    result_low = estimate_generation_kwh(1000.0, low_efficiency)
    result_high = estimate_generation_kwh(1000.0, high_efficiency)

    assert result_low == pytest.approx(400.0)
    assert result_high == pytest.approx(400.0)
    assert result_low == result_high
