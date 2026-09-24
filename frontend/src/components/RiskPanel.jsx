export default function RiskPanel({ risk }) {
  if (!risk) {
    return (
      <div className="h-full">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">RISK ASSESSMENT</h3>
        <p className="text-[11px] leading-5 text-ops-400">
          Select a hotspot to compute prototype risk from FRP deviation, persistence, night activity, source class, and GIS proximity.
        </p>
      </div>
    );
  }

  const tone =
    risk.level === "CRITICAL"
      ? "border-[#ff4d4d] bg-[#ff4d4d]/15 text-[#ff6b6b]"
      : risk.level === "HIGH"
        ? "border-[#ff8a3d] bg-[#ff8a3d]/15 text-[#ff8a3d]"
        : risk.level === "MODERATE"
          ? "border-[#f0c14b] bg-[#f0c14b]/15 text-[#f0c14b]"
          : "border-[#5dcc8a] bg-[#5dcc8a]/15 text-[#5dcc8a]";

  return (
    <div className="flex h-full min-w-0 flex-col">
      <h3 className="mb-2 text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">RISK ASSESSMENT</h3>
      <div className={`mb-2 border px-2 py-1.5 text-[11px] font-semibold tracking-wider ${tone}`}>
        THREAT LEVEL: {risk.level}
      </div>
      <div className="mb-2 font-mono text-[12px] text-white">
        SCORE <span className="text-lg">{risk.score}</span>
        <span className="text-ops-400"> / 100</span>
      </div>
      <div className="space-y-1.5">
        {risk.drivers.map((driver) => (
          <div key={driver.name}>
            <div className="mb-0.5 flex justify-between text-[10px] text-ops-300">
              <span>{driver.name}</span>
              <span className={driver.level === "HIGH" ? "text-[#ff6b6b]" : "text-ops-300"}>{driver.level}</span>
            </div>
            <div className="meter">
              <span
                style={{
                  width: `${Math.round(driver.value * 100)}%`,
                  background: driver.level === "HIGH" ? "#ff4d4d" : driver.level === "MODERATE" ? "#f0c14b" : "#3ec7ff",
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-auto pt-2 text-[9px] text-ops-400">Prototype scoring · not scientifically validated</div>
    </div>
  );
}
