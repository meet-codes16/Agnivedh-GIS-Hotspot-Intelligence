export default function NearbyPlaces({
  places = [],
  osmFacility = null,
  criticalContext = null,
  osmLoading = false,
  osmStatus = null,
  osmElapsedSeconds = 0,
}) {
  return (
    <div>
      <h3 className="mb-2 text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">NEARBY GIS CONTEXT</h3>
      <div className="mb-3 border border-ops-700/60 bg-ops-950/40 p-2">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-[10px] font-semibold tracking-[0.12em] text-[#3ec7ff]">
            NEAREST INDUSTRY
          </span>
          <span className="text-[9px] text-ops-500">OSM</span>
        </div>

        {osmLoading ? (
          <div className="text-[10px] text-ops-400">
            <span className="font-mono text-[#3ec7ff]">WAIT {osmElapsedSeconds}s</span> · LIVE OpenStreetMap lookup...
          </div>
        ) : osmFacility ? (
          <div className="flex items-start justify-between gap-3">
            <span className="min-w-0">
              <span className="block truncate text-[11px] text-white">
                {osmFacility.name}
              </span>
              <span className="block text-[9px] text-ops-400">
                {osmFacility.category || "Industrial Facility"} · OpenStreetMap
              </span>
            </span>

            <span className="shrink-0 font-mono text-[11px] text-white">
              {Number(osmFacility.distance_km).toFixed(1)} km
            </span>
          </div>
        ) : (
          <div className="text-[10px] text-ops-400">
            {osmStatus && osmStatus.available === false
              ? "OpenStreetMap lookup unavailable right now."
              : `No industrial OSM feature found within ${osmStatus?.radius_km || 3} km.`}
          </div>
        )}
      </div>

      <div className="mb-3 border border-[#5b4b2b]/70 bg-[#1a160d]/40 p-2">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-[10px] font-semibold tracking-[0.12em] text-[#e8ce7a]">CRITICAL CONTEXT</span>
          <span className="text-[9px] text-ops-500">OSM</span>
        </div>
        {osmLoading ? (
          <div className="text-[10px] text-ops-400"><span className="font-mono text-[#e8ce7a]">WAIT {osmElapsedSeconds}s</span> · checking military / nuclear / power context...</div>
        ) : criticalContext ? (
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[11px] font-medium text-white">{criticalContext.name || criticalContext.display_name || criticalContext.category}</div>
              <div className="mt-0.5 text-[9px] text-ops-400">{criticalContext.category} · OpenStreetMap</div>
            </div>
            <div className="shrink-0 font-mono text-[11px] text-white">{Number(criticalContext.distance_km).toFixed(1)} km</div>
          </div>
        ) : (
          <div className="text-[10px] text-ops-400">{osmStatus && osmStatus.available === false
            ? "OpenStreetMap lookup unavailable right now."
            : `No military / nuclear / power OSM context found within ${osmStatus?.radius_km || 3} km.`}</div>
        )}
      </div>

      <div className="space-y-1">
        {places.length ? places.map((place) => (
          <div key={place.id} className="flex items-start justify-between gap-2 text-[11px]">
            <span className="min-w-0">
              <span className="block text-ops-300">{place.category}</span>
              <span className="block truncate text-[10px] text-ops-400">{place.name}</span>
            </span>
            <span className="shrink-0 font-mono text-white">{place.distance_km.toFixed(1)} km</span>
          </div>
        )) : <div className="text-[10px] text-ops-400">No live GIS context attached to this FIRMS observation.</div>}
      </div>
      <div className="mt-2 text-[9px] text-ops-400">
        OpenStreetMap facility enrichment is separate from hotspot
        classification and risk scoring.
      </div>
    </div>
  );
}
