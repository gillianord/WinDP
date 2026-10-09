# WinDP — Wind Data Processing
Desktop app for processing wind speed and direction data. Includes the WMM Declination Calculator which can be used to apply a magnetic correction to the direction. This is generally done to refer anemometer data installed with a compass to geographic North. A midpoint date is used for the for the simple correction, while the complete correction applies the declination to each timestamp.  

## Features
- Load tab-delimited or Excel wind data files
- Interactive wind rose, polar scatter, and time-series plots with point selection
- Toggle raw (read-only) vs processed views and optional series overlays (gust, battery)
- Magnetic correction to geographic North via the World Magnetic Model (WMM) through [pygeomag](https://github.com/boxpet/pygeomag).
- Direction correction for incorrect anemometer orientation, with correction history
- Manual deletion of outliers with notes and deletion history and option to undo deletions
- Export raw and processed Excel workbooks (including deleted points and direction corrections that can be reloaded)

## Requirements
- Python 3.10+
- See `requirements.txt` (`numpy`, `pandas`, `matplotlib`, `windrose`, `openpyxl`,
  `xlsxwriter`, `pyproj`, `pygeomag`, `cartopy`)
- Internet access is needed for the shaded-relief basemap tiles used by magnetic correction
- A desktop environment with Tkinter (included with most standard Python installs on Windows)

## Setup
```powershell
cd "path\to\WinDP"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python WinDP.py