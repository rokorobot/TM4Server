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
  Clock,
  CheckCircle
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

interface SystemInfo {
  api_version: string;
  tm4server_version: string;
  tm4core_version: string;
  instance_id: string;
  runtime_root: string;
  ok?: boolean;
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
    const totalRequests = 5;

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
      const resp = await fetch(`/api/control/${mode}`, { method: 'POST' });
      const data = await resp.json();
      if (!data.ok) throw data.error;
      // Immediate refresh of control and history
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
                {launchInFlight ? <Clock className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4 fill-zinc-950" />}
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
