# AGNIVEDH — GIS Hotspot Intelligence

Agnivedh is a real-data GIS intelligence prototype for the SIH26162 problem: using NASA FIRMS, WorldCover and OpenStreetMap context to classify thermal detections, identify persistent/recurrent thermal sources, compare current activity with historical baselines, and prioritize events for investigation.

## Problem-to-solution architecture

```text
NASA FIRMS 2024 detection
        ↓
Runtime feature/context integrity
        ↓
Spatio-temporal source history
        ↓
Fire Evidence / Fire Confidence
        ↓
Real XGBoost source classification
        ↓
Persistent / recurrent / abnormal behaviour
        ↓
2022-2023 leakage-safe historical baseline
        ↓
Raw baseline deviation → relative 0-100 score
        ↓
OSM industrial / mine / forest context
        ↓
Deterministic operational risk
        ↓
Existing React + Leaflet GIS dashboard
        ↓
Explainable evidence chain + source history
```

The design deliberately separates three questions: **is there evidence of a fire-like event, what source does it resemble, and does its behaviour deserve attention?** A high source-class confidence is never treated as proof that a fire occurred.

### What the prototype adds beyond a raw hotspot map

- **Fire Confidence:** FIRMS confidence, brightness, FRP, spatial clustering and short-term persistence are combined into a conservative evidence score. It is explicitly not a calibrated probability of ground-truth fire.
- **Source History:** the selected detection is compared with prior 2024 detections within a 5 km spatial neighbourhood. The UI reports first/last seen date, active days, detection count, span and a compact timeline. Repeated detections are described as persistent/recurrent thermal activity, not as one continuous fire.
- **Abnormal persistence:** a persistent source with a current FRP spike relative to its local prior median is surfaced for review.
- **Industrial context:** OSM is used as evidence around the selected detection rather than merely as map decoration.
- **Historical deviation:** raw FRP deviation is preserved and a relative 0-100 score is calculated against the maximum absolute deviation in the currently loaded 2024 date/day-night comparison set.
- **2024 held-out validation:** 2024 remains unseen during model fitting. Independent incident/news/satellite evidence can be used after inference to validate selected events; it is not used as training input.

The existing dashboard layout is retained. The source-history panel is an additive intelligence block inside the existing selected-hotspot panel; no new framework or dashboard redesign is introduced.

## Dataset used for training

The supplied real FIRMS-derived labeled dataset is:

```text
backend/data/training_source/train_2022_2023_clean.csv
```

It contains **1,101,314 labeled observations** from 2022 and 2023. No synthetic observations are used for model training. Labels were constructed from WorldCover/OSM evidence, so the resulting ML metrics measure agreement with that labeling methodology rather than independent ground-truth fire occurrence.

The target mapping is:

- `FOREST` → `Wildfire`
- `AGRICULTURAL` → `Agriculture`
- `INDUSTRIAL` → `Industry`
- `UNKNOWN` → `Other`
- `URBAN_WASTE` → `Other`

The shipped classifier uses inference-available `worldcover_code` as contextual input. The runtime now preserves this field from the 2024 CSV so the deployed model receives the same feature contract used during training.

## Temporal ML protocol

```text
2022 labeled observations
        ↓
forward validation
        ↓
2023 labeled observations
        ↓
FINAL TRAINING: 2022 + 2023
        ↓
2024 real hotspot observations
        ↓
UNTOUCHED FINAL TEST
```

This is chronological evaluation rather than a random row split. The 2024 target/source labels are never used as inference features or for fitting.

### Shipped model

```text
Model: XGBClassifier_worldcover_context_balanced08
Training years: 2022, 2023
Forward validation: 2023
Final test year: 2024
Training rows: 1,101,314
Final test rows: 552,312
```

Configuration:

```text
n_estimators = 20
max_depth = 6
learning_rate = 0.08
subsample = 0.90
colsample_bytree = 0.90
max_bin = 96
tree_method = hist
random_state = 42
class weighting = inverse-frequency^0.8
LOW label-confidence weight = 0.5
```

### Forward validation: 2022 → 2023

```text
Accuracy        99.43%
Macro Precision 92.38%
Macro Recall    96.72%
Macro F1        94.28%
Weighted F1     99.47%
```

### Final held-out test: 2022+2023 → 2024

```text
Accuracy        94.82%
Macro Precision 90.37%
Macro Recall    81.51%
Macro F1        82.57%
Weighted F1     93.75%
```

The 2024 result includes a meaningful class-imbalance/shift caveat: Industry recall is **28.01%** with F1 **41.59%**, while Agriculture and Wildfire have much higher recall. This is why Agnivedh uses the classifier as one evidence layer rather than presenting its class probability as a claim of actual fire occurrence.

Saved artifacts:

```text
backend/models/fireops_classifier.joblib
backend/models/feature_names.json
backend/models/label_mapping.json
backend/models/model_metrics.json
backend/models/model_comparison.csv
backend/models/feature_importance.json
backend/models/confusion_matrix.png
backend/models/baseline_profiles.json
```

## 2024 runtime data

The supplied real 2024 hotspot file is:

```text
backend/data/hotspots_2024.csv
```

It contains **552,312** observations for 2024. The runtime preserves the detector measurements and contextual WorldCover/source-evidence fields. Prediction uses only the feature contract expected by the saved classifier.

Example:

```text
GET /api/hotspots/query?year=2024&acq_date=2024-03-15&daynight=D
```

The response contains the real observations plus model classification, model distribution, leakage-safe baseline comparison, relative deviation score, derived risk features and deterministic risk.

## Persistence and event behaviour

FIRMS detections arrive as individual satellite observations on different dates. Agnivedh therefore does **not** assume that one detection equals one fire. For a selected detection, the source-history engine searches prior 2024 observations in a 5 km neighbourhood and builds: detection count, active days, first/last seen dates, duration span, local prior median FRP, current FRP spike ratio, and a compact date-level timeline.

Behaviour is interpreted as:

```text
Few/short-lived detections  → TRANSIENT ACTIVITY
Repeated detections          → RECURRENT THERMAL ACTIVITY
Repeated + long span         → PERSISTENT THERMAL SOURCE
Persistent + FRP spike       → ABNORMAL / REVIEW
```

This distinction matters for SIH26162 because a persistent industrial thermal source and an accidental fire can occupy the same geographic area but exhibit different temporal behaviour. Persistence is therefore evidence, not an automatic industrial-fire label.

## Leakage-safe historical baseline

The classifier and baseline are separate systems. For a selected 2024 date, the baseline uses observations strictly before that date for the comparable temporal/spatial context; when insufficient history exists, the saved 2022-2023 baseline artifact is used as fallback.

The comparison retains raw deviation and additionally exposes:

```text
baseline_deviation_score: 0-100
baseline_deviation_reference: maximum absolute deviation in the loaded date/day-night set
```

Thus the raw number is auditable while the UI can communicate relative abnormality consistently.

## API

```text
GET /api/health
GET /api/hotspots
GET /api/hotspots/{id}
GET /api/hotspots/query?year=2024&acq_date=YYYY-MM-DD&daynight=D|N
GET /api/analysis/{id}
GET /api/osm/facility/{id}
GET /api/baseline/{region}
GET /api/nearby/{id}
GET /api/forecast
```

2024 IDs use the form `F24-<row-number>` in the runtime fetch layer.

## Run on Windows

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
```

### Frontend

Open another PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally:

```text
http://localhost:5173
```

Vite proxies `/api` to `http://127.0.0.1:8001`.

If an older Agnivedh backend is still running on port 8000, it can be left alone; this build uses port 8001 so the frontend cannot accidentally read stale API results.

## Retraining

Classifier — final real-life temporal setup:

```powershell
cd backend
python training/train_model.py `
  --train-data data/training_source/train_2022_2023_clean.csv `
  --test-data data/hotspots_2024.csv `
  --out models
```

This command first checks forward generalization from **2022 → 2023**, then refits the same XGBoost architecture on **all 2022+2023 labeled observations**, and finally evaluates once on the **2024 held-out hotspot file**. The 2024 labels are never used to fit the model.


Historical baseline artifact:

```powershell
python training/build_baseline.py --data data/training_source/train_2022_2023_clean.csv
```

The current project evaluation is:

```text
2022 real labeled data        → forward validation training
2023 real labeled data        → forward validation
2022 + 2023 real labeled data → FINAL MODEL TRAINING
2024 real hotspot data        → FINAL HELD-OUT TEST
```

## Model metadata

```text
backend/models/
├── fireops_classifier.joblib
├── feature_names.json
├── label_mapping.json
├── model_metrics.json
├── model_comparison.csv
├── feature_importance.json
├── confusion_matrix.png
├── baseline_profiles.json
└── data_quality_report.json
```

## Important limitations

- Current trained source classifier supports four real classes: Agriculture, Wildfire, Industry and Other.
- Gas Flare and Mining require additional real labeled observations before they can be added honestly.
- The 2024 runtime file is real FIRMS-derived data but does not contain the training target column; its labels are not used during prediction.
- Risk scoring remains a separate operational rule engine and is not a scientifically validated incident decision system.
- Live NASA/OSM network enrichment is not part of this local artifact.


## Backend smoke test

After installing the backend requirements, run:

```powershell
cd backend
python scripts/smoke_test.py
```

The smoke test checks the health endpoint, a real 2024 query, preservation of `worldcover_code`, relative baseline scoring, selected-hotspot analysis, fire evidence, source history, and rejection of unsupported years.

## Manual scenario validation

The dashboard now includes a compact **Manual Scenario Validation** panel directly below the 2024 FIRMS fetch controls. It accepts FIRMS-style observable inputs (coordinates, brightness, Bright T31, FRP, scan/track, confidence, date/time, day/night and type) and sends them through the **same trained classifier + 2022-2023 baseline + fire-evidence + GIS + risk pipeline** used for inference.

WorldCover is **not a NASA FIRMS field**. The manual validator therefore tries to resolve the ESA WorldCover 2021 v200 class from the entered coordinates. A manual WorldCover class/code override is available only as a fallback when the external lookup is unavailable. The UI explicitly warns when WorldCover could not be resolved; such a run should not be presented as a high-confidence validation result because WorldCover is an important model feature.

Endpoint:

```text
POST /api/validation/manual
```

## Industrial and critical-infrastructure context

Selected hotspots now use one bounded, cached OpenStreetMap context lookup instead of multiple repeated facility searches. The result shows:

- nearest named industrial facility + distance
- supported critical power context + distance
- explicit nuclear power classification only when OSM has a nuclear power-source tag

This context is an enrichment/alert layer and does **not** silently change the trained source-class prediction. OSM completeness can vary by area, so absence of a facility is not proof that no facility exists.

Exact military-installation discovery is not exposed as a public map-target layer. The critical-context feature is intentionally limited to generic critical infrastructure and explicitly tagged nuclear power facilities.

The selected-hotspot map no longer renders the duplicate permanent GIS-demand marker; nearby context remains available in the intelligence panel to keep Leaflet stable and avoid marker/viewport jitter.
