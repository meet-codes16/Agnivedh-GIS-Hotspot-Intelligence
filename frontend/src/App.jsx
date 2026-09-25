import { apiUrl } from "./utils/api";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import ClassificationPanel from "./components/ClassificationPanel";
import BaselinePanel from "./components/BaselinePanel";
import FeaturePanel from "./components/FeaturePanel";
import EventHistoryPanel from "./components/EventHistoryPanel";
import ForecastPanel from "./components/ForecastPanel";
import HotspotDetails from "./components/HotspotDetails";
import MapLegend from "./components/MapLegend";
import MapView from "./components/MapView";
import NearbyPlaces from "./components/NearbyPlaces";
import RiskPanel from "./components/RiskPanel";
import Sidebar from "./components/Sidebar";
import StatusBadge from "./components/StatusBadge";
import TopBar from "./components/TopBar";
import ManualValidationPanel from "./components/ManualValidationPanel";
import { buildIntelligenceRecords } from "./utils/pipeline";
import { getValidatedIncident } from "./data/validatedIncidents2024";

export default function App() {
  const [showBottomPanel, setShowBottomPanel] = useState(false);
  const [isPending, startTransition] = useTransition();
  const queryCache = useRef(new Map());
  const [rawHotspots, setRawHotspots] = useState([]);
  const [source, setSource] = useState("waiting-for-real-data");
  const [activeNav, setActiveNav] = useState("overview");
  const [selectedId, setSelectedId] = useState(null);
  const [intelOpen, setIntelOpen] = useState(false);
  const [baseLayer, setBaseLayer] = useState("street");
  const [broadcast, setBroadcast] = useState(null);
  const [resetToken, setResetToken] = useState(0);
  const [osmFacility, setOsmFacility] = useState(null);
  const [osmLoading, setOsmLoading] = useState(false);
  const [osmElapsedSeconds, setOsmElapsedSeconds] = useState(0);
  const [osmStatus, setOsmStatus] = useState(null);
  const [criticalContext, setCriticalContext] = useState(null);
  const [fetchYear, setFetchYear] = useState("2024");
  const [fetchDate, setFetchDate] = useState("");
  const [fetchDaynight, setFetchDaynight] = useState("ALL");
  const [fetchingHotspots, setFetchingHotspots] = useState(false);
  const [fetchMessage, setFetchMessage] = useState("");
  const [fetchPanelOpen, setFetchPanelOpen] = useState(false);
  const [baselineGridCount, setBaselineGridCount] = useState(0);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  const [manualHotspot, setManualHotspot] = useState(null);

  useEffect(() => {
    if (!osmLoading) {
      setOsmElapsedSeconds(0);
      return undefined;
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      setOsmElapsedSeconds(Math.floor((Date.now() - started) / 1000));
    }, 250);
    return () => window.clearInterval(timer);
  }, [osmLoading]);

  const allRecords = useMemo(() => buildIntelligenceRecords(rawHotspots), [rawHotspots]);

  const anomalyRecords = useMemo(() => {
    return allRecords.filter((r) => {
      const riskLevel = String(r.risk?.level || "").toUpperCase();
      const fireStatus = String(r.fireDetection?.status || "").toUpperCase();
      return riskLevel === "HIGH" || riskLevel === "CRITICAL" || fireStatus === "LIKELY FIRE";
    });
  }, [allRecords]);

  const records = useMemo(() => {
    if (activeNav === "anomalies") {
      return anomalyRecords;
    }
    if (activeNav === "facilities") {
      return allRecords.filter((r) => r.classification?.label === "Industry");
    }
    if (activeNav === "hotspots") {
      return [...allRecords].sort((a, b) => (b.risk?.score || 0) - (a.risk?.score || 0));
    }
    return allRecords;
  }, [allRecords, activeNav]);

  const selectedRecord = allRecords.find((r) => r.hotspot.id === selectedId) || null;
  const dateDeviationMax = useMemo(() => {
    if (!allRecords.length) return 0;
    return Math.max(
      ...allRecords.map((r) => Math.abs(Number(r.comparison?.frp_deviation || 0)))
    );
  }, [allRecords]);
  const displayedSelectedRecord = selectedAnalysis && selectedRecord
    ? {
        ...selectedRecord,
        ...selectedAnalysis,
        comparison: {
          ...(selectedAnalysis.comparison || selectedRecord.comparison || {}),
          baseline_deviation_score: dateDeviationMax > 0
            ? Math.round((Math.abs(Number(selectedAnalysis.comparison?.frp_deviation || 0)) / dateDeviationMax) * 100)
            : 0,
          baseline_deviation_reference: "max absolute FRP deviation in loaded 2024 date/day-night set",
        },
        fireDetection: selectedAnalysis.fire_detection || selectedRecord.fireDetection,
        criticalContext: selectedAnalysis.critical_context || null,
        sourceHistory: selectedAnalysis.source_history || null,
      }
    : selectedRecord;
  const selected = displayedSelectedRecord?.hotspot;

  const aggregate = useMemo(() => {
    const counts = {};
    allRecords.forEach((r) => {
      const label = r.classification?.label;
      if (label) counts[label] = (counts[label] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([label, count]) => ({ label, count, probability: count }))
      .sort((a, b) => b.count - a.count);
  }, [allRecords]);

  const anomalyCount = anomalyRecords.length;

  const regionCount = useMemo(
    () => new Set(allRecords.map((r) => r.hotspot.region_key).filter(Boolean)).size,
    [allRecords]
  );

  const facilityCount = allRecords.filter((r) => r.classification?.label === "Industry").length;

  function handleManualValidation(payload) {
  const hotspot = payload?.hotspot;
  if (!hotspot) return;

  const manualRecord = {
    ...hotspot,
    id: "MANUAL-VALIDATION",
    classification: payload.classification || null,
    fire_detection: payload.fire_detection || null,
    risk: payload.risk || null,
    nearby: payload.nearby || [],
    baseline: payload.baseline || null,
    comparison: payload.comparison || null,
    features: payload.features || null,
    worldcover: payload.worldcover || null,
    nearest_industry: payload.nearest_industry || null,
    critical_context: payload.critical_context || null,
  };

  setManualHotspot(manualRecord);
  setRawHotspots((prev) => [
    ...prev.filter((item) => item.id !== "MANUAL-VALIDATION"),
    manualRecord,
  ]);
  setSelectedId("MANUAL-VALIDATION");
  setSelectedAnalysis(payload);
  setOsmFacility(payload.nearest_industry || null);
  setCriticalContext(payload.critical_context || null);
  setOsmStatus(payload.osm_context || null);
  setOsmLoading(false);
  setShowBottomPanel(true);
  setBaseLayer("satellite");
  setIntelOpen(true);
}
async function handleSelect(id) {
    setSelectedId(id);
    setShowBottomPanel(true);
    setBaseLayer("satellite");
    setIntelOpen(true);
    setOsmFacility(null);
    setOsmStatus(null);
    setCriticalContext(null);
    setSelectedAnalysis(null);
    setOsmLoading(true);
    setOsmElapsedSeconds(0);

    try {
      const analysisRes = await fetch(apiUrl(`/api/analysis/${id}`));
      const analysisPayload = await analysisRes.json();
      if (analysisRes.ok) {
        setSelectedAnalysis(analysisPayload);
      }
      if (analysisRes.ok) {
        setOsmFacility(analysisPayload?.nearest_industry || null);
        setCriticalContext(analysisPayload?.critical_context || null);
        setOsmStatus(analysisPayload?.osm_context || null);
      }
    } catch (error) {
      console.error("OSM facility lookup failed:", error);
      setOsmFacility(null);
    } finally {
      setOsmLoading(false);
    }
  }

  async function handleHistoricalFetch() {
    if (!fetchDate) {
      setFetchMessage("Select a date first.");
      return;
    }
    if (!fetchDate.startsWith(`${fetchYear}-`)) {
      setFetchMessage("Selected date must belong to the selected year.");
      return;
    }

    setFetchingHotspots(true);
    setFetchMessage("");
    try {
      const cacheKey = `${fetchYear}-${fetchDate}-${fetchDaynight}`;
      const cached = queryCache.current.get(cacheKey);
      let payload = cached || null;

      if (cached) {
        startTransition(() => {
          setRawHotspots(cached.hotspots || []);
          setSource(cached.source || "internal_2024_firms_csv");
          setBaselineGridCount(cached.baseline?.grid_count || 0);
        });
      } else {
        const params = new URLSearchParams({ year: fetchYear, acq_date: fetchDate });
      if (fetchDaynight !== "ALL") params.set("daynight", fetchDaynight);
      const res = await fetch(apiUrl(`/api/hotspots/query?${params.toString()}`));
      payload = await res.json();
      if (!res.ok) throw new Error(payload?.detail || "Unable to fetch hotspots");

      setRawHotspots(payload.hotspots || []);
      setSource(payload.source || "internal_2024_firms_csv");
        queryCache.current.set(cacheKey, payload);

        startTransition(() => {
          setRawHotspots(payload.hotspots || []);
          setSource(payload.source || "internal_2024_firms_csv");
          setBaselineGridCount(payload.baseline?.grid_count || 0);
        });
      }
      setSelectedId(null);
    setSelectedAnalysis(null);
    setOsmFacility(null);
    setOsmStatus(null);
    setCriticalContext(null);
    setOsmLoading(false);
      setIntelOpen(false);
      setActiveNav("overview");
      setFetchMessage(
        `${payload.count || 0} real hotspots loaded • ${fetchDaynight === "ALL" ? "Day + Night" : fetchDaynight === "D" ? "Day" : "Night"}`
      );
    } catch (error) {
      setFetchMessage(error.message || "Hotspot fetch failed.");
    } finally {
      setFetchingHotspots(false);
    }
  }

  function handleReset() {
    setRawHotspots([]);
    setBaselineGridCount(0);
    setFetchMessage("");
    setFetchingHotspots(false);
    setSelectedId(null);
    setSelectedAnalysis(null);
    setOsmFacility(null);
    setOsmStatus(null);
    setCriticalContext(null);
    setOsmLoading(false);
    setIntelOpen(false);
    setBaseLayer("street");
    setActiveNav("overview");
    setResetToken((n) => n + 1);
  }



  return (
    <div className="flex h-full flex-col bg-ops-950 text-ops-300">
      <TopBar
        hotspotCount={allRecords.length}
        highAnomalyCount={anomalyCount}
        selected={selected}
        regionCount={regionCount}
      />

      <div className="flex min-h-0 flex-1">
        <Sidebar
          activeNav={activeNav}
          onNav={setActiveNav}
          hotspotCount={allRecords.length}
          anomalyCount={anomalyCount}
          facilityCount={facilityCount}
          onBroadcast={() => setBroadcast("EMERGENCY CHANNEL ARMED — prototype only. No live dispatch.")}
          onReset={handleReset}
        />

        <main className="relative min-w-0 flex-1">
          <MapView
            records={records}
            selectedId={selectedId}
            selectedHotspot={selectedId === "MANUAL-VALIDATION" ? manualHotspot : selected}
            nearby={displayedSelectedRecord?.nearby || []}
            osmFacility={osmFacility}
            criticalContext={criticalContext}
            osmStatus={osmStatus}
            baseLayer={baseLayer}
            onSelect={handleSelect}
            onViewIntelligence={handleSelect}
            resetToken={resetToken}
            layoutToken={`${intelOpen}-${activeNav}-${rawHotspots.length}`}
            datasetToken={`${source}-${fetchDate}-${fetchDaynight}-${rawHotspots.length}`}
          />

          <div className="pointer-events-none absolute left-3 top-3 z-[500] flex flex-wrap gap-2">
            <div className="pointer-events-auto panel-glass px-2 py-1.5 font-mono text-[11px] text-ops-300">
              {selected ? `${selected.latitude.toFixed(4)}, ${selected.longitude.toFixed(4)}` : "INDIA / CENTRAL BELT"}
            </div>
            <div className="pointer-events-auto flex overflow-hidden border border-[#2a3c58] bg-[#0c1422]/90 text-[10px]">
              {["street", "satellite", "hybrid"].map((layer) => (
                <button
                  key={layer}
                  type="button"
                  onClick={() => setBaseLayer(layer)}
                  className={`px-2 py-1.5 uppercase tracking-wider ${baseLayer === layer ? "bg-[#1a2b44] text-[#3ec7ff]" : "text-ops-300"}`}
                >
                  {layer === "street" ? "OSM" : layer}
                </button>
              ))}
            </div>
          </div>

          <div className="pointer-events-none absolute right-3 top-3 z-[500] w-[240px] panel-glass p-2 text-[10px]">
            <div className="tracking-[0.14em] text-[#ff6b6b]">SATELLITE STATUS</div>
            <div className="mt-1 text-ops-300">LAYER: <span className="text-white">{baseLayer.toUpperCase()}</span></div>
            <div className="text-ops-300">SENSOR: <span className="text-white">{selected?.instrument || "VIIRS / MODIS"}</span></div>
            <div className="text-ops-300">PASS: <span className="text-white">{selected ? `${selected.acq_date} ${selected.acq_time}` : "REGIONAL MOSAIC"}</span></div>
            <div className="mt-1 text-[9px] text-ops-400">Data source: {source}</div>
          </div>

          {/* Only new control: it occupies the old detection-list space and does not redesign the dashboard. */}
          <div className="pointer-events-auto absolute left-3 top-[72px] z-[540]">
            <button
              type="button"
              onClick={() => setFetchPanelOpen((open) => !open)}
              className="border border-[#2a3c58] bg-[#0c1422]/95 px-2 py-1.5 text-[10px] uppercase tracking-wider text-[#3ec7ff] shadow-panel"
            >
              {fetchPanelOpen ? "Close search" : "SEARCH 2024 FIRMS OBSERVATIONS"}
            </button>
            {fetchPanelOpen && (
              <div className="mt-1 max-h-[calc(100vh-92px)] w-[270px] overflow-y-auto panel-glass p-3 shadow-panel scroll-thin">
                <div className="mb-2 text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">SEARCH 2024 FIRMS OBSERVATIONS</div>
                <div className="mb-2 text-[8px] leading-3 text-ops-500">Search the supplied 2024 FIRMS observations by date and day/night. Select a result to inspect ML, baseline, Industry and critical GIS context.</div>
                <div className="grid grid-cols-1 gap-2">
                  <label className="text-[9px] uppercase tracking-wider text-ops-400">
                    Day / Night
                    <select
                      value={fetchDaynight}
                      onChange={(e) => setFetchDaynight(e.target.value)}
                      className="mt-1 w-full border border-[#2a3c58] bg-[#0a1220] px-2 py-1.5 font-mono text-[10px] text-white outline-none"
                    >
                      <option value="ALL">ALL</option>
                      <option value="D">DAY</option>
                      <option value="N">NIGHT</option>
                    </select>
                  </label>
                </div>
                <label className="mt-2 block text-[9px] uppercase tracking-wider text-ops-400">
                  Date
                  <input
                    type="date"
                    value={fetchDate}
                    min="2024-01-01"
                    max="2024-12-31"
                    onChange={(e) => setFetchDate(e.target.value)}
                    className="mt-1 w-full border border-[#2a3c58] bg-[#0a1220] px-2 py-1.5 font-mono text-[10px] text-white outline-none"
                  />
                </label>
                <button
                  type="button"
                  onClick={handleHistoricalFetch}
                  disabled={fetchingHotspots}
                  className="mt-2 w-full border border-[#3ec7ff]/50 bg-[#10253a] px-2 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#3ec7ff] hover:bg-[#15334e] disabled:cursor-wait disabled:opacity-50"
                >
                  {fetchingHotspots ? "SEARCHING..." : "SEARCH & CLASSIFY"}
                </button>
                <div className="mt-2 text-[9px] leading-4 text-ops-400">Search the supplied FIRMS observations by date/day-night, then select a hotspot to validate its ML + GIS context.</div>
                {fetchMessage && <div className="mt-2 border-t border-[#1e2d45] pt-2 text-[9px] leading-4 text-white">{fetchMessage}</div>}
                <ManualValidationPanel onManualResult={handleManualValidation} />
              </div>
            )}
          </div>

          <div className="pointer-events-none absolute left-[268px] top-3 z-[400] hidden max-w-[520px] text-[9px] tracking-[0.12em] text-ops-400 xl:block">
            FIRMS → DETECTION → GIS + BASELINE → FEATURES → CLASSIFIER → RISK
          </div>

          <div className="pointer-events-none absolute bottom-[270px] left-3 z-[500] hidden md:block">
            <MapLegend />
          </div>

          {!selectedRecord && activeNav !== "anomalies" && (
            <div className="pointer-events-none absolute right-3 top-[118px] z-[500] w-[240px] panel-glass p-3 text-[11px]">
              <div className="mb-2 text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">OPERATIONAL OVERVIEW</div>
              <div className="space-y-1 text-ops-300">
                <div className="flex justify-between"><span>Detections</span><span className="font-mono text-white">{allRecords.length}</span></div>
                <div className="flex justify-between"><span>Regions</span><span className="font-mono text-white">{regionCount}</span></div>
                <div className="flex justify-between"><span>Facilities</span><span className="font-mono text-white">{facilityCount}</span></div>
                <div className="flex justify-between"><span>High anomalies</span><span className="font-mono text-[#ff6b6b]">{anomalyCount}</span></div>
              </div>
              <p className="mt-2 text-[10px] leading-4 text-ops-400">Click a real hotspot marker to open GIS intelligence.</p>
            </div>
          )}

          {activeNav === "anomalies" && allRecords.length > 0 && (
            <div className="pointer-events-auto absolute right-3 top-[118px] z-[500] w-[310px] max-h-[calc(100%-390px)] overflow-auto panel-glass p-3 shadow-panel scroll-thin">
              <div className="mb-2 flex items-center justify-between">
                <div>
                  <div className="text-[10px] font-semibold tracking-[0.16em] text-[#ff6b6b]">2024 MODEL ANOMALIES</div>
                  <div className="mt-1 text-[8px] font-mono text-ops-500">REAL LOADED FIRMS EVENTS · MODEL OUTPUT</div>
                </div>
                <span className="font-mono text-[11px] text-white">{records.length}</span>
              </div>
              <div className="space-y-1.5">
                {[...records]
                  .sort((a, b) => (b.fireDetection?.fire_confidence || 0) - (a.fireDetection?.fire_confidence || 0) || (b.risk?.score || 0) - (a.risk?.score || 0))
                  .slice(0, 12)
                  .map((r) => (
                    <button
                      key={r.hotspot.id}
                      type="button"
                      onClick={() => handleSelect(r.hotspot.id)}
                      className="w-full border border-[#243650] bg-[#0b1520]/90 px-2 py-2 text-left hover:border-[#3ec7ff]/60"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[9px] text-[#3ec7ff]">{r.hotspot.id}</span>
                        <span className="font-mono text-[9px] text-[#ff6b6b]">{r.risk?.level || "—"} {r.risk?.score ?? "—"}</span>
                      </div>
                      <div className="mt-1 text-[9px] text-white">{r.hotspot.acq_date} {String(r.hotspot.acq_time).padStart(4, "0")} · {r.classification?.label || "—"}</div>
                      <div className="mt-1 text-[8px] text-ops-400">Fire evidence {r.fireDetection?.fire_confidence ?? "—"}% · {r.fireDetection?.status || "—"}</div>
                      {getValidatedIncident(r.hotspot.id) && (
                        <div className="mt-1 text-[8px] font-semibold tracking-wide text-[#5dcc8a]">FSI LFF CORROBORATION · {getValidatedIncident(r.hotspot.id).name}</div>
                      )}
                    </button>
                  ))}
              </div>
            </div>
          )}

          {broadcast && (
            <div className="absolute left-1/2 top-14 z-[600] -translate-x-1/2 border border-[#ff8a3d] bg-[#1a120c] px-3 py-1.5 text-[11px] text-[#ffb080]">
              {broadcast}
              <button className="ml-3 text-ops-400" type="button" onClick={() => setBroadcast(null)}>dismiss</button>
            </div>
          )}

          {intelOpen && displayedSelectedRecord && (
            <aside className="absolute right-3 top-[118px] z-[550] w-[300px] max-h-[calc(100%-390px)] overflow-auto panel-glass p-3 shadow-panel scroll-thin">
              <div className="mb-2 flex items-center justify-between">
                <div className="font-mono text-[12px] text-white">{displayedSelectedRecord.hotspot.id}</div>
                <div className="flex items-center gap-2">
                  <StatusBadge
                    label={displayedSelectedRecord.risk?.level || "—"}
                    tone={displayedSelectedRecord.risk?.level === "CRITICAL" || displayedSelectedRecord.risk?.level === "HIGH" ? "red" : "amber"}
                  />
                  <button type="button" className="text-[10px] text-ops-400 hover:text-white" onClick={() => setIntelOpen(false)}>close</button>
                </div>
              </div>
              <HotspotDetails
  hotspot={displayedSelectedRecord.hotspot}
  classification={displayedSelectedRecord.classification}
  fireDetection={displayedSelectedRecord.fireDetection}
  risk={displayedSelectedRecord.risk}
  osmFacility={osmFacility}
  criticalContext={criticalContext}
  osmLoading={osmLoading}
  osmStatus={osmStatus}
/>
              <div className="my-3"><NearbyPlaces
  places={displayedSelectedRecord.nearby}
  osmFacility={osmFacility}
  criticalContext={criticalContext}
  osmLoading={osmLoading}
  osmElapsedSeconds={osmElapsedSeconds}
/></div>
              <FeaturePanel features={displayedSelectedRecord.features} />
              <div className="mt-3"><EventHistoryPanel history={displayedSelectedRecord.sourceHistory} /></div>
              <div className="mt-3 border-t border-[#1e2d45] pt-2 text-[10px] text-ops-300">
                <div className="mb-1 text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">AI ENGINE STATUS</div>
                <div>Model: {displayedSelectedRecord.classification?.model || "real_trained_model"}</div>
                <div>Status: ONLINE</div>
                <div>Validation: Held-out temporal test</div>
                <div>
                  Confidence: {displayedSelectedRecord.classification?.confidence != null
                    ? `${displayedSelectedRecord.classification.confidence}% model probability`
                    : "—"}
                </div>
                <div className="text-[9px] text-ops-500">Probability is not calibrated.</div>
              </div>
            </aside>
          )}

          <section
            className="absolute bottom-0 left-0 right-0 z-[520] grid h-[258px] grid-cols-1 gap-px overflow-auto border-t border-[#35506f] bg-[#07101a]/78 p-3 pt-9 backdrop-blur-xl transition-transform duration-300 ease-out sm:grid-cols-2 lg:grid-cols-4"
            style={{
              transform: showBottomPanel
                ? "translateY(0)"
                : "translateY(calc(100% - 34px))",
            }}
          >
            <button
              type="button"
              onClick={() => setShowBottomPanel((value) => !value)}
              className="absolute left-1/2 top-0 z-30 flex h-8 w-32 -translate-x-1/2 items-center justify-center rounded-t-md border border-[#35506f] bg-[#08131f]/88 text-[10px] font-mono font-semibold tracking-[0.14em] text-[#3ec7ff] shadow-[0_-4px_18px_rgba(0,0,0,0.35)] hover:bg-[#122235]"
              title={showBottomPanel ? "Hide analysis" : "Show analysis"}
            >
              {showBottomPanel ? (
                <>
                  <ChevronDown size={13} />
                  HIDE ANALYSIS
                </>
              ) : (
                <>
                  <ChevronUp size={13} />
                  SHOW ANALYSIS
                </>
              )}
            </button>

            <div className="min-w-0 overflow-hidden border border-[#30465c]/80 bg-[#0b1520]/72 p-2">
              <ClassificationPanel
                classification={displayedSelectedRecord?.classification}
                fireDetection={displayedSelectedRecord?.fireDetection}
                aggregate={aggregate}
              />
            </div>

            <div className="min-w-0 overflow-hidden border border-[#30465c]/80 bg-[#0b1520]/72 p-2">
              <BaselinePanel
                comparison={displayedSelectedRecord?.comparison}
                baseline={displayedSelectedRecord?.baseline}
                hotspot={displayedSelectedRecord?.hotspot}
                loadedCount={allRecords.length}
                baselineGridCount={baselineGridCount}
              />
            </div>

            <div className="min-w-0 overflow-hidden border border-[#30465c]/80 bg-[#0b1520]/72 p-2">
              <RiskPanel
                risk={displayedSelectedRecord?.risk}
              />
            </div>

            <div className="min-w-0 overflow-hidden border border-[#30465c]/80 bg-[#0b1520]/72 p-2">
              <ForecastPanel
                comparison={displayedSelectedRecord?.comparison}
                baseline={displayedSelectedRecord?.baseline}
                hotspot={displayedSelectedRecord?.hotspot}
                records={allRecords}
              />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}












