"use client";

import { CheckCircle2, ChevronDown, ChevronRight, CircleAlert, Filter, RefreshCw, ScrollText, Search, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { AuditLogItem } from "@/lib/types";

function formatTimestamp(val: string) {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(val)) + " UTC";
}

export default function AuditLogsPage() {
  const { token } = useAuth();
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [search, setSearch] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const data = await api.auditLogs(token, "limit=200");
      setLogs(data);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = logs.filter((log) => {
    const matchesSearch =
      `${log.action} ${log.resource_type} ${log.actor_id ?? ""} ${log.resource_id ?? ""}`
        .toLowerCase()
        .includes(search.toLowerCase());
    const matchesOutcome = outcomeFilter === "all" || log.outcome === outcomeFilter;
    return matchesSearch && matchesOutcome;
  });

  return (
    <AppShell>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Governance &amp; Audit Trail / 06</span>
          <h1>Audit log explorer.</h1>
          <p>Inspect immutable event logs, administrative actions, and model job executions across the workspace.</p>
        </div>
        <button className="button" onClick={() => void load()} disabled={busy}>
          <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Refresh logs
        </button>
      </div>

      {error && <div className="banner error"><CircleAlert size={16} /><span>{error}</span></div>}

      <div className="banner">
        <ShieldCheck size={16} />
        <span><strong>Audit trail assurance:</strong> Application actions are recorded in an append-only audit register for compliance and security forensics.</span>
      </div>

      <div className="toolbar">
        <div style={{ position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 11, top: 12, color: "#9d907f" }} />
          <input
            aria-label="Search audit logs"
            className="input"
            style={{ paddingLeft: 32 }}
            placeholder="Search action, actor, or resource…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <Filter size={14} color="#8c7d6a" />
        <select
          aria-label="Outcome filter"
          className="select"
          value={outcomeFilter}
          onChange={(e) => setOutcomeFilter(e.target.value)}
        >
          <option value="all">All outcomes</option>
          <option value="success">Success only</option>
          <option value="failure">Failure only</option>
        </select>

        <span style={{ marginLeft: "auto", fontSize: 10, color: "#928678" }}>
          {filtered.length} displayed · {logs.length} loaded
        </span>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 30 }}></th>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Resource</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((log) => {
                const isExpanded = expandedId === log.id;
                return (
                  <tr key={log.id} style={{ cursor: "pointer" }} onClick={() => setExpandedId(isExpanded ? null : log.id)}>
                    <td>
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </td>
                    <td>
                      <span className="mono" style={{ fontSize: 11 }}>{formatTimestamp(log.created_at)}</span>
                    </td>
                    <td>
                      <span className="primary-cell mono">{log.action}</span>
                    </td>
                    <td>
                      <span className="secondary-cell mono">{log.actor_id ? log.actor_id.slice(0, 8) : "System"}</span>
                    </td>
                    <td>
                      <span>{log.resource_type}</span>
                      {log.resource_id && <span className="secondary-cell mono">{log.resource_id.slice(0, 8)}</span>}
                    </td>
                    <td>
                      <span className={`badge ${log.outcome}`}>{log.outcome}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {filtered.length === 0 && !busy && (
            <div className="empty-state">
              <ScrollText size={24} />
              <strong>No audit log entries found</strong>
              <p>Adjust your search filter or trigger workspace activities.</p>
            </div>
          )}
        </div>
      </div>

      {expandedId && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-head">
            <div>
              <h2>Record details</h2>
              <p className="mono">{expandedId}</p>
            </div>
            <button className="button small" onClick={() => setExpandedId(null)}>Close inspector</button>
          </div>
          <div className="card-body">
            <pre className="json-block">
              {JSON.stringify(logs.find((l) => l.id === expandedId), null, 2)}
            </pre>
          </div>
        </div>
      )}
    </AppShell>
  );
}
