import { dayNightLabel, formatAcqDate, formatAcqTime } from "../utils/pipeline";

export default function HotspotDetails({
  hotspot,
  classification,
  fireDetection = null,
  risk = null,
  osmFacility = null,
  criticalContext = null,
  osmLoading = false,
}) {
  if (!hotspot) return null;

  const rows = [
    ["Date", formatAcqDate(hotspot.acq_date)],
    ["Time", formatAcqTime(hotspot.acq_time)],
    ["Satellite", hotspot.satellite],
    ["Instrument", hotspot.instrument],
    ["Confidence", typeof hotspot.confidence === "number" ? `${hotspot.confidence}%` : String(hotspot.confidence || "—").toUpperCase()],
    ["Brightness", hotspot.brightness],
    ["Bright T31", hotspot.bright_t31],
    ["FRP", `${hotspot.frp} MW`],
    ["Day/Night", dayNightLabel(hotspot.daynight)],
    ["Type", hotspot.type],
    ["Predicted source", classification?.label || "—"],
    ["Study area", hotspot.study_area],
  ];

  return (
    <div>
      <h3 className="mb-2 text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">HOTSPOT DETAILS</h3>
      <div className="space-y-0.5 text-[11px]">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3 border-b border-[#1e2d45]/80 py-0.5">
            <span className="shrink-0 text-ops-400">{k}</span>
            <span className="truncate text-right font-mono text-white">{v}</span>
          </div>
        ))}
      </div>

      <div className="mt-3 border border-[#2a3c58] bg-[#08131f]/70 p-2">
        <div className="mb-1 text-[10px] font-semibold tracking-[0.14em] text-[#3ec7ff]">FIRE / RISK ASSESSMENT</div>
        <div className="grid grid-cols-[1fr_auto] gap-y-1 text-[10px]">
          <span className="text-ops-400">Fire evidence</span>
          <span className="font-mono font-semibold text-white">{fireDetection ? `${fireDetection.fire_confidence}% · ${fireDetection.status}` : "—"}</span>
          <span className="text-ops-400">Risk</span>
          <span className="font-mono font-semibold text-white">{risk ? `${risk.level} · ${risk.score}/100` : "—"}</span>
        </div>
        {fireDetection?.evidence && (
          <div className="mt-2 border-t border-[#1e2d45] pt-2 text-[8px] leading-4 text-ops-500">
            Same-pass detections: {fireDetection.evidence.same_pass_detections ?? 0} · 24h nearby: {fireDetection.evidence.nearby_detections_24h ?? 0} · 72h nearby: {fireDetection.evidence.nearby_detections_72h ?? 0}
          </div>
        )}
      </div>

      <div className="mt-3 border border-ops-700/60 bg-ops-950/40 p-2">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-[10px] font-semibold tracking-[0.14em] text-[#3ec7ff]">
            NEAREST INDUSTRY
          </span>
          <span className="text-[9px] text-ops-500">OSM</span>
        </div>

        {osmLoading ? (
          <div className="text-[10px] text-ops-400">
            Searching OpenStreetMap...
          </div>
        ) : osmFacility ? (
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-[11px] font-medium text-white">
                {osmFacility.name}
              </div>
              <div className="mt-0.5 text-[9px] text-ops-400">
                {osmFacility.category || "Industrial Facility"}
              </div>
              <div className="text-[9px] text-ops-500">
                OpenStreetMap
              </div>
            </div>

            <div className="shrink-0 font-mono text-[11px] text-white">
              {Number(osmFacility.distance_km).toFixed(1)} km
            </div>
          </div>
        ) : (
          <div className="text-[10px] text-ops-400">
            No named industrial facility found within 5 km.
          </div>
        )}
      </div>

      <div className="mt-3 border border-[#5b4b2b]/70 bg-[#1a160d]/40 p-2">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-[10px] font-semibold tracking-[0.14em] text-[#e8ce7a]">CRITICAL CONTEXT</span>
          <span className="text-[9px] text-ops-500">OSM</span>
        </div>
        {osmLoading ? (
          <div className="text-[10px] text-ops-400">Checking critical infrastructure...</div>
        ) : criticalContext ? (
          <div className="grid grid-cols-[1fr_auto] gap-y-1 text-[10px]">
            <span className="text-ops-400">Name</span><span className="font-semibold text-white">{criticalContext.name || criticalContext.display_name || "—"}</span>
            <span className="text-ops-400">Type</span><span className="font-semibold text-white">{criticalContext.category}</span>
            <span className="text-ops-400">Distance</span><span className="font-mono text-white">{Number(criticalContext.distance_km).toFixed(1)} km</span>
          </div>
        ) : (
          <div className="text-[10px] text-ops-400">No supported critical infrastructure context found within 5 km.</div>
        )}
      </div>
    </div>
  );
}
