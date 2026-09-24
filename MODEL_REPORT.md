# Agnivedh — Final Temporal ML Report

## Production protocol

```text
2022 labeled FIRMS observations
        ↓
Forward validation on 2023
        ↓
Final fit on ALL 2022 + 2023 labeled observations
        ↓
2024 real hotspot CSV
        ↓
Untouched final test
```

2024 labels are used only after prediction for the held-out evaluation. They are never used to fit the production model.

## Data

- Training source: `backend/data/training_source/train_2022_2023_clean.csv`
- Training rows: **1,101,314**
- Final test source: `backend/data/hotspots_2024.csv`
- Final test rows: **552,312**
- Classes: **Agriculture, Industry, Other, Wildfire**
- The original five contextual labels are mapped as `FOREST → Wildfire`, `AGRICULTURAL → Agriculture`, `INDUSTRIAL → Industry`, `URBAN_WASTE/UNKNOWN → Other`.

## Source/context classifier

**XGBClassifier — WorldCover-context + balanced training**

```text
n_estimators      = 20
max_depth         = 6
learning_rate     = 0.08
subsample         = 0.90
colsample_bytree  = 0.90
max_bin           = 96
tree_method       = hist
random_state      = 42
class weighting   = inverse_frequency^0.8
LOW label weight  = 0.5
```

WorldCover code is used as an inference-available geographic context feature. This is important because the supplied source labels were themselves constructed using WorldCover/OSM evidence. Consequently, the high classification metrics below measure agreement with that labeling methodology; they must **not** be interpreted as independent proof that a satellite detection was a real fire.

## Forward validation — 2022 → 2023

| Metric | Result |
|---|---:|
| Accuracy | **99.43%** |
| Macro Precision | **92.38%** |
| Macro Recall | **96.72%** |
| Macro F1 | **94.28%** |
| Weighted F1 | **99.47%** |

## Final held-out test — 2022+2023 → 2024

| Metric | Result |
|---|---:|
| Accuracy | **94.82%** |
| Macro Precision | **90.37%** |
| Macro Recall | **81.51%** |
| Macro F1 | **82.57%** |
| Weighted F1 | **93.75%** |

### 2024 per-class results

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Agriculture | 99.74% | 99.99% | 99.86% | 215,275 |
| Industry | 80.77% | 28.01% | 41.59% | 36,358 |
| Other | 82.95% | 98.43% | 90.03% | 107,573 |
| Wildfire | 98.03% | 99.62% | 98.81% | 193,106 |

Industry remains the hardest class by recall. The model is deliberately not presented as having independent ground-truth fire detection accuracy.

## Two-stage intelligence architecture

```text
2024 FIRMS detection
        ↓
FIRMS satellite signal
+ spatial/temporal history
        ↓
FIRE EXISTENCE EVIDENCE
        ↓
Fire Confidence + status
        │
        ├── LOW → Possible Thermal Anomaly
        ├── MEDIUM → Review
        └── HIGH → Likely Fire
                         ↓
                 Source/type classifier
                         ↓
                 Type + Type Confidence
                         ↓
                 Leakage-safe baseline
                         ↓
                 Risk engine
```

### Fire Confidence

The supplied labels do not contain an independent `real_fire / no_fire` ground-truth target. Therefore the first stage is intentionally an **evidence score**, not a fabricated supervised probability.

It combines:

- FIRMS confidence
- brightness vs. background-temperature signal
- FRP signal
- nearby prior detections within a spatial radius
- 24-hour cluster evidence
- 72-hour persistence across distinct dates

Future observations are never used when calculating the selected hotspot's persistence evidence.

### Type Confidence

The existing supervised model provides the source/type distribution. It remains separate from Fire Confidence. A high type confidence therefore means:

> "Given this detection, the source/context model strongly prefers this type."

It does **not** mean:

> "The satellite detection is confirmed to be a real fire."

## Baseline

The historical baseline remains leakage-safe and is separate from the classifier:

- 2022–2023 historical FIRMS observations for the independent baseline artifact.
- 2024 historical baseline windows use only observations **before the selected 2024 date**.
- Same month and day/night filtering is retained.
- If insufficient prior 2024 observations exist for a spatial region, the independent 2022–2023 baseline is used as fallback.
- Baseline contains historical FRP, activity frequency, timing, day/night ratio, persistence, spatial stability and hourly profiles.

## Runtime integration

```text
2024 hotspot query
        ↓
Saved XGBoost model
        ↓
Type + Type Confidence
        ↓
Selected hotspot → spatial/temporal fire evidence
        ↓
Fire Confidence + Fire Status
        ↓
Historical baseline comparison
        ↓
Risk engine gated by fire-existence evidence
        ↓
Existing React GIS dashboard
```

The existing dashboard structure is preserved. The additional fire-existence information is placed inside the existing bottom analysis slider rather than creating a new dashboard layout.

## Model files

```text
backend/models/fireops_classifier.joblib
backend/models/feature_names.json
backend/models/label_mapping.json
backend/models/model_metrics.json
backend/models/model_comparison.csv
backend/models/feature_importance.json
backend/models/confusion_matrix.png
```

## Retraining

From `backend`:

```powershell
python training/train_model.py `
  --train-data data/training_source/train_2022_2023_clean.csv `
  --test-data data/hotspots_2024.csv `
  --out models
```

The production model is trained on **2022 + 2023** and evaluated on the untouched **2024** dataset.

## 2024 real-event evidence layer

The supplied 2024 dataset is retained as the runtime FIRMS observation source. The dashboard does **not** relabel these satellite detections as independently confirmed ground-truth fires. For a selected 2024 hotspot, the evidence layer combines the FIRMS signal with only prior 2024 detections within the spatial/temporal window, plus the leakage-safe thermal source history. This produces a fire-existence **evidence score** and statuses such as `LIKELY FIRE`, `REVIEW`, or `POSSIBLE THERMAL ANOMALY`.

The map/batch path keeps the existing fast anomaly/risk behavior and defers the full 72-hour prior-event calculation until a hotspot is selected. This prevents the 552k-row 2024 dataset from making the map sluggish while ensuring the selected-hotspot intelligence panel uses the detailed real-event evidence. `F24-*` hotspot IDs are tied to the source dataset's stable `fire_row_id`, so selecting a filtered/sorted 2024 detection resolves back to the exact same observation.
