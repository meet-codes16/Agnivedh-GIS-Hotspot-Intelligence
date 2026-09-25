import { apiUrl } from "../utils/api";
import { useState } from "react";

const WORLD_COVER = [
  [10, "Tree cover"], [20, "Shrubland"], [30, "Grassland"], [40, "Cropland"],
  [50, "Built-up"], [60, "Bare / sparse vegetation"], [70, "Snow / ice"],
  [80, "Permanent water"], [90, "Herbaceous wetland"], [95, "Mangroves"], [100, "Moss / lichen"],
];

const initial = {
  latitude: "", longitude: "", brightness: "", bright_t31: "", frp: "", scan: "", track: "",
  confidence: "h", daynight: "D", type: "0", acq_date: "2025-01-01", acq_time: "1200",
  satellite: "VIIRS", instrument: "VIIRS", version: "1.0", worldcover_code: "",
};

export default function ManualValidationPanel({ onManualResult }) {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function update(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const body = {
        ...form,
        latitude: Number(form.latitude), longitude: Number(form.longitude),
        brightness: Number(form.brightness), bright_t31: Number(form.bright_t31),
        frp: Number(form.frp), scan: Number(form.scan), track: Number(form.track),
        type: Number(form.type),
        worldcover_code: form.worldcover_code ? Number(form.worldcover_code) : null,
      };
      const res = await fetch(apiUrl("/api/validation/manual"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload?.detail || "Manual validation failed");
      setResult(payload);
      onManualResult?.(payload);
    } catch (err) {
      setResult(null);
      setError(err.message || "Manual validation failed");
    } finally {
      setLoading(false);
    }
  }

  const c = result?.classification;
  const fire = result?.fire_detection;
  const risk = result?.risk;
  const critical = result?.critical_context;
  const industry = result?.nearest_industry;

  return (
    <div className="mt-2 border border-[#2a3c58] bg-[#091321]/95">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-2.5 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-[#3ec7ff]"
      >
        <span>Manual scenario validation</span>
        <span className="text-ops-500">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <form onSubmit={submit} className="max-h-[62vh] overflow-y-auto border-t border-[#1e2d45] p-2.5 scroll-thin">
          <div className="mb-2 text-[8px] leading-4 text-ops-400">
            FIRMS-style inputs only. The same trained model, 2022–2023 baseline, fire-evidence and GIS pipeline are reused.
          </div>

          <div className="grid grid-cols-2 gap-1.5">
            {[
              ["latitude", "Latitude"], ["longitude", "Longitude"], ["brightness", "Brightness"],
              ["bright_t31", "Bright T31"], ["frp", "FRP"], ["scan", "Scan"], ["track", "Track"],
            ].map(([key, label]) => (
              <label key={key} className="text-[8px] uppercase tracking-wider text-ops-400">
                {label}
                <input required type="number" step="any" value={form[key]} onChange={(e) => update(key, e.target.value)} placeholder="—" className="mt-0.5 w-full border border-[#2a3c58] bg-[#0a1220] px-1.5 py-1.5 font-mono text-[10px] text-white outline-none" />
              </label>
            ))}

            <label className="text-[8px] uppercase tracking-wider text-ops-400">
              Confidence
              <select value={form.confidence} onChange={(e) => update("confidence", e.target.value)} className="mt-0.5 w-full border border-[#2a3c58] bg-[#0a1220] px-1.5 py-1.5 font-mono text-[10px] text-white outline-none">
                <option value="h">HIGH (H)</option><option value="n">NOMINAL (N)</option><option value="l">LOW (L)</option>
              </select>
            </label>
            <label className="text-[8px] uppercase tracking-wider text-ops-400">
              Day / Night
              <select value={form.daynight} onChange={(e) => update("daynight", e.target.value)} className="mt-0.5 w-full border border-[#2a3c58] bg-[#0a1220] px-1.5 py-1.5 font-mono text-[10px] text-white outline-none"><option value="D">DAY</option><option value="N">NIGHT</option></select>
            </label>
            <label className="text-[8px] uppercase tracking-wider text-ops-400">
              Date
              <input required type="date" value={form.acq_date} onChange={(e) => update("acq_date", e.target.value)} className="mt-0.5 w-full border border-[#2a3c58] bg-[#0a1220] px-1.5 py-1.5 font-mono text-[10px] text-white outline-none" />
            </label>
            <label className="text-[8px] uppercase tracking-wider text-ops-400">
              FIRMS time
              <input required inputMode="numeric" value={form.acq_time} onChange={(e) => update("acq_time", e.target.value.replace(/\D/g, "").slice(0, 4))} className="mt-0.5 w-full border border-[#2a3c58] bg-[#0a1220] px-1.5 py-1.5 font-mono text-[10px] text-white outline-none" />
            </label>
          </div>

          


          <button disabled={loading} className="mt-2 w-full border border-[#3ec7ff]/50 bg-[#10253a] px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#3ec7ff] disabled:opacity-50">
            {loading ? "RUNNING SAME PIPELINE..." : "RUN MANUAL VALIDATION"}
          </button>
<div className="mt-2 border-t border-[#1e2d45] pt-2">
            <div className="mb-1 text-[8px] font-semibold tracking-[0.12em] text-[#3ec7ff]">GIS MODEL CONTEXT</div>
            <label className="text-[8px] uppercase tracking-wider text-ops-400">
              WorldCover override (optional)
              <select value={form.worldcover_code} onChange={(e) => update("worldcover_code", e.target.value)} className="mt-0.5 w-full border border-[#2a3c58] bg-[#0a1220] px-1.5 py-1.5 font-mono text-[10px] text-white outline-none">
                <option value="">AUTO FROM COORDINATES</option>
                {WORLD_COVER.map(([code, label]) => <option key={code} value={code}>{code} · {label}</option>)}
              </select>
            </label>
            <div className="mt-1 text-[8px] leading-3 text-ops-500">NASA FIRMS does not provide WorldCover. AgniVedh resolves ESA WorldCover from latitude/longitude when available; manual override is only a fallback.</div>
          </div>

          {error && <div className="mt-2 border border-[#7f3c3c] bg-[#241116] p-2 text-[9px] text-[#ff9b9b]">{error}</div>}

          {result && (
            <div className="mt-2 space-y-1.5 border-t border-[#1e2d45] pt-2">
              <div className="text-[8px] font-semibold tracking-[0.14em] text-[#3ec7ff]">VALIDATION OUTPUT</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[9px]">
                <span className="text-ops-500">Predicted source</span><span className="font-semibold text-white">{c?.label || "—"}</span>
                <span className="text-ops-500">Model confidence</span><span className="font-mono text-white">{c?.confidence ?? "—"}%</span>
                <span className="text-ops-500">Fire evidence</span><span className="font-mono text-white">{fire?.fire_confidence ?? "—"}% · {fire?.status || "—"}</span>
                <span className="text-ops-500">Risk</span><span className="font-semibold text-white">{risk?.level || "—"} · {risk?.score ?? "—"}/100</span>
                <span className="text-ops-500">Nearest industry</span><span className="text-white">{industry ? `${industry.name} · ${industry.distance_km} km` : "None"}</span>
                <span className="text-ops-500">Critical context</span><span className="font-semibold text-white">{critical ? `${critical.name || critical.display_name || critical.category} · ${critical.distance_km} km` : "None detected"}</span>
                <span className="text-ops-500">WorldCover</span><span className="font-mono text-white">{result.worldcover?.class || result.worldcover?.code || "UNRESOLVED"}</span>
              </div>
              {result.validation?.worldcover_warning && <div className="border border-[#6d5b2c] bg-[#211c0e] p-1.5 text-[8px] leading-3 text-[#e8ce7a]">{result.validation.worldcover_warning}</div>}
              <div className="text-[8px] text-ops-500">This is a manual FIRMS validation case. It may represent an unseen 2025 observation and is not part of the 2024 dataset.</div>
            </div>
          )}
        </form>
      )}
    </div>
  );
}













