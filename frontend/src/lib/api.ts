const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface VerdictCitation {
  source: string;
  page: number | null;
  section: string | null;
  snippet: string;
  is_official: boolean;
}

export interface VerdictConflict {
  description: string;
  resolution: string;
}

export interface JudgeVerdict {
  query_id: string;
  verdict: string;
  confidence: number;
  reasoning_chain: string | null;
  citations: VerdictCitation[];
  conflicts: VerdictConflict[] | null;
  follow_up_hint: string | null;
}

export async function fetcher<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "An error occurred" }));
    throw new Error(error.detail || `Error ${res.status}`);
  }

  return res.json();
}

export const api = {
  createSession: async (data: { game_name: string; persona?: string; system_prompt_override?: string }) => {
    return fetcher<{ id: string; game_name: string }>("/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  listRulesets: async () => {
    return fetcher<
      Array<{
        id: string;
        game_name: string;
        status: string;
        created_at: string | null;
        chunk_count: number;
        filename: string;
        session_id: string;
      }>
    >("/rulesets");
  },

  uploadRuleset: async (sessionId: string, formData: FormData) => {
    // Note: Don't set Content-Type header manually for FormData, fetch handles it
    const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/rulesets`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("Upload failed");
    return res.json();
  },
  
  getRulesetStatus: async (rulesetId: string) => {
    return fetcher<{ status: string; chunk_count?: number; message?: string }>(
      `/rulesets/${rulesetId}/status`
    );
  },

  listAgents: async () => {
    const res = await fetch(`${API_BASE_URL}/sessions?persona_only=true`);
    if (!res.ok) throw new Error("Failed to fetch agents");
    return res.json() as Promise<Array<{
      id: string;
      game_name: string;
      persona: string | null;
      system_prompt_override: string | null;
      created_at: string;
      active_ruleset_ids: string[] | null;
    }>>;
  },

  submitQuery: async (data: { session_id: string; query: string; ruleset_ids?: string[] }) => {
    return fetcher<JudgeVerdict>("/judge", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};
