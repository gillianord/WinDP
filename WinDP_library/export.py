def export_raw_data(path, center, df, sheet_name="Datos_Preprocesados"):
    import pandas as pd
    import os

    df = df.copy()
    df.columns = ["Dir. Media [°]", "Vel. media [m/s]", "Racha [m/s]"]
    df.index.name = "Fecha y Hora"

    output_filepath = os.path.join(path, f"Datos_Preprocesados_{center}.xlsx")

    with pd.ExcelWriter(output_filepath, engine="xlsxwriter", datetime_format="dd-mm-yyyy HH:MM") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=True)

        worksheet = writer.sheets[sheet_name]

        # Set column widths (A:D → index + 3 columns)
        worksheet.set_column("A:D", 15)

        textbox_text = (
            "Datos Preprocesados:\n"
            "• Datos referidos al norte magnético\n"
            "• Datos referidos en UTC-0"
        )

        worksheet.insert_textbox(
            "F2",
            textbox_text,
            {
                "width": 255,
                "height": 80,
                "font": {"size": 11},
                "align": {"vertical": "top", "horizontal": "left"},
            },
        )

    return output_filepath


def export_processed_data(
    path,
    center,
    df,
    deleted_df=None,
    direction_correction_df=None,
    sheet_names=("Datos_procesados", "Datos_eliminados", "Correccion_direccion"),
):
    import pandas as pd
    import os

    df = df.copy()
    df.columns = ["Dir. Media [°]", "Vel. media [m/s]", "Racha [m/s]"]
    df.index.name = "Fecha y Hora"

    output_filepath = os.path.join(path, f"Datos_Procesados_{center}.xlsx")

    with pd.ExcelWriter(output_filepath, engine="xlsxwriter", datetime_format="dd-mm-yyyy HH:MM") as writer:
        df.to_excel(writer, sheet_name=sheet_names[0], index=True)

        worksheet = writer.sheets[sheet_names[0]]

        # Set column widths (A:D → index + 3 columns)
        worksheet.set_column("A:D", 15)

        textbox_text = (
            "Datos Procesados:\n"
            "• Datos referidos al norte geográfico\n"
            "• Datos referidos en UTC-0"
        )

        worksheet.insert_textbox(
            "F2",
            textbox_text,
            {
                "width": 255,
                "height": 80,
                "font": {"size": 11},
                "align": {"vertical": "top", "horizontal": "left"},
            },
        )

        if deleted_df is not None and not deleted_df.empty:
            deleted_export = deleted_df.copy()
            deleted_export.index.name = "Fecha y Hora"
            deleted_export.to_excel(writer, sheet_name=sheet_names[1], index=True)

            deleted_worksheet = writer.sheets[sheet_names[1]]
            deleted_worksheet.set_column("A:E", 15)

        if direction_correction_df is not None and not direction_correction_df.empty:
            corr_export = direction_correction_df.copy()
            corr_export.to_excel(writer, sheet_name=sheet_names[2], index=False)
            corr_worksheet = writer.sheets[sheet_names[2]]
            corr_worksheet.set_column("A:E", 20)

    return output_filepath

def export_notes_tables_figures(path, df, center, vel_bins, lon, lat, declination, error, fig):
    """
    For data less than a year a shorter version is exported.
    For data at least a year long monthly tables and figures are included.
    Data notes are exported with data time index in UTC0,
    then a timezone adjustment is applied to the data so that daily cycle analysis is in local time.
    """
    from datetime import timedelta
    import os

    from .figures import (
        daily_annual_cycle,
        spectral_density_figure,
        wind_report_figures,
        wind_year_figures,
    )
    from .notes_tables import (
        wind_incident_tables,
        wind_incident_tables_months,
        wind_notes,
    )

    filename = wind_notes(path, df, center, lon, lat, declination, error, fig)
    df1 = df.copy()
    #df1.index = df1.index.tz_localize("UTC").tz_convert("America/Santiago")
    df1.index += -timedelta(hours=3)
    # If the tz moves data into another month by a few hours, exclude these hours from analysis.
    if df.index[0].month != df1.index[0].month:
        df1 = df1[df1.index >= df.index[0]]

    wind_report_figures(path, df1, vel_bins)
    wind_incident_tables(path, filename, df1, vel_bins)
    spectral_density_figure(df1, path)

    if df1.index[-1] - df1.index[0] >= timedelta(days=365):
        XLABELS, MAX, MEAN, P5, P95 = wind_incident_tables_months(
            path, filename, df1, vel_bins
        )
        wind_year_figures(path, df1, XLABELS, MAX, MEAN, P5, P95, vel_bins)
        daily_annual_cycle(
            df1, title="Ciclo Diario y Mensual del Viento", save_path=path
        )

    return os.path.join(path, filename)
