"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, ArrowLeft } from "lucide-react";
import Textarea from "react-textarea-autosize";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./MessageBubble";
import { CitationViewer } from "./CitationViewer";
import { api, JudgeVerdict, VerdictCitation } from "@/lib/api";
import Link from "next/link";
import { useToast } from "@/hooks/use-toast";

interface ChatInterfaceProps {
  sessionId: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  verdict?: JudgeVerdict;
}

export function ChatInterface({ sessionId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hello! I am the Arbiter. Ask me any question about the rules, and I will issue a verdict based on the rulebook."
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<VerdictCitation | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

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
      const response = await api.submitQuery({
        session_id: sessionId,
        query: userMsg.content,
      }) as JudgeVerdict;

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.verdict,
        verdict: response,
      };

      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to get a verdict. Please try again.",
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
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);
    api.submitQuery({ session_id: sessionId, query: question })
      .then((response) => {
        const aiMsg: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: response.verdict,
          verdict: response,
        };
        setMessages(prev => [...prev, aiMsg]);
      })
      .catch(() => {
        toast({
          title: "Error",
          description: "Failed to get a verdict. Please try again.",
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
      <header className="flex h-14 items-center border-b px-4 lg:h-[60px] lg:px-6">
        <Link href="/dashboard" className="mr-4">
             <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
             </Button>
        </Link>
        <span className="font-semibold">Session {sessionId.slice(0, 8)}</span>
      </header>

      <div className="flex-1 overflow-hidden relative">
          <ScrollArea className="h-full p-4" ref={scrollRef}>
            <div className="space-y-4 pb-4">
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onCitationClick={setSelectedCitation}
                  onFollowUp={handleFollowUp}
                />
              ))}
              {isLoading && (
                <div className="flex w-full px-4 justify-start">
                   <div className="flex items-center gap-2 rounded-lg bg-muted p-4 text-sm text-muted-foreground">
                     <Loader2 className="h-4 w-4 animate-spin" />
                     Adjudicating...
                   </div>
                </div>
              )}
            </div>
          </ScrollArea>
           
          {selectedCitation && (
             <CitationViewer 
                citation={selectedCitation} 
                onClose={() => setSelectedCitation(null)} 
             />
          )}
      </div>

      <div className="border-t p-4 bg-background">
        <form onSubmit={handleSubmit} className="flex gap-4">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about the rules..."
            className="flex-1 min-h-[50px] max-h-[200px] resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          />
          <Button type="submit" disabled={isLoading || !input.trim()}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            <span className="sr-only">Send</span>
          </Button>
        </form>
      </div>
    </div>
  );
}
