import { getApiUrl } from "@/lib/api";
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(getApiUrl("/upload"), {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to upload spec.");
      
      // Navigate to the job timeline view
      router.push(`/jobs/${data.job_id}`);
    } catch (err: any) {
      console.error("Upload failed", err);
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-900 py-20 px-4">
      <div className="max-w-4xl mx-auto space-y-12">
        <div className="text-center space-y-4">
          <h1 className="text-5xl font-extrabold tracking-tight">APIForge AI</h1>
          <p className="text-xl text-zinc-600 max-w-2xl mx-auto leading-relaxed">
            Upload your OpenAPI spec. Watch our agents autonomously map dependencies, test endpoints, fix bugs, and generate production-ready SDKs.
          </p>
        </div>

          <div className="max-w-md mx-auto bg-white p-8 rounded-2xl shadow-sm border border-zinc-200">
            <form onSubmit={handleUpload} className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-zinc-800 mb-2">OpenAPI Spec (JSON/YAML)</label>
                <input
                  type="file"
                  accept=".json,.yaml,.yml"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="block w-full text-sm text-zinc-500
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-full file:border-0
                    file:text-sm file:font-semibold
                    file:bg-black file:text-white
                    hover:file:bg-zinc-800 transition-colors cursor-pointer"
                />
              </div>
              <button
                type="submit"
                disabled={!file || isUploading}
                className="w-full py-3 px-4 bg-black hover:bg-zinc-800 text-white font-medium rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-lg"
              >
                {isUploading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    Initializing Agent...
                  </span>
                ) : "Forge SDK"}
              </button>
              {error && (
                <div className="p-4 mt-4 bg-red-50 text-red-600 rounded-lg text-sm border border-red-100 font-medium">
                  {error}
                </div>
              )}
            </form>
          </div>
      </div>
    </main>
  );
}
