// Realistic placeholder data for the BI Engine dashboard.

// --- Survival analysis: retention probability (%) over days for cohorts ---
// Each cohort declines from 100% at different hazard rates.
function survivalCurve(halfLifeDays: number, floor: number) {
  const days = [0, 15, 30, 45, 60, 75, 90, 120, 150, 180];
  return days.map((d) => {
    const p = 100 * Math.exp(-Math.LN2 * (d / halfLifeDays));
    return { day: d, value: +Math.max(floor, p).toFixed(1) };
  });
}

export const survivalCohorts = [
  { key: "enterprise", label: "Enterprise", color: "#1d4ed8", data: survivalCurve(210, 61) },
  { key: "midmarket", label: "Mid-Market", color: "#10b981", data: survivalCurve(120, 38) },
  { key: "smb", label: "SMB (Self-serve)", color: "#f59e0b", data: survivalCurve(64, 14) },
  { key: "trial", label: "Trial Conversions", color: "#ef4444", data: survivalCurve(38, 4) },
];

// Merge into a single recharts-friendly series keyed by day
export const survivalMerged = survivalCohorts[0].data.map((_, i) => {
  const row: Record<string, number> = { day: survivalCohorts[0].data[i].day };
  for (const c of survivalCohorts) row[c.key] = c.data[i].value;
  return row;
});

// --- Uplift modeling matrix (persuadability vs. baseline conversion) ---
export type Quadrant = "Persuadable" | "Sure-Thing" | "Lost-Cause" | "Do-Not-Disturb";

export interface UpliftPoint {
  x: number; // baseline propensity to retain (0-100)
  y: number; // treatment uplift (-40 to +40)
  size: number; // cohort MRR weight
  quadrant: Quadrant;
  name: string;
}

export const upliftPoints: UpliftPoint[] = [
  { x: 34, y: 27, size: 520, quadrant: "Persuadable", name: "SMB · onboarding drop-off" },
  { x: 41, y: 19, size: 340, quadrant: "Persuadable", name: "Mid-market · low seat usage" },
  { x: 28, y: 33, size: 610, quadrant: "Persuadable", name: "Self-serve · no integrations" },
  { x: 46, y: 12, size: 210, quadrant: "Persuadable", name: "Trial · single-user" },
  { x: 78, y: 22, size: 180, quadrant: "Sure-Thing", name: "Enterprise · power users" },
  { x: 84, y: 9, size: 260, quadrant: "Sure-Thing", name: "Annual · multi-team" },
  { x: 72, y: 16, size: 150, quadrant: "Sure-Thing", name: "Design partners" },
  { x: 22, y: -18, size: 300, quadrant: "Lost-Cause", name: "Churned · payment failed" },
  { x: 31, y: -9, size: 190, quadrant: "Lost-Cause", name: "Sunset plan holdouts" },
  { x: 17, y: -26, size: 240, quadrant: "Lost-Cause", name: "Legacy · unsupported region" },
  { x: 81, y: -14, size: 420, quadrant: "Do-Not-Disturb", name: "Enterprise · exec sponsors" },
  { x: 88, y: -22, size: 380, quadrant: "Do-Not-Disturb", name: "Renewed < 30d ago" },
  { x: 74, y: -11, size: 200, quadrant: "Do-Not-Disturb", name: "High-NPS advocates" },
];

// --- Executive sparkline (NRR trend) ---
export const nrrTrend = [104, 106, 105, 108, 109, 108, 110, 111, 110, 112].map((v, i) => ({
  m: i,
  v,
}));

// --- AI strategy feed ---
export interface Strategy {
  id: string;
  tag: string;
  tagTone: "sig" | "telemetry" | "warning";
  title: string;
  body: string;
  method: string;
  confidence: number;
  payload: string;
  impact: string;
}

export const strategies: Strategy[] = [
  {
    id: "ACT-4471",
    tag: "Statistically Significant",
    tagTone: "sig",
    title: "Workflow Builder adoption cuts SMB churn 22%",
    body:
      "Causal ML (double-ML uplift) indicates the 'Workflow Builder' feature reduces SMB churn by 22% (ATE +0.22, p < 0.01). Recommendation: trigger mandatory in-app guide for the 512-account Persuadable cohort.",
    method: "Double-ML · Uplift",
    confidence: 96,
    payload:
      '{ "action":"trigger_in_app_guide", "cohort":"smb_persuadable", "guide_id":"wf_builder_v3", "accounts":512 }',
    impact: "+$8,200 MRR protected",
  },
  {
    id: "ACT-4472",
    tag: "Gathering Telemetry",
    tagTone: "telemetry",
    title: "Involuntary churn spike from failed renewals",
    body:
      "Hazard function for the 'Payment Failed' segment is rising (λ +1.8σ over 14d). Dunning retries are under-configured. Recommendation: enable smart-retry + pre-dunning email 3 days pre-charge.",
    method: "Survival · Cox PH",
    confidence: 71,
    payload:
      '{ "action":"enable_smart_dunning", "segment":"payment_failed", "retry_window_days":7, "pre_notice":true }',
    impact: "$4,100 MRR at risk",
  },
  {
    id: "ACT-4473",
    tag: "Statistically Significant",
    tagTone: "sig",
    title: "Do-Not-Disturb guardrail on renewed accounts",
    body:
      "Uplift is negative (ATE −0.14) for recently-renewed enterprise sponsors. Suppress the win-back campaign for 380 accounts to avoid annoyance-driven attrition.",
    method: "Uplift · Guardrail",
    confidence: 89,
    payload:
      '{ "action":"suppress_campaign", "campaign":"winback_q3", "cohort":"enterprise_dnd", "accounts":380 }',
    impact: "Prevents ~$2,300 MRR erosion",
  },
  {
    id: "ACT-4474",
    tag: "Early Warning",
    tagTone: "warning",
    title: "Seat-utilization decay in mid-market",
    body:
      "Feature-impact model flags a 31% drop in active-seat ratio across 42 mid-market accounts within 21 days — a leading indicator of downgrade. Recommendation: route to CS with expansion playbook.",
    method: "Feature Impact",
    confidence: 64,
    payload:
      '{ "action":"route_to_cs", "playbook":"seat_reactivation", "segment":"midmarket_decay", "accounts":42 }',
    impact: "$3,900 MRR expansion",
  },
];
