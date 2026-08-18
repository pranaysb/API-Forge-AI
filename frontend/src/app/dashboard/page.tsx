"use client";

import { useEffect, useState } from "react";
import { getApiUrl } from "@/lib/api";
import Link from "next/link";
import Nav from "@/components/Nav";

interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

interface Job {
  id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

const STATUS_STYLE: Record<string, string> = {
  SUCCESS: "bg-green-500/10 text-green-700",
  FAILED: "bg-red-500/10 text-red-700",
  RUNNING: "bg-indigo-500/10 text-indigo-700",
  PENDING: "bg-amber-500/10 text-amber-700",
};

const STATUS_DOT: Record<string, string> = {
  SUCCESS: "bg-green-500",
  FAILED: "bg-red-500",
  RUNNING: "bg-indigo-500 animate-pulse",
  PENDING: "bg-amber-500",
};

function formatDuration(createdAt: string, completedAt: string | null): string | null {
  if (!completedAt) return null;
  const ms = new Date(completedAt).getTime() - new Date(createdAt).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  // Tracks which project's jobs are currently loaded; loadingJobs is derived
  // from this instead of a separate flag toggled synchronously in an effect.
  const [jobsLoadedFor, setJobsLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    fetch(getApiUrl("/dashboard/projects"))
      .then((res) => res.json())
      .then((data) => {
        setProjects(data);
        if (data.length > 0) setSelectedProjectId(data[0].id);
      })
      .catch(console.error)
      .finally(() => setLoadingProjects(false));
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    let cancelled = false;
    fetch(getApiUrl(`/dashboard/projects/${selectedProjectId}/jobs`))
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        setJobs(data);
        setJobsLoadedFor(selectedProjectId);
      })
      .catch(console.error);
    return () => { cancelled = true; };
  }, [selectedProjectId]);

  const loadingJobs = selectedProjectId !== null && jobsLoadedFor !== selectedProjectId;
  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <>
      <Nav />
      <div className="min-h-[calc(100vh-65px)] bg-[#fafafa] text-zinc-900 flex">
        {/* Sidebar */}
        <div className="w-64 shrink-0 border-r border-zinc-200/70 bg-white p-6">
          <h2 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wide mb-4">Projects</h2>

          {loadingProjects ? (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-9 rounded-lg bg-zinc-100 animate-pulse" />
              ))}
            </div>
          ) : projects.length === 0 ? (
            <p className="text-sm text-zinc-400">No projects yet.</p>
          ) : (
            <div className="space-y-0.5">
              {projects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedProjectId(p.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    selectedProjectId === p.id ? "bg-zinc-100 text-zinc-900 font-medium" : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800"
                  }`}
                >
                  {p.name}
                </button>
              ))}
            </div>
          )}

          <div className="mt-8 pt-6 border-t border-zinc-200/70">
            <Link href="/" className="text-sm font-medium text-indigo-600 hover:text-indigo-700 transition-colors">
              + New Upload
            </Link>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 p-10">
          <h1 className="text-2xl font-semibold tracking-tight mb-1">Integration Jobs</h1>
          {selectedProject && (
            <p className="text-sm text-zinc-500 mb-8">{selectedProject.name}</p>
          )}
          {!selectedProject && !loadingProjects && <div className="mb-8" />}

          {loadingProjects || loadingJobs ? (
            <div className="grid gap-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-24 rounded-xl bg-white border border-zinc-200/70 animate-pulse" />
              ))}
            </div>
          ) : projects.length === 0 ? (
            <div className="bg-white border border-dashed border-zinc-300 rounded-2xl p-12 text-center">
              <p className="text-zinc-500 mb-4">No projects yet — upload an OpenAPI spec to get started.</p>
              <Link href="/" className="inline-block px-5 py-2.5 bg-zinc-900 hover:bg-zinc-800 active:scale-[0.99] text-white rounded-xl text-sm font-medium transition-all duration-150">
                Upload a Spec
              </Link>
            </div>
          ) : jobs.length === 0 ? (
            <div className="bg-white border border-dashed border-zinc-300 rounded-2xl p-12 text-center">
              <p className="text-zinc-500">No jobs found for this project yet.</p>
            </div>
          ) : (
            <div className="grid gap-3">
              {jobs.map((job) => {
                const duration = formatDuration(job.created_at, job.completed_at);
                return (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className="bg-white border border-zinc-200/70 rounded-xl p-6 flex justify-between items-center shadow-[0_1px_2px_rgba(0,0,0,0.03)] hover:shadow-[0_1px_2px_rgba(0,0,0,0.03),0_4px_16px_-8px_rgba(0,0,0,0.08)] hover:border-zinc-300/70 transition-all group"
                  >
                    <div>
                      <p className="font-mono text-xs text-zinc-400 mb-1.5">{job.id}</p>
                      <div className="flex items-center gap-3">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wide ${STATUS_STYLE[job.status] || "bg-zinc-500/10 text-zinc-700"}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[job.status] || "bg-zinc-400"}`} />
                          {job.status}
                        </span>
                        <span className="text-sm text-zinc-400">{new Date(job.created_at).toLocaleString()}</span>
                        {duration && <span className="text-sm text-zinc-400 font-mono">· {duration}</span>}
                      </div>
                    </div>
                    <span className="text-sm font-medium text-zinc-400 group-hover:text-zinc-900 transition-colors shrink-0 flex items-center gap-1.5">
                      View Timeline
                      <span className="transition-transform group-hover:translate-x-0.5">→</span>
                    </span>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
