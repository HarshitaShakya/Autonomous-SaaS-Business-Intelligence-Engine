import { useLayoutEffect, useRef, useState } from "react";
import {
  survivalCohorts,
  survivalMerged,
  upliftPoints,
  nrrTrend,
  type UpliftPoint,
} from "./data";

/* Measure container width so SVG marks stay crisp (no viewBox distortion). */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      setW(entries[0].contentRect.width);
    });
    ro.observe(el);
    setW(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

/* ---------------- Sparkline ---------------- */
export function Sparkline() {
  const [ref, w] = useWidth();
  const h = 44;
  const vals = nrrTrend.map((d) => d.v);
  const min = Math.min(...vals) - 1;
  const max = Math.max(...vals) + 1;
  const x = (i: number) => (i / (vals.length - 1)) * w;
  const y = (v: number) => h - 3 - ((v - min) / (max - min)) * (h - 6);
  const line = vals.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `${line} ${w},${h} 0,${h}`;

  return (
    <div ref={ref} className="w-full" style={{ height: h }}>
      {w > 0 && (
        <svg width={w} height={h} className="overflow-visible">
          <defs>
            <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.18} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>
          <polygon points={area} fill="url(#spark)" />
          <polyline
            points={line}
            fill="none"
            stroke="#10b981"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx={x(vals.length - 1)} cy={y(vals[vals.length - 1])} r={3} fill="#10b981" />
        </svg>
      )}
    </div>
  );
}

/* ---------------- Survival analysis line chart ---------------- */
export function SurvivalChart() {
  const [ref, w] = useWidth();
  const h = 288;
  const m = { t: 12, r: 16, b: 28, l: 40 };
  const iw = Math.max(0, w - m.l - m.r);
  const ih = h - m.t - m.b;
  const days = survivalMerged.map((d) => d.day);
  const maxDay = days[days.length - 1];
  const [hover, setHover] = useState<number | null>(null);

  const px = (day: number) => m.l + (day / maxDay) * iw;
  const py = (val: number) => m.t + (1 - val / 100) * ih;

  const yTicks = [0, 25, 50, 75, 100];

  function onMove(e: React.MouseEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = e.clientX - rect.left - m.l;
    const ratio = Math.max(0, Math.min(1, rel / iw));
    const day = ratio * maxDay;
    // snap to nearest sampled day
    let nearest = 0;
    let best = Infinity;
    days.forEach((d, i) => {
      const dist = Math.abs(d - day);
      if (dist < best) {
        best = dist;
        nearest = i;
      }
    });
    setHover(nearest);
  }

  const hoverRow = hover != null ? survivalMerged[hover] : null;

  return (
    <div ref={ref} className="relative w-full" style={{ height: h }}>
      {w > 0 && (
        <svg width={w} height={h}>
          {/* gridlines + y labels */}
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={m.l} x2={m.l + iw} y1={py(t)} y2={py(t)} stroke="#eef2f7" />
              <text x={m.l - 8} y={py(t)} dy="0.32em" textAnchor="end" className="fill-slate-400 text-[11px]">
                {t}%
              </text>
            </g>
          ))}
          {/* x labels */}
          {days.map((d) => (
            <text key={d} x={px(d)} y={h - 8} textAnchor="middle" className="fill-slate-400 text-[11px]">
              {d}d
            </text>
          ))}
          {/* baseline */}
          <line x1={m.l} x2={m.l + iw} y1={py(0)} y2={py(0)} stroke="#e2e8f0" />

          {/* cohort lines */}
          {survivalCohorts.map((c) => {
            const pts = survivalMerged.map((row) => `${px(row.day)},${py(row[c.key])}`).join(" ");
            return (
              <polyline
                key={c.key}
                points={pts}
                fill="none"
                stroke={c.color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            );
          })}

          {/* hover crosshair + dots */}
          {hoverRow && (
            <>
              <line
                x1={px(hoverRow.day)}
                x2={px(hoverRow.day)}
                y1={m.t}
                y2={m.t + ih}
                stroke="#cbd5e1"
                strokeDasharray="4 4"
              />
              {survivalCohorts.map((c) => (
                <circle
                  key={c.key}
                  cx={px(hoverRow.day)}
                  cy={py(hoverRow[c.key])}
                  r={4}
                  fill={c.color}
                  stroke="#fff"
                  strokeWidth={2}
                />
              ))}
            </>
          )}

          <rect
            x={m.l}
            y={m.t}
            width={iw}
            height={ih}
            fill="transparent"
            onMouseMove={onMove}
            onMouseLeave={() => setHover(null)}
          />
        </svg>
      )}

      {/* tooltip */}
      {hoverRow && w > 0 && (
        <div
          className="pointer-events-none absolute z-10 w-52 rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-lg"
          style={{
            left: Math.min(px(hoverRow.day) + 12, w - 210),
            top: m.t,
          }}
        >
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Day {hoverRow.day}
          </div>
          <div className="space-y-1">
            {survivalCohorts.map((c) => (
              <div key={c.key} className="flex items-center gap-2 text-xs">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: c.color }} />
                <span className="truncate text-slate-600">{c.label}</span>
                <span className="tnum ml-auto font-semibold text-slate-900">{hoverRow[c.key]}%</span>
              </div>
            ))}
          </div>
          <div className="tnum mt-1.5 border-t border-slate-100 pt-1.5 text-[11px] text-slate-400">
            Cancel prob. {(100 - hoverRow[survivalCohorts[3].key]).toFixed(1)}% (trial)
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Uplift modeling matrix (scatter) ---------------- */
const quadrantColor: Record<string, string> = {
  Persuadable: "#1d4ed8",
  "Sure-Thing": "#10b981",
  "Lost-Cause": "#ef4444",
  "Do-Not-Disturb": "#94a3b8",
};

export function UpliftMatrix() {
  const [ref, w] = useWidth();
  const h = 288;
  const m = { t: 12, r: 16, b: 28, l: 40 };
  const iw = Math.max(0, w - m.l - m.r);
  const ih = h - m.t - m.b;
  const [hover, setHover] = useState<number | null>(null);

  const px = (x: number) => m.l + (x / 100) * iw;
  const py = (y: number) => m.t + (1 - (y + 40) / 80) * ih; // y range -40..40
  const r = (size: number) => 5 + (size / 620) * 13;

  const midX = px(50);
  const midY = py(0);

  return (
    <div ref={ref} className="relative w-full" style={{ height: h }}>
      {w > 0 && (
        <svg width={w} height={h}>
          {/* persuadable quadrant highlight: x<50, y>0 */}
          <rect x={m.l} y={m.t} width={midX - m.l} height={midY - m.t} fill="#1d4ed8" fillOpacity={0.06} />
          {/* grid frame */}
          <rect x={m.l} y={m.t} width={iw} height={ih} fill="none" stroke="#eef2f7" />
          {/* quadrant dividers */}
          <line x1={midX} x2={midX} y1={m.t} y2={m.t + ih} stroke="#cbd5e1" strokeWidth={1.5} />
          <line x1={m.l} x2={m.l + iw} y1={midY} y2={midY} stroke="#cbd5e1" strokeWidth={1.5} />

          {/* axis labels */}
          {[0, 50, 100].map((t) => (
            <text key={t} x={px(t)} y={h - 8} textAnchor="middle" className="fill-slate-400 text-[11px]">
              {t}%
            </text>
          ))}
          {[-40, 0, 40].map((t) => (
            <text key={t} x={m.l - 8} y={py(t)} dy="0.32em" textAnchor="end" className="fill-slate-400 text-[11px]">
              {t > 0 ? `+${t}` : t}
            </text>
          ))}

          {/* quadrant corner labels */}
          <text x={m.l + 6} y={m.t + 14} className="fill-blue-600 text-[10px] font-semibold uppercase tracking-wide">
            Persuadable
          </text>
          <text x={m.l + iw - 6} y={m.t + 14} textAnchor="end" className="fill-emerald-600 text-[10px] font-semibold uppercase tracking-wide">
            Sure-Thing
          </text>
          <text x={m.l + 6} y={m.t + ih - 6} className="fill-red-500 text-[10px] font-semibold uppercase tracking-wide">
            Lost-Cause
          </text>
          <text x={m.l + iw - 6} y={m.t + ih - 6} textAnchor="end" className="fill-slate-400 text-[10px] font-semibold uppercase tracking-wide">
            Do-Not-Disturb
          </text>

          {/* points */}
          {upliftPoints.map((p, i) => (
            <circle
              key={i}
              cx={px(p.x)}
              cy={py(p.y)}
              r={r(p.size)}
              fill={quadrantColor[p.quadrant]}
              fillOpacity={p.quadrant === "Persuadable" ? 0.9 : 0.55}
              stroke="#fff"
              strokeWidth={1.5}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              className="cursor-pointer transition-[fill-opacity]"
            />
          ))}
        </svg>
      )}

      {hover != null && w > 0 && <UpliftTip p={upliftPoints[hover]} x={px(upliftPoints[hover].x)} y={py(upliftPoints[hover].y)} w={w} />}
    </div>
  );
}

function UpliftTip({ p, x, y, w }: { p: UpliftPoint; x: number; y: number; w: number }) {
  return (
    <div
      className="pointer-events-none absolute z-10 w-48 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg"
      style={{ left: Math.min(x + 12, w - 200), top: Math.max(0, y - 20) }}
    >
      <div className="text-xs font-semibold text-slate-900">{p.name}</div>
      <div className="mt-1 flex items-center gap-2">
        <span className="inline-block h-2 w-2 rounded-full" style={{ background: quadrantColor[p.quadrant] }} />
        <span className="text-[11px] text-slate-500">{p.quadrant}</span>
      </div>
      <div className="tnum mt-1 text-[11px] text-slate-500">
        Uplift {p.y > 0 ? "+" : ""}
        {p.y}% · Retain {p.x}%
      </div>
    </div>
  );
}
