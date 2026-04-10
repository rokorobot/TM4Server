import React, { useMemo, useState } from "react";

type TabKey = "status" | "runs" | "classification" | "gradients" | "control";

type RuntimeState = "idle" | "running" | "paused" | "halted";

const tabs: { key: TabKey; label: string }[] = [
  { key: "status", label: "Status" },
  { key: "runs", label: "Runs" },
  { key: "classification", label: "Classification" },
  { key: "gradients", label: "Gradients" },
  { key: "control", label: "Control" },
];

const statusData = {
  runtime_state: "idle" as RuntimeState,
  current_exp_id: null,
  queue_depth: 0,
  last_completed_exp: "EXP-AUT-SERVER-0001",
  last_aggregation_at: "2026-04-08T12:00:00Z",
  last_classification_at: "2026-04-08T12:05:00Z",
  instance_id: "tm4-dev-01",
  tm4_version: "dev",
  tm4server_version: "dev",
  uptime_s: 1234,
  health: { runtime: "ok", ledger: "ok", classifier: "ok" },
  recent_events: [
    { ts: "2026-04-08T12:06:00Z", level: "info", message: "Operator console UI mounted." },
    { ts: "2026-04-08T12:05:00Z", level: "info", message: "Last classification completed." },
  ],
};

const runs = [
  {
    exp_id: "EXP-AUT-SERVER-0001",
    status: "success",
    started_at: "2026-04-08T11:58:00Z",
    completed_at: "2026-04-08T11:59:18Z",
    duration_s: 78,
    fitness_max: 100,
    ttc: 1,
    violations: 0,
    classification: "CONVERGENT",
    execution_mode: "VPS",
    benchmark_family: "identity_anchor",
    model: "qwen2.5:3b",
    anchor_regime: "A0_STRICT_IDENTITY",
  },
  {
    exp_id: "EXP-AUT-SERVER-0002",
    status: "success",
    started_at: "2026-04-08T12:10:00Z",
    completed_at: "2026-04-08T12:14:00Z",
    duration_s: 240,
    fitness_max: 92,
    ttc: 3,
    violations: 0,
    classification: "SATURATED",
    execution_mode: "VPS",
    benchmark_family: "gradient_suite",
    model: "qwen2.5:3b",
    anchor_regime: "A1_WEAKENED_ANCHOR",
  },
];

const classificationSummary = {
  counts: {
    FAILED_EXECUTION: 0,
    SATURATED: 2,
    NO_GRADIENT: 1,
    CONVERGENT: 4,
    UNSTABLE: 0,
    UNCLASSIFIED: 1,
  },
  confidence_distribution: { high: 4, medium: 3, low: 1 },
};

const classificationRuns = [
  {
    exp_id: "EXP-AUT-SERVER-0001",
    classification: "CONVERGENT",
    confidence: 0.92,
    reason: "Fast convergence with no violations and stable metrics.",
    triggered_rules: ["ttc_fast", "violations_zero", "variance_low"],
  },
  {
    exp_id: "EXP-AUT-SERVER-0002",
    classification: "SATURATED",
    confidence: 0.88,
    reason: "Performance plateau reached with low incremental gain.",
    triggered_rules: ["plateau_detected", "late_stage_gain_low"],
  },
];

const gradientCards = [
  { label: "Convergence Rate", value: "62%" },
  { label: "Instability Rate", value: "8%" },
  { label: "Saturation Rate", value: "22%" },
  { label: "No-Gradient Rate", value: "11%" },
];

function classNames(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 shadow-sm">
      <div className="border-b border-zinc-800 px-5 py-4">
        <h2 className="text-sm font-semibold tracking-wide text-zinc-100">{title}</h2>
        {subtitle ? <p className="mt-1 text-sm text-zinc-400">{subtitle}</p> : null}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">{label}</div>
      <div className="mt-2 text-xl font-semibold text-zinc-100">{value}</div>
    </div>
  );
}

function StatusBanner({ state }: { state: RuntimeState }) {
  const tone =
    state === "running"
      ? "border-emerald-700/60 bg-emerald-950/40 text-emerald-300"
      : state === "paused"
      ? "border-amber-700/60 bg-amber-950/40 text-amber-300"
      : state === "halted"
      ? "border-red-700/60 bg-red-950/40 text-red-300"
      : "border-zinc-700 bg-zinc-900 text-zinc-300";

  return (
    <div className={classNames("rounded-2xl border px-4 py-3 text-sm font-medium", tone)}>
      Runtime state: <span className="font-semibold uppercase">{state}</span>
    </div>
  );
}

function SectionHeader({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-zinc-400">{title}</h3>
      {action}
    </div>
  );
}

function ActionButton({
  children,
  subtle = false,
}: {
  children: React.ReactNode;
  subtle?: boolean;
}) {
  return (
    <button
      type="button"
      className={classNames(
        "rounded-xl border px-3 py-2 text-sm font-medium transition",
        subtle
          ? "border-zinc-700 bg-zinc-900 text-zinc-200 hover:bg-zinc-800"
          : "border-emerald-700/60 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-950/60"
      )}
    >
      {children}
    </button>
  );
}

function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-800 text-sm">
        <thead className="bg-zinc-950">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-4 py-3 text-left font-medium text-zinc-400">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800 bg-zinc-950/40">
          {rows.map((row, idx) => (
            <tr key={idx} className="hover:bg-zinc-900/60">
              {row.map((cell, cellIdx) => (
                <td key={cellIdx} className="px-4 py-3 text-zinc-200">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusTab() {
  return (
    <div className="space-y-6">
      <StatusBanner state={statusData.runtime_state} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active Experiment" value={statusData.current_exp_id ?? "None"} />
        <StatCard label="Queue Depth" value={statusData.queue_depth} />
        <StatCard label="Last Completed" value={statusData.last_completed_exp ?? "None"} />
        <StatCard label="Uptime (s)" value={statusData.uptime_s} />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Panel title="System Health" subtitle="Server-side source of truth">
          <div className="space-y-3 text-sm text-zinc-300">
            <div className="flex justify-between"><span>Runtime</span><span>{statusData.health.runtime}</span></div>
            <div className="flex justify-between"><span>Ledger</span><span>{statusData.health.ledger}</span></div>
            <div className="flex justify-between"><span>Classifier</span><span>{statusData.health.classifier}</span></div>
          </div>
        </Panel>

        <Panel title="Versioning" subtitle="Runtime identity">
          <div className="space-y-3 text-sm text-zinc-300">
            <div className="flex justify-between"><span>Instance</span><span>{statusData.instance_id}</span></div>
            <div className="flex justify-between"><span>TM4</span><span>{statusData.tm4_version}</span></div>
            <div className="flex justify-between"><span>TM4Server</span><span>{statusData.tm4server_version}</span></div>
          </div>
        </Panel>

        <Panel title="Recent Events" subtitle="Latest operator-visible history">
          <div className="space-y-3">
            {statusData.recent_events.map((event) => (
              <div key={event.ts + event.message} className="rounded-xl border border-zinc-800 p-3">
                <div className="text-xs text-zinc-500">{event.ts}</div>
                <div className="mt-1 text-sm text-zinc-200">{event.message}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function RunsTab() {
  const [query, setQuery] = useState("");

  const filteredRuns = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return runs;
    return runs.filter((run) =>
      [run.exp_id, run.classification, run.benchmark_family, run.model, run.anchor_regime]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [query]);

  return (
    <div className="space-y-6">
      <Panel title="Run Ledger" subtitle="Evidence inventory across completed and active runs">
        <SectionHeader
          title="Filters"
          action={<ActionButton subtle>Refresh</ActionButton>}
        />
        <div className="mb-5 grid gap-4 md:grid-cols-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by exp_id, class, benchmark, model..."
            className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none ring-0 placeholder:text-zinc-500"
          />
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-400">
            Status filter stub
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-400">
            Date range stub
          </div>
        </div>

        <DataTable
          columns={[
            "exp_id",
            "status",
            "duration_s",
            "fitness_max",
            "ttc",
            "violations",
            "classification",
          ]}
          rows={filteredRuns.map((run) => [
            <span className="font-medium text-zinc-100">{run.exp_id}</span>,
            run.status,
            String(run.duration_s),
            String(run.fitness_max),
            String(run.ttc),
            String(run.violations),
            run.classification,
          ])}
        />
      </Panel>

      <Panel title="Selected Run Detail" subtitle="Replace this static card with /api/runs/{exp_id}">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Artifacts</div>
            <div className="mt-3 space-y-2 text-sm text-zinc-300">
              <div>/var/lib/tm4/runs/EXP-AUT-SERVER-0001/run_summary.json</div>
              <div>/var/lib/tm4/runs/EXP-AUT-SERVER-0001/report.md</div>
              <div>/var/lib/tm4/runs/EXP-AUT-SERVER-0001/run_manifest.json</div>
            </div>
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Metadata</div>
            <pre className="mt-3 overflow-x-auto text-xs text-zinc-300">
{`{
  "execution_mode": "VPS",
  "instance_id": "tm4-dev-01",
  "model": "qwen2.5:3b"
}`}
            </pre>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function ClassificationTab() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        {Object.entries(classificationSummary.counts).map(([label, value]) => (
          <StatCard key={label} label={label} value={value} />
        ))}
      </div>

      <Panel title="Classification Queue" subtitle="Interpretation layer over completed runs">
        <SectionHeader
          title="Actions"
          action={
            <div className="flex gap-2">
              <ActionButton subtle>Reclassify selected</ActionButton>
              <ActionButton>Reclassify all</ActionButton>
            </div>
          }
        />
        <DataTable
          columns={["exp_id", "classification", "confidence", "reason", "triggered_rules"]}
          rows={classificationRuns.map((item) => [
            item.exp_id,
            item.classification,
            item.confidence.toFixed(2),
            item.reason,
            item.triggered_rules.join(", "),
          ])}
        />
      </Panel>
    </div>
  );
}

function GradientsTab() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {gradientCards.map((card) => (
          <StatCard key={card.label} label={card.label} value={card.value} />
        ))}
      </div>

      <Panel title="Cross-Run Trends" subtitle="Aggregate patterns across experiment families">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">TTC Distribution</div>
            <div className="mt-3 text-sm text-zinc-300">[1, 1, 2, 3, 5]</div>
          </div>
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Grouped Outcomes</div>
            <div className="mt-3 text-sm text-zinc-300">
              Convergent dominates current sample, with moderate saturation and low instability.
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function ControlTab() {
  return (
    <div className="space-y-6">
      <Panel title="Runtime Control" subtitle="Conservative intervention surface">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <ActionButton subtle>Pause runtime</ActionButton>
          <ActionButton subtle>Resume runtime</ActionButton>
          <ActionButton subtle>Halt runtime</ActionButton>
          <ActionButton>Trigger aggregation</ActionButton>
          <ActionButton>Trigger classification</ActionButton>
          <ActionButton>Refresh ledger</ActionButton>
        </div>
      </Panel>

      <Panel title="Control History" subtitle="Audit trail">
        <DataTable
          columns={["timestamp", "action", "operator", "result", "detail"]}
          rows={[
            [
              "2026-04-08T12:07:00Z",
              "aggregate",
              "user",
              "success",
              "Manual aggregation from operator console.",
            ],
          ]}
        />
      </Panel>
    </div>
  );
}

export default function TM4OperatorConsoleLayout() {
  const [activeTab, setActiveTab] = useState<TabKey>("status");

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto flex max-w-7xl gap-6 px-4 py-6 lg:px-6">
        <aside className="hidden w-64 shrink-0 lg:block">
          <div className="sticky top-6 rounded-3xl border border-zinc-800 bg-zinc-950/80 p-4">
            <div className="mb-5">
              <div className="text-xs uppercase tracking-[0.25em] text-zinc-500">TM4Server</div>
              <h1 className="mt-2 text-2xl font-semibold">Operator Console</h1>
              <p className="mt-2 text-sm text-zinc-400">Governed experiment control surface.</p>
            </div>

            <nav className="space-y-2">
              {tabs.map((tab) => {
                const active = activeTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    className={classNames(
                      "flex w-full items-center justify-between rounded-2xl border px-3 py-3 text-left text-sm transition",
                      active
                        ? "border-emerald-700/60 bg-emerald-950/40 text-emerald-300"
                        : "border-zinc-800 bg-zinc-900/60 text-zinc-300 hover:bg-zinc-900"
                    )}
                  >
                    <span>{tab.label}</span>
                    <span className="text-xs uppercase tracking-[0.2em]">v1</span>
                  </button>
                );
              })}
            </nav>
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <div className="mb-6 rounded-3xl border border-zinc-800 bg-zinc-950/80 p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.25em] text-zinc-500">Canonical Interface</div>
                <h2 className="mt-2 text-3xl font-semibold">Web-based. Server-hosted. Operator-first.</h2>
                <p className="mt-2 max-w-3xl text-sm text-zinc-400">
                  Facts, interpretations, and actions are deliberately separated to keep TM4 control explicit and auditable.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <ActionButton subtle>Open API Docs</ActionButton>
                <ActionButton>Generate Report</ActionButton>
              </div>
            </div>
          </div>

          <div className="mb-4 flex gap-2 overflow-x-auto lg:hidden">
            {tabs.map((tab) => {
              const active = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={classNames(
                    "whitespace-nowrap rounded-xl border px-3 py-2 text-sm",
                    active
                      ? "border-emerald-700/60 bg-emerald-950/40 text-emerald-300"
                      : "border-zinc-800 bg-zinc-900 text-zinc-300"
                  )}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {activeTab === "status" && <StatusTab />}
          {activeTab === "runs" && <RunsTab />}
          {activeTab === "classification" && <ClassificationTab />}
          {activeTab === "gradients" && <GradientsTab />}
          {activeTab === "control" && <ControlTab />}
        </main>
      </div>
    </div>
  );
}
