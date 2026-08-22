const TOKEN_KEY = "search_admin_token";

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
  if (auth && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail ?? JSON.stringify(payload);
    } catch {
      // ignore parse errors
    }
    throw new ApiError(String(detail), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  login(username: string, password: string) {
    const body = new URLSearchParams({ username, password });
    return request<{ access_token: string; token_type: string }>(
      "/api/v1/account/token",
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      },
      false,
    );
  },

  health() {
    return request<import("../types").HealthResponse>("/health", {}, false);
  },

  listIndexes(orgId: string, skip = 0, limit = 50) {
    const params = new URLSearchParams({
      org_id: orgId,
      skip: String(skip),
      limit: String(limit),
    });
    return request<{ results: import("../types").SearchIndex[]; count: number }>(
      `/api/v1/index/list?${params}`,
    );
  },

  getIndex(indexId: string) {
    return request<import("../types").IndexDetailResponse>(
      `/api/v1/index/${indexId}`,
    );
  },

  createIndex(payload: Record<string, string | null | undefined>) {
    return request<{
      message: string;
      id: string;
      documents_indexed: number;
      vector_backend: string;
    }>("/api/v1/index/create", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  deleteIndex(indexId: string) {
    return request<{ message: string; id: string }>(
      `/api/v1/index/${indexId}`,
      { method: "DELETE" },
    );
  },

  search(
    indexId: string,
    payload: {
      query: string;
      mode: import("../types").SearchMode;
      top_k: number;
      offset?: number;
      org_id?: string | null;
      vector_weight?: number;
    },
  ) {
    return request<{
      results: import("../types").SearchResult[];
      mode: string;
      total_returned: number;
    }>(`/api/v1/search/${indexId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listUsers(skip = 0, limit = 100) {
    const params = new URLSearchParams({
      skip: String(skip),
      limit: String(limit),
    });
    return request<{ results: import("../types").UserRecord[]; count: number }>(
      `/api/v1/account/users?${params}`,
    );
  },

  createUser(payload: Record<string, string | number | null | undefined>) {
    return request<{ message: string; user: string }>("/api/v1/account/user/create", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listOrganizations(skip = 0, limit = 100) {
    const params = new URLSearchParams({
      skip: String(skip),
      limit: String(limit),
    });
    return request<{
      results: import("../types").OrganizationRecord[];
      count: number;
    }>(`/api/v1/account/organizations?${params}`);
  },

  createOrganization(payload: Record<string, string | null | undefined>) {
    return request<{ message: string; organization: string }>(
      "/api/v1/account/organization/create",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  info(auth = true) {
    return request<{ user: string; version: string; message: string }>(
      "/api/v1/info",
      {},
      auth,
    );
  },

  multimodalStatus() {
    return request<import("../types").MultimodalStatus>("/api/v1/multimodal/status");
  },

  createMultimodalIndex(payload: {
    title: string;
    org_id: string;
    description?: string;
  }) {
    return request<{ id: string; message: string }>("/api/v1/multimodal/index/create", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  uploadMultimodalImages(indexId: string, files: File[], orgId?: string) {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    if (orgId) form.append("org_id", orgId);
    return request<{ message: string; indexed: Record<string, unknown>[] }>(
      `/api/v1/multimodal/${indexId}/images`,
      { method: "POST", body: form },
      true,
      true,
    );
  },

  indexMultimodalDirectory(
    indexId: string,
    directoryPath: string,
    pattern = "*.jpg",
    orgId?: string,
  ) {
    const form = new FormData();
    form.append("directory_path", directoryPath);
    form.append("pattern", pattern);
    if (orgId) form.append("org_id", orgId);
    return request<{ message: string; documents_indexed: number }>(
      `/api/v1/multimodal/${indexId}/images/directory`,
      { method: "POST", body: form },
      true,
      true,
    );
  },

  multimodalSearch(
    indexId: string,
    queryText: string,
    queryImage: File | null,
    topK = 9,
    orgId?: string,
  ) {
    const form = new FormData();
    form.append("query_text", queryText);
    form.append("top_k", String(topK));
    if (queryImage) form.append("query_image", queryImage);
    if (orgId) form.append("org_id", orgId);
    return request<{ results: Record<string, unknown>[]; query_type: string }>(
      `/api/v1/multimodal/${indexId}/search`,
      { method: "POST", body: form },
      true,
      true,
    );
  },

  multimodalSearchRerank(
    indexId: string,
    queryText: string,
    queryImage: File,
    topK = 9,
    orgId?: string,
  ) {
    const form = new FormData();
    form.append("query_text", queryText);
    form.append("top_k", String(topK));
    form.append("query_image", queryImage);
    if (orgId) form.append("org_id", orgId);
    return request<import("../types").MultimodalRerankResponse>(
      `/api/v1/multimodal/${indexId}/search/rerank`,
      { method: "POST", body: form },
      true,
      true,
    );
  },
};
