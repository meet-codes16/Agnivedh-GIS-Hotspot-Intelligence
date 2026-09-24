const ITEMS = [
  { label: "Nominal", className: "hotspot-dot nominal" },
  { label: "Watch", className: "hotspot-dot watch" },
  { label: "High", className: "hotspot-dot high" },
  { label: "Critical", className: "hotspot-dot critical" },
];

export default function MapLegend() {
  return (
    <div className="pointer-events-auto panel-glass px-2.5 py-2 text-[10px]">
      <div className="mb-1.5 tracking-[0.14em] text-[#3ec7ff]">LEGEND</div>
      <div className="space-y-1.5">
        {ITEMS.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-ops-300">
            <span className={`${item.className} !w-2.5 !h-2.5`} />
            {item.label}
          </div>
        ))}
        <div className="flex items-center gap-2 text-ops-300">
          <span className="gis-pin !w-2 !h-2 bg-[#ff8a3d]" />
          GIS place
        </div>
      </div>
    </div>
  );
}
