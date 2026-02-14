/**
 * API client for communicating with the Arbiter AI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RequestOptions extends RequestInit {
  token?: string;
}

/**
 * Make an authenticated API request.
 */
async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { token, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: { code: "UNKNOWN", message: response.statusText },
    }));
    throw new ApiError(response.status, error.error);
  }

  return response.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: { code: string; message: string }
  ) {
    super(detail.message);
    this.name = "ApiError";
  }
}

// ─── Health ──────────────────────────────────────────────────────────────────

export async function getHealth() {
  return apiRequest<{
    status: string;
    database: string;
    redis: string;
    version: string;
  }>("/health");
}

// ─── Sessions ────────────────────────────────────────────────────────────────

export async function createSession(token: string, gameName: string) {
  return apiRequest<{
    id: string;
    user_id: string;
    game_name: string;
    created_at: string;
    expires_at: string;
  }>("/api/v1/sessions", {
    method: "POST",
    token,
    body: JSON.stringify({ game_name: gameName }),
  });
}

// ─── Judge ───────────────────────────────────────────────────────────────────

export interface JudgeVerdict {
  verdict: string;
  reasoning_chain: string | null;
  confidence: number;
  confidence_reason: string | null;
  citations: Array<{
    source: string;
    page: number | null;
    section: string | null;
    snippet: string;
    is_official: boolean;
  }>;
  conflicts: Array<{
    description: string;
    resolution: string;
  }> | null;
  follow_up_hint: string | null;
  query_id: string;
}

export async function submitQuery(
  token: string,
  sessionId: string,
  query: string
) {
  return apiRequest<JudgeVerdict>("/api/v1/judge", {
    method: "POST",
    token,
    body: JSON.stringify({ session_id: sessionId, query }),
  });
}

export async function submitFeedback(
  token: string,
  queryId: string,
  feedback: "up" | "down"
) {
  return apiRequest<{ status: string }>(
    `/api/v1/judge/${queryId}/feedback`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ feedback }),
    }
  );
}
