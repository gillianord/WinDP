#!/usr/bin/env python
# coding: utf-8

import os
from datetime import datetime

import pandas as pd


EXCEL_COLUMN_MAP = {
    "Dir. Media [°]": "WD",
    "Vel. media [m/s]": "WS",
    "Racha [m/s]": "WS_max",
}


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


def ensure_ten_minute_frequency(df):
    """
    Reindex onto a regular 10-minute timeline.

    Existing timestamps are rounded to the nearest 10 minutes, duplicates are
    dropped, and missing intervals are inserted as NaN via ``asfreq``.
    """
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    out.index = out.index.round("10min")
    out = out[~out.index.duplicated(keep="first")]
    return out.asfreq("10min")


def _excel_wind_frame(df, date_format):
    """Map an exported Excel wind sheet onto WD / WS / WS_max columns."""
    missing = [name for name in EXCEL_COLUMN_MAP if name not in df.columns]
    if missing:
        raise ValueError(
            "Excel sheet is missing required column(s): " + ", ".join(missing)
        )
    timestamps = _parse_timestamps(df.iloc[:, 0], date_format)
    out = df.rename(columns=EXCEL_COLUMN_MAP)
    out = out.loc[:, ["WD", "WS", "WS_max"]].copy()
    out.index = timestamps
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

    Excel files are expected to use:
    - Column A: timestamp
    - ``Dir. Media [°]``: wind direction
    - ``Vel. media [m/s]``: wind speed
    - ``Racha [m/s]``: wind gust

    Rows where both wind speed and gust are 0 have WD, WS, and WS_max set to NaN.

    Default date_format = '%Y-%m-%d %H:%M:%S' (used for string timestamps).
    """
    filepath = os.path.join(path, filename)
    extension = os.path.splitext(filename)[1].lower()

    if extension in {".xlsx", ".xls", ".xlsm"}:
        df = pd.read_excel(filepath, header=header)
        return _null_zero_speed_and_gust(_excel_wind_frame(df, date_format))

    df = pd.read_csv(filepath, header=header, sep="\t", engine="python")
    timestamps = _parse_timestamps(df.iloc[:, 0], date_format, strict=True)
    df.index = timestamps
    df = df.iloc[:, 1:]
    return _null_zero_speed_and_gust(df)


def read_processed_export(
    path,
    filename,
    date_format="%Y-%m-%d %H:%M:%S",
    processed_sheet="Datos_procesados",
    deleted_sheet="Datos_eliminados",
    direction_correction_sheet="Correccion_direccion",
    header=0,
):
    """
    Load a workbook written by ``export_processed_data``.

    Returns
    -------
    data : pandas.DataFrame
        Rows from ``Datos_procesados`` (WD / WS / WS_max).
    deleted : pandas.DataFrame
        Rows from ``Datos_eliminados`` with WD / WS / WS_max and a ``Notes``
        column. Empty when that sheet is absent.
    direction_corrections : pandas.DataFrame
        Rows from ``Correccion_direccion`` when present; otherwise empty with the
        expected columns.
    """
    filepath = os.path.join(path, filename)
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".xlsx", ".xls", ".xlsm"}:
        raise ValueError("Processed data must be an Excel workbook (.xlsx).")

    workbook = pd.ExcelFile(filepath)
    sheet_lookup = {name.casefold(): name for name in workbook.sheet_names}
    processed_key = processed_sheet.casefold()
    if processed_key not in sheet_lookup:
        raise ValueError(
            f"Workbook is missing required sheet '{processed_sheet}'."
        )

    data = _excel_wind_frame(
        pd.read_excel(
            workbook, sheet_name=sheet_lookup[processed_key], header=header
        ),
        date_format,
    )

    deleted_key = deleted_sheet.casefold()
    if deleted_key not in sheet_lookup:
        deleted = pd.DataFrame(columns=["WD", "WS", "WS_max", "Notes"])
        deleted.index = pd.DatetimeIndex([], name="Fecha y Hora")
    else:
        deleted_raw = pd.read_excel(
            workbook, sheet_name=sheet_lookup[deleted_key], header=header
        )
        if deleted_raw.empty:
            deleted = pd.DataFrame(columns=["WD", "WS", "WS_max", "Notes"])
            deleted.index = pd.DatetimeIndex([], name="Fecha y Hora")
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
    corr_key = direction_correction_sheet.casefold()
    if corr_key not in sheet_lookup:
        direction_corrections = pd.DataFrame(columns=corr_columns)
    else:
        direction_corrections = pd.read_excel(
            workbook, sheet_name=sheet_lookup[corr_key], header=header
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

    return data, deleted, direction_corrections


def influx2df(empresa, center, nowdate):
    """
    Downloads the influx database
    """
    from influxdb_client import InfluxDBClient
    from datetime import datetime

    org = "org"
    url = "http://anemoserver:8086"
    token = "7OS1uxe1XhzmKhsMeh6KUxgFbVBQfUIs6bfsnUb4SME0O4vkeDqcmXQ_dQCLajU6d1Pl2vVJvrWLx1F8mEhtuA=="  # TOKEN LECTURA

    client = InfluxDBClient(url=url, token=token, org=org)

    # WD DIRECCION // WS_max RACHA // WS VIENTO NORMAL

    query = f'''
    from(bucket: "P_{empresa}")  
        |> range(start: 2021-01-01T00:00:00Z, stop: {nowdate.strftime('%Y-%m-%dT%H:%M:%SZ')})
        |> filter(fn: (r) => r["_measurement"] == "{center}")
        |> filter(fn: (r) => r["_field"] == "_time" or r["_field"] == "WD" or r["_field"] == "WS" or r["_field"] == "WS_max") 
        |> pivot(rowKey: ["_time"], columnKey:["_field"], valueColumn:"_value")
    '''

    df = client.query_api().query_data_frame(org=org, query=query)

    date_obj = []
    for i in range(len(df._time)):
        date_str = str(df._time[i])
        date_str = date_str[:-6]
        date_obj.append(datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S"))

    df.index = date_obj
    df = df.iloc[:, 6:]
    df.dropna()  # Percent of data missing is based on length of dataset so we don't want to count nans

    return df
