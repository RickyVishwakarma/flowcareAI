"use client";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const PREFIX = "/api/v1";

const ACCESS_KEY = "flowcare_access";
const REFRESH_KEY = "flowcare_refresh";

function accessToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY);
}
function refreshToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
export function isAuthed(): boolean {
  return !!accessToken();
}

async function rawFetch(path: string, init: RequestInit, token: string | null) {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  return fetch(`${BASE}${PREFIX}${path}`, { ...init, headers });
}

// Single-flight refresh so concurrent 401s don't stampede the refresh endpoint.
let refreshing: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  const rt = refreshToken();
  if (!rt) return false;
  if (!refreshing) {
    refreshing = (async () => {
      const res = await fetch(`${BASE}${PREFIX}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) {
        clearTokens();
        return false;
      }
      const data = await res.json();
      setTokens(data.access_token, data.refresh_token);
      return true;
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await rawFetch(path, init, accessToken());
  // Transparently refresh once on an expired access token.
  if (res.status === 401 && !path.startsWith("/auth/") && (await tryRefresh())) {
    res = await rawFetch(path, init, accessToken());
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed (${res.status})`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export interface Referral {
  id: string;
  reference_code: string;
  source: string;
  status: string;
  patient_name: string | null;
  referring_doctor: string | null;
  created_at: string;
}

export interface ReferralDetail extends Referral {
  documents: { id: string; filename: string; ocr_confidence: number | null }[];
  extracted_data: {
    patient_name: string | null;
    dob: string | null;
    insurance_provider: string | null;
    insurance_member_id: string | null;
    diagnosis: string | null;
    referral_reason: string | null;
    overall_confidence: number | null;
    extractor: string | null;
    validation_status: string | null;
    validation_report: { errors: string[]; warnings: string[] };
  } | null;
}

export interface WorkflowNode {
  id: string;
  node_key: string;
  kind: string;
  type: string;
  config: Record<string, unknown>;
  next: Record<string, string>;
}

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  trigger_event: string;
  status: string;
  version: number;
  nodes: WorkflowNode[];
}

export interface ReviewQueueItem {
  id: string;
  reference_code: string;
  status: string;
  patient_name: string | null;
  created_at: string;
  error_count: number;
  warning_count: number;
}

export interface ReviewDetail {
  id: string;
  reference_code: string;
  status: string;
  ocr_text: string | null;
  fields: Record<string, string | null>;
  field_confidence: Record<string, number>;
  validation_report: { errors?: string[]; warnings?: string[] };
}

export interface ReviewResult {
  referral_id: string;
  status: string;
  validation_status: string;
  changed_fields: string[];
  workflow_executions: string[];
}

export const REVIEW_FIELDS = [
  "patient_name",
  "dob",
  "insurance_provider",
  "insurance_member_id",
  "referring_doctor",
  "diagnosis",
  "referral_reason",
] as const;

export interface Tokens {
  access_token: string;
  refresh_token: string;
}

export interface SignupResult extends Tokens {
  verification_link: string | null;
}

export interface Me {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  organization_id: string;
  organization_name: string;
  is_active: boolean;
  email_verified: boolean;
}

export interface DashboardStats {
  referrals_total: number;
  referrals_by_status: Record<string, number>;
  referrals_by_source: Record<string, number>;
  referrals_timeseries: { date: string; count: number }[];
  validation_breakdown: Record<string, number>;
  extractor_breakdown: Record<string, number>;
  avg_confidence: number | null;
  workflow_total: number;
  workflow_by_status: Record<string, number>;
  workflow_success_rate: number;
  insurance_total: number;
  insurance_active: number;
  insurance_active_rate: number;
  appointments_total: number;
  review_queue_size: number;
  open_tasks: number;
}

export interface TaskItem {
  id: string;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  referral_id: string | null;
  referral_reference: string | null;
  assigned_to: string | null;
  assignee_email: string | null;
  created_at: string;
}

export const api = {
  dashboard: () => request<DashboardStats>("/dashboard/overview"),
  listTasks: (params: { status?: string; mine?: boolean } = {}) => {
    const q = new URLSearchParams();
    if (params.status) q.set("status_filter", params.status);
    if (params.mine) q.set("mine", "true");
    const qs = q.toString();
    return request<TaskItem[]>(`/tasks${qs ? `?${qs}` : ""}`);
  },
  claimTask: (id: string) => request<TaskItem>(`/tasks/${id}/claim`, { method: "POST" }),
  updateTask: (id: string, body: { status?: string; priority?: string }) =>
    request<TaskItem>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  login: (email: string, password: string) =>
    request<Tokens>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  signup: (organization_name: string, email: string, password: string, full_name?: string) =>
    request<SignupResult>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ organization_name, email, password, full_name }),
    }),
  logout: () => {
    const rt = typeof window !== "undefined" ? localStorage.getItem(REFRESH_KEY) : null;
    const done = rt
      ? request<{ detail: string }>("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: rt }) }).catch(() => {})
      : Promise.resolve();
    clearTokens();
    return done;
  },
  changePassword: (current_password: string, new_password: string) =>
    request<Tokens>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
  me: () => request<Me>("/auth/me"),
  verifyEmail: (token: string) =>
    request<{ detail: string }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  forgotPassword: (email: string) =>
    request<{ detail: string; reset_link: string | null }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, new_password: string) =>
    request<{ detail: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    }),
  resendVerification: () =>
    request<{ detail: string; verification_link: string | null }>("/auth/resend-verification", {
      method: "POST",
    }),
  listReferrals: () => request<Referral[]>("/referrals"),
  getReferral: (id: string) => request<ReferralDetail>(`/referrals/${id}`),
  reviewQueue: () => request<ReviewQueueItem[]>("/review/queue"),
  getReview: (id: string) => request<ReviewDetail>(`/review/${id}`),
  submitReview: (id: string, body: Record<string, unknown>) =>
    request<ReviewResult>(`/review/${id}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  uploadReferral: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ id: string; reference_code: string; status: string }>("/referrals", {
      method: "POST",
      body: fd,
    });
  },
  listWorkflows: () => request<Workflow[]>("/workflows"),
  getWorkflow: (id: string) => request<Workflow>(`/workflows/${id}`),
  createWorkflow: (body: Record<string, unknown>) =>
    request<Workflow>("/workflows", { method: "POST", body: JSON.stringify(body) }),
  saveWorkflow: (id: string, body: Record<string, unknown>) =>
    request<Workflow>(`/workflows/${id}`, { method: "PUT", body: JSON.stringify(body) }),
};
