"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, Bell, Camera, ChevronDown, CircleHelp, LayoutDashboard, LogOut, MapPin, Radar, ScrollText, Settings2, ShieldCheck, Users, Video, X } from "lucide-react";
import { useAuth } from "./auth-provider";

const links = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/map", label: "Tactical map", icon: MapPin },
  { href: "/events", label: "Event review", icon: Radar },
  { href: "/devices", label: "Devices & sites", icon: Camera },
  { href: "/jobs", label: "Video analysis", icon: Video },
];

function playTacticalChime() {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    // Dual sonar/radar ping: 880Hz quickly ascending to 1320Hz
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch {
    // AudioContext blocked by browser policy until user interacts
  }
}

interface AlertEvent {
  id: string;
  site_id?: string | null;
  source_id?: string;
  event_type: string;
  score?: number | null;
  primary_label?: string | null;
  is_semantic?: boolean;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, token, ready, logout } = useAuth();
  const [wsConnected, setWsConnected] = useState(false);
  const [liveAlert, setLiveAlert] = useState<AlertEvent | null>(null);

  useEffect(() => {
    if (ready && (!token || !user) && pathname !== "/login") router.replace("/login");
  }, [ready, token, user, pathname, router]);

  useEffect(() => {
    if (!token) return;
    let ws: WebSocket | null = null;
    let pingTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function initWs() {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const parsed = new URL(apiBase, "http://127.0.0.1:8000");
        const wsProto = parsed.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${wsProto}//${parsed.host}/api/v1/ws/alerts?token=${encodeURIComponent(token!)}`;

        ws = new WebSocket(wsUrl);
        ws.onopen = () => {
          setWsConnected(true);
          pingTimer = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "PING", timestamp: Date.now() }));
            }
          }, 30000);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "NEW_ALERT" && data.event) {
              playTacticalChime();
              setLiveAlert(data.event);
            }
          } catch {}
        };

        ws.onclose = () => {
          setWsConnected(false);
          if (pingTimer) clearInterval(pingTimer);
          reconnectTimer = setTimeout(initWs, 6000);
        };

        ws.onerror = () => {
          if (ws) ws.close();
        };
      } catch {
        setWsConnected(false);
      }
    }

    initWs();

    return () => {
      if (ws) ws.close();
      if (pingTimer) clearInterval(pingTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [token]);

  if (!ready) return <div className="screen-loading"><span className="spinner" /> Restoring secure session…</div>;
  if (!token || !user) return <div className="screen-loading"><span className="spinner" /> Opening Sentinel…</div>;

  return (
    <div className="app-frame">
      {/* Floating Tactical Alert Banner */}
      {liveAlert && (
        <div className="live-alert-banner" role="alert">
          <AlertTriangle size={18} color="#ef4444" style={{ flexShrink: 0 }} />
          <div>
            <strong>
              {liveAlert.is_semantic && liveAlert.primary_label
                ? `🚨 AI DETECTION: ${liveAlert.primary_label.toUpperCase()}`
                : `⚠️ TACTICAL ALERT: ${liveAlert.event_type.replaceAll("_", " ").toUpperCase()}`}
            </strong>
            <p>
              {liveAlert.score !== undefined && liveAlert.score !== null ? `Confidence: ${(liveAlert.score * 100).toFixed(0)}% · ` : ""}
              Source: {liveAlert.source_id ?? "Sensor feed"}
            </p>
          </div>
          <Link
            href={`/events/${liveAlert.id}`}
            className="button small"
            style={{ background: "#ef4444", color: "#fff", borderColor: "#dc2626", padding: "4px 10px", fontSize: 11 }}
            onClick={() => setLiveAlert(null)}
          >
            Review
          </Link>
          <button
            onClick={() => setLiveAlert(null)}
            style={{ background: "transparent", border: "none", color: "#9ca3af", cursor: "pointer", padding: 4 }}
            aria-label="Dismiss alert"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="Sentinel BD home">
          <span className="brand-mark"><ShieldCheck size={21} /></span>
          <span><strong>sentinel<span className="brand-dot">.</span></strong><small>BD / SENSOR INTELLIGENCE</small></span>
        </Link>
        <div className="workspace-switcher"><span className="workspace-icon">{user.email.slice(0, 1).toUpperCase()}</span><span className="workspace-copy"><strong>{user.email.split("@")[0]}</strong><small>{user.role} workspace</small></span><ChevronDown size={15} /></div>
        <p className="nav-label">WORKSPACE</p>
        <nav className="side-nav" aria-label="Main navigation">
          {links.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link key={href} href={href} className={`nav-link ${active ? "active" : ""}`}>
                <Icon size={17} strokeWidth={1.8} />
                <span>{label}</span>
                {label === "Event review" && (
                  <span className={`nav-indicator ${liveAlert ? "pulse-active" : ""}`} />
                )}
              </Link>
            );
          })}
          {(user.role === "admin" || user.role === "auditor") && (
            <>
              {user.role === "admin" && (
                <Link href="/users" className={`nav-link ${pathname.startsWith("/users") ? "active" : ""}`}><Users size={17} strokeWidth={1.8} /><span>Users</span></Link>
              )}
              <Link href="/audit" className={`nav-link ${pathname.startsWith("/audit") ? "active" : ""}`}><ScrollText size={17} strokeWidth={1.8} /><span>Audit logs</span></Link>
            </>
          )}
        </nav>
        <div className="sidebar-spacer" />
        <div className="system-card">
          <span className="system-pulse" />
          <div>
            <strong>Local system</strong>
            <small>Data stays on this deployment</small>
          </div>
        </div>
        <div className="sidebar-bottom"><a href="https://fastapi.tiangolo.com/" target="_blank" rel="noreferrer"><CircleHelp size={16} /> API documentation</a><a href="https://owasp.org/www-project-application-security-verification-standard/" target="_blank" rel="noreferrer"><Settings2 size={16} /> Security principles</a></div>
        <button className="profile-row" onClick={() => { logout(); router.replace("/login"); }}><span className="avatar">{user.email.slice(0, 1).toUpperCase()}</span><span className="profile-copy"><strong>{user.email}</strong><small>{user.role}</small></span><LogOut size={16} /></button>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Sentinel BD</span><span className="crumb-sep">/</span><strong>{links.find((item) => item.href === pathname || (item.href !== "/" && pathname.startsWith(item.href)))?.label ?? "Overview"}</strong></div>
          <div className="topbar-right">
            <span className="connection-pill" title={wsConnected ? "Real-time WebSocket stream active" : "Reconnecting stream..."}>
              <span className={wsConnected ? "dot-live" : "dot-offline"} style={!wsConnected ? { background: "#9ca3af" } : {}} />
              {wsConnected ? "Live Alert Stream" : "Connecting..."}
            </span>
            <span className="topbar-date">{new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" }).format(new Date())}</span>
          </div>
        </header>
        <div className="page-content">{children}</div>
        <footer className="footer-note"><span><ShieldCheck size={13} /> Authorized monitoring and research only</span><span>Sentinel BD · v0.1.0</span></footer>
      </main>
    </div>
  );
}

