import React from "react";
import type { IncidentState } from "../types";
import { ApprovalPanel } from "./ApprovalPanel";
import { TraceViewerButton } from "./TraceViewerButton";
import { Activity, ShieldCheck, CheckCircle2, XCircle, FileText, Cpu, AlertTriangle } from "lucide-react";

interface IncidentDetailProps {
  incident: IncidentState | null;
  apiBaseUrl: string;
  onApprove: (incidentId: string) => Promise<void>;
  onReject: (incidentId: string, reason: string) => Promise<void>;
  actionLoading: boolean;
}

export const IncidentDetail: React.FC<IncidentDetailProps> = ({
  incident,
  apiBaseUrl,
  onApprove,
  onReject,
  actionLoading,
}) => {
  if (!incident) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-500 flex flex-col items-center justify-center min-h-[400px]">
        <Activity className="w-12 h-12 text-slate-700 mb-3 animate-pulse" />
        <h3 className="text-base font-semibold text-slate-400 mb-1">No Incident Selected</h3>
        <p className="text-xs text-slate-600 max-w-sm">
          Select an incident from the feed on the left or simulate a new incident above to view the autonomous agent pipeline.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-lg font-bold text-slate-100 font-mono">
              Incident ID: {incident.incident_id}
            </h1>
            <span className="text-xs font-semibold uppercase px-2.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
              {incident.incident_type || "Synthetic Incident"}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Created at: {incident.created_at ? new Date(incident.created_at).toLocaleString() : "Just now"}
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <TraceViewerButton incidentId={incident.incident_id} apiBaseUrl={apiBaseUrl} />
        </div>
      </div>

      {/* Approval Panel Guardrail */}
      <ApprovalPanel
        incident={incident}
        onApprove={onApprove}
        onReject={onReject}
        loading={actionLoading}
      />

      {/* Diagnosis & Resolution Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Diagnosis */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md space-y-2">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-cyan-400" /> Diagnosis Hypothesis
            </h3>
            {incident.confidence_score !== undefined && incident.confidence_score !== null && (
              <span className="text-xs font-mono font-bold text-cyan-400">
                Confidence: {(incident.confidence_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-slate-200 leading-relaxed">
            {incident.root_cause_hypothesis || (
              <span className="text-slate-500 italic">Diagnosis in progress...</span>
            )}
          </p>
        </div>

        {/* Resolution / Status */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md space-y-2">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" /> Pipeline Status & Outcome
            </h3>
          </div>
          {incident.resolution ? (
            <div className="flex items-start space-x-2 text-emerald-400 text-sm font-medium">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{incident.resolution}</span>
            </div>
          ) : incident.approval_status === "rejected" ? (
            <div className="flex items-start space-x-2 text-red-400 text-sm font-medium">
              <XCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>Action Rejected: {incident.approval_notes || "Rejected by operator"}</span>
            </div>
          ) : incident.proposed_fix && !incident.approval_status ? (
            <div className="flex items-start space-x-2 text-amber-400 text-sm font-medium">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>Pipeline Paused — Awaiting HITL Approval above.</span>
            </div>
          ) : (
            <div className="text-sm text-slate-400 italic">
              Pipeline running through agent graph...
            </div>
          )}
        </div>
      </div>

      {/* Symptoms & Raw Signals */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Symptoms */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 border-b border-slate-800 pb-2">
            <FileText className="w-4 h-4 text-indigo-400" /> Detected Symptoms
          </h4>
          {incident.symptoms && incident.symptoms.length > 0 ? (
            <ul className="space-y-1.5 text-xs text-slate-300">
              {incident.symptoms.map((s, idx) => (
                <li key={idx} className="flex items-center gap-2 bg-slate-950/60 p-2 rounded border border-slate-800/80">
                  <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full"></span>
                  {s}
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-xs text-slate-500 italic">No symptoms recorded yet.</div>
          )}
        </div>

        {/* Raw Signals */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 border-b border-slate-800 pb-2">
            <FileText className="w-4 h-4 text-cyan-400" /> Raw Telemetry Signals
          </h4>
          {incident.raw_signals && Object.keys(incident.raw_signals).length > 0 ? (
            <pre className="text-xs font-mono bg-slate-950 p-2.5 rounded border border-slate-800 text-slate-300 overflow-x-auto max-h-40">
              {JSON.stringify(incident.raw_signals, null, 2)}
            </pre>
          ) : (
            <div className="text-xs text-slate-500 italic">No raw signals recorded.</div>
          )}
        </div>
      </div>

      {/* Event Log Vertical Timeline */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 border-b border-slate-800 pb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" /> Audit Trail — Event Log Timeline
        </h3>

        {!incident.event_log || incident.event_log.length === 0 ? (
          <div className="text-xs text-slate-500 italic py-4 text-center">
            No events logged in the audit trail yet.
          </div>
        ) : (
          <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
            {incident.event_log.map((evt, idx) => (
              <div key={idx} className="relative flex items-start space-x-3">
                {/* Node icon dot */}
                <div className="absolute -left-6 top-1.5 w-3 h-3 rounded-full bg-cyan-500 border-2 border-slate-900 shadow-sm"></div>

                <div className="flex-1 bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-xs space-y-1">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="font-semibold text-cyan-400 font-mono">
                      [{evt.source_agent}] {evt.action}
                    </span>
                    <span className="font-mono text-[10px] text-slate-500">
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-slate-300 font-sans leading-relaxed">{evt.details}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
