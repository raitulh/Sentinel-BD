"use client";

import Link from "next/link";
import { Activity, ArrowDownRight, ArrowRight, Camera, Clock3, FileVideo, Radar, RefreshCw, ShieldAlert, ShieldCheck, Workflow } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Device, EventRecord, Job } from "@/lib/types";

function formatDate(value: string) { return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
function Badge({ value }: { value: string }) { return <span className={`status ${value}`}>{value.replaceAll("_", " ")}</span>; }

export default function HomePage() {
  const { token, user } = useAuth();
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [devices, setDevices] = useState<Device[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true); setError("");
    try {
      const [eventResult, deviceResult, jobResult] = await Promise.all([api.events(token, "limit=8"), api.devices(token), api.jobs(token)]);
      setEvents(eventResult.items); setTotalEvents(eventResult.total); setDevices(deviceResult); setJobs(jobResult);
    } catch (e) { setError((e as ApiError).message); }
    finally { setLoading(false); }
  }, [token]);
  useEffect(() => { void load(); }, [load]);

  const unreviewed = events.filter(e => e.review_status === "unreviewed").length;
  const online = devices.filter(d => d.status === "active").length;
  const processing = jobs.filter(j => j.status === "queued" || j.status === "running").length;

  return <AppShell>
    <div className="page-heading"><div><span className="eyebrow">Operations overview / 01</span><h1>Good to see you{user?.email ? `, ${user.email.split("@")[0]}` : ""}.</h1><p>A considered view of sensor activity, review workload and the health of your local deployment.</p></div><button className="button" onClick={() => void load()} disabled={loading}><RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh data</button></div>
    {error && <div className="banner error"><ShieldAlert size={16} /><span>{error}</span></div>}
    <div className="banner"><ShieldCheck size={16} /><span><strong>Interpretation boundary:</strong> video analysis reports generic scene motion only. Events require human review and are not threat assessments.</span></div>
    <section className="stats-grid" aria-label="System summary">
      <div className="card stat-card"><div className="stat-top"><span>Total recorded events</span><span className="stat-icon"><Activity size={15} /></span></div><div className="stat-number">{totalEvents.toLocaleString()}</div><div className="stat-caption">All events in this workspace</div></div>
      <div className="card stat-card"><div className="stat-top"><span>Unreviewed in latest page</span><span className="stat-icon"><Radar size={15} /></span></div><div className="stat-number">{unreviewed}</div><div className="stat-caption">Requires an operator decision</div></div>
      <div className="card stat-card"><div className="stat-top"><span>Active devices</span><span className="stat-icon"><Camera size={15} /></span></div><div className="stat-number">{online}</div><div className="stat-caption">Of {devices.length} registered devices</div></div>
      <div className="card stat-card"><div className="stat-top"><span>Jobs in progress</span><span className="stat-icon"><Workflow size={15} /></span></div><div className="stat-number">{processing}</div><div className="stat-caption">Queued or running analysis</div></div>
    </section>
    <section className="overview-grid">
      <div className="card"><div className="card-head"><div><h2>Recent events</h2><p>Newest recorded observations</p></div><Link className="text-link" href="/events">View all <ArrowRight size={12} style={{ verticalAlign: "-2px" }} /></Link></div>
        {loading ? <div className="empty-state"><span className="spinner" /></div> : events.length === 0 ? <div className="empty-state"><Radar size={25} /><strong>No events recorded yet</strong><p>Run a video motion scan or post an event from the API to see it here.</p><Link className="button small" href="/jobs">Analyze a video</Link></div> : <div className="table-wrap"><table><thead><tr><th>Observation</th><th>Source</th><th>Review</th><th>Observed</th></tr></thead><tbody>{events.slice(0, 8).map(event => <tr key={event.id}><td><Link href={`/events/${event.id}`} className="primary-cell">{event.event_type.replaceAll("_", " ")}</Link><span className="secondary-cell mono">{event.id.slice(0, 8)}</span></td><td>{event.source_id}</td><td><Badge value={event.review_status} /></td><td>{formatDate(event.observed_at)}</td></tr>)}</tbody></table></div>}
      </div>
      <div className="card"><div className="card-head"><div><h2>System snapshot</h2><p>Current workspace inventory</p></div><Activity size={17} color="#8b5a3c" /></div><div className="card-body">
        <div className="job-row"><div className="job-icon"><Camera size={17} /></div><div className="job-main"><strong>Registered devices</strong><small>Including cameras, sensors & simulators</small><div className="progress-track"><div className="progress-bar" style={{ width: `${devices.length ? Math.max(8, online / devices.length * 100) : 0}%` }} /></div></div><strong>{devices.length}</strong></div>
        <div className="job-row"><div className="job-icon"><FileVideo size={17} /></div><div className="job-main"><strong>Video analysis jobs</strong><small>Completed, queued and failed jobs</small><div className="progress-track"><div className="progress-bar" style={{ width: `${jobs.length ? Math.max(8, jobs.filter(j => j.status === "succeeded").length / jobs.length * 100) : 0}%` }} /></div></div><strong>{jobs.length}</strong></div>
        <div className="job-row"><div className="job-icon"><Clock3 size={17} /></div><div className="job-main"><strong>Latest analysis</strong><small>{jobs[0] ? formatDate(jobs[0].created_at) : "No analysis submitted"}</small></div>{jobs[0] && <Badge value={jobs[0].status} />}</div>
        <div style={{ paddingTop: 15 }}><Link className="button full" href="/devices">Manage sensors &amp; sites <ArrowRight size={14} /></Link></div>
      </div></div>
    </section>
    <div style={{ display: "flex", justifyContent: "flex-end", gap: 5, color: "#9b8f80", fontSize: 10, marginTop: 15 }}><ArrowDownRight size={13} /> A local workspace is only as reliable as its test data and operational procedures.</div>
  </AppShell>;
}
