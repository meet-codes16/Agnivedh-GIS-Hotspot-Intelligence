from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import analysis, baseline, hotspots, validation
from app.store import FIRMS_CSV_PATH, HOTSPOTS_2024_CSV_PATH, SOURCE

app = FastAPI(
    title="AGNIVEDH API",
    version="2.5.0",
    description="Agnivedh GIS hotspot intelligence API with real trained source classification, historical FIRMS baseline and manual validation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hotspots.router, prefix="/api")
app.include_router(baseline.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(validation.router, prefix="/api")


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "mode": "real_ml",
        "source": SOURCE,
        "csv": "loaded" if HOTSPOTS_2024_CSV_PATH.exists() else ("loaded" if FIRMS_CSV_PATH.exists() else "not loaded"),
        "csv_path": str(HOTSPOTS_2024_CSV_PATH if HOTSPOTS_2024_CSV_PATH.exists() else FIRMS_CSV_PATH),
        "manual_validation": True,
        "critical_context": True,
    }
