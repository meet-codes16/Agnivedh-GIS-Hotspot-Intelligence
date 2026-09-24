import { markerSeverity } from "./risk";

const FIRMS_FIELDS = [
  "latitude", "longitude", "brightness", "scan", "track", "acq_date", "acq_time",
  "satellite", "instrument", "confidence", "version", "bright_t31", "frp", "daynight", "type",
  "assigned_class", "study_area", "region_key",
];

export function normalizeHotspotData(raw = {}) {
  const hotspot = {};
  for (const field of FIRMS_FIELDS) hotspot[field] = raw[field];
  hotspot.id = raw.id || `F24-${String(raw.latitude ?? "0").replace(".", "")}`;
  hotspot.latitude = Number(hotspot.latitude);
  hotspot.longitude = Number(hotspot.longitude);
  hotspot.brightness = Number(hotspot.brightness);
  hotspot.scan = Number(hotspot.scan);
  hotspot.track = Number(hotspot.track);
  hotspot.bright_t31 = Number(hotspot.bright_t31);
  hotspot.frp = Number(hotspot.frp);
  hotspot.type = Number(hotspot.type);
  return hotspot;
}

export function runIntelligencePipeline(rawHotspot, regionCount = 1) {
  const hotspot = normalizeHotspotData(rawHotspot);
  const baseline = rawHotspot._baseline || null;
  const nearby = rawHotspot._nearby || [];
  const comparison = rawHotspot._comparison || null;
  const features = rawHotspot._features || null;
  const classification = rawHotspot._classification || null;
  const risk = rawHotspot._risk || null;
  const fireDetection = rawHotspot._fire_detection || null;


  return {
    hotspot,
    baseline,
    nearby,
    comparison,
    features,
    classification,
    fireDetection,
    risk,
    severity: markerSeverity(hotspot, risk, fireDetection),
  };
}

export function formatAcqTime(acqTime) {
  const raw = String(acqTime ?? "0000").padStart(4, "0");
  return `${raw.slice(0, 2)}:${raw.slice(2, 4)}`;
}

export function formatAcqDate(acqDate) {
  if (!acqDate) return "—";
  const date = new Date(`${acqDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return acqDate;
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function dayNightLabel(value) {
  if (value === "N") return "Night";
  if (value === "D") return "Day";
  return "—";
}

export function buildIntelligenceRecords(list = []) {
  return list.map((item) => runIntelligencePipeline(item, 1));
}

