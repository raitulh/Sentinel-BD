"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, CircleAlert, Fingerprint, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

export default function LoginPage() {
  const router = useRouter();
  const { acceptToken, token, ready } = useAuth();
  const [mode, setMode] = useState<"login" | "bootstrap">("login");
  const [organization, setOrganization] = useState("Sentinel Lab");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [bootstrapToken, setBootstrapToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { if (ready && token) router.replace("/"); }, [ready, token, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = mode === "login"
        ? await api.login(email, password)
        : await api.bootstrap({ organization_name: organization, email, password }, bootstrapToken);
      acceptToken(result);
      router.replace("/");
    } catch (e) {
      const err = e as ApiError;
      setError(err.message || "Request failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="login-wrap">
    <section className="login-story">
      <Link className="brand" href="/login"><span className="brand-mark"><ShieldCheck size={21} /></span><span><strong>sentinel<span className="brand-dot">.</span></strong><small>BD / SENSOR INTELLIGENCE</small></span></Link>
      <div className="login-story-copy"><span className="eyebrow">Local-first monitoring platform</span><h1>Clarity from<br />every signal.</h1><p>Understand what your sensors are seeing. Review events with context, inspect source metadata, and keep your operational data within your own environment.</p></div>
      <div className="story-foot">BUILT FOR AUTHORIZED MONITORING, RESEARCH &amp; RELIABLE OPERATIONS</div>
    </section>
    <section className="login-panel">
      <span className="eyebrow">Secure workspace</span>
      <h2>{mode === "login" ? "Welcome back." : "Create your workspace."}</h2>
      <p>{mode === "login" ? "Sign in to review events and system health." : "Bootstrap is only for the very first administrator; it will be disabled after the first account is created."}</p>
      <div className="login-mode"><button className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>Sign in</button><button className={mode === "bootstrap" ? "active" : ""} onClick={() => { setMode("bootstrap"); setError(""); }}>Initial setup</button></div>
      {error && <div className="banner error"><CircleAlert size={16} /><span>{error}</span></div>}
      <form className="form-stack" onSubmit={submit}>
        {mode === "bootstrap" && <div className="field"><label htmlFor="organization">Organization / lab name</label><input id="organization" className="input" value={organization} onChange={e => setOrganization(e.target.value)} required minLength={2} maxLength={160} /></div>}
        <div className="field"><label htmlFor="email">Work email</label><input id="email" className="input" type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.org" required maxLength={254} /></div>
        <div className="field"><label htmlFor="password">Password</label><input id="password" className="input" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={e => setPassword(e.target.value)} placeholder={mode === "login" ? "Your password" : "At least 12 characters"} required minLength={mode === "bootstrap" ? 12 : 1} maxLength={256} /></div>
        {mode === "bootstrap" && <div className="field"><label htmlFor="bootstrap">Bootstrap token</label><input id="bootstrap" className="input" type="password" autoComplete="off" value={bootstrapToken} onChange={e => setBootstrapToken(e.target.value)} required /><span className="field-hint">Set BOOTSTRAP_TOKEN in the backend environment first.</span></div>}
        <button className="button primary full" type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in to Sentinel" : "Create first administrator"}<ArrowRight size={15} /></button>
      </form>
      <div className="login-footnote"><Fingerprint size={14} style={{ verticalAlign: "-3px", marginRight: 5 }} /> Session tokens are held for this browser session only. Use HTTPS outside localhost.</div>
    </section>
  </main>;
}
