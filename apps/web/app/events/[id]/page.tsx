"use client";

import Link from "next/link";
import { ArrowLeft, Camera, CheckCircle2, CircleAlert, Play, RefreshCw, ShieldCheck, Video } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { EventRecord, Review } from "@/lib/types";

function date(value: string) { return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "medium", timeZone: "UTC" }).format(new Date(value)) + " UTC"; }
export default function EventDetailPage() {
  const params = useParams<{ id: string }>();
  const eventId = params.id;
  const { token, user } = useAuth();
  const [event, setEvent] = useState<EventRecord | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [decision, setDecision] = useState("needs_follow_up");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [mediaTab, setMediaTab] = useState<"snapshot" | "video">("snapshot");
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const load = useCallback(async () => {
    if (!token || !eventId) return;
    setBusy(true); setError("");
    try {
      const record = await api.event(token, eventId);
      setEvent(record);
      setReviews(await api.reviews(token, eventId));
    } catch (e) { setError((e as ApiError).message); }
    finally { setBusy(false); }
  }, [token, eventId]);
  useEffect(() => { void load(); }, [load]);

  async function submitReview(e: FormEvent) {
    e.preventDefault(); if (!token) return;
    setBusy(true); setError(""); setSuccess("");
    try { await api.review(token, eventId, decision, note); setNote(""); setSuccess("Review decision saved."); await load(); }
    catch (err) { setError((err as ApiError).message); }
    finally { setBusy(false); }
  }

  const frameTime = typeof event?.details?.frame_timestamp_seconds === "number" ? event.details.frame_timestamp_seconds : null;
  const hasSnapshot = Boolean(event?.details?.snapshot_ref);
  const hasVideo = Boolean(event?.details?.job_id || event?.source_id?.startsWith("video-job:"));

  function jumpToMotion() {
    if (videoRef.current && frameTime !== null) {
      videoRef.current.currentTime = Math.max(0, frameTime - 1.5);
      void videoRef.current.play();
    }
  }

  return <AppShell>
    <div className="page-heading"><div><span className="eyebrow">Evidence record / review</span><h1>Event details.</h1><p>Inspect provenance, visual keyframe evidence and record an auditable human review decision.</p></div><Link href="/events" className="button"><ArrowLeft size={14} /> Back to events</Link></div>
    {error && <div className="banner error"><CircleAlert size={16} />{error}</div>}{success && <div className="banner success"><CheckCircle2 size={16} />{success}</div>}
    {!event && !error ? <div className="card empty-state"><span className="spinner" /> Loading event…</div> : event && <div className="event-detail-layout">
      <div style={{ display: "grid", gap: 16 }}>
        {(hasSnapshot || hasVideo) && <div className="card"><div className="card-head"><div><h2>Visual evidence</h2><p>{hasSnapshot ? "Motion keyframe & source footage" : "Source recording footage"}</p></div>
          <div className="login-mode" style={{ margin: 0, padding: 2 }}>
            {hasSnapshot && <button className={mediaTab === "snapshot" ? "active" : ""} onClick={() => setMediaTab("snapshot")}><Camera size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />Keyframe</button>}
            {hasVideo && <button className={mediaTab === "video" ? "active" : ""} onClick={() => setMediaTab("video")}><Video size={13} style={{ verticalAlign: "-2px", marginRight: 4 }} />Video player</button>}
          </div></div>
          <div className="card-body">
            {mediaTab === "snapshot" && hasSnapshot && <div className="media-box">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img className="snapshot-img" src={`${api.eventSnapshotUrl(eventId)}?token=${encodeURIComponent(token || "")}`} alt="Motion snapshot" />
              <div className="media-actions"><span>Captured at {frameTime !== null ? `${frameTime.toFixed(2)}s` : "event time"}</span>{hasVideo && <button className="button small" onClick={() => { setMediaTab("video"); setTimeout(jumpToMotion, 300); }}><Play size={11} /> Play from this moment</button>}</div>
            </div>}
            {mediaTab === "video" && hasVideo && <div className="media-box">
              <video ref={videoRef} controls preload="metadata" className="video-player" src={`${api.eventVideoUrl(eventId)}?token=${encodeURIComponent(token || "")}`} />
              <div className="media-actions"><span>{frameTime !== null ? `Observed motion at ${frameTime.toFixed(2)}s` : "Recorded video source"}</span>{frameTime !== null && <button className="button small primary" onClick={jumpToMotion}><Play size={11} /> Seek to motion ({frameTime.toFixed(1)}s)</button>}</div>
            </div>}
          </div>
        </div>}
        <div className="card"><div className="card-head"><div><div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}><h2>{event.event_type.replaceAll("_", " ")}</h2>{Boolean(event.details?.primary_label) && <span className={`badge ${String(event.details?.primary_label).toLowerCase() === "person" ? "person" : "vehicle"}`}>AI: {String(event.details?.primary_label).toUpperCase()}</span>}</div><p className="mono">{event.id}</p></div><span className={`status ${event.review_status}`}>{event.review_status}</span></div><div className="card-body"><div className="detail-pairs"><div className="detail-pair"><span>Source ID</span><strong>{event.source_id}</strong></div><div className="detail-pair"><span>Site</span><strong>{event.site_id ?? "Not assigned"}</strong></div><div className="detail-pair"><span>Observed at</span><strong>{date(event.observed_at)}</strong></div><div className="detail-pair"><span>Received at</span><strong>{date(event.received_at)}</strong></div><div className="detail-pair"><span>Score</span><strong>{event.score === null ? "Not scored" : `${(event.score * 100).toFixed(2)}%`}</strong></div><div className="detail-pair"><span>Score kind</span><strong>{event.score_kind ?? "—"}</strong></div><div className="detail-pair"><span>Model version</span><strong>{event.model_version ?? "Manual / external"}</strong></div><div className="detail-pair"><span>Evidence reference</span><strong>{event.evidence_ref ?? "None"}</strong></div>{Boolean(event.details?.primary_label) && <div className="detail-pair"><span>Target object</span><strong style={{ color: "#b91c1c" }}>{String(event.details?.primary_label).toUpperCase()}</strong></div>}{Array.isArray(event.details?.bounding_boxes) && <div className="detail-pair"><span>Bounding boxes</span><strong>{event.details.bounding_boxes.length} bounding box(es)</strong></div>}</div><h3 style={{ marginTop: 23 }}>Event metadata</h3><pre className="json-block">{JSON.stringify(event.details, null, 2)}</pre><div className="banner" style={{ marginTop: 12, marginBottom: 0 }}><ShieldCheck size={15} /><span>Human review is required. A motion score is not a semantic classifier or a threat probability.</span></div></div></div>
      </div>
      <div style={{ display: "grid", gap: 15 }}><div className="card"><div className="card-head"><div><h2>Review decision</h2><p>As {user?.role}, record your interpretation.</p></div></div><div className="card-body"><form className="form-stack" onSubmit={submitReview}><div className="field"><label htmlFor="decision">Decision</label><select id="decision" className="select" value={decision} onChange={e => setDecision(e.target.value)}><option value="confirmed">Confirmed observation</option><option value="false_positive">False positive</option><option value="not_actionable">Not actionable</option><option value="needs_follow_up">Needs follow-up</option></select></div><div className="field"><label htmlFor="note">Review note</label><textarea id="note" className="textarea" rows={4} maxLength={4000} placeholder="What did you verify? What remains uncertain?" value={note} onChange={e => setNote(e.target.value)} /></div><button className="button primary full" disabled={busy || user?.role === "viewer" || user?.role === "auditor"}>{busy ? "Saving…" : "Save review"}</button></form></div></div>
        <div className="card"><div className="card-head"><div><h2>Review history</h2><p>Previously recorded decisions</p></div><button className="button small" onClick={() => void load()} disabled={busy}><RefreshCw size={12} /> Refresh</button></div><div className="card-body">{reviews.length === 0 ? <div className="empty-state" style={{ padding: "22px 10px" }}><p>No reviews recorded yet.</p></div> : reviews.map(review => <div key={review.id} className="job-row"><div className="job-icon"><ShieldCheck size={15} /></div><div className="job-main"><strong>{review.decision.replaceAll("_", " ")}</strong><small>{date(review.created_at)}{review.note ? ` · ${review.note}` : ""}</small></div></div>)}</div></div>
      </div>
    </div>}
  </AppShell>;
}
