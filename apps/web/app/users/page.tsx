"use client";

import { CheckCircle2, CircleAlert, Plus, RefreshCw, Shield, UserCheck, UserX, Users } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

function formatDate(val: string) {
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(val));
}

export default function UsersPage() {
  const { token, user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "operator" | "reviewer" | "viewer" | "auditor">("operator");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const data = await api.users(token);
      setUsers(data);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createUser(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api.createUser(token, { email: email.trim(), password, role });
      setEmail("");
      setPassword("");
      setSuccess("User account created successfully.");
      await load();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(targetUser: User) {
    if (!token) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api.setUserActive(token, targetUser.id, !targetUser.is_active);
      setSuccess(`User ${targetUser.email} has been ${targetUser.is_active ? "deactivated" : "activated"}.`);
      await load();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="page-heading">
        <div>
          <span className="eyebrow">Access &amp; Governance / 05</span>
          <h1>User management.</h1>
          <p>Administer accounts, roles and active statuses within your organization workspace.</p>
        </div>
        <button className="button" onClick={() => void load()} disabled={busy}>
          <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Refresh users
        </button>
      </div>

      {error && <div className="banner error"><CircleAlert size={16} /><span>{error}</span></div>}
      {success && <div className="banner success"><CheckCircle2 size={16} /><span>{success}</span></div>}

      <div className="overview-grid">
        <div className="card">
          <div className="card-head">
            <div>
              <h2>Organization accounts</h2>
              <p>{users.length} registered user(s)</p>
            </div>
            <Users size={17} color="#8b5a3c" />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf = u.id === currentUser?.id;
                  return (
                    <tr key={u.id}>
                      <td>
                        <span className="primary-cell">{u.email}</span>
                        <span className="secondary-cell mono">{u.id.slice(0, 8)}</span>
                      </td>
                      <td>
                        <span className={`badge ${u.role}`}>{u.role}</span>
                      </td>
                      <td>
                        <span className={`status ${u.is_active ? "active" : "offline"}`}>
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>{formatDate(u.created_at)}</td>
                      <td>
                        {isSelf ? (
                          <span className="field-hint">Your account</span>
                        ) : (
                          <button
                            className={`button small ${u.is_active ? "danger" : ""}`}
                            onClick={() => void toggleActive(u)}
                            disabled={busy || currentUser?.role !== "admin"}
                          >
                            {u.is_active ? <UserX size={12} /> : <UserCheck size={12} />}
                            {u.is_active ? "Deactivate" : "Activate"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {users.length === 0 && !busy && (
              <div className="empty-state">
                <Users size={24} />
                <strong>No users found</strong>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <h2>Add new user</h2>
              <p>Authorize team members</p>
            </div>
            <Plus size={17} color="#8b5a3c" />
          </div>
          <div className="card-body">
            <form className="form-stack" onSubmit={createUser}>
              <div className="field">
                <label htmlFor="user-email">Work email</label>
                <input
                  id="user-email"
                  className="input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@agency.local"
                  required
                  maxLength={254}
                />
              </div>

              <div className="field">
                <label htmlFor="user-role">Role permission</label>
                <select
                  id="user-role"
                  className="select"
                  value={role}
                  onChange={(e) => setRole(e.target.value as any)}
                >
                  <option value="operator">Operator (Submits jobs &amp; manages sensors)</option>
                  <option value="reviewer">Reviewer (Audits &amp; reviews detections)</option>
                  <option value="admin">Administrator (Full control &amp; user admin)</option>
                  <option value="auditor">Auditor (Read-only access with audit log)</option>
                  <option value="viewer">Viewer (Read-only observation access)</option>
                </select>
              </div>

              <div className="field">
                <label htmlFor="user-password">Initial password</label>
                <input
                  id="user-password"
                  className="input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 12 characters"
                  required
                  minLength={12}
                  maxLength={256}
                />
                <span className="field-hint">Must meet minimum complexity (12+ chars).</span>
              </div>

              <button
                className="button primary full"
                type="submit"
                disabled={busy || currentUser?.role !== "admin"}
              >
                {busy ? "Creating…" : "Create account"}
              </button>
            </form>

            <div className="banner" style={{ marginTop: 15, marginBottom: 0 }}>
              <Shield size={14} />
              <span>Role permissions are enforced server-side. The last active admin cannot be deactivated.</span>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
