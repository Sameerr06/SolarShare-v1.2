import os

from app.integrations.electricity_dataset import (
    DERIVED_UNIT_DESCRIPTION,
    SOURCE_UNIT_DESCRIPTION,
    ElectricityDatasetSourceConfig,
    convert_to_energy_kwh,
    validate_and_convert,
)
from app.integrations.tsf_parser import parse_tsf

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_PATH = os.path.join(FIXTURE_DIR, "sample_electricity_hourly_fixture.tsf")
MISSING_FIXTURE_PATH = os.path.join(FIXTURE_DIR, "sample_electricity_hourly_missing_fixture.tsf")


def test_source_and_internal_unit_labels_are_locked_text():
    assert SOURCE_UNIT_DESCRIPTION == "Hourly average electricity demand in kW."
    assert DERIVED_UNIT_DESCRIPTION == "Hourly energy consumption in kWh."


def test_convert_to_energy_kwh_is_power_times_time():
    # Energy = Power x Time, interval_hours = 1.0 for this dataset.
    assert convert_to_energy_kwh(10.5, interval_hours=1.0) == 10.5
    assert convert_to_energy_kwh(0.0, interval_hours=1.0) == 0.0


def test_convert_to_energy_kwh_scales_with_interval_width():
    # Sanity check the formula isn't hardcoded to always return its input --
    # a different interval width must change the result.
    assert convert_to_energy_kwh(10.0, interval_hours=0.5) == 5.0
    assert convert_to_energy_kwh(10.0, interval_hours=2.0) == 20.0


def test_convert_to_energy_kwh_preserves_none_for_missing():
    assert convert_to_energy_kwh(None, interval_hours=1.0) is None


def test_validate_and_convert_on_fixture_all_valid():
    ds = parse_tsf(FIXTURE_PATH)
    report = validate_and_convert(ds, ElectricityDatasetSourceConfig())
    assert len(report.valid_series) == 12
    assert report.rejected_series == []
    assert report.total_records_negative_rejected == 0


def test_validate_and_convert_kwh_matches_kw_at_hourly_resolution():
    ds = parse_tsf(FIXTURE_PATH)
    report = validate_and_convert(ds, ElectricityDatasetSourceConfig())
    series = report.valid_series[0]
    for kw, kwh in zip(series.hourly_average_kw, series.energy_kwh):
        assert kw == kwh  # interval_hours == 1.0 for this dataset


def test_validate_and_convert_reconstructs_hourly_timestamps():
    ds = parse_tsf(FIXTURE_PATH)
    report = validate_and_convert(ds, ElectricityDatasetSourceConfig())
    series = report.valid_series[0]
    diffs = [
        (series.timestamps[i + 1] - series.timestamps[i]).total_seconds()
        for i in range(len(series.timestamps) - 1)
    ]
    assert all(d == 3600.0 for d in diffs)  # exactly 1 hour apart, every step


def test_validate_and_convert_handles_missing_markers():
    ds = parse_tsf(MISSING_FIXTURE_PATH)
    report = validate_and_convert(ds, ElectricityDatasetSourceConfig())
    assert len(report.valid_series) == 2
    assert report.total_records_missing_value == 3  # 2 in T1, 1 in T2

    t1 = next(s for s in report.valid_series if s.series_name == "T1")
    assert t1.hourly_average_kw == [10.5, None, 12.3, 0.0, 15.7, None]
    assert t1.energy_kwh == [10.5, None, 12.3, 0.0, 15.7, None]  # missing stays missing, not 0


def test_validate_and_convert_rejects_wrong_frequency():
    from app.integrations.electricity_dataset import ElectricityDatasetValidationError
    import io
    from app.integrations.tsf_parser import parse_tsf as _parse

    content = (
        "@relation test\n"
        "@attribute series_name string\n"
        "@attribute start_timestamp date\n"
        "@frequency weekly\n"
        "@missing false\n"
        "@equallength true\n"
        "@data\n"
        "T1:2012-01-01 00-00-00:1.0,2.0\n"
    )
    ds = _parse(io.StringIO(content))
    try:
        validate_and_convert(ds, ElectricityDatasetSourceConfig())
        assert False, "expected ElectricityDatasetValidationError"
    except ElectricityDatasetValidationError:
        pass


def test_negative_values_treated_as_missing_not_fabricated_zero():
    import io
    from app.integrations.tsf_parser import parse_tsf as _parse

    content = (
        "@relation test\n"
        "@attribute series_name string\n"
        "@attribute start_timestamp date\n"
        "@frequency hourly\n"
        "@missing false\n"
        "@equallength true\n"
        "@data\n"
        "T1:2012-01-01 00-00-00:10.0,-5.0,8.0\n"
    )
    ds = _parse(io.StringIO(content))
    report = validate_and_convert(ds, ElectricityDatasetSourceConfig())
    assert report.total_records_negative_rejected == 1
    series = report.valid_series[0]
    assert series.hourly_average_kw == [10.0, None, 8.0]


def test_source_config_carries_locked_provenance():
    cfg = ElectricityDatasetSourceConfig()
    assert cfg.source_doi == "10.5281/zenodo.4656140"
    assert "zenodo.org" in cfg.source_url
