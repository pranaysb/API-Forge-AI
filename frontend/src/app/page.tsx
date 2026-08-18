"use client";
import { getApiUrl } from "@/lib/api";
import { PIPELINE_NODES } from "@/lib/pipeline";
import Nav from "@/components/Nav";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";

interface SpecPreview {
  valid: boolean;
  title?: string;
  version?: string;
  endpointCount?: number;
  methods?: { method: string; path: string }[];
  warning?: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// Best-effort client-side preview so users get instant feedback instead of a
// round trip. JSON specs get a full parse; YAML specs just get file-shape
// checks since we don't ship a YAML parser to the client. The backend is
// always the source of truth and re-validates on upload.
function previewSpec(filename: string, text: string): SpecPreview {
  const isJson = filename.toLowerCase().endsWith(".json") || text.trim().startsWith("{");

  if (!isJson) {
    const looksLikeSpec = /^\s*(openapi|swagger)\s*:/m.test(text) && /^\s*paths\s*:/m.test(text);
    if (!looksLikeSpec) {
      return { valid: false, warning: "This doesn't look like an OpenAPI/Swagger YAML file (missing 'openapi:' or 'paths:')." };
    }
    return { valid: true, warning: "YAML detected — full validation happens after upload." };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { valid: false, warning: "This file is not valid JSON — it will be rejected on upload." };
  }

  if (typeof parsed !== "object" || parsed === null) {
    return { valid: false, warning: "File does not contain a JSON object." };
  }
  const spec = parsed as Record<string, unknown>;
  if (!("openapi" in spec) && !("swagger" in spec)) {
    return { valid: false, warning: "Missing 'openapi' or 'swagger' version field — not a valid spec." };
  }
  const paths = spec.paths as Record<string, Record<string, unknown>> | undefined;
  if (!paths || Object.keys(paths).length === 0) {
    return { valid: false, warning: "Spec has no 'paths' — there's nothing to generate an SDK from." };
  }

  const methods: { method: string; path: string }[] = [];
  const HTTP_METHODS = ["get", "post", "put", "delete", "patch", "options", "head"];
  for (const [path, item] of Object.entries(paths)) {
    if (!item || typeof item !== "object") continue;
    for (const m of Object.keys(item)) {
      if (HTTP_METHODS.includes(m.toLowerCase())) {
        methods.push({ method: m.toUpperCase(), path });
      }
    }
  }

  if (methods.length === 0) {
    return { valid: false, warning: "Spec has 'paths' but no GET/POST/PUT/DELETE/etc. operations were found under any of them." };
  }

  const info = spec.info as Record<string, unknown> | undefined;
  return {
    valid: true,
    title: (info?.title as string) || filename,
    version: (info?.version as string) || undefined,
    endpointCount: methods.length,
    methods,
  };
}

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

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-blue-100 text-blue-700",
  POST: "bg-green-100 text-green-700",
  PUT: "bg-amber-100 text-amber-700",
  PATCH: "bg-orange-100 text-orange-700",
  DELETE: "bg-red-100 text-red-700",
  OPTIONS: "bg-zinc-100 text-zinc-700",
  HEAD: "bg-zinc-100 text-zinc-700",
};

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<SpecPreview | null>(null);
  const [projectName, setProjectName] = useState("Demo Project");
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const handleFile = useCallback((f: File | null) => {
    setError(null);
    setFile(f);
    setPreview(null);
    if (!f) return;

    if (f.size > 10 * 1024 * 1024) {
      setPreview({ valid: false, warning: `File is ${formatBytes(f.size)} — exceeds the 10MB upload limit.` });
      return;
    }

    f.text()
      .then((text) => setPreview(previewSpec(f.name, text)))
      .catch(() => setPreview({ valid: false, warning: "Could not read file as text." }));
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsUploading(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("project_name", projectName || "Demo Project");

    try {
      const res = await fetch(getApiUrl("/upload"), {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        const hint =
          res.status === 413 ? " (file too large — 10MB limit)" :
          res.status === 422 ? " (not a recognizable OpenAPI spec)" :
          res.status === 429 ? " (too many uploads — wait a minute and retry)" :
          res.status === 400 ? " (couldn't parse the file)" : "";
        throw new Error((data.detail || "Failed to upload spec.") + hint);
      }

      router.push(`/jobs/${data.job_id}`);
    } catch (err: unknown) {
      console.error("Upload failed", err);
      setError((err as Error).message);
    } finally {
      setIsUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  return (
    <>
      <Nav />
      <main className="min-h-screen bg-zinc-50 text-zinc-900 py-16 px-4">
        <div className="max-w-4xl mx-auto space-y-16">
          <div className="text-center space-y-4">
            <h1 className="text-5xl font-extrabold tracking-tight">APIForge AI</h1>
            <p className="text-xl text-zinc-600 max-w-2xl mx-auto leading-relaxed">
              Upload your OpenAPI spec. Watch autonomous agents map dependencies, test every endpoint,
              self-heal bugs, and generate a production-ready Python SDK — live, in your browser.
            </p>
          </div>

          {/* Upload card */}
          <div className="max-w-xl mx-auto bg-white p-8 rounded-2xl shadow-sm border border-zinc-200">
            <form onSubmit={handleUpload} className="space-y-5">
              <div>
                <label className="block text-sm font-semibold text-zinc-800 mb-2">Project name</label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="Demo Project"
                  className="w-full px-3 py-2 border border-zinc-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black/10 focus:border-zinc-400"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-zinc-800 mb-2">OpenAPI Spec (JSON/YAML)</label>
                <div
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={onDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-colors ${
                    isDragging ? "border-black bg-zinc-50" : "border-zinc-200 hover:border-zinc-300"
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".json,.yaml,.yml"
                    onChange={(e) => handleFile(e.target.files?.[0] || null)}
                    className="hidden"
                  />
                  {!file ? (
                    <>
                      <p className="text-sm font-medium text-zinc-700">Drop your spec here, or click to browse</p>
                      <p className="text-xs text-zinc-400 mt-1">.json, .yaml, .yml — up to 10MB</p>
                    </>
                  ) : (
                    <div className="text-left flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-zinc-800 truncate">{file.name}</p>
                        <p className="text-xs text-zinc-400">{formatBytes(file.size)}</p>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); handleFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}
                        className="text-xs font-semibold text-zinc-400 hover:text-red-600 shrink-0"
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </div>

                {/* Client-side preview / validation feedback */}
                {preview && (
                  <div className={`mt-3 rounded-lg p-3 text-xs border ${
                    preview.valid ? "bg-green-50 border-green-100 text-green-800" : "bg-red-50 border-red-100 text-red-700"
                  }`}>
                    {preview.valid ? (
                      <div className="space-y-1.5">
                        <p className="font-semibold">
                          ✓ {preview.title || "Spec detected"}{preview.version ? ` (v${preview.version})` : ""}
                          {preview.endpointCount !== undefined && ` — ${preview.endpointCount} endpoint${preview.endpointCount === 1 ? "" : "s"} found`}
                        </p>
                        {preview.warning && <p className="text-amber-700">{preview.warning}</p>}
                        {preview.methods && preview.methods.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {preview.methods.slice(0, 12).map((m, i) => (
                              <span key={i} className={`px-1.5 py-0.5 rounded font-mono font-semibold ${METHOD_COLORS[m.method] || "bg-zinc-100 text-zinc-700"}`}>
                                {m.method} {m.path}
                              </span>
                            ))}
                            {preview.methods.length > 12 && (
                              <span className="px-1.5 py-0.5 text-zinc-500">+{preview.methods.length - 12} more</span>
                            )}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="font-semibold">✗ {preview.warning}</p>
                    )}
                  </div>
                )}
              </div>

              <button
                type="submit"
                disabled={!file || isUploading || preview?.valid === false}
                className="w-full py-3 px-4 bg-black hover:bg-zinc-800 text-white font-medium rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-lg"
              >
                {isUploading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    Uploading &amp; starting agents...
                  </span>
                ) : "Forge SDK"}
              </button>
              {error && (
                <div className="p-4 bg-red-50 text-red-600 rounded-lg text-sm border border-red-100 font-medium">
                  {error}
                </div>
              )}
            </form>
          </div>

          {/* How it works */}
          <div>
            <h2 className="text-center text-2xl font-bold mb-2">How it works</h2>
            <p className="text-center text-zinc-500 text-sm mb-8 max-w-xl mx-auto">
              Every endpoint moves through this pipeline independently. Failures loop back to the Diagnoser,
              which patches the SDK in memory and retries — up to 5 attempts — before moving on.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {PIPELINE_NODES.map((node, i) => (
                <div key={node.key} className="bg-white border border-zinc-200 rounded-xl p-4 relative">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`w-2.5 h-2.5 rounded-full ${NODE_DOT_COLOR[node.key] || "bg-zinc-500"}`} />
                    <span className="text-xs font-bold text-zinc-400">{i + 1}</span>
                    <span className="text-sm font-bold">{node.label}</span>
                  </div>
                  <p className="text-xs text-zinc-500 leading-relaxed">{node.short}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
