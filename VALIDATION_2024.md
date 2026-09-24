# Agnivedh — 2024 Independent Fire Cross-Checks

These are retrospective validation examples, not model training labels and not inputs to
the production classifier/risk calculation. The FIRMS hotspot is the system input.
The external reference is the Forest Survey of India (FSI) Large Forest Fire (LFF)
archive. FSI describes LFF as candidate large fires detected using contiguous SNPP-VIIRS
pixels and subsequently monitored across satellite passes. Because FSI LFF also uses
SNPP-VIIRS, these records are **external operational corroboration**, not an independent
sensor/ground-truth label. For strict ground-truth validation, pair the cases with a
burned-area or field-observation source.

## Current dataset records

| Agnivedh hotspot ID | Date | UTC time | Lat | Lon | FRP MW | Source label |
|---|---|---:|---:|---:|---:|---|
| F24-1493001 | 2024-04-29 | 08:13 | 23.27085 | 80.16953 | 7.37 | FOREST |
| F24-1493002 | 2024-04-29 | 08:13 | 23.27508 | 80.16898 | 7.37 | FOREST |
| F24-1584147 | 2024-05-26 | 08:09 | 31.16776 | 77.05315 | 6.94 | FOREST |
| F24-1584148 | 2024-05-26 | 08:09 | 31.16993 | 77.05482 | 6.02 | FOREST |
| F24-1597174 | 2024-06-13 | 07:30 | 31.01169 | 77.19762 | 3.46 | FOREST |

## Independent FSI records

### KUNDAM-3 — Jabalpur, Madhya Pradesh
FSI LFF record for 29-Apr-2024 lists KUNDAM-3 detections including:
- 23.27093, 80.16821
- 23.27525, 80.16838
- 23.27102, 80.16891
- 23.27142, 80.17239

The two strongest Agnivedh dataset records above are approximately 135 m and 64 m
from the first two listed FSI coordinates respectively.

FSI page:
https://fsiforestfire.gov.in/lff/lfire.php?date=2024-04-29&filter=total&firename=KUNDAM+-3&state=MADHYA+PRADESH

### DHAMI-1 — Shimla, Himachal Pradesh
FSI LFF record for 26-May-2024 lists DHAMI-1 detections including:
- 31.17088, 77.05329 on 27-May
- 31.16335, 77.05363 on 26-May
- 31.16551, 77.05544 on 26-May
and earlier 25-May detections around 31.1692, 77.04826 and 31.16801, 77.05372.

The two Agnivedh records are within roughly 0.18–0.32 km of these FSI detections.

FSI page:
https://fsiforestfire.gov.in/lff/lfire.php?date=2024-05-26&filter=total&firename=DHAMI+-1&state=HIMACHAL+PRADESH

### MASHOBRA-12 — Shimla, Himachal Pradesh
FSI LFF record for 13-Jun-2024 lists a detection at 31.01176, 77.19644.
The Agnivedh record F24-1597174 at 31.01169, 77.19762 is approximately 113 m away.

FSI page:
https://fsiforestfire.gov.in/lff/lfire.php?date=2024-06-13&filter=total&firename=MASHOBRA+-12&state=HIMACHAL+PRADESH

## How to demonstrate these cases

1. Select the date in the Agnivedh UI.
2. Click `FETCH & CLASSIFY`.
3. The returned hotspot IDs are stable and can be opened through `/api/analysis/{id}`.
4. The same production pipeline computes source classification, fire evidence, current-event
   persistence, and operational risk.
5. The FSI LFF record is an external retrospective cross-check; it is not fed into the
   prediction/risk calculation.

## Important interpretation

Do not describe the classifier probability as a probability that a fire exists.
The source classifier predicts source/context classes. The fire-detection score is an
evidence score and is not independently ground-truth calibrated. The FSI LFF records
provide independent corroboration of large forest-fire events, but they are not a claim
that every FIRMS point is ground-confirmed.

For a judge demonstration, the strongest examples in this package are:
- F24-1493001 / F24-1493002 — KUNDAM-3
- F24-1584147 / F24-1584148 — DHAMI-1
- F24-1597174 — MASHOBRA-12
