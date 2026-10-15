"use client";

import { Activity, Camera, Plus, RefreshCw, RadioTower } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Device, Site } from "@/lib/types";

export default function DevicesPage() {
  const { token, user } = useAuth();
  const [devices, setDevices] = useState<Device[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [name, setName] = useState("");
  const [deviceType, setDeviceType] = useState("camera");
  const [siteId, setSiteId] = useState("");
  const [siteName, setSiteName] = useState("");
  const [panel, setPanel] = useState<"device" | "site">("device");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true); setError("");
    try { const [ds, ss] = await Promise.all([api.devices(token), api.sites(token)]); setDevices(ds); setSites(ss); }
    catch (e) { setError((e as ApiError).message); }
    finally { setBusy(false); }
  }, [token]);
  useEffect(() => { void load(); }, [load]);
  async function create(e: FormEvent) {
    e.preventDefault(); if (!token) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      if (panel === "site") { await api.createSite(token, { name: siteName.trim() }); setSiteName(""); setSuccess("Site created."); }
      else { await api.createDevice(token, { name: name.trim(), device_type: deviceType, site_id: siteId || null }); setName(""); setSuccess("Device registered."); }
      await load();
    } catch (e) { setError((e as ApiError).message); }
    finally { setBusy(false); }
  }
  async function updateHeartbeat(device: Device, status: string) {
    if (!token) return;
    setError("");
    try { await api.heartbeat(token, device.id, status); await load(); }
    catch (e) { setError((e as ApiError).message); }
  }
  return <AppShell>
    <div className="page-heading"><div><span className="eyebrow">Inventory &amp; integration / 03</span><h1>Devices &amp; sites.</h1><p>Register data sources and track basic health metadata. Registration does not imply live device connectivity.</p></div><button className="button" onClick={() => void load()} disabled={busy}><RefreshCw size={14} /> Refresh inventory</button></div>
    {error && <div className="banner error">{error}</div>}{success && <div className="banner success">{success}</div>}
    <div className="overview-grid">
      <div className="card"><div className="card-head"><div><h2>Registered devices</h2><p>{devices.length} devices in this workspace</p></div><Camera size={17} color="#8b5a3c" /></div>
        <div className="table-wrap"><table><thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Last heartbeat</th><th>Action</th></tr></thead><tbody>{devices.map(device => <tr key={device.id}><td><span className="primary-cell">{device.name}</span><span className="secondary-cell mono">{device.id.slice(0, 8)}</span></td><td>{device.device_type.replaceAll("_", " ")}</td><td><span className={`status ${device.status}`}>{device.status}</span></td><td>{device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : "Never"}</td><td><button className="button small" onClick={() => void updateHeartbeat(device, device.status === "active" ? "maintenance" : "active")}>{device.status === "active" ? "Set maintenance" : "Set active"}</button></td></tr>)}</tbody></table>{devices.length === 0 && <div className="empty-state"><Camera size={23} /><strong>No devices registered</strong><p>Add a camera, sensor, simulator or commercial telemetry source.</p></div>}</div>
      </div>
      <div className="card"><div className="card-head"><div><h2>Register source</h2><p>Workspace: {user?.email}</p></div><Plus size={17} color="#8b5a3c" /></div><div className="card-body"><div className="login-mode" style={{ marginBottom: 17 }}><button className={panel === "device" ? "active" : ""} onClick={() => setPanel("device")}>Device</button><button className={panel === "site" ? "active" : ""} onClick={() => setPanel("site")}>Site</button></div><form className="form-stack" onSubmit={create}>{panel === "device" ? <><div className="field"><label htmlFor="name">Device name</label><input id="name" className="input" value={name} onChange={e => setName(e.target.value)} required maxLength={160} placeholder="North gate camera" /></div><div className="field"><label htmlFor="type">Device type</label><select id="type" className="select" value={deviceType} onChange={e => setDeviceType(e.target.value)}><option value="camera">Camera</option><option value="sensor">Sensor</option><option value="commercial_drone_telemetry">Commercial drone telemetry</option><option value="edge_computer">Edge computer</option><option value="simulator">Simulator</option></select></div><div className="field"><label htmlFor="site">Site (optional)</label><select id="site" className="select" value={siteId} onChange={e => setSiteId(e.target.value)}><option value="">No site assigned</option>{sites.map(site => <option value={site.id} key={site.id}>{site.name}</option>)}</select></div></> : <div className="field"><label htmlFor="siteName">Site name</label><input id="siteName" className="input" value={siteName} onChange={e => setSiteName(e.target.value)} required maxLength={160} placeholder="Test lab / campus" /></div>}<button className="button primary full" type="submit" disabled={busy || user?.role === "viewer" || user?.role === "auditor"}>{busy ? "Saving…" : panel === "device" ? "Register device" : "Create site"}</button></form><div className="banner" style={{ marginTop: 15, marginBottom: 0 }}><RadioTower size={15} /><span>Device status is operator-managed metadata. A real heartbeat integration must authenticate its source before status can be treated as live.</span></div></div></div>
    </div>
    <div className="card" style={{ marginTop: 16 }}><div className="card-head"><div><h2>Sites</h2><p>Logical deployment locations. Coordinates are optional.</p></div><Activity size={17} color="#8b5a3c" /></div><div className="card-body"><div className="detail-pairs">{sites.map(site => <div className="detail-pair" key={site.id}><span>{site.id.slice(0, 8)}</span><strong>{site.name}</strong><div className="field-hint">{site.latitude != null && site.longitude != null ? `${site.latitude}, ${site.longitude}` : site.description ?? "No coordinates provided"}</div></div>)}{sites.length === 0 && <p className="field-hint">No sites yet. Create one using the form above.</p>}</div></div></div>
  </AppShell>;
}
