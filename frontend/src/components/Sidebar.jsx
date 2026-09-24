import {
  Activity,
  AlertTriangle,
  Factory,
  Flame,
  LayoutGrid,
  LogOut,
  Radio,
} from "lucide-react";

const NAV = [
  { id: "overview", label: "Overview", icon: LayoutGrid },
  { id: "facilities", label: "Facilities", icon: Factory },
  { id: "hotspots", label: "Hotspots", icon: Flame },
  { id: "anomalies", label: "Anomalies", icon: AlertTriangle },
];

export default function Sidebar({
  activeNav,
  onNav,
  hotspotCount,
  anomalyCount,
  facilityCount,
  onBroadcast,
  onReset,
}) {
  return (
    <aside className="flex w-[212px] shrink-0 flex-col border-r border-[#1e2d45] bg-[#0a1220]">
      <div className="border-b border-[#1e2d45] px-4 py-3">
        <div className="text-[10px] tracking-[0.22em] text-[#3ec7ff]">AGNIVEDH</div>
        <div className="mt-0.5 text-sm font-semibold text-white">COMMAND NODE</div>
        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-[#5dcc8a]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#5dcc8a]" />
          ONLINE
        </div>
      </div>

      <nav className="flex-1 px-2 py-3">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = activeNav === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNav(item.id)}
              className={`mb-0.5 flex w-full items-center gap-2.5 px-2.5 py-2 text-left text-[12px] ${
                active
                  ? "border-l-2 border-[#3ec7ff] bg-[#132033] text-white"
                  : "border-l-2 border-transparent text-ops-300 hover:bg-[#101a2c] hover:text-white"
              }`}
            >
              <Icon size={14} strokeWidth={1.75} />
              {item.label}
            </button>
          );
        })}

        <div className="mt-5 space-y-2 px-2 text-[11px]">
          <Counter label="Facilities" value={facilityCount} tone="#3ec7ff" />
          <Counter label="Hotspots" value={hotspotCount} tone="#3ec7ff" />
          <Counter label="Anomalies" value={anomalyCount} tone="#f0c14b" />
          <div className="pt-1 text-[9px] leading-4 text-ops-400">
            Counts are calculated from the currently loaded 2024 FIRMS observations.
          </div>
        </div>
      </nav>

      <div className="border-t border-[#1e2d45] p-2">
        <button
          type="button"
          onClick={onBroadcast}
          className="mb-1 flex w-full items-center gap-2 px-2.5 py-2 text-left text-[12px] text-[#ff8a3d] hover:bg-[#1a1420]"
        >
          <Radio size={14} />
          Emergency Broadcast
        </button>
        <button
          type="button"
          onClick={onReset}
          className="flex w-full items-center gap-2 px-2.5 py-2 text-left text-[12px] text-ops-300 hover:bg-[#101a2c]"
        >
          <LogOut size={14} />
          Logout
        </button>
        <div className="mt-2 flex items-center gap-1.5 px-2.5 pb-2 text-[10px] text-ops-400">
          <Activity size={11} />
          Node V2.4 · local prototype
        </div>
      </div>
    </aside>
  );
}

function Counter({ label, value, tone }) {
  return (
    <div className="flex items-center justify-between border border-[#1e2d45] bg-[#0d1626] px-2 py-1.5">
      <span className="text-ops-300">{label}</span>
      <span className="font-mono text-[12px] text-white">
        <span style={{ color: tone }}>●</span> {String(value).padStart(3, "0")}
      </span>
    </div>
  );
}
