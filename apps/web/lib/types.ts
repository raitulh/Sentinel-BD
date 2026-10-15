export type User = {
  id: string;
  organization_id: string;
  email: string;
  role: "admin" | "operator" | "reviewer" | "viewer" | "auditor";
  is_active: boolean;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
};

export type Site = {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
};

export type Device = {
  id: string;
  organization_id: string;
  site_id: string | null;
  name: string;
  device_type: string;
  status: string;
  details: Record<string, unknown>;
  last_seen_at: string | null;
  created_at: string;
};

export type EventRecord = {
  id: string;
  organization_id: string;
  site_id: string | null;
  source_id: string;
  event_type: string;
  observed_at: string;
  received_at: string;
  review_status: "unreviewed" | "reviewed";
  score: number | null;
  score_kind: string | null;
  evidence_ref: string | null;
  model_version: string | null;
  details: Record<string, unknown>;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
};

export type EventList = {
  items: EventRecord[];
  total: number;
  limit: number;
  offset: number;
};

export type Review = {
  id: string;
  organization_id: string;
  event_id: string;
  reviewer_id: string;
  decision: string;
  note: string | null;
  created_at: string;
};

export type Job = {
  id: string;
  organization_id: string;
  requested_by: string;
  job_type: string;
  status: "queued" | "running" | "succeeded" | "failed";
  source_name: string;
  site_id: string | null;
  attempts: number;
  result_summary: Record<string, unknown>;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type AuditLogItem = {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: string;
  details: Record<string, unknown>;
  created_at: string;
};
