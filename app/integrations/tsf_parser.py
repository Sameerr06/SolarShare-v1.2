"""
Generic parser for the Monash Time Series Forecasting Archive ".tsf" file
format.

This format is used by the entire Monash TSF Archive, including the
"Electricity Hourly Dataset" (Zenodo DOI 10.5281/zenodo.4656140) that
SolarShare uses as its public tenant-load proxy dataset.

============================================================================
FORMAT VERIFICATION
============================================================================
This parser's understanding of the .tsf format was verified against a real,
official file from the Monash TSF Archive's own reference repository
(github.com/rakshitha123/TSForecasting, file tsf_data/sample.tsf — the
Ausgrid weekly dataset), not invented or guessed. That file was fetched
directly from GitHub during implementation and is checked into
tests/fixtures/real_monash_sample_ausgrid.tsf, where
test_tsf_parser_real_sample.py parses it and asserts against its actual
known structure.

IMPORTANT LIMITATION (documented, not hidden): the specific
electricity_hourly_dataset.tsf file itself (Zenodo DOI 10.5281/zenodo.4656140,
~36 MB) could not be downloaded in this implementation environment —
zenodo.org and huggingface.co are outside this sandbox's network allowlist.
This parser is therefore verified against the real .tsf *format* (via the
Ausgrid sample above) and exercised against a documented synthetic fixture
built to match the electricity dataset's known, cited metadata (321 series,
hourly frequency, 2012-2014, no missing values, equal length) — see
tests/fixtures/sample_electricity_hourly_fixture.tsf and its header comment
for exactly what is fixture vs. real. The parser code itself makes no
electricity-dataset-specific assumptions, so it will parse the real file
identically once it is acquired in an environment with Zenodo access.
============================================================================

Format summary (as verified):
    # optional free-text header comment lines, starting with '#'
    @relation <name>
    @attribute series_name string
    @attribute start_timestamp date
    @frequency <yearly|quarterly|monthly|weekly|daily|hourly|...>
    @horizon <int>
    @missing <true|false>
    @equallength <true|false>
    @data
    <series_name>:<start_timestamp>:<value1>,<value2>,...

Each @data line is colon-separated into (series_name, start_timestamp,
comma-separated values). Missing values within a series are represented as
'?' (per the Monash format specification); this parser converts '?' to
`None`, never to 0.0 — a missing reading is not the same as a zero reading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, TextIO, Union


class TsfParseError(Exception):
    """Raised for structurally invalid .tsf content."""


@dataclass(frozen=True)
class TsfMetadata:
    relation: str
    attributes: List[tuple]  # [(name, type), ...] e.g. [("series_name", "string"), ...]
    frequency: str
    horizon: Optional[int]
    missing: bool
    equallength: bool
    header_comments: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TsfSeries:
    series_name: str
    start_timestamp: datetime
    values: List[Optional[float]]  # None represents a '?' missing value


@dataclass(frozen=True)
class TsfDataset:
    metadata: TsfMetadata
    series: List[TsfSeries]


_TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H-%M-%S",  # observed in the real Ausgrid sample.tsf
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def _parse_timestamp(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise TsfParseError(f"Unrecognized start_timestamp format: {raw!r}")


def _parse_value(raw: str) -> Optional[float]:
    raw = raw.strip()
    if raw == "?":
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise TsfParseError(f"Non-numeric series value: {raw!r}") from exc


def parse_tsf(source: Union[str, TextIO]) -> TsfDataset:
    """
    Parse .tsf content from either a file path (str) or an already-open
    text stream, returning a fully-parsed `TsfDataset` with ALL series
    materialized in memory.

    For large files (e.g. the real ~8.4M-observation electricity dataset),
    prefer `parse_tsf_streaming()` below instead — this eager function is
    kept for the existing test suite and for small/medium files where
    holding everything in memory is not a concern.
    """
    if isinstance(source, str):
        with open(source, "r", encoding="utf-8") as fh:
            return _parse_tsf_lines(fh)
    return _parse_tsf_lines(source)


def _consume_header(fh: TextIO) -> TsfMetadata:
    """
    Read and parse only the header block (comments + @-directives) up
    through and including the `@data` line, leaving `fh`'s read position
    at the start of the first data line. Does not touch any data lines —
    cheap regardless of file size.
    """
    header_comments: List[str] = []
    relation: Optional[str] = None
    attributes: List[tuple] = []
    frequency: Optional[str] = None
    horizon: Optional[int] = None
    missing: Optional[bool] = None
    equallength: Optional[bool] = None
    in_data_section = False

    for raw_line in fh:
        line = raw_line.rstrip("\n").rstrip("\r")
        if not line:
            continue

        if line.startswith("#"):
            header_comments.append(line[1:].strip())
            continue
        if line.startswith("@relation"):
            relation = line.split(maxsplit=1)[1].strip()
            continue
        if line.startswith("@attribute"):
            parts = line.split()
            if len(parts) < 3:
                raise TsfParseError(f"Malformed @attribute line: {line!r}")
            attributes.append((parts[1], parts[2]))
            continue
        if line.startswith("@frequency"):
            frequency = line.split(maxsplit=1)[1].strip()
            continue
        if line.startswith("@horizon"):
            horizon = int(line.split(maxsplit=1)[1].strip())
            continue
        if line.startswith("@missing"):
            missing = line.split(maxsplit=1)[1].strip().lower() == "true"
            continue
        if line.startswith("@equallength"):
            equallength = line.split(maxsplit=1)[1].strip().lower() == "true"
            continue
        if line.startswith("@data"):
            in_data_section = True
            break
        raise TsfParseError(f"Unrecognized header line before @data: {line!r}")

    if relation is None or frequency is None or missing is None or equallength is None:
        raise TsfParseError(
            "Incomplete .tsf metadata: @relation, @frequency, @missing, and @equallength are all required."
        )
    if not in_data_section:
        raise TsfParseError("No @data section found in .tsf content.")

    return TsfMetadata(
        relation=relation,
        attributes=attributes,
        frequency=frequency,
        horizon=horizon,
        missing=missing,
        equallength=equallength,
        header_comments=header_comments,
    )


def _parse_data_line(line: str) -> TsfSeries:
    parts = line.split(":", 2)
    if len(parts) != 3:
        raise TsfParseError(f"Malformed data line (expected 3 colon-separated fields): {line!r}")
    series_name, ts_raw, values_raw = parts
    series_name = series_name.strip()
    if not series_name:
        raise TsfParseError(f"Empty series_name in data line: {line!r}")

    start_ts = _parse_timestamp(ts_raw)
    values = [_parse_value(v) for v in values_raw.split(",")] if values_raw.strip() else []
    return TsfSeries(series_name=series_name, start_timestamp=start_ts, values=values)


def _parse_tsf_lines(fh: TextIO) -> TsfDataset:
    metadata = _consume_header(fh)

    series_list: List[TsfSeries] = []
    for raw_line in fh:
        line = raw_line.rstrip("\n").rstrip("\r")
        if not line:
            continue
        series_list.append(_parse_data_line(line))

    # Duplicate series-name validation (a data-quality check, not just a
    # format check) — each series must appear exactly once.
    seen_names: Dict[str, int] = {}
    for s in series_list:
        seen_names[s.series_name] = seen_names.get(s.series_name, 0) + 1
    duplicates = [name for name, count in seen_names.items() if count > 1]
    if duplicates:
        raise TsfParseError(f"Duplicate series_name entries found: {duplicates}")

    # equallength validation, if the file claims it.
    if metadata.equallength and series_list:
        lengths = {len(s.values) for s in series_list}
        if len(lengths) > 1:
            raise TsfParseError(
                f"@equallength is true but series have differing lengths: {sorted(lengths)}"
            )

    return TsfDataset(metadata=metadata, series=series_list)


def parse_tsf_streaming(source: Union[str, TextIO]):
    """
    Parse .tsf content WITHOUT materializing all series in memory at once.

    Returns `(metadata, series_iterator)`. `metadata` is available
    immediately (the header block is small and read eagerly). The second
    element is a generator that yields one `TsfSeries` at a time as the
    file is read — at no point does this function hold more than one
    series' values in memory simultaneously (aside from the small
    bookkeeping needed for duplicate-name and equal-length validation).

    Equivalent validation to the eager `parse_tsf()`/`_parse_tsf_lines()`
    path (duplicate series names, @equallength consistency) is performed
    INCREMENTALLY as series are consumed, raising `TsfParseError` from
    within the generator at the point a violation is found, rather than
    only after the whole file has been read.

    If `source` is a file path (str), the file is opened here and closed
    automatically once the generator is exhausted or garbage-collected
    (via a try/finally in the generator body) — the caller does not need
    to manage the file handle.
    """
    if isinstance(source, str):
        fh = open(source, "r", encoding="utf-8")
        owns_file = True
    else:
        fh = source
        owns_file = False

    metadata = _consume_header(fh)

    def _series_generator():
        seen_names: Dict[str, int] = {}
        first_length: Optional[int] = None
        try:
            for raw_line in fh:
                line = raw_line.rstrip("\n").rstrip("\r")
                if not line:
                    continue
                series = _parse_data_line(line)

                if series.series_name in seen_names:
                    raise TsfParseError(f"Duplicate series_name entries found: [{series.series_name!r}]")
                seen_names[series.series_name] = 1

                if metadata.equallength:
                    if first_length is None:
                        first_length = len(series.values)
                    elif len(series.values) != first_length:
                        raise TsfParseError(
                            f"@equallength is true but series {series.series_name!r} has length "
                            f"{len(series.values)}, expected {first_length}"
                        )

                yield series
        finally:
            if owns_file:
                fh.close()

    return metadata, _series_generator()
