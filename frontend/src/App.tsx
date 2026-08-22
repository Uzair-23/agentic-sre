import { useState, useEffect, useCallback } from "react";
import axios from "axios";
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
  Cpu,
  FileText,
  Terminal,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";

const API_BASE_URL = "http://localhost:8000";

export function App() {
  const [incidents, setIncidents] = useState<IncidentState[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<IncidentState | null>(null);
  
  // Controls state
  const [selectedType, setSelectedType] = useState<IncidentType>("bad_deploy");
  const [loading, setLoading] = useState<boolean>(false);
  
  // Approval Panel state
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [typedAction, setTypedAction] = useState<string>("");
  const [showRejectInput, setShowRejectInput] = useState<boolean>(false);
  const [rejectReason, setRejectReason] = useState<string>("");

  // Fetch list of incidents for left sidebar feed
  const fetchIncidentsList = useCallback(async () => {
    try {
      const res = await axios.get<IncidentState[]>(`${API_BASE_URL}/incidents`);
      if (Array.isArray(res.data)) {
        setIncidents(res.data);
        // Auto-select first incident if none selected
        if (!selectedIncidentId && res.data.length > 0) {
          setSelectedIncidentId(res.data[0].incident_id);
        }
      }
    } catch (err) {
      console.error("Error fetching incidents list:", err);
    }
  }, [selectedIncidentId]);

  // Fetch specific selected incident details
  const fetchSelectedIncident = useCallback(async (id: string) => {
    try {
      const res = await axios.get<IncidentState>(`${API_BASE_URL}/incidents/${id}`);
      if (res.data) {
        setSelectedIncident(res.data);
      }
    } catch (err) {
      console.error(`Error fetching incident ${id}:`, err);
    }
  }, []);

  // Poll list of incidents every 3 seconds
  useEffect(() => {
    fetchIncidentsList();
    const interval = setInterval(fetchIncidentsList, 3000);
    return () => clearInterval(interval);
  }, [fetchIncidentsList]);

  // Poll active selected incident every 2 seconds
  useEffect(() => {
    if (!selectedIncidentId) return;

    fetchSelectedIncident(selectedIncidentId);
    const interval = setInterval(() => {
      fetchSelectedIncident(selectedIncidentId);
    }, 2000);

    return () => clearInterval(interval);
  }, [selectedIncidentId, fetchSelectedIncident]);

  // Handler: Simulate incident
  const handleSimulate = async (incidentTypeToRun: IncidentType) => {
    setLoading(true);
    try {
      const res = await axios.post<{ incident_id: string }>(`${API_BASE_URL}/incidents/simulate`, {
        incident_type: incidentTypeToRun,
      });
      if (res.data && res.data.incident_id) {
        const newId = res.data.incident_id;
        setSelectedIncidentId(newId);
        setTypedAction("");
        setShowRejectInput(false);
        await fetchIncidentsList();
        await fetchSelectedIncident(newId);
      }
    } catch (err) {
      console.error("Failed to simulate incident:", err);
    } finally {
      setLoading(false);
    }
  };

  // Handler: HITL Approve Action
  const handleApprove = async (incidentId: string) => {
    setActionLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/incidents/${incidentId}/approve`);
      setTypedAction("");
      await fetchSelectedIncident(incidentId);
      await fetchIncidentsList();
    } catch (err) {
      console.error(`Failed to approve incident ${incidentId}:`, err);
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: HITL Reject Action
  const handleReject = async (incidentId: string) => {
    setActionLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/incidents/${incidentId}/reject`, {
        reason: rejectReason || "Rejected by operator",
      });
      setRejectReason("");
      setShowRejectInput(false);
      await fetchSelectedIncident(incidentId);
      await fetchIncidentsList();
    } catch (err) {
      console.error(`Failed to reject incident ${incidentId}:`, err);
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: View Trace in Langfuse
  const handleViewTrace = async (incidentId: string) => {
    try {
      const res = await axios.get<{ trace_url: string }>(`${API_BASE_URL}/incidents/${incidentId}/trace`);
      if (res.data && res.data.trace_url) {
        window.open(res.data.trace_url, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      console.error("Failed to fetch trace URL:", err);
      window.open(`https://us.cloud.langfuse.com/project/agentic-sre/traces/${incidentId}`, "_blank");
    }
  };

  // Helper for Status Badge
  const renderStatusBadge = (inc: IncidentState, isLarge = false) => {
    const sizeClasses = isLarge ? "px-3.5 py-1 text-sm" : "px-2.5 py-0.5 text-xs";

    if (inc.approval_status === "approved") {
      return (
        <span className={`${sizeClasses} rounded-full font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5`}>
          <CheckCircle2 className={isLarge ? "w-4 h-4" : "w-3 h-3"} /> Resolved
        </span>
      );
    }
    if (inc.approval_status === "rejected") {
      return (
        <span className={`${sizeClasses} rounded-full font-semibold bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1.5`}>
          <XCircle className={isLarge ? "w-4 h-4" : "w-3 h-3"} /> Rejected
        </span>
      );
    }
    if (inc.proposed_fix && !inc.approval_status) {
      return (
        <span className={`${sizeClasses} rounded-full font-semibold bg-orange-500/20 text-orange-400 border border-orange-500/30 flex items-center gap-1.5 animate-pulse`}>
          <ShieldAlert className={isLarge ? "w-4 h-4" : "w-3 h-3"} /> Awaiting Approval
        </span>
      );
    }
    if (inc.status === "pending") {
      return (
        <span className={`${sizeClasses} rounded-full font-semibold bg-gray-800 text-gray-300 border border-gray-700 flex items-center gap-1.5`}>
          <Clock className={isLarge ? "w-4 h-4" : "w-3 h-3"} /> Pending
        </span>
      );
    }
    return (
      <span className={`${sizeClasses} rounded-full font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30 flex items-center gap-1.5`}>
        <Cpu className={isLarge ? "w-4 h-4" : "w-3 h-3"} /> Investigating
      </span>
    );
  };

  // Check strict guardrail approval enablement
  const proposedFix = selectedIncident?.proposed_fix;
  const isHighRisk = selectedIncident?.risk_level === "high";
  const requiredActionName = proposedFix?.action_type || "";
  const isApproveEnabled = !isHighRisk || typedAction.trim().toLowerCase() === requiredActionName.toLowerCase();

  return (
    <div className="h-screen w-full bg-gray-950 text-gray-100 flex overflow-hidden font-sans">
      {/* Sidebar (Left) */}
      <aside className="w-80 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0">
        {/* Sidebar Header */}
        <div className="p-5 border-b border-gray-800 flex items-center space-x-3">
          <div className="p-2 bg-blue-600/20 text-blue-400 rounded-lg border border-blue-500/30">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-wide flex items-center gap-1.5">
              Agentic-SRE
            </h1>
            <p className="text-xs text-gray-400">Autonomous Incident Response</p>
          </div>
        </div>

        {/* Sidebar Simulation Controls */}
        <div className="p-4 border-b border-gray-800 space-y-3 bg-gray-900/60">
          <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
            Simulate New Incident
          </label>

          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value as IncidentType)}
            className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 font-medium"
          >
            <option value="bad_deploy">Bad Deploy (v2.3.1)</option>
            <option value="memory_leak">Memory Leak (Payment Service)</option>
            <option value="dependency_timeout">Dependency Timeout (DB Exhaustion)</option>
            <option value="traffic_spike">Traffic Spike (Black Friday Surge)</option>
            <option value="config_drift">Config Drift (Auth Flag Mismatch)</option>
          </select>

          <div className="flex gap-2">
            <button
              onClick={() => handleSimulate(selectedType)}
              disabled={loading}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg flex items-center justify-center gap-2 transition-all shadow cursor-pointer disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-current" />
              {loading ? "Running..." : "Simulate"}
            </button>

            <button
              onClick={() => handleSimulate("bad_deploy")}
              disabled={loading}
              title="Replay Golden Incident"
              className="px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-amber-300 rounded-lg flex items-center justify-center transition-all cursor-pointer disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Incident Feed Header */}
        <div className="px-4 py-3 border-b border-gray-800/80 bg-gray-950/40 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-blue-400" /> Incidents Stream
          </span>
          <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full font-mono">
            {incidents.length}
          </span>
        </div>

        {/* Incident Feed Scrollable List */}
        <div className="flex-1 overflow-y-auto divide-y divide-gray-800/60">
          {incidents.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500 italic">
              No simulated incidents recorded. Click 'Simulate' above to start a test.
            </div>
          ) : (
            incidents.map((inc) => {
              const isSelected = inc.incident_id === selectedIncidentId;
              return (
                <div
                  key={inc.incident_id}
                  onClick={() => {
                    setSelectedIncidentId(inc.incident_id);
                    setTypedAction("");
                    setShowRejectInput(false);
                  }}
                  className={`p-4 border-b border-gray-800 hover:bg-gray-800 cursor-pointer transition-colors ${
                    isSelected ? "bg-gray-800/90 border-l-4 border-l-blue-500" : ""
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-mono text-xs font-bold text-gray-200">
                      ID: {inc.incident_id.slice(0, 8)}...
                    </span>
                    {renderStatusBadge(inc)}
                  </div>
                  <div className="text-xs text-gray-400 capitalize font-medium">
                    Type: {inc.incident_type || "Unknown"}
                  </div>
                  {inc.root_cause_hypothesis && (
                    <p className="text-[11px] text-gray-500 mt-1 line-clamp-1 italic">
                      "{inc.root_cause_hypothesis}"
                    </p>
                  )}
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* Main Content (Right) */}
      <main className="flex-1 overflow-y-auto p-8 space-y-6">
        {!selectedIncident ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 space-y-3 py-20">
            <Activity className="w-12 h-12 text-gray-700 animate-pulse" />
            <h3 className="text-lg font-semibold text-gray-400">No Incident Selected</h3>
            <p className="text-xs text-gray-600 max-w-sm text-center">
              Select an incident card from the sidebar or click 'Simulate' to start a new multi-agent response pipeline.
            </p>
          </div>
        ) : (
          <>
            {/* Header: Incident ID, timestamp, status badge, Langfuse trace button */}
            <div className="flex flex-wrap items-center justify-between gap-4 bg-gray-900 p-6 rounded-lg border border-gray-800 shadow-lg">
              <div className="space-y-1">
                <div className="flex items-center space-x-3">
                  <h1 className="text-xl font-bold font-mono text-white">
                    Incident ID: {selectedIncident.incident_id}
                  </h1>
                  {renderStatusBadge(selectedIncident, true)}
                </div>
                <p className="text-xs text-gray-400">
                  Created: {selectedIncident.created_at ? new Date(selectedIncident.created_at).toLocaleString() : "Just now"}
                  {selectedIncident.incident_type && (
                    <span className="ml-2 px-2 py-0.5 bg-gray-800 text-gray-300 rounded font-mono text-[11px]">
                      {selectedIncident.incident_type}
                    </span>
                  )}
                </p>
              </div>

              {/* View Trace in Langfuse button */}
              <button
                onClick={() => handleViewTrace(selectedIncident.incident_id)}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-cyan-400 hover:text-cyan-300 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all cursor-pointer shadow"
              >
                <Terminal className="w-4 h-4" />
                View Trace in Langfuse
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Approval Gate Panel (Prominent Card) */}
            {proposedFix && !selectedIncident.approval_status && (
              <div className="bg-gray-900 border-2 border-orange-500/50 p-6 rounded-lg shadow-xl space-y-4">
                <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-orange-500/10 text-orange-400 rounded-lg border border-orange-500/30">
                      <ShieldAlert className="w-6 h-6 animate-pulse" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-white">Human-In-The-Loop Approval Gate</h3>
                      <p className="text-xs text-gray-400">
                        Autonomous pipeline paused. Action proposal requires operator authorization.
                      </p>
                    </div>
                  </div>

                  {/* Risk Level Badge */}
                  <div>
                    {selectedIncident.risk_level === "high" && (
                      <span className="px-3.5 py-1 bg-red-500/20 text-red-400 border border-red-500/50 text-xs font-bold rounded-full flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4" /> HIGH RISK
                      </span>
                    )}
                    {selectedIncident.risk_level === "medium" && (
                      <span className="px-3.5 py-1 bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 text-xs font-bold rounded-full flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4" /> MEDIUM RISK
                      </span>
                    )}
                    {selectedIncident.risk_level === "low" && (
                      <span className="px-3.5 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 text-xs font-bold rounded-full flex items-center gap-1.5">
                        <ShieldCheck className="w-4 h-4" /> LOW RISK
                      </span>
                    )}
                  </div>
                </div>

                {/* Proposed Fix Details */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-gray-950 p-4 rounded-lg border border-gray-800 text-sm">
                  <div>
                    <span className="text-xs text-gray-500 font-semibold block uppercase">Action</span>
                    <span className="font-mono text-cyan-400 font-bold text-base">
                      {proposedFix.action_type}
                    </span>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500 font-semibold block uppercase">Target</span>
                    <span className="font-mono text-indigo-400 font-bold text-base">
                      {proposedFix.target}
                    </span>
                  </div>
                  {proposedFix.params && Object.keys(proposedFix.params).length > 0 && (
                    <div className="col-span-1 md:col-span-2">
                      <span className="text-xs text-gray-500 font-semibold block uppercase mb-1">Parameters</span>
                      <pre className="text-xs font-mono bg-gray-900 p-2.5 rounded border border-gray-800 text-gray-300 overflow-x-auto">
                        {JSON.stringify(proposedFix.params, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Strict High Risk Guardrail Confirmation Input */}
                {isHighRisk && (
                  <div className="bg-red-950/40 border border-red-500/40 rounded-lg p-4 space-y-2">
                    <div className="flex items-center space-x-2 text-red-400 text-xs font-bold uppercase tracking-wider">
                      <AlertTriangle className="w-4 h-4" />
                      <span>Safety Guardrail Enforcement</span>
                    </div>
                    <p className="text-xs text-gray-300">
                      High-risk actions require typing the exact action name to confirm before approval:
                    </p>
                    <input
                      type="text"
                      value={typedAction}
                      onChange={(e) => setTypedAction(e.target.value)}
                      placeholder={`Type '${requiredActionName}' to enable approve...`}
                      className="bg-gray-950 border border-gray-700 rounded px-3 py-2 text-sm text-white font-mono w-full focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 placeholder:text-gray-600"
                    />
                  </div>
                )}

                {/* Approval & Rejection Buttons */}
                <div className="flex items-center justify-between pt-2">
                  {!showRejectInput ? (
                    <button
                      onClick={() => setShowRejectInput(true)}
                      disabled={actionLoading}
                      className="px-4 py-2 bg-gray-800 hover:bg-red-950/60 text-gray-300 hover:text-red-400 border border-gray-700 hover:border-red-500/50 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50"
                    >
                      <XCircle className="w-4 h-4" /> Reject
                    </button>
                  ) : (
                    <div className="flex-1 mr-4 flex items-center gap-2">
                      <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="Reason for rejection..."
                        className="flex-1 bg-gray-950 border border-gray-700 rounded px-3 py-1.5 text-xs text-white placeholder:text-gray-600 focus:outline-none focus:border-red-500"
                        autoFocus
                      />
                      <button
                        onClick={() => handleReject(selectedIncident.incident_id)}
                        disabled={actionLoading}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded text-xs font-semibold cursor-pointer"
                      >
                        Confirm Reject
                      </button>
                      <button
                        onClick={() => setShowRejectInput(false)}
                        className="px-2 py-1.5 text-gray-400 hover:text-gray-200 text-xs"
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  <button
                    onClick={() => handleApprove(selectedIncident.incident_id)}
                    disabled={!isApproveEnabled || actionLoading}
                    className={`px-6 py-2.5 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow ${
                      isApproveEnabled && !actionLoading
                        ? "bg-emerald-600 hover:bg-emerald-500 text-white cursor-pointer"
                        : "bg-gray-800 text-gray-500 border border-gray-700 cursor-not-allowed opacity-50"
                    }`}
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    {actionLoading ? "Processing..." : "Approve"}
                  </button>
                </div>
              </div>
            )}

            {/* Diagnosis Grid (CSS Grid: grid grid-cols-2 gap-6 mt-6) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
              {/* Left column: Symptoms Card */}
              <div className="bg-gray-900 p-6 rounded-lg border border-gray-800 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center gap-2 border-b border-gray-800 pb-2">
                  <FileText className="w-4 h-4 text-blue-400" /> Symptoms
                </h3>
                {selectedIncident.symptoms && selectedIncident.symptoms.length > 0 ? (
                  <ul className="space-y-2 text-xs text-gray-300">
                    {selectedIncident.symptoms.map((symptom, idx) => (
                      <li key={idx} className="flex items-start gap-2 bg-gray-950 p-2.5 rounded border border-gray-800/80">
                        <span className="w-1.5 h-1.5 bg-blue-400 rounded-full mt-1.5 flex-shrink-0"></span>
                        <span className="leading-relaxed">{symptom}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-xs text-gray-500 italic">No symptoms recorded yet.</div>
                )}
              </div>

              {/* Right column: Root Cause Hypothesis Card */}
              <div className="bg-gray-900 p-6 rounded-lg border border-gray-800 space-y-4">
                <div className="flex items-center justify-between border-b border-gray-800 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-cyan-400" /> Root Cause Hypothesis
                  </h3>
                  {selectedIncident.confidence_score !== undefined && selectedIncident.confidence_score !== null && (
                    <span className="text-xs font-mono font-bold text-cyan-400">
                      Score: {(selectedIncident.confidence_score * 100).toFixed(0)}%
                    </span>
                  )}
                </div>

                <p className="text-sm text-gray-200 leading-relaxed font-medium">
                  {selectedIncident.root_cause_hypothesis || (
                    <span className="text-gray-500 italic">Awaiting diagnosis output...</span>
                  )}
                </p>

                {/* Visual Confidence Score Bar */}
                {selectedIncident.confidence_score !== undefined && selectedIncident.confidence_score !== null && (
                  <div className="space-y-1.5 pt-2">
                    <div className="flex justify-between text-[11px] text-gray-400">
                      <span>Confidence Calibration</span>
                      <span className="font-mono">{(selectedIncident.confidence_score * 100).toFixed(0)} / 100</span>
                    </div>
                    <div className="w-full bg-gray-950 h-2 rounded-full overflow-hidden border border-gray-800">
                      <div
                        className="bg-cyan-500 h-full transition-all duration-500"
                        style={{ width: `${selectedIncident.confidence_score * 100}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Raw Signals (Full-width card containing JSON inside <pre>) */}
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center gap-2 border-b border-gray-800 pb-2">
                <Terminal className="w-4 h-4 text-green-400" /> Raw Telemetry Signals
              </h3>
              <pre className="bg-black p-4 rounded text-green-400 text-sm overflow-x-auto font-mono max-h-60 border border-gray-800">
                {JSON.stringify(selectedIncident.raw_signals || {}, null, 2)}
              </pre>
            </div>

            {/* Audit Trail (Timeline at bottom) */}
            <div className="bg-gray-900 p-6 rounded-lg border border-gray-800 space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center gap-2 border-b border-gray-800 pb-3">
                <Activity className="w-4 h-4 text-emerald-400" /> Audit Trail Timeline
              </h3>

              {!selectedIncident.event_log || selectedIncident.event_log.length === 0 ? (
                <div className="text-xs text-gray-500 italic py-2">
                  No events logged in the audit trail.
                </div>
              ) : (
                <div className="border-l-2 border-gray-700 pl-6 space-y-6 relative ml-2 my-2">
                  {selectedIncident.event_log.map((evt, idx) => (
                    <div key={idx} className="relative group">
                      {/* Timeline dot */}
                      <div className="absolute -left-[31px] top-1 w-3 h-3 rounded-full bg-cyan-500 border-2 border-gray-900"></div>

                      <div className="bg-gray-950 p-4 rounded border border-gray-800 text-xs space-y-1">
                        <div className="flex items-center justify-between text-gray-400">
                          <span className="font-mono font-bold text-cyan-400">
                            [{evt.source_agent}] {evt.action}
                          </span>
                          <span className="font-mono text-[11px] text-gray-500">
                            {new Date(evt.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="text-gray-300 text-xs leading-relaxed">{evt.details}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
