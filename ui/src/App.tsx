import { useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { 
  Activity, 
  Settings, 
  History as HistoryIcon, 
  ShieldAlert, 
  CheckCircle2, 
  Play, 
  Pause, 
  Square,
  Server,
  Zap,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Database,
  Loader2
} from 'lucide-react';

const POLL_INTERVAL = 3000;

// --- API Contracts ---

interface ApiError {
  code: string;
  message: string;
}

interface StatusInfo {
  runtime_state: 'idle' | 'running' | 'paused' | 'halted' | 'error';
  current_exp_id: string | null;
  queue_depth: number;
  last_completed_exp_id: string | null;
  pending: number;
  running: number;
  completed: number;
  failed: number;
  interrupted: number;
}

interface ControlInfo {
  mode: 'run' | 'pause' | 'halt';
}

interface HistoryItem {
  ts_utc: string;
  action: string;
  source: string;
  result: 'accepted' | 'rejected' | 'error';
}

interface RunInfo {
  exp_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'interrupted' | 'unknown';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  task: string;
  model: string;
  requested_by: string;
  failure_reason?: string;
  has_summary: boolean;
  has_results: boolean;
  has_stdout: boolean;
  has_stderr: boolean;
  classification_label?: 'EXECUTION_FAILURE' | 'SATURATED' | 'UNSTABLE' | 'CONVERGENT' | 'SIGNAL_ABSENT' | 'UNCLASSIFIED';
  classification_confidence?: number;
}

interface RunDetail {
  exp_id: string;
  manifest: any;
  runtime_state: any;
  summary: any;
  classification: any;
}

interface SystemInfo {
  api_version: string;
  tm4server_version: string;
  tm4core_version: string;
  instance_id: string;
  runtime_root: string;
  ok?: boolean;
}

interface RegimeInsight {
  regime_key: string;
  task: string;
  model: string;
  label: 'CONVERGENT_CLUSTER' | 'NOISY_REGIME' | 'SATURATED_REGIME' | 'SIGNAL_ABSENT_REGIME' | 'FAILURE_PRONE' | 'INSUFFICIENT_EVIDENCE' | 'UNCLASSIFIED';
  mean_confidence: number;
  run_count: number;
  distribution_counts: Record<string, number>;
  distribution_weighted: Record<string, number>;
  reason: string;
}

interface GradientReport {
  gradient_version: string;
  generated_at: string;
  regimes: RegimeInsight[];
}

// --- Components ---

function ErrorBanner({ error }: { error: ApiError }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-red-700/50 bg-red-950/30 p-4 text-red-200">
      <ShieldAlert className="h-5 w-5 shrink-0" />
      <div>
        <div className="text-xs font-bold uppercase tracking-wider">{error.code}</div>
        <div className="text-sm opacity-90">{error.message}</div>
      </div>
    </div>
  );
}

function StatItem({ label, value, loading }: { label: string; value: ReactNode; loading?: boolean }) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-500">{label}</div>
      <div className={`mt-2 text-lg font-semibold tracking-tight ${loading ? 'animate-pulse text-zinc-700' : 'text-zinc-100'}`}>
        {value ?? '--'}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: RunInfo['status'] }) {
  const styles = {
    queued: 'border-zinc-700 bg-zinc-800/30 text-zinc-400',
    running: 'border-blue-700/50 bg-blue-950/20 text-blue-400 animate-pulse',
    completed: 'border-emerald-700/50 bg-emerald-950/20 text-emerald-400',
    failed: 'border-red-700/50 bg-red-950/20 text-red-400',
    interrupted: 'border-amber-700/50 bg-amber-950/20 text-amber-400',
    unknown: 'border-zinc-800 bg-zinc-900 text-zinc-600',
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wider ${styles[status]}`}>
      {status}
    </span>
  );
}

function ScientificBadge({ label }: { label: RunInfo['classification_label'] }) {
  if (!label) return <span className="text-[10px] font-bold text-zinc-700 uppercase tracking-tighter">—</span>;
  
  const styles = {
    EXECUTION_FAILURE: 'border-red-900 bg-red-950/40 text-red-500',
    SATURATED: 'border-purple-700/50 bg-purple-950/20 text-purple-400',
    UNSTABLE: 'border-orange-700/50 bg-orange-950/20 text-orange-400',
    CONVERGENT: 'border-cyan-700/50 bg-cyan-950/20 text-cyan-400',
    SIGNAL_ABSENT: 'border-zinc-700 bg-zinc-800/30 text-zinc-500',
    UNCLASSIFIED: 'border-zinc-800 bg-zinc-900 text-zinc-600',
  };
  
  return (
    <span className={`rounded border px-2 py-0.5 text-[9px] font-black uppercase tracking-tight ${styles[label] || styles.UNCLASSIFIED}`}>
      {label.replaceAll('_', ' ')}
    </span>
  );
}

function RegimeBadge({ label }: { label: RegimeInsight['label'] }) {
  const styles = {
    CONVERGENT_CLUSTER: 'border-cyan-700/50 bg-cyan-950/20 text-cyan-400',
    NOISY_REGIME: 'border-orange-700/50 bg-orange-950/20 text-orange-400',
    SATURATED_REGIME: 'border-purple-700/50 bg-purple-950/20 text-purple-400',
    SIGNAL_ABSENT_REGIME: 'border-zinc-700 bg-zinc-800/30 text-zinc-500',
    FAILURE_PRONE: 'border-red-700/50 bg-red-950/20 text-red-400',
    INSUFFICIENT_EVIDENCE: 'border-zinc-800 bg-zinc-900 text-zinc-600',
    UNCLASSIFIED: 'border-zinc-800 bg-zinc-900 text-zinc-600',
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wider ${styles[label] || styles.UNCLASSIFIED}`}>
      {label.replaceAll('_', ' ')}
    </span>
  );
}

function DistributionBar({ counts, total }: { counts: Record<string, number>; total: number }) {
  const colors: Record<string, string> = {
    CONVERGENT: 'bg-cyan-500',
    UNSTABLE: 'bg-orange-500',
    SATURATED: 'bg-purple-500',
    SIGNAL_ABSENT: 'bg-zinc-500',
    EXECUTION_FAILURE: 'bg-red-500',
    UNCLASSIFIED: 'bg-zinc-700',
  };

  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-zinc-900">
      {Object.entries(counts).map(([label, count]) => (
        <div 
          key={label}
          style={{ width: `${(count / total) * 100}%` }}
          className={`${colors[label] || colors.UNCLASSIFIED} h-full transition-all`}
          title={`${label}: ${count}`}
        />
      ))}
    </div>
  );
}

function RegimeCard({ insight }: { insight: RegimeInsight }) {
  return (
    <div className="flex flex-col gap-4 rounded-3xl border border-zinc-800 bg-zinc-950/50 p-6 transition hover:border-zinc-700">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-600">Regime Evidence</div>
          <div className="mt-1 text-lg font-black tracking-tight text-zinc-100">{insight.task} <span className="font-light text-zinc-500">/ {insight.model}</span></div>
        </div>
        <RegimeBadge label={insight.label} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col">
          <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-700">Run Count</span>
          <span className="text-sm font-mono font-bold text-zinc-300">{insight.run_count}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-700">Mean Conf</span>
          <span className="text-sm font-mono font-bold text-cyan-500">{Math.round(insight.mean_confidence * 100)}%</span>
        </div>
      </div>

      <div className="space-y-2">
         <div className="flex justify-between text-[9px] font-bold uppercase text-zinc-600">
            <span>Label Distribution (Raw)</span>
            <span>{insight.run_count} Samples</span>
         </div>
         <DistributionBar counts={insight.distribution_counts} total={insight.run_count} />
      </div>

      <div className="text-xs font-medium leading-relaxed text-zinc-400">
        {insight.reason}
      </div>
    </div>
  );
}

function JsonView({ title, data }: { title: string; data: any }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-[9px] font-bold uppercase tracking-widest text-zinc-600">{title}</div>
      <pre className="max-h-[200px] overflow-auto rounded-xl bg-zinc-950/80 p-3 font-mono text-[10px] text-zinc-300 shadow-inner">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}

function EvidenceItem({ label, value, unit = '' }: { label: string; value: any; unit?: string }) {
  return (
    <div className="flex justify-between border-b border-zinc-900 pb-1">
      <span className="text-[9px] font-bold uppercase tracking-wider text-zinc-600">{label}</span>
      <span className="text-[10px] font-mono font-medium text-zinc-300">{value ?? '--'}{unit}</span>
    </div>
  );
}

// --- Main App ---

export default function App() {
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);
  const [health, setHealth] = useState<boolean | null>(null);
  
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [statusErr, setStatusErr] = useState<ApiError | null>(null);
  
  const [control, setControl] = useState<ControlInfo | null>(null);
  const [controlErr, setControlErr] = useState<ApiError | null>(null);
  const [controlInFlight, setControlInFlight] = useState(false);
  const [controlActionErr, setControlActionErr] = useState<ApiError | null>(null);
  
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyErr, setHistoryErr] = useState<ApiError | null>(null);
  
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [systemErr, setSystemErr] = useState<ApiError | null>(null);

  const [launchInFlight, setLaunchInFlight] = useState(false);
  const [lastLaunchId, setLastLaunchId] = useState<string | null>(null);
  const [launchErr, setLaunchErr] = useState<ApiError | null>(null);

  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [runsErr, setRunsErr] = useState<ApiError | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [gradients, setGradients] = useState<GradientReport | null>(null);
  const [gradientsErr, setGradientsErr] = useState<ApiError | null>(null);

  const fetchJson = async (path: string, options?: RequestInit) => {
    const resp = await fetch(path, options);
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
        const err = data?.detail?.error || data?.error || { code: 'HTTP_ERROR', message: resp.statusText || 'An unexpected error occurred' };
        throw err;
    }
    return data;
  };

  const refreshData = useCallback(async () => {
    let successCount = 0;
    const totalRequests = 7;

    // Health check
    try {
      const h = await fetchJson('/healthz');
      setHealth(h.ok);
      successCount++;
    } catch { setHealth(false); }

    // Status
    try {
      const s = await fetchJson('/api/status');
      setStatus(s.status);
      setStatusErr(null);
      successCount++;
    } catch (e: any) { setStatusErr(e); }

    // Control State
    try {
      const c = await fetchJson('/api/control/state');
      setControl(c.control);
      setControlErr(null);
      successCount++;
    } catch (e: any) { setControlErr(e); }

    // History
    try {
      const h = await fetchJson('/api/control/history?limit=50');
      setHistory(h.items);
      setHistoryErr(null);
      successCount++;
    } catch (e: any) { setHistoryErr(e); }

    // System
    try {
      const v = await fetchJson('/api/system/version');
      setSystem(v);
      setSystemErr(null);
      successCount++;
    } catch (e: any) { setSystemErr(e); }

    // Runs
    try {
      const r = await fetchJson('/api/runs?limit=100');
      setRuns(r.items);
      setRunsErr(null);
      successCount++;
    } catch (e: any) { setRunsErr(e); }

    // Gradients
    try {
      const g = await fetchJson('/api/analysis/gradients');
      setGradients(g.report);
      setGradientsErr(null);
      successCount++;
    } catch (e: any) { setGradientsErr(e); }

    // Only update "Last Refresh" if all core endpoints succeeded
    if (successCount === totalRequests) {
      setLastSuccess(new Date().toLocaleTimeString());
    }
  }, []);

  useEffect(() => {
    refreshData();
    const timer = setInterval(refreshData, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [refreshData]);

  const handleControl = async (mode: string) => {
    setControlInFlight(true);
    setControlActionErr(null);
    try {
      await fetchJson(`/api/control/${mode}`, { method: 'POST' });
      // Refresh of control and history is handled by refreshData called in handleLaunch or wait for poll
      // But for better UX we trigger a full data refresh immediately
      await refreshData();
    } catch (e: any) {
      setControlActionErr(e);
    } finally {
      setControlInFlight(false);
    }
  };

  const handleLaunch = async () => {
    setLaunchInFlight(true);
    setLaunchErr(null);
    setLastLaunchId(null);
    try {
      const data = await fetchJson('/api/runs/launch', { method: 'POST' });
      setLastLaunchId(data.exp_id);
      await refreshData();
      // Auto-clear success message after 10s
      setTimeout(() => setLastLaunchId(prev => prev === data.exp_id ? null : prev), 10000);
    } catch (e: any) {
      setLaunchErr(e);
    } finally {
      setLaunchInFlight(false);
    }
  };

  const toggleRunDetail = async (expId: string) => {
    if (selectedRunId === expId) {
      setSelectedRunId(null);
      setRunDetail(null);
      return;
    }
    
    setSelectedRunId(expId);
    setDetailLoading(true);
    setRunDetail(null);
    try {
      const data = await fetchJson(`/api/runs/${expId}`);
      setRunDetail(data.detail);
    } catch (e: any) {
      console.error(e);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleClassify = async (expId: string) => {
    setDetailLoading(true);
    try {
      await fetchJson(`/api/runs/${expId}/classify`, { method: 'POST' });
      // Refresh detail and list
      const data = await fetchJson(`/api/runs/${expId}`);
      setRunDetail(data.detail);
      const r = await fetchJson('/api/runs?limit=100');
      setRuns(r.items);
    } catch (e: any) {
      console.error(e);
      alert(`Classification failed: ${e.message}`);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 md:px-6">
      <header className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-zinc-50">TM4 <span className="font-light text-zinc-500">Operator Console v1</span></h1>
        </div>
        
        <div className="flex items-center gap-4 rounded-2xl border border-zinc-800 bg-zinc-900/30 px-5 py-3 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${health ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-red-500'}`} />
            <span className="text-xs font-bold uppercase tracking-widest text-zinc-400">API Health</span>
          </div>
          <div className="h-4 w-px bg-zinc-800" />
          <div className="flex flex-col">
            <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-600">Instance</span>
            <span className="text-xs font-medium text-zinc-300">{system?.instance_id ?? '...'}</span>
          </div>
          <div className="h-4 w-px bg-zinc-800" />
          <div className="flex flex-col">
            <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-600">Last Refresh</span>
            <span className="text-xs font-medium text-zinc-300">{lastSuccess ?? 'Never'}</span>
          </div>
        </div>
      </header>

      <main className="grid gap-6 lg:grid-cols-2">
        {/* Status Section */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center gap-2 px-1 text-zinc-400">
            <Activity className="h-4 w-4" />
            <h2 className="text-xs font-bold uppercase tracking-[0.25em]">Runtime Status</h2>
          </div>
          
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={`rounded-2xl border px-5 py-4 transition-colors ${
              status?.runtime_state === 'running' ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-400' :
              status?.runtime_state === 'paused' ? 'border-amber-500/30 bg-amber-500/5 text-amber-400' :
              status?.runtime_state === 'halted' ? 'border-red-500/30 bg-red-500/5 text-red-400' :
              'border-zinc-800 bg-zinc-900/40 text-zinc-500'
            }`}>
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-60">Engine State</div>
              <div className="mt-1 text-xl font-black uppercase tracking-tight">{status?.runtime_state ?? 'Unknown'}</div>
            </div>
            <StatItem label="Active ID" value={status?.current_exp_id ?? 'None'} />
            <StatItem label="Pending" value={status?.pending ?? 0} />
            <StatItem label="Last Completed" value={status?.last_completed_exp_id ?? 'None'} />
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-3 grid grid-cols-3 gap-2">
               <div className="flex flex-col items-center">
                  <span className="text-[8px] font-bold text-zinc-600 uppercase">Succ</span>
                  <span className="text-xs font-bold text-emerald-500">{status?.completed ?? 0}</span>
               </div>
               <div className="flex flex-col items-center border-x border-zinc-800">
                  <span className="text-[8px] font-bold text-zinc-600 uppercase">Fail</span>
                  <span className="text-xs font-bold text-red-500">{status?.failed ?? 0}</span>
               </div>
               <div className="flex flex-col items-center">
                  <span className="text-[8px] font-bold text-zinc-600 uppercase">Intr</span>
                  <span className="text-xs font-bold text-amber-500">{status?.interrupted ?? 0}</span>
               </div>
            </div>
          </div>
          {statusErr && <ErrorBanner error={statusErr} />}
        </section>

        {/* Research Signal Section */}
        <section className="flex flex-col gap-4 lg:col-span-2">
          <div className="flex items-center gap-2 px-1 text-cyan-500">
            <Zap className="h-4 w-4 fill-cyan-500" />
            <h2 className="text-xs font-bold uppercase tracking-[0.25em]">Research Signal Gaps</h2>
          </div>
          
          <div className="grid gap-6 md:grid-cols-2">
            {gradientsErr ? (
              <div className="md:col-span-2"><ErrorBanner error={gradientsErr} /></div>
            ) : gradients?.regimes.length ? (
              gradients.regimes.map((insight) => (
                <RegimeCard key={insight.regime_key} insight={insight} />
              ))
            ) : (
              <div className="md:col-span-2 flex flex-col items-center justify-center rounded-3xl border border-zinc-800 border-dashed bg-zinc-950/30 py-12 text-zinc-600">
                <Database className="h-8 w-8 mb-3 opacity-20" />
                <div className="text-sm font-medium">No convergent regimes detected yet.</div>
                <div className="text-[10px] uppercase tracking-widest mt-1">Requires $N \ge 3$ classified runs per Task/Model pairing.</div>
              </div>
            )}
          </div>
        </section>

        {/* Control Section */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center gap-2 px-1 text-zinc-400">
            <Settings className="h-4 w-4" />
            <h2 className="text-xs font-bold uppercase tracking-[0.25em]">Intervention</h2>
          </div>
          
          <div className="flex flex-col justify-between h-full gap-4 rounded-3xl border border-zinc-800 bg-zinc-950/50 p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-500">Requested Mode</div>
                <div className="mt-1 text-2xl font-black text-zinc-100 uppercase tracking-tighter">
                  {control?.mode ?? '---'}
                </div>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => handleControl('run')}
                  disabled={controlInFlight || control?.mode === 'run'}
                  className="flex items-center gap-2 rounded-xl border border-emerald-700/50 bg-emerald-950/20 px-4 py-2 text-sm font-bold text-emerald-400 transition hover:bg-emerald-950/40 disabled:opacity-20"
                >
                  <Play className="h-4 w-4 fill-emerald-400" /> Run
                </button>
                <button 
                  onClick={() => handleControl('pause')}
                  disabled={controlInFlight || control?.mode === 'pause'}
                  className="flex items-center gap-2 rounded-xl border border-amber-700/50 bg-amber-950/20 px-4 py-2 text-sm font-bold text-amber-400 transition hover:bg-amber-950/40 disabled:opacity-20"
                >
                  <Pause className="h-4 w-4 fill-amber-400" /> Pause
                </button>
                <button 
                  onClick={() => handleControl('halt')}
                  disabled={controlInFlight || control?.mode === 'halt'}
                  className="flex items-center gap-2 rounded-xl border border-red-700/50 bg-red-950/20 px-4 py-2 text-sm font-bold text-red-100 transition hover:bg-red-950/40 disabled:opacity-20"
                >
                  <Square className="h-4 w-4 fill-red-100" /> Halt
                </button>
              </div>
            </div>
            {controlActionErr && <ErrorBanner error={controlActionErr} />}
            {controlErr && <ErrorBanner error={controlErr} />}
            
            <div className="mt-4 pt-4 border-t border-zinc-900">
              <button
                onClick={handleLaunch}
                disabled={launchInFlight}
                className="w-full flex items-center justify-center gap-2 rounded-2xl bg-zinc-100 py-4 text-sm font-black text-zinc-950 transition hover:bg-white disabled:opacity-50"
              >
                {launchInFlight ? <Loader2 className="h-4 w-4 animate-spin text-zinc-950" /> : <Zap className="h-4 w-4 fill-zinc-950" />}
                LAUNCH EXPERIMENT
              </button>
              
              {lastLaunchId && (
                <div className="mt-3 flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold">
                  <CheckCircle className="h-3 w-3" />
                  Queued: {lastLaunchId}
                </div>
              )}
              {launchErr && (
                <div className="mt-3">
                  <ErrorBanner error={launchErr} />
                </div>
              )}
            </div>
          </div>
        </section>

        {/* History Section */}
        <section className="flex flex-col gap-4 lg:col-span-2">
          <div className="flex items-center gap-2 px-1 text-zinc-400">
            <HistoryIcon className="h-4 w-4" />
            <h2 className="text-xs font-bold uppercase tracking-[0.25em]">Audit Trail</h2>
          </div>
          
          <div className="overflow-hidden rounded-3xl border border-zinc-800 bg-zinc-950/50">
            {historyErr ? (
              <div className="p-6"><ErrorBanner error={historyErr} /></div>
            ) : (
              <div className="max-h-[300px] overflow-y-auto">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 border-b border-zinc-800 bg-zinc-950/80 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500 backdrop-blur-md">
                    <tr>
                      <th className="px-6 py-4">Timestamp</th>
                      <th className="px-6 py-4">Action</th>
                      <th className="px-6 py-4">Source</th>
                      <th className="px-6 py-4">Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-900 border-zinc-800">
                    {history.length > 0 ? history.map((e, i) => (
                      <tr key={i} className="hover:bg-zinc-900/20">
                        <td className="whitespace-nowrap px-6 py-3 font-mono text-[11px] text-zinc-400">{e.ts_utc}</td>
                        <td className="px-6 py-3"><span className="rounded-md bg-zinc-900 px-2 py-0.5 font-bold uppercase text-zinc-100 text-[11px]">{e.action}</span></td>
                        <td className="px-6 py-3 text-zinc-400">{e.source}</td>
                        <td className="px-6 py-3">
                          <span className={`flex items-center gap-1.5 font-bold uppercase text-[10px] ${e.result === 'accepted' ? 'text-emerald-500' : 'text-red-400'}`}>
                            {e.result === 'accepted' && <CheckCircle2 className="h-3 w-3" />}
                            {e.result}
                          </span>
                        </td>
                      </tr>
                    )) : (
                      <tr><td colSpan={4} className="px-6 py-12 text-center text-zinc-600 font-medium italic">Audit log is empty.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* Runs Explorer Section */}
        <section className="flex flex-col gap-4 lg:col-span-2">
          <div className="flex items-center gap-2 px-1 text-zinc-400">
            <Database className="h-4 w-4" />
            <h2 className="text-xs font-bold uppercase tracking-[0.25em]">Runs Explorer</h2>
          </div>
          
          <div className="overflow-hidden rounded-3xl border border-zinc-800 bg-zinc-950/50">
            {runsErr ? (
              <div className="p-6"><ErrorBanner error={runsErr} /></div>
            ) : (
              <div className="max-h-[500px] overflow-y-auto">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 border-b border-zinc-800 bg-zinc-950/80 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500 backdrop-blur-md">
                    <tr>
                      <th className="px-6 py-4">EXP ID</th>
                      <th className="px-6 py-4">Status</th>
                      <th className="px-6 py-4">Interpretation</th>
                      <th className="px-6 py-4">Created</th>
                      <th className="px-6 py-4 text-center">Artifacts</th>
                      <th className="px-6 py-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-900 border-zinc-800">
                    {runs.length > 0 ? runs.map((r) => (
                      <tbody key={r.exp_id} className="contents divide-y divide-zinc-900 border-zinc-800">
                        <tr className={`hover:bg-zinc-900/20 cursor-pointer ${selectedRunId === r.exp_id ? 'bg-zinc-900/40 border-l-2 border-blue-500' : ''}`} onClick={() => toggleRunDetail(r.exp_id)}>
                          <td className="whitespace-nowrap px-6 py-3 font-mono font-bold text-zinc-100">{r.exp_id}</td>
                          <td className="px-6 py-3"><StatusBadge status={r.status} /></td>
                          <td className="px-6 py-3"><ScientificBadge label={r.classification_label} /></td>
                          <td className="whitespace-nowrap px-6 py-3 font-mono text-[11px] text-zinc-500">{r.created_at}</td>
                          <td className="px-6 py-3 text-center">
                            <div className="flex justify-center gap-2">
                              {r.has_summary && <CheckCircle2 className="h-3 w-3 text-emerald-500" />}
                              {r.has_stdout && <div className="h-2 w-2 rounded-full border border-zinc-700" title="stdout.log" />}
                            </div>
                          </td>
                          <td className="px-6 py-3 text-right text-zinc-600">
                             {selectedRunId === r.exp_id ? <ChevronDown className="h-4 w-4 inline" /> : <ChevronRight className="h-4 w-4 inline" />}
                          </td>
                        </tr>
                        {selectedRunId === r.exp_id && (
                          <tr>
                            <td colSpan={6} className="bg-zinc-900/30 p-6 shadow-inner animate-in fade-in slide-in-from-top-1 duration-300">
                              {detailLoading ? (
                                <div className="flex items-center justify-center py-12">
                                  <Loader2 className="h-6 w-6 animate-spin text-zinc-600" />
                                </div>
                              ) : runDetail ? (
                                <div className="grid gap-6 md:grid-cols-4">
                                  <JsonView title="Manifest (Launch Intent)" data={runDetail.manifest} />
                                  <JsonView title="Runtime State (Lifecycle)" data={runDetail.runtime_state} />
                                  <JsonView title="Run Summary (Evidence)" data={runDetail.summary} />
                                  
                                  {/* Classification Pane */}
                                  <div className="flex flex-col gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4">
                                    <div className="flex items-center justify-between">
                                      <div className="text-[9px] font-bold uppercase tracking-widest text-zinc-500">Interpretation</div>
                                      {runDetail.classification && (
                                        <div className="text-[10px] font-black text-cyan-500">{Math.round(runDetail.classification.confidence * 100)}% Match</div>
                                      )}
                                    </div>
                                    
                                    {runDetail.classification ? (
                                      <>
                                        <div className="mt-1">
                                          <ScientificBadge label={runDetail.classification.label} />
                                        </div>
                                        <div className="text-[11px] font-medium leading-relaxed text-zinc-300">
                                          {runDetail.classification.reason}
                                        </div>
                                        <div className="mt-2 space-y-1">
                                          <EvidenceItem label="Net Improvement" value={runDetail.classification.evidence.net_improvement} />
                                          <EvidenceItem label="Signal Density" value={runDetail.classification.evidence.improvement_density} />
                                          <EvidenceItem label="Late Variance" value={runDetail.classification.evidence.late_variance} />
                                          <EvidenceItem label="Violations" value={runDetail.classification.evidence.violation_rate} unit="%" />
                                        </div>
                                      </>
                                    ) : (
                                      <div className="flex flex-1 flex-col items-center justify-center gap-2 py-4">
                                        <div className="text-[10px] text-zinc-600 italic">No scientific label assigned</div>
                                        <button 
                                          onClick={(e) => { e.stopPropagation(); handleClassify(r.exp_id); }}
                                          disabled={r.status === 'queued' || r.status === 'running' || !r.has_summary}
                                          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-1.5 text-[10px] font-black uppercase text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-20"
                                        >
                                          Classify Run
                                        </button>
                                      </div>
                                    )}
                                  </div>

                                  <div className="md:col-span-4 flex justify-between items-center pt-4 border-t border-zinc-800">
                                      <span className="text-[10px] font-bold uppercase text-zinc-600 flex items-center gap-2">
                                        Logs: {r.has_stdout ? <span className="text-zinc-400 underline cursor-pointer hover:text-white">stdout.log</span> : 'none'}
                                      </span>
                                      <div className="flex gap-2">
                                         <button disabled className="rounded-md bg-zinc-800 px-3 py-1 text-[10px] font-bold text-zinc-400 hover:bg-zinc-700 disabled:opacity-30">Forensics</button>
                                         <button disabled className="rounded-md bg-zinc-800 px-3 py-1 text-[10px] font-bold text-zinc-400 hover:bg-zinc-700 disabled:opacity-30">Replay</button>
                                      </div>
                                  </div>
                                </div>
                              ) : (
                                <div className="text-center py-6 text-zinc-600 italic">Failed to load run detail.</div>
                              )}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    )) : (
                      <tr><td colSpan={6} className="px-6 py-12 text-center text-zinc-600 font-medium italic">No experiment runs found.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* System Section */}
        <section className="flex flex-col gap-4 lg:col-span-2">
           <div className="flex items-center gap-2 px-1 text-zinc-400">
            <Server className="h-4 w-4" />
            <h2 className="text-xs font-bold uppercase tracking-[0.25em]">System Identity</h2>
          </div>
          
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-3xl border border-zinc-800 bg-zinc-950/50 p-6">
               <div className="space-y-4">
                  <div className="flex justify-between border-b border-zinc-900 pb-2">
                    <span className="text-xs font-bold uppercase tracking-widest text-zinc-600">API Version</span>
                    <span className="text-xs font-mono font-medium text-emerald-400">{system?.api_version ?? '---'}</span>
                  </div>
                  <div className="flex justify-between border-b border-zinc-900 pb-2">
                    <span className="text-xs font-bold uppercase tracking-widest text-zinc-600">TM4Server</span>
                    <span className="text-xs font-mono font-medium text-zinc-300">{system?.tm4server_version ?? 'unknown'}</span>
                  </div>
                  <div className="flex justify-between border-b border-zinc-900 pb-2">
                    <span className="text-xs font-bold uppercase tracking-widest text-zinc-600">TM4Core</span>
                    <span className="text-xs font-mono font-medium text-zinc-300">{system?.tm4core_version ?? 'unknown'}</span>
                  </div>
               </div>
            </div>

            <div className="rounded-3xl border border-zinc-800 bg-zinc-950/50 p-6 flex flex-col justify-between">
               <div className="space-y-3">
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-700">Client Runtime Root</span>
                    <div className="rounded-xl bg-zinc-900/50 px-3 py-2 text-xs font-mono text-zinc-400 break-all">
                      {system?.runtime_root ?? '---'}
                    </div>
                  </div>
               </div>
               
               {systemErr && <ErrorBanner error={systemErr} />}
            </div>
          </div>
        </section>
      </main>

      <footer className="mt-12 flex items-center justify-center gap-4 border-t border-zinc-900 pt-8 opacity-40 hover:opacity-100 transition-opacity">
        <div className="text-[10px] font-black uppercase tracking-[0.3em] text-zinc-600">Governed. Persistent. Auditable.</div>
      </footer>
    </div>
  );
}
