"""Real Agnivedh source-classification inference service."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any
import joblib
import pandas as pd

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
MODEL_PATH = MODEL_DIR / "fireops_classifier.joblib"
FEATURES_PATH = MODEL_DIR / "feature_names.json"
_mapping = json.loads((MODEL_DIR / "label_mapping.json").read_text(encoding="utf-8")) if (MODEL_DIR / "label_mapping.json").exists() else {}
_bundle = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None
MODEL_AVAILABLE = _bundle is not None
MODEL_NAME = _bundle.get("model_name", "real_trained_model") if _bundle else "real_trained_model_unavailable"
FEATURE_NAMES = _bundle.get("feature_names", json.loads(FEATURES_PATH.read_text(encoding="utf-8"))) if _bundle else []


def _features(h: dict[str, Any]) -> pd.DataFrame:
    date = pd.to_datetime(h.get("acq_date"), errors="coerce")
    raw_time = int(float(h.get("acq_time") or 0))
    hour = raw_time // 100 + (raw_time % 100) / 60
    doy = int(date.dayofyear) if not pd.isna(date) else 1
    month = int(date.month) if not pd.isna(date) else 1
    dow = int(date.dayofweek) if not pd.isna(date) else 0
    conf = str(h.get("confidence") or "n").lower()
    row = {
        "latitude": float(h.get("latitude") or 0), "longitude": float(h.get("longitude") or 0),
        "brightness": float(h.get("brightness") or 0), "scan": float(h.get("scan") or 0),
        "track": float(h.get("track") or 0), "bright_t31": float(h.get("bright_t31") or 0),
        "frp": float(h.get("frp") or 0), "type": int(float(h.get("type") or 0)),
        "hour": hour, "month": month, "doy": doy, "dow": dow,
        "hs": __import__("math").sin(2 * __import__("math").pi * hour / 24),
        "hc": __import__("math").cos(2 * __import__("math").pi * hour / 24),
        "ds": __import__("math").sin(2 * __import__("math").pi * doy / 365.25),
        "dc": __import__("math").cos(2 * __import__("math").pi * doy / 365.25),
        "bd": float(h.get("brightness") or 0) - float(h.get("bright_t31") or 0),
        "cn": {"l": 0, "n": 1, "h": 2}.get(conf, -1),
        "dn": {"d": 0, "n": 1}.get(str(h.get("daynight") or "d").lower(), -1),
        "worldcover_code": float(h.get("worldcover_code") or 0),
    }
    return pd.DataFrame([row], columns=FEATURE_NAMES)


def classify_hotspot(hotspot: dict[str, Any]) -> dict[str, Any]:
    if not MODEL_AVAILABLE:
        return {"label": "Unknown", "confidence": 0, "alternatives": [], "distribution": [], "model": MODEL_NAME, "prototype": True}
    x = _features(hotspot)
    raw_pred = _bundle["pipeline"].predict(x)[0]
    # XGBoost is trained on encoded class IDs; decode them back to the
    # human-readable labels stored in the bundle.
    encoder = _bundle.get("label_encoder")
    if encoder is not None and hasattr(encoder, "inverse_transform"):
        pred = str(encoder.inverse_transform([int(raw_pred)])[0])
    elif isinstance(encoder, dict):
        pred = str(encoder.get(int(raw_pred), raw_pred))
    else:
        pred = str(raw_pred)
    probs = _bundle["pipeline"].predict_proba(x)[0]
    pairs = sorted(zip(_bundle["classes"], probs), key=lambda p: p[1], reverse=True)
    distribution = [{"label": label, "probability": round(float(prob) * 100)} for label, prob in pairs]
    return {
        "label": pred,
        "confidence": round(float(max(probs)) * 100),
        "alternatives": [{"label": label, "probability": round(float(prob) * 100)} for label, prob in pairs[1:3]],
        "distribution": distribution,
        "model": MODEL_NAME,
        "prototype": False,
        "probability_note": "Model predict_proba output; not calibrated probability.",
    }


def classify_hotspots(hotspots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not MODEL_AVAILABLE:
        return [classify_hotspot(h) for h in hotspots]

    if not hotspots:
        return []

    import math

    rows = []
    for h in hotspots:
        date = pd.to_datetime(h.get("acq_date"), errors="coerce")
        raw_time = int(float(h.get("acq_time") or 0))
        hour = raw_time // 100 + (raw_time % 100) / 60

        doy = int(date.dayofyear) if not pd.isna(date) else 1
        month = int(date.month) if not pd.isna(date) else 1
        dow = int(date.dayofweek) if not pd.isna(date) else 0

        conf = str(h.get("confidence") or "n").lower()
        brightness = float(h.get("brightness") or 0)
        bright_t31 = float(h.get("bright_t31") or 0)

        rows.append({
            "latitude": float(h.get("latitude") or 0),
            "longitude": float(h.get("longitude") or 0),
            "brightness": brightness,
            "scan": float(h.get("scan") or 0),
            "track": float(h.get("track") or 0),
            "bright_t31": bright_t31,
            "frp": float(h.get("frp") or 0),
            "type": int(float(h.get("type") or 0)),
            "hour": hour,
            "month": month,
            "doy": doy,
            "dow": dow,
            "hs": math.sin(2 * math.pi * hour / 24),
            "hc": math.cos(2 * math.pi * hour / 24),
            "ds": math.sin(2 * math.pi * doy / 365.25),
            "dc": math.cos(2 * math.pi * doy / 365.25),
            "bd": brightness - bright_t31,
            "cn": {"l": 0, "n": 1, "h": 2}.get(conf, -1),
            "dn": {"d": 0, "n": 1}.get(
                str(h.get("daynight") or "d").lower(), -1
            ),
            "worldcover_code": float(h.get("worldcover_code") or 0),
        })

    x = pd.DataFrame(rows, columns=FEATURE_NAMES)

    preds = _bundle["pipeline"].predict(x)
    prob = _bundle["pipeline"].predict_proba(x)

    out = []
    encoder = _bundle.get("label_encoder")

    for raw_pred, probs in zip(preds, prob):
        if encoder is not None and hasattr(encoder, "inverse_transform"):
            pred = str(encoder.inverse_transform([int(raw_pred)])[0])
        elif isinstance(encoder, dict):
            pred = str(encoder.get(int(raw_pred), raw_pred))
        else:
            pred = str(raw_pred)

        pairs = sorted(
            zip(_bundle["classes"], probs),
            key=lambda p: p[1],
            reverse=True
        )

        out.append({
            "label": pred,
            "confidence": round(float(max(probs)) * 100),
            "alternatives": [
                {
                    "label": label,
                    "probability": round(float(probability) * 100)
                }
                for label, probability in pairs[1:3]
            ],
            "distribution": [
                {
                    "label": label,
                    "probability": round(float(probability) * 100)
                }
                for label, probability in pairs
            ],
            "model": MODEL_NAME,
            "prototype": False,
            "probability_note": "Model predict_proba output; not calibrated probability.",
        })

    return out

