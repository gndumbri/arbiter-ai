/**
 * EnvironmentBadge.tsx — Floating badge showing the active environment mode.
 *
 * Displays a small, color-coded badge in the bottom-left corner of the app:
 *   - 🟠 Orange  "MOCK"    → All data is fake, no real API calls
 *   - 🔵 Blue    "SANDBOX" → Real DB, sandbox API keys (Stripe test mode)
 *   - (Hidden)   PROD      → Not shown in production
 *
 * HOW IT WORKS:
 *   On mount, calls GET /health and reads the "mode" field from the response.
 *   Falls back to reading the X-Arbiter-Env header if "mode" isn't in the body.
 *   The badge only renders in non-production environments.
 *
 * WHY:
 *   Developers need a constant visual indicator of which backend tier they're
 *   hitting. Without this, it's easy to accidentally test against production
 *   or wonder why data looks different. The badge is always visible but
 *   intentionally unobtrusive so it doesn't interfere with UI development.
 *
 * Called by: dashboard/layout.tsx (rendered in the root layout)
 * Depends on: Backend /health endpoint (returns { mode: "mock" | "sandbox" | "production" })
 */

"use client";

import { useEffect, useState } from "react";

/** ─── Configuration ──────────────────────────────────────────────────────── */

const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL?.trim();
const API_BASE = RAW_API_URL
  ? RAW_API_URL.replace(/\/api\/v1\/?$/, "")
  // Production fallback is same-origin (empty base) to avoid hardcoded localhost
  // in deployed browser bundles. Dev keeps localhost for local backend workflows.
  : (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

/**
 * Badge styling per environment mode.
 *
 * Each mode gets a distinct color so developers can identify the tier
 * at a glance without reading the text. Colors are chosen for contrast
 * against both light and dark backgrounds.
 */
const MODE_STYLES: Record<
  string,
  { bg: string; text: string; border: string; label: string; emoji: string }
> = {
  mock: {
    bg: "rgba(245, 158, 11, 0.15)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.4)",
    label: "MOCK",
    emoji: "🎭",
  },
  sandbox: {
    bg: "rgba(59, 130, 246, 0.15)",
    text: "#3b82f6",
    border: "rgba(59, 130, 246, 0.4)",
    label: "SANDBOX",
    emoji: "🧪",
  },
  // Production mode — badge is hidden entirely (see early return below)
  production: {
    bg: "transparent",
    text: "transparent",
    border: "transparent",
    label: "PRODUCTION",
    emoji: "🚀",
  },
};

/** ─── Component ──────────────────────────────────────────────────────────── */

export default function EnvironmentBadge() {
  const [mode, setMode] = useState<string | null>(null);

  useEffect(() => {
    /**
     * Detect the active environment mode from the backend.
     *
     * Strategy:
     *   1. Call GET /health (lightweight, no auth needed)
     *   2. Read the "mode" field from the JSON response body
     *   3. Fallback: read the X-Arbiter-Env response header
     *   4. If all else fails, don't render the badge
     */
    async function detectMode() {
      try {
        const res = await fetch(`${API_BASE}/health`, {
          // WHY: cache: "no-store" ensures we always get the current mode,
          // not a stale cached response from a previous server restart.
          cache: "no-store",
        });

        // Try to read mode from response body (mock health endpoint includes it)
        const data = await res.json();
        if (data.mode) {
          setMode(data.mode);
          return;
        }

        // Fallback: read X-Arbiter-Env header (set by EnvironmentMiddleware)
        const envHeader = res.headers.get("X-Arbiter-Env");
        if (envHeader) {
          setMode(envHeader);
          return;
        }

        // If no mode info available, assume production (don't show badge)
        setMode("production");
      } catch {
        // WHY: If /health fails, the backend is probably down.
        // Don't show a badge — the user will see other error indicators.
        setMode(null);
      }
    }

    detectMode();
  }, []);

  // ─── Don't render in production or when mode is unknown ────────────────
  if (!mode || mode === "production") {
    return null;
  }

  const style = MODE_STYLES[mode] || MODE_STYLES.mock;

  return (
    <div
      style={{
        position: "fixed",
        bottom: "16px",
        left: "16px",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        gap: "6px",
        padding: "6px 12px",
        borderRadius: "20px",
        fontSize: "11px",
        fontWeight: 700,
        fontFamily:
          'ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace',
        letterSpacing: "0.05em",
        color: style.text,
        backgroundColor: style.bg,
        border: `1px solid ${style.border}`,
        backdropFilter: "blur(8px)",
        // WHY: pointer-events: none so the badge doesn't interfere with
        // clicking elements underneath it. Developers can't accidentally
        // click the badge when testing interactive UI elements.
        pointerEvents: "none",
        userSelect: "none",
        transition: "opacity 0.3s ease",
      }}
      // WHY: aria-hidden because this is a developer tool, not user-facing
      // content. Screen readers should ignore it entirely.
      aria-hidden="true"
      data-testid="environment-badge"
    >
      <span>{style.emoji}</span>
      <span>{style.label}</span>
    </div>
  );
}
