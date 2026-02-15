/**
 * Invite Landing Page — Accept/Decline party invite from JWT link.
 *
 * When a user clicks a party invite link, they land here. The page
 * decodes the token, shows the party name, and offers Accept/Decline.
 * If the user isn't signed in, they're redirected to sign-in first.
 *
 * Route: /invite/[token]
 * Used by: JWT invite links from CopyInviteButton
 */
"use client";

import { useState, use } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { motion } from "framer-motion";
import {
  Users,
  Check,
  X,
  Loader2,
  Shield,
  LogIn,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export default function InvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const router = useRouter();
  const { data: session, status } = useSession();
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Decode JWT payload (client-side, no signature verification — server validates)
  let partyName = "a party";
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.party_name) partyName = payload.party_name;
  } catch {
    // Token might be malformed — will fail on server
  }

  const handleAccept = async () => {
    setJoining(true);
    setError(null);
    try {
      await api.joinViaInvite(token);
      setSuccess(true);
      setTimeout(() => router.push("/dashboard/parties"), 1500);
    } catch (e: unknown) {
      const errMsg =
        e instanceof Error ? e.message : "Failed to join party";
      setError(errMsg);
    } finally {
      setJoining(false);
    }
  };

  const handleDecline = () => {
    router.push("/dashboard");
  };

  // Not signed in
  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex h-screen items-center justify-center bg-background p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="w-full max-w-md border-border/50">
            <CardHeader className="text-center pb-4">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <Shield className="h-8 w-8 text-primary" />
              </div>
              <CardTitle className="text-xl">Sign in to join</CardTitle>
            </CardHeader>
            <CardContent className="text-center space-y-4">
              <p className="text-muted-foreground text-sm">
                You&apos;ve been invited to join <strong>{partyName}</strong>.
                Sign in first to accept the invitation.
              </p>
              <Button
                className="w-full gap-2"
                onClick={() =>
                  router.push(
                    `/api/auth/signin?callbackUrl=${encodeURIComponent(
                      `/invite/${token}`
                    )}`
                  )
                }
              >
                <LogIn className="h-4 w-4" />
                Sign In
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  // Success state
  if (success) {
    return (
      <div className="flex h-screen items-center justify-center bg-background p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <Card className="w-full max-w-md border-green-500/30 bg-green-500/5">
            <CardContent className="flex flex-col items-center p-8 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/20">
                <Check className="h-8 w-8 text-green-400" />
              </div>
              <h2 className="text-xl font-bold">You&apos;re in!</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Welcome to <strong>{partyName}</strong>. Redirecting...
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  // Main invite view
  return (
    <div className="flex h-screen items-center justify-center bg-background p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card className="w-full max-w-md border-border/50">
          <CardHeader className="text-center pb-4">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <Users className="h-8 w-8 text-primary" />
            </div>
            <CardTitle className="text-xl">Party Invitation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-center text-muted-foreground text-sm">
              You&apos;ve been invited to join{" "}
              <strong className="text-foreground">{partyName}</strong>.
            </p>

            {error && (
              <div className="rounded-md bg-destructive/10 border border-destructive/30 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <Button
                variant="outline"
                className="flex-1 gap-1.5"
                onClick={handleDecline}
                disabled={joining}
              >
                <X className="h-4 w-4" />
                Decline
              </Button>
              <Button
                className="flex-1 gap-1.5"
                onClick={handleAccept}
                disabled={joining}
              >
                {joining ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                {joining ? "Joining..." : "Accept"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
