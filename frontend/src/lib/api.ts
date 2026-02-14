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
  model: string;
}

export interface Ruleset {
  id: string;
  game_name: string;
  status: string;
  created_at: string | null;
  chunk_count: number;
  filename: string;
  session_id: string;
}

export interface CatalogEntry {
  id: string;
  game_name: string;
  game_slug: string;
  publisher_name: string;
  version: string;
  status: string;
}

export interface PartyResponse {
  id: string;
  name: string;
  owner_id: string;
  member_count: number;
  created_at: string | null;
}

export interface PartyMemberResponse {
  user_id: string;
  role: string;
  joined_at: string | null;
}

export interface SavedRulingResponse {
  id: string;
  query: string;
  verdict_json: JudgeVerdict;
  privacy_level: string;
  tags: string[] | null;
  created_at: string | null;
}

export interface Agent {
  id: string;
  game_name: string;
  persona: string | null;
  system_prompt_override: string | null;
  created_at: string;
  active_ruleset_ids: string[] | null;
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
  // ─── Sessions ───────────────────────────────────────────────────────────────
  createSession: async (data: { game_name: string; persona?: string; system_prompt_override?: string }) => {
    return fetcher<{ id: string; game_name: string }>("/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // ─── Rulesets ───────────────────────────────────────────────────────────────
  listRulesets: async () => {
    return fetcher<Ruleset[]>("/rulesets");
  },

  uploadRuleset: async (sessionId: string, formData: FormData) => {
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

  // ─── Agents ─────────────────────────────────────────────────────────────────
  listAgents: async () => {
    const res = await fetch(`${API_BASE_URL}/sessions?persona_only=true`);
    if (!res.ok) throw new Error("Failed to fetch agents");
    return res.json() as Promise<Agent[]>;
  },

  // ─── Judge ──────────────────────────────────────────────────────────────────
  submitQuery: async (data: { session_id: string; query: string; ruleset_ids?: string[] }) => {
    return fetcher<JudgeVerdict>("/judge", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // ─── Game Catalog ───────────────────────────────────────────────────────────
  listCatalog: async () => {
    return fetcher<CatalogEntry[]>("/catalog/");
  },

  // ─── Parties ────────────────────────────────────────────────────────────────
  listParties: async () => {
    return fetcher<PartyResponse[]>("/parties");
  },

  createParty: async (name: string) => {
    return fetcher<PartyResponse>("/parties", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },

  getPartyMembers: async (partyId: string) => {
    return fetcher<PartyMemberResponse[]>(`/parties/${partyId}/members`);
  },

  joinParty: async (partyId: string) => {
    return fetcher<{ party_id: string; status: string }>(`/parties/${partyId}/join`, {
      method: "POST",
    });
  },

  leaveParty: async (partyId: string) => {
    return fetcher<{ party_id: string; status: string }>(`/parties/${partyId}/leave`, {
      method: "POST",
    });
  },

  deleteParty: async (partyId: string) => {
    const res = await fetch(`${API_BASE_URL}/parties/${partyId}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error("Failed to delete party");
  },

  // ─── Saved Rulings ─────────────────────────────────────────────────────────
  listRulings: async () => {
    return fetcher<SavedRulingResponse[]>("/rulings");
  },

  listPublicRulings: async () => {
    return fetcher<SavedRulingResponse[]>("/rulings/public");
  },

  saveRuling: async (data: { query: string; verdict_json: Record<string, unknown>; privacy_level?: string; tags?: string[] }) => {
    return fetcher<SavedRulingResponse>("/rulings", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateRulingPrivacy: async (rulingId: string, privacyLevel: string) => {
    return fetcher<{ id: string; privacy_level: string }>(`/rulings/${rulingId}/privacy`, {
      method: "PATCH",
      body: JSON.stringify({ privacy_level: privacyLevel }),
    });
  },

  deleteRuling: async (rulingId: string) => {
    const res = await fetch(`${API_BASE_URL}/rulings/${rulingId}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) throw new Error("Failed to delete ruling");
  },
};
