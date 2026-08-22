import React, { useState } from "react";
import axios from "axios";
import { ExternalLink, Terminal } from "lucide-react";

interface TraceViewerButtonProps {
  incidentId: string;
  apiBaseUrl: string;
}

export const TraceViewerButton: React.FC<TraceViewerButtonProps> = ({
  incidentId,
  apiBaseUrl,
}) => {
  const [loading, setLoading] = useState(false);

  const handleOpenTrace = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${apiBaseUrl}/incidents/${incidentId}/trace`);
      if (res.data && res.data.trace_url) {
        window.open(res.data.trace_url, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      console.error("Failed to fetch trace URL:", err);
      // Fallback open
      window.open(`https://us.cloud.langfuse.com/project/agentic-sre/traces/${incidentId}`, "_blank");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleOpenTrace}
      disabled={loading}
      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600 text-cyan-400 hover:text-cyan-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
    >
      <Terminal className="w-3.5 h-3.5" />
      {loading ? "Fetching Trace..." : "View Langfuse Trace"}
      <ExternalLink className="w-3 h-3 ml-0.5" />
    </button>
  );
};
