"use client";

import Link from "next/link";
import { Camera, ChevronLeft, ChevronRight, Filter, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { EventRecord } from "@/lib/types";

function shortDate(value: string) { return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }

const PAGE_SIZE = 25;

export default function EventsPage() {
  const { token } = useAuth();
  const [items, setItems] = useState<EventRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true); setError("");
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
    if (reviewStatus) params.set("review_status", reviewStatus);
    try {
      const response = await api.events(token, params.toString());
      setItems(response.items);
      setTotal(response.total);
    } catch (e) { setError((e as ApiError).message); }
    finally { setBusy(false); }
  }, [token, reviewStatus, page]);

  useEffect(() => { void load(); }, [load]);

  const filtered = items.filter(item => `${item.event_type} ${item.source_id} ${item.id}`.toLowerCase().includes(search.toLowerCase()));
  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;

  return <AppShell>
    <div className="page-heading"><div><span className="eyebrow">Event operations / 02</span><h1>Event review.</h1><p>Inspect observed events, supporting metadata, visual keyframes and review status.</p></div><button className="button" onClick={() => void load()} disabled={busy}><RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Refresh</button></div>
    <div className="banner"><ShieldAlert size={16} /><span>Model output is supporting evidence, not a confirmed identity or threat verdict. Review decisions remain human-entered and auditable.</span></div>
    {error && <div className="banner error">{error}</div>}
    <div className="toolbar"><div style={{ position: "relative" }}><Search size={14} style={{ position: "absolute", left: 11, top: 12, color: "#9d907f" }} /><input aria-label="Search events" className="input" style={{ paddingLeft: 32 }} placeholder="Search type, source or event ID…" value={search} onChange={e => setSearch(e.target.value)} /></div><Filter size={14} color="#8c7d6a" /><select aria-label="Review status" className="select" value={reviewStatus} onChange={e => { setReviewStatus(e.target.value); setPage(0); }}><option value="">All review states</option><option value="unreviewed">Unreviewed</option><option value="reviewed">Reviewed</option></select><span style={{ marginLeft: "auto", fontSize: 10, color: "#928678" }}>Page {page + 1} of {totalPages} · {total} total</span></div>
    <div className="card"><div className="table-wrap"><table><thead><tr><th>Event</th><th>Source</th><th>Observed</th><th>Score</th><th>Review status</th><th>Evidence</th><th></th></tr></thead><tbody>{filtered.map(event => {
      const isAi = Boolean(event.details?.semantic_classification);
      const label = (event.details?.primary_label as string | undefined)?.toLowerCase();
      const badgeClass = label === "person" ? "person" : (label && ["car", "truck", "bus", "motorcycle"].some(v => label.includes(v))) ? "vehicle" : (label && ["boat", "vessel", "airplane"].some(v => label.includes(v))) ? "vessel" : isAi ? "ai-verified" : "";

      return <tr key={event.id}>
        <td>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span className="primary-cell">{event.event_type.replaceAll("_", " ")}</span>
            {label && <span className={`badge ${badgeClass}`}>{label.toUpperCase()}</span>}
          </div>
          <span className="secondary-cell mono">{event.id}</span>
        </td>
        <td>{event.source_id}</td>
        <td>{shortDate(event.observed_at)}</td>
        <td>
          {event.score === null ? "—" : `${(event.score * 100).toFixed(1)}%`}
          <span className="secondary-cell">{label ? `AI: ${label}` : (event.score_kind ?? "not scored")}</span>
        </td>
        <td><span className={`status ${event.review_status}`}>{event.review_status}</span></td>
        <td>{event.details?.snapshot_ref ? <span className="badge" style={{ background: "#efe4d5", color: "#614732" }}><Camera size={11} style={{ verticalAlign: "-2px", marginRight: 3 }} /> Keyframe</span> : <span className="field-hint">Telemetry</span>}</td>
        <td><Link className="button small" href={`/events/${event.id}`}>Review</Link></td>
      </tr>;
    })}</tbody></table>{!busy && filtered.length === 0 && <div className="empty-state"><Search size={24} /><strong>No matching events</strong><p>Change the filters or create a test event using the API.</p></div>}</div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 18px", borderTop: "1px solid var(--line)" }}>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>Showing {total > 0 ? page * PAGE_SIZE + 1 : 0}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total} events</span>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="button small" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0 || busy}><ChevronLeft size={13} /> Prev</button>
          <button className="button small" onClick={() => setPage(p => p + 1)} disabled={(page + 1) >= totalPages || busy}>Next <ChevronRight size={13} /></button>
        </div>
      </div>
    </div>
  </AppShell>;
}

