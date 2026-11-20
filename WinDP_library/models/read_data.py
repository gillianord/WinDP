#!/usr/bin/env python
# coding: utf-8

import os
import unicodedata
from datetime import datetime

import pandas as pd


def _parse_timestamps(values, date_format, *, strict=False):
    """Parse a timestamp column that may contain strings or Excel datetimes.

    When ``strict`` is True, string timestamps must match ``date_format`` exactly
    (used for tab-delimited text files). Otherwise a pandas inference fallback
    is allowed (useful for Excel string cells).
    """
    date_obj = []
    for value in values:
        if pd.isna(value):
            raise ValueError("Timestamp column contains missing values.")
        if isinstance(value, datetime):
            date_obj.append(
                value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
            )
            continue
        if isinstance(value, pd.Timestamp):
            date_obj.append(value.to_pydatetime())
            continue
        text = str(value).strip()
        try:
            date_obj.append(datetime.strptime(text, date_format))
        except ValueError:
            if strict:
                raise ValueError(
                    f"Timestamp '{text}' does not match format '{date_format}'."
                ) from None
            parsed = pd.to_datetime(text, dayfirst=False, errors="raise")
            date_obj.append(parsed.to_pydatetime())
    return date_obj


def detect_time_step(index):
    """
    Infer the dominant sampling interval from a DatetimeIndex.

    Uses the median positive gap between consecutive timestamps so occasional
    missing records do not inflate the detected step.
    """
    if not isinstance(index, pd.DatetimeIndex):
        index = pd.DatetimeIndex(pd.to_datetime(index))
    if len(index) < 2:
        return pd.Timedelta(minutes=10)
    diffs = pd.Series(index).diff().dropna()
    diffs = diffs[diffs > pd.Timedelta(0)]
    if diffs.empty:
        return pd.Timedelta(minutes=10)
    step = diffs.median()
    # Snap sub-second jitter to whole seconds when the series is second-aligned.
    if step >= pd.Timedelta(seconds=1):
        step = pd.Timedelta(seconds=max(1, int(round(step.total_seconds()))))
    return step


def ensure_regular_frequency(df):
    """
    Reindex onto a regular timeline at the detected sampling interval.

    Duplicates are dropped and missing intervals between the first and last
    timestamp are inserted as NaN rows.
    """
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="first")]
    if len(out) < 2:
        return out
    step = detect_time_step(out.index)
    full_index = pd.date_range(start=out.index[0], end=out.index[-1], freq=step)
    return out.reindex(full_index)


# Backwards-compatible alias used by older call sites / notebooks.
ensure_ten_minute_frequency = ensure_regular_frequency


def _fold_header(text):
    """Lowercase a header and strip accents so Spanish labels still match."""
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in folded)


def _header_compact(text):
    """Folded header with spaces removed for token checks like WD / WS / WS_max."""
    return "".join(_fold_header(text).split())


def _is_gust_header(column):
    """True when a header looks like wind gust (optional column)."""
    folded = _fold_header(column)
    compact = _header_compact(column)
    return (
        "gust" in folded
        or "racha" in folded
        or "rafagas" in folded
        or "ws_max" in compact
        or compact.endswith("wsmax")
        or compact == "wsmax"
    )


def _is_direction_header(column):
    """True when a header looks like wind direction (dir / WD / °)."""
    folded = _fold_header(column)
    compact = _header_compact(column)
    if "dir" in folded or "wd" in compact:
        return True
    raw = str(column)
    raw_fold = raw.casefold()
    # Match a bare degree symbol, but skip temperature-style ``°C`` headers.
    if "°" not in raw and "º" not in raw:
        return False
    if "°c" in raw_fold or "ºc" in raw_fold or "temp" in folded:
        return False
    return True


def _is_speed_header(column):
    """True when a header looks like mean wind speed (Speed / Vel / m/s / WS)."""
    if _is_gust_header(column):
        return False
    raw = str(column).casefold()
    folded = _fold_header(column)
    compact = _header_compact(column)
    if "speed" in folded or "vel" in folded:
        return True
    if "m/s" in raw or " m s" in f" {folded} ":
        # Avoid treating direction columns that only carry a degree symbol as speed.
        if "dir" in folded or "wd" in compact:
            return False
        return True
    # Whole-token / prefix WS (WS, WS_ms_Avg) but not WS_max (handled as gust).
    return compact == "ws" or (
        compact.startswith("ws") and not compact.startswith("wsmax")
    )


def _is_strong_direction_header(column):
    """Direction match via ``dir`` / ``WD`` (preferred over a bare ``°``)."""
    folded = _fold_header(column)
    compact = _header_compact(column)
    return "dir" in folded or "wd" in compact


def _find_wind_columns(columns, *, skip=()):
    """
    Locate direction / speed / optional gust columns by flexible header matching.

    Direction: label contains ``dir`` / ``WD`` / ``°``.
    Speed: label contains ``Speed`` / ``Vel`` / ``m/s`` / ``WS``.
    Gust (optional): label contains ``Gust`` / ``Racha`` / ``WS_max``.
    """
    candidates = [column for column in columns if column not in skip]
    gust = next((column for column in candidates if _is_gust_header(column)), None)
    remaining = [column for column in candidates if column != gust]
    direction = next(
        (column for column in remaining if _is_strong_direction_header(column)), None
    )
    if direction is None:
        direction = next(
            (column for column in remaining if _is_direction_header(column)), None
        )
    remaining = [column for column in remaining if column != direction]
    speed = next((column for column in remaining if _is_speed_header(column)), None)
    return direction, speed, gust


def _excel_wind_frame(df, date_format, *, strict_timestamps=False):
    """Map a wind sheet onto WD / WS / optional WS_max columns.

    Column labels are matched flexibly (English / Spanish / short codes), e.g.
    ``Direction (°)``, ``Dir. Media [°]``, ``WD`` for direction; ``Speed (m/s)``,
    ``Vel. media``, ``WS`` for speed; ``Gust``, ``Racha``, ``WS_max`` for gust.
    Gust is optional when that column is absent.
    """
    timestamp_column = df.columns[0]
    direction_col, speed_col, gust_col = _find_wind_columns(
        df.columns, skip=(timestamp_column,)
    )
    missing = []
    if direction_col is None:
        missing.append("direction (label containing dir / WD / °)")
    if speed_col is None:
        missing.append("speed (label containing Speed / Vel / m/s / WS)")
    if missing:
        available = ", ".join(str(name) for name in df.columns)
        raise ValueError(
            "Excel sheet is missing required wind column(s): "
            + ", ".join(missing)
            + f". Found headers: {available}."
        )

    timestamps = _parse_timestamps(
        df.iloc[:, 0], date_format, strict=strict_timestamps
    )
    frame = {
        "WD": pd.to_numeric(df[direction_col], errors="coerce").to_numpy(),
        "WS": pd.to_numeric(df[speed_col], errors="coerce").to_numpy(),
    }
    if gust_col is not None:
        frame["WS_max"] = pd.to_numeric(df[gust_col], errors="coerce").to_numpy()
    out = pd.DataFrame(frame, index=timestamps)
    return out


def _null_zero_speed_and_gust(df):
    """Set WD / WS / WS_max to NaN where both wind speed and gust are 0."""
    if "WS" not in df.columns or "WS_max" not in df.columns:
        return df
    ws = pd.to_numeric(df["WS"], errors="coerce")
    gust = pd.to_numeric(df["WS_max"], errors="coerce")
    calm = (ws == 0) & (gust == 0)
    if not calm.any():
        return df
    out = df.copy()
    out.loc[calm, ["WD", "WS", "WS_max"]] = float("nan")
    return out


def read_wind_data(path, filename, date_format="%Y-%m-%d %H:%M:%S", header=0):
    """
    Reads wind direction and velocity from a tab-delimited text file or Excel workbook.

    Column A is the timestamp. Remaining headers are matched flexibly:
    - Direction: label contains ``dir`` / ``WD`` / ``°``
    - Speed: label contains ``Speed`` / ``Vel`` / ``m/s`` / ``WS``
    - Gust (optional): label contains ``Gust`` / ``Racha`` / ``WS_max``

    Rows where both wind speed and gust are 0 have WD, WS, and WS_max set to NaN.

    Default date_format = '%Y-%m-%d %H:%M:%S' (used for string timestamps).
    """
    filepath = os.path.join(path, filename)
    extension = os.path.splitext(filename)[1].lower()

    if extension in {".xlsx", ".xls", ".xlsm"}:
        df = pd.read_excel(filepath, header=header)
        return _null_zero_speed_and_gust(_excel_wind_frame(df, date_format))

    df = pd.read_csv(filepath, header=header, sep="\t", engine="python")
    return _null_zero_speed_and_gust(
        _excel_wind_frame(df, date_format, strict_timestamps=True)
    )


def _resolve_sheet_name(sheet_lookup, *candidates):
    """Return the workbook sheet matching the first known candidate name."""
    for candidate in candidates:
        key = candidate.casefold()
        if key in sheet_lookup:
            return sheet_lookup[key]
    return None


def read_processed_export(
    path,
    filename,
    date_format="%Y-%m-%d %H:%M:%S",
    processed_sheet="processed_data",
    deleted_sheet="deleted_data",
    direction_correction_sheet="direction_corrections",
    magnetic_correction_sheet="magnetic_correction",
    preprocessed_sheet="preprocessed_data",
    header=0,
):
    """
    Load a workbook written by ``export_processed_data``.

    Sheet names default to the current English export labels and also accept the
    legacy Spanish names (``Datos_procesados``, ``Datos_eliminados``,
    ``Correccion_direccion``).

    Returns
    -------
    data : pandas.DataFrame
        Rows from the processed sheet (WD / WS / WS_max).
    deleted : pandas.DataFrame
        Rows from the deleted sheet with WD / WS / WS_max and a ``Notes``
        column. Empty when that sheet is absent.
    direction_corrections : pandas.DataFrame
        Rows from the direction-corrections sheet when present; otherwise empty
        with the expected columns.
    magnetic_correction : pandas.DataFrame
        Rows from ``magnetic_correction`` when present (original direction and
        declination); otherwise empty with the expected columns.
    preprocessed : pandas.DataFrame
        Rows from ``preprocessed_data`` when present; otherwise empty with the
        expected wind columns.
    """
    filepath = os.path.join(path, filename)
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".xlsx", ".xls", ".xlsm"}:
        raise ValueError("Processed data must be an Excel workbook (.xlsx).")

    workbook = pd.ExcelFile(filepath)
    sheet_lookup = {name.casefold(): name for name in workbook.sheet_names}
    processed_name = _resolve_sheet_name(
        sheet_lookup, processed_sheet, "Datos_procesados"
    )
    if processed_name is None:
        raise ValueError(
            f"Workbook is missing required sheet '{processed_sheet}'."
        )

    data = _excel_wind_frame(
        pd.read_excel(workbook, sheet_name=processed_name, header=header),
        date_format,
    )

    preprocessed_name = _resolve_sheet_name(
        sheet_lookup, preprocessed_sheet, "Datos_Preprocesados"
    )
    if preprocessed_name is None:
        preprocessed = pd.DataFrame(columns=["WD", "WS", "WS_max"])
        preprocessed.index = pd.DatetimeIndex([], name="Timestamp")
    else:
        preprocessed = _excel_wind_frame(
            pd.read_excel(
                workbook, sheet_name=preprocessed_name, header=header
            ),
            date_format,
        )

    deleted_name = _resolve_sheet_name(
        sheet_lookup, deleted_sheet, "Datos_eliminados"
    )
    if deleted_name is None:
        deleted = pd.DataFrame(columns=["WD", "WS", "WS_max", "Notes"])
        deleted.index = pd.DatetimeIndex([], name="Timestamp")
    else:
        deleted_raw = pd.read_excel(
            workbook, sheet_name=deleted_name, header=header
        )
        if deleted_raw.empty:
            deleted = pd.DataFrame(columns=["WD", "WS", "WS_max", "Notes"])
            deleted.index = pd.DatetimeIndex([], name="Timestamp")
        else:
            deleted = _excel_wind_frame(deleted_raw, date_format)
            if "Notas" in deleted_raw.columns:
                notes = deleted_raw["Notas"]
            elif "Notes" in deleted_raw.columns:
                notes = deleted_raw["Notes"]
            else:
                notes = pd.Series("", index=deleted_raw.index)
            deleted = deleted.copy()
            deleted["Notes"] = [
                "" if pd.isna(value) else str(value).strip() for value in notes
            ]

    corr_columns = [
        "Correct start",
        "Correct end",
        "Incorrect start",
        "Incorrect end",
        "Rotation [°]",
    ]
    corr_name = _resolve_sheet_name(
        sheet_lookup,
        direction_correction_sheet,
        "Correccion_direccion",
    )
    if corr_name is None:
        direction_corrections = pd.DataFrame(columns=corr_columns)
    else:
        direction_corrections = pd.read_excel(
            workbook, sheet_name=corr_name, header=header
        )
        rename = {}
        for column in direction_corrections.columns:
            key = str(column).strip().casefold()
            if key in {"correct start", "inicio correcto"}:
                rename[column] = "Correct start"
            elif key in {"correct end", "fin correcto"}:
                rename[column] = "Correct end"
            elif key in {"incorrect start", "inicio incorrecto"}:
                rename[column] = "Incorrect start"
            elif key in {"incorrect end", "fin incorrecto"}:
                rename[column] = "Incorrect end"
            elif key in {"rotation [°]", "rotation", "rotacion [°]", "rotacion"}:
                rename[column] = "Rotation [°]"
        direction_corrections = direction_corrections.rename(columns=rename)
        for column in corr_columns:
            if column not in direction_corrections.columns:
                direction_corrections[column] = pd.NA
        direction_corrections = direction_corrections.loc[:, corr_columns].copy()

    magnetic_columns = ["Original Direction (°)", "Declination (°)"]
    magnetic_name = _resolve_sheet_name(
        sheet_lookup, magnetic_correction_sheet
    )
    if magnetic_name is None:
        magnetic_correction = pd.DataFrame(columns=magnetic_columns)
        magnetic_correction.index = pd.DatetimeIndex([], name="Timestamp")
    else:
        magnetic_raw = pd.read_excel(
            workbook, sheet_name=magnetic_name, header=header
        )
        if magnetic_raw.empty:
            magnetic_correction = pd.DataFrame(columns=magnetic_columns)
            magnetic_correction.index = pd.DatetimeIndex([], name="Timestamp")
        else:
            rename = {}
            for column in magnetic_raw.columns:
                key = str(column).strip().casefold()
                if key in {
                    "original direction (°)",
                    "original direction",
                    "original wd",
                }:
                    rename[column] = "Original Direction (°)"
                elif key in {"declination (°)", "declination"}:
                    rename[column] = "Declination (°)"
            magnetic_frame = magnetic_raw.rename(columns=rename)
            for column in magnetic_columns:
                if column not in magnetic_frame.columns:
                    raise ValueError(
                        "magnetic_correction sheet is missing required "
                        f"column '{column}'."
                    )
            timestamps = _parse_timestamps(magnetic_raw.iloc[:, 0], date_format)
            magnetic_correction = magnetic_frame.loc[:, magnetic_columns].copy()
            magnetic_correction["Original Direction (°)"] = pd.to_numeric(
                magnetic_correction["Original Direction (°)"], errors="coerce"
            )
            magnetic_correction["Declination (°)"] = pd.to_numeric(
                magnetic_correction["Declination (°)"], errors="coerce"
            )
            magnetic_correction.index = pd.DatetimeIndex(timestamps, name="Timestamp")

    return data, deleted, direction_corrections, magnetic_correction, preprocessed


RAW_FORMAT_DATE_DEFAULTS = {
    "excel": "%Y-%m-%d %H:%M:%S",
    "tab": "%Y-%m-%d %H:%M:%S",
    "campbell": "%Y-%m-%d %H:%M:%S",
    "hobo": "%m/%d/%y %I:%M:%S %p",
}

# HOBOware timestamp patterns vary by language / 12- vs 24-hour clock.
HOBO_DATE_FORMATS = (
    "%m/%d/%y %I:%M:%S %p",
    "%d/%m/%y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%y %H:%M:%S",
    "%d/%m/%y %I:%M:%S %p",
    "%m/%d/%Y %I:%M:%S %p",
)


def detect_raw_wind_format(filepath):
    """
    Detect the raw wind file layout.

    Returns one of ``\"excel\"``, ``\"campbell\"``, ``\"hobo\"``, or ``\"tab\"``.
    Campbell TOA5 is identified from the first line (even when the extension is
    ``.csv``). Plain ``.csv`` files are treated as HOBO exports.
    """
    extension = os.path.splitext(filepath)[1].lower()
    if extension in {".xlsx", ".xls", ".xlsm"}:
        return "excel"

    with open(filepath, "r", encoding="utf-8", errors="replace") as handle:
        first_line = handle.readline().lstrip("\ufeff").strip()

    first_token = first_line.lstrip('"').split(",", 1)[0].strip().strip('"')
    if first_token.upper() == "TOA5":
        return "campbell"
    if extension == ".csv":
        return "hobo"
    return "tab"


def read_raw_wind(path, filename, date_format=None, header=0, raw_format=None):
    """
    Load a raw wind file, auto-detecting HOBO / Campbell / Excel / tab text.

    When ``date_format`` is omitted, a format-specific default is used.
    """
    filepath = os.path.join(path, filename)
    fmt = raw_format or detect_raw_wind_format(filepath)
    if date_format is None or not str(date_format).strip():
        date_format = RAW_FORMAT_DATE_DEFAULTS.get(fmt, "%Y-%m-%d %H:%M:%S")

    if fmt == "hobo":
        return read_HOBO(path, filename, date_format=date_format)
    if fmt == "campbell":
        return read_campbell(path, filename, date_format=date_format)
    return read_wind_data(path, filename, date_format=date_format, header=header)


def _read_csv_with_encoding(filepath, **kwargs):
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(filepath, encoding=encoding, **kwargs)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error


def _find_hobo_column(columns, *needles, exclude=()):
    """Return the first column whose folded header contains all ``needles``."""
    for column in columns:
        folded = _fold_header(column)
        if any(token in folded for token in exclude):
            continue
        if all(needle in folded for needle in needles):
            return column
    return None


def _parse_hobo_timestamps(values, date_format):
    """Parse HOBO timestamps, trying locale-specific formats if needed."""
    formats = []
    for candidate in (date_format,) + HOBO_DATE_FORMATS:
        if candidate and candidate not in formats:
            formats.append(candidate)
    last_error = None
    for fmt in formats:
        try:
            return _parse_timestamps(values, fmt, strict=True)
        except ValueError as exc:
            last_error = exc
    raise last_error


def _hobo_required_columns(columns):
    """Map HOBO export headers onto timestamp / WD / WS / optional WS_max."""
    timestamp = (
        _find_hobo_column(columns, "fecha", "tiempo")
        or _find_hobo_column(columns, "date", "time")
        or _find_hobo_column(columns, "fecha")
    )
    # Prefer HOBO-specific labels, then the shared flexible matcher.
    direction = (
        _find_hobo_column(columns, "direccion", "viento")
        or _find_hobo_column(columns, "direcci", "viento")
        or _find_hobo_column(columns, "wind", "direction")
    )
    gust = (
        _find_hobo_column(columns, "velocidad", "rafagas")
        or _find_hobo_column(columns, "rafagas")
        or _find_hobo_column(columns, "gust")
    )
    speed = (
        _find_hobo_column(columns, "velocidad", "viento", exclude=("rafagas", "gust"))
        or _find_hobo_column(columns, "wind", "speed", exclude=("gust",))
    )
    if direction is None or speed is None or gust is None:
        flex_direction, flex_speed, flex_gust = _find_wind_columns(
            columns, skip=() if timestamp is None else (timestamp,)
        )
        direction = direction or flex_direction
        speed = speed or flex_speed
        gust = gust or flex_gust

    missing = []
    if timestamp is None:
        missing.append("timestamp (Fecha Tiempo)")
    if direction is None:
        missing.append('direction ("Dirección del viento")')
    if speed is None:
        missing.append('wind speed ("Velocidad del viento")')
    if missing:
        available = ", ".join(str(name) for name in columns)
        raise ValueError(
            "HOBO file is missing required column(s): "
            + ", ".join(missing)
            + f". Found headers: {available}."
        )
    return timestamp, direction, speed, gust


def read_HOBO(path, filename, date_format="%m/%d/%y %I:%M:%S %p"):
    """
    Reads HOBO / HOBOware CSV wind exports.

    Expected layout:
    - Row 0: plot / project title
    - Row 1: headers. Column order is not fixed; names include units and
      logger/sensor serials. Spanish HOBOware headers are matched by:
      - ``Dirección del viento`` → WD
      - ``Velocidad del viento`` → WS
      - ``Velocidad de Ráfagas`` → WS_max (optional)
      English HOBOware labels (Wind Direction / Wind Speed / Gust) are
      also accepted.
    - Remaining rows: data

    Returns a DataFrame indexed by timestamp with columns WD, WS, and WS_max
    when a gust column is present.
    Rows where both wind speed and gust are 0 have WD, WS, and WS_max set to NaN.
    """
    filepath = os.path.join(path, filename)
    raw = _read_csv_with_encoding(
        filepath, header=1, sep=",", engine="python"
    )
    timestamp_col, direction_col, speed_col, gust_col = _hobo_required_columns(
        raw.columns
    )

    timestamps = _parse_hobo_timestamps(raw[timestamp_col], date_format)
    frame = {
        "WD": pd.to_numeric(raw[direction_col], errors="coerce").to_numpy(),
        "WS": pd.to_numeric(raw[speed_col], errors="coerce").to_numpy(),
    }
    if gust_col is not None:
        frame["WS_max"] = pd.to_numeric(raw[gust_col], errors="coerce").to_numpy()
    out = pd.DataFrame(frame, index=timestamps)
    return _null_zero_speed_and_gust(out)


def read_campbell(path, filename, date_format="%Y-%m-%d %H:%M:%S"):
    """
    Reads Campbell Scientific TOA5 table exports (``.dat`` / CSV).

    Expected layout:
    - Row 1: station metadata (TOA5, ...)
    - Row 2: column names
    - Row 3: units
    - Row 4: processing types (Avg, Max, WVc, ...)
    - Remaining rows: data

    Renames ``WS_ms_Avg`` → WS, ``WS_ms_Max`` → WS_max, and
    ``WindDir_D1_WVT`` → WD, then falls back to flexible header matching.
    Returns WD / WS / optional WS_max indexed by TIMESTAMP, plus ``BattV``
    when that column is present.
    Rows where both wind speed and gust are 0 have WD, WS, and WS_max set to NaN.
    """
    filepath = os.path.join(path, filename)
    # Skip metadata (row 0), units (row 2), and types (row 3); use names on row 1.
    raw = pd.read_csv(filepath, skiprows=[0, 2, 3], header=0)

    rename_map = {
        "WS_ms_Avg": "WS",
        "WS_ms_Max": "WS_max",
        "WindDir_D1_WVT": "WD",
    }
    raw = raw.rename(columns=rename_map)

    if "TIMESTAMP" not in raw.columns:
        raise ValueError("Campbell file is missing required column(s): TIMESTAMP")

    if "WD" not in raw.columns or "WS" not in raw.columns:
        direction_col, speed_col, gust_col = _find_wind_columns(
            raw.columns, skip=("TIMESTAMP",)
        )
        rename = {}
        if direction_col is not None and "WD" not in raw.columns:
            rename[direction_col] = "WD"
        if speed_col is not None and "WS" not in raw.columns:
            rename[speed_col] = "WS"
        if gust_col is not None and "WS_max" not in raw.columns:
            rename[gust_col] = "WS_max"
        raw = raw.rename(columns=rename)

    missing = [name for name in ("WD", "WS") if name not in raw.columns]
    if missing:
        raise ValueError(
            "Campbell file is missing required column(s): " + ", ".join(missing)
        )

    timestamps = _parse_timestamps(raw["TIMESTAMP"], date_format, strict=True)
    frame = {
        "WD": pd.to_numeric(raw["WD"], errors="coerce").to_numpy(),
        "WS": pd.to_numeric(raw["WS"], errors="coerce").to_numpy(),
    }
    if "WS_max" in raw.columns:
        frame["WS_max"] = pd.to_numeric(raw["WS_max"], errors="coerce").to_numpy()
    if "BattV" in raw.columns:
        frame["BattV"] = pd.to_numeric(raw["BattV"], errors="coerce").to_numpy()
    out = pd.DataFrame(frame, index=timestamps)
    return _null_zero_speed_and_gust(out)
