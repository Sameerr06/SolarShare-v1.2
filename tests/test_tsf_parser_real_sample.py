"""
Tests for app/integrations/tsf_parser.py against a REAL, official Monash
TSF Archive file (tests/fixtures/real_monash_sample_ausgrid.tsf), fetched
directly from github.com/rakshitha123/TSForecasting during implementation.

This is not the electricity dataset itself (that specific file could not
be downloaded in this environment — see module docstrings), but it is a
genuine file from the same archive using the identical .tsf format, so it
validates the parser's understanding of the real format rather than a
guessed one.
"""

import os

from app.integrations.tsf_parser import TsfParseError, parse_tsf

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REAL_SAMPLE_PATH = os.path.join(FIXTURE_DIR, "real_monash_sample_ausgrid.tsf")


def test_real_sample_parses_without_error():
    ds = parse_tsf(REAL_SAMPLE_PATH)
    assert ds is not None


def test_real_sample_metadata_matches_known_header():
    ds = parse_tsf(REAL_SAMPLE_PATH)
    assert ds.metadata.relation == "Ausgrid"
    assert ds.metadata.frequency == "weekly"
    assert ds.metadata.horizon == 8
    assert ds.metadata.missing is False
    assert ds.metadata.equallength is True
    assert ("series_name", "string") in ds.metadata.attributes
    assert ("start_timestamp", "date") in ds.metadata.attributes


def test_real_sample_series_count_matches_header_claim():
    # The file's own header comment states "299 weekly series".
    ds = parse_tsf(REAL_SAMPLE_PATH)
    assert len(ds.series) == 299


def test_real_sample_first_series_values_match_raw_file():
    ds = parse_tsf(REAL_SAMPLE_PATH)
    first = ds.series[0]
    assert first.series_name == "T1"
    # First 5 values as they literally appear in the raw file after "T1:2010-07-01 00-30-00:"
    assert first.values[:5] == [207.06, 195.618, 173.042, 126.198, 132.969]


def test_real_sample_start_timestamp_parsed_correctly():
    ds = parse_tsf(REAL_SAMPLE_PATH)
    assert ds.series[0].start_timestamp.year == 2010
    assert ds.series[0].start_timestamp.month == 7
    assert ds.series[0].start_timestamp.day == 1


def test_real_sample_equallength_actually_holds():
    ds = parse_tsf(REAL_SAMPLE_PATH)
    lengths = {len(s.values) for s in ds.series}
    assert len(lengths) == 1  # @equallength true is honestly reflected in the data


def test_real_sample_no_duplicate_series_names():
    ds = parse_tsf(REAL_SAMPLE_PATH)
    names = [s.series_name for s in ds.series]
    assert len(names) == len(set(names))
