# AgniVedh v5 — Build/Test Report

## Changes verified

- Removed runtime use of hardcoded/mock nearby GIS templates.
- Selected FIRMS hotspot context now comes from the OSM lookup module.
- OSM lookup is a single cached context request for the selected hotspot instead of separate nearby + nearest requests.
- Query is name-first and explicitly covers industrial, military, nuclear and critical power context.
- Actual `name`, `official_name`, `operator` or `brand` is used; no synthetic facility names are generated.
- Public Overpass calls are bounded and sequential to avoid parallel load.
- UI shows a live `WAIT Ns` OSM lookup indicator while the selected hotspot is being enriched.
- Added live India/IST date and clock to the top bar.
- Selected hotspot map zoom was tightened for faster, closer interaction.
- Fixed runtime nearby GIS wiring so `nearby` no longer falls back to hardcoded templates.
- Validation helper now targets backend port 8001.

## Tests run in the build environment

- Python `compileall`: PASS
- `/api/health`: PASS (`200`, `mode=real_ml`)
- `/api/hotspots/query?year=2024&acq_date=2024-01-01`: PASS (`200`, real 2024 records returned)
- OSM parser contract test: PASS
- End-to-end `/api/analysis/F24-1597907` with controlled OSM response: PASS
  - named industrial context surfaced
  - named military context surfaced
  - named nuclear context surfaced
  - nearby list came from the same OSM context
- Frontend production build was not completed in this sandbox because the npm registry was not reachable, so `npm ci` could not finish. The source changes were inspected, but a successful Vite build should still be run on the target Windows machine.

## External-service limitation

The build environment could not reach public Overpass/DNS, so a live Overpass response could not honestly be claimed as tested here. The shipped code therefore includes bounded provider fallback and the offline OSM contract/end-to-end tests above. On the target machine, the final verification is the real selected-hotspot test with the backend running on port 8001.

## v7 OSM context hardening
- OSM query no longer requires a `name` tag at query time.
- Industrial landuse, industrial-tagged objects, industrial/warehouse buildings, works/factories/refineries, power infrastructure, nuclear tags, and military tags are queried directly.
- Unnamed OSM objects are retained with tag-derived labels such as `Industrial Facility`, `Military Installation`, `Critical Power Infrastructure`, or `Nuclear Facility`; no synthetic company/facility names are generated.
- Lookup is bounded to a 3 km primary radius with a 1 km fallback to reduce public Overpass load and timeout risk.
- Offline contract test and Python compileall passed.
- Live Overpass verification cannot be claimed from the build environment because outbound DNS/network access is unavailable; the application will perform the live lookup from the user's machine.
