"use client";

import { AlertCircle, CheckCircle2, FileVideo, Film, RefreshCw, UploadCloud } from "lucide-react";
import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Job, Site } from "@/lib/types";

function date(value: string) { return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
export default function JobsPage() {
  const { token, user } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [siteId, setSiteId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const load = useCallback(async () => {
    if (!token) return;
    try { const [jobList, siteList] = await Promise.all([api.jobs(token), api.sites(token)]); setJobs(jobList); setSites(siteList); }
    catch (e) { setError((e as ApiError).message); }
  }, [token]);
  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const hasActiveJob = jobs.some(j => j.status === "queued" || j.status === "running");
    if (!hasActiveJob || !token) return;
    const timer = setInterval(() => { void load(); }, 3000);
    return () => clearInterval(timer);
  }, [jobs, token, load]);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!token || !file) return;
    setBusy(true); setError(""); setSuccess("");
    try { await api.enqueueVideo(token, file, siteId || undefined); setFile(null); setSuccess("Video queued. Start the backend worker to process queued jobs."); await load(); const input = document.getElementById("video-file") as HTMLInputElement | null; if (input) input.value = ""; }
    catch (e) { setError((e as ApiError).message); }
    finally { setBusy(false); }
  }
  async function retry(job: Job) {
    if (!token) return; setError("");
    try { await api.retryJob(token, job.id); setSuccess("Job requeued."); await load(); }
    catch (e) { setError((e as ApiError).message); }
  }
  function onFileChange(event: ChangeEvent<HTMLInputElement>) { setFile(event.target.files?.[0] ?? null); }
  return <AppShell>
    <div className="page-heading"><div><span className="eyebrow">Local media processing / 04</span><h1>Video analysis.</h1><p>Submit authorized recorded footage for generic motion observations. Analysis does not identify objects or assess threats.</p></div><button className="button" onClick={() => void load()}><RefreshCw size={14} /> Refresh jobs</button></div>
    {error && <div className="banner error"><AlertCircle size={16} />{error}</div>}{success && <div className="banner success"><CheckCircle2 size={16} />{success}</div>}
    <div className="banner warning"><AlertCircle size={16} /><span><strong>Privacy &amp; safety:</strong> upload only footage you are authorized to process. The backend stores the source media locally. Outputs are generic scene-motion observations and must not be treated as a threat classification.</span></div>
    <div className="overview-grid">
      <div className="card"><div className="card-head"><div><h2>Submit a recording</h2><p>Accepted: MP4, AVI, MOV, MKV · server-side size limit applies</p></div><UploadCloud size={18} color="#8b5a3c" /></div><div className="card-body"><form className="form-stack" onSubmit={submit}><div className="field"><label htmlFor="video-file">Video file</label><input id="video-file" className="input" type="file" accept=".mp4,.avi,.mov,.mkv,video/*" onChange={onFileChange} required /><span className="field-hint">The extension and file content are validated by the backend. Do not upload classified, restricted or unauthorized footage.</span></div><div className="field"><label htmlFor="job-site">Site (optional)</label><select id="job-site" className="select" value={siteId} onChange={e => setSiteId(e.target.value)}><option value="">No site association</option>{sites.map(site => <option key={site.id} value={site.id}>{site.name}</option>)}</select></div>{file && <div className="banner"><Film size={15} /><span><strong>{file.name}</strong><br />{(file.size / (1024 * 1024)).toFixed(2)} MB</span></div>}<button className="button primary full" disabled={busy || !file || user?.role === "viewer" || user?.role === "auditor"}>{busy ? "Uploading…" : "Queue motion scan"}<UploadCloud size={14} /></button></form><p className="field-hint" style={{ marginTop: 12 }}>The API saves an upload and queues a job. Keep the worker process running to execute analysis.</p></div></div>
      <div className="card"><div className="card-head"><div><h2>Processing model</h2><p>Generic motion scan</p></div><FileVideo size={18} color="#8b5a3c" /></div><div className="card-body"><div className="job-row"><div className="job-icon"><Film size={17} /></div><div className="job-main"><strong>Frame sampling</strong><small>Sampled frames, resized for bounded memory use</small></div></div><div className="job-row"><div className="job-icon"><ActivityIcon /></div><div className="job-main"><strong>Background subtraction</strong><small>OpenCV MOG2 estimates moving foreground pixels</small></div></div><div className="job-row"><div className="job-icon"><CheckCircle2 size={17} /></div><div className="job-main"><strong>Human review</strong><small>Each generated event remains unreviewed until actioned</small></div></div><div className="banner" style={{ marginTop: 14, marginBottom: 0 }}><AlertCircle size={15} /><span>Foreground ratio is not a probability that an object or threat exists. Lighting changes can generate false positives.</span></div></div></div>
    </div>
    <div className="card" style={{ marginTop: 16 }}><div className="card-head"><div><h2>Recent processing jobs</h2><p>{jobs.length} jobs in this workspace</p></div><button className="button small" onClick={() => void load()}><RefreshCw size={12} /> Refresh</button></div><div className="card-body">{jobs.length === 0 ? <div className="empty-state"><FileVideo size={24} /><strong>No analysis jobs</strong><p>Submit an authorized video to create the first job.</p></div> : jobs.map(job => <div className="job-row" key={job.id}><div className="job-icon"><FileVideo size={17} /></div><div className="job-main"><strong>{job.source_name}</strong><small>{date(job.created_at)} · {job.attempts} attempt(s) · {job.id.slice(0, 8)}</small>{job.error_message && <small style={{ color: "#a44840" }}>{job.error_message}</small>}{job.status === "succeeded" && <small>{String(job.result_summary.motion_events_created ?? 0)} motion events created</small>}</div><span className={`status ${job.status}`}>{job.status}</span>{job.status === "failed" && <button className="button small" onClick={() => void retry(job)}>Retry</button>}</div>)}</div></div>
  </AppShell>;
}

function ActivityIcon() { return <AlertCircle size={17} />; }
