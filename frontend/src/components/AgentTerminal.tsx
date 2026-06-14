"use client";

import { useEffect, useState } from "react";

type LogEvent = {
  status: string;
  message: string;
};

export default function AgentTerminal({ specId }: { specId: string }) {
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (!specId) return;

    const eventSource = new EventSource(`http://localhost:8000/api/stream/${specId}`);

    eventSource.onmessage = (event) => {
      try {
        const data: LogEvent = JSON.parse(event.data);
        setLogs((prev) => [...prev, data]);
        
        if (data.status === "complete") {
          setIsComplete(true);
          eventSource.close();
        }
      } catch (e) {
        console.error("Failed to parse SSE data", e);
      }
    };

    eventSource.onerror = (error) => {
      console.error("SSE error", error);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [specId]);

  return (
    <div className="w-full max-w-3xl mx-auto mt-8 bg-zinc-950 rounded-xl overflow-hidden shadow-2xl border border-zinc-800">
      <div className="flex items-center px-4 py-3 bg-zinc-900 border-b border-zinc-800">
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
        </div>
        <div className="mx-auto text-xs font-medium text-zinc-400">APIForge Agent Execution</div>
      </div>
      <div className="p-6 font-mono text-sm h-96 overflow-y-auto flex flex-col gap-2">
        {logs.map((log, i) => (
          <div key={i} className="flex gap-4">
            <span className="text-zinc-500">[{new Date().toLocaleTimeString()}]</span>
            <span className={
              log.status === 'executing' ? 'text-blue-400' :
              log.status === 'diagnosing' ? 'text-yellow-400' :
              log.status === 'complete' ? 'text-green-400' :
              'text-zinc-300'
            }>
              {log.message}
            </span>
          </div>
        ))}
        {!isComplete && (
          <div className="flex gap-2 items-center mt-2">
            <span className="text-zinc-500">[{new Date().toLocaleTimeString()}]</span>
            <span className="text-zinc-300 animate-pulse">_</span>
          </div>
        )}
      </div>
      {isComplete && (
        <div className="p-4 bg-zinc-900 border-t border-zinc-800 flex justify-end">
          <a href={`http://localhost:8000/api/download/${specId}`} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors shadow-lg">
            Download Python SDK
          </a>
        </div>
      )}
    </div>
  );
}
