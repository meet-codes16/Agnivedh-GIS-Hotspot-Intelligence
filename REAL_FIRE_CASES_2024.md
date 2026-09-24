# 2024 Real-Fire Corroboration Cases

These are retrospective validation cases from the supplied 2024 FIRMS hotspot dataset. The production pipeline is run on the FIRMS hotspot as the input; it is **not** a pre-FIRMS fire forecast.

## Cases

| FIRMS ID | Date | Location | Model source class | Fire evidence | Risk | External corroboration |
|---|---|---|---|---:|---|---|
| F24-1493001 | 2024-04-29 | 23.27085, 80.16953 | Wildfire (79%) | 69% · LIKELY FIRE | 65 · HIGH | FSI LFF KUNDAM-3, Jabalpur: SNPP-VIIRS detections within about 0.14 km and minutes of the FIRMS event |
| F24-1493002 | 2024-04-29 | 23.27508, 80.16898 | Wildfire (79%) | 68% · LIKELY FIRE | 65 · HIGH | FSI LFF KUNDAM-3, Jabalpur: SNPP-VIIRS detection within about 0.07 km and minutes of the FIRMS event |
| F24-1584147 | 2024-05-26 | 31.16776, 77.05315 | Wildfire (75%) | 67% · LIKELY FIRE | 55 · MODERATE | FSI LFF DHAMI-1, Shimla: SNPP-VIIRS detection about 0.18 km away at approximately the same local time |
| F24-1584148 | 2024-05-26 | 31.16993, 77.05482 | Wildfire (75%) | 66% · LIKELY FIRE | 55 · MODERATE | FSI LFF DHAMI-1, Shimla: SNPP-VIIRS detection about 0.18 km away at approximately the same local time |
| F24-1597174 | 2024-06-13 | 31.01169, 77.19762 | Wildfire (77%) | 72% · LIKELY FIRE | 55 · MODERATE | FSI LFF MASHOBRA-12, Shimla: SNPP-VIIRS detection about 0.11 km away at approximately the same local time |

## What this proves

For these retrospective cases, the same production pipeline that receives a FIRMS hotspot classified the event as **Wildfire** and produced **LIKELY FIRE** evidence. The selected cases also have close spatial/temporal corroboration in the Forest Survey of India Large Forest Fire records.

This supports the statement:

> **FIRMS hotspot → Agnivedh fire/source assessment → risk triage → external retrospective corroboration.**

It does **not** support the stronger statement that Agnivedh predicted a fire before FIRMS detected it, because the FIRMS hotspot is the input to the pipeline.

## Important validation limitation

FSI Large Forest Fire records are based on SNPP-VIIRS hotspot data. Therefore they are useful **external operational corroboration**, but they are not independent ground truth from a different sensor or field observation. A strict independent accuracy/recall study should use an independent burned-area or field-observation reference dataset.

The source classifier's `predict_proba` output is also not calibrated probability. The fire-detection percentage is an evidence score, not an independently ground-truth-calibrated probability of real fire.
