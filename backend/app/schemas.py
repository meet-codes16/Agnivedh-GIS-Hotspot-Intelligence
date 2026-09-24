from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class FirmsHotspot(BaseModel):
    """NASA FIRMS column contract. Keep in sync with fires_2024.csv."""

    latitude: float
    longitude: float
    brightness: float
    scan: float
    track: float
    acq_date: str
    acq_time: str
    satellite: str
    instrument: str
    confidence: Union[float, str]
    version: str
    bright_t31: float
    frp: float
    daynight: str
    type: int
    assigned_class: Optional[str] = None
    study_area: Optional[str] = None
    id: Optional[str] = None
    region_key: Optional[str] = None


class BaselineRecord(BaseModel):
    region_key: str
    region: str
    normal_frp: float
    normal_frequency: float
    normal_hour: str
    normal_hour_value: float
    normal_daynight_ratio: float
    normal_persistence: str
    persistence_score: float
    normal_location_density: float
    location_stability: float
    notes: str


class NearbyPlace(BaseModel):
    id: str
    hotspot_id: str
    category: str
    name: str
    distance_km: float
    latitude: float
    longitude: float


class AnalysisResponse(BaseModel):
    hotspot: Dict[str, Any]
    baseline: Dict[str, Any]
    nearby: List[Dict[str, Any]]
    comparison: Dict[str, Any]
    features: Dict[str, Any]
    classification: Dict[str, Any]
    risk: Dict[str, Any]
    forecast: List[Dict[str, Any]]
    prototype: bool = Field(default=True)


class ManualValidationRequest(BaseModel):
    """FIRMS-style observable inputs for an isolated validation run."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    brightness: float = Field(..., ge=0)
    bright_t31: float = Field(..., ge=0)
    frp: float = Field(..., ge=0)
    scan: float = Field(..., ge=0)
    track: float = Field(..., ge=0)
    confidence: Union[float, str] = "n"
    daynight: str = "D"
    type: int = 0
    acq_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    acq_time: str = Field(..., pattern=r"^\d{3,4}$")
    satellite: str = "VIIRS"
    instrument: str = "VIIRS"
    version: str = "1.0"
    worldcover_code: Optional[int] = Field(default=None, ge=10, le=100)
