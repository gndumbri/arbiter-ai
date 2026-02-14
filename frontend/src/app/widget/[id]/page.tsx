"use client";

import { useParams } from "next/navigation";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

export default function WidgetPage() {
  const params = useParams();
  const id = params.id as string;
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fake loading for effect or fetch session validation
    setTimeout(() => {
        setLoading(false);
    }, 500);
  }, [id]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
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
