"use client";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { useSession } from "next-auth/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function SessionPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const params = useParams();
  const sessionId = params.id as string; // Casting for simplicity

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/");
    }
  }, [status, router]);

  if (status === "loading") return <div className="flex h-screen items-center justify-center">Loading...</div>;
  if (!session?.user) return null;

  return <ChatInterface sessionId={sessionId} />;
}

