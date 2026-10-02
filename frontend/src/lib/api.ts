/**
 * Centralized API client — all backend calls go through here.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'APIError';
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || msg;
    } catch {}
    throw new APIError(res.status, msg);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Auth ────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user_id: string; role: string; full_name: string }>(
      '/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      }
    ),

  register: (data: { email: string; password: string; full_name: string; role: string; department?: string }) =>
    request('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  me: (token: string) => request<{ id: string; email: string; full_name: string; role: string; department?: string }>('/auth/me', {}, token),

  logout: (token: string) => request('/auth/logout', { method: 'POST' }, token),
};

// ── Documents ───────────────────────────────────────────────────────────
export const documentsAPI = {
  upload: (formData: FormData, token: string) =>
    request<{ results: Array<{ filename: string; status: string; source_id?: string; chunks?: number; message?: string }> }>(
      '/documents/upload', { method: 'POST', body: formData }, token
    ),

  list: (token: string, params?: { classification?: string; is_standard_resource?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.classification) qs.set('classification', params.classification);
    if (params?.is_standard_resource !== undefined) qs.set('is_standard_resource', String(params.is_standard_resource));
    return request<any[]>(`/documents/?${qs}`, {}, token);
  },

  delete: (sourceId: string, token: string) =>
    request(`/documents/${sourceId}`, { method: 'DELETE' }, token),
};

// ── Chat ────────────────────────────────────────────────────────────────
export const chatAPI = {
  query: (data: { query: string; session_id?: string; force_local_model?: boolean; source_ids?: string[] }, token: string) =>
    request<{
      answer: string | null;
      session_id: string;
      message_id: string;
      model_used: string | null;
      is_local_model: boolean;
      sources: Array<{ source_name?: string; source_id?: string; classification?: string; url?: string; source_type?: string }>;
      needs_fallback_confirmation: boolean;
      fallback_reason: string | null;
      error?: string;
    }>('/chat/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }, token),

  history: (sessionId: string, token: string) =>
    request<{ session_id: string; messages: any[] }>(`/chat/history/${sessionId}`, {}, token),

  modelStatus: (token: string) =>
    request<{ mode: string; is_local: boolean; local_available: boolean }>('/chat/model-status', {}, token),
};

// ── Analysis ────────────────────────────────────────────────────────────
export const analysisAPI = {
  detectMissing: (formData: FormData, token: string) =>
    request<{ total: number; responded: number; missing_count: number; missing_names: string[] }>(
      '/analysis/missing-responses', { method: 'POST', body: formData }, token
    ),

  analyzeResponses: (formData: FormData, token: string) =>
    request<{
      total_students: number;
      yes_count: number;
      no_count: number;
      no_response_count: number;
      yes_students: string[];
      no_students: string[];
      no_response_students: string[];
    }>('/analysis/responses', { method: 'POST', body: formData }, token),

  compareLists: (formData: FormData, token: string) =>
    request<{
      only_in_a: string[];
      only_in_b: string[];
      in_both: string[];
      count_only_in_a: number;
      count_only_in_b: number;
      count_in_both: number;
    }>('/analysis/compare-lists', { method: 'POST', body: formData }, token),
};

// ── Deadlines ───────────────────────────────────────────────────────────
export const deadlinesAPI = {
  create: (data: any, token: string) =>
    request('/deadlines/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }, token),

  list: (token: string) => request<any[]>('/deadlines/', {}, token),

  notifications: (token: string) => request<any[]>('/deadlines/notifications', {}, token),

  markRead: (id: string, token: string) =>
    request(`/deadlines/notifications/${id}/read`, { method: 'PUT' }, token),
};

// ── Admin ───────────────────────────────────────────────────────────────
export const adminAPI = {
  users: (token: string) => request<any[]>('/admin/users', {}, token),

  updateUser: (id: string, data: any, token: string) =>
    request(`/admin/users/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }, token),

  apiUsageSummary: (token: string) => request<any>('/admin/api-usage/summary', {}, token),

  recentUsage: (token: string) => request<any[]>('/admin/api-usage/recent', {}, token),

  auditLogs: (token: string) => request<any[]>('/admin/audit-logs', {}, token),
};

export { APIError };
