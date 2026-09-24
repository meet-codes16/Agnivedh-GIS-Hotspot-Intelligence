"""Train the Agnivedh source/context classifier with temporal validation.

2022 -> validation on 2023 -> final refit on 2022+2023 -> untouched 2024 test.
WorldCover is an inference-available context feature. The labels themselves
were constructed using WorldCover/OSM evidence, so evaluation measures
agreement with that labeling methodology rather than independent fire truth.
"""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
    precision_score, recall_score,
)

LABEL_MAP = {
    "FOREST": "Wildfire",
    "AGRICULTURAL": "Agriculture",
    "INDUSTRIAL": "Industry",
    "URBAN_WASTE": "Other",
    "UNKNOWN": "Other",
}
CLASSES = ["Agriculture", "Industry", "Other", "Wildfire"]
ENCODER = {c: i for i, c in enumerate(CLASSES)}
FEATURES = [
    "latitude", "longitude", "brightness", "scan", "track", "bright_t31", "frp", "type",
    "hour", "month", "doy", "dow", "hs", "hc", "ds", "dc", "bd", "cn", "dn",
    "worldcover_code",
]
READ_COLS = [
    "latitude", "longitude", "brightness", "scan", "track", "acq_date", "acq_time",
    "confidence", "bright_t31", "frp", "daynight", "type", "worldcover_code",
    "final_source_label", "final_label_confidence", "year",
]


def prepare(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=READ_COLS, low_memory=False)
    df["target"] = df["final_source_label"].map(LABEL_MAP)
    df = df.dropna(subset=["target"]).copy()
    d = pd.to_datetime(df["acq_date"], errors="coerce")
    t = pd.to_numeric(df["acq_time"], errors="coerce").fillna(0).astype(int)
    df["hour"] = t // 100 + (t % 100) / 60.0
    df["month"] = d.dt.month
    df["doy"] = d.dt.dayofyear
    df["dow"] = d.dt.dayofweek
    df["hs"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hc"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["ds"] = np.sin(2 * np.pi * df["doy"] / 365.25)
    df["dc"] = np.cos(2 * np.pi * df["doy"] / 365.25)
    df["bd"] = df["brightness"] - df["bright_t31"]
    df["cn"] = df["confidence"].astype(str).str.lower().map({"l": 0, "n": 1, "h": 2}).fillna(-1)
    df["dn"] = df["daynight"].astype(str).str.upper().map({"D": 0, "N": 1}).fillna(-1)
    df["worldcover_code"] = pd.to_numeric(df["worldcover_code"], errors="coerce").fillna(0)
    df["year"] = d.dt.year.astype("Int64")
    return df


def make_model():
    from xgboost import XGBClassifier
    return XGBClassifier(
        n_estimators=20,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.90,
        colsample_bytree=0.90,
        objective="multi:softprob",
        num_class=4,
        eval_metric="mlogloss",
        tree_method="hist",
        max_bin=96,
        n_jobs=-1,
        random_state=42,
    )


def sample_weights(df: pd.DataFrame) -> np.ndarray:
    y = df["target"].map(ENCODER).astype("int8").to_numpy()
    counts = np.bincount(y, minlength=len(CLASSES))
    class_weight = (len(y) / (len(CLASSES) * np.maximum(counts, 1))) ** 0.8
    weights = class_weight[y].astype("float32")
    # LOW-confidence contextual labels are still useful, but less authoritative.
    weights *= np.where(df["final_label_confidence"].eq("LOW").to_numpy(), 0.5, 1.0)
    return weights


def evaluate(model, df: pd.DataFrame) -> dict:
    y = df["target"].to_numpy()
    pred = np.asarray([CLASSES[int(i)] for i in model.predict(df[FEATURES].astype("float32"))])
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "precision_macro": float(precision_score(y, pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y, pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y, pred, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y, pred, average="weighted", zero_division=0)),
        "classification_report": classification_report(y, pred, labels=CLASSES, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y, pred, labels=CLASSES).tolist(),
        "labels": CLASSES,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-data", default="../data/training_source/train_2022_2023_clean.csv")
    ap.add_argument("--test-data", default="../data/hotspots_2024.csv")
    ap.add_argument("--out", default="../models")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    train = prepare(args.train_data)
    test = prepare(args.test_data)
    train22 = train[train.year == 2022].copy()
    train23 = train[train.year == 2023].copy()
    final_train = train[train.year.isin([2022, 2023])].copy()
    final_test = test[test.year == 2024].copy()

    validator = make_model()
    validator.fit(
        train22[FEATURES].astype("float32"),
        train22["target"].map(ENCODER).astype("int8"),
        sample_weight=sample_weights(train22),
        verbose=False,
    )
    validation = evaluate(validator, train23)
    validation.update({"train_year": 2022, "validation_year": 2023, "train_rows": len(train22), "validation_rows": len(train23)})
    del validator
    gc.collect()

    final = make_model()
    final.fit(
        final_train[FEATURES].astype("float32"),
        final_train["target"].map(ENCODER).astype("int8"),
        sample_weight=sample_weights(final_train),
        verbose=False,
    )
    final_test_metrics = evaluate(final, final_test)
    final_test_metrics.update({"test_year": 2024, "test_rows": len(final_test)})

    bundle = {
        "pipeline": final,
        "feature_names": FEATURES,
        "label_mapping": LABEL_MAP,
        "classes": CLASSES,
        "model_name": "XGBClassifier_worldcover_context_balanced08",
        "label_encoder": {i: c for i, c in enumerate(CLASSES)},
        "probability_note": "predict_proba output; not calibrated probability.",
        "training_years": [2022, 2023],
        "validation_year": 2023,
        "test_year": 2024,
        "training_rows": len(final_train),
        "feature_version": "v2_worldcover_context_balanced08",
    }
    joblib.dump(bundle, out / "fireops_classifier.joblib", compress=3)
    (out / "feature_names.json").write_text(json.dumps(FEATURES, indent=2), encoding="utf-8")
    (out / "label_mapping.json").write_text(json.dumps(LABEL_MAP, indent=2), encoding="utf-8")

    metrics = {
        "protocol": "temporal_train_2022_2023_test_2024",
        "selected_model": bundle["model_name"],
        "train_years": [2022, 2023],
        "validation_year": 2023,
        "test_year": 2024,
        "train_rows": len(final_train),
        "validation_rows": len(train23),
        "test_rows": len(final_test),
        "classes": final_train["target"].value_counts().to_dict(),
        "features": FEATURES,
        "model_hyperparameters": {
            "n_estimators": 20, "max_depth": 6, "learning_rate": 0.08,
            "subsample": 0.90, "colsample_bytree": 0.90, "max_bin": 96,
            "tree_method": "hist", "random_state": 42,
            "class_weighting": "inverse_frequency^0.8",
            "low_label_confidence_weight": 0.5,
        },
        "forward_validation_2022_to_2023": validation,
        "final_2024_test": final_test_metrics,
        "leakage_controls": [
            "2024 labels are never used for fitting or model selection.",
            "WorldCover context is available at 2024 inference time.",
            "Label confidence is used only as a training weight.",
            "Evaluation is chronological rather than a random year mix.",
            "Metrics measure agreement with the WorldCover/OSM-derived labeling methodology, not independent fire truth.",
        ],
    }
    (out / "model_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    pd.DataFrame([
        {"model": bundle["model_name"], "stage": "forward_validation", "train_years": "2022", "eval_year": "2023", **{k: validation[k] for k in ["accuracy", "precision_macro", "recall_macro", "f1_macro", "f1_weighted"]}},
        {"model": bundle["model_name"], "stage": "final_test", "train_years": "2022,2023", "eval_year": "2024", **{k: final_test_metrics[k] for k in ["accuracy", "precision_macro", "recall_macro", "f1_macro", "f1_weighted"]}},
    ]).to_csv(out / "model_comparison.csv", index=False)
    importance = {k: float(v) for k, v in sorted(zip(FEATURES, final.feature_importances_), key=lambda x: x[1], reverse=True)}
    (out / "feature_importance.json").write_text(json.dumps(importance, indent=2), encoding="utf-8")

    try:
        import matplotlib.pyplot as plt
        cm = np.asarray(final_test_metrics["confusion_matrix"])
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.imshow(cm)
        ax.set_xticks(range(4), CLASSES, rotation=30, ha="right")
        ax.set_yticks(range(4), CLASSES)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_title("Agnivedh — 2024 Held-out Test Confusion Matrix")
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center")
        fig.tight_layout()
        fig.savefig(out / "confusion_matrix.png", dpi=160)
        plt.close(fig)
    except Exception as exc:
        (out / "confusion_matrix_error.txt").write_text(str(exc), encoding="utf-8")

    print(json.dumps({"forward_validation_2023": validation, "final_test_2024": final_test_metrics}, indent=2))


if __name__ == "__main__":
    main()
