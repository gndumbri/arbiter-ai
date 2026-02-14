"use client";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { useAuth } from "@/contexts/AuthContext";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function SessionPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const sessionId = params.id as string; // Casting for simplicity

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
    }
  }, [user, isLoading, router]);

  if (isLoading) return <div className="flex h-screen items-center justify-center">Loading...</div>;
  if (!user) return null;

  return <ChatInterface sessionId={sessionId} />;
}
