"use client";

import { useEffect, useMemo, useState } from "react";
import { getApiUrl } from "@/lib/api";
import { useParams } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import { PIPELINE_NODES, nodeInfo } from "@/lib/pipeline";

// Kept local (not in lib/pipeline.ts) so these literal Tailwind classes are
// scanned by the build — see the note in pipeline.ts.
const NODE_DOT_COLOR: Record<string, string> = {
  planner: "bg-purple-500",
  sdk_validator: "bg-indigo-500",
  schema_validator: "bg-sky-500",
  coder: "bg-blue-500",
  test_linter: "bg-teal-500",
  executor: "bg-yellow-500",
  diagnoser: "bg-red-500",
};

interface EndpointInfo {
  path?: string;
  method?: string;
  status?: string;
  attempts?: number;
  agent_reasoning?: string;
  generated_code?: string;
  execution_stdout?: string;
  execution_stderr?: string;
  diagnostic_feedback?: string;
  validation_mode?: string;
}

interface ExecutionLog {
  id: string;
  node_name: string;
  state_delta: Record<string, unknown>;
  created_at: string;
  duration_ms?: number;
}

const TERMINAL_SUCCESS = "SUCCESS";
const TERMINAL_FAILURE = "FAILED_PERMANENTLY";

const ENDPOINT_STATUS_STYLES: Record<string, string> = {
  SUCCESS: "bg-green-500/8 text-green-700 border-green-500/15",
  FAILED_PERMANENTLY: "bg-red-500/8 text-red-700 border-red-500/15",
  FAILED: "bg-amber-500/8 text-amber-700 border-amber-500/15",
  SCHEMA_FAILED: "bg-amber-500/8 text-amber-700 border-amber-500/15",
  LINTER_FAILED: "bg-amber-500/8 text-amber-700 border-amber-500/15",
  SCHEMA_VALIDATED: "bg-sky-500/8 text-sky-700 border-sky-500/15",
};

function endpointStyle(status?: string): string {
  return ENDPOINT_STATUS_STYLES[status || ""] || "bg-zinc-500/6 text-zinc-600 border-zinc-500/12";
}

function computeSummary(logs: ExecutionLog[]) {
  let endpoints: EndpointInfo[] = [];
  let providerFailovers = 0;
  let modelFailovers = 0;
  let finalModel: string | undefined;

  for (const log of logs) {
    const sd = log.state_delta || {};
    if (Array.isArray(sd.endpoints)) endpoints = sd.endpoints as EndpointInfo[];
    if (typeof sd.provider_failovers === "number") providerFailovers = sd.provider_failovers;
    if (typeof sd.model_failovers === "number") modelFailovers = sd.model_failovers;
    const gc = sd.global_context as Record<string, unknown> | undefined;
    if (gc && typeof gc.final_model_used === "string") finalModel = gc.final_model_used;
  }

  const succeeded = endpoints.filter((e) => e.status === TERMINAL_SUCCESS).length;
  const failed = endpoints.filter((e) => e.status === TERMINAL_FAILURE).length;
  const totalRetries = endpoints.reduce((sum, e) => sum + (e.attempts || 0), 0);

  return {
    endpoints,
    total: endpoints.length,
    succeeded,
    failed,
    inProgress: endpoints.length - succeeded - failed,
    totalRetries,
    providerFailovers,
    modelFailovers,
    finalModel,
  };
}

function StatCard({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="bg-zinc-50/70 border border-zinc-200/60 rounded-xl px-4 py-3">
      <p className="text-[11px] font-medium text-zinc-400 uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-semibold mt-0.5 tabular-nums ${tone || "text-zinc-900"}`}>{value}</p>
    </div>
  );
}

export default function JobTimeline() {
  const { id } = useParams();

  const [status, setStatus] = useState<string>("PENDING");
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [createdAt, setCreatedAt] = useState<string | null>(null);
  const [completedAt, setCompletedAt] = useState<string | null>(null);
  const [showGlossary, setShowGlossary] = useState(false);
  const [streamNote, setStreamNote] = useState<string | null>(null);

  // Connect to SSE if not already finished
  useEffect(() => {
    let eventSource: EventSource | null = null;

    // First fetch historical data
    fetch(getApiUrl(`/dashboard/jobs/${id}/timeline`))
      .then((res) => res.json())
      .then((data) => {
        setStatus(data.status);
        setLogs(data.logs || []);
        setCreatedAt(data.created_at);
        setCompletedAt(data.completed_at);
        setLoading(false);

        if (data.status !== "SUCCESS" && data.status !== "FAILED") {
          // Connect to SSE stream to resume/watch execution
          eventSource = new EventSource(getApiUrl(`/jobs/${id}/stream`));
          eventSource.onmessage = (e) => {
            const evData = JSON.parse(e.data);
            if (evData.status === "complete") {
              if (typeof evData.success === "boolean") {
                setStatus(evData.success ? "SUCCESS" : "FAILED");
              } else if (evData.message && evData.message.toLowerCase().includes("failed")) {
                // Fallback for older backends without the explicit success flag
                setStatus("FAILED");
              } else {
                setStatus("SUCCESS");
              }
              if (!evData.success) setStreamNote(evData.message || null);
              eventSource?.close();
            } else if (evData.error) {
              setStatus("FAILED");
              setStreamNote(evData.error);
              eventSource?.close();
            } else if (evData.status === "running" || evData.status === "resuming") {
              setStreamNote(evData.message || null);
            } else {
              // Re-fetch timeline to get full logs cleanly instead of hacking state
              fetch(getApiUrl(`/dashboard/jobs/${id}/timeline`))
                .then((r) => r.json())
                .then((d) => {
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

  const summary = useMemo(() => computeSummary(logs), [logs]);

  if (loading) return (
    <>
      <Nav />
      <div className="min-h-screen bg-[#fafafa] p-10 text-sm text-zinc-400">Loading timeline…</div>
    </>
  );

  const totalRuntimeMs = (createdAt && completedAt) ? new Date(completedAt).getTime() - new Date(createdAt).getTime() : null;
  const isRunning = status !== "SUCCESS" && status !== "FAILED";
  const donePct = summary.total > 0 ? Math.round(((summary.succeeded + summary.failed) / summary.total) * 100) : 0;
  const succeededPct = summary.total > 0 ? (summary.succeeded / summary.total) * 100 : 0;
  const failedPct = summary.total > 0 ? (summary.failed / summary.total) * 100 : 0;

  return (
    <>
      <Nav />
      <div className="min-h-screen bg-[#fafafa] text-zinc-900 py-12 px-6">
        <div className="max-w-5xl mx-auto space-y-6">

          {/* Header */}
          <div className="bg-white p-6 rounded-2xl border border-zinc-200/70 shadow-[0_1px_2px_rgba(0,0,0,0.03),0_8px_24px_-12px_rgba(0,0,0,0.08)] space-y-5">
            <div className="flex justify-between items-start flex-wrap gap-4">
              <div>
                <Link href="/dashboard" className="text-sm font-medium text-indigo-600 hover:text-indigo-700 mb-2 block">← Back to Dashboard</Link>
                <h1 className="text-2xl font-semibold tracking-tight">Execution Timeline</h1>
                <p className="text-zinc-400 font-mono text-xs mt-1.5">{id}</p>
                {totalRuntimeMs !== null && (
                  <p className="text-zinc-500 text-sm mt-1">
                    Runtime <span className="font-mono">{totalRuntimeMs >= 1000 ? `${(totalRuntimeMs / 1000).toFixed(1)}s` : `${totalRuntimeMs}ms`}</span>
                  </p>
                )}
              </div>

              <div className="text-right flex flex-col items-end gap-3">
                <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide ${
                  status === "SUCCESS" ? "bg-green-500/10 text-green-700" :
                  status === "FAILED" ? "bg-red-500/10 text-red-700" :
                  "bg-indigo-500/10 text-indigo-700"
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    status === "SUCCESS" ? "bg-green-500" :
                    status === "FAILED" ? "bg-red-500" :
                    "bg-indigo-500 animate-pulse"
                  }`} />
                  {status}
                </span>

                {status === "SUCCESS" && (
                  <a
                    href={getApiUrl(`/download/${id}`)}
                    className="inline-flex items-center gap-2 bg-zinc-900 hover:bg-zinc-800 active:scale-[0.99] text-white px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 shadow-[0_1px_2px_rgba(0,0,0,0.1),0_4px_12px_-4px_rgba(0,0,0,0.2)]"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Download SDK Artifact
                  </a>
                )}
              </div>
            </div>

            {isRunning && streamNote && (
              <div className="text-xs font-medium text-indigo-700 bg-indigo-500/5 border border-indigo-500/15 rounded-lg px-3 py-2">
                {streamNote}
              </div>
            )}

            {/* Progress bar */}
            {summary.total > 0 && (
              <div>
                <div className="flex justify-between text-xs font-medium text-zinc-500 mb-1.5">
                  <span>{summary.succeeded + summary.failed} / {summary.total} endpoints complete</span>
                  <span className="tabular-nums">{donePct}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-zinc-100 overflow-hidden flex">
                  <div className="h-full bg-green-500 transition-all duration-300" style={{ width: `${succeededPct}%` }} />
                  <div className="h-full bg-red-500 transition-all duration-300" style={{ width: `${failedPct}%` }} />
                </div>
              </div>
            )}

            {/* Stat cards */}
            {summary.total > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-1">
                <StatCard label="Endpoints" value={summary.total} />
                <StatCard label="Succeeded" value={summary.succeeded} tone="text-green-600" />
                <StatCard label="Failed" value={summary.failed} tone={summary.failed > 0 ? "text-red-600" : undefined} />
                <StatCard label="Diagnoser Retries" value={summary.totalRetries} tone={summary.totalRetries > 0 ? "text-amber-600" : undefined} />
                <StatCard label="Model" value={summary.finalModel ? summary.finalModel.split("/").pop() || summary.finalModel : "—"} />
                <StatCard label="Failovers" value={`${summary.providerFailovers}p / ${summary.modelFailovers}m`} />
              </div>
            )}

            {/* Endpoint grid */}
            {summary.endpoints.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {summary.endpoints.map((ep, i) => (
                  <span
                    key={i}
                    title={ep.agent_reasoning || ep.status}
                    className={`px-2.5 py-1 rounded-lg text-xs font-mono font-medium border ${endpointStyle(ep.status)}`}
                  >
                    {ep.method} {ep.path}
                    {ep.attempts ? <span className="opacity-60 ml-1">×{ep.attempts}</span> : null}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Glossary toggle */}
          <div>
            <button
              onClick={() => setShowGlossary((v) => !v)}
              className="text-sm font-medium text-zinc-500 hover:text-zinc-800 flex items-center gap-1.5 transition-colors"
            >
              <span className={`transition-transform inline-block text-zinc-400 ${showGlossary ? "rotate-90" : ""}`}>›</span>
              What do these pipeline steps mean?
            </button>
            {showGlossary && (
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                {PIPELINE_NODES.map((node) => (
                  <div key={node.key} className="bg-white border border-zinc-200/70 rounded-xl p-4 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`w-2 h-2 rounded-full ${NODE_DOT_COLOR[node.key] || "bg-zinc-500"}`} />
                      <span className="text-sm font-medium text-zinc-900">{node.label}</span>
                    </div>
                    <p className="text-xs text-zinc-500 leading-relaxed">{node.detail}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Timeline */}
          <div className="space-y-5">
            {logs.map((log, index) => {
              const activeIndex = log.state_delta?.active_endpoint_index;
              const ep = (activeIndex !== undefined && activeIndex !== null) ? (log.state_delta?.endpoints as EndpointInfo[] | undefined)?.[activeIndex as number] : undefined;
              const method = log.state_delta?.active_endpoint_method as string | undefined;
              const path = log.state_delta?.active_endpoint_path as string | undefined;
              const info = nodeInfo(log.node_name);
              const errors = log.state_delta?.errors as string[] | undefined;
              const failed = ep?.status === "LINTER_FAILED" || ep?.status === "SCHEMA_FAILED" ||
                (log.node_name === "executor" && ep && ep.status !== "SUCCESS") ||
                (log.node_name === "sdk_validator" && errors && errors.length > 0);

              return (
                <div key={log.id} className="relative pl-8">
                  {/* Timeline Line */}
                  {index !== logs.length - 1 && (
                    <div className="absolute left-[11px] top-8 bottom-[-22px] w-px bg-zinc-200" />
                  )}

                  {/* Timeline Dot */}
                  <div className={`absolute left-0 top-3 w-6 h-6 rounded-full border-4 border-[#fafafa] flex items-center justify-center ${NODE_DOT_COLOR[log.node_name] || "bg-zinc-500"}`} />

                  <div className="bg-white p-6 rounded-xl border border-zinc-200/70 shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:shadow-[0_1px_2px_rgba(0,0,0,0.03),0_4px_16px_-8px_rgba(0,0,0,0.08)] hover:border-zinc-300/70 transition-all">
                    <div className="flex justify-between items-center mb-1.5">
                      <h3 className="text-[13px] font-semibold uppercase tracking-wide flex items-center gap-2 text-zinc-900">
                        {info?.label || log.node_name} {method && path && <span className="text-zinc-400 text-sm normal-case font-mono ml-2 font-normal">({method} {path})</span>}

                        {/* Success/Failure Icon */}
                        {failed ? (
                          <span className="text-red-500 ml-0.5">✗</span>
                        ) : (
                          <span className="text-green-500 ml-0.5">✓</span>
                        )}

                        {/* Duration */}
                        {log.duration_ms !== undefined && (
                          <span className="text-xs text-zinc-400 font-mono font-normal ml-0.5 lowercase tracking-normal">
                            {log.duration_ms >= 1000 ? `${(log.duration_ms / 1000).toFixed(1)}s` : `${log.duration_ms}ms`}
                          </span>
                        )}
                      </h3>
                      <span className="text-xs text-zinc-400 font-mono shrink-0">
                        {new Date(log.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    {info?.short && <p className="text-xs text-zinc-400 mb-4">{info.short}</p>}

                    {/* Rendering specific node outputs */}
                    {log.node_name === "planner" && (
                       <div className="text-zinc-500 text-sm italic border-l-2 border-purple-500/20 pl-4 py-1">
                          &quot;Planner initialized execution trace.&quot;
                       </div>
                    )}

                    {log.node_name === "sdk_validator" && (
                      errors && errors.length > 0 ? (
                        <div className="bg-red-500/5 border border-red-500/15 p-3 rounded-lg text-xs font-mono text-red-700 whitespace-pre-wrap">
                          {errors.join("\n")}
                        </div>
                      ) : (
                        <p className="text-sm text-zinc-500">All SDK files compiled and export checks passed.</p>
                      )
                    )}

                    {log.node_name === "schema_validator" && ep && (
                      <div className="space-y-3">
                        {ep.validation_mode && (
                          <span className="inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide bg-sky-500/10 text-sky-700">
                            {ep.validation_mode} validation
                          </span>
                        )}
                        {ep.execution_stderr && ep.status === "SCHEMA_FAILED" && (
                          <pre className="bg-red-500/5 text-red-700 p-3 rounded-lg text-xs font-mono overflow-x-auto whitespace-pre-wrap border border-red-500/15">
                            {ep.execution_stderr}
                          </pre>
                        )}
                      </div>
                    )}

                    {log.node_name === "test_linter" && ep && (
                      ep.status === "LINTER_FAILED" ? (
                        <pre className="bg-red-500/5 text-red-700 p-3 rounded-lg text-xs font-mono overflow-x-auto whitespace-pre-wrap border border-red-500/15">
                          {ep.execution_stderr}
                        </pre>
                      ) : (
                        <p className="text-sm text-zinc-500">Test script passed static checks (no pytest, uses MockTransport).</p>
                      )
                    )}

                    {log.node_name === "coder" && ep?.agent_reasoning && (
                      <div className="space-y-3">
                        <p className="text-sm text-zinc-600">{ep.agent_reasoning}</p>
                        {ep.generated_code && (
                          <pre className="bg-zinc-950 text-zinc-100 p-4 rounded-lg text-xs overflow-x-auto font-mono leading-relaxed">
                            {ep.generated_code}
                          </pre>
                        )}
                      </div>
                    )}

                    {log.node_name === "executor" && ep && (
                      <div className="space-y-3">
                        {ep.execution_stdout && (
                          <div>
                            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wide">Stdout</span>
                            <pre className="bg-zinc-500/5 text-zinc-700 p-3 rounded-lg text-xs font-mono overflow-x-auto whitespace-pre-wrap mt-1">
                              {ep.execution_stdout}
                            </pre>
                          </div>
                        )}
                        {ep.execution_stderr && (
                          <div>
                            <span className="text-[11px] font-semibold text-red-500 uppercase tracking-wide">Stderr</span>
                            <pre className="bg-red-500/5 text-red-700 p-3 rounded-lg text-xs font-mono overflow-x-auto whitespace-pre-wrap mt-1 border border-red-500/15">
                              {ep.execution_stderr}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}

                    {log.node_name === "diagnoser" && ep?.diagnostic_feedback && (
                      <div className="bg-orange-500/5 border border-orange-500/15 p-4 rounded-lg">
                        <span className="text-[11px] font-semibold text-orange-600 uppercase tracking-wide mb-2 block">Diagnostic Feedback</span>
                        <p className="text-sm text-orange-900/90 font-medium">
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
    </>
  );
}
