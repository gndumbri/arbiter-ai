"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, ArrowLeft, Bot, Swords } from "lucide-react";
import Textarea from "react-textarea-autosize";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./MessageBubble";
import { CitationViewer } from "./CitationViewer";
import { api, type JudgeHistoryTurn, type JudgeVerdict, type VerdictCitation, type SessionSummary } from "@/lib/api";
import Link from "next/link";
import { useToast } from "@/hooks/use-toast";
import useSWR from "swr";

interface ChatInterfaceProps {
  sessionId: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  verdict?: JudgeVerdict;
}

function buildJudgeHistory(messages: Message[]): JudgeHistoryTurn[] {
  return messages
    .filter((message) => message.id !== "welcome")
    .slice(-6)
    .map((message) => ({
      role: message.role,
      content: message.content.trim().slice(0, 1000),
    }))
    .filter((turn) => turn.content.length > 0);
}

export function ChatInterface({ sessionId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "⚖️ The Arbiter is in session. State your rules question, and I shall deliver a verdict — with citations, not opinions."
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<VerdictCitation | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  // WHY: Fetch a single session for reliable game/NPC context and ruling tagging.
  const { data: sessionMeta } = useSWR(
    sessionId ? ["session", sessionId] : null,
    () => api.getSession(sessionId),
    {
      onError: () => {},
      revalidateOnFocus: false,
    }
  );

  // Fallback list keeps compatibility if single-session lookup fails.
  const { data: sessions } = useSWR("sessions", () => api.listSessions(), {
    onError: () => {},
  });
  const fallbackMeta = sessions?.find((s: SessionSummary) => s.id === sessionId);
  const resolvedSession = sessionMeta ?? fallbackMeta;
  const gameName = resolvedSession?.game_name;
  const persona = resolvedSession?.persona?.trim() || null;
  const npcDetail = resolvedSession?.system_prompt_override?.trim() || null;
  const headerTitle = gameName || "Unknown Game Session";
  const personaLine = persona
    ? `NPC Persona: ${persona}`
    : "NPC Persona: Default Arbiter";

  useEffect(() => {
    if (scrollRef.current) {
        const viewport = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
        if (viewport) {
             viewport.scrollTop = viewport.scrollHeight;
        }
    }
  }, [messages]);


  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const history = buildJudgeHistory([...messages, userMsg]);
      const response = await api.submitQuery({
        session_id: sessionId,
        query: userMsg.content,
        history,
      }) as JudgeVerdict;

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.verdict,
        verdict: response,
      };

      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to get a verdict. Please try again.";
      toast({
        title: "The Arbiter Hit a Snag",
        description: message,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFollowUp = (question: string) => {
    setInput(question);
    // Auto-submit follow-up
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: question,
    };
    const history = buildJudgeHistory([...messages, userMsg]);
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);
    api.submitQuery({ session_id: sessionId, query: question, history })
      .then((response) => {
        const aiMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: response.verdict,
          verdict: response,
        };
        setMessages(prev => [...prev, aiMsg]);
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : "Failed to get a verdict. Please try again.";
        toast({
          title: "The Arbiter Hit a Snag",
          description: message,
          variant: "destructive",
        });
      })
      .finally(() => {
        setIsLoading(false);
        setInput("");
      });
  };

  return (
    <div className="flex h-screen flex-col bg-background/50">
      <header className="border-b bg-background/90">
        <div className="mx-auto flex h-14 w-full max-w-4xl items-center gap-3 px-3 sm:h-[60px] sm:px-5">
          <Link href="/dashboard">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold sm:text-base" title={headerTitle}>
              {headerTitle}
            </p>
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground sm:text-xs">
              <span className="inline-flex items-center gap-1">
                <Swords className="h-3 w-3" />
                {gameName || "Game unknown"}
              </span>
              <span className="inline-flex items-center gap-1 truncate">
                <Bot className="h-3 w-3" />
                <span className="truncate" title={personaLine}>
                  {personaLine}
                </span>
              </span>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-hidden relative">
          <div className="mx-auto h-full w-full max-w-4xl">
            <ScrollArea className="h-full px-3 py-4 sm:px-5" ref={scrollRef}>
              {!!npcDetail && (
                <div className="mb-4 rounded-md border border-border/60 bg-card/60 px-3 py-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">NPC Directive:</span>{" "}
                  <span className="line-clamp-2">{npcDetail}</span>
                </div>
              )}
              <div className="space-y-4 pb-4">
                {messages.map((msg) => (
                  <MessageBubble
                    key={msg.id}
                    message={msg}
                    gameName={gameName}
                    sessionId={sessionId}
                    onCitationClick={setSelectedCitation}
                    onFollowUp={handleFollowUp}
                  />
                ))}
                {isLoading && (
                  <div className="flex w-full px-4 justify-start">
                    <div className="flex items-center gap-2 rounded-lg bg-muted p-4 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Consulting the tomes...
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
           
          {selectedCitation && (
             <CitationViewer 
                citation={selectedCitation} 
                onClose={() => setSelectedCitation(null)} 
             />
          )}
      </div>

      <div className="border-t bg-background/95">
        <div className="mx-auto w-full max-w-4xl p-3 sm:p-5">
          <form onSubmit={handleSubmit} className="flex gap-3 sm:gap-4">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="State your case, adventurer..."
              className="flex-1 min-h-[50px] max-h-[200px] resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            />
            <Button type="submit" disabled={isLoading || !input.trim()}>
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              <span className="sr-only">Send</span>
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
