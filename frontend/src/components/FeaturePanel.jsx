import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

const GROUPS = [
  {
    title: "FIRMS inputs",
    keys: ["brightness", "bright_t31", "frp", "scan", "track", "confidence", "daynight", "type"],
  },
  {
    title: "Derived",
    keys: [
      "frp_deviation",
      "frequency_deviation",
      "temporal_deviation",
      "location_persistence",
      "night_ratio",
      "spatial_stability",
      "industrial_proximity",
      "forest_proximity",
      "mine_proximity",
      "oilgas_proximity",
    ],
  },
];

function fmt(key, value) {
  if (value == null) return "—";
  if (typeof value === "number") {
    if (key.includes("deviation")) return `${value.toFixed(1)}%`;
    if (value <= 1 && value >= 0 && !["scan", "track", "type", "frp", "brightness", "bright_t31", "confidence"].includes(key)) {
      return value.toFixed(2);
    }
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return String(value);
}

export default function FeaturePanel({ features }) {
  const [open, setOpen] = useState(false);
  if (!features) return null;

  return (
    <div className="border-t border-[#1e2d45] pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]"
      >
        FEATURE ENGINE
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <div className="mt-2 max-h-40 space-y-2 overflow-auto scroll-thin">
          {GROUPS.map((group) => (
            <div key={group.title}>
              <div className="mb-1 text-[9px] uppercase tracking-wider text-ops-400">{group.title}</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
                {group.keys.map((key) => (
                  <div key={key} className="flex justify-between gap-2">
                    <span className="text-ops-400">{key}</span>
                    <span className="font-mono text-white">{fmt(key, features[key])}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div className="text-[9px] text-ops-400">
            GIS distances: ind {features.gis?.distance_to_industrial ?? "—"} km · road {features.gis?.distance_to_road ?? "—"} km ·
            forest {features.gis?.distance_to_forest ?? "—"} km
          </div>
        </div>
      )}
    </div>
  );
}
