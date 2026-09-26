import L from "leaflet";

const hotspotIconCache = new Map();

export function hotspotIcon(severity = "nominal", selected = false) {
  const key = `${severity}:${selected ? "selected" : "normal"}`;

  if (hotspotIconCache.has(key)) {
    return hotspotIconCache.get(key);
  }

  const cls = `hotspot-dot ${severity}${selected ? " selected" : ""}`;
  const size = selected ? 16 : 12;

  const icon = L.divIcon({
    className: "hotspot-icon",
    html: `<div class="${cls}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -10],
  });

  hotspotIconCache.set(key, icon);
  return icon;
}

const gisIconCache = new Map();

export function gisIcon(category) {
  const key = category || "default";

  if (gisIconCache.has(key)) {
    return gisIconCache.get(key);
  }

  const colors = {
    "Industrial Facility": "#ff8a3d",
    Road: "#9aa8bc",
    Settlement: "#f0c14b",
    Forest: "#5dcc8a",
    Mine: "#c9845a",
    "Oil/Gas Facility": "#3ec7ff",
    "Power Plant": "#d07cff",
    "Water Body": "#5aa8ff",
    "Critical Area": "#e8ce7a",
    "Nuclear Facility": "#e8ce7a",
    "Nuclear Power Facility": "#e8ce7a",
    "Military Installation": "#f07d7d",
    "Critical Power Infrastructure": "#e8ce7a",
  };

  const color = colors[category] || "#9aa8bc";

  const icon = L.divIcon({
    className: "gis-icon",
    html: `<div class="gis-pin gis-pin-visible" style="background:${color}"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });

  gisIconCache.set(key, icon);
  return icon;
}
