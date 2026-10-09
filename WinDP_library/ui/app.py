#!/usr/bin/env python
"""Main application window for Wind Data Processing."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import MouseButton

from WinDP_library.models.direction_correction import (
    DIR_BIN_CENTERS,
    best_rotation_degrees,
    circular_smooth,
    density_correlation,
    direction_density_histogram,
    peak_normalize,
    rotate_directions,
    wrap_degrees,
)
from WinDP_library.models.export import (
    export_processed_data as write_processed_export,
    export_raw_data as write_raw_export,
)
from WinDP_library.models.figures import _draw_wind_rose, wind_rose_polar_timeseries
from WinDP_library.models.magnetic_correction import (
    lonlat2utm,
    magnetic_correction,
    magnetic_correction_complete,
    magnetic_correction_wind,
    utm2lonlat,
)
from WinDP_library.models.read_data import (
    ensure_ten_minute_frequency,
    read_processed_export,
    read_wind_data,
)


class WindDataProcessingApp:
    """Load, inspect, select, delete, and restore wind observations."""

    ROW_ID_COLUMN = "_WINDP_ROW_ID"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Wind Data Processing")
        self.root.minsize(1000, 650)

        self.raw_data: pd.DataFrame | None = None
        self.original_data: pd.DataFrame | None = None
        self.active_data: pd.DataFrame | None = None
        self.deleted_row_ids: list[int] = []
        self.deletion_notes: dict[int, str] = {}
        self.selected_row_ids: set[int] = set()
        self._selection_focus_id: int | None = None
        self.magnetic_correction_applied = False
        self.lon = None
        self.lat = None
        self.declination = None
        self.error = None
        self.magnetic_fig = None
        self.fig3 = None

        self.figure_canvas: FigureCanvasTkAgg | None = None
        self.navigation_toolbar: NavigationToolbar2Tk | None = None
        self.plot_artists: dict[str, object] = {}
        self.pick_connection_id: int | None = None
        self.xlim_callback_id: int | None = None
        self.press_connection_id: int | None = None
        self.motion_connection_id: int | None = None
        self.release_connection_id: int | None = None
        self.visible_mask: np.ndarray | None = None
        self._last_synced_xlim: tuple[float, float] | None = None
        self._box_select_origin: tuple[float, float] | None = None
        self._box_select_axes: object | None = None
        self._box_select_button: object | None = None
        self._box_select_dragged: bool = False
        self.history_window: tk.Toplevel | None = None
        self.history_tree: ttk.Treeview | None = None
        self._info_popup: tk.Toplevel | None = None
        self._dir_corr_window: tk.Toplevel | None = None
        self._dir_corr_canvas: FigureCanvasTkAgg | None = None
        self._dir_corr_hist_ax = None
        self._dir_corr_polar_ax = None
        self._dir_corr_correct_ids: set[int] = set()
        self._dir_corr_incorrect_ids: set[int] = set()
        self._dir_corr_rotation = tk.IntVar(value=0)
        self._dir_corr_rotation_trace = None
        self._dir_corr_set_correct_button: ttk.Button | None = None
        self._dir_corr_fit_label: ttk.Label | None = None
        self.direction_correction_history: list[dict] = []
        self._dir_corr_history_window: tk.Toplevel | None = None
        self._dir_corr_history_tree: ttk.Treeview | None = None

        self.time_value = tk.StringVar(value="—")
        self.speed_value = tk.StringVar(value="—")
        self.direction_value = tk.StringVar(value="—")
        self.gust_value = tk.StringVar(value="—")
        self.battery_value = tk.StringVar(value="—")
        self.deletion_note = tk.StringVar(value="")
        self._has_battery = False
        self._battery_info_widgets: list[ttk.Label] = []
        self._popup_battery_info_widgets: list[ttk.Label] = []
        self.show_wind_speed = tk.BooleanVar(value=True)
        self.show_direction = tk.BooleanVar(value=False)
        self.show_gust = tk.BooleanVar(value=False)
        self.show_battery = tk.BooleanVar(value=False)
        self.view_store_var = tk.StringVar(value="processed")
        self.file_value = tk.StringVar(value="No data loaded")
        self.center_value = tk.StringVar(value="—")
        self.records_value = tk.StringVar(value="—")
        self.date_format = tk.StringVar(value="%Y-%m-%d %H:%M:%S")
        self.loaded_directory: str | None = None
        self.loaded_basename: str | None = None
        self.center_name: str | None = None

        self._build_interface()

    def _build_interface(self) -> None:
        self.show_information_panel_var = tk.BooleanVar(value=True)
        self.show_control_panel_var = tk.BooleanVar(value=True)
        self.show_magnetic_panel_var = tk.BooleanVar(value=True)
        self.show_direction_corr_panel_var = tk.BooleanVar(value=True)
        self.show_filtering_panel_var = tk.BooleanVar(value=True)
        self.show_all_panels_var = tk.BooleanVar(value=True)

        self.content = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.content.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.left_panel = ttk.Frame(self.content)
        self.content.add(self.left_panel, weight=0)
        # ttk.Panedwindow has no minsize; a slim guard keeps the left pane wide enough.
        self._left_width_guard = ttk.Frame(self.left_panel, width=260, height=1)
        self._left_width_guard.pack()
        self._left_width_guard.pack_propagate(False)
        self.root.after_idle(lambda: self.content.sashpos(0, 260))

        self.information_panel = ttk.LabelFrame(
            self.left_panel, text="Information panel", padding=(8, 4)
        )
        self.information_panel.pack(fill=tk.X)
        self.information_panel.columnconfigure(1, weight=1)

        self._add_information_row(
            self.information_panel,
            "File:",
            self.file_value,
            0,
            stacked=True,
            wraplength=236,
        )
        self._add_information_row(
            self.information_panel, "Center:", self.center_value, 2
        )
        self._add_information_row(
            self.information_panel, "Records:", self.records_value, 3
        )
        self._add_information_row(self.information_panel, "Time:", self.time_value, 4)
        self._add_information_row(
            self.information_panel, "Wind speed (m/s):", self.speed_value, 5
        )
        self._add_information_row(
            self.information_panel, "Wind gust (m/s):", self.gust_value, 6
        )
        self._add_information_row(
            self.information_panel, "Direction (°):", self.direction_value, 7
        )
        self._battery_info_widgets = self._add_information_row(
            self.information_panel, "Battery (V):", self.battery_value, 8
        )
        self._set_battery_info_visible(False)

        self.control_panel = ttk.LabelFrame(
            self.left_panel, text="Control panel", padding=10
        )
        self.control_panel.pack(fill=tk.X, pady=(8, 0))

        ttk.Radiobutton(
            self.control_panel,
            text="View processed data",
            variable=self.view_store_var,
            value="processed",
            command=self._on_view_store_changed,
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            self.control_panel,
            text="View raw data (read-only)",
            variable=self.view_store_var,
            value="raw",
            command=self._on_view_store_changed,
        ).pack(anchor=tk.W, pady=(2, 0))

        datasets_frame = ttk.LabelFrame(self.control_panel, text="Datasets", padding=10)
        datasets_frame.pack(fill=tk.X, pady=(8, 0))

        self.wind_speed_checkbox = ttk.Checkbutton(
            datasets_frame,
            text="Wind speed",
            variable=self.show_wind_speed,
            command=self._on_dataset_toggled,
        )
        self.wind_speed_checkbox.pack(anchor=tk.W)

        self.gust_checkbox = ttk.Checkbutton(
            datasets_frame,
            text="Wind gust",
            variable=self.show_gust,
            command=self._on_dataset_toggled,
            state=tk.DISABLED,
        )
        self.gust_checkbox.pack(anchor=tk.W, pady=(4, 0))

        self.direction_checkbox = ttk.Checkbutton(
            datasets_frame,
            text="Direction",
            variable=self.show_direction,
            command=self._on_direction_toggled,
        )
        self.direction_checkbox.pack(anchor=tk.W, pady=(4, 0))

        self.battery_checkbox = ttk.Checkbutton(
            datasets_frame,
            text="Battery (V)",
            variable=self.show_battery,
            command=self._on_battery_toggled,
            state=tk.DISABLED,
        )
        self.battery_checkbox.pack(anchor=tk.W, pady=(4, 0))

        self.magnetic_correction_frame = ttk.LabelFrame(
            self.left_panel, text="Magnetic correction", padding=10
        )
        self.magnetic_correction_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            self.magnetic_correction_frame,
            text="Magnetic correction",
            command=self.magnetic_correction_pressed,
            width=18,
        ).pack(anchor=tk.CENTER)

        self.direction_correction_frame = ttk.LabelFrame(
            self.left_panel, text="Direction correction", padding=10
        )
        self.direction_correction_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            self.direction_correction_frame,
            text="Correct direction",
            command=self.direction_correction_pressed,
            width=18,
        ).pack(anchor=tk.CENTER)
        ttk.Button(
            self.direction_correction_frame,
            text="Correction history",
            command=self.open_direction_correction_history,
            width=18,
        ).pack(anchor=tk.CENTER, pady=(6, 0))

        self.filtering_frame = ttk.LabelFrame(
            self.left_panel, text="Data filtering", padding=10
        )
        self.filtering_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(self.filtering_frame, text="Deletion note:").pack(anchor=tk.CENTER)
        note_entry = ttk.Entry(
            self.filtering_frame,
            textvariable=self.deletion_note,
            width=18,
            validate="key",
            validatecommand=(self.root.register(self._validate_deletion_note), "%P"),
        )
        note_entry.pack(anchor=tk.CENTER, pady=(2, 6))

        self.delete_button = ttk.Button(
            self.filtering_frame,
            text="Delete selected",
            command=self.delete_selected,
            state=tk.DISABLED,
            width=18,
        )
        self.delete_button.pack(anchor=tk.CENTER)

        ttk.Button(
            self.filtering_frame,
            text="Deletion history",
            command=self.open_deletion_history,
            width=18,
        ).pack(anchor=tk.CENTER, pady=(6, 0))

        self.plot_frame = ttk.Frame(self.content)
        self.content.add(self.plot_frame, weight=5)
        ttk.Label(
            self.plot_frame,
            text="Load wind data file to begin.",
            anchor=tk.CENTER,
        ).pack(fill=tk.BOTH, expand=True)

        self._build_menubar()

    def _build_menubar(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load raw data", command=self.load_data)
        file_menu.add_command(
            label="Load processed data", command=self.load_processed_data
        )
        file_menu.add_separator()
        file_menu.add_command(label="Export raw data", command=self.export_raw_data)
        file_menu.add_command(
            label="Export processed data", command=self.export_processed_data
        )
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(
            label="All panels",
            variable=self.show_all_panels_var,
            command=self._on_toggle_all_panels,
        )
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label="Information panel",
            variable=self.show_information_panel_var,
            command=self._apply_panel_visibility,
        )
        view_menu.add_checkbutton(
            label="Control panel",
            variable=self.show_control_panel_var,
            command=self._apply_panel_visibility,
        )
        view_menu.add_checkbutton(
            label="Magnetic correction",
            variable=self.show_magnetic_panel_var,
            command=self._apply_panel_visibility,
        )
        view_menu.add_checkbutton(
            label="Direction correction",
            variable=self.show_direction_corr_panel_var,
            command=self._apply_panel_visibility,
        )
        view_menu.add_checkbutton(
            label="Data filtering",
            variable=self.show_filtering_panel_var,
            command=self._apply_panel_visibility,
        )
        menubar.add_cascade(label="View", menu=view_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        self._tools_menu = tools_menu

        control_menu = tk.Menu(tools_menu, tearoff=0)
        view_submenu = tk.Menu(control_menu, tearoff=0)
        view_submenu.add_radiobutton(
            label="View processed data",
            variable=self.view_store_var,
            value="processed",
            command=self._on_view_store_changed,
        )
        view_submenu.add_radiobutton(
            label="View raw data (read-only)",
            variable=self.view_store_var,
            value="raw",
            command=self._on_view_store_changed,
        )
        control_menu.add_cascade(label="View", menu=view_submenu)

        datasets_menu = tk.Menu(control_menu, tearoff=0)
        self._datasets_tools_menu = datasets_menu
        datasets_menu.add_checkbutton(
            label="Wind speed",
            variable=self.show_wind_speed,
            command=self._on_dataset_toggled,
        )
        datasets_menu.add_checkbutton(
            label="Wind gust",
            variable=self.show_gust,
            command=self._on_dataset_toggled,
        )
        self._gust_tools_menu_index = datasets_menu.index("end")
        datasets_menu.add_checkbutton(
            label="Direction",
            variable=self.show_direction,
            command=self._on_direction_toggled,
        )
        datasets_menu.add_checkbutton(
            label="Battery (V)",
            variable=self.show_battery,
            command=self._on_battery_toggled,
        )
        self._battery_tools_menu_index = datasets_menu.index("end")
        control_menu.add_cascade(label="Datasets", menu=datasets_menu)
        tools_menu.add_cascade(label="Control panel", menu=control_menu)

        tools_menu.add_command(
            label="Magnetic correction",
            command=self.magnetic_correction_pressed,
        )
        self._magnetic_tools_index = tools_menu.index("end")

        direction_corr_menu = tk.Menu(tools_menu, tearoff=0)
        direction_corr_menu.add_command(
            label="Correct direction",
            command=self.direction_correction_pressed,
        )
        direction_corr_menu.add_command(
            label="Correction history",
            command=self.open_direction_correction_history,
        )
        tools_menu.add_cascade(
            label="Direction correction", menu=direction_corr_menu
        )
        self._direction_corr_tools_index = tools_menu.index("end")

        filtering_menu = tk.Menu(tools_menu, tearoff=0)
        self._filtering_tools_menu = filtering_menu
        filtering_menu.add_command(
            label="Delete selected",
            command=self.delete_selected,
            state=tk.DISABLED,
        )
        self._delete_tools_menu_index = filtering_menu.index("end")
        filtering_menu.add_command(
            label="Deletion history",
            command=self.open_deletion_history,
        )
        tools_menu.add_cascade(label="Data filtering", menu=filtering_menu)
        self._filtering_tools_index = tools_menu.index("end")

        tools_menu.add_command(
            label="Information panel",
            command=self.open_information_panel_popup,
        )
        menubar.add_cascade(label="Tools", menu=tools_menu)

        self.root.config(menu=menubar)
        self._set_gust_tools_enabled(False)
        self._set_battery_tools_enabled(False)
        self._update_tools_menu_availability()

    def _set_all_panels(self, show: bool) -> None:
        self.show_information_panel_var.set(show)
        self.show_control_panel_var.set(show)
        self.show_magnetic_panel_var.set(show)
        self.show_direction_corr_panel_var.set(show)
        self.show_filtering_panel_var.set(show)
        self.show_all_panels_var.set(show)
        self._apply_panel_visibility()

    def _on_toggle_all_panels(self) -> None:
        self._set_all_panels(self.show_all_panels_var.get())

    def _sync_all_panels_var(self) -> None:
        all_on = (
            self.show_information_panel_var.get()
            and self.show_control_panel_var.get()
            and self.show_magnetic_panel_var.get()
            and self.show_direction_corr_panel_var.get()
            and self.show_filtering_panel_var.get()
        )
        if self.show_all_panels_var.get() != all_on:
            self.show_all_panels_var.set(all_on)

    def _apply_panel_visibility(self) -> None:
        specs = [
            (self.information_panel, self.show_information_panel_var, {"fill": tk.X}),
            (
                self.control_panel,
                self.show_control_panel_var,
                {"fill": tk.X, "pady": (8, 0)},
            ),
            (
                self.magnetic_correction_frame,
                self.show_magnetic_panel_var,
                {"fill": tk.X, "pady": (8, 0)},
            ),
            (
                self.direction_correction_frame,
                self.show_direction_corr_panel_var,
                {"fill": tk.X, "pady": (8, 0)},
            ),
            (
                self.filtering_frame,
                self.show_filtering_panel_var,
                {"fill": tk.X, "pady": (8, 0)},
            ),
        ]
        for panel, _var, _opts in specs:
            panel.pack_forget()

        any_visible = False
        first = True
        for panel, var, opts in specs:
            if not var.get():
                continue
            pack_opts = dict(opts)
            if first:
                pack_opts.pop("pady", None)
                first = False
            panel.pack(**pack_opts)
            any_visible = True

        left_id = str(self.left_panel)
        left_in_pane = left_id in self.content.panes()
        if any_visible and not left_in_pane:
            self.content.insert(0, self.left_panel, weight=0)
            self.root.after_idle(lambda: self.content.sashpos(0, 260))
        elif not any_visible and left_in_pane:
            self.content.forget(self.left_panel)

        self._sync_all_panels_var()
        self._update_tools_menu_availability()

    def _set_menu_item_state(
        self, menu: tk.Menu | None, index: int | None, enabled: bool
    ) -> None:
        if menu is None or index is None:
            return
        try:
            menu.entryconfig(index, state=tk.NORMAL if enabled else tk.DISABLED)
        except tk.TclError:
            pass

    def _update_tools_menu_availability(self) -> None:
        """Disable panel tools that are already available on a visible panel."""
        self._set_menu_item_state(
            getattr(self, "_tools_menu", None),
            getattr(self, "_magnetic_tools_index", None),
            not self.show_magnetic_panel_var.get(),
        )
        self._set_menu_item_state(
            getattr(self, "_tools_menu", None),
            getattr(self, "_direction_corr_tools_index", None),
            not self.show_direction_corr_panel_var.get(),
        )
        self._set_menu_item_state(
            getattr(self, "_tools_menu", None),
            getattr(self, "_filtering_tools_index", None),
            not self.show_filtering_panel_var.get(),
        )

    def _set_gust_tools_enabled(self, enabled: bool) -> None:
        self._set_menu_item_state(
            getattr(self, "_datasets_tools_menu", None),
            getattr(self, "_gust_tools_menu_index", None),
            enabled,
        )

    def _set_battery_tools_enabled(self, enabled: bool) -> None:
        self._set_menu_item_state(
            getattr(self, "_datasets_tools_menu", None),
            getattr(self, "_battery_tools_menu_index", None),
            enabled,
        )

    def _set_delete_tools_enabled(self, enabled: bool) -> None:
        self._set_menu_item_state(
            getattr(self, "_filtering_tools_menu", None),
            getattr(self, "_delete_tools_menu_index", None),
            enabled,
        )

    def open_information_panel_popup(self) -> None:
        popup = getattr(self, "_info_popup", None)
        if popup is not None and popup.winfo_exists():
            popup.lift()
            popup.focus_force()
            return

        popup = tk.Toplevel(self.root)
        popup.title("Information panel")
        popup.resizable(False, False)
        self._info_popup = popup
        content = ttk.LabelFrame(popup, text="Information panel", padding=(8, 4))
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        content.columnconfigure(1, weight=1)
        self._add_information_row(
            content,
            "File:",
            self.file_value,
            0,
            stacked=True,
            wraplength=280,
        )
        self._add_information_row(content, "Center:", self.center_value, 2)
        self._add_information_row(content, "Records:", self.records_value, 3)
        self._add_information_row(content, "Time:", self.time_value, 4)
        self._add_information_row(content, "Wind speed (m/s):", self.speed_value, 5)
        self._add_information_row(content, "Wind gust (m/s):", self.gust_value, 6)
        self._add_information_row(content, "Direction (°):", self.direction_value, 7)
        self._popup_battery_info_widgets = self._add_information_row(
            content, "Battery (V):", self.battery_value, 8
        )
        if not self._has_battery:
            for widget in self._popup_battery_info_widgets:
                widget.grid_remove()

        def _on_close() -> None:
            self._info_popup = None
            self._popup_battery_info_widgets = []
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", _on_close)

    @staticmethod
    def _add_information_row(
        parent: ttk.LabelFrame,
        caption: str,
        value: tk.StringVar,
        row: int,
        *,
        stacked: bool = False,
        wraplength: int | None = None,
    ) -> list[ttk.Label]:
        if stacked:
            caption_label = ttk.Label(parent, text=caption)
            caption_label.grid(
                row=row, column=0, columnspan=2, sticky=tk.W, pady=(1, 0)
            )
            value_label = ttk.Label(
                parent,
                textvariable=value,
                wraplength=wraplength or 0,
                justify=tk.LEFT,
            )
            value_label.grid(
                row=row + 1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 1)
            )
            return [caption_label, value_label]

        caption_label = ttk.Label(parent, text=caption)
        caption_label.grid(row=row, column=0, sticky=tk.W, pady=1)
        value_label = ttk.Label(parent, textvariable=value)
        value_label.grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=1)
        return [caption_label, value_label]

    def _set_battery_info_visible(self, visible: bool) -> None:
        self._has_battery = bool(visible)
        for widget in (
            *self._battery_info_widgets,
            *self._popup_battery_info_widgets,
        ):
            if visible:
                widget.grid()
            else:
                widget.grid_remove()
        if not visible:
            self.battery_value.set("—")

    def load_data(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Open raw wind data",
            filetypes=[
                ("Wind data", "*.txt *.dat *.tsv *.xlsx *.xls *.xlsm"),
                ("Excel", "*.xlsx *.xls *.xlsm"),
                ("Text", "*.txt *.dat *.tsv"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        directory, basename = os.path.split(filename)
        extension = os.path.splitext(basename)[1].lower()
        is_tab_text = extension not in {".xlsx", ".xls", ".xlsm"}
        date_format = self.date_format.get().strip() or "%Y-%m-%d %H:%M:%S"

        while True:
            try:
                data = read_wind_data(
                    directory,
                    basename,
                    date_format=date_format,
                )
                self._validate_data(data)
                break
            except Exception as exc:
                if is_tab_text and self._is_date_format_error(exc):
                    new_format = simpledialog.askstring(
                        "Date format",
                        "Timestamps could not be parsed with the current date "
                        f"format:\n{date_format}\n\n"
                        f"{exc}\n\n"
                        "Enter the date format for this tab-delimited file\n"
                        "(example: %d/%m/%Y %H:%M:%S):",
                        initialvalue=date_format,
                        parent=self.root,
                    )
                    if new_format is None:
                        return
                    new_format = new_format.strip()
                    if not new_format:
                        messagebox.showwarning(
                            "Date format",
                            "A date format is required for tab-delimited files.",
                            parent=self.root,
                        )
                        return
                    date_format = new_format
                    self.date_format.set(date_format)
                    continue

                messagebox.showerror(
                    "Unable to load wind data",
                    str(exc),
                    parent=self.root,
                )
                return

        center = self._resolve_center_name(basename)
        if center is None:
            return

        self._install_loaded_dataset(
            data,
            directory=directory,
            basename=basename,
            center=center,
            magnetic_correction_applied=False,
        )

    @staticmethod
    def _is_date_format_error(exc: BaseException) -> bool:
        message = str(exc).casefold()
        return (
            "does not match format" in message
            or "time data" in message
            or "unconverted data remains" in message
        )

    def load_processed_data(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Open processed wind data",
            filetypes=[
                ("Processed Excel", "*.xlsx *.xls *.xlsm"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        directory, basename = os.path.split(filename)
        try:
            data, deleted, direction_corrections = read_processed_export(
                directory,
                basename,
                date_format=self.date_format.get().strip(),
            )
            if not deleted.empty:
                deleted_values = deleted.loc[:, ["WD", "WS", "WS_max"]]
                combined = pd.concat([data, deleted_values])
                combined = combined[~combined.index.duplicated(keep="first")]
            else:
                combined = data
            self._validate_data(combined)
        except Exception as exc:
            messagebox.showerror(
                "Unable to load processed data",
                str(exc),
                parent=self.root,
            )
            return

        deletion_notes_by_time = None
        if not deleted.empty:
            deletion_notes_by_time = {
                pd.Timestamp(timestamp).round("10min"): note
                for timestamp, note in deleted["Notes"].items()
            }

        center = self._resolve_center_name(basename)
        if center is None:
            return

        self._install_loaded_dataset(
            combined,
            directory=directory,
            basename=basename,
            center=center,
            magnetic_correction_applied=True,
            deletion_notes_by_time=deletion_notes_by_time,
            direction_corrections=direction_corrections,
        )

    @staticmethod
    def _center_from_basename(basename: str) -> str | None:
        stem = os.path.splitext(basename)[0]
        for prefix in ("Datos_Preprocesados_", "Datos_Procesados_"):
            if stem.startswith(prefix):
                center = stem[len(prefix) :].strip()
                return center or None
        return None

    def _resolve_center_name(self, basename: str) -> str | None:
        derived = self._center_from_basename(basename)
        if derived:
            return derived

        center = simpledialog.askstring(
            "Center name",
            "Enter the center name for this dataset:",
            initialvalue="center_name",
            parent=self.root,
        )
        if center is None:
            return None
        center = center.strip()
        if not center:
            messagebox.showwarning(
                "Center name",
                "A center name is required.",
                parent=self.root,
            )
            return None
        return center

    def _install_loaded_dataset(
        self,
        data: pd.DataFrame,
        *,
        directory: str,
        basename: str,
        center: str,
        magnetic_correction_applied: bool,
        deletion_notes_by_time: dict | None = None,
        direction_corrections: pd.DataFrame | None = None,
    ) -> None:
        data = data.copy()
        data["WD"] = pd.to_numeric(data["WD"], errors="coerce")
        data["WS"] = pd.to_numeric(data["WS"], errors="coerce")
        if "WS_max" in data.columns:
            data["WS_max"] = pd.to_numeric(data["WS_max"], errors="coerce")
        else:
            data["WS_max"] = np.nan
        if "BattV" in data.columns:
            data["BattV"] = pd.to_numeric(data["BattV"], errors="coerce")
        data = ensure_ten_minute_frequency(data)
        data[self.ROW_ID_COLUMN] = np.arange(len(data), dtype=int)

        self.deleted_row_ids.clear()
        self.deletion_notes.clear()
        self.deletion_note.set("")
        self._close_direction_correction()
        self._close_direction_correction_history()
        self.direction_correction_history.clear()
        self._dir_corr_correct_ids.clear()
        self._dir_corr_incorrect_ids.clear()
        self._dir_corr_rotation.set(0)
        if deletion_notes_by_time:
            for timestamp, note in deletion_notes_by_time.items():
                if timestamp not in data.index:
                    continue
                row_id = int(data.loc[timestamp, self.ROW_ID_COLUMN])
                if row_id not in self.deleted_row_ids:
                    self.deleted_row_ids.append(row_id)
                self.deletion_notes[row_id] = note

        observed = int(data["WS"].notna().sum())
        deleted_count = len(self.deleted_row_ids)
        self.raw_data = data.copy()
        self.original_data = data
        self.loaded_directory = directory
        self.loaded_basename = basename
        self.center_name = center
        self.magnetic_correction_applied = magnetic_correction_applied
        self.lon = None
        self.lat = None
        self.declination = None
        self.error = None
        if self.fig3 is not None:
            import matplotlib.pyplot as plt

            plt.close(self.fig3)
        self.magnetic_fig = None
        self.fig3 = None
        self.view_store_var.set("processed")
        self.show_wind_speed.set(True)
        self.show_direction.set(False)
        self.show_gust.set(False)
        self.show_battery.set(False)
        has_gust = data["WS_max"].notna().any()
        self.gust_checkbox.configure(state=tk.NORMAL if has_gust else tk.DISABLED)
        self._set_gust_tools_enabled(bool(has_gust))
        has_battery = "BattV" in data.columns and data["BattV"].notna().any()
        self.battery_checkbox.configure(
            state=tk.NORMAL if has_battery else tk.DISABLED
        )
        self._set_battery_tools_enabled(bool(has_battery))
        self._set_battery_info_visible(bool(has_battery))
        self.file_value.set(basename)
        self.center_value.set(center)
        records = f"{observed:,}"
        if deleted_count:
            records += f" / {deleted_count:,} deleted"
        self.records_value.set(records)
        if direction_corrections is not None and not direction_corrections.empty:
            self._load_direction_correction_history(direction_corrections)
        self._rebuild_plot()
        self._refresh_history_list()
        self._refresh_direction_correction_history_list()

    def _prompt_export_directory(self, title: str) -> str | None:
        initial_dir = self.loaded_directory or os.getcwd()
        path = filedialog.askdirectory(
            parent=self.root,
            title=title,
            initialdir=initial_dir,
        )
        return path or None

    def _require_center_name(self) -> str | None:
        if self.center_name:
            return self.center_name
        messagebox.showwarning(
            "Export",
            "A center name is required. Load data again to set it.",
            parent=self.root,
        )
        return None

    @staticmethod
    def _export_columns(data: pd.DataFrame) -> pd.DataFrame:
        export_df = pd.DataFrame(index=data.index)
        export_df["WD"] = pd.to_numeric(data["WD"], errors="coerce").round(2)
        export_df["WS"] = pd.to_numeric(data["WS"], errors="coerce").round(3)
        drop_subset = ["WD", "WS"]
        if "WS_max" in data.columns:
            export_df["WS_max"] = pd.to_numeric(
                data["WS_max"], errors="coerce"
            ).round(3)
            if data["WS_max"].notna().any():
                drop_subset.append("WS_max")
        else:
            export_df["WS_max"] = np.nan
        return export_df.dropna(subset=drop_subset)

    def _deleted_export_frame(self) -> pd.DataFrame | None:
        if self.original_data is None or not self.deleted_row_ids:
            return None

        deleted = self.original_data.iloc[self.deleted_row_ids]
        notes = pd.Series(
            [
                self.deletion_notes.get(int(row_id), "")
                for row_id in self.deleted_row_ids
            ],
            index=deleted.index,
        )
        export_df = self._export_columns(deleted)
        export_df.columns = ["Dir. Media [°]", "Vel. media [m/s]", "Racha [m/s]"]
        export_df["Notas"] = notes.reindex(export_df.index).fillna("")
        return export_df

    def _direction_correction_export_frame(self) -> pd.DataFrame | None:
        if not self.direction_correction_history:
            return None
        rows = []
        for entry in self.direction_correction_history:
            rows.append(
                {
                    "Correct start": entry["correct_start"],
                    "Correct end": entry["correct_end"],
                    "Incorrect start": entry["incorrect_start"],
                    "Incorrect end": entry["incorrect_end"],
                    "Rotation [°]": int(entry["rotation"]),
                }
            )
        return pd.DataFrame(rows)

    def export_raw_data(self) -> None:
        if self.raw_data is None or self.raw_data.empty:
            messagebox.showwarning(
                "Export raw data",
                "Load wind data before exporting.",
                parent=self.root,
            )
            return

        center = self._require_center_name()
        if center is None:
            return

        path = self._prompt_export_directory("Select folder for raw data export")
        if path is None:
            return

        try:
            output_filepath = write_raw_export(
                path, center, self._export_columns(self.raw_data)
            )
        except Exception as exc:
            messagebox.showerror(
                "Export raw data",
                str(exc),
                parent=self.root,
            )
            return

        messagebox.showinfo(
            "Export raw data",
            f"Raw data exported to:\n{output_filepath}",
            parent=self.root,
        )

    def export_processed_data(self) -> None:
        if self.original_data is None or self.original_data.empty:
            messagebox.showwarning(
                "Export processed data",
                "Load wind data before exporting.",
                parent=self.root,
            )
            return

        center = self._require_center_name()
        if center is None:
            return

        path = self._prompt_export_directory("Select folder for processed data export")
        if path is None:
            return

        try:
            output_filepath = write_processed_export(
                path,
                center,
                self._processed_export_frame(),
                deleted_df=self._deleted_export_frame(),
                direction_correction_df=self._direction_correction_export_frame(),
            )
        except Exception as exc:
            messagebox.showerror(
                "Export processed data",
                str(exc),
                parent=self.root,
            )
            return

        messagebox.showinfo(
            "Export processed data",
            f"Processed data exported to:\n{output_filepath}",
            parent=self.root,
        )

    def _processed_export_frame(self) -> pd.DataFrame:
        assert self.original_data is not None
        deleted_ids = set(self.deleted_row_ids)
        if deleted_ids:
            keep_mask = ~self.original_data[self.ROW_ID_COLUMN].isin(deleted_ids)
            processed = self.original_data.loc[keep_mask]
        else:
            processed = self.original_data
        return self._export_columns(processed)

    @staticmethod
    def _validate_data(data: pd.DataFrame) -> None:
        missing = {"WD", "WS"}.difference(data.columns)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"The selected file is missing required column(s): {names}.")
        if data.empty:
            raise ValueError("The selected file contains no datapoints.")

        columns = ["WD", "WS"]
        if "WS_max" in data.columns:
            columns.append("WS_max")
        if "BattV" in data.columns:
            columns.append("BattV")
        for column in columns:
            original = data[column]
            numeric = pd.to_numeric(original, errors="coerce")
            # Allow blanks/NaNs (pre-filled gaps); reject non-numeric text and inf.
            if pd.api.types.is_numeric_dtype(original):
                was_present = original.notna()
            else:
                text = original.astype("string").str.strip()
                was_present = original.notna() & text.ne("") & text.str.lower().ne("nan")
            values = numeric.to_numpy(dtype=float)
            invalid_text = was_present.to_numpy() & np.isnan(values)
            if invalid_text.any() or np.isinf(values).any():
                raise ValueError(
                    f"Column {column} contains non-numeric values "
                    "(empty / NaN gap cells are allowed)."
                )

        wd = pd.to_numeric(data["WD"], errors="coerce").to_numpy(dtype=float)
        ws = pd.to_numeric(data["WS"], errors="coerce").to_numpy(dtype=float)
        if not (np.isfinite(wd) & np.isfinite(ws)).any():
            raise ValueError(
                "The selected file has no finite WD/WS pairs to plot."
            )

    def _is_raw_view(self) -> bool:
        return self.view_store_var.get() == "raw"

    def _on_view_store_changed(self) -> None:
        self._rebuild_plot(preferred_row_ids=set(self.selected_row_ids))

    def _source_data_for_view(self) -> pd.DataFrame | None:
        if self._is_raw_view():
            return self.raw_data
        return self.original_data

    def _current_timeseries_xlim(self) -> tuple[float, float] | None:
        timeseries_ax = self.plot_artists.get("timeseries_axis")
        if timeseries_ax is None:
            return None
        x_min, x_max = timeseries_ax.get_xlim()
        return (float(x_min), float(x_max))

    def _rebuild_plot(
        self,
        preferred_row_id: int | None = None,
        preferred_row_ids: set[int] | None = None,
        preserve_xlim: bool = False,
    ) -> None:
        source = self._source_data_for_view()
        if source is None:
            return

        preserved_xlim = self._current_timeseries_xlim() if preserve_xlim else None

        self.active_data = source.copy()
        if not self._is_raw_view() and self.deleted_row_ids:
            deleted = set(self.deleted_row_ids)
            mask = self.active_data[self.ROW_ID_COLUMN].isin(deleted)
            value_columns = ["WD", "WS"]
            if "WS_max" in self.active_data.columns:
                value_columns.append("WS_max")
            if "BattV" in self.active_data.columns:
                value_columns.append("BattV")
            self.active_data.loc[mask, value_columns] = np.nan
        self._clear_plot_frame()

        if self.active_data.empty or not np.isfinite(
            self.active_data["WS"].to_numpy(dtype=float)
        ).any():
            ttk.Label(
                self.plot_frame,
                text="All datapoints have been deleted. Use Deletion history to undo.",
                anchor=tk.CENTER,
            ).pack(fill=tk.BOTH, expand=True)
            self.selected_row_ids.clear()
            self._selection_focus_id = None
            self._clear_information()
            return

        try:
            bins = self._velocity_bins(self.active_data["WS"])
            figure, self.plot_artists = wind_rose_polar_timeseries(
                "", self.active_data, bins
            )
        except Exception as exc:
            messagebox.showerror("Unable to draw wind data", str(exc), parent=self.root)
            self._clear_information()
            return

        self.figure_canvas = FigureCanvasTkAgg(figure, master=self.plot_frame)
        self.navigation_toolbar = NavigationToolbar2Tk(
            self.figure_canvas, self.plot_frame, pack_toolbar=False
        )
        self.navigation_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.figure_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.pick_connection_id = self.figure_canvas.mpl_connect(
            "pick_event", self._on_point_picked
        )
        self.press_connection_id = self.figure_canvas.mpl_connect(
            "button_press_event", self._on_mouse_press
        )
        self.motion_connection_id = self.figure_canvas.mpl_connect(
            "motion_notify_event", self._on_mouse_motion
        )
        self.release_connection_id = self.figure_canvas.mpl_connect(
            "button_release_event", self._on_mouse_release
        )
        timeseries_ax = self.plot_artists["timeseries_axis"]
        self._sync_plots_to_time_window(draw=False)
        self._apply_dataset_visibility(draw=False)

        # Seed Home with the full-data view before restoring any zoom window.
        # Otherwise a rebuild with preserve_xlim leaves an empty nav stack and
        # Home cannot return past the preserved limits.
        self.navigation_toolbar.update()
        self.navigation_toolbar.push_current()
        self.xlim_callback_id = timeseries_ax.callbacks.connect(
            "xlim_changed", self._on_timeseries_xlim_changed
        )
        if preserved_xlim is not None:
            timeseries_ax.set_xlim(*preserved_xlim)
            self.navigation_toolbar.push_current()

        restore_ids = set(preferred_row_ids or ())
        if preferred_row_id is not None:
            restore_ids.add(int(preferred_row_id))
        available_ids = set(
            self.active_data[self.ROW_ID_COLUMN].astype(int).tolist()
        )
        restore_ids &= available_ids
        if restore_ids:
            self._select_row_ids(
                restore_ids,
                focus_id=self._selection_focus_id
                if self._selection_focus_id in restore_ids
                else next(iter(restore_ids)),
            )
        else:
            self._select_position(int(self.plot_artists["selected_position"]))
        self.figure_canvas.draw()

    def _on_dataset_toggled(self) -> None:
        self._apply_dataset_visibility(draw=True)

    def _on_direction_toggled(self) -> None:
        if self.show_direction.get():
            self.show_battery.set(False)
        self._apply_dataset_visibility(draw=True)

    def _on_battery_toggled(self) -> None:
        if self.show_battery.get():
            self.show_direction.set(False)
        self._apply_dataset_visibility(draw=True)

    def _apply_dataset_visibility(self, draw: bool = True) -> None:
        if not self.plot_artists:
            return

        show_speed = bool(self.show_wind_speed.get())
        show_direction = bool(self.show_direction.get())
        show_gust = bool(self.show_gust.get())
        show_battery = bool(self.show_battery.get())
        show_twin = show_direction or show_battery

        for artist_name in (
            "timeseries_line",
            "timeseries_points",
            "timeseries_selection",
        ):
            artist = self.plot_artists.get(artist_name)
            if artist is not None:
                artist.set_visible(show_speed)

        timeseries_ax = self.plot_artists.get("timeseries_axis")
        if timeseries_ax is not None:
            timeseries_ax.yaxis.set_visible(show_speed)
            label = timeseries_ax.yaxis.label
            if label is not None:
                label.set_visible(show_speed)

        gust_line = self.plot_artists.get("gust_line")
        if gust_line is not None:
            gust_line.set_visible(show_gust)

        direction_line = self.plot_artists.get("direction_line")
        battery_line = self.plot_artists.get("battery_line")
        direction_ax = self.plot_artists.get("direction_axis")
        if direction_line is not None:
            direction_line.set_visible(show_direction)
        if battery_line is not None:
            battery_line.set_visible(show_battery)
        if direction_ax is not None:
            direction_ax.yaxis.set_visible(show_twin)
            direction_ax.spines["right"].set_visible(show_twin)
            label = direction_ax.yaxis.label
            if label is not None:
                label.set_visible(show_twin)
            # Leave room on the right for twin-axis tick labels and ylabel.
            direction_ax.figure.subplots_adjust(right=0.90 if show_twin else 0.98)
            direction_ax.yaxis.labelpad = 8
            if show_battery:
                battery_voltages = np.asarray(
                    self.plot_artists.get("battery_voltages", []), dtype=float
                )
                finite = battery_voltages[np.isfinite(battery_voltages)]
                if finite.size:
                    y_min = float(np.nanmin(finite))
                    y_max = float(np.nanmax(finite))
                    if y_min == y_max:
                        pad = max(abs(y_min) * 0.05, 0.1)
                        direction_ax.set_ylim(y_min - pad, y_max + pad)
                    else:
                        direction_ax.set_ylim(y_min, y_max)
                direction_ax.set_ylabel("Battery (V)", color="darkgreen")
                direction_ax.tick_params(axis="y", colors="darkgreen", pad=3)
            else:
                direction_ax.set_ylim(0, 360)
                direction_ax.set_ylabel("Direction (°)", color="black")
                direction_ax.tick_params(axis="y", colors="black", pad=3)
            direction_ax.margins(0)

        wind_speeds = np.asarray(self.plot_artists.get("wind_speeds", []), dtype=float)
        if timeseries_ax is not None and wind_speeds.size:
            y_values = []
            if show_speed:
                y_values.append(wind_speeds)
            gust_speeds = self.plot_artists.get("gust_speeds")
            if show_gust and gust_speeds is not None:
                y_values.append(np.asarray(gust_speeds, dtype=float))
            if y_values:
                y_min = float(np.nanmin([np.nanmin(values) for values in y_values]))
                y_max = float(np.nanmax([np.nanmax(values) for values in y_values]))
                if np.isfinite(y_min) and np.isfinite(y_max):
                    timeseries_ax.set_ylim(y_min, y_max)
                    timeseries_ax.margins(0)

        if draw and self.figure_canvas is not None:
            self.figure_canvas.draw_idle()

    @staticmethod
    def _velocity_bins(speeds: pd.Series) -> np.ndarray:
        finite = pd.to_numeric(speeds, errors="coerce")
        maximum = float(finite.max()) if finite.notna().any() else 0.0
        if not np.isfinite(maximum):
            maximum = 0.0
        upper = max(float(np.ceil(maximum)) + 1.0, 1.0)
        return np.linspace(0.0, upper, 7)

    def _clear_plot_frame(self) -> None:
        if self.figure_canvas is not None:
            if self.pick_connection_id is not None:
                self.figure_canvas.mpl_disconnect(self.pick_connection_id)
            if self.press_connection_id is not None:
                self.figure_canvas.mpl_disconnect(self.press_connection_id)
            if self.motion_connection_id is not None:
                self.figure_canvas.mpl_disconnect(self.motion_connection_id)
            if self.release_connection_id is not None:
                self.figure_canvas.mpl_disconnect(self.release_connection_id)
        timeseries_ax = self.plot_artists.get("timeseries_axis")
        if timeseries_ax is not None and self.xlim_callback_id is not None:
            timeseries_ax.callbacks.disconnect(self.xlim_callback_id)
        for child in self.plot_frame.winfo_children():
            child.destroy()
        self.figure_canvas = None
        self.navigation_toolbar = None
        self.pick_connection_id = None
        self.press_connection_id = None
        self.motion_connection_id = None
        self.release_connection_id = None
        self.xlim_callback_id = None
        self.visible_mask = None
        self._last_synced_xlim = None
        self._box_select_origin = None
        self._box_select_axes = None
        self._box_select_button = None
        self._box_select_dragged = False
        self.plot_artists = {}

    def _on_timeseries_xlim_changed(self, _axis: object) -> None:
        self._sync_plots_to_time_window(draw=True)

    def _toolbar_owns_left_drag(self) -> bool:
        """True when the navigation toolbar zoom/pan tool is active."""
        toolbar = self.navigation_toolbar
        if toolbar is None:
            return False
        mode = getattr(toolbar, "mode", None)
        if mode is None:
            return False
        name = getattr(mode, "name", None)
        if isinstance(name, str):
            return name.upper() not in ("", "NONE")
        text = str(mode).strip().lower()
        return bool(text) and text not in ("none", "nonemode")

    def _resolve_box_select_axes(self, inaxes: object | None) -> object | None:
        """Map the clicked axes to the scatter plot used for selection."""
        if inaxes is None:
            return None
        timeseries_ax = self.plot_artists.get("timeseries_axis")
        direction_ax = self.plot_artists.get("direction_axis")
        polar_ax = self.plot_artists.get("polar_axis")
        # The direction twin sits under a transparent timeseries patch, so clicks
        # often report direction_axis even when the user is aiming at wind speed.
        if inaxes is timeseries_ax or inaxes is direction_ax:
            return timeseries_ax
        if inaxes is polar_ax:
            return polar_ax
        return None

    @staticmethod
    def _is_left_button(button: object | None) -> bool:
        return button in (MouseButton.LEFT, 1)

    @staticmethod
    def _is_right_button(button: object | None) -> bool:
        return button in (MouseButton.RIGHT, 3)

    def _on_mouse_press(self, event: object) -> None:
        button = getattr(event, "button", None)
        # Same gesture as toolbar zoom: left-drag selects when zoom/pan is off.
        # Right-drag also selects, but only when zoom/pan is not active.
        if self._is_left_button(button):
            if self._toolbar_owns_left_drag():
                return
        elif self._is_right_button(button):
            if self._toolbar_owns_left_drag():
                return
        else:
            return

        axes = self._resolve_box_select_axes(getattr(event, "inaxes", None))
        if axes is None:
            return
        x = getattr(event, "x", None)
        y = getattr(event, "y", None)
        if x is None or y is None:
            return
        self._box_select_origin = (float(x), float(y))
        self._box_select_axes = axes
        self._box_select_button = button
        self._box_select_dragged = False

    def _on_mouse_motion(self, event: object) -> None:
        if self._box_select_origin is None or self.navigation_toolbar is None:
            return
        x0, y0 = self._box_select_origin
        x = getattr(event, "x", None)
        y = getattr(event, "y", None)
        if x is None or y is None:
            return
        x1, y1 = float(x), float(y)
        if abs(x1 - x0) >= 5 or abs(y1 - y0) >= 5:
            self._box_select_dragged = True
        if not self._box_select_dragged:
            return
        self.navigation_toolbar.draw_rubberband(event, x0, y0, x1, y1)

    def _cancel_box_select(self) -> None:
        if self.navigation_toolbar is not None and self._box_select_dragged:
            self.navigation_toolbar.remove_rubberband()
        self._box_select_origin = None
        self._box_select_axes = None
        self._box_select_button = None
        self._box_select_dragged = False

    def _on_mouse_release(self, event: object) -> None:
        if self._box_select_origin is not None:
            button = getattr(event, "button", None)
            started = self._box_select_button
            same_button = button == started or (
                self._is_left_button(button) and self._is_left_button(started)
            ) or (
                self._is_right_button(button) and self._is_right_button(started)
            )
            if same_button:
                if self._box_select_dragged:
                    self._finish_box_select(event)
                else:
                    # Plain click: leave point-picking to handle selection.
                    self._cancel_box_select()
            return
        # Toolbar zoom/pan finishes on mouse release; force a final sync.
        self._sync_plots_to_time_window(draw=True)

    def _finish_box_select(self, event: object) -> None:
        origin = self._box_select_origin
        axes = self._box_select_axes
        self._box_select_origin = None
        self._box_select_axes = None
        self._box_select_button = None
        dragged = self._box_select_dragged
        self._box_select_dragged = False
        if self.navigation_toolbar is not None and dragged:
            self.navigation_toolbar.remove_rubberband()
        if origin is None or axes is None or self.active_data is None:
            return

        x0, y0 = origin
        x = getattr(event, "x", None)
        y = getattr(event, "y", None)
        x1 = float(x) if x is not None else x0
        y1 = float(y) if y is not None else y0
        if abs(x1 - x0) < 5 and abs(y1 - y0) < 5:
            return

        if axes is self.plot_artists.get("timeseries_axis"):
            artist = self.plot_artists.get("timeseries_points")
        elif axes is self.plot_artists.get("polar_axis"):
            artist = self.plot_artists.get("polar_points")
        else:
            return
        if artist is None:
            return

        positions = self._positions_in_display_rect(artist, x0, y0, x1, y1)
        if (
            axes is self.plot_artists.get("polar_axis")
            and self.visible_mask is not None
            and positions.size
        ):
            positions = positions[self.visible_mask[positions]]
        if positions.size == 0:
            if not self._mouse_event_has_control(event):
                self.selected_row_ids.clear()
                self._selection_focus_id = None
                self._update_selection_artists()
                self._clear_information()
                if self.figure_canvas is not None:
                    self.figure_canvas.draw_idle()
                self._update_direction_correction_plots()
            return

        wind_speeds = np.asarray(self.plot_artists.get("wind_speeds", []), dtype=float)
        positions = positions[np.isfinite(wind_speeds[positions])]
        if positions.size == 0:
            return

        row_ids = {
            int(row_id)
            for row_id in self.active_data.iloc[positions][self.ROW_ID_COLUMN]
            .astype(int)
            .tolist()
        }
        if self._mouse_event_has_control(event):
            row_ids |= self.selected_row_ids
        focus_id = int(
            self.active_data.iloc[int(positions[-1])][self.ROW_ID_COLUMN]
        )
        self._select_row_ids(row_ids, focus_id=focus_id)

    @staticmethod
    def _positions_in_display_rect(
        artist: object,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> np.ndarray:
        offsets = np.asarray(artist.get_offsets(), dtype=float)
        if offsets.size == 0:
            return np.asarray([], dtype=int)
        pixels = np.asarray(
            artist.get_offset_transform().transform(offsets), dtype=float
        )
        x_min, x_max = sorted((x0, x1))
        y_min, y_max = sorted((y0, y1))
        finite = np.isfinite(pixels).all(axis=1)
        inside = (
            finite
            & (pixels[:, 0] >= x_min)
            & (pixels[:, 0] <= x_max)
            & (pixels[:, 1] >= y_min)
            & (pixels[:, 1] <= y_max)
        )
        return np.flatnonzero(inside)

    def _sync_plots_to_time_window(self, draw: bool = True) -> None:
        """Update polar and rose plots to the visible time-series window."""
        if self.active_data is None or not self.plot_artists:
            return

        timeseries_ax = self.plot_artists["timeseries_axis"]
        x_min, x_max = timeseries_ax.get_xlim()
        current_xlim = (float(x_min), float(x_max))
        if self._last_synced_xlim == current_xlim and self.visible_mask is not None:
            return
        self._last_synced_xlim = current_xlim

        # Use the plotted x-coordinates so the mask matches the zoom window units.
        time_numbers = np.asarray(
            self.plot_artists["timeseries_points"].get_offsets()[:, 0], dtype=float
        )
        mask = (time_numbers >= x_min) & (time_numbers <= x_max)
        self.visible_mask = mask

        wind_directions = np.asarray(self.plot_artists["wind_directions"], dtype=float)
        wind_speeds = np.asarray(self.plot_artists["wind_speeds"], dtype=float)
        polar_offsets = np.asarray(self.plot_artists["polar_offsets"], dtype=float).copy()

        if mask.any():
            filtered = polar_offsets.copy()
            filtered[~mask] = np.nan
            self.plot_artists["polar_points"].set_offsets(filtered)
            visible_speeds = wind_speeds[mask]
            finite_visible = np.isfinite(visible_speeds)
            if finite_visible.any():
                self.plot_artists["polar_axis"].set_rmax(
                    max(float(np.ceil(np.nanmax(visible_speeds))) + 1.0, 1.0)
                )
            finite_mask = mask & np.isfinite(wind_directions) & np.isfinite(wind_speeds)
            self.plot_artists["rose_axis"] = _draw_wind_rose(
                self.plot_artists["rose_axis"],
                wind_directions[finite_mask],
                wind_speeds[finite_mask],
                self.plot_artists["rose_bins"],
            )
        else:
            self.plot_artists["polar_points"].set_offsets(np.empty((0, 2)))
            self.plot_artists["rose_axis"] = _draw_wind_rose(
                self.plot_artists["rose_axis"],
                np.array([]),
                np.array([]),
                self.plot_artists["rose_bins"],
            )

        if self.selected_row_ids and self.active_data is not None:
            self._update_selection_artists()

        if draw and self.figure_canvas is not None:
            self.figure_canvas.draw_idle()

    @staticmethod
    def _mouse_event_has_control(mouse_event: object | None) -> bool:
        if mouse_event is None:
            return False
        key = getattr(mouse_event, "key", None)
        if isinstance(key, str):
            key_lower = key.lower()
            if "control" in key_lower or "ctrl" in key_lower:
                return True
        gui_event = getattr(mouse_event, "guiEvent", None)
        if gui_event is not None:
            # Tk: Control=0x4; Qt: ControlModifier=0x04000000
            state = int(getattr(gui_event, "state", 0) or 0)
            if state & 0x4 or state & 0x04000000:
                return True
        return False

    def _on_point_picked(self, event: object) -> None:
        mouse_event = getattr(event, "mouseevent", None)
        if mouse_event is not None and getattr(mouse_event, "button", None) in (
            MouseButton.RIGHT,
            3,
        ):
            return
        artist = getattr(event, "artist", None)
        if artist not in (
            self.plot_artists.get("polar_points"),
            self.plot_artists.get("timeseries_points"),
        ):
            return

        candidates = np.asarray(getattr(event, "ind", []), dtype=int)
        if candidates.size == 0:
            return

        if (
            artist is self.plot_artists.get("polar_points")
            and self.visible_mask is not None
        ):
            candidates = candidates[self.visible_mask[candidates]]
            if candidates.size == 0:
                return

        wind_speeds = np.asarray(self.plot_artists.get("wind_speeds", []), dtype=float)
        candidates = candidates[np.isfinite(wind_speeds[candidates])]
        if candidates.size == 0:
            return

        position = int(candidates[0])
        mouse_event = getattr(event, "mouseevent", None)
        if candidates.size > 1 and mouse_event is not None:
            offsets = np.asarray(self.plot_artists["polar_offsets"], dtype=float)
            if artist is self.plot_artists.get("timeseries_points"):
                offsets = artist.get_offsets()
            pixels = artist.get_offset_transform().transform(offsets[candidates])
            distances = np.square(pixels[:, 0] - mouse_event.x) + np.square(
                pixels[:, 1] - mouse_event.y
            )
            position = int(candidates[int(np.argmin(distances))])
        self._select_position(
            position, additive=self._mouse_event_has_control(mouse_event)
        )

    def _update_selection_artists(self) -> None:
        empty = np.empty((0, 2))
        timeseries_selection = self.plot_artists.get("timeseries_selection")
        polar_selection = self.plot_artists.get("polar_selection")
        if timeseries_selection is None or polar_selection is None:
            return

        if self.active_data is None or not self.selected_row_ids:
            timeseries_selection.set_offsets(empty)
            polar_selection.set_offsets(empty)
            return

        row_ids = self.active_data[self.ROW_ID_COLUMN].to_numpy()
        positions = np.flatnonzero(np.isin(row_ids, list(self.selected_row_ids)))
        if positions.size == 0:
            timeseries_selection.set_offsets(empty)
            polar_selection.set_offsets(empty)
            return

        time_offsets = self.plot_artists["timeseries_points"].get_offsets()[positions]
        timeseries_selection.set_offsets(time_offsets)

        polar_offsets = np.asarray(self.plot_artists["polar_offsets"], dtype=float)
        if self.visible_mask is not None:
            visible_positions = positions[self.visible_mask[positions]]
        else:
            visible_positions = positions
        if visible_positions.size:
            polar_selection.set_offsets(polar_offsets[visible_positions])
        else:
            polar_selection.set_offsets(empty)

    def _select_row_ids(
        self,
        row_ids: set[int],
        focus_id: int | None = None,
    ) -> None:
        if self.active_data is None:
            return

        valid_ids: set[int] = set()
        row_id_to_position: dict[int, int] = {}
        for position, row_id in enumerate(
            self.active_data[self.ROW_ID_COLUMN].astype(int).tolist()
        ):
            if row_id not in row_ids:
                continue
            row = self.active_data.iloc[position]
            speed = float(row["WS"])
            direction = float(row["WD"])
            if np.isfinite(speed) and np.isfinite(direction):
                valid_ids.add(row_id)
                row_id_to_position[row_id] = position

        self.selected_row_ids = valid_ids
        if not valid_ids:
            self._selection_focus_id = None
            self._update_selection_artists()
            self._clear_information()
            if self.figure_canvas is not None:
                self.figure_canvas.draw_idle()
            self._update_direction_correction_plots()
            return

        if focus_id in valid_ids:
            self._selection_focus_id = focus_id
        else:
            self._selection_focus_id = next(iter(valid_ids))
        self._update_selection_artists()
        self._update_information_for_position(
            row_id_to_position[self._selection_focus_id]
        )
        if self.figure_canvas is not None:
            self.figure_canvas.draw_idle()
        self._update_direction_correction_plots()

    def _select_position(self, position: int, additive: bool = False) -> None:
        if self.active_data is None or not 0 <= position < len(self.active_data):
            return

        row = self.active_data.iloc[position]
        speed = float(row["WS"])
        direction = float(row["WD"])
        if not np.isfinite(speed) or not np.isfinite(direction):
            if not additive:
                self.selected_row_ids.clear()
                self._selection_focus_id = None
                self._update_selection_artists()
                self._clear_information()
                if self.figure_canvas is not None:
                    self.figure_canvas.draw_idle()
                self._update_direction_correction_plots()
            return

        row_id = int(row[self.ROW_ID_COLUMN])
        if additive:
            if row_id in self.selected_row_ids:
                self.selected_row_ids.discard(row_id)
                if self._selection_focus_id == row_id:
                    self._selection_focus_id = (
                        next(iter(self.selected_row_ids), None)
                    )
            else:
                self.selected_row_ids.add(row_id)
                self._selection_focus_id = row_id
        else:
            self.selected_row_ids = {row_id}
            self._selection_focus_id = row_id

        if not self.selected_row_ids:
            self._selection_focus_id = None
            self._update_selection_artists()
            self._clear_information()
            if self.figure_canvas is not None:
                self.figure_canvas.draw_idle()
            self._update_direction_correction_plots()
            return

        self._update_selection_artists()
        focus_id = self._selection_focus_id
        if focus_id is None:
            focus_id = next(iter(self.selected_row_ids))
            self._selection_focus_id = focus_id
        focus_positions = np.flatnonzero(
            self.active_data[self.ROW_ID_COLUMN].to_numpy() == focus_id
        )
        if focus_positions.size:
            self._update_information_for_position(int(focus_positions[0]))

        if self.figure_canvas is not None:
            self.figure_canvas.draw_idle()
        self._update_direction_correction_plots()

    def _update_information_for_position(self, position: int) -> None:
        if self.active_data is None or not 0 <= position < len(self.active_data):
            self._clear_information()
            return

        row = self.active_data.iloc[position]
        speed = float(row["WS"])
        direction = float(row["WD"])
        timestamp = self.active_data.index[position]
        if hasattr(timestamp, "strftime"):
            time_text = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_text = str(timestamp)
        selected_count = len(self.selected_row_ids)
        if selected_count > 1:
            time_text = f"{time_text}  (+{selected_count - 1} more)"
        self.time_value.set(time_text)
        self.speed_value.set(f"{speed:.3f}")
        self.direction_value.set(f"{direction % 360:.2f}")
        if "WS_max" in self.active_data.columns:
            gust = float(row["WS_max"])
            self.gust_value.set(f"{gust:.3f}" if np.isfinite(gust) else "—")
        else:
            self.gust_value.set("—")
        if self._has_battery and "BattV" in self.active_data.columns:
            battery = float(row["BattV"])
            self.battery_value.set(
                f"{battery:.3f}" if np.isfinite(battery) else "—"
            )
        else:
            self.battery_value.set("—")
        self.delete_button.configure(
            state=tk.NORMAL if not self._is_raw_view() else tk.DISABLED
        )
        self._set_delete_tools_enabled(not self._is_raw_view())

    def _clear_information(self) -> None:
        self.time_value.set("—")
        self.speed_value.set("—")
        self.direction_value.set("—")
        self.gust_value.set("—")
        self.battery_value.set("—")
        self.delete_button.configure(state=tk.DISABLED)
        self._set_delete_tools_enabled(False)

    @staticmethod
    def _validate_deletion_note(proposed: str) -> bool:
        return len(proposed) <= 15

    def delete_selected(self) -> None:
        if self._is_raw_view():
            messagebox.showinfo(
                "Data filtering",
                "Switch to processed data to delete datapoints.",
                parent=self.root,
            )
            return
        if not self.selected_row_ids:
            return
        note = self.deletion_note.get().strip()
        for deleted_id in sorted(self.selected_row_ids):
            if deleted_id not in self.deleted_row_ids:
                self.deleted_row_ids.append(deleted_id)
            self.deletion_notes[deleted_id] = note
        self.deletion_note.set("")
        self.selected_row_ids.clear()
        self._selection_focus_id = None
        self._rebuild_plot(preserve_xlim=True)
        self._refresh_history_list()

    def open_deletion_history(self) -> None:
        if self.history_window is not None and self.history_window.winfo_exists():
            self.history_window.deiconify()
            self.history_window.lift()
            self.history_window.focus_force()
            self._refresh_history_list()
            return

        window = tk.Toplevel(self.root)
        window.title("Deletion history")
        window.geometry("780x360")
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self._close_history_window)
        self.history_window = window

        container = ttk.Frame(window, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        columns = ("timestamp", "speed", "direction", "gust", "notes")
        tree = ttk.Treeview(
            container,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        tree.heading("timestamp", text="Timestamp")
        tree.heading("speed", text="Wind speed (m/s)")
        tree.heading("direction", text="Direction (°)")
        tree.heading("gust", text="Wind gust (m/s)")
        tree.heading("notes", text="Deletion notes")
        tree.column("timestamp", width=160, anchor=tk.W)
        tree.column("speed", width=120, anchor=tk.E)
        tree.column("direction", width=110, anchor=tk.E)
        tree.column("gust", width=120, anchor=tk.E)
        tree.column("notes", width=140, anchor=tk.W)

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.history_tree = tree

        button_row = ttk.Frame(window)
        button_row.pack(pady=(0, 10))
        ttk.Button(
            button_row, text="Undo selected", command=self.undo_selected_deletion
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            button_row, text="Undo all", command=self.undo_all_deletions
        ).pack(side=tk.LEFT)
        self._refresh_history_list()

    def _close_history_window(self) -> None:
        if self.history_window is not None:
            self.history_window.destroy()
        self.history_window = None
        self.history_tree = None

    def _refresh_history_list(self) -> None:
        if self.history_tree is None or not self.history_tree.winfo_exists():
            return
        for item_id in self.history_tree.get_children():
            self.history_tree.delete(item_id)

        if self.original_data is None or not self.deleted_row_ids:
            return

        indexed = self.original_data.set_index(self.ROW_ID_COLUMN, drop=False)
        has_gust = "WS_max" in self.original_data.columns
        for row_id in reversed(self.deleted_row_ids):
            row = indexed.loc[row_id]
            source_position = int(row_id)
            timestamp = self.original_data.index[source_position]
            if hasattr(timestamp, "strftime"):
                timestamp_text = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp_text = str(timestamp)
            gust_text = f"{float(row['WS_max']):.3f}" if has_gust else "—"
            self.history_tree.insert(
                "",
                tk.END,
                iid=str(row_id),
                values=(
                    timestamp_text,
                    f"{float(row['WS']):.3f}",
                    f"{float(row['WD']) % 360:.2f}",
                    gust_text,
                    self.deletion_notes.get(row_id, ""),
                ),
            )

    def undo_selected_deletion(self) -> None:
        if self._is_raw_view():
            messagebox.showinfo(
                "Deletion history",
                "Switch to processed data to undo deletions.",
                parent=self.history_window or self.root,
            )
            return
        if self.history_tree is None:
            return
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showinfo(
                "Deletion history",
                "Select one or more deleted datapoints to undo.",
                parent=self.history_window,
            )
            return

        restored_ids = [int(item_id) for item_id in selection]
        restore_set = set(restored_ids)
        self.deleted_row_ids = [
            row_id for row_id in self.deleted_row_ids if row_id not in restore_set
        ]
        for row_id in restored_ids:
            self.deletion_notes.pop(row_id, None)
        self._rebuild_plot(preferred_row_id=restored_ids[0], preserve_xlim=True)
        self._refresh_history_list()

    def undo_all_deletions(self) -> None:
        if self._is_raw_view():
            messagebox.showinfo(
                "Deletion history",
                "Switch to processed data to undo deletions.",
                parent=self.history_window or self.root,
            )
            return
        if not self.deleted_row_ids:
            messagebox.showinfo(
                "Deletion history",
                "There are no deletions to undo.",
                parent=self.history_window or self.root,
            )
            return

        preferred_row_id = next(iter(self.deleted_row_ids), None)
        self.deleted_row_ids.clear()
        self.deletion_notes.clear()
        self._rebuild_plot(preferred_row_id=preferred_row_id, preserve_xlim=True)
        self._refresh_history_list()

    def _has_wind_data(self) -> bool:
        return self.original_data is not None and not self.original_data.empty

    def _parse_magnetic_coordinates(self) -> dict:
        if self.coordinate_mode_var.get() == "utm":
            try:
                easting = float(self.easting_entry.get())
                northing = float(self.northing_entry.get())
                utm_zone = int(float(self.zone_entry.get()))
                hemisphere = bool(self.bool_var2.get())
            except ValueError as exc:
                raise ValueError(
                    "Easting, Northing, and UTM zone must be valid numbers."
                ) from exc
            return {
                "Easting": easting,
                "Northing": northing,
                "utm_zone": utm_zone,
                "northern_hemisphere": hemisphere,
            }

        try:
            latitude = float(self.latitude_entry.get())
            longitude = float(self.longitude_entry.get())
        except ValueError as exc:
            raise ValueError(
                "Latitude and longitude must be valid numbers."
            ) from exc
        easting, northing, utm_zone, northern_hemisphere = lonlat2utm(
            longitude, latitude
        )
        return {
            "Easting": easting,
            "Northing": northing,
            "utm_zone": utm_zone,
            "northern_hemisphere": northern_hemisphere,
        }

    def _toggle_coordinate_mode(self) -> None:
        use_utm = self.coordinate_mode_var.get() == "utm"
        utm_widgets = (
            self.easting_label,
            self.easting_entry,
            self.northing_label,
            self.northing_entry,
            self.zone_label,
            self.zone_entry,
            self.hemisphere_label,
            self.radiobutton_north,
            self.radiobutton_south,
        )
        latlon_widgets = (
            self.latitude_label,
            self.latitude_entry,
            self.longitude_label,
            self.longitude_entry,
        )
        for widget in utm_widgets:
            if use_utm:
                widget.grid()
            else:
                widget.grid_remove()
        for widget in latlon_widgets:
            if use_utm:
                widget.grid_remove()
            else:
                widget.grid()

    def _parse_custom_timestamp(self):
        from datetime import datetime

        text = self.custom_date_var.get().strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        raise ValueError(
            "Custom date must use YYYY-MM-DD or YYYY-MM-DD HH:MM format."
        )

    def _resolve_magnetic_timestamp(self):
        if self.use_custom_date_var.get():
            return None, self._parse_custom_timestamp()
        if not self._has_wind_data():
            raise ValueError(
                "Load wind data to use the dataset midpoint, "
                "or enable a custom date."
            )
        return self.original_data, None

    def _toggle_custom_date_entry(self) -> None:
        state = "normal" if self.use_custom_date_var.get() else "disabled"
        self.custom_date_entry.configure(state=state)

    def _toggle_correction_type(self) -> None:
        use_complete = self.correction_type_var.get() == "complete"
        if use_complete:
            self.use_custom_date_var.set(False)
            self.custom_date_check.configure(state="disabled")
            self.custom_date_entry.configure(state="disabled")
            return
        if self._has_wind_data():
            self.custom_date_check.configure(state="normal")
        else:
            self.custom_date_check.configure(state="disabled")
            self.use_custom_date_var.set(True)
        self._toggle_custom_date_entry()

    def _show_magnetic_correction_figure(self, fig) -> None:
        for widget in self.declination_frame.winfo_children():
            widget.destroy()
        old_fig = self.fig3
        if old_fig is not None and old_fig is not fig:
            import matplotlib.pyplot as plt

            plt.close(old_fig)
        self.magnetic_fig = fig
        self.fig3 = fig
        self.canvas3 = FigureCanvasTkAgg(self.fig3, master=self.declination_frame)
        toolbar = NavigationToolbar2Tk(
            self.canvas3, self.declination_frame, pack_toolbar=False
        )
        toolbar.update()
        toolbar.grid(row=0, column=0, columnspan=1)
        self.canvas3.draw()
        self.canvas3.get_tk_widget().grid(row=1, column=0, pady=1, padx=1)

    def _direction_correction_window_open(self) -> bool:
        window = self._dir_corr_window
        return window is not None and bool(window.winfo_exists())

    def _close_direction_correction(self) -> None:
        if self._dir_corr_rotation_trace is not None:
            try:
                self._dir_corr_rotation.trace_remove(
                    "write", self._dir_corr_rotation_trace
                )
            except tk.TclError:
                pass
            self._dir_corr_rotation_trace = None
        if self._dir_corr_window is not None:
            try:
                self._dir_corr_window.destroy()
            except tk.TclError:
                pass
        self._dir_corr_window = None
        self._dir_corr_canvas = None
        self._dir_corr_hist_ax = None
        self._dir_corr_polar_ax = None
        self._dir_corr_set_correct_button = None
        self._dir_corr_fit_label = None
        self._dir_corr_incorrect_ids.clear()
        self._dir_corr_rotation.set(0)

    def direction_correction_pressed(self) -> None:
        if not self._has_wind_data():
            messagebox.showinfo(
                "Direction correction",
                "Load wind data before opening direction correction.",
                parent=self.root,
            )
            return
        if self._is_raw_view():
            messagebox.showinfo(
                "Direction correction",
                "Switch to processed data to correct directions.",
                parent=self.root,
            )
            return
        if self._direction_correction_window_open():
            self._dir_corr_window.deiconify()
            self._dir_corr_window.lift()
            self._dir_corr_window.focus_force()
            self._sync_dir_corr_correct_button()
            self._update_direction_correction_plots()
            return

        from matplotlib.figure import Figure

        window = tk.Toplevel(self.root)
        window.title("Direction correction")
        window.geometry("980x760")
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self._close_direction_correction)
        self._dir_corr_window = window
        self._dir_corr_incorrect_ids.clear()
        self._dir_corr_rotation.set(0)

        plot_frame = ttk.Frame(window, padding=8)
        plot_frame.pack(fill=tk.BOTH, expand=True)

        figure = Figure(figsize=(9.0, 5.2), facecolor="whitesmoke")
        grid = figure.add_gridspec(1, 2, width_ratios=[1.55, 1.0], wspace=0.28)
        self._dir_corr_hist_ax = figure.add_subplot(grid[0, 0])
        self._dir_corr_polar_ax = figure.add_subplot(grid[0, 1], projection="polar")
        self._dir_corr_canvas = FigureCanvasTkAgg(figure, master=plot_frame)
        self._dir_corr_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(window, padding=(8, 0, 8, 10))
        controls.pack(fill=tk.X)
        controls.columnconfigure(1, weight=1)

        self._dir_corr_fit_label = ttk.Label(
            controls,
            text="Fit correlation: —",
        )
        self._dir_corr_fit_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))

        self._dir_corr_rotation_trace = self._dir_corr_rotation.trace_add(
            "write", lambda *_args: self._update_direction_correction_plots()
        )

        self._dir_corr_set_correct_button = ttk.Button(
            controls,
            text="Set correct distribution",
            command=self._dir_corr_set_correct,
            width=28,
        )
        self._dir_corr_set_correct_button.grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Label(
            controls,
            text=(
                "Step 1 (optional): Select and set data which represents the correct "
                "directional distribution. Skip if the offset is known from field notes."
            ),
        ).grid(row=1, column=1, sticky=tk.W, padx=(12, 0), pady=2)

        ttk.Button(
            controls,
            text="Set incorrect distribution",
            command=self._dir_corr_set_incorrect,
            width=28,
        ).grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Label(
            controls,
            text=(
                "Step 2 (required): Select and set data with incorrect directional distribution."
            ),
        ).grid(row=2, column=1, sticky=tk.W, padx=(12, 0), pady=2)

        ttk.Button(
            controls,
            text="Calculate correction rotation",
            command=self._dir_corr_calculate_rotation,
            width=28,
        ).grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Label(
            controls,
            text=(
                "Step 3 (optional): Calculate the rotation which will produce the best "
                "fit. Requires both correct and incorrect distributions."
            ),
        ).grid(row=3, column=1, sticky=tk.W, padx=(12, 0), pady=2)

        rotate_row = ttk.Frame(controls)
        rotate_row.grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Label(rotate_row, text="Rotate (°):").pack(side=tk.LEFT)
        ttk.Spinbox(
            rotate_row,
            from_=-180,
            to=180,
            textvariable=self._dir_corr_rotation,
            width=8,
            command=self._update_direction_correction_plots,
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(
            controls,
            text=(
                "Step 4: Explore manual rotation. Required when only incorrect data is "
                "set (field-known offset)."
            ),
        ).grid(row=4, column=1, sticky=tk.W, padx=(12, 0), pady=2)

        ttk.Button(
            controls,
            text="Apply correction",
            command=self._dir_corr_apply,
            width=28,
        ).grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Label(
            controls,
            text="Step 5: Once satisfied with the fit, apply correction to the data.",
        ).grid(row=5, column=1, sticky=tk.W, padx=(12, 0), pady=2)

        self._sync_dir_corr_correct_button()
        self._update_direction_correction_plots()

    def _sync_dir_corr_correct_button(self) -> None:
        button = self._dir_corr_set_correct_button
        if button is None:
            return
        button.configure(
            state=tk.DISABLED if self._dir_corr_correct_ids else tk.NORMAL
        )

    def _dir_corr_directions_for_ids(self, row_ids: set[int]) -> np.ndarray:
        if self.original_data is None or not row_ids:
            return np.asarray([], dtype=float)
        mask = self.original_data[self.ROW_ID_COLUMN].isin(row_ids)
        if self.deleted_row_ids:
            mask &= ~self.original_data[self.ROW_ID_COLUMN].isin(self.deleted_row_ids)
        values = pd.to_numeric(self.original_data.loc[mask, "WD"], errors="coerce")
        return values.to_numpy(dtype=float)

    def _dir_corr_speeds_for_ids(self, row_ids: set[int]) -> np.ndarray:
        if self.original_data is None or not row_ids:
            return np.asarray([], dtype=float)
        mask = self.original_data[self.ROW_ID_COLUMN].isin(row_ids)
        if self.deleted_row_ids:
            mask &= ~self.original_data[self.ROW_ID_COLUMN].isin(self.deleted_row_ids)
        values = pd.to_numeric(self.original_data.loc[mask, "WS"], errors="coerce")
        return values.to_numpy(dtype=float)

    def _dir_corr_all_directions(self) -> np.ndarray:
        if self.original_data is None:
            return np.asarray([], dtype=float)
        mask = pd.Series(True, index=self.original_data.index)
        if self.deleted_row_ids:
            mask &= ~self.original_data[self.ROW_ID_COLUMN].isin(self.deleted_row_ids)
        values = pd.to_numeric(self.original_data.loc[mask, "WD"], errors="coerce")
        return values.to_numpy(dtype=float)

    def _dir_corr_all_speeds(self) -> np.ndarray:
        if self.original_data is None:
            return np.asarray([], dtype=float)
        mask = pd.Series(True, index=self.original_data.index)
        if self.deleted_row_ids:
            mask &= ~self.original_data[self.ROW_ID_COLUMN].isin(self.deleted_row_ids)
        values = pd.to_numeric(self.original_data.loc[mask, "WS"], errors="coerce")
        return values.to_numpy(dtype=float)

    def _dir_corr_timestamps_for_ids(
        self, row_ids: set[int]
    ) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
        if self.original_data is None or not row_ids:
            return None, None
        mask = self.original_data[self.ROW_ID_COLUMN].isin(row_ids)
        if not mask.any():
            return None, None
        times = self.original_data.index[mask]
        return pd.Timestamp(times.min()), pd.Timestamp(times.max())

    def _dir_corr_row_ids_in_range(
        self,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> set[int]:
        if self.original_data is None:
            return set()
        index = self.original_data.index
        mask = (index >= start) & (index <= end)
        if self.deleted_row_ids:
            mask &= ~self.original_data[self.ROW_ID_COLUMN].isin(self.deleted_row_ids)
        wd = pd.to_numeric(self.original_data.loc[mask, "WD"], errors="coerce")
        finite = wd.notna().to_numpy()
        row_ids = self.original_data.loc[mask, self.ROW_ID_COLUMN].astype(int)
        return set(row_ids.to_numpy()[finite].tolist())

    def _dir_corr_previously_corrected_ids(self) -> set[int]:
        corrected: set[int] = set()
        for entry in self.direction_correction_history:
            ids = entry.get("incorrect_row_ids")
            if ids:
                corrected.update(int(row_id) for row_id in ids)
                continue
            start = entry.get("incorrect_start")
            end = entry.get("incorrect_end")
            if start is not None and end is not None:
                corrected |= self._dir_corr_row_ids_in_range(
                    pd.Timestamp(start), pd.Timestamp(end)
                )
        return corrected

    def _dir_corr_format_overlap_ranges(self, overlapped_ids: set[int]) -> str:
        if self.original_data is None or not overlapped_ids:
            return ""
        mask = self.original_data[self.ROW_ID_COLUMN].isin(overlapped_ids)
        times = sorted(pd.Timestamp(ts) for ts in self.original_data.index[mask])
        if not times:
            return ""
        ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        start = times[0]
        prev = times[0]
        for current in times[1:]:
            if current - prev > pd.Timedelta(minutes=10):
                ranges.append((start, prev))
                start = current
            prev = current
        ranges.append((start, prev))
        lines = []
        for range_start, range_end in ranges:
            lines.append(
                f"{range_start.strftime('%Y-%m-%d %H:%M')} – "
                f"{range_end.strftime('%Y-%m-%d %H:%M')}"
            )
        return "\n".join(lines)

    def _dir_corr_set_correct(self) -> None:
        if self._dir_corr_correct_ids:
            return
        if not self.selected_row_ids:
            messagebox.showinfo(
                "Direction correction",
                "Select data in the main window first.",
                parent=self._dir_corr_window or self.root,
            )
            return
        self._dir_corr_correct_ids = set(self.selected_row_ids)
        self._sync_dir_corr_correct_button()
        self._update_direction_correction_plots()

    def _dir_corr_set_incorrect(self) -> None:
        if not self.selected_row_ids:
            messagebox.showinfo(
                "Direction correction",
                "Select data in the main window first.",
                parent=self._dir_corr_window or self.root,
            )
            return
        selected = set(self.selected_row_ids)
        already_corrected = self._dir_corr_previously_corrected_ids()
        overlapped = selected & already_corrected
        usable = selected - already_corrected
        if overlapped:
            ranges_text = self._dir_corr_format_overlap_ranges(overlapped)
            messagebox.showerror(
                "Direction correction",
                "Some selected dates were already corrected and will be excluded:\n"
                f"{ranges_text}",
                parent=self._dir_corr_window or self.root,
            )
        if not usable:
            messagebox.showinfo(
                "Direction correction",
                "No uncorrected points remain in the selection.",
                parent=self._dir_corr_window or self.root,
            )
            return
        self._dir_corr_incorrect_ids = usable
        self._update_direction_correction_plots()

    def _dir_corr_calculate_rotation(self) -> None:
        if not self._dir_corr_correct_ids or not self._dir_corr_incorrect_ids:
            messagebox.showinfo(
                "Direction correction",
                "Set both the correct and incorrect distributions first.",
                parent=self._dir_corr_window or self.root,
            )
            return
        correct = direction_density_histogram(
            self._dir_corr_directions_for_ids(self._dir_corr_correct_ids)
        )
        incorrect = direction_density_histogram(
            self._dir_corr_directions_for_ids(self._dir_corr_incorrect_ids)
        )
        rotation = best_rotation_degrees(correct, incorrect)
        self._dir_corr_rotation.set(int(rotation))
        self._update_direction_correction_plots()

    def _dir_corr_apply(self) -> None:
        if self._is_raw_view():
            messagebox.showinfo(
                "Direction correction",
                "Switch to processed data to apply corrections.",
                parent=self._dir_corr_window or self.root,
            )
            return
        if self.original_data is None or not self._dir_corr_incorrect_ids:
            messagebox.showinfo(
                "Direction correction",
                "Set an incorrect distribution before applying a correction.",
                parent=self._dir_corr_window or self.root,
            )
            return
        try:
            rotation = int(self._dir_corr_rotation.get())
        except (tk.TclError, TypeError, ValueError):
            messagebox.showerror(
                "Direction correction",
                "Rotate value must be an integer between -180 and 180.",
                parent=self._dir_corr_window or self.root,
            )
            return
        rotation = int(np.clip(rotation, -180, 180))
        if rotation == 0:
            messagebox.showinfo(
                "Direction correction",
                "Rotation is 0°. Nothing to apply.",
                parent=self._dir_corr_window or self.root,
            )
            return

        incorrect_ids = set(self._dir_corr_incorrect_ids)
        if self._dir_corr_correct_ids:
            correct_start, correct_end = self._dir_corr_timestamps_for_ids(
                self._dir_corr_correct_ids
            )
        else:
            correct_start, correct_end = None, None
        incorrect_start, incorrect_end = self._dir_corr_timestamps_for_ids(
            incorrect_ids
        )
        if incorrect_start is None or incorrect_end is None:
            messagebox.showerror(
                "Direction correction",
                "Could not determine timestamps for the incorrect distribution.",
                parent=self._dir_corr_window or self.root,
            )
            return
        if self._dir_corr_correct_ids and (
            correct_start is None or correct_end is None
        ):
            messagebox.showerror(
                "Direction correction",
                "Could not determine timestamps for the correct distribution.",
                parent=self._dir_corr_window or self.root,
            )
            return

        mask = self.original_data[self.ROW_ID_COLUMN].isin(incorrect_ids)
        current = pd.to_numeric(self.original_data.loc[mask, "WD"], errors="coerce")
        self.original_data.loc[mask, "WD"] = rotate_directions(
            current.to_numpy(dtype=float), rotation
        )
        self.direction_correction_history.append(
            {
                "correct_start": correct_start,
                "correct_end": correct_end,
                "incorrect_start": incorrect_start,
                "incorrect_end": incorrect_end,
                "rotation": rotation,
                "incorrect_row_ids": sorted(incorrect_ids),
            }
        )
        self._dir_corr_incorrect_ids.clear()
        self._dir_corr_rotation.set(0)
        self.view_store_var.set("processed")
        self._rebuild_plot(
            preferred_row_ids=set(self.selected_row_ids),
            preserve_xlim=True,
        )
        self._update_direction_correction_plots()
        self._refresh_direction_correction_history_list()
        messagebox.showinfo(
            "Direction correction",
            f"Applied {rotation:+d}° to the incorrect distribution.",
            parent=self._dir_corr_window or self.root,
        )

    @staticmethod
    def _format_fit_value(value: float) -> str:
        if not np.isfinite(value):
            return "—"
        return f"{value:.3f}"

    def _update_direction_correction_plots(self) -> None:
        if not self._direction_correction_window_open():
            return
        hist_ax = self._dir_corr_hist_ax
        polar_ax = self._dir_corr_polar_ax
        canvas = self._dir_corr_canvas
        if hist_ax is None or polar_ax is None or canvas is None:
            return

        try:
            rotation = int(self._dir_corr_rotation.get())
        except (tk.TclError, TypeError, ValueError):
            rotation = 0
        rotation = int(np.clip(rotation, -180, 180))

        all_dirs = self._dir_corr_all_directions()
        all_density = direction_density_histogram(all_dirs)
        display_all = peak_normalize(all_density)
        fit_all = peak_normalize(circular_smooth(all_density))

        hist_ax.clear()
        if np.any(display_all > 0):
            hist_ax.bar(
                DIR_BIN_CENTERS,
                display_all,
                width=1.0,
                align="center",
                color="skyblue",
                edgecolor="dodgerblue",
                linewidth=0.4,
                alpha=0.5,
                label="All directions",
            )
        hist_ax.plot(
            DIR_BIN_CENTERS,
            fit_all,
            color="navy",
            linewidth=1.4,
            label="All fit",
        )

        # Hide live selection once incorrect is set (fit workflow or manual-only).
        show_live = not self._dir_corr_incorrect_ids
        live_ids = set(self.selected_row_ids)
        live_dirs = self._dir_corr_directions_for_ids(live_ids)
        if (
            show_live
            and live_dirs.size
            and np.isfinite(live_dirs).any()
        ):
            if self._dir_corr_correct_ids:
                live_color = "crimson"
                live_edge = "darkred"
                live_label = "Selected (incorrect candidate)"
                live_fit_color = "darkred"
            else:
                live_color = "limegreen"
                live_edge = "darkgreen"
                live_label = "Selected (correct candidate)"
                live_fit_color = "darkgreen"
            finite_live = wrap_degrees(live_dirs[np.isfinite(live_dirs)])
            live_density = direction_density_histogram(finite_live)
            hist_ax.bar(
                DIR_BIN_CENTERS,
                peak_normalize(live_density),
                width=1.0,
                align="center",
                color=live_color,
                edgecolor=live_edge,
                linewidth=0.4,
                alpha=0.5,
                label=live_label,
            )
            hist_ax.plot(
                DIR_BIN_CENTERS,
                peak_normalize(circular_smooth(live_density)),
                color=live_fit_color,
                linewidth=1.3,
                label=f"{live_label} fit",
            )

        correct_density = None
        if self._dir_corr_correct_ids:
            correct_dirs = self._dir_corr_directions_for_ids(self._dir_corr_correct_ids)
            if correct_dirs.size and np.isfinite(correct_dirs).any():
                finite_correct = wrap_degrees(correct_dirs[np.isfinite(correct_dirs)])
                correct_density = direction_density_histogram(finite_correct)
                hist_ax.bar(
                    DIR_BIN_CENTERS,
                    peak_normalize(correct_density),
                    width=1.0,
                    align="center",
                    color="limegreen",
                    edgecolor="darkgreen",
                    linewidth=0.4,
                    alpha=0.5,
                    label="Correct distribution",
                )
                hist_ax.plot(
                    DIR_BIN_CENTERS,
                    peak_normalize(circular_smooth(correct_density)),
                    color="darkgreen",
                    linewidth=1.4,
                    label="Correct fit",
                )

        fit_text = "Fit correlation: —"
        if self._dir_corr_incorrect_ids:
            incorrect_dirs = self._dir_corr_directions_for_ids(
                self._dir_corr_incorrect_ids
            )
            if incorrect_dirs.size and np.isfinite(incorrect_dirs).any():
                finite_incorrect = incorrect_dirs[np.isfinite(incorrect_dirs)]
                before_density = direction_density_histogram(finite_incorrect)
                preview_dirs = rotate_directions(finite_incorrect, rotation)
                after_density = direction_density_histogram(preview_dirs)
                hist_ax.bar(
                    DIR_BIN_CENTERS,
                    peak_normalize(after_density),
                    width=1.0,
                    align="center",
                    color="crimson",
                    edgecolor="darkred",
                    linewidth=0.4,
                    alpha=0.5,
                    label=f"Incorrect (rotated {rotation:+d}°)",
                )
                hist_ax.plot(
                    DIR_BIN_CENTERS,
                    peak_normalize(circular_smooth(after_density)),
                    color="darkred",
                    linewidth=1.4,
                    label="Incorrect fit",
                )
                if correct_density is not None:
                    before = density_correlation(correct_density, before_density)
                    after = density_correlation(correct_density, after_density)
                    fit_text = (
                        "Fit correlation (vs correct): "
                        f"before {self._format_fit_value(before)} → "
                        f"after {self._format_fit_value(after)}"
                    )
                else:
                    fit_text = (
                        "Fit correlation: — (manual rotation; no correct distribution)"
                    )

        if self._dir_corr_fit_label is not None:
            self._dir_corr_fit_label.configure(text=fit_text)

        hist_ax.set_xlim(0, 360)
        hist_ax.set_ylim(0, 1.05)
        hist_ax.set_xlabel("Wind direction (°)")
        hist_ax.set_ylabel("Relative density (peak = 1)")
        hist_ax.set_title("Directional distributions")
        hist_ax.grid(True, alpha=0.3)
        hist_ax.legend(loc="best", fontsize=8)

        polar_ax.clear()
        polar_ax.set_theta_zero_location("N")
        polar_ax.set_theta_direction(-1)
        polar_ax.set_title("Preview", pad=12)

        def _scatter(
            ids: set[int],
            color: str,
            rotate: float = 0.0,
            *,
            zorder: float = 3,
        ) -> None:
            dirs = self._dir_corr_directions_for_ids(ids)
            speeds = self._dir_corr_speeds_for_ids(ids)
            if dirs.size == 0:
                return
            if rotate:
                dirs = rotate_directions(dirs, rotate)
            finite = np.isfinite(dirs) & np.isfinite(speeds)
            if not finite.any():
                return
            polar_ax.scatter(
                np.deg2rad(wrap_degrees(dirs[finite])),
                speeds[finite],
                s=8,
                c=color,
                alpha=0.5,
                edgecolors="none",
                zorder=zorder,
            )

        if self.original_data is not None:
            all_ids = set(
                self.original_data[self.ROW_ID_COLUMN].astype(int).tolist()
            )
            if self.deleted_row_ids:
                all_ids -= set(self.deleted_row_ids)
            _scatter(all_ids, "skyblue", zorder=1)

        if self._dir_corr_correct_ids:
            _scatter(self._dir_corr_correct_ids, "limegreen", zorder=3)
        if self._dir_corr_incorrect_ids:
            _scatter(
                self._dir_corr_incorrect_ids,
                "crimson",
                rotate=rotation,
                zorder=4,
            )
        elif show_live and live_ids:
            _scatter(
                live_ids,
                "crimson" if self._dir_corr_correct_ids else "limegreen",
                zorder=3,
            )

        r_values = []
        if self.original_data is not None:
            all_speeds = self._dir_corr_all_speeds()
            finite_all_speeds = all_speeds[np.isfinite(all_speeds)]
            if finite_all_speeds.size:
                r_values.append(float(np.nanmax(finite_all_speeds)))
        scatter_sets = [
            self._dir_corr_correct_ids,
            self._dir_corr_incorrect_ids,
        ]
        if show_live:
            scatter_sets.append(live_ids)
        for ids in scatter_sets:
            speeds = self._dir_corr_speeds_for_ids(ids)
            finite = speeds[np.isfinite(speeds)]
            if finite.size:
                r_values.append(float(np.nanmax(finite)))
        if r_values:
            polar_ax.set_rmax(max(float(np.ceil(max(r_values))) + 1.0, 1.0))
        else:
            polar_ax.set_rmax(1.0)

        canvas.draw_idle()

    def _load_direction_correction_history(
        self, corrections: pd.DataFrame
    ) -> None:
        self.direction_correction_history.clear()
        self._dir_corr_correct_ids.clear()
        for _, row in corrections.iterrows():
            try:
                incorrect_start = pd.Timestamp(row["Incorrect start"])
                incorrect_end = pd.Timestamp(row["Incorrect end"])
                rotation = int(float(row["Rotation [°]"]))
            except (TypeError, ValueError, KeyError):
                continue
            if pd.isna(incorrect_start) or pd.isna(incorrect_end):
                continue

            correct_start = row.get("Correct start", pd.NaT)
            correct_end = row.get("Correct end", pd.NaT)
            try:
                correct_start = pd.Timestamp(correct_start)
                correct_end = pd.Timestamp(correct_end)
            except (TypeError, ValueError):
                correct_start, correct_end = pd.NaT, pd.NaT
            if pd.isna(correct_start) or pd.isna(correct_end):
                correct_start, correct_end = None, None

            incorrect_ids = sorted(
                self._dir_corr_row_ids_in_range(incorrect_start, incorrect_end)
            )
            self.direction_correction_history.append(
                {
                    "correct_start": correct_start,
                    "correct_end": correct_end,
                    "incorrect_start": incorrect_start,
                    "incorrect_end": incorrect_end,
                    "rotation": rotation,
                    "incorrect_row_ids": incorrect_ids,
                }
            )
            if (
                not self._dir_corr_correct_ids
                and correct_start is not None
                and correct_end is not None
            ):
                self._dir_corr_correct_ids = self._dir_corr_row_ids_in_range(
                    correct_start, correct_end
                )

    def open_direction_correction_history(self) -> None:
        if (
            self._dir_corr_history_window is not None
            and self._dir_corr_history_window.winfo_exists()
        ):
            self._dir_corr_history_window.deiconify()
            self._dir_corr_history_window.lift()
            self._dir_corr_history_window.focus_force()
            self._refresh_direction_correction_history_list()
            return

        window = tk.Toplevel(self.root)
        window.title("Direction correction history")
        window.geometry("980x360")
        window.transient(self.root)
        window.protocol(
            "WM_DELETE_WINDOW", self._close_direction_correction_history
        )
        self._dir_corr_history_window = window

        container = ttk.Frame(window, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        columns = (
            "correct_start",
            "correct_end",
            "incorrect_start",
            "incorrect_end",
            "rotation",
        )
        tree = ttk.Treeview(
            container,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        tree.heading("correct_start", text="Correct start")
        tree.heading("correct_end", text="Correct end")
        tree.heading("incorrect_start", text="Incorrect start")
        tree.heading("incorrect_end", text="Incorrect end")
        tree.heading("rotation", text="Rotation (°)")
        tree.column("correct_start", width=160, anchor=tk.W)
        tree.column("correct_end", width=160, anchor=tk.W)
        tree.column("incorrect_start", width=160, anchor=tk.W)
        tree.column("incorrect_end", width=160, anchor=tk.W)
        tree.column("rotation", width=100, anchor=tk.E)

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self._dir_corr_history_tree = tree

        ttk.Button(
            window,
            text="Undo",
            command=self.undo_selected_direction_correction,
        ).pack(pady=(0, 10))
        self._refresh_direction_correction_history_list()

    def _close_direction_correction_history(self) -> None:
        if self._dir_corr_history_window is not None:
            try:
                self._dir_corr_history_window.destroy()
            except tk.TclError:
                pass
        self._dir_corr_history_window = None
        self._dir_corr_history_tree = None

    @staticmethod
    def _format_history_timestamp(value: object) -> str:
        if value is None:
            return "—"
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError):
            return "—"
        if pd.isna(timestamp):
            return "—"
        if hasattr(timestamp, "strftime"):
            return timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)

    def _refresh_direction_correction_history_list(self) -> None:
        tree = self._dir_corr_history_tree
        if tree is None or not tree.winfo_exists():
            return
        for item_id in tree.get_children():
            tree.delete(item_id)
        for index, entry in enumerate(reversed(self.direction_correction_history)):
            source_index = len(self.direction_correction_history) - 1 - index
            tree.insert(
                "",
                tk.END,
                iid=str(source_index),
                values=(
                    self._format_history_timestamp(entry["correct_start"]),
                    self._format_history_timestamp(entry["correct_end"]),
                    self._format_history_timestamp(entry["incorrect_start"]),
                    self._format_history_timestamp(entry["incorrect_end"]),
                    f"{int(entry['rotation']):+d}",
                ),
            )

    def undo_selected_direction_correction(self) -> None:
        if self._is_raw_view():
            messagebox.showinfo(
                "Direction correction history",
                "Switch to processed data to undo direction corrections.",
                parent=self._dir_corr_history_window or self.root,
            )
            return
        tree = self._dir_corr_history_tree
        if tree is None:
            return
        selection = tree.selection()
        if not selection:
            messagebox.showinfo(
                "Direction correction history",
                "Select a correction to undo.",
                parent=self._dir_corr_history_window,
            )
            return
        if self.original_data is None:
            return

        index = int(selection[0])
        entry = self.direction_correction_history.pop(index)
        rotation = int(entry["rotation"])
        incorrect_ids = {
            int(row_id) for row_id in entry.get("incorrect_row_ids", [])
        }
        if not incorrect_ids:
            incorrect_ids = self._dir_corr_row_ids_in_range(
                pd.Timestamp(entry["incorrect_start"]),
                pd.Timestamp(entry["incorrect_end"]),
            )
        if incorrect_ids:
            mask = self.original_data[self.ROW_ID_COLUMN].isin(incorrect_ids)
            current = pd.to_numeric(
                self.original_data.loc[mask, "WD"], errors="coerce"
            )
            self.original_data.loc[mask, "WD"] = rotate_directions(
                current.to_numpy(dtype=float), -rotation
            )

        if not self.direction_correction_history:
            self._dir_corr_correct_ids.clear()
            self._sync_dir_corr_correct_button()
        self._dir_corr_incorrect_ids.clear()
        self._rebuild_plot(
            preferred_row_ids=set(self.selected_row_ids),
            preserve_xlim=True,
        )
        self._update_direction_correction_plots()
        self._refresh_direction_correction_history_list()

    def magnetic_correction_pressed(self) -> None:
        from datetime import datetime

        has_data = self._has_wind_data()
        self.popup1 = tk.Toplevel(self.root)
        self.popup1.title("Reference to geographic North")
        self.popup1.resizable(False, False)
        default_easting = 675461
        default_northing = 5405048
        default_zone = 18
        default_hemisphere = False
        default_lon, default_lat = utm2lonlat(
            default_easting,
            default_northing,
            utm_zone=default_zone,
            northern_hemisphere=default_hemisphere,
        )
        default_lon = round(default_lon, 4)
        default_lat = round(default_lat, 4)

        self.coordinate_mode_var = tk.StringVar(value="utm")
        self.coordinate_mode_label = tk.Label(
            self.popup1,
            width=15,
            text="Coordinates: ",
            font=("Calibri", 10, "bold"),
        )
        self.coordinate_mode_label.grid(sticky="W", row=0, column=0, pady=3, padx=3)
        coordinate_mode_frame = tk.Frame(self.popup1)
        coordinate_mode_frame.grid(sticky="W", row=0, column=1, pady=3, padx=3)
        self.utm_mode_radio = tk.Radiobutton(
            coordinate_mode_frame,
            text="UTM",
            variable=self.coordinate_mode_var,
            value="utm",
            command=self._toggle_coordinate_mode,
            font=("Calibri", 10),
        )
        self.latlon_mode_radio = tk.Radiobutton(
            coordinate_mode_frame,
            text="Lat/Lon",
            variable=self.coordinate_mode_var,
            value="latlon",
            command=self._toggle_coordinate_mode,
            font=("Calibri", 10),
        )
        self.utm_mode_radio.grid(row=0, column=0, padx=(0, 8))
        self.latlon_mode_radio.grid(row=0, column=1)

        east = tk.DoubleVar(value=default_easting)
        north = tk.DoubleVar(value=default_northing)
        z = tk.DoubleVar(value=default_zone)
        self.easting_label = tk.Label(
            self.popup1, width=15, text="Easting: ", font=("Calibri", 10, "bold")
        )
        self.easting_label.grid(sticky="W", row=1, column=0, pady=3, padx=3)
        self.easting_entry = tk.Entry(self.popup1, width=15, textvariable=east)
        self.easting_entry.grid(sticky="W", row=1, column=1, pady=3, padx=3)
        self.northing_label = tk.Label(
            self.popup1, width=15, text="Northing: ", font=("Calibri", 10, "bold")
        )
        self.northing_label.grid(sticky="W", row=2, column=0, pady=3, padx=3)
        self.northing_entry = tk.Entry(self.popup1, width=15, textvariable=north)
        self.northing_entry.grid(sticky="W", row=2, column=1, pady=3, padx=3)
        self.zone_label = tk.Label(
            self.popup1, width=15, text="UTM Zone: ", font=("Calibri", 10, "bold")
        )
        self.zone_label.grid(sticky="W", row=3, column=0, pady=3, padx=3)
        self.zone_entry = tk.Entry(self.popup1, width=15, textvariable=z)
        self.zone_entry.grid(sticky="W", row=3, column=1, pady=3, padx=3)
        self.bool_var2 = tk.BooleanVar(value=default_hemisphere)

        self.hemisphere_label = tk.Label(
            self.popup1, width=15, text="Hemisphere: ", font=("Calibri", 10, "bold")
        )
        self.hemisphere_label.grid(sticky="W", row=4, column=0, pady=3, padx=3)
        self.radiobutton_north = tk.Radiobutton(
            self.popup1,
            text="North",
            variable=self.bool_var2,
            value=True,
            font=("Calibri", 10),
        )
        self.radiobutton_south = tk.Radiobutton(
            self.popup1,
            text="South",
            variable=self.bool_var2,
            value=False,
            font=("Calibri", 10),
        )
        self.radiobutton_north.grid(row=5, column=0, pady=1, padx=1)
        self.radiobutton_south.grid(row=6, column=0, pady=1, padx=1)

        lat = tk.DoubleVar(value=default_lat)
        lon = tk.DoubleVar(value=default_lon)
        self.latitude_label = tk.Label(
            self.popup1, width=15, text="Latitude: ", font=("Calibri", 10, "bold")
        )
        self.latitude_label.grid(sticky="W", row=1, column=0, pady=3, padx=3)
        self.latitude_entry = tk.Entry(self.popup1, width=15, textvariable=lat)
        self.latitude_entry.grid(sticky="W", row=1, column=1, pady=3, padx=3)
        self.longitude_label = tk.Label(
            self.popup1, width=15, text="Longitude: ", font=("Calibri", 10, "bold")
        )
        self.longitude_label.grid(sticky="W", row=2, column=0, pady=3, padx=3)
        self.longitude_entry = tk.Entry(self.popup1, width=15, textvariable=lon)
        self.longitude_entry.grid(sticky="W", row=2, column=1, pady=3, padx=3)
        self._toggle_coordinate_mode()

        self.correction_type_var = tk.StringVar(value="simple")
        self.correction_type_label = tk.Label(
            self.popup1,
            width=15,
            text="Correction: ",
            font=("Calibri", 10, "bold"),
        )
        self.correction_type_label.grid(sticky="NW", row=7, column=0, pady=3, padx=3)
        self.simple_correction_radio = tk.Radiobutton(
            self.popup1,
            text="Simple (using midpoint timestamp)",
            variable=self.correction_type_var,
            value="simple",
            command=self._toggle_correction_type,
            font=("Calibri", 10),
        )
        self.simple_correction_radio.grid(sticky="W", row=7, column=1, pady=3, padx=3)
        self.complete_correction_radio = tk.Radiobutton(
            self.popup1,
            text="Complete (at each timestep)",
            variable=self.correction_type_var,
            value="complete",
            command=self._toggle_correction_type,
            font=("Calibri", 10),
        )
        self.complete_correction_radio.grid(sticky="W", row=8, column=1, pady=3, padx=3)
        if not has_data:
            self.complete_correction_radio.configure(state="disabled")

        self.use_custom_date_var = tk.BooleanVar(value=not has_data)
        self.custom_date_var = tk.StringVar(
            value=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        self.custom_date_check = tk.Checkbutton(
            self.popup1,
            text="Use custom date",
            variable=self.use_custom_date_var,
            command=self._toggle_custom_date_entry,
            font=("Calibri", 10),
        )
        self.custom_date_check.grid(
            sticky="W", row=9, column=0, columnspan=2, pady=(8, 3), padx=3
        )
        self.custom_date_entry = tk.Entry(
            self.popup1, width=18, textvariable=self.custom_date_var
        )
        self.custom_date_entry.grid(
            sticky="W", row=10, column=0, columnspan=2, pady=3, padx=3
        )
        if not has_data:
            self.custom_date_check.configure(state="disabled")
        self._toggle_correction_type()

        button_frame = tk.Frame(self.popup1)
        button_frame.grid(sticky="E", row=11, column=0, columnspan=2, pady=3, padx=3)
        self.calculate_button = ttk.Button(
            button_frame,
            text="Calculate",
            width=10,
            command=self.calculate_pressed,
        )
        self.calculate_button.grid(row=0, column=0, padx=(0, 5))
        self.apply_button = ttk.Button(
            button_frame,
            text="Apply",
            width=10,
            command=self.apply_pressed,
        )
        self.apply_button.grid(row=0, column=1)
        if not has_data or self.magnetic_correction_applied:
            self.apply_button.state(["disabled"])

        self.apply_status_var = tk.StringVar(
            value=(
                "Magnetic correction has been applied to the wind dataset."
                if self.magnetic_correction_applied
                else ""
            )
        )
        self.apply_status_label = tk.Label(
            self.popup1,
            textvariable=self.apply_status_var,
            font=("Calibri", 10),
            fg="green",
            wraplength=220,
            justify="left",
        )
        self.apply_status_label.grid(
            sticky="W",
            row=12,
            column=0,
            columnspan=2,
            pady=(0, 3),
            padx=3,
        )

        self.declination_frame = tk.Frame(
            self.popup1, bg="whitesmoke", width=300, height=400
        )
        self.declination_frame.grid(
            sticky="W",
            row=0,
            column=2,
            rowspan=13,
            columnspan=1,
            pady=0.5,
            padx=0.5,
        )
        if self.fig3 is not None:
            self._show_magnetic_correction_figure(self.fig3)

    def calculate_pressed(self) -> None:
        try:
            location_kwargs = self._parse_magnetic_coordinates()
            direction_df, timestamp = self._resolve_magnetic_timestamp()
        except ValueError as exc:
            messagebox.showerror(
                "Magnetic correction", str(exc), parent=self.popup1
            )
            return

        if timestamp is not None:
            t = timestamp
        else:
            t = direction_df.index[int(len(direction_df) / 2)]

        try:
            lon, lat, declination, error, fig = magnetic_correction(
                t,
                **location_kwargs,
            )
        except Exception as exc:
            messagebox.showerror(
                "Magnetic correction",
                f"Could not calculate correction:\n{exc}",
                parent=self.popup1,
            )
            return

        self.declination = declination
        self.error = error
        self.lat = lat
        self.lon = lon
        self._show_magnetic_correction_figure(fig)

    def apply_pressed(self) -> None:
        if self.magnetic_correction_applied:
            return
        if not self._has_wind_data():
            messagebox.showwarning(
                "Magnetic correction",
                "Wind data is not loaded.",
                parent=self.popup1,
            )
            return

        try:
            location_kwargs = self._parse_magnetic_coordinates()
        except ValueError as exc:
            messagebox.showerror(
                "Magnetic correction", str(exc), parent=self.popup1
            )
            return

        correction_type = self.correction_type_var.get()
        try:
            if correction_type == "complete":
                declination, error, lon, lat, fig = magnetic_correction_complete(
                    self.original_data,
                    **location_kwargs,
                )
            else:
                declination, error, lon, lat, fig = magnetic_correction_wind(
                    self.original_data,
                    **location_kwargs,
                )
        except Exception as exc:
            messagebox.showerror(
                "Magnetic correction",
                f"Could not apply correction:\n{exc}",
                parent=self.popup1,
            )
            return

        self.magnetic_correction_applied = True
        self.apply_button.state(["disabled"])

        self.declination = declination
        self.error = error
        self.lat = lat
        self.lon = lon
        self._show_magnetic_correction_figure(fig)
        self.apply_status_var.set(
            "Magnetic correction has been applied to the wind dataset."
        )
        self.view_store_var.set("processed")
        self._rebuild_plot(preferred_row_ids=set(self.selected_row_ids))
