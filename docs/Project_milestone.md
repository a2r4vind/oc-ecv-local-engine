# Project Milestones: OC-ECV Local Engine
**Deadline:** September 15, 2026  
**Total Timeline:** ~8 Weeks (July 21, 2026 – September 15, 2026)

---

## Phase 1: Environment Setup & Core Ingestion Engine
* **Timeline:** Week 1 (July 21, 2026 – July 27, 2026)
* **Goal:** Initialize repository, build local desktop shell, and establish local NetCDF/HDF/GeoTIFF reading via Python backend.

### Day-by-Day Task Breakdown
DONE* **Day 1 (July 21):** Initialize Tauri/Electron project wrapper and React frontend template. Verify local build pipeline.
* **Day 2 (July 22):** Configure Python virtual environment and sidecar communication (Local Loopback / IPC API).
* **Day 3 (July 23):** Implement local file ingestion script using `xarray` and `netCDF4` to parse sample Ocean Color ECV files ($Chl-a$, $R_{rs}$).
* **Day 4 (July 24):** Build file validation logic (checking spatial bounds, dimensions, and time coordinates).
* **Day 5 (July 25):** Create basic frontend drag-and-drop file uploader component connected to the local ingestion parser.
* **Day 6-7 (July 26–27):** **Buffer & Review:** Test parsing speed across multi-gigabyte sample files; fix dependency alignment issues.

### Phase 1 Exit Criteria (End of Week 1 Checkpoint)
* [ ] App successfully launches as a local desktop window.
* [ ] Local NetCDF/GeoTIFF files can be selected via UI and successfully parsed by the Python backend.
* [ ] Metadata (variables, dimensions, time steps) displays correctly on the frontend dashboard.

---

## Phase 2: Processing Pipeline & Subsetting Engine
* **Timeline:** Week 2-3 (July 28, 2026 – August 10, 2026)
* **Goal:** Implement spatial-temporal subsetting, quality flag masking, and statistical calculations for Ocean Color, Physical, and Energy ECVs.

### Day-by-Day Task Breakdown (Week 2)
* **Day 8 (July 28):** Build bounding-box coordinate slicing functions using `xarray`.
* **Day 9 (July 29):** Implement temporal filter logic (date-range extraction).
* **Day 10 (July 30):** Write masking algorithms for cloud/land pixels using dataset quality flags.
* **Day 11 (July 31):** Develop statistical calculation modules (spatial mean, min, max, standard deviation over subsetted arrays).
* **Day 12-14 (August 1–3):** Build parameter selection UI (Dropdowns for ECVs like $SST$, $Chl-a$, $PAR$, bounding box inputs, date pickers).

### Day-by-Day Task Breakdown (Week 3)
* **Day 15 (August 4):** Connect UI parameter selections to backend processing APIs.
* **Day 16 (August 5):** Optimize backend array processing using multi-threaded NumPy routines.
* **Day 17 (August 6):** Implement multi-file batch processing capability for time-series extraction.
* **Day 18 (August 7):** Build local caching layer (`joblib` or local SQLite index) for processed subset outputs.
* **Day 19-21 (August 8–10):** **Buffer & Review:** End-to-end testing of data processing pipelines for all 13 listed ECVs.

### Phase 2 Exit Criteria (End of Week 3 Checkpoint)
* [ ] User can select custom bounding boxes and date ranges on the UI.
* [ ] Backend correctly computes spatial subsets, applies data masks, and returns summary stats.
* [ ] Local cache prevents redundant computations on identical queries.

---

## Phase 3: Visualization & Interactive UI Dashboards
* **Timeline:** Week 4-5 (August 11, 2026 – August 24, 2026)
* **Goal:** Render spatial maps with WebGL color-ramps and generate analytical charts (time-series, histograms).

### Day-by-Day Task Breakdown (Week 4)
* **Day 22 (August 11):** Integrate Leaflet.js / Deck.gl into the React frontend.
* **Day 23 (August 12):** Implement dynamic WebGL color-ramps (*Viridis*, *Ocean*, *Jet*) for scalar raster rendering.
* **Day 24 (August 13):** Build map layer controls (opacity sliders, color scale legends).
* **Day 25 (August 14):** Integrate charting library (Chart.js / Plotly.js) for time-series anomaly trendlines.
* **Day 26-28 (August 15–17):** Build auxiliary plots (histograms and scatter plots for parameter correlation).

### Day-by-Day Task Breakdown (Week 5)
* **Day 29 (August 18):** Refine UI styling to mimic professional NASA Giovanni layouts.
* **Day 30 (August 19):** Implement interactive tooltips on maps and charts for exact pixel value inspection.
* **Day 31-35 (August 20–24):** **Integration & Stress Testing:** Connect visualization layers with backend processing outputs; optimize render speeds for large grids.

### Phase 3 Exit Criteria (End of Week 5 Checkpoint)
* [ ] Interactive map displays geospatial raster layers with custom color maps.
* [ ] Time-series trendlines and histograms update dynamically upon running a query.
* [ ] UI handles memory efficiently without browser/desktop crashes.

---

## Phase 4: Export Engines & Advanced Utilities
* **Timeline:** Week 6 (August 25, 2026 – August 31, 2026)
* **Goal:** Enable multi-format data and visualization exports, plus local workspace history tracking.

### Day-by-Day Task Breakdown
* **Day 36 (August 25):** Implement high-resolution PNG/JPEG map and plot export functionality.
* **Day 37 (August 26):** Implement raw data matrix export (.bin, CSV tables).
* **Day 38 (August 27):** Implement georeferenced raster export (.tif / GeoTIFF or NetCDF subset export).
* **Day 39 (August 28):** Build processing history panel tracking previous user queries and parameters.
* **Day 40-42 (August 29–31):** **Buffer & Review:** Validate export file integrity in external GIS software (e.g., QGIS).

### Phase 4 Exit Criteria (End of Week 6 Checkpoint)
* [ ] Users can export high-res visual snapshots (.png) and spatial data files (.tif, .csv).
* [ ] Processing history allows reloading past workflows instantly.

---

## Phase 5: Comprehensive Testing, Packaging & Deployment
* **Timeline:** Weeks 7-8 (September 1, 2026 – September 15, 2026)
* **Goal:** Debug edge cases, package installers for deployment, and prepare final documentation.

### Day-by-Day Task Breakdown
* **Day 43-46 (September 1–4):** Execute end-to-end integration testing across all ECV categories; resolve memory leaks and UI glitches.
* **Day 47-49 (September 5–7):** Configure electron-builder / Tauri bundler to produce standalone desktop installers (.exe, .dmg, .AppImage).
* **Day 50-52 (September 8–10):** Write comprehensive user manual and administrator deployment documentation.
* **Day 53-56 (September 11–15):** Final code clean-up, buffer days, and formal handover/deployment prep ahead of September 15.

### Phase 5 Exit Criteria (End of Week 8 / Deadline Checkpoint)
* [ ] Standalone application installers generated successfully for target operating systems.
* [ ] Zero critical bugs during offline execution.
* [ ] Project ready for formal deployment and mentor presentation.

