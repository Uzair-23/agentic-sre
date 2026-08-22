import React, { useState } from "react";
import type { IncidentType } from "../types";
import { Play, RotateCcw, Activity } from "lucide-react";

interface SimulationControlsProps {
  onSimulate: (incidentType: IncidentType) => Promise<void>;
  onReplayGolden: () => Promise<void>;
  loading: boolean;
}

export const SimulationControls: React.FC<SimulationControlsProps> = ({
  onSimulate,
  onReplayGolden,
  loading,
}) => {
  const [selectedType, setSelectedType] = useState<IncidentType>("bad_deploy");

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-lg">
      <div className="flex items-center space-x-2">
        <Activity className="w-5 h-5 text-indigo-400" />
        <span className="text-sm font-bold text-slate-200">Incident Simulator</span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {/* Dropdown Selector */}
        <select
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value as IncidentType)}
          className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-medium cursor-pointer"
        >
          <option value="bad_deploy">Bad Deploy (v2.3.1)</option>
          <option value="memory_leak">Memory Leak (Payment Service)</option>
          <option value="dependency_timeout">Dependency Timeout (DB Exhaustion)</option>
          <option value="traffic_spike">Traffic Spike (Black Friday Surge)</option>
          <option value="config_drift">Config Drift (Auth Flag Mismatch)</option>
        </select>

        {/* Simulate Button */}
        <button
          onClick={() => onSimulate(selectedType)}
          disabled={loading}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white text-sm font-semibold rounded-lg flex items-center gap-2 transition-all shadow-md cursor-pointer disabled:cursor-not-allowed"
        >
          <Play className="w-4 h-4 fill-current" />
          {loading ? "Simulating..." : "Simulate Incident"}
        </button>

        {/* Replay Golden Incident Button */}
        <button
          onClick={onReplayGolden}
          disabled={loading}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600 text-amber-300 hover:text-amber-200 text-sm font-semibold rounded-lg flex items-center gap-2 transition-all shadow-sm cursor-pointer disabled:cursor-not-allowed"
        >
          <RotateCcw className="w-4 h-4 text-amber-400" />
          Replay Golden Incident
        </button>
      </div>
    </div>
  );
};
