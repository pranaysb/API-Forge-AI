"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

interface ExecutionLog {
  id: string;
  node_name: string;
  state_delta: any;
  created_at: string;
  duration_ms?: number;
}

export default function JobTimeline() {
  const { id } = useParams();
  const router = useRouter();
  
  const [status, setStatus] = useState<string>("PENDING");
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [createdAt, setCreatedAt] = useState<string | null>(null);
  const [completedAt, setCompletedAt] = useState<string | null>(null);
  
  // Connect to SSE if not already finished
  useEffect(() => {
    let eventSource: EventSource | null = null;
    
    // First fetch historical data
    fetch(`http://localhost:8000/api/dashboard/jobs/${id}/timeline`)
      .then(res => res.json())
      .then(data => {
        setStatus(data.status);
        setLogs(data.logs || []);
        setCreatedAt(data.created_at);
        setCompletedAt(data.completed_at);
        setLoading(false);
        
        if (data.status !== "SUCCESS" && data.status !== "FAILED") {
          // Connect to SSE stream to resume/watch execution
          eventSource = new EventSource(`http://localhost:8000/api/jobs/${id}/stream`);
          eventSource.onmessage = (e) => {
            const evData = JSON.parse(e.data);
            if (evData.status === "complete") {
              if (evData.message && evData.message.toLowerCase().includes("failed")) {
                setStatus("FAILED");
              } else {
                setStatus("SUCCESS");
              }
              eventSource?.close();
            } else if (evData.error) {
              setStatus("FAILED");
              eventSource?.close();
            } else {
              // Re-fetch timeline to get full logs cleanly instead of hacking state
              fetch(`http://localhost:8000/api/dashboard/jobs/${id}/timeline`)
                .then(r => r.json())
                .then(d => {
                  setLogs(d.logs || []);
                  setCreatedAt(d.created_at);
                  setCompletedAt(d.completed_at);
                });
            }
          };
        }
      })
      .catch(console.error);
      
    return () => {
      if (eventSource) eventSource.close();
    };
  }, [id]);

  if (loading) return <div className="p-10 text-zinc-500">Loading timeline...</div>;

  const totalRuntimeMs = (createdAt && completedAt) ? new Date(completedAt).getTime() - new Date(createdAt).getTime() : null;

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 py-12 px-6">
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-zinc-200">
          <div>
            <Link href="/dashboard" className="text-sm font-semibold text-blue-600 hover:underline mb-2 block">← Back to Dashboard</Link>
            <h1 className="text-3xl font-extrabold tracking-tight">Execution Timeline</h1>
            <p className="text-zinc-500 font-mono text-sm mt-1">Job: {id}</p>
            {totalRuntimeMs !== null && (
              <p className="text-zinc-500 font-mono text-sm mt-1">
                Runtime: {totalRuntimeMs >= 1000 ? `${(totalRuntimeMs / 1000).toFixed(1)}s` : `${totalRuntimeMs}ms`}
              </p>
            )}
          </div>
          
          <div className="text-right flex flex-col items-end gap-3">
            <span className={`px-4 py-2 rounded-full text-sm font-bold uppercase tracking-wider ${
              status === "SUCCESS" ? "bg-green-100 text-green-700" :
              status === "FAILED" ? "bg-red-100 text-red-700" :
              "bg-blue-100 text-blue-700 animate-pulse"
            }`}>
              {status}
            </span>
            
            {status === "SUCCESS" && (
              <a
                href={`http://localhost:8000/api/download/${id}`}
                className="inline-flex items-center gap-2 bg-black hover:bg-zinc-800 text-white px-5 py-2.5 rounded-xl text-sm font-medium transition-colors shadow-md"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                Download SDK Artifact
              </a>
            )}
          </div>
        </div>

        {/* Timeline */}
        <div className="space-y-6">
          {logs.map((log, index) => {
            const activeIndex = log.state_delta?.active_endpoint_index;
            const ep = activeIndex !== undefined ? log.state_delta?.endpoints?.[activeIndex] : undefined;
            const method = log.state_delta?.active_endpoint_method;
            const path = log.state_delta?.active_endpoint_path;
            
            return (
              <div key={log.id} className="relative pl-8">
                {/* Timeline Line */}
                {index !== logs.length - 1 && (
                  <div className="absolute left-[11px] top-8 bottom-[-24px] w-0.5 bg-zinc-200" />
                )}
                
                {/* Timeline Dot */}
                <div className={`absolute left-0 top-3 w-6 h-6 rounded-full border-4 border-white shadow-sm flex items-center justify-center ${
                  log.node_name === "planner" ? "bg-purple-500" :
                  log.node_name === "coder" ? "bg-blue-500" :
                  log.node_name === "executor" ? "bg-yellow-500" :
                  log.node_name === "diagnoser" ? "bg-red-500" : "bg-zinc-500"
                }`} />

                <div className="bg-white p-6 rounded-xl shadow-sm border border-zinc-200 hover:border-zinc-300 transition-colors">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-bold uppercase tracking-wider flex items-center gap-2">
                      {log.node_name} {method && path && <span className="text-zinc-500 text-sm normal-case font-mono ml-2">({method} {path})</span>}
                      
                      {/* Success/Failure Icon */}
                      {log.node_name === "executor" && ep && ep.status !== "SUCCESS" ? (
                        <span className="text-red-600 font-bold ml-1">✗</span>
                      ) : (
                        <span className="text-green-600 font-bold ml-1">✓</span>
                      )}
                      
                      {/* Duration */}
                      {log.duration_ms !== undefined && (
                        <span className="text-xs text-zinc-500 font-mono ml-1 lowercase">
                          {log.duration_ms >= 1000 ? `${(log.duration_ms / 1000).toFixed(1)}s` : `${log.duration_ms}ms`}
                        </span>
                      )}
                    </h3>
                    <span className="text-xs text-zinc-400 font-mono">
                      {new Date(log.created_at).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Rendering specific node outputs */}
                  {log.node_name === "planner" && (
                     <div className="text-zinc-600 text-sm italic border-l-2 border-purple-200 pl-4 py-1">
                        "Planner initialized execution trace."
                     </div>
                  )}

                  {log.node_name === "coder" && ep?.agent_reasoning && (
                    <div className="space-y-3">
                      <p className="text-sm text-zinc-600">{ep.agent_reasoning}</p>
                      {ep.generated_code && (
                        <pre className="bg-zinc-900 text-zinc-100 p-4 rounded-lg text-xs overflow-x-auto font-mono leading-relaxed">
                          {ep.generated_code}
                        </pre>
                      )}
                    </div>
                  )}

                  {log.node_name === "executor" && ep && (
                    <div className="space-y-3">
                      {ep.execution_stdout && (
                        <div>
                          <span className="text-xs font-bold text-zinc-500 uppercase">Stdout</span>
                          <pre className="bg-black/5 text-zinc-800 p-3 rounded-lg text-xs font-mono overflow-x-auto whitespace-pre-wrap mt-1">
                            {ep.execution_stdout}
                          </pre>
                        </div>
                      )}
                      {ep.execution_stderr && (
                        <div>
                          <span className="text-xs font-bold text-red-500 uppercase">Stderr</span>
                          <pre className="bg-red-50 text-red-800 p-3 rounded-lg text-xs font-mono overflow-x-auto whitespace-pre-wrap mt-1 border border-red-100">
                            {ep.execution_stderr}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}

                  {log.node_name === "diagnoser" && ep?.diagnostic_feedback && (
                    <div className="bg-orange-50 border border-orange-100 p-4 rounded-lg">
                      <span className="text-xs font-bold text-orange-600 uppercase mb-2 block">Diagnostic Feedback</span>
                      <p className="text-sm text-orange-900 font-medium">
                        {ep.diagnostic_feedback}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
