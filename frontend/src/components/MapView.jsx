import { useEffect, useState } from "react";
import L from "leaflet";
import {
  Circle,
  MapContainer,
  Marker,
  Popup,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { gisIcon, hotspotIcon } from "./HotspotMarker";
import { dayNightLabel, formatAcqDate, formatAcqTime } from "../utils/pipeline";

const INDIA_CENTER = [22.9, 79.2];
const INDIA_ZOOM = 5;

function FlyToSelected({ selected, resetToken }) {
  const map = useMap();

  useEffect(() => {
    if (!selected && resetToken > 0) {
      map.flyTo(INDIA_CENTER, INDIA_ZOOM, { duration: 0.45 });
    }
  }, [map, resetToken, selected]);

  return null;
}


function FitSelectedContext({ selected, osmFacility, criticalContext }) {
  const map = useMap();

  useEffect(() => {
    if (!selected) return;
    const points = [[Number(selected.latitude), Number(selected.longitude)]];
    for (const item of [osmFacility, criticalContext]) {
      const lat = Number(item?.latitude);
      const lon = Number(item?.longitude);
      if (Number.isFinite(lat) && Number.isFinite(lon)) points.push([lat, lon]);
    }
    if (points.length === 1) {
      map.flyTo(points[0], 15.5, { duration: 0.45 });
      return;
    }
    const bounds = L.latLngBounds(points);
    map.fitBounds(bounds, { padding: [48, 48], maxZoom: 15, animate: true, duration: 0.45 });
  }, [map, selected?.id, selected?.latitude, selected?.longitude, osmFacility?.latitude, osmFacility?.longitude, criticalContext?.latitude, criticalContext?.longitude]);

  return null;
}

function InvalidateSize({ token }) {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => map.invalidateSize(), 120);
    const onResize = () => map.invalidateSize();
    window.addEventListener("resize", onResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", onResize);
    };
  }, [map, token]);
  return null;
}

function FitToDataset({ records, selected, datasetToken }) {
  const map = useMap();

  useEffect(() => {
    if (selected || !records?.length) return;
    const valid = records
      .map((record) => [Number(record.hotspot.latitude), Number(record.hotspot.longitude)])
      .filter(([lat, lon]) => Number.isFinite(lat) && Number.isFinite(lon));
    if (!valid.length) return;
    if (valid.length === 1) {
      map.setView(valid[0], 8, { animate: true });
      return;
    }
    const bounds = valid.reduce(
      (acc, point) => acc.extend(point),
      // eslint-disable-next-line no-undef
      L.latLngBounds(valid)
    );
    map.fitBounds(bounds, { padding: [60, 60], maxZoom: 8, animate: true });
  }, [map, datasetToken]);

  return null;
}

function ZoomSync({ onZoom }) {
  const map = useMapEvents({
    zoomend: () => onZoom(map.getZoom()),
  });
  useEffect(() => {
    onZoom(map.getZoom());
  }, [map, onZoom]);
  return null;
}

export default function MapView({
  records,
  selectedId,
  selectedHotspot,
  nearby,
  osmFacility,
  criticalContext,
  osmStatus,
  baseLayer,
  onSelect,
  onViewIntelligence,
  resetToken = 0,
  layoutToken = 0,
  datasetToken = 0,
}) {
  const [zoom, setZoom] = useState(INDIA_ZOOM);
  const selected = selectedHotspot || records.find((r) => r.hotspot.id === selectedId)?.hotspot;
  return (
    <div className="absolute inset-0 z-0">
      <MapContainer
        center={INDIA_CENTER}
        zoom={INDIA_ZOOM}
        minZoom={4}
        maxZoom={18}
        zoomControl
        attributionControl
        className="h-full w-full"
      >
        <InvalidateSize token={layoutToken} />
        <FitToDataset records={records} selected={selected} datasetToken={datasetToken} />
        <ZoomSync onZoom={setZoom} />
        <FlyToSelected selected={selected} resetToken={resetToken} />
        <FitSelectedContext selected={selected} osmFacility={osmFacility} criticalContext={criticalContext} />

        {baseLayer === "street" && (
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        )}
        {baseLayer === "satellite" && (
          <TileLayer
            attribution="Tiles &copy; Esri"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          />
        )}
        {baseLayer === "hybrid" && (
          <>
            <TileLayer
              attribution="Tiles &copy; Esri"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
              attribution=""
            />
          </>
        )}
{selected && (
          <Circle
            center={[selected.latitude, selected.longitude]}
            radius={Math.max(400, (selected.scan || 1) * 700)}
            pathOptions={{ color: "#3ec7ff", weight: 1, fillColor: "#3ec7ff", fillOpacity: 0.08 }}
          />
        )}

        {selected &&
          nearby.map((place) => (
            <Polyline
              key={`line-${place.id}`}
              positions={[
                [selected.latitude, selected.longitude],
                [place.latitude, place.longitude],
              ]}
              pathOptions={{ color: "#3ec7ff", weight: 1, opacity: 0.45, dashArray: "4 6" }}
            />
          ))}

        {selected && osmFacility && Number.isFinite(Number(osmFacility.latitude)) && Number.isFinite(Number(osmFacility.longitude)) && (
          <Polyline
            key="line-nearest-industry"
            positions={[
              [selected.latitude, selected.longitude],
              [Number(osmFacility.latitude), Number(osmFacility.longitude)],
            ]}
            pathOptions={{ color: "#ff8a3d", weight: 2, opacity: 0.7, dashArray: "5 5" }}
          />
        )}

        {selected && criticalContext && Number.isFinite(Number(criticalContext.latitude)) && Number.isFinite(Number(criticalContext.longitude)) && (
          <Polyline
            key="line-critical-context"
            positions={[
              [selected.latitude, selected.longitude],
              [Number(criticalContext.latitude), Number(criticalContext.longitude)],
            ]}
            pathOptions={{ color: "#e8ce7a", weight: 2, opacity: 0.75, dashArray: "3 5" }}
          />
        )}

        {/* Nearby context is kept in the intelligence panel to avoid duplicate/unstable map markers. */}


        {records.map((record) => {
          const { hotspot, comparison, risk, severity, classification } = record;
          const isSelected = hotspot.id === selectedId;
          const sign = (comparison?.frp_deviation ?? 0) >= 0 ? "+" : "";
          return (
            <Marker
              key={hotspot.id}
              position={[hotspot.latitude, hotspot.longitude]}
              icon={hotspotIcon(severity, isSelected)}
              zIndexOffset={isSelected ? 1000 : 0}
              eventHandlers={{
                click: () => onSelect(hotspot.id),
              }}
            >
              <Tooltip direction="top" offset={[0, -8]} opacity={0.95}>
                <span className="font-mono text-[10px]">
                  {hotspot.id} Â· {classification?.label || "UNCLASSIFIED"} Â· FRP {hotspot.frp}
                </span>
              </Tooltip>
              <Popup>
                <div className="p-2.5">
                  <div className="text-[9px] tracking-[0.14em] text-[#3ec7ff]">HOTSPOT #{hotspot.id}</div>
                  <div className="mt-1 grid grid-cols-[72px_1fr] gap-y-0.5 text-[11px]">
                    <span className="text-ops-400">CLASS</span>
                    <span className="font-semibold text-white">{(classification?.label || "UNCLASSIFIED").toUpperCase()}</span>
                    <span className="text-ops-400">FRP</span>
                    <span className="font-mono">{hotspot.frp} MW</span>
                    <span className="text-ops-400">CONFIDENCE</span>
                    <span className="font-mono">{typeof hotspot.confidence === "string" ? hotspot.confidence.toUpperCase() : `${hotspot.confidence}%`}</span>
                    <span className="text-ops-400">DETECTED</span>
                    <span className="font-mono">
                      {formatAcqDate(hotspot.acq_date)} {formatAcqTime(hotspot.acq_time)}
                    </span>
                    <span className="text-ops-400">DAY/NIGHT</span>
                    <span>{dayNightLabel(hotspot.daynight)}</span>
                    {record.fireDetection && (
                      <>
                        <span className="text-ops-400">FIRE EVIDENCE</span>
                        <span className="font-mono font-semibold text-white">
                          {record.fireDetection.fire_confidence}% Â· {record.fireDetection.status}
                        </span>
                      </>
                    )}
                    {isSelected && osmFacility && (
                      <>
                        <span className="text-ops-400">NEAREST INDUSTRY</span>
                        <span className="font-semibold text-white">
                          {osmFacility.name}
                        </span>
                        <span className="text-ops-400">DISTANCE</span>
                        <span className="font-mono text-white">
                          {Number(osmFacility.distance_km).toFixed(1)} km
                        </span>
                      </>
                    )}
                    {comparison && (
                      <>
                        <span className="text-ops-400">BASELINE</span>
                        <span className="font-mono">{comparison.normal_frp.toFixed(1)} MW</span>
                        <span className="text-ops-400">DEVIATION</span>
                        <span className="font-mono text-[#ff8a8a]">
                          {sign}
                          {comparison.frp_deviation.toFixed(1)}%
                        </span>
                        <span className="text-ops-400">RISK</span>
                        <span className="font-semibold text-[#ff6b6b]">{risk?.level}</span>
                      </>
                    )}
                  </div>
                  <button
                    type="button"
                    className="mt-2 w-full border border-[#3ec7ff]/50 bg-[#3ec7ff]/10 py-1 text-[10px] tracking-[0.12em] text-[#3ec7ff]"
                    onClick={() => onViewIntelligence(hotspot.id)}
                  >
                    VIEW INTELLIGENCE
                  </button>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {selected && osmFacility && Number.isFinite(Number(osmFacility.latitude)) && Number.isFinite(Number(osmFacility.longitude)) && (
          <Marker
            key={`nearest-industry-${osmFacility.osm_type || "x"}-${osmFacility.osm_id || osmFacility.name}`}
            position={[Number(osmFacility.latitude), Number(osmFacility.longitude)]}
            icon={gisIcon("Industrial Facility")}
            zIndexOffset={500}
          >
            <Tooltip direction="right" offset={[6, 0]}>
              <span className="text-[10px]">
                Nearest Industry: {osmFacility.name} ({Number(osmFacility.distance_km).toFixed(2)} km)
              </span>
            </Tooltip>
          </Marker>
        )}

        {selected && criticalContext && Number.isFinite(Number(criticalContext.latitude)) && Number.isFinite(Number(criticalContext.longitude)) && (
          <Marker
            key={`critical-${criticalContext.osm_type || "x"}-${criticalContext.osm_id || criticalContext.name || criticalContext.category}`}
            position={[Number(criticalContext.latitude), Number(criticalContext.longitude)]}
            icon={gisIcon(criticalContext.category || "Critical Area")}
            zIndexOffset={520}
          >
            <Tooltip direction="right" offset={[6, 0]}>
              <span className="text-[10px]">
                Critical Area: {criticalContext.name || criticalContext.category} ({Number(criticalContext.distance_km).toFixed(2)} km)
              </span>
            </Tooltip>
          </Marker>
        )}

        {selected && nearby.map((place) => (
          <Marker
            key={place.id}
            position={[place.latitude, place.longitude]}
            icon={gisIcon(place.category)}
            zIndexOffset={200}
          >
            <Tooltip direction="right" offset={[6, 0]}>
              <span className="text-[10px]">
                {place.category}: {place.name} ({place.distance_km} km)
              </span>
            </Tooltip>
          </Marker>
        ))}

        {/* Explicit nearest-industry and critical-context markers are rendered separately so they
            cannot disappear just because the general nearby list is capped. */}
      </MapContainer>
    </div>
  );
}


