import pytest

from app.integrations.nasa_power import (
    NasaPowerValidationError,
    parse_and_validate_response,
)

PARAMS = ["ALLSKY_SFC_SW_DWN", "T2M"]


def _valid_response():
    return {
        "properties": {
            "parameter": {
                "ALLSKY_SFC_SW_DWN": {"2024010100": 0.0, "2024010101": 250.5},
                "T2M": {"2024010100": 24.1, "2024010101": 24.5},
            }
        }
    }


def test_valid_response_parses_correctly():
    records = parse_and_validate_response(_valid_response(), expected_parameters=PARAMS)
    assert len(records) == 2
    assert records[0].timestamp.hour == 0
    assert records[0].values["ALLSKY_SFC_SW_DWN"] == 0.0
    assert records[1].values["ALLSKY_SFC_SW_DWN"] == 250.5
    assert records[1].values["T2M"] == 24.5


def test_timestamps_are_utc_aware():
    records = parse_and_validate_response(_valid_response(), expected_parameters=PARAMS)
    assert records[0].timestamp.tzinfo is not None


def test_records_sorted_chronologically():
    resp = _valid_response()
    # Deliberately reorder keys to check output is still sorted
    resp["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"] = {
        "2024010101": 250.5,
        "2024010100": 0.0,
    }
    resp["properties"]["parameter"]["T2M"] = {
        "2024010101": 24.5,
        "2024010100": 24.1,
    }
    records = parse_and_validate_response(resp, expected_parameters=PARAMS)
    assert [r.timestamp.hour for r in records] == [0, 1]


def test_missing_top_level_properties_rejected():
    with pytest.raises(NasaPowerValidationError):
        parse_and_validate_response({"foo": "bar"}, expected_parameters=PARAMS)


def test_missing_parameter_block_rejected():
    with pytest.raises(NasaPowerValidationError):
        parse_and_validate_response({"properties": {}}, expected_parameters=PARAMS)


def test_missing_requested_parameter_rejected():
    resp = _valid_response()
    del resp["properties"]["parameter"]["T2M"]
    with pytest.raises(NasaPowerValidationError):
        parse_and_validate_response(resp, expected_parameters=PARAMS)


def test_error_message_payload_rejected():
    resp = {"messages": ["Invalid latitude value"], "properties": {}}
    with pytest.raises(NasaPowerValidationError):
        parse_and_validate_response(resp, expected_parameters=PARAMS)


def test_non_numeric_value_rejected():
    resp = _valid_response()
    resp["properties"]["parameter"]["T2M"]["2024010100"] = "not-a-number"
    with pytest.raises(NasaPowerValidationError):
        parse_and_validate_response(resp, expected_parameters=PARAMS)


def test_unparseable_timestamp_rejected():
    resp = _valid_response()
    resp["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]["not-a-timestamp"] = 100.0
    with pytest.raises(NasaPowerValidationError):
        parse_and_validate_response(resp, expected_parameters=PARAMS)


def test_inconsistent_timestamp_sets_across_parameters_rejected():
    resp = _valid_response()
    resp["properties"]["parameter"]["T2M"]["2024010102"] = 25.0  # extra timestamp not in ALLSKY series
    with pytest.raises(NasaPowerValidationError):
        parse_and_validate_response(resp, expected_parameters=PARAMS)


def test_fill_value_converted_to_none():
    resp = _valid_response()
    resp["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]["2024010100"] = -999.0
    records = parse_and_validate_response(resp, expected_parameters=PARAMS, fill_value=-999.0)
    assert records[0].values["ALLSKY_SFC_SW_DWN"] is None


def test_zero_is_not_treated_as_fill_value():
    resp = _valid_response()
    records = parse_and_validate_response(resp, expected_parameters=PARAMS, fill_value=-999.0)
    # 0.0 GHI at hour 00:00 (nighttime) is a legitimate real reading, not missing data
    assert records[0].values["ALLSKY_SFC_SW_DWN"] == 0.0
