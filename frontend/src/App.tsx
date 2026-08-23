import { useState, useEffect, useCallback, useRef } from "react";
import axios, { type AxiosError } from "axios";
import type { IncidentState, IncidentType } from "./types";
import {
  Shield,
  Play,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  ExternalLink,
  Activity,
  Terminal,
  ChevronRight,
  Wifi,
  WifiOff,
} from "lucide-react";

const API_BASE_URL = "http://localhost:8000";

/** Returns true when an incident has reached a terminal state (no more polling needed) */
function isTerminal(inc: IncidentState | null): boolean {
  if (!inc) return false;
  return (
    inc.approval_status === "approved" ||
    inc.approval_status === "rejected" ||
    inc.status === "no_anomaly" ||
    inc.status === "error"
  );
}

// ---------------------------------------------------------------------------
// Toast notification (lightweight, no library)
// ---------------------------------------------------------------------------
interface Toast {
  id: number;
  message: string;
  kind: "error" | "info" | "success";
}

let toastCounter = 0;

export function App() {
  const [incidents, setIncidents] = useState<IncidentState[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [incident, setIncident] = useState<IncidentState | null>(null);

  const [apiOnline, setApiOnline] = useState<boolean | null>(null); // null = unknown
  const [simType, setSimType] = useState<IncidentType>("bad_deploy");
  const [simLoading, setSimLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Approval gate local state
  const [typedConfirm, setTypedConfirm] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  // Toasts
  const [toasts, setToasts] = useState<Toast[]>([]);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const feedPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ---------------------------------------------------------------------------
  // Toast helpers
  // ---------------------------------------------------------------------------
  const pushToast = useCallback((message: string, kind: Toast["kind"] = "error") => {
    const id = ++toastCounter;
    setToasts((prev) => [...prev, { id, message, kind }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  function dismissToast(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  function apiErrorMessage(err: unknown): string {
    const e = err as AxiosError<{ detail?: string }>;
    if (!e.response && e.code === "ERR_NETWORK") return "Cannot reach API — is the server running on :8000?";
    return e.response?.data?.detail ?? e.message ?? "Unexpected error";
  }

  // ---------------------------------------------------------------------------
  // API Health
  // ---------------------------------------------------------------------------
  const checkHealth = useCallback(async () => {
    try {
      await axios.get(`${API_BASE_URL}/`, { timeout: 2000 });
      setApiOnline(true);
    } catch {
      setApiOnline(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const t = setInterval(checkHealth, 8000);
    return () => clearInterval(t);
  }, [checkHealth]);

  // ---------------------------------------------------------------------------
  // Feed polling (every 4 s)
  // ---------------------------------------------------------------------------
  const fetchFeed = useCallback(async () => {
    try {
      const res = await axios.get<IncidentState[]>(`${API_BASE_URL}/incidents`);
      if (Array.isArray(res.data)) {
        setIncidents(res.data);
        setApiOnline(true);
        if (!selectedId && res.data.length > 0) {
          setSelectedId(res.data[0].incident_id);
        }
      }
    } catch (err) {
      setApiOnline(false);
      // silent — health dot already shows offline
      console.error("Feed poll error:", err);
    }
  }, [selectedId]);

  useEffect(() => {
    fetchFeed();
    feedPollingRef.current = setInterval(fetchFeed, 4000);
    return () => {
      if (feedPollingRef.current) clearInterval(feedPollingRef.current);
    };
  }, [fetchFeed]);

  // ---------------------------------------------------------------------------
  // Incident detail polling (every 2 s, stops on terminal state)
  // ---------------------------------------------------------------------------
  const fetchIncident = useCallback(async (id: string) => {
    try {
      const res = await axios.get<IncidentState>(`${API_BASE_URL}/incidents/${id}`);
      setIncident(res.data);
      setApiOnline(true);
      // Stop polling once terminal
      if (isTerminal(res.data)) {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }
    } catch (err) {
      console.error("Incident fetch error:", err);
      // Don't wipe existing incident data on transient failures
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    // Reset + start fresh poll
    if (pollingRef.current) clearInterval(pollingRef.current);
    fetchIncident(selectedId);
    pollingRef.current = setInterval(() => fetchIncident(selectedId), 2000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [selectedId, fetchIncident]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------
  async function handleSimulate(type: IncidentType) {
    setSimLoading(true);
    try {
      const res = await axios.post<{ incident_id: string }>(
        `${API_BASE_URL}/incidents/simulate`,
        { incident_type: type }
      );
      const newId = res.data.incident_id;
      setSelectedId(newId);
      setIncident(null);
      setTypedConfirm("");
      setShowReject(false);
      setApiOnline(true);
      await fetchFeed();
    } catch (err) {
      pushToast(`Simulation failed: ${apiErrorMessage(err)}`);
    } finally {
      setSimLoading(false);
    }
  }

  async function handleApprove() {
    if (!selectedId) return;
    setActionLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/incidents/${selectedId}/approve`);
      setTypedConfirm("");
      await fetchIncident(selectedId);
      await fetchFeed();
      pushToast("Remediation approved and executed.", "success");
    } catch (err) {
      pushToast(`Approve failed: ${apiErrorMessage(err)}`);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!selectedId) return;
    setActionLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/incidents/${selectedId}/reject`, {
        reason: rejectReason.trim() || "Rejected by operator",
      });
      setRejectReason("");
      setShowReject(false);
      await fetchIncident(selectedId);
      await fetchFeed();
      pushToast("Incident rejected.", "info");
    } catch (err) {
      pushToast(`Reject failed: ${apiErrorMessage(err)}`);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleViewTrace() {
    if (!selectedId) return;
    try {
      const res = await axios.get<{ trace_url: string }>(`${API_BASE_URL}/incidents/${selectedId}/trace`);
      window.open(res.data.trace_url, "_blank", "noopener,noreferrer");
    } catch {
      window.open(
        `https://us.cloud.langfuse.com/project/agentic-sre/traces/${selectedId}`,
        "_blank"
      );
    }
  }

  function selectIncident(id: string) {
    setSelectedId(id);
    setIncident(null);
    setTypedConfirm("");
    setShowReject(false);
    setRejectReason("");
  }

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------
  const fix = incident?.proposed_fix;
  const isHighRisk = incident?.risk_level === "high";
  const confirmTarget = fix?.action_type ?? "";
  const approveEnabled =
    !isHighRisk || typedConfirm.trim().toLowerCase() === confirmTarget.toLowerCase();

  // ---------------------------------------------------------------------------
  // Status helpers
  // ---------------------------------------------------------------------------
  function statusLabel(inc: IncidentState): { label: string; color: string } {
    if (inc.approval_status === "approved")
      return { label: "Resolved", color: "text-emerald-400" };
    if (inc.approval_status === "rejected")
      return { label: "Rejected", color: "text-red-400" };
    if (inc.proposed_fix && !inc.approval_status)
      return { label: "Awaiting Approval", color: "text-amber-400" };
    if (inc.status === "pending")
      return { label: "Pending", color: "text-gray-500" };
    return { label: "Investigating", color: "text-blue-400" };
  }

  function riskBadge(level: string | null | undefined) {
    const map: Record<string, string> = {
      high: "text-red-400 border-red-900/60",
      medium: "text-amber-400 border-amber-900/60",
      low: "text-emerald-400 border-emerald-900/60",
    };
    return map[level ?? ""] ?? "text-gray-400 border-white/10";
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="h-screen w-full bg-[#0a0a0a] text-gray-100 flex overflow-hidden font-sans antialiased tracking-tight">

      {/* ── Toast stack ────────────────────────────────────────────────── */}
      <div className="fixed top-4 right-4 z-50 space-y-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => dismissToast(t.id)}
            className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-md border text-sm shadow-lg cursor-pointer transition-all
              ${t.kind === "error" ? "bg-[#1a0808] border-red-900/60 text-red-300" : ""}
              ${t.kind === "success" ? "bg-[#081a0e] border-emerald-900/60 text-emerald-300" : ""}
              ${t.kind === "info" ? "bg-[#111] border-white/10 text-gray-300" : ""}
            `}
          >
            <span className="flex-1">{t.message}</span>
            <XCircle className="w-4 h-4 flex-shrink-0 opacity-60 mt-0.5" />
          </div>
        ))}
      </div>

      {/* ── Sidebar ────────────────────────────────────────────────────── */}
      <aside className="w-72 flex flex-col flex-shrink-0 bg-[#111111] border-r border-white/10">

        {/* Brand */}
        <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Shield className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-semibold text-gray-100">Agentic SRE</span>
          </div>
          {/* API health dot */}
          <div className="flex items-center gap-1.5 text-xs" title={`API: ${apiOnline === null ? "checking…" : apiOnline ? "online" : "offline"}`}>
            {apiOnline === false
              ? <WifiOff className="w-3.5 h-3.5 text-red-500" />
              : <Wifi className={`w-3.5 h-3.5 ${apiOnline ? "text-emerald-500" : "text-gray-600"}`} />
            }
            <span className={`font-mono ${apiOnline ? "text-emerald-500" : apiOnline === false ? "text-red-500" : "text-gray-600"}`}>
              {apiOnline === null ? "…" : apiOnline ? "online" : "offline"}
            </span>
          </div>
        </div>

        {/* Simulate controls */}
        <div className="px-5 py-4 border-b border-white/10 space-y-3">
          <p className="text-[11px] font-medium text-gray-600 uppercase tracking-widest">Simulate</p>
          <select
            value={simType}
            onChange={(e) => setSimType(e.target.value as IncidentType)}
            className="w-full bg-black border border-white/10 rounded-md px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-white/30 transition"
          >
            <option value="bad_deploy">Bad Deploy</option>
            <option value="memory_leak">Memory Leak</option>
            <option value="dependency_timeout">Dependency Timeout</option>
            <option value="traffic_spike">Traffic Spike</option>
            <option value="config_drift">Config Drift</option>
          </select>
          <div className="flex gap-2">
            <button
              onClick={() => handleSimulate(simType)}
              disabled={simLoading}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-white text-black text-sm font-medium rounded-md hover:bg-gray-200 transition disabled:opacity-40 cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-black" />
              {simLoading ? "Starting…" : "Run"}
            </button>
            <button
              onClick={() => handleSimulate("bad_deploy")}
              disabled={simLoading}
              title="Replay golden incident (bad_deploy)"
              className="px-3 py-2 border border-white/10 rounded-md text-gray-500 hover:text-gray-300 hover:border-white/20 transition disabled:opacity-40 cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Incident feed */}
        <div className="px-5 py-3 border-b border-white/10 flex items-center justify-between">
          <p className="text-[11px] font-medium text-gray-600 uppercase tracking-widest">Incidents</p>
          <span className="text-[11px] font-mono text-gray-600">{incidents.length}</span>
        </div>

        <div className="flex-1 overflow-y-auto">
          {incidents.length === 0 ? (
            <p className="px-5 py-6 text-xs text-gray-600 italic">No incidents yet.</p>
          ) : (
            incidents.map((inc) => {
              const active = inc.incident_id === selectedId;
              const { label, color } = statusLabel(inc);
              return (
                <button
                  key={inc.incident_id}
                  onClick={() => selectIncident(inc.incident_id)}
                  className={`w-full text-left px-5 py-3.5 border-b border-white/5 hover:bg-white/5 transition flex items-center justify-between gap-2 group
                    ${active ? "bg-white/5" : ""}`}
                >
                  <div className="min-w-0">
                    <p className="text-xs font-mono text-gray-300 truncate">
                      {inc.incident_id.slice(0, 8)}…
                    </p>
                    <p className={`text-[11px] mt-0.5 ${color}`}>{label}</p>
                  </div>
                  <ChevronRight className={`w-3.5 h-3.5 flex-shrink-0 text-gray-700 group-hover:text-gray-500 transition ${active ? "text-gray-400" : ""}`} />
                </button>
              );
            })
          )}
        </div>
      </aside>

      {/* ── Main canvas ────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto bg-[#0a0a0a]">
        {!incident ? (
          <div className="h-full flex flex-col items-center justify-center gap-3">
            <Activity className="w-8 h-8 text-gray-800" />
            <p className="text-sm text-gray-600">Select or simulate an incident</p>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto px-8 py-10 space-y-6">

            {/* ── Header ── */}
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="font-mono text-sm font-medium text-gray-100">
                    {incident.incident_id}
                  </h1>
                  {(() => {
                    const { label, color } = statusLabel(incident);
                    return <span className={`text-xs font-medium ${color}`}>{label}</span>;
                  })()}
                  {incident.incident_type && (
                    <span className="text-xs font-mono border border-white/10 rounded px-1.5 py-0.5 text-gray-500">
                      {incident.incident_type}
                    </span>
                  )}
                </div>
                {incident.created_at && (
                  <p className="text-xs text-gray-600">
                    {new Date(incident.created_at).toLocaleString()}
                  </p>
                )}
              </div>

              <button
                onClick={handleViewTrace}
                className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 border border-white/10 rounded-md text-xs text-gray-400 hover:text-gray-200 hover:border-white/20 transition cursor-pointer"
              >
                <Terminal className="w-3.5 h-3.5" />
                Langfuse trace
                <ExternalLink className="w-3 h-3 opacity-60" />
              </button>
            </div>

            {/* ── Approval gate ── */}
            {fix && !incident.approval_status && (
              <div className={`rounded-md border p-5 space-y-4 ${isHighRisk ? "border-red-900/50 bg-red-950/20" : "border-white/10 bg-[#111]"}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className={`w-4 h-4 ${isHighRisk ? "text-red-500" : "text-amber-500"}`} />
                    <p className="text-sm font-medium text-gray-100">Awaiting approval</p>
                  </div>
                  {incident.risk_level && (
                    <span className={`text-[11px] font-mono border rounded px-1.5 py-0.5 uppercase ${riskBadge(incident.risk_level)}`}>
                      {incident.risk_level} risk
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="space-y-0.5">
                    <p className="text-[11px] text-gray-600 uppercase tracking-wider">Action</p>
                    <p className="font-mono text-gray-200">{fix.action_type}</p>
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-[11px] text-gray-600 uppercase tracking-wider">Target</p>
                    <p className="font-mono text-gray-200">{fix.target}</p>
                  </div>
                  {fix.params && Object.keys(fix.params).length > 0 && (
                    <div className="col-span-2 space-y-1">
                      <p className="text-[11px] text-gray-600 uppercase tracking-wider">Parameters</p>
                      <pre className="bg-black border border-white/10 rounded-md px-3 py-2 text-xs font-mono text-gray-400 overflow-x-auto">
                        {JSON.stringify(fix.params, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                {/* High-risk confirmation */}
                {isHighRisk && (
                  <div className="space-y-2">
                    <p className="text-xs text-red-400">
                      Type <span className="font-mono bg-red-950/40 px-1 rounded">{confirmTarget}</span> to confirm this action.
                    </p>
                    <input
                      type="text"
                      value={typedConfirm}
                      onChange={(e) => setTypedConfirm(e.target.value)}
                      placeholder={confirmTarget}
                      className="w-full bg-black border border-white/10 focus:border-white/30 outline-none rounded-md px-3 py-2 text-sm font-mono text-gray-200 placeholder:text-gray-700 transition"
                    />
                  </div>
                )}

                {/* Action buttons */}
                <div className="flex items-center justify-between pt-1">
                  {!showReject ? (
                    <button
                      onClick={() => setShowReject(true)}
                      disabled={actionLoading}
                      className="text-xs text-gray-500 hover:text-gray-300 transition cursor-pointer"
                    >
                      Reject
                    </button>
                  ) : (
                    <div className="flex items-center gap-2 flex-1 mr-4">
                      <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="Reason (optional)"
                        autoFocus
                        className="flex-1 bg-black border border-white/10 focus:border-white/30 outline-none rounded-md px-3 py-1.5 text-xs font-mono text-gray-300 placeholder:text-gray-700 transition"
                      />
                      <button
                        onClick={handleReject}
                        disabled={actionLoading}
                        className="px-3 py-1.5 bg-red-950 border border-red-900/60 text-red-400 text-xs rounded-md hover:bg-red-900/40 transition cursor-pointer disabled:opacity-50"
                      >
                        {actionLoading ? "…" : "Confirm"}
                      </button>
                      <button
                        onClick={() => setShowReject(false)}
                        className="text-xs text-gray-600 hover:text-gray-400 transition"
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  <button
                    onClick={handleApprove}
                    disabled={!approveEnabled || actionLoading}
                    className="px-4 py-2 bg-white text-black text-sm font-medium rounded-md hover:bg-gray-200 transition disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {actionLoading ? "Processing…" : "Approve"}
                  </button>
                </div>
              </div>
            )}

            {/* Resolved/Rejected banner */}
            {incident.approval_status === "approved" && (
              <div className="flex items-center gap-2 px-4 py-3 border border-emerald-900/50 bg-emerald-950/20 rounded-md text-sm text-emerald-400">
                <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                Remediation approved and executed.
                {incident.resolution && <span className="ml-1 text-gray-400 text-xs">{incident.resolution}</span>}
              </div>
            )}
            {incident.approval_status === "rejected" && (
              <div className="flex items-center gap-2 px-4 py-3 border border-red-900/50 bg-red-950/20 rounded-md text-sm text-red-400">
                <XCircle className="w-4 h-4 flex-shrink-0" />
                Rejected.
                {incident.approval_notes && <span className="ml-1 text-gray-400 text-xs">{incident.approval_notes}</span>}
              </div>
            )}

            {/* ── Diagnosis grid ── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Symptoms */}
              <div className="rounded-md border border-white/10 bg-[#111111] p-5 space-y-3">
                <p className="text-[11px] font-medium text-gray-600 uppercase tracking-widest">Symptoms</p>
                {incident.symptoms && incident.symptoms.length > 0 ? (
                  <ul className="space-y-1.5">
                    {incident.symptoms.map((s, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                        <span className="mt-1.5 w-1 h-1 rounded-full bg-gray-600 flex-shrink-0" />
                        {s}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-700 italic">No symptoms recorded.</p>
                )}
              </div>

              {/* Root cause */}
              <div className="rounded-md border border-white/10 bg-[#111111] p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] font-medium text-gray-600 uppercase tracking-widest">Root Cause</p>
                  {incident.confidence_score != null && (
                    <span className="text-[11px] font-mono text-gray-600">
                      {(incident.confidence_score * 100).toFixed(0)}% conf.
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-300 leading-relaxed">
                  {incident.root_cause_hypothesis ?? (
                    <span className="text-gray-700 italic">Awaiting diagnosis…</span>
                  )}
                </p>
                {incident.confidence_score != null && (
                  <div className="w-full h-1 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full bg-gray-400 transition-all duration-500"
                      style={{ width: `${incident.confidence_score * 100}%` }}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* ── Raw telemetry ── */}
            <div className="rounded-md border border-white/10 bg-[#111111] p-5 space-y-3">
              <p className="text-[11px] font-medium text-gray-600 uppercase tracking-widest">Raw Telemetry</p>
              <pre className="bg-black text-gray-300 font-mono text-xs p-4 rounded-md overflow-x-auto max-h-56 border border-white/5">
                {JSON.stringify(incident.raw_signals ?? {}, null, 2)}
              </pre>
            </div>

            {/* ── Audit trail ── */}
            <div className="rounded-md border border-white/10 bg-[#111111] p-5 space-y-4">
              <p className="text-[11px] font-medium text-gray-600 uppercase tracking-widest">Audit Trail</p>
              {!incident.event_log || incident.event_log.length === 0 ? (
                <div className="flex items-center gap-2 text-xs text-gray-700 py-2">
                  <Clock className="w-3.5 h-3.5" />
                  No events recorded.
                </div>
              ) : (
                <div className="pl-4 border-l border-white/10 space-y-4">
                  {incident.event_log.map((evt, idx) => (
                    <div key={idx} className="relative">
                      {/* Timeline dot */}
                      <div className="absolute -left-[19px] top-[5px] w-2 h-2 rounded-full bg-gray-700 border border-[#111111]" />
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono text-gray-400">
                            {evt.source_agent}
                          </span>
                          <span className="text-[11px] text-gray-600 font-medium">{evt.action}</span>
                          <span className="ml-auto text-[11px] font-mono text-gray-700">
                            {new Date(evt.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 leading-relaxed">{evt.details}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        )}
      </main>
    </div>
  );
}

export default App;
