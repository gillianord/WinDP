# Canonical Excel wind-column labels (also accepted when loading).
EXPORT_WIND_COLUMNS = ["Direction (°)", "Speed (m/s)", "Gust (m/s)"]
EXPORT_INDEX_NAME = "Timestamp"
MAGNETIC_CORRECTION_COLUMNS = ["Original Direction (°)", "Declination (°)"]


def export_raw_data(path, center, df, sheet_name="preprocessed_data"):
    import pandas as pd
    import os

    df = df.copy()
    df.columns = list(EXPORT_WIND_COLUMNS)
    df.index.name = EXPORT_INDEX_NAME

    output_filepath = os.path.join(path, f"preprocessed_wind_data_{center}.xlsx")

    with pd.ExcelWriter(output_filepath, engine="xlsxwriter", datetime_format="dd-mm-yyyy HH:MM") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=True)

        worksheet = writer.sheets[sheet_name]

        # Set column widths (A:D → index + 3 columns)
        worksheet.set_column("A:D", 15)

    return output_filepath


def export_processed_data(
    path,
    center,
    df,
    deleted_df=None,
    direction_correction_df=None,
    magnetic_correction_df=None,
    preprocessed_df=None,
    sheet_names=(
        "processed_data",
        "deleted_data",
        "direction_corrections",
        "magnetic_correction",
    ),
    preprocessed_sheet="preprocessed_data",
):
    import pandas as pd
    import os

    df = df.copy()
    df.columns = list(EXPORT_WIND_COLUMNS)
    df.index.name = EXPORT_INDEX_NAME

    output_filepath = os.path.join(path, f"processed_wind_data_{center}.xlsx")

    with pd.ExcelWriter(output_filepath, engine="xlsxwriter", datetime_format="dd-mm-yyyy HH:MM") as writer:
        df.to_excel(writer, sheet_name=sheet_names[0], index=True)

        worksheet = writer.sheets[sheet_names[0]]

        # Set column widths (A:D → index + 3 columns)
        worksheet.set_column("A:D", 15)

        if preprocessed_df is not None and not preprocessed_df.empty:
            preprocessed_export = preprocessed_df.copy()
            preprocessed_export.columns = list(EXPORT_WIND_COLUMNS)
            preprocessed_export.index.name = EXPORT_INDEX_NAME
            preprocessed_export.to_excel(
                writer, sheet_name=preprocessed_sheet, index=True
            )
            preprocessed_worksheet = writer.sheets[preprocessed_sheet]
            preprocessed_worksheet.set_column("A:D", 15)

        if deleted_df is not None and not deleted_df.empty:
            deleted_export = deleted_df.copy()
            deleted_export.index.name = EXPORT_INDEX_NAME
            deleted_export.to_excel(writer, sheet_name=sheet_names[1], index=True)

            deleted_worksheet = writer.sheets[sheet_names[1]]
            deleted_worksheet.set_column("A:E", 15)

        if direction_correction_df is not None and not direction_correction_df.empty:
            corr_export = direction_correction_df.copy()
            corr_export.to_excel(writer, sheet_name=sheet_names[2], index=False)
            corr_worksheet = writer.sheets[sheet_names[2]]
            corr_worksheet.set_column("A:E", 20)

        if magnetic_correction_df is not None and not magnetic_correction_df.empty:
            magnetic_export = magnetic_correction_df.copy()
            magnetic_export.index.name = EXPORT_INDEX_NAME
            magnetic_export.to_excel(writer, sheet_name=sheet_names[3], index=True)
            magnetic_worksheet = writer.sheets[sheet_names[3]]
            magnetic_worksheet.set_column("A:C", 20)

    return output_filepath
