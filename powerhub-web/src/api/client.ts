const TOKEN_KEY = "powerhub_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true,
  isFormData = false,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!isFormData && !headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (auth && token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail ?? JSON.stringify(payload);
    } catch {
      /* ignore */
    }
    throw new ApiError(String(detail), response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type User = {
  user_id: string;
  username: string;
  full_name?: string | null;
  email?: string | null;
  organization_id?: string | null;
  role?: string | null;
  capabilities: string[];
};

export type OrgSettings = {
  org_id: string;
  allowed_domains: string;
  allow_public_email: boolean;
  recycle_retention_days: number;
  storage_quota_bytes: number;
  storage_used_bytes: number;
  default_embedding_model: string;
  default_chunk_size: number;
  default_chunk_overlap: number;
  embedding_model_choices: string[];
};

export const api = {
  loginPassword(email: string, password: string) {
    return request<{ access_token: string; user: User }>(
      "/api/v1/powerhub/auth/password",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    );
  },
  requestCode(email: string) {
    return request<{ demo_code: string; message: string; demo_link: string }>(
      "/api/v1/powerhub/auth/email/request",
      { method: "POST", body: JSON.stringify({ email }) },
      false,
    );
  },
  verifyCode(email: string, code: string) {
    return request<{ access_token: string; user: User }>(
      "/api/v1/powerhub/auth/email/verify",
      { method: "POST", body: JSON.stringify({ email, code }) },
      false,
    );
  },
  me() {
    return request<User>("/api/v1/powerhub/me");
  },
  updateProfile(payload: { full_name?: string; password?: string }) {
    return request<User>("/api/v1/powerhub/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  dashboard() {
    return request<Record<string, unknown>>("/api/v1/powerhub/dashboard");
  },
  library(folderId?: string | null) {
    const params = new URLSearchParams();
    if (folderId) params.set("folder_id", folderId);
    const q = params.toString();
    return request<{
      folder: Record<string, unknown> | null;
      breadcrumbs: Array<Record<string, unknown>>;
      folders: Array<Record<string, unknown>>;
      files: Array<Record<string, unknown>>;
    }>(`/api/v1/powerhub/library${q ? `?${q}` : ""}`);
  },
  createFolder(name: string, parentId?: string | null) {
    return request("/api/v1/powerhub/folders", {
      method: "POST",
      body: JSON.stringify({ name, parent_id: parentId ?? null }),
    });
  },
  uploadFile(file: File, folderId?: string | null) {
    const form = new FormData();
    form.append("file", file);
    const params = new URLSearchParams();
    if (folderId) params.set("folder_id", folderId);
    const q = params.toString();
    return request(`/api/v1/powerhub/files/upload${q ? `?${q}` : ""}`, {
      method: "POST",
      body: form,
    }, true, true);
  },
  downloadUrl(fileId: string) {
    return `/api/v1/powerhub/files/${fileId}/download`;
  },
  renameFile(fileId: string, name: string) {
    return request(`/api/v1/powerhub/files/${fileId}/rename`, {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },
  starFile(fileId: string) {
    return request(`/api/v1/powerhub/files/${fileId}/star`, { method: "POST" });
  },
  deleteFile(fileId: string) {
    return request(`/api/v1/powerhub/files/${fileId}`, { method: "DELETE" });
  },
  deleteFolder(folderId: string) {
    return request(`/api/v1/powerhub/folders/${folderId}`, { method: "DELETE" });
  },
  search(q: string, kind?: string) {
    const params = new URLSearchParams({ q });
    if (kind) params.set("kind", kind);
    return request<Array<Record<string, unknown>>>(`/api/v1/powerhub/search?${params}`);
  },
  shares(scope: "mine" | "all" = "mine") {
    return request<Array<Record<string, unknown>>>(`/api/v1/powerhub/shares?scope=${scope}`);
  },
  createShare(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>("/api/v1/powerhub/shares", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  revokeShare(id: string) {
    return request(`/api/v1/powerhub/shares/${id}`, { method: "DELETE" });
  },
  listAccess(itemType: string, itemId: string) {
    return request<Array<Record<string, unknown>>>(
      `/api/v1/powerhub/access/${itemType}/${itemId}`,
    );
  },
  grantAccess(payload: Record<string, unknown>) {
    return request("/api/v1/powerhub/access", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  recycle() {
    return request<Array<Record<string, unknown>>>("/api/v1/powerhub/recycle");
  },
  restore(itemType: string, itemId: string) {
    return request(`/api/v1/powerhub/recycle/${itemType}/${itemId}/restore`, {
      method: "POST",
    });
  },
  purge(itemType: string, itemId: string) {
    return request(`/api/v1/powerhub/recycle/${itemType}/${itemId}`, {
      method: "DELETE",
    });
  },
  notifications() {
    return request<Array<Record<string, unknown>>>("/api/v1/powerhub/notifications");
  },
  markNotificationsRead() {
    return request("/api/v1/powerhub/notifications/read-all", { method: "POST" });
  },
  settings() {
    return request<OrgSettings>("/api/v1/powerhub/settings");
  },
  updateSettings(payload: {
    allowed_domains?: string;
    allow_public_email?: boolean;
    recycle_retention_days?: number;
    default_embedding_model?: string;
    default_chunk_size?: number;
    default_chunk_overlap?: number;
  }) {
    return request("/api/v1/powerhub/settings", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  users() {
    return request<{ results: User[]; count: number }>("/api/v1/powerhub/users");
  },
  audit() {
    return request<Array<Record<string, unknown>>>("/api/v1/powerhub/audit");
  },
  groups() {
    return request<Array<Record<string, unknown>>>("/api/v1/powerhub/groups");
  },
  createGroup(name: string, description?: string) {
    return request("/api/v1/powerhub/groups", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  },
  indexes() {
    return request<Array<Record<string, unknown>>>("/api/v1/powerhub/indexes");
  },
  foldersForIndex() {
    return request<
      Array<{ id: string; name: string; path: string; file_count: number }>
    >("/api/v1/powerhub/folders");
  },
  createIndex(payload: {
    title: string;
    description?: string;
    folder_id: string;
    embedding_model?: string;
    chunk_size?: number;
    chunk_overlap?: number;
  }) {
    return request<Record<string, unknown>>("/api/v1/powerhub/indexes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteIndex(id: string) {
    return request(`/api/v1/powerhub/indexes/${id}`, { method: "DELETE" });
  },
  syncIndex(id: string) {
    return request<Record<string, unknown>>(`/api/v1/powerhub/indexes/${id}/sync`, {
      method: "POST",
    });
  },
  getIndex(id: string) {
    return request<Record<string, unknown>>(`/api/v1/powerhub/indexes/${id}`);
  },
  searchIndex(linkId: string, query: string, mode = "full_text", topK = 10) {
    return request<Record<string, unknown>>(`/api/v1/powerhub/indexes/${linkId}/search`, {
      method: "POST",
      body: JSON.stringify({ query, mode, top_k: topK }),
    });
  },
  publicShare(token: string) {
    return request<Record<string, unknown>>(`/api/v1/powerhub/public/share/${token}`, {}, false);
  },
};
