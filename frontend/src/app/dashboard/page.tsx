"use client";

import { useEffect, useState } from "react";
import { getApiUrl } from "@/lib/api";
import Link from "next/link";

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

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    fetch(getApiUrl("/dashboard/projects"))
      .then((res) => res.json())
      .then((data) => {
        setProjects(data);
        if (data.length > 0) setSelectedProjectId(data[0].id);
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    fetch(getApiUrl(`/dashboard/projects/${selectedProjectId}/jobs`))
      .then((res) => res.json())
      .then(setJobs)
      .catch(console.error);
  }, [selectedProjectId]);

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 flex">
      {/* Sidebar */}
      <div className="w-64 border-r border-zinc-200 bg-white p-6">
        <h2 className="text-xl font-bold mb-6">Projects</h2>
        <div className="space-y-2">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelectedProjectId(p.id)}
              className={`w-full text-left px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedProjectId === p.id ? "bg-black text-white" : "hover:bg-zinc-100"
              }`}
            >
              {p.name}
            </button>
          ))}
        </div>
        <div className="mt-8">
          <Link href="/" className="text-sm font-semibold text-blue-600 hover:underline">
            + New Upload
          </Link>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-10">
        <h1 className="text-3xl font-extrabold mb-8">Integration Jobs</h1>
        <div className="grid gap-4">
          {jobs.map((job) => (
            <div key={job.id} className="bg-white border border-zinc-200 rounded-xl p-6 flex justify-between items-center shadow-sm">
              <div>
                <p className="font-mono text-sm text-zinc-500 mb-1">Job ID: {job.id}</p>
                <div className="flex items-center gap-3">
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase ${
                    job.status === "SUCCESS" ? "bg-green-100 text-green-700" :
                    job.status === "FAILED" ? "bg-red-100 text-red-700" :
                    job.status === "RUNNING" ? "bg-blue-100 text-blue-700" :
                    "bg-zinc-100 text-zinc-700"
                  }`}>
                    {job.status}
                  </span>
                  <span className="text-sm text-zinc-400">{new Date(job.created_at).toLocaleString()}</span>
                </div>
              </div>
              <Link
                href={`/jobs/${job.id}`}
                className="px-4 py-2 bg-zinc-100 hover:bg-zinc-200 rounded-lg text-sm font-semibold transition-colors"
              >
                View Timeline →
              </Link>
            </div>
          ))}
          {jobs.length === 0 && (
            <p className="text-zinc-500 text-sm">No jobs found for this project.</p>
          )}
        </div>
      </div>
    </div>
  );
}
