import React, { useState } from "react";
import type { IncidentState } from "../types";
import { ShieldAlert, CheckCircle2, XCircle, AlertTriangle, ShieldCheck } from "lucide-react";

interface ApprovalPanelProps {
  incident: IncidentState;
  onApprove: (incidentId: string) => Promise<void>;
  onReject: (incidentId: string, reason: string) => Promise<void>;
  loading: boolean;
}

export const ApprovalPanel: React.FC<ApprovalPanelProps> = ({
  incident,
  onApprove,
  onReject,
  loading,
}) => {
  const [typedAction, setTypedAction] = useState<string>("");
  const [rejectReason, setRejectReason] = useState<string>("");
  const [showRejectInput, setShowRejectInput] = useState<boolean>(false);

  if (!incident.proposed_fix || incident.approval_status) {
    return null;
  }

  const { proposed_fix, risk_level } = incident;
  const isHighRisk = risk_level === "high";
  const requiredActionText = proposed_fix.action_type;

  const isApproveEnabled = !isHighRisk || typedAction.trim().toLowerCase() === requiredActionText.toLowerCase();

  const handleApproveSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isApproveEnabled && !loading) {
      await onApprove(incident.incident_id);
      setTypedAction("");
    }
  };

  const handleRejectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loading) {
      await onReject(incident.incident_id, rejectReason || "Rejected by operator");
      setRejectReason("");
      setShowRejectInput(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-amber-500/40 rounded-xl p-5 shadow-2xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-amber-500/10 text-amber-400 rounded-lg border border-amber-500/30">
            <ShieldAlert className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white tracking-wide">
              Human-In-The-Loop Approval Gate
            </h3>
            <p className="text-xs text-slate-400">
              Autonomous remediation paused. Operator decision required.
            </p>
          </div>
        </div>

        {/* Risk Badge */}
        <div className="flex items-center space-x-2">
          <span className="text-xs uppercase text-slate-400 font-medium">Risk Level:</span>
          {risk_level === "high" && (
            <span className="px-3 py-1 bg-red-500/20 text-red-400 border border-red-500/50 text-xs font-bold rounded-full flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5" /> HIGH RISK
            </span>
          )}
          {risk_level === "medium" && (
            <span className="px-3 py-1 bg-amber-500/20 text-amber-400 border border-amber-500/50 text-xs font-bold rounded-full flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5" /> MEDIUM RISK
            </span>
          )}
          {risk_level === "low" && (
            <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 text-xs font-bold rounded-full flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" /> LOW RISK
            </span>
          )}
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-950/70 p-4 rounded-lg border border-slate-800 text-sm">
        <div>
          <span className="text-xs text-slate-500 font-semibold block uppercase">Action Type</span>
          <span className="font-mono text-cyan-400 font-bold text-base">
            {proposed_fix.action_type}
          </span>
        </div>
        <div>
          <span className="text-xs text-slate-500 font-semibold block uppercase">Target Service</span>
          <span className="font-mono text-indigo-400 font-bold text-base">
            {proposed_fix.target}
          </span>
        </div>
        {proposed_fix.params && Object.keys(proposed_fix.params).length > 0 && (
          <div className="col-span-1 md:col-span-2">
            <span className="text-xs text-slate-500 font-semibold block uppercase mb-1">Parameters</span>
            <pre className="text-xs font-mono bg-slate-900 p-2 rounded border border-slate-800 text-slate-300 overflow-x-auto">
              {JSON.stringify(proposed_fix.params, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Strict High Risk Guardrail Confirmation Input */}
      {isHighRisk && (
        <div className="bg-red-950/30 border border-red-500/30 rounded-lg p-3 space-y-2">
          <div className="flex items-center space-x-2 text-red-400 text-xs font-bold uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span>Strict Safety Guardrail Enforcement</span>
          </div>
          <p className="text-xs text-slate-300">
            High risk actions require explicit typed confirmation to prevent accidental execution during production incidents.
            Type <code className="bg-red-900/50 text-red-200 px-1.5 py-0.5 rounded font-mono font-bold text-xs">{requiredActionText}</code> below to enable approval:
          </p>
          <input
            type="text"
            value={typedAction}
            onChange={(e) => setTypedAction(e.target.value)}
            placeholder={`Type '${requiredActionText}' to confirm...`}
            className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-2">
        {!showRejectInput ? (
          <button
            type="button"
            onClick={() => setShowRejectInput(true)}
            disabled={loading}
            className="px-4 py-2 bg-slate-800 hover:bg-red-950/60 text-slate-300 hover:text-red-400 border border-slate-700 hover:border-red-500/50 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all disabled:opacity-50"
          >
            <XCircle className="w-4 h-4" /> Reject Action
          </button>
        ) : (
          <form onSubmit={handleRejectSubmit} className="flex-1 mr-4 flex items-center gap-2">
            <input
              type="text"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter rejection reason..."
              className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-red-500"
              autoFocus
            />
            <button
              type="submit"
              disabled={loading}
              className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-semibold"
            >
              Confirm Rejection
            </button>
            <button
              type="button"
              onClick={() => setShowRejectInput(false)}
              className="px-2 py-1.5 text-slate-400 hover:text-slate-200 text-xs"
            >
              Cancel
            </button>
          </form>
        )}

        <form onSubmit={handleApproveSubmit}>
          <button
            type="submit"
            disabled={!isApproveEnabled || loading}
            className={`px-5 py-2.5 rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-lg ${
              isApproveEnabled && !loading
                ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/50 cursor-pointer"
                : "bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed opacity-60"
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            {loading ? "Processing..." : "Approve Remediation"}
          </button>
        </form>
      </div>
    </div>
  );
};
