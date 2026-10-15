"use client";

import Link from "next/link";
import { Activity, ArrowRight, Camera, Crosshair, ExternalLink, Eye, Filter, Layers, MapPin, Maximize2, Minimize2, Radio, RefreshCw, ShieldAlert, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Device, EventRecord, Site } from "@/lib/types";

function formatDate(val: string) {
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(val));
}

// Fallback center: Dhaka / Central Bangladesh (23.8103, 90.4125)
const DEFAULT_LAT = 23.8103;
const DEFAULT_LNG = 90.4125;

export default function TacticalMapPage() {
  const { token } = useAuth();
  const [sites, setSites] = useState<Site[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<string>("");
  const [selectedEvent, setSelectedEvent] = useState<EventRecord | null>(null);
  const [selectedSite, setSelectedSite] = useState<Site | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const svgRef = useRef<SVGSVGElement | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const [sList, dList, eList] = await Promise.all([
        api.sites(token),
        api.devices(token),
        api.events(token, "limit=60"),
      ]);
      setSites(sList);
      setDevices(dList);
      setEvents(eList.items);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  // Determine coordinate bounding box
  const { centerLat, centerLng, latSpan, lngSpan } = useMemo(() => {
    const coords: { lat: number; lng: number }[] = [];
    sites.forEach((s) => {
      if (s.latitude != null && s.longitude != null) coords.push({ lat: s.latitude, lng: s.longitude });
    });
    events.forEach((e) => {
      if (e.latitude != null && e.longitude != null) coords.push({ lat: e.latitude, lng: e.longitude });
    });

    if (coords.length === 0) {
      return { centerLat: DEFAULT_LAT, centerLng: DEFAULT_LNG, latSpan: 1.0, lngSpan: 1.0 };
    }

    const lats = coords.map((c) => c.lat);
    const lngs = coords.map((c) => c.lng);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);

    return {
      centerLat: (minLat + maxLat) / 2,
      centerLng: (minLng + maxLng) / 2,
      latSpan: Math.max(0.1, (maxLat - minLat) * 1.5),
      lngSpan: Math.max(0.1, (maxLng - minLng) * 1.5),
    };
  }, [sites, events]);

  // Project geographic coord to map viewport [0, 800] x [0, 600]
  const project = useCallback(
    (lat: number, lng: number) => {
      const width = 800;
      const height = 550;
      const x = ((lng - (centerLng - lngSpan / 2)) / lngSpan) * width;
      // Invert Y because latitude goes north (up)
      const y = height - ((lat - (centerLat - latSpan / 2)) / latSpan) * height;
      return { x, y };
    },
    [centerLat, centerLng, latSpan, lngSpan]
  );

  function handleMouseDown(e: React.MouseEvent) {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  }

  function handleMouseUp() {
    setIsDragging(false);
  }

  function resetView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setSelectedEvent(null);
    setSelectedSite(null);
  }

  // Filtered lists
  const displaySites = selectedSiteId ? sites.filter((s) => s.id === selectedSiteId) : sites;
  const displayEvents = selectedSiteId ? events.filter((e) => e.site_id === selectedSiteId) : events;

  return (
    <AppShell>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Geospatial Intelligence / 07</span>
          <h1>Tactical situation map.</h1>
          <p>Real-time spatial visualization of deployment sites, perimeter sensors, and detected event alerts.</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="button" onClick={() => void load()} disabled={busy}>
            <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Refresh radar
          </button>
          <button className="button" onClick={resetView}>
            <Crosshair size={14} /> Center view
          </button>
        </div>
      </div>

      {error && <div className="banner error"><ShieldAlert size={16} /><span>{error}</span></div>}

      <div className="toolbar" style={{ marginBottom: 12 }}>
        <Filter size={14} color="#8c7d6a" />
        <select
          aria-label="Filter site"
          className="select"
          value={selectedSiteId}
          onChange={(e) => setSelectedSiteId(e.target.value)}
        >
          <option value="">All monitoring sectors &amp; sites ({sites.length})</option>
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.latitude != null ? `${s.latitude.toFixed(2)}°N, ${s.longitude?.toFixed(2)}°E` : "No coords"})
            </option>
          ))}
        </select>

        <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#39a853" }} /> Active Sensor Site
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#e84a3b" }} /> Incident / Motion Alert
          </span>
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(320px, 0.7fr)", gap: 16, alignItems: "start" }}>
        {/* Tactical Map Canvas */}
        <div className="card" style={{ overflow: "hidden", position: "relative", background: "#171512", border: "1px solid #3c3429" }}>
          {/* Zoom controls */}
          <div style={{ position: "absolute", top: 12, right: 12, zIndex: 10, display: "flex", flexDirection: "column", gap: 4 }}>
            <button className="button small" onClick={() => setZoom((z) => Math.min(3.5, z + 0.3))} title="Zoom In">
              <ZoomIn size={13} />
            </button>
            <button className="button small" onClick={() => setZoom((z) => Math.max(0.6, z - 0.3))} title="Zoom Out">
              <ZoomOut size={13} />
            </button>
          </div>

          {/* Coordinates HUD Overlay */}
          <div style={{ position: "absolute", bottom: 12, left: 14, zIndex: 10, color: "#928471", fontSize: 10, fontFamily: "monospace", display: "flex", gap: 16, pointerEvents: "none" }}>
            <span>CENTER: {centerLat.toFixed(4)}°N, {centerLng.toFixed(4)}°E</span>
            <span>ZOOM: {(zoom * 100).toFixed(0)}%</span>
            <span>SECTOR: GRID-LOC-BD</span>
          </div>

          <div
            style={{ width: "100%", height: 560, cursor: isDragging ? "grabbing" : "grab", userSelect: "none" }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <svg
              ref={svgRef}
              viewBox="0 0 800 550"
              style={{ width: "100%", height: "100%", transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: "center" }}
            >
              <defs>
                {/* Radar Grid Pattern */}
                <pattern id="tactical-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#2a251e" strokeWidth="0.8" />
                </pattern>
                <radialGradient id="radar-sweep" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#8b5a3c" stopOpacity="0.08" />
                  <stop offset="100%" stopColor="#8b5a3c" stopOpacity="0" />
                </radialGradient>
              </defs>

              {/* Background grid */}
              <rect width="800" height="550" fill="#171512" />
              <rect width="800" height="550" fill="url(#tactical-grid)" />

              {/* Concentric Sector Radar Rings */}
              <circle cx="400" cy="275" r="100" fill="none" stroke="#352e25" strokeWidth="1" strokeDasharray="4 4" />
              <circle cx="400" cy="275" r="200" fill="none" stroke="#352e25" strokeWidth="1" strokeDasharray="4 4" />
              <circle cx="400" cy="275" r="300" fill="none" stroke="#352e25" strokeWidth="1" strokeDasharray="4 4" />
              <line x1="400" y1="0" x2="400" y2="550" stroke="#352e25" strokeWidth="0.8" strokeDasharray="3 3" />
              <line x1="0" y1="275" x2="800" y2="275" stroke="#352e25" strokeWidth="0.8" strokeDasharray="3 3" />

              {/* Plot Sites */}
              {displaySites.map((s, idx) => {
                const pos = s.latitude != null && s.longitude != null ? project(s.latitude, s.longitude) : { x: 220 + (idx % 4) * 120, y: 180 + Math.floor(idx / 4) * 100 };
                const isSelected = selectedSite?.id === s.id;
                const siteDeviceCount = devices.filter((d) => d.site_id === s.id).length;

                return (
                  <g
                    key={s.id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    style={{ cursor: "pointer" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedSite(s);
                      setSelectedEvent(null);
                    }}
                  >
                    {/* Radar ping ring */}
                    <circle r="18" fill="none" stroke="#39a853" strokeWidth="1" opacity="0.4" />
                    <circle r="9" fill={isSelected ? "#5ad377" : "#39a853"} stroke="#fff" strokeWidth="1.5" />
                    <text x="14" y="4" fill="#d8cfbe" fontSize="11" fontFamily="sans-serif" fontWeight="bold">
                      {s.name}
                    </text>
                    <text x="14" y="16" fill="#8c7e6c" fontSize="9" fontFamily="monospace">
                      {siteDeviceCount} sensors · {s.latitude != null ? `${s.latitude.toFixed(2)}N` : "unmapped"}
                    </text>
                  </g>
                );
              })}

              {/* Plot Events / Incident Alerts */}
              {displayEvents.map((evt, idx) => {
                let pos: { x: number; y: number };
                if (evt.latitude != null && evt.longitude != null) {
                  pos = project(evt.latitude, evt.longitude);
                } else if (evt.site_id) {
                  const s = sites.find((site) => site.id === evt.site_id);
                  if (s && s.latitude != null && s.longitude != null) {
                    const base = project(s.latitude, s.longitude);
                    // Slight deterministic scatter around the site
                    pos = { x: base.x + ((idx % 5) - 2) * 14, y: base.y + (((idx * 3) % 5) - 2) * 14 };
                  } else {
                    pos = { x: 380 + (idx % 6) * 35, y: 260 + (idx % 4) * 35 };
                  }
                } else {
                  pos = { x: 350 + (idx % 7) * 30, y: 220 + (idx % 5) * 30 };
                }

                const isSelected = selectedEvent?.id === evt.id;
                const isUnreviewed = evt.review_status === "unreviewed";
                const color = isUnreviewed ? "#e84a3b" : "#45b364";

                return (
                  <g
                    key={evt.id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    style={{ cursor: "pointer" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedEvent(evt);
                      setSelectedSite(null);
                    }}
                  >
                    {/* Animated pulse ring for unreviewed incidents */}
                    {isUnreviewed && (
                      <circle r="14" fill="none" stroke={color} strokeWidth="1.2" opacity="0.6">
                        <animate attributeName="r" values="8;20;8" dur="2.4s" repeatCount="indefinite" />
                        <animate attributeName="opacity" values="0.8;0.1;0.8" dur="2.4s" repeatCount="indefinite" />
                      </circle>
                    )}
                    <circle r={isSelected ? "7" : "5"} fill={color} stroke="#ffffff" strokeWidth="1.2" />
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        {/* Tactical Inspector Panel */}
        <div style={{ display: "grid", gap: 14 }}>
          {selectedEvent ? (
            <div className="card">
              <div className="card-head">
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <h2>Incident Inspector</h2>
                    {selectedEvent.details?.primary_label && (
                      <span className="badge person">{String(selectedEvent.details.primary_label).toUpperCase()}</span>
                    )}
                  </div>
                  <p className="mono">{selectedEvent.id.slice(0, 12)}</p>
                </div>
                <span className={`status ${selectedEvent.review_status}`}>{selectedEvent.review_status}</span>
              </div>
              <div className="card-body">
                {selectedEvent.details?.snapshot_ref && (
                  <div className="media-box" style={{ marginBottom: 12 }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      className="snapshot-img"
                      src={`${api.eventSnapshotUrl(selectedEvent.id)}?token=${encodeURIComponent(token || "")}`}
                      alt="Incident Keyframe"
                      style={{ maxHeight: 200 }}
                    />
                  </div>
                )}
                <div className="detail-pairs">
                  <div className="detail-pair">
                    <span>Observation</span>
                    <strong>{selectedEvent.event_type.replaceAll("_", " ")}</strong>
                  </div>
                  {selectedEvent.details?.primary_label && (
                    <div className="detail-pair">
                      <span>AI Target</span>
                      <strong style={{ color: "#b91c1c" }}>{String(selectedEvent.details.primary_label).toUpperCase()}</strong>
                    </div>
                  )}
                  <div className="detail-pair">
                    <span>Source</span>
                    <strong>{selectedEvent.source_id}</strong>
                  </div>
                  <div className="detail-pair">
                    <span>Observed At</span>
                    <strong>{formatDate(selectedEvent.observed_at)}</strong>
                  </div>
                  <div className="detail-pair">
                    <span>Score</span>
                    <strong>{selectedEvent.score !== null ? `${(selectedEvent.score * 100).toFixed(1)}%` : "N/A"}</strong>
                  </div>
                </div>

                <div style={{ marginTop: 16 }}>
                  <Link href={`/events/${selectedEvent.id}`} className="button primary full">
                    Open Event &amp; Review <ArrowRight size={14} />
                  </Link>
                </div>
              </div>
            </div>
          ) : selectedSite ? (
            <div className="card">
              <div className="card-head">
                <div>
                  <h2>Sector / Site</h2>
                  <p className="mono">{selectedSite.id.slice(0, 8)}</p>
                </div>
                <Radio size={16} color="#39a853" />
              </div>
              <div className="card-body">
                <div className="detail-pairs">
                  <div className="detail-pair">
                    <span>Site Name</span>
                    <strong>{selectedSite.name}</strong>
                  </div>
                  <div className="detail-pair">
                    <span>Sensors</span>
                    <strong>{devices.filter((d) => d.site_id === selectedSite.id).length} registered</strong>
                  </div>
                  <div className="detail-pair">
                    <span>Coordinates</span>
                    <strong>
                      {selectedSite.latitude != null && selectedSite.longitude != null
                        ? `${selectedSite.latitude.toFixed(4)}°, ${selectedSite.longitude.toFixed(4)}°`
                        : "Unspecified"}
                    </strong>
                  </div>
                  <div className="detail-pair">
                    <span>Description</span>
                    <strong>{selectedSite.description || "Perimeter sector"}</strong>
                  </div>
                </div>
                <div style={{ marginTop: 14 }}>
                  <Link href="/devices" className="button full">
                    Manage Sector Sensors <ExternalLink size={13} />
                  </Link>
                </div>
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="card-head">
                <div>
                  <h2>Sector Overview</h2>
                  <p>Deployment summary</p>
                </div>
                <Layers size={16} color="#8b5a3c" />
              </div>
              <div className="card-body">
                <div className="job-row">
                  <div className="job-icon"><MapPin size={16} /></div>
                  <div className="job-main">
                    <strong>Total Deployment Sites</strong>
                    <small>{sites.length} tactical sectors</small>
                  </div>
                  <strong>{sites.length}</strong>
                </div>
                <div className="job-row">
                  <div className="job-icon"><Camera size={16} /></div>
                  <div className="job-main">
                    <strong>Registered Devices</strong>
                    <small>{devices.length} sensor telemetry sources</small>
                  </div>
                  <strong>{devices.length}</strong>
                </div>
                <div className="job-row">
                  <div className="job-icon"><ShieldAlert size={16} /></div>
                  <div className="job-main">
                    <strong>Recent Incident Pings</strong>
                    <small>{events.filter((e) => e.review_status === "unreviewed").length} unreviewed events</small>
                  </div>
                  <strong>{events.length}</strong>
                </div>
                <p className="field-hint" style={{ marginTop: 12 }}>
                  Click any marker or incident pin on the map to inspect keyframes and jump directly to human review.
                </p>
              </div>
            </div>
          )}

          {/* Quick Incidents Feed */}
          <div className="card">
            <div className="card-head">
              <div>
                <h2>Recent Map Events</h2>
                <p>Latest sector detections</p>
              </div>
              <Activity size={15} color="#8b5a3c" />
            </div>
            <div className="card-body">
              {events.slice(0, 5).map((evt) => (
                <div
                  key={evt.id}
                  className="job-row"
                  style={{ cursor: "pointer" }}
                  onClick={() => {
                    setSelectedEvent(evt);
                    setSelectedSite(null);
                  }}
                >
                  <div className="job-icon">
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: evt.review_status === "unreviewed" ? "#e84a3b" : "#45b364" }} />
                  </div>
                  <div className="job-main">
                    <strong>{evt.details?.primary_label ? `AI: ${String(evt.details.primary_label).toUpperCase()}` : evt.event_type.replaceAll("_", " ")}</strong>
                    <small>{formatDate(evt.observed_at)} · {evt.score !== null ? `${(evt.score * 100).toFixed(0)}%` : "unscored"}</small>
                  </div>
                  <button className="button small">Inspect</button>
                </div>
              ))}
              {events.length === 0 && <p className="field-hint">No events recorded in this workspace.</p>}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
