export const VALIDATED_INCIDENTS_2024 = {
  "F24-1493001": { name: "KUNDAM-3 / Jabalpur", source: "FSI LFF" },
  "F24-1493002": { name: "KUNDAM-3 / Jabalpur", source: "FSI LFF" },
  "F24-1584147": { name: "DHAMI-1 / Shimla", source: "FSI LFF" },
  "F24-1584148": { name: "DHAMI-1 / Shimla", source: "FSI LFF" },
  "F24-1597174": { name: "MASHOBRA-12 / Shimla", source: "FSI LFF" },
};

export function getValidatedIncident(id) {
  return VALIDATED_INCIDENTS_2024[id] || null;
}
