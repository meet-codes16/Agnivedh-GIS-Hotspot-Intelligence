export default function ForecastPanel({
  records = [],
  comparison,
  baseline,
  hotspot,
}) {
  const valid = records.filter(
    (r) =>
      r?.hotspot &&
      Number.isFinite(Number(r.hotspot.acq_time)) &&
      Number.isFinite(Number(r.hotspot.frp))
  );

  const selectedHour = Number(
    String(hotspot?.acq_time ?? "0000").padStart(4, "0").slice(0, 2)
  );

  /*
   * Three-hour window:
   * previous hour -> selected/current hour -> next hour
   */
  const windowHours = new Set(
    [selectedHour - 1, selectedHour, selectedHour + 1].filter(
      (hour) => hour >= 0 && hour <= 23
    )
  );

  /*
   * CURRENT 2024 ACTIVITY
   *
   * Outside the selected 3-hour window we intentionally show 0.
   * Inside the window we use the real loaded 2024 FIRMS observations.
   */
  const hourlyCurrent = Array.from({ length: 24 }, (_, hour) => {
    if (!windowHours.has(hour)) {
      return {
        hour,
        current: 0,
        prediction: false,
        comparison: "outside",
      };
    }

    const rows = valid.filter((r) => {
      const t = String(r.hotspot.acq_time).padStart(4, "0");
      return Number(t.slice(0, 2)) === hour;
    });

    if (!rows.length) {
      return {
        hour,
        current: 0,
        prediction: false,
        comparison: "missing",
      };
    }

    const values = rows
      .map((r) => Number(r.hotspot.frp))
      .filter(Number.isFinite);

    const current = values.length
      ? values.reduce((a, b) => a + b, 0) / values.length
      : 0;

    return {
      hour,
      current,
      prediction: true,
      comparison: "current",
    };
  });

  /*
   * LOCATION-SPECIFIC HISTORICAL BASELINE
   *
   * Actual 2022-2023 hourly historical profile.
   * Missing historical hours remain 0 only for display.
   * Backend baseline calculation is untouched.
   */
  const historicalHourly = baseline?.hourly_frp || {};

  const hourlyBaseline = Array.from({ length: 24 }, (_, hour) => {
    if (!windowHours.has(hour)) {
      return {
        hour,
        baseline: 0,
        hasBaseline: false,
      };
    }

    const raw = historicalHourly[String(hour)];

    const value =
      raw === null || raw === undefined || raw === ""
        ? null
        : Number(raw);

    return {
      hour,
      baseline: Number.isFinite(value) ? value : 0,
      hasBaseline: Number.isFinite(value),
    };
  });

  /*
   * Current color is determined ONLY by comparison with baseline:
   *
   * current > baseline -> RED
   * current < baseline -> YELLOW
   * current === baseline -> YELLOW/neutral
   */
  const getCurrentColor = (hour) => {
    const currentPoint = hourlyCurrent.find((p) => p.hour === hour);
    const baselinePoint = hourlyBaseline.find((p) => p.hour === hour);

    if (
      !currentPoint ||
      !baselinePoint ||
      !windowHours.has(hour) ||
      !baselinePoint.hasBaseline ||
      !Number.isFinite(currentPoint.current)
    ) {
      return "#111820";
    }

    if (currentPoint.current > baselinePoint.baseline) {
      return "#ff6b6b";
    }

    if (currentPoint.current < baselinePoint.baseline) {
      return "#f0c14b";
    }

    return "#f0c14b";
  };

  const W = 560;
  const H = 175;

  const left = 32;
  const right = 10;
  const top = 10;
  const bottom = 25;

  const gw = W - left - right;
  const gh = H - top - bottom;

  /*
   * Scale the graph around the selected 3-hour window.
   * Outside hours are 0 and therefore do not distort the useful range.
   */
  const windowValues = [
    ...hourlyBaseline
      .filter((p) => windowHours.has(p.hour))
      .map((p) => p.baseline),
    ...hourlyCurrent
      .filter((p) => windowHours.has(p.hour))
      .map((p) => p.current),
  ].filter(Number.isFinite);

  const max = Math.max(...windowValues, 1) * 1.12;

  const windowStart = Math.max(0, selectedHour - 1);
const windowEnd = Math.min(23, selectedHour + 1);

const X = (hour) => {
  if (windowEnd === windowStart) return left;

  return (
    left +
    ((hour - windowStart) / (windowEnd - windowStart)) * gw
  );
};

  const Y = (value) =>
    top + gh - (value / max) * gh;

  /*
   * Baseline path.
   *
   * We draw only the actual three-hour baseline values.
   * Outside the selected window the graph remains at zero.
   */
  const baselinePoints = hourlyBaseline.filter((p) => windowHours.has(p.hour)).map((p) => ({
    hour: p.hour,
    value: p.baseline,
  }));

  const makePath = (points) => {
    if (points.length < 2) return "";

    let d = `M ${X(points[0].hour)} ${Y(points[0].value)}`;

    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1];
      const b = points[i];

      const mx = (X(a.hour) + X(b.hour)) / 2;

      d +=
        ` C ${mx} ${Y(a.value)},` +
        ` ${mx} ${Y(b.value)},` +
        ` ${X(b.hour)} ${Y(b.value)}`;
    }

    return d;
  };

  const bluePath = makePath(baselinePoints);

  /*
   * Selected three-hour current path.
   */
  const currentPoints = hourlyCurrent.filter((p) =>
    windowHours.has(p.hour)
  );

  const currentPathSegments = [];

  for (let i = 1; i < currentPoints.length; i++) {
    const a = currentPoints[i - 1];
    const b = currentPoints[i];

    const x1 = X(a.hour);
    const y1 = Y(a.current);
    const x2 = X(b.hour);
    const y2 = Y(b.current);

    const mx = (x1 + x2) / 2;

    currentPathSegments.push({
      hour: b.hour,
      d:
        `M ${x1} ${y1}` +
        ` C ${mx} ${y1},` +
        ` ${mx} ${y2},` +
        ` ${x2} ${y2}`,
      color: getCurrentColor(b.hour),
    });
  }

  const baselineRegion =
    baseline?.region || "HISTORICAL PROFILE";

  const windowLabel = [selectedHour - 1, selectedHour, selectedHour + 1]
    .filter((hour) => hour >= 0 && hour <= 23)
    .map((hour) => `${String(hour).padStart(2, "0")}:00`)
    .join(" – ");

  return (
    <div className="h-full overflow-hidden border border-[#2a3c58] bg-[#101b29]/90 p-3">

      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] font-semibold tracking-[0.16em] text-[#3ec7ff]">
            HISTORICAL ACTIVITY
          </div>

          <div className="mt-1 text-[10px] text-ops-400">
            2022–2023 baseline vs current 2024 activity
          </div>

          <div className="mt-1 text-[8px] font-mono text-ops-500">
            {baselineRegion}
          </div>

          <div className="mt-1 text-[8px] font-mono text-[#3ec7ff]">
            3-HOUR WINDOW · {windowLabel}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 text-[8px] font-mono">
          <span className="flex items-center gap-1 text-ops-400">
            <span className="h-[2px] w-5 bg-[#3ec7ff]" />
            BASELINE
          </span>

          <span className="flex items-center gap-1 text-ops-400">
            <span className="h-[2px] w-5 bg-[#f0c14b]" />
            BELOW
          </span>

          <span className="flex items-center gap-1 text-ops-400">
            <span className="h-[2px] w-5 bg-[#ff6b6b]" />
            ABOVE
          </span>
        </div>
      </div>

      <div className="mt-2 w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-[165px] w-full"
          preserveAspectRatio="none"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((r) => {
            const yy = top + gh - r * gh;

            return (
              <g key={r}>
                <line
                  x1={left}
                  x2={W - right}
                  y1={yy}
                  y2={yy}
                  stroke="#26384f"
                  strokeWidth="0.7"
                  opacity="0.65"
                />

                <text
                  x="2"
                  y={yy + 3}
                  fill="#64758a"
                  fontSize="8"
                  fontFamily="monospace"
                >
                  {(max * r).toFixed(0)}
                </text>
              </g>
            );
          })}

          {[windowStart, selectedHour, windowEnd].map((hour) => (
            <text
              key={hour}
              x={X(hour)}
              y={H - 6}
              textAnchor="middle"
              fill="#64758a"
              fontSize="8"
              fontFamily="monospace"
            >
              {String(hour).padStart(2, "0")}:00
            </text>
          ))}

          {/* Historical baseline */}
          {bluePath && (
            <path
              d={bluePath}
              fill="none"
              stroke="#3ec7ff"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Current 2024 comparison */}
          {currentPathSegments.map((segment) => (
            <path
              key={`current-line-${segment.hour}`}
              d={segment.d}
              fill="none"
              stroke={segment.color}
              strokeWidth="2.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}

          {/* Baseline points */}
          {hourlyBaseline.map((p) => (
            <circle
              key={`b-${p.hour}`}
              cx={X(p.hour)}
              cy={Y(p.baseline)}
              r={windowHours.has(p.hour) && p.hasBaseline ? 2 : 0}
              fill="#3ec7ff"
            />
          ))}

          {/* Current points */}
          {currentPoints.map((p) => (
            <circle
              key={`c-${p.hour}`}
              cx={X(p.hour)}
              cy={Y(p.current)}
              r="2.2"
              fill={getCurrentColor(p.hour)}
            />
          ))}

          {/* Selected/current hour marker */}
          <line
            x1={X(selectedHour)}
            x2={X(selectedHour)}
            y1={top}
            y2={top + gh}
            stroke="#64758a"
            strokeWidth="0.7"
            strokeDasharray="3 3"
            opacity="0.7"
          />

          <text
            x={X(selectedHour)}
            y={top + 9}
            textAnchor="middle"
            fill="#ffffff"
            fontSize="8"
            fontFamily="monospace"
          >
            CURRENT
          </text>
        </svg>
      </div>

      <div className="flex items-center justify-between border-t border-[#26384f] pt-1.5">

        <div className="text-[8px] font-mono text-ops-500">
          BLUE = HISTORICAL NORMAL
        </div>

        <div className="text-[8px] font-mono text-ops-400">
          RED = ABOVE · YELLOW = BELOW
        </div>

      </div>
    </div>
  );
}
