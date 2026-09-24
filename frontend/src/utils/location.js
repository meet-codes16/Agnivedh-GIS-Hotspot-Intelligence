export async function resolveLocation(latitude, longitude) {
  if (!Number.isFinite(Number(latitude)) || !Number.isFinite(Number(longitude))) {
    return null;
  }

  const lat = Number(latitude);
  const lon = Number(longitude);

  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}&zoom=10&addressdetails=1`,
      {
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) return null;

    const data = await response.json();
    const address = data?.address || {};

    const city =
      address.city ||
      address.town ||
      address.municipality ||
      address.village ||
      address.county ||
      null;

    const state = address.state || null;

    if (!city && !state) return null;

    return {
      city,
      state,
      displayName: [city, state].filter(Boolean).join(", "),
    };
  } catch {
    return null;
  }
}
