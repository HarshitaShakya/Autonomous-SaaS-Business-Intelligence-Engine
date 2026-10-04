import { useState } from "react";
import { Sparkline, SurvivalChart, UpliftMatrix } from "./charts";
import { strategies, survivalCohorts } from "./data";

/* ---------- Icons (inline, 1.75 stroke) ---------- */
const Ic = ({ d, className = "" }: { d: string; className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d={d} />
  </svg>
);

const icons = {
  command: "M4 5h16M4 12h10M4 19h16",
  churn: "M3 3v18h18M7 15l4-5 3 3 5-7",
  causal: "M12 3v6m0 0-3-3m3 3 3-3M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm12 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM7.5 15.5 11 11m2 0 3.5 4.5",
  feed: "M4 6h16M4 12h16M4 18h10",
  queue: "M9 11l3 3 8-8M4 12l3 3M4 18h11",
  connectors: "M6 3v6M6 15v6M6 9a3 3 0 0 0 0 6M18 3v6m0 6v6m0-6a3 3 0 0 1 0-6M9 12h6",
  shield: "M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3Zm-2.5 8.5 2 2 3.5-4",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35",
  bell: "M6 8a6 6 0 1 1 12 0c0 7 3 7 3 7H3s3 0 3-7M10 21h4",
  chevron: "M9 6l6 6-6 6",
  check: "M5 13l4 4L19 7",
  x: "M6 6l12 12M18 6L6 18",
  cite: "M9 7h6M9 11h6M9 15h3M6 3h9l5 5v13H6V3Z",
  spark: "M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5Z",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v9H5v-9Z",
};

const navGroups = [
  {
    label: "Overview",
    items: [{ name: "Command Center", icon: icons.command, active: true }],
  },
  {
    label: "Intelligence",
    items: [
      { name: "Churn Risk", sub: "Survival Analysis", icon: icons.churn },
      { name: "Causal Insights", sub: "Feature Impact", icon: icons.causal },
    ],
  },
  {
    label: "Action",
    items: [
      { name: "Strategy Feed", icon: icons.feed },
      { name: "Approval Queue", icon: icons.queue, badge: 4 },
    ],
  },
  {
    label: "Governance",
    items: [
      { name: "Data Connectors", icon: icons.connectors },
      { name: "Security & Audit Logs", icon: icons.lock },
    ],
  },
];

/* ---------- Status pill ---------- */
const pillTones: Record<string, string> = {
  sig: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  telemetry: "bg-slate-100 text-slate-600 ring-slate-500/20",
  warning: "bg-amber-50 text-amber-700 ring-amber-600/20",
  executed: "bg-blue-50 text-blue-700 ring-blue-600/20",
  rejected: "bg-slate-100 text-slate-500 ring-slate-400/20",
};

function Pill({ tone, children }: { tone: string; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${pillTones[tone]}`}
    >
      {children}
    </span>
  );
}

const quadrantLegend = [
  { q: "Persuadable", color: "#1d4ed8", note: "target" },
  { q: "Sure-Thing", color: "#10b981", note: "" },
  { q: "Lost-Cause", color: "#ef4444", note: "" },
  { q: "Do-Not-Disturb", color: "#94a3b8", note: "suppress" },
];

export default function App() {
  const [env, setEnv] = useState<"Staging" | "Production">("Production");
  const [activeNav, setActiveNav] = useState("Command Center");
  const [decisions, setDecisions] = useState<Record<string, "approved" | "rejected">>({});
  const pending = strategies.filter((s) => !decisions[s.id]).length;
  const activeGroup = navGroups.find((g) => g.items.some((it) => it.name === activeNav))?.label ?? "Overview";

  return (
    <div className="flex h-full w-full bg-canvas text-slate-900">
      {/* ---------- Sidebar ---------- */}
      <aside className="hidden w-64 shrink-0 flex-col bg-slate-900 text-slate-300 lg:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
            <Ic d={icons.spark} className="h-4.5 w-4.5" />
          </div>
          <div className="leading-tight">
            <div className="text-[13px] font-bold text-white">Autonomous BI</div>
            <div className="text-[10px] uppercase tracking-widest text-slate-500">Engine</div>
          </div>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-2">
          {navGroups.map((g) => (
            <div key={g.label}>
              <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                {g.label}
              </div>
              <div className="space-y-0.5">
                {g.items.map((it) => (
                  <button
                    key={it.name}
                    onClick={() => setActiveNav(it.name)}
                    aria-current={activeNav === it.name ? "page" : undefined}
                    className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-[13px] transition-colors ${
                      activeNav === it.name
                        ? "bg-blue-600 font-semibold text-white"
                        : "text-slate-300 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <Ic d={it.icon} className="h-4.5 w-4.5 shrink-0" />
                    <span className="flex-1 truncate">
                      {it.name}
                      {"sub" in it && it.sub && (
                        <span className="block text-[10px] font-normal text-slate-400 group-hover:text-slate-300">
                          {it.sub}
                        </span>
                      )}
                    </span>
                    {"badge" in it && it.badge && (
                      <span className="tnum rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold text-slate-900">
                        {it.badge}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="m-3 rounded-xl bg-white/5 p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-emerald-400">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            Models online
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
            Cox PH · Double-ML · Uplift ensembles retrained 2h ago.
          </p>
        </div>
      </aside>

      {/* ---------- Main column ---------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-16 shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-4 sm:px-6">
          <nav className="flex items-center gap-1.5 text-[13px] text-slate-400">
            <span>{activeGroup}</span>
            <Ic d={icons.chevron} className="h-3.5 w-3.5" />
            <span className="font-semibold text-slate-900">{activeNav}</span>
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="relative hidden md:block">
              <Ic
                d={icons.search}
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              />
              <input
                placeholder="Search cohorts, accounts, models…"
                className="h-9 w-64 rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-[13px] text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-500/20"
              />
            </div>

            {/* Env toggle */}
            <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5">
              {(["Staging", "Production"] as const).map((e) => (
                <button
                  key={e}
                  onClick={() => setEnv(e)}
                  className={`rounded-md px-2.5 py-1 text-[12px] font-semibold transition-colors ${
                    env === e
                      ? e === "Production"
                        ? "bg-slate-900 text-white shadow-sm"
                        : "bg-white text-amber-600 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {e}
                </button>
              ))}
            </div>

            <div className="hidden items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-[12px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20 sm:flex">
              <Ic d={icons.shield} className="h-4 w-4" />
              Secure Environment
            </div>

            <button className="relative grid h-9 w-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100">
              <Ic d={icons.bell} className="h-4.5 w-4.5" />
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-white" />
            </button>

            <div className="flex items-center gap-2.5 border-l border-slate-200 pl-3">
              <div className="grid h-9 w-9 place-items-center rounded-full bg-slate-900 text-[13px] font-bold text-white">
                AV
              </div>
              <div className="hidden leading-tight lg:block">
                <div className="text-[13px] font-semibold text-slate-900">A. Vasquez</div>
                <div className="text-[11px] font-medium text-blue-600">Super Admin</div>
              </div>
            </div>
          </div>
        </header>

        {/* Scroll body */}
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          <div className="mx-auto max-w-[1400px] space-y-6">
            {/* Section 1 — KPIs */}
            <section className="grid grid-cols-1 gap-5 md:grid-cols-3">
              {/* NRR */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.1)]">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-[12px] font-semibold uppercase tracking-wide text-slate-400">
                      Net Revenue Retention
                    </div>
                    <div className="tnum mt-2 text-[38px] font-bold leading-none text-slate-900">
                      112<span className="text-2xl text-slate-400">%</span>
                    </div>
                  </div>
                  <Pill tone="sig">
                    <Ic d={icons.check} className="h-3 w-3" />
                    +4.2 QoQ
                  </Pill>
                </div>
                <div className="mt-3 -mx-1">
                  <Sparkline />
                </div>
                <div className="mt-1 text-[12px] text-slate-500">
                  Trailing 10 months · target ≥ 110%
                </div>
              </div>

              {/* Churn risk */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.1)]">
                <div className="text-[12px] font-semibold uppercase tracking-wide text-slate-400">
                  Predicted 30-Day Churn Risk
                </div>
                <div className="tnum mt-2 text-[38px] font-bold leading-none text-slate-900">
                  $14,500 <span className="text-lg font-semibold text-slate-400">MRR</span>
                </div>
                <div className="mt-4 flex gap-2">
                  <div className="flex-1 rounded-lg bg-amber-50 px-3 py-2 ring-1 ring-inset ring-amber-600/20">
                    <div className="text-[11px] font-medium text-amber-700">Voluntary</div>
                    <div className="tnum text-[15px] font-bold text-amber-800">$8,900</div>
                  </div>
                  <div className="flex-1 rounded-lg bg-red-50 px-3 py-2 ring-1 ring-inset ring-red-600/20">
                    <div className="text-[11px] font-medium text-red-700">Involuntary</div>
                    <div className="tnum text-[15px] font-bold text-red-800">$5,600</div>
                  </div>
                </div>
              </div>

              {/* Pending AI actions */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.1)]">
                <div className="text-[12px] font-semibold uppercase tracking-wide text-slate-400">
                  Pending AI Actions
                </div>
                <div className="mt-2 flex items-center gap-3">
                  <div className="tnum grid h-14 w-14 place-items-center rounded-2xl bg-blue-600 text-3xl font-bold text-white">
                    {pending}
                  </div>
                  <div className="text-[13px] leading-snug text-slate-600">
                    action{pending === 1 ? "" : "s"} awaiting
                    <br />
                    <span className="font-semibold text-slate-900">human authorization</span>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-2 text-[12px] text-slate-500">
                  <Ic d={icons.lock} className="h-4 w-4 text-slate-400" />
                  Human-in-the-loop required in {env}
                </div>
              </div>
            </section>

            {/* Section 2 — Predictive + Causal */}
            <section className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              {/* Survival */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.1)]">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-[15px] font-semibold text-slate-900">
                      Survival Analysis · Hazard Functions
                    </h2>
                    <p className="mt-0.5 text-[12px] text-slate-500">
                      Probability of continued subscription over account tenure
                    </p>
                  </div>
                  <Pill tone="telemetry">Cox PH · 4 cohorts</Pill>
                </div>
                <div className="mt-4">
                  <SurvivalChart />
                </div>
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-slate-100 pt-3">
                  {survivalCohorts.map((c) => (
                    <div key={c.key} className="flex items-center gap-1.5 text-[12px] text-slate-600">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: c.color }} />
                      {c.label}
                    </div>
                  ))}
                </div>
              </div>

              {/* Uplift */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_6px_-1px_rgba(0,0,0,0.1)]">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-[15px] font-semibold text-slate-900">
                      Uplift Modeling Matrix
                    </h2>
                    <p className="mt-0.5 text-[12px] text-slate-500">
                      Baseline retention vs. treatment uplift · bubble = MRR weight
                    </p>
                  </div>
                  <Pill tone="sig">Statistically Significant</Pill>
                </div>
                <div className="mt-4">
                  <UpliftMatrix />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 sm:grid-cols-4">
                  {quadrantLegend.map((q) => (
                    <div
                      key={q.q}
                      className={`flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-medium ${
                        q.q === "Persuadable" ? "bg-blue-50 text-blue-700" : "text-slate-600"
                      }`}
                    >
                      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: q.color }} />
                      <span className="truncate">{q.q}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Section 3 — Strategy feed + approvals */}
            <section className="rounded-2xl border border-slate-200 bg-white shadow-[0_4px_6px_-1px_rgba(0,0,0,0.1)]">
              <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
                <div>
                  <h2 className="text-[15px] font-semibold text-slate-900">
                    AI Strategy Feed · Human-in-the-Loop Approvals
                  </h2>
                  <p className="mt-0.5 text-[12px] text-slate-500">
                    Every executed action is signed, cited, and written to the audit log
                  </p>
                </div>
                <Pill tone="warning">
                  <Ic d={icons.spark} className="h-3 w-3" />
                  {pending} awaiting authorization
                </Pill>
              </div>

              <div className="divide-y divide-slate-100">
                {strategies.map((s) => {
                  const decision = decisions[s.id];
                  return (
                    <div
                      key={s.id}
                      className="grid grid-cols-1 gap-5 px-5 py-5 lg:grid-cols-[1fr_380px]"
                    >
                      {/* Left — insight */}
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Pill tone={s.tagTone}>{s.tag}</Pill>
                          <span className="tnum text-[11px] font-medium text-slate-400">
                            {s.id}
                          </span>
                          <span className="text-[11px] text-slate-400">· {s.method}</span>
                        </div>
                        <h3 className="mt-2 text-[15px] font-semibold text-slate-900">
                          {s.title}
                        </h3>
                        <p className="mt-1 text-[13px] leading-relaxed text-slate-600">
                          {s.body}
                        </p>
                        <div className="mt-3 flex flex-wrap items-center gap-4">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-medium text-slate-400">
                              Confidence
                            </span>
                            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100">
                              <div
                                className="h-full rounded-full bg-blue-600"
                                style={{ width: `${s.confidence}%` }}
                              />
                            </div>
                            <span className="tnum text-[12px] font-semibold text-slate-700">
                              {s.confidence}%
                            </span>
                          </div>
                          <span className="text-[12px] font-semibold text-emerald-700">
                            {s.impact}
                          </span>
                        </div>
                      </div>

                      {/* Right — execution block */}
                      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                            Proposed API Payload
                          </span>
                          {decision === "approved" && <Pill tone="executed">Executed</Pill>}
                          {decision === "rejected" && <Pill tone="rejected">Rejected</Pill>}
                        </div>
                        <pre className="tnum overflow-x-auto rounded-lg bg-slate-900 p-3 text-[11px] leading-relaxed text-slate-100">
                          <code>{s.payload}</code>
                        </pre>

                        {!decision ? (
                          <div className="mt-3 flex gap-2">
                            <button
                              onClick={() =>
                                setDecisions((d) => ({ ...d, [s.id]: "approved" }))
                              }
                              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                            >
                              <Ic d={icons.check} className="h-4 w-4" />
                              Approve &amp; Execute
                            </button>
                            <button
                              onClick={() =>
                                setDecisions((d) => ({ ...d, [s.id]: "rejected" }))
                              }
                              className="flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[13px] font-semibold text-slate-600 transition-colors hover:bg-slate-100"
                            >
                              <Ic d={icons.x} className="h-4 w-4" />
                              Reject
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() =>
                              setDecisions((d) => {
                                const n = { ...d };
                                delete n[s.id];
                                return n;
                              })
                            }
                            className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold text-slate-500 transition-colors hover:bg-slate-100"
                          >
                            Undo decision
                          </button>
                        )}

                        <button className="mt-2 flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:underline">
                          <Ic d={icons.cite} className="h-3.5 w-3.5" />
                          View Full Citation Trail
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <footer className="flex items-center justify-between pb-2 text-[11px] text-slate-400">
              <span>Autonomous SaaS BI Engine · SOC 2 Type II · Audit ID a7f3-2c19</span>
              <span className="tnum">Last sync 14:22 UTC · {env}</span>
            </footer>
          </div>
        </main>
      </div>
    </div>
  );
}
