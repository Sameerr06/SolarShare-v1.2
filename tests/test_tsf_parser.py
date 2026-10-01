import io

import pytest

from app.integrations.tsf_parser import TsfParseError, parse_tsf


def _minimal_tsf(data_lines, missing="false", equallength="true"):
    header = (
        "# test fixture\n"
        "@relation test\n"
        "@attribute series_name string\n"
        "@attribute start_timestamp date\n"
        "@frequency hourly\n"
        "@horizon 24\n"
        f"@missing {missing}\n"
        f"@equallength {equallength}\n"
        "@data\n"
    )
    return header + "\n".join(data_lines) + "\n"


def test_parses_header_comments():
    content = _minimal_tsf(["T1:2012-01-01 00-00-00:1.0,2.0"])
    ds = parse_tsf(io.StringIO(content))
    assert ds.metadata.header_comments == ["test fixture"]


def test_parses_relation_and_frequency():
    content = _minimal_tsf(["T1:2012-01-01 00-00-00:1.0,2.0"])
    ds = parse_tsf(io.StringIO(content))
    assert ds.metadata.relation == "test"
    assert ds.metadata.frequency == "hourly"
    assert ds.metadata.horizon == 24


def test_missing_value_marker_becomes_none():
    content = _minimal_tsf(["T1:2012-01-01 00-00-00:1.0,?,3.0"], missing="true", equallength="true")
    ds = parse_tsf(io.StringIO(content))
    assert ds.series[0].values == [1.0, None, 3.0]


def test_multiple_series_parsed():
    content = _minimal_tsf([
        "T1:2012-01-01 00-00-00:1.0,2.0",
        "T2:2012-01-01 00-00-00:3.0,4.0",
    ])
    ds = parse_tsf(io.StringIO(content))
    assert len(ds.series) == 2
    assert ds.series[1].series_name == "T2"
    assert ds.series[1].values == [3.0, 4.0]


def test_duplicate_series_name_rejected():
    content = _minimal_tsf([
        "T1:2012-01-01 00-00-00:1.0,2.0",
        "T1:2012-01-01 00-00-00:3.0,4.0",
    ])
    with pytest.raises(TsfParseError):
        parse_tsf(io.StringIO(content))


def test_equallength_violation_rejected():
    content = _minimal_tsf([
        "T1:2012-01-01 00-00-00:1.0,2.0,3.0",
        "T2:2012-01-01 00-00-00:4.0,5.0",
    ], equallength="true")
    with pytest.raises(TsfParseError):
        parse_tsf(io.StringIO(content))


def test_non_numeric_value_rejected():
    content = _minimal_tsf(["T1:2012-01-01 00-00-00:1.0,notanumber,3.0"])
    with pytest.raises(TsfParseError):
        parse_tsf(io.StringIO(content))


def test_malformed_data_line_rejected():
    content = (
        "@relation test\n"
        "@attribute series_name string\n"
        "@attribute start_timestamp date\n"
        "@frequency hourly\n"
        "@missing false\n"
        "@equallength true\n"
        "@data\n"
        "this line has no colons at all\n"
    )
    with pytest.raises(TsfParseError):
        parse_tsf(io.StringIO(content))


def test_missing_required_metadata_rejected():
    content = (
        "@attribute series_name string\n"
        "@data\n"
        "T1:2012-01-01 00-00-00:1.0\n"
    )
    with pytest.raises(TsfParseError):
        parse_tsf(io.StringIO(content))


def test_no_data_section_rejected():
    content = (
        "@relation test\n"
        "@frequency hourly\n"
        "@missing false\n"
        "@equallength true\n"
    )
    with pytest.raises(TsfParseError):
        parse_tsf(io.StringIO(content))


def test_empty_series_values_allowed_as_empty_list():
    content = _minimal_tsf(["T1:2012-01-01 00-00-00:"], equallength="true")
    ds = parse_tsf(io.StringIO(content))
    assert ds.series[0].values == []
