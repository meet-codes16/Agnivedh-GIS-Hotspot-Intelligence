import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

const COLORS = {
  Wildfire: "#5dcc8a",
  Agriculture: "#f0c14b",
  "Agricultural Burning": "#f0c14b",
  Industry: "#ff6b6b",
  Industrial: "#ff6b6b",
  "Gas Flare": "#ff8a3d",
  Mining: "#c9845a",
  Other: "#7d8da8",
};

export default function ClassificationPanel({ classification, fireDetection, aggregate }) {
  const selected = classification?.label || "—";
  const data = (classification?.distribution || aggregate || []).map((item) => ({
    name: item.label,
    value: item.probability ?? item.count ?? 0,
  }));

  return (
    <div className="flex h-full min-w-0 flex-col">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">AI CLASSIFICATION</h3>
        <span className="text-[9px] text-ops-400">2024 FIRMS + TRAINED MODEL</span>
      </div>
      <div className="flex min-h-0 flex-1 items-center gap-3">
        <div className="relative h-[108px] w-[108px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data.length ? data : [{ name: "none", value: 1 }]}
                dataKey="value"
                innerRadius={34}
                outerRadius={50}
                paddingAngle={1}
                stroke="none"
              >
                {(data.length ? data : [{ name: "none" }]).map((entry) => (
                  <Cell key={entry.name} fill={COLORS[entry.name] || "#2a3c58"} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <div className="font-mono text-lg leading-none text-white">
              {fireDetection ? `${fireDetection.fire_confidence}` : classification ? `${classification.confidence}` : data.reduce((s, d) => s + d.value, 0) || "—"}
            </div>
            <div className="text-[8px] tracking-wider text-ops-400">{fireDetection ? "FIRE %" : classification ? "TYPE %" : "N"}</div>
          </div>
        </div>
        <div className="min-w-0 flex-1">
          {fireDetection && (
            <div className="mb-1.5 border border-[#2a3c58] bg-[#08131f]/70 px-2 py-1.5">
              <div className="flex items-center justify-between text-[9px]">
                <span className="text-ops-400">FIRE CONFIDENCE</span>
                <span className={`font-mono font-semibold ${fireDetection.fire_confidence >= 70 ? "text-[#5dcc8a]" : fireDetection.fire_confidence >= 45 ? "text-[#f0c14b]" : "text-[#ff8a3d]"}`}>{fireDetection.fire_confidence}%</span>
              </div>
              <div className="mt-0.5 text-[9px] font-semibold tracking-wide text-white">{fireDetection.status}</div>
              <div className="mt-1 text-[8px] leading-3 text-ops-500">
                FIRMS signal + prior 2024 spatial/temporal evidence; not a ground-truth-calibrated fire probability.
              </div>
            </div>
          )}
          <div className="text-[9px] text-ops-400">SOURCE / FIRE TYPE</div>
          <div className="truncate text-[13px] font-semibold text-white">{selected}</div>
          <div className="mt-0.5 text-[9px] text-ops-400">TYPE CONFIDENCE <span className="font-mono text-ops-300">{classification?.confidence ?? "—"}%</span></div>
          {classification?.alternatives?.map((alt) => (
            <div key={alt.label} className="mt-1 flex items-center justify-between text-[10px] text-ops-300">
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5" style={{ background: COLORS[alt.label] }} />
                {alt.label}
              </span>
              <span className="font-mono">{alt.probability}%</span>
            </div>
          ))}
          {!classification && !fireDetection &&
            data.slice(0, 5).map((item) => (
              <div key={item.name} className="mt-0.5 flex items-center justify-between text-[10px] text-ops-300">
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5" style={{ background: COLORS[item.name] }} />
                  {item.name}
                </span>
                <span className="font-mono">{item.value}</span>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
