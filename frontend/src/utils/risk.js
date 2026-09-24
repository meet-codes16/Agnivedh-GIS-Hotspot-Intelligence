/**
 * Prototype risk scoring. Not scientifically validated.
 */

function band(value) {
  if (value >= 0.7) return "HIGH";
  if (value >= 0.4) return "MODERATE";
  return "LOW";
}

export function riskLevel(score) {
  if (score >= 80) return "CRITICAL";
  if (score >= 60) return "HIGH";
  if (score >= 40) return "MODERATE";
  return "LOW";
}

export function riskEngine(features, classification) {
  const frpAbs = Math.min(Math.abs(features.frp_deviation ?? 0) / 150, 1);
  const persist = features.location_persistence ?? 0;
  const night = features.night_ratio ?? 0;
  const industrial = features.industrial_proximity ?? 0;
  const mine = features.mine_proximity ?? 0;
  const forest = features.forest_proximity ?? 0;
  const conf = (features.confidence ?? 50) / 100;
  const classLabel = classification?.label ?? "Other";

  let classWeight = 0.35;
  if (classLabel === "Industrial" || classLabel === "Mining") classWeight = 0.55;
  if (classLabel === "Gas Flare") classWeight = 0.48;
  if (classLabel === "Wildfire") classWeight = 0.5;
  if (classLabel === "Agricultural Burning") classWeight = 0.32;

  const proximity = Math.max(industrial, mine, forest * 0.7);
  const raw =
    frpAbs * 28 +
    persist * 18 +
    night * 12 +
    proximity * 16 +
    classWeight * 16 +
    conf * 10;

  const score = Math.round(Math.max(8, Math.min(96, raw)));
  const drivers = [
    { name: "FRP deviation", level: band(frpAbs), value: frpAbs },
    { name: "Persistence", level: band(persist), value: persist },
    { name: "Night activity", level: band(night), value: night },
    {
      name:
        industrial >= mine && industrial >= forest
          ? "Industrial proximity"
          : mine >= forest
            ? "Mine proximity"
            : "Forest proximity",
      level: band(proximity),
      value: proximity,
    },
  ].sort((a, b) => b.value - a.value);

  return {
    score,
    level: riskLevel(score),
    drivers,
    prototype: true,
  };
}

export function markerSeverity(hotspot, risk, fireDetection) {
  if (risk?.level === "CRITICAL") return "critical";
  if (risk?.level === "HIGH") return "high";
  if (fireDetection?.status === "LIKELY FIRE") return "high";
  if (risk?.level === "MODERATE") return "watch";
  if (fireDetection?.status === "REVIEW") return "watch";
  if ((hotspot?.frp ?? 0) >= 50) return "high";
  if ((hotspot?.frp ?? 0) >= 25) return "watch";
  return "nominal";
}
