function fmtDate(value) {
  if (!value) return "—";
  const d = new Date(`${value}T00:00:00`);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export default function EventHistoryPanel({ history }) {
  if (!history || history.status === "UNAVAILABLE") {
    return (
      <div className="border-t border-[#1e2d45] pt-2 text-[10px] text-ops-300">
        <div className="mb-1 text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">THERMAL BEHAVIOUR</div>
        <div className="text-ops-400">Select a 2024 detection to inspect its spatial-temporal source history.</div>
      </div>
    );
  }

  const persistent = history.behaviour !== "TRANSIENT ACTIVITY";
  const abnormal = history.abnormal_persistence;

  return (
    <div className="border-t border-[#1e2d45] pt-2 text-[10px]">
      <div className="mb-1 flex items-center justify-between">
        <div className="text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">THERMAL BEHAVIOUR</div>
        <span className={abnormal ? "text-[#ff6b6b]" : persistent ? "text-[#f0c14b]" : "text-ops-400"}>
          {abnormal ? "ABNORMAL" : history.behaviour}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-1.5 font-mono">
        <Stat label="DETECTIONS" value={history.detection_count} />
        <Stat label="ACTIVE DAYS" value={history.active_days} />
        <Stat label="FIRST SEEN" value={fmtDate(history.first_seen)} />
        <Stat label="LAST SEEN" value={fmtDate(history.last_seen)} />
      </div>

      <div className="mt-2 flex items-center justify-between text-[9px] text-ops-400">
        <span>SPAN {history.duration_days ?? 0} days</span>
        <span>RADIUS ≤ {history.radius_km ?? 5} km</span>
      </div>

      {history.timeline?.length > 0 && (
        <div className="mt-2 border border-[#1e2d45] bg-[#08131f]/70 p-2">
          <div className="mb-1 text-[8px] tracking-[0.14em] text-ops-400">RECENT SOURCE HISTORY</div>
          <div className="space-y-1">
            {history.timeline.slice(-8).map((point) => (
              <div key={point.date} className="flex items-center gap-2">
                <span className="w-[54px] shrink-0 font-mono text-[8px] text-ops-400">{point.date.slice(5)}</span>
                <div className="h-1.5 flex-1 overflow-hidden bg-[#142237]">
                  <span className="block h-full bg-[#ff6b6b]" style={{ width: `${Math.min(100, 12 + point.count * 12)}%` }} />
                </div>
                <span className="w-8 text-right font-mono text-[8px] text-white">{point.count}×</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-2 leading-4 text-ops-400">
        {history.interpretation}
      </div>
      {history.frp_spike_ratio >= 2 && (
        <div className="mt-1 text-[9px] text-[#ff8a3d]">
          Current FRP is {history.frp_spike_ratio}× the prior local median — review for abnormal activity.
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="border border-[#1e2d45] bg-[#0d1626] px-1.5 py-1">
      <div className="text-[7px] tracking-wider text-ops-400">{label}</div>
      <div className="truncate text-[10px] text-white">{value}</div>
    </div>
  );
}
