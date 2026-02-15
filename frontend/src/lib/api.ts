/**
 * api.ts — Typed API client for Arbiter AI backend.
 *
 * All methods auto-attach the NextAuth JWT as a Bearer token.
 * Uses the NEXT_PUBLIC_API_URL env var or defaults to localhost:8000.
 *
 * Called by: All frontend pages and components that fetch data.
 * Depends on: next-auth (getSession), backend /api/v1/* endpoints.
 */

import { getSession } from "next-auth/react";

const RAW_API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, "").endsWith("/api/v1")
  ? RAW_API_BASE_URL.replace(/\/+$/, "")
  : `${RAW_API_BASE_URL.replace(/\/+$/, "")}/api/v1`;

// ─── Types ──────────────────────────────────────────────────────────────────

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

export interface JudgeHistoryTurn {
  role: "user" | "assistant";
  content: string;
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
  license_type?: string;
  attribution_text?: string;
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
  user_name?: string | null;
  user_email?: string | null;
  role: string;
  joined_at: string | null;
}

export interface SavedRulingResponse {
  id: string;
  query: string;
  verdict_json: JudgeVerdict;
  game_name: string | null;
  session_id: string | null;
  privacy_level: string;
  tags: string[] | null;
  created_at: string | null;
}

export interface GameRulingCount {
  game_name: string;
  count: number;
}

export interface AdminStats {
  total_users: number;
  total_sessions: number;
  total_queries: number;
  total_rulesets: number;
  total_publishers: number;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string | null;
  role: string;
  created_at: string | null;
}

export interface AdminPublisher {
  id: string;
  name: string;
  slug: string;
  contact_email: string;
  verified: boolean;
  created_at: string | null;
}

export interface AdminTier {
  id: string;
  name: string;
  daily_query_limit: number;
}

export interface Agent {
  id: string;
  game_name: string;
  persona: string | null;
  system_prompt_override: string | null;
  created_at: string;
  active_ruleset_ids: string[] | null;
}

export interface SessionSummary {
  id: string;
  game_name: string;
  persona: string | null;
  system_prompt_override: string | null;
  active_ruleset_ids: string[] | null;
  created_at: string;
  expires_at: string;
}

export interface LibraryEntry {
  id: string;
  game_name: string;
  game_slug: string;
  added_from_catalog: boolean;
  official_ruleset_id: string | null;
  official_ruleset_ids: string[] | null;
  personal_ruleset_ids: string[] | null;
  is_favorite: boolean;
  favorite: boolean;
  last_queried: string | null;
  created_at: string;
}

// ─── Auth Helper ────────────────────────────────────────────────────────────

/**
 * Get the current NextAuth JWT for API requests.
 * Returns the raw JWT string from the session, or null if unauthenticated.
 */
async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const session = await getSession();
    const sessionAccessToken = (session as { accessToken?: string } | null)?.accessToken;
    if (sessionAccessToken) {
      return { Authorization: `Bearer ${sessionAccessToken}` };
    }
    if (session) {
      // Backward-compatible fallback for older session callback payloads.
      const res = await fetch("/api/auth/session", { cache: "no-store" });
      const sessionData = await res.json();
      if (sessionData?.accessToken) {
        return { Authorization: `Bearer ${sessionData.accessToken}` };
      }
    }
  } catch {
    // Session fetch failed — continue without auth
  }
  return {};
}

// ─── Core Fetcher ───────────────────────────────────────────────────────────

export async function fetcher<T>(url: string, options?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();

  const res = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    credentials: "include", // Include cookies for NextAuth session
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => null);
    const detail = error?.detail ?? error?.error ?? error;

    let message = `Error ${res.status}`;
    if (typeof detail === "string" && detail.trim()) {
      message = detail;
    } else if (detail && typeof detail === "object") {
      const detailObj = detail as {
        message?: unknown;
        detail?: unknown;
        code?: unknown;
      };
      if (typeof detailObj.message === "string" && detailObj.message.trim()) {
        message = detailObj.message;
      } else if (typeof detailObj.detail === "string" && detailObj.detail.trim()) {
        message = detailObj.detail;
      } else if (typeof detailObj.code === "string" && detailObj.code.trim()) {
        message = detailObj.code;
      }
    }

    throw new Error(message);
  }

  // 204/205 responses intentionally have no body.
  if (res.status === 204 || res.status === 205) {
    return undefined as T;
  }

  const text = await res.text();
  if (!text) {
    return undefined as T;
  }

  return JSON.parse(text) as T;
}

/**
 * Fetch with FormData (file uploads). Does NOT set Content-Type
 * header — the browser sets it with the boundary automatically.
 */
async function fetchMultipart<T>(url: string, formData: FormData): Promise<T> {
  const authHeaders = await getAuthHeaders();

  const res = await fetch(`${API_BASE_URL}${url}`, {
    method: "POST",
    credentials: "include",
    headers: {
      ...authHeaders,
    },
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || `Error ${res.status}`);
  }

  return res.json();
}

// ─── API Methods ────────────────────────────────────────────────────────────

export const api = {
  // ─── Sessions ───────────────────────────────────────────────────────────────
  createSession: async (data: {
    game_name: string;
    persona?: string;
    system_prompt_override?: string;
    active_ruleset_ids?: string[];
  }) => {
    return fetcher<{ id: string; game_name: string }>("/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  listSessions: async () => {
    return fetcher<SessionSummary[]>("/sessions");
  },

  getSession: async (sessionId: string) => {
    return fetcher<SessionSummary>(`/sessions/${sessionId}`);
  },

  // ─── Rulesets ───────────────────────────────────────────────────────────────
  listRulesets: async () => {
    return fetcher<Ruleset[]>("/rulesets");
  },

  uploadRuleset: async (sessionId: string, formData: FormData) => {
    return fetchMultipart<{ ruleset_id: string; status: string }>(
      `/sessions/${sessionId}/rulesets`,
      formData
    );
  },

  getRulesetStatus: async (rulesetId: string) => {
    return fetcher<{ status: string; chunk_count?: number; message?: string }>(
      `/rulesets/${rulesetId}/status`
    );
  },

  // ─── Agents ─────────────────────────────────────────────────────────────────
  listAgents: async () => {
    return fetcher<Agent[]>("/agents");
  },

  // ─── Judge ──────────────────────────────────────────────────────────────────
  submitQuery: async (data: {
    session_id: string;
    query: string;
    ruleset_ids?: string[];
    history?: JudgeHistoryTurn[];
  }) => {
    return fetcher<JudgeVerdict>("/judge", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // ─── Game Catalog ───────────────────────────────────────────────────────────
  listCatalog: async () => {
    return fetcher<CatalogEntry[]>("/catalog/");
  },

  /**
   * Search the catalog by game name or publisher (powers the wizard Step 1).
   * Uses the ?search= ILIKE param on the backend.
   */
  searchCatalog: async (query: string) => {
    return fetcher<CatalogEntry[]>(`/catalog/?search=${encodeURIComponent(query)}`);
  },

  // ─── User Game Library ──────────────────────────────────────────────────────
  listLibrary: async () => {
    return fetcher<LibraryEntry[]>("/library");
  },

  addToLibrary: async (data: { game_slug: string; game_name: string; official_ruleset_id?: string }) => {
    return fetcher<LibraryEntry>("/library", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  removeFromLibrary: async (id: string) => {
    return fetcher<void>(`/library/${id}`, { method: "DELETE" });
  },

  startSessionFromLibrary: async (id: string) => {
    return fetcher<SessionSummary>(`/library/${id}/sessions`, {
      method: "POST",
    });
  },

  toggleFavorite: async (id: string) => {
    return fetcher<{ id: string; favorite: boolean }>(`/library/${id}/favorite`, {
      method: "PATCH",
    });
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
    return fetcher<void>(`/parties/${partyId}`, { method: "DELETE" });
  },

  getInviteLink: async (partyId: string) => {
    return fetcher<{ invite_url: string; expires_at: string }>(`/parties/${partyId}/invite`);
  },

  joinViaInvite: async (token: string) => {
    return fetcher<{ party_id: string; status: string }>("/parties/join-via-link", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
  },

  removeMember: async (partyId: string, userId: string) => {
    return fetcher<{ status: string }>(`/parties/${partyId}/members/${userId}`, {
      method: "DELETE",
    });
  },

  transferOwnership: async (partyId: string, newOwnerId: string) => {
    return fetcher<{ status: string }>(`/parties/${partyId}/owner`, {
      method: "PATCH",
      body: JSON.stringify({ new_owner_id: newOwnerId }),
    });
  },

  listGameShares: async (partyId: string) => {
    return fetcher<{ game_name: string; user_id: string }[]>(`/parties/${partyId}/game-shares`);
  },

  updateGameShares: async (partyId: string, gameNames: string[]) => {
    return fetcher<{ status: string }>(`/parties/${partyId}/game-shares`, {
      method: "PUT",
      body: JSON.stringify({ game_names: gameNames }),
    });
  },

  // ─── Saved Rulings ─────────────────────────────────────────────────────────
  listRulings: async (gameName?: string) => {
    const qs = gameName ? `?game_name=${encodeURIComponent(gameName)}` : "";
    return fetcher<SavedRulingResponse[]>(`/rulings${qs}`);
  },

  listRulingGames: async () => {
    return fetcher<GameRulingCount[]>("/rulings/games");
  },

  listPublicRulings: async () => {
    return fetcher<SavedRulingResponse[]>("/rulings/public");
  },

  listPartyRulings: async (gameName?: string) => {
    const qs = gameName ? `?game_name=${encodeURIComponent(gameName)}` : "";
    return fetcher<SavedRulingResponse[]>(`/rulings/party${qs}`);
  },

  saveRuling: async (data: {
    query: string;
    verdict_json: Record<string, unknown>;
    game_name?: string;
    session_id?: string;
    privacy_level?: string;
    tags?: string[];
  }) => {
    return fetcher<SavedRulingResponse>("/rulings", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateRuling: async (
    rulingId: string,
    data: { tags?: string[] | null; game_name?: string; privacy_level?: string }
  ) => {
    return fetcher<SavedRulingResponse>(`/rulings/${rulingId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  deleteRuling: async (rulingId: string) => {
    return fetcher<void>(`/rulings/${rulingId}`, { method: "DELETE" });
  },

  // ─── Billing ────────────────────────────────────────────────────────────────
  getSubscription: async () => {
    return fetcher<{ plan_tier: string; status: string; stripe_customer_id?: string; current_period_end?: string }>("/billing/subscription");
  },

  createCheckout: async (tier: string) => {
    return fetcher<{ checkout_url: string }>("/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ tier }),
    });
  },

  /** Open Stripe Customer Portal for managing subscription. */
  createPortalSession: async () => {
    return fetcher<{ portal_url: string }>("/billing/portal", {
      method: "POST",
    });
  },

  // ─── Admin ────────────────────────────────────────────────────────────────
  getAdminStats: async () => {
    return fetcher<AdminStats>("/admin/stats");
  },

  listAdminUsers: async () => {
    return fetcher<AdminUser[]>("/admin/users");
  },

  listAdminPublishers: async () => {
    return fetcher<AdminPublisher[]>("/admin/publishers");
  },

  listAdminTiers: async () => {
    return fetcher<AdminTier[]>("/admin/tiers");
  },

  // ─── User Profile ──────────────────────────────────────────────────────────
  getProfile: async () => {
    return fetcher<{ id: string; email: string; name: string | null; role: string; default_ruling_privacy: string }>("/users/me");
  },

  updateProfile: async (data: { name?: string; default_ruling_privacy?: string }) => {
    return fetcher<{ id: string; name: string; default_ruling_privacy: string }>("/users/me", {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  deleteAccount: async () => {
    return fetcher<void>("/users/me", { method: "DELETE" });
  },

  // ─── Agents ──────────────────────────────────────────────────────────────────
  /** List active sessions as agents (powers the agent dashboard). */
  getAgents: async () => {
    return fetcher<AgentEntry[]>("/agents");
  },
};

/** Agent entry — a session that acts as a configured rules judge. */
export interface AgentEntry {
  id: string;
  game_name: string;
  persona: string | null;
  created_at: string | null;
}
