import { useEffect, useState } from "react";

function LiveClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const time = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(now);

  const date = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(now);

  return (
    <div className="hidden border border-[#1e2d45] bg-[#0e1a2c] px-2 py-1 text-right sm:block">
      <div className="font-mono text-[11px] text-white tabular-nums">{time} IST</div>
      <div className="text-[8px] tracking-wider text-ops-400">{date} · LIVE</div>
    </div>
  );
}

export default function TopBar({ hotspotCount, highAnomalyCount, selected, regionCount = 0 }) {
  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-[#1e2d45] bg-[#0b1322] px-4">
      <div className="flex items-center gap-6">
        <div>
          <div className="text-[11px] font-semibold tracking-[0.18em] text-white">AGNIVEDH COMMAND</div>
          <div className="text-[9px] tracking-[0.16em] text-ops-400">V2.4 PROTOTYPE</div>
        </div>
        <div className="hidden h-7 w-px bg-[#1e2d45] md:block" />
        <div className="hidden items-center gap-6 text-[11px] md:flex">
          <div>
            <div className="text-[9px] tracking-wider text-ops-400">LIVE TELEMETRY</div>
            <div className="text-ops-300">
              Monitored Regions: <span className="font-mono text-white">{regionCount}</span>
            </div>
          </div>
          <div>
            <div className="text-[9px] tracking-wider text-ops-400">ACTIVE HOTSPOTS</div>
            <div className="font-mono text-white">{hotspotCount}</div>
          </div>
          {selected && (
            <div className="font-mono text-[11px] text-[#3ec7ff]">
              {selected.latitude.toFixed(3)}°N {selected.longitude.toFixed(3)}°E
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 text-[11px]">
        <LiveClock />
        <div className="hidden text-right md:block">
          <div className="text-[9px] tracking-wider text-[#ff6b6b]">HIGH ANOMALIES</div>
          <div className="font-mono text-white">
            {highAnomalyCount} <span className="text-ops-400">HIGH / LIKELY FIRE</span>
          </div>
        </div>
        <div className="flex items-center gap-2 border border-[#1e2d45] bg-[#0e1a2c] px-2.5 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#5dcc8a]" />
          <span className="text-[10px] tracking-wider text-ops-300">SYSTEM</span>
          <span className="text-[10px] font-semibold text-[#5dcc8a]">ONLINE</span>
        </div>
      </div>
    </header>
  );
}
