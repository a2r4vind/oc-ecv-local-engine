# OC-ECV Local Engine — User Manual

**Version:** 0.1.0 (MVP)
**Last updated:** September 2026

---

## 1. What is OC-ECV Local Engine?

OC-ECV Local Engine is a local-first desktop application for ingesting, processing, analyzing, and visualizing Ocean Color and Essential Climate Variable (ECV) satellite data. It combines the browser-style interface and parameter selection familiar from NASA Giovanni with the offline, no-internet-required processing capabilities of SeaDAS.

Everything runs on your own machine. No files are uploaded anywhere, and no internet connection is required once the application is installed.

---

## 2. System Requirements

- Linux, **glibc version 2.39 or later** (e.g. Ubuntu 24.04 or newer). The
  application will fail to launch on older systems — see the note in
  Section 3 and item in Section 10 for detail.
- ~500MB free disk space for the application itself
- Additional disk space for your data files and local query cache (grows over time with usage — see Section 8)

**Not sure what glibc version your system has?** Run this in a terminal:
```bash
ldd --version
```
The first line shows your glibc version. If it's below 2.39, the packaged
application will not run on this machine (see Section 10).

---

## 3. Installation

The application is distributed as a standalone `.AppImage` file — no system installation, package manager, or admin rights required.

1. Download `oc-ecv-local_engine_0.1.0_amd64.AppImage`.
2. Make it executable:
   ```bash
   chmod +x oc-ecv-local_engine_0.1.0_amd64.AppImage
   ```
3. Launch it:
   ```bash
   ./oc-ecv-local_engine_0.1.0_amd64.AppImage
   ```

The application window should open within a few seconds. A local backend process starts automatically in the background — you do not need to start or manage it separately.

> **Note:** `.deb` and `.rpm` installer packages are also produced alongside the AppImage during builds, for users who prefer a system package manager. All three formats (`.AppImage`, `.deb`, `.rpm`) were built on Ubuntu 24.04 and require glibc 2.39+ on the machine running them — see Section 2. This is not specific to one package format; a system too old for the AppImage will also be too old for `.deb`/`.rpm`.

> **If the app fails to launch with an error mentioning `GLIBC_2.38` or `GLIBC_2.39` not found:** your system's glibc version is older than what this build requires. This is a known limitation (Section 10), not a corrupted download — redownloading or re-extracting will not fix it. The application currently requires Ubuntu 24.04 or an equivalently recent Linux distribution.

---

## 4. Loading a File

On launch, you'll see a file ingestion screen.

- **Drag and drop** a NetCDF (`.nc`), HDF, or GeoTIFF file directly onto the drop zone, **or**
- Click **Browse Files** to select a file using the system file picker.

> **Note:** if you're running inside WSL/WSLg, drag-and-drop from Windows File Explorer into the app window may not work reliably (a known WSL/Windows boundary limitation). Use **Browse Files** instead — it works identically and reliably in all environments.

Once loaded, the app displays the file's metadata: available variables, dimensions, spatial bounds, and time coverage.

---

## 5. Understanding the Interface

After a file loads, the main workspace has:

- **A persistent map** (center), showing the file's spatial coverage and your query results as a colored raster or point overlay.
- **Colormap selector** (Viridis / Ocean / Jet) and an **opacity slider** — these apply instantly with no need to re-run a query.
- **A color-scale legend**, showing the value range for whatever variable is currently displayed.
- **Five tabs** on the left, each a different way to work with your data:

| Tab | Purpose |
|---|---|
| **Query** | Select a variable, draw or type a bounding box, optionally set a date range, and compute summary statistics + a raster/point visualization for that region |
| **Time Series** | Plot a variable's values over time — either within a single multi-time-step file, or aggregated across a directory of files (e.g. a batch of satellite passes) |
| **Histogram** | View the distribution of a variable's values within a query region |
| **Scatter** | Plot two variables against each other to explore correlation within a query region |
| **History** | Browse your past queries — file, variable, bounding box, and when each was run |

Each tab keeps its own independent bounding box and settings — switching tabs doesn't lose your work on another tab. Colormap and opacity preferences persist across file switches, so you don't need to reset them each time.

---

## 6. Running a Query

1. Select a variable from the **Variable (ECV)** dropdown — only variables actually present in your loaded file are shown.
2. Set a bounding box either by:
   - Typing latitude/longitude values directly into the four fields, or
   - Using the bounding-box drawing tool on the map (click the dotted-rectangle icon, then click-and-drag on the map).
3. If your file has multiple time steps, optionally set a date range.
4. Click **Run Query**.

Results appear as:
- A colored raster or point overlay on the map, using your selected colormap.
- A statistics panel: valid pixel count and fraction, mean, min, max, and standard deviation.

> **A low "valid pixel fraction" is often normal, not an error.** Real satellite passes have cloud cover, sun glint, and land masking that can leave large portions of any given region without usable data. If a query returns very few valid pixels, try a different date/file, or a region known to have clearer conditions, before assuming something is wrong.

> **An error saying the bounding box doesn't overlap the file** means your box and the file's actual coverage don't intersect — this is common with single-pass swath files (each covers only a narrow geographic strip). Check the file's spatial bounds shown at ingestion time and adjust your box accordingly.

---

## 7. Supported Climate Variables

| Category | Variables |
|---|---|
| Ocean Color & Biogeochemistry | Chlorophyll-a, Remote Sensing Reflectance, CDOM, Particulate Organic Carbon, Normalized Fluorescence Line Height |
| Physical Oceanography | Sea Surface Temperature, Sea Surface Height, Sea Surface Salinity, Ocean Surface Vector Winds |
| Energy & Air-Sea Interaction | Photosynthetically Active Radiation, Aerosol Optical Depth |

**Not included in this release:** Sea Ice Concentration and Total Suspended Matter/Suspended Sediment Concentration are not supported in this version — synthetic test coverage exists internally, but no real-data access path was available in time for this release. These are candidates for a future update.

---

## 8. Exporting Your Results

From the Query tab, once you've run a query:

- **Export Data** — saves the queried region as a CSV table.
- **Export GeoTIFF/NetCDF** — saves a georeferenced raster file, suitable for opening in GIS software (e.g. QGIS).
- **Export Map** — saves the current map view as a PNG image.

A save dialog will prompt you for a location, or files will be written to a default export folder depending on your system configuration.

---

## 9. Local Data & Cache

The application maintains a local cache of previously computed query results to speed up repeated queries — a query you've run before will return near-instantly on a repeat. This cache lives in a per-user application data folder and persists across app restarts; it does not need to be managed manually. See the **History** tab to browse what's been cached.

---

## 10. Known Limitations

- **Minimum system requirement: glibc 2.39+ (e.g. Ubuntu 24.04 or later).**
  Confirmed by direct testing: the application (in all three package
  forms — `.AppImage`, `.deb`, `.rpm`) fails to launch on Ubuntu 22.04 and
  similarly-aged systems with errors referencing `GLIBC_2.38`/`GLIBC_2.39
  not found`. There is currently no workaround for older systems other
  than upgrading the host OS. See Section 2 for how to check your
  system's glibc version.
- **Bounding-box draw tool cursor:** when the draw tool is active, the mouse cursor does not visually change to a crosshair. The tool still works correctly — click-and-drag draws the box as expected. This is a cosmetic rendering quirk in some Linux desktop environments, not a functional issue.
- **Quality flag filtering** (cloud/land/glint masking) is supported by the underlying engine but not yet exposed as a UI control in this release.

---

## 11. Getting Help

If you encounter an issue not covered here, note:
- The file you were working with and its structure (single-pass swath vs. multi-time-step gridded file)
- The exact variable, bounding box, and date range used
- Any error message shown

and pass this along to the development team for investigation.