#!/usr/bin/env python
# coding: utf-8

"""Wind Data Processing — application entry point."""

import matplotlib

matplotlib.use("TkAgg")

import tkinter as tk

from WinDP_library.ui.app import WindDataProcessingApp

__all__ = ["WindDataProcessingApp"]


def main() -> None:
    root = tk.Tk()
    WindDataProcessingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
