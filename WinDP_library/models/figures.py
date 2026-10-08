#!/usr/bin/env python
# coding: utf-8

"""Interactive wind plots used by the WinDP desktop UI."""


def _draw_wind_rose(rose_ax, wd, ws, rose_bins):
    """Redraw a wind rose for the provided samples.

    WindroseAxes does not reliably redraw after ``clear()``, so the axes is
    replaced in-place and the new axes is returned.
    """
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick

    fig = rose_ax.figure
    subplot_spec = rose_ax.get_subplotspec()

    # Windrose legends often cannot be removed with Artist.remove().
    # Dropping the axes itself is enough; hide any leftover figure legends.
    rose_ax.remove()
    for extra_legend in list(getattr(fig, "legends", [])):
        try:
            extra_legend.remove()
        except NotImplementedError:
            extra_legend.set_visible(False)

    rose_ax = fig.add_subplot(subplot_spec, projection="windrose")

    if len(wd) == 0 or len(ws) == 0:
        return rose_ax

    cm = plt.get_cmap("jet")
    rose_ax.bar(
        wd,
        ws,
        normed=True,
        blowto=False,
        nsector=8,
        opening=1,
        bins=rose_bins,
        cmap=cm,
        edgecolor="k",
    )
    rose_ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    rose_ax.set_legend(loc="center left", bbox_to_anchor=(1.08, 0.5))
    return rose_ax


def wind_rose_polar_timeseries(path, df, vel_bins):
    """Create the wind rose, polar scatter, and wind-speed time series.

    ``path`` is retained for compatibility with existing callers.  The
    returned artist dictionary lets GUI callers update the selected point
    without rebuilding the whole figure.
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from windrose import WindroseAxes  # noqa: F401 - registers the projection

    del path
    if df.empty:
        raise ValueError("Cannot plot an empty wind data set.")
    missing_columns = {"WD", "WS"}.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Wind data is missing required column(s): {missing}")

    wd = np.asarray(df["WD"], dtype=float)
    ws = np.asarray(df["WS"], dtype=float)
    finite = np.isfinite(wd) & np.isfinite(ws)
    if not finite.any():
        raise ValueError("WD and WS contain no finite values to plot.")

    rose_bins = np.asarray(vel_bins, dtype=float)
    if rose_bins.ndim != 1 or len(rose_bins) < 2:
        raise ValueError("vel_bins must contain at least two values.")
    rose_bins = rose_bins[:-1]

    fig = Figure(figsize=(14, 7), facecolor="whitesmoke")
    grid = fig.add_gridspec(
        3,
        2,
        width_ratios=[1.05, 1],
        height_ratios=[1, 1, 0.95],
        left=0.04,
        right=0.90,
        top=0.94,
        bottom=0.07,
        wspace=0.28,
        hspace=0.32,
    )
    rose_ax = fig.add_subplot(grid[0:2, 0], projection="windrose")
    polar_ax = fig.add_subplot(grid[0:2, 1], projection="polar")
    timeseries_ax = fig.add_subplot(grid[2, :])

    # Dummy axes first so windrose sectors render with curved edges.
    hist_ax = plt.Axes(fig, [0.1, 0.1, 0.8, 0.8])
    hist_ax.bar(np.array([1]), np.array([1]))
    rose_ax = _draw_wind_rose(rose_ax, wd[finite], ws[finite], rose_bins)

    directions_radians = np.deg2rad(wd)
    polar_points = polar_ax.scatter(
        directions_radians,
        ws,
        s=5,
        c="skyblue",
        edgecolors="dodgerblue",
        linewidths=0.7,
        alpha=0.8,
        picker=5,
    )
    selected_position = int(np.nanargmax(ws))
    polar_selection = polar_ax.scatter(
        [directions_radians[selected_position]],
        [ws[selected_position]],
        s=10,
        c="magenta",
        edgecolors="darkmagenta",
        zorder=5,
    )
    polar_ax.set_theta_zero_location("N")
    polar_ax.set_theta_direction(-1)
    polar_ax.set_rmax(max(float(np.ceil(np.nanmax(ws))) + 1.0, 1.0))

    gust_line = None
    gust_speeds = None
    if "WS_max" in df.columns:
        gust_speeds = np.asarray(df["WS_max"], dtype=float)
        # Gust under wind speed; above direction (drawn on the twin axis).
        (gust_line,) = timeseries_ax.plot(
            df.index,
            gust_speeds,
            color="crimson",
            linewidth=0.8,
            zorder=2,
            visible=False,
            label="Wind gust",
            picker=False,
        )

    (timeseries_line,) = timeseries_ax.plot(
        df.index,
        ws,
        color="skyblue",
        linewidth=0.8,
        zorder=3,
        label="Wind speed",
        picker=False,
    )
    timeseries_points = timeseries_ax.scatter(
        df.index,
        ws,
        s=8,
        c="skyblue",
        linewidths=0.5,
        picker=6,
        zorder=4,
    )
    timeseries_selection = timeseries_ax.scatter(
        [df.index[selected_position]],
        [ws[selected_position]],
        s=10,
        c="magenta",
        edgecolors="darkmagenta",
        zorder=5,
        picker=False,
    )
    timeseries_ax.set_ylabel("Wind speed (m/s)")
    timeseries_ax.grid(True)
    timeseries_ax.margins(0)

    # Twin axis sits below the primary axes so wind-speed picking still works.
    direction_ax = timeseries_ax.twinx()
    (direction_line,) = direction_ax.plot(
        df.index,
        wd,
        color="black",
        linewidth=0.8,
        zorder=1,
        visible=False,
        label="Direction",
        picker=False,
    )
    battery_line = None
    battery_voltages = None
    if "BattV" in df.columns:
        battery_voltages = np.asarray(df["BattV"], dtype=float)
        (battery_line,) = direction_ax.plot(
            df.index,
            battery_voltages,
            color="darkgreen",
            linewidth=0.8,
            zorder=1,
            visible=False,
            label="Battery",
            picker=False,
        )
    direction_ax.set_ylim(0, 360)
    direction_ax.set_ylabel("Direction (°)", color="black", labelpad=8)
    direction_ax.tick_params(axis="y", colors="black", pad=3)
    direction_ax.grid(True)
    direction_ax.margins(0)
    direction_ax.spines["right"].set_visible(False)
    direction_ax.yaxis.set_visible(False)
    direction_ax.set_zorder(timeseries_ax.get_zorder() - 1)
    direction_ax.patch.set_visible(False)
    direction_ax.set_navigate(False)
    timeseries_ax.set_zorder(direction_ax.get_zorder() + 1)
    timeseries_ax.patch.set_visible(False)

    artists = {
        "rose_axis": rose_ax,
        "polar_axis": polar_ax,
        "timeseries_axis": timeseries_ax,
        "direction_axis": direction_ax,
        "polar_points": polar_points,
        "polar_selection": polar_selection,
        "timeseries_line": timeseries_line,
        "timeseries_points": timeseries_points,
        "timeseries_selection": timeseries_selection,
        "gust_line": gust_line,
        "direction_line": direction_line,
        "battery_line": battery_line,
        "directions_radians": directions_radians,
        "polar_offsets": np.column_stack([directions_radians, ws]),
        "timestamps": np.asarray(df.index),
        "wind_directions": wd,
        "wind_speeds": ws,
        "gust_speeds": gust_speeds,
        "battery_voltages": battery_voltages,
        "rose_bins": rose_bins,
        "selected_position": selected_position,
    }
    return fig, artists
