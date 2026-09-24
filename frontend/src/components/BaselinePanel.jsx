import { useEffect, useState } from "react";
import { resolveLocation } from "../utils/location";

export default function BaselinePanel({
  comparison,
  baseline,
  hotspot,
  loadedCount = 0,
  baselineGridCount = 0,
}) {
  const [locationName, setLocationName] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadLocation() {
      if (!hotspot?.latitude || !hotspot?.longitude) {
        setLocationName(null);
        return;
      }

      setLocationName(null);

      const result = await resolveLocation(
        hotspot.latitude,
        hotspot.longitude
      );

      if (!cancelled) {
        setLocationName(result?.displayName || null);
      }
    }

    loadLocation();

    return () => {
      cancelled = true;
    };
  }, [hotspot?.latitude, hotspot?.longitude]);

  if (!comparison) {
    return (
      <div className="h-full text-[11px]">
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">2024 BASELINE</h3>
          <span className="text-[9px] text-ops-400">HISTORICAL</span>
        </div>
        {baseline ? (
          <>
            <div className="mb-2 truncate text-ops-300">Grid: <span className="text-white">{baseline.region || "—"}</span></div>
            <div className="grid grid-cols-3 gap-1.5 font-mono">
              <Stat label="NORMAL FRP" value={Number(baseline.normal_frp || 0).toFixed(1)} />
              <Stat label="NORMAL FREQ" value={Number(baseline.normal_frequency || 0).toFixed(1)} />
              <Stat label="PEAK" value={baseline.normal_hour || "—"} />
            </div>
            <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] text-ops-300">
              <div>Night {(Number(baseline.normal_daynight_ratio || 0) * 100).toFixed(0)}%</div>
              <div>Persist {baseline.normal_persistence || "—"}</div>
              <div>Stab {(Number(baseline.location_stability || 0) * 100).toFixed(0)}%</div>
              <div>Profiles {baselineGridCount || "—"}</div>
            </div>
            <div className="mt-2 text-[9px] leading-4 text-ops-400">{baseline.notes || "Historical baseline active. Select a marker for hotspot deviation."}</div>
          </>
        ) : (
          <p className="text-[11px] leading-5 text-ops-400">Fetch a 2024 date to build the leakage-safe historical baseline.</p>
        )}
      </div>
    );
  }

  const sign = comparison.frp_deviation >= 0 ? "+" : "";
  const high = Math.abs(comparison.frp_deviation) >= 100;

  return (
    <div className="flex h-full min-w-0 flex-col text-[11px]">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">2024 BASELINE</h3>
        <span className="text-[9px] text-ops-400">2024 HISTORY</span>
      </div>
      <div className="mb-2 truncate text-ops-300">
        Location:{" "}
        <span className="text-white">
          {locationName || "Resolving location..."}
        </span>
        <div className="text-[9px] text-ops-400">
          Grid: {comparison.region}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-1.5 font-mono">
        <Stat label="NORMAL" value={comparison.normal_frp.toFixed(1)} />
        <Stat label="CURRENT" value={comparison.current_frp.toFixed(1)} />
        <Stat
          label="DEVIATION"
          value={`${sign}${comparison.frp_deviation.toFixed(1)}%`}
          alert={high}
        />
      </div>
      <div className={`mt-1 text-[9px] ${high ? "text-[#ff6b6b]" : "text-ops-400"}`}>
        {comparison.frp_deviation_label}
      </div>
      <div className="mt-2 flex items-center justify-between border border-[#1e2d45] bg-[#0d1626] px-1.5 py-1">
        <span className="text-[8px] tracking-wider text-ops-400">RELATIVE DEVIATION</span>
        <span className="font-mono text-[11px] text-white">{Number(comparison.baseline_deviation_score ?? 0).toFixed(0)} / 100</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] text-ops-300">
        <div>Freq {comparison.normal_frequency.toFixed(1)} / mo</div>
        <div>Set {comparison.current_frequency ?? "—"}</div>
        <div>Peak {comparison.normal_hour}</div>
        <div>Night {(comparison.night_ratio * 100).toFixed(0)}%</div>
        <div>
          Persist {comparison.persistence.label} · Stab {(comparison.location_stability * 100).toFixed(0)}%
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, alert }) {
  return (
    <div className="border border-[#1e2d45] bg-[#0d1626] px-1.5 py-1">
      <div className="text-[8px] tracking-wider text-ops-400">{label}</div>
      <div className={`text-[12px] ${alert ? "text-[#ff6b6b]" : "text-white"}`}>{value}</div>
    </div>
  );
}
