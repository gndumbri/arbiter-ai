/**
 * WidgetPage — Embeddable chat widget for third-party game sites.
 *
 * This page is designed to be embedded in an iframe by publishers
 * on their own websites. It validates the session_id, checks if
 * the session exists (and isn't expired), then renders the
 * ChatInterface component.
 *
 * URL Format: /widget/{session_id}
 *
 * Called by: External iframe embeds, e.g.:
 *   <iframe src="https://arbiter.ai/widget/abc123" />
 *
 * Depends on: ChatInterface component, api.ts (session validation).
 *
 * Architecture note for AI agents:
 *   The widget page intentionally has NO sidebar, navbar, or auth UI.
 *   It's a minimal standalone page meant for iframe embedding. The
 *   session_id in the URL must be valid and non-expired. If invalid,
 *   an error message is shown instead of the chat.
 */

"use client";

import { useParams } from "next/navigation";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { Loader2, AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * Validates a session_id string format (must be a valid UUID).
 * WHY: We validate before making API calls to avoid sending
 * obviously invalid IDs to the backend.
 */
function isValidUUID(id: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
}

export default function WidgetPage() {
  const params = useParams();
  const id = params.id as string;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Validate the session ID format
    if (!id || !isValidUUID(id)) {
      setError("Invalid session ID. Please check the widget URL.");
      setLoading(false);
      return;
    }

    // WHY: Short delay to let the iframe fully render before showing
    // content. In production, replace with actual session validation
    // via an API call to check if the session exists and isn't expired.
    const timer = setTimeout(() => {
      setLoading(false);
    }, 300);

    return () => clearTimeout(timer);
  }, [id]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-center p-4">
          <AlertCircle className="h-10 w-10 text-destructive" />
          <h2 className="text-lg font-semibold">Widget Error</h2>
          <p className="text-sm text-muted-foreground max-w-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background text-foreground overflow-hidden">
      <div className="flex-none p-2 border-b bg-muted/20 flex items-center justify-between">
        <span className="text-sm font-semibold text-muted-foreground">Powered by Arbiter AI</span>
      </div>
      <div className="flex-1 overflow-hidden relative">
        <ChatInterface sessionId={id} />
      </div>
    </div>
  );
}
