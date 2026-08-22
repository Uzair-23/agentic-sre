import React from "react";
import type { IncidentState } from "../types";
import { Clock, CheckCircle2, XCircle, AlertCircle, ShieldAlert, Cpu } from "lucide-react";

interface IncidentFeedProps {
  incidents: IncidentState[];
  selectedIncidentId: string | null;
  onSelectIncident: (id: string) => void;
}

export const IncidentFeed: React.FC<IncidentFeedProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
}) => {
  const getBadge = (inc: IncidentState) => {
    if (inc.approval_status === "approved") {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3" /> Resolved
        </span>
      );
    }
    if (inc.approval_status === "rejected") {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1">
          <XCircle className="w-3 h-3" /> Rejected
        </span>
      );
    }
    if (inc.proposed_fix && !inc.approval_status) {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center gap-1 animate-pulse">
          <ShieldAlert className="w-3 h-3" /> Awaiting Approval
        </span>
      );
    }
    if (inc.status === "pending") {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-700 text-slate-300 border border-slate-600 flex items-center gap-1">
          <Clock className="w-3 h-3" /> Pending
        </span>
      );
    }
    return (
      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30 flex items-center gap-1">
        <Cpu className="w-3 h-3 animate-spin" /> Investigating
      </span>
    );
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col h-full shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-cyan-400" />
          Incident Feed
        </h2>
        <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-mono font-bold">
          {incidents.length}
        </span>
      </div>

      {incidents.length === 0 ? (
        <div className="text-center py-10 text-slate-500 text-xs italic">
          No simulated incidents yet. Click 'Simulate Incident' to trigger the agent pipeline.
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto max-h-[600px] pr-1">
          {incidents.map((inc) => {
            const isSelected = inc.incident_id === selectedIncidentId;
            return (
              <div
                key={inc.incident_id}
                onClick={() => onSelectIncident(inc.incident_id)}
                className={`p-3 rounded-lg border text-left cursor-pointer transition-all ${
                  isSelected
                    ? "bg-slate-800 border-cyan-500/60 shadow-md shadow-cyan-950/40"
                    : "bg-slate-950/60 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/80"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-mono font-semibold text-slate-300">
                    ID: {inc.incident_id.slice(0, 8)}...
                  </span>
                  {getBadge(inc)}
                </div>

                <div className="text-xs text-slate-400 font-medium">
                  Type: <span className="text-slate-200 capitalize">{inc.incident_type || "Unknown"}</span>
                </div>

                {inc.root_cause_hypothesis && (
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-1 italic">
                    "{inc.root_cause_hypothesis}"
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
