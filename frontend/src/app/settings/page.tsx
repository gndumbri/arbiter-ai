/**
 * SettingsPage — User profile management, subscription, and account deletion.
 *
 * Displays three cards:
 * 1. Identity — Edit display name (calls PATCH /api/v1/users/me)
 * 2. Tribute & Patronage — Shows current tier, "Upgrade to Hero" button
 *    (calls POST /api/v1/billing/checkout → redirects to Stripe)
 * 3. Danger Zone — "Retire Character" button (calls DELETE /api/v1/users/me)
 *
 * Called by: Dashboard sidebar "Settings" link, navbar user menu.
 * Depends on: api.ts (updateProfile, createCheckout, deleteAccount, getSubscription),
 *             next-auth/react (useSession for current user info).
 *
 * Architecture note for AI agents:
 *   Previously this page had non-functional buttons. The Save button only
 *   called NextAuth's `update()` which doesn't persist to the backend.
 *   Now all three actions call real backend endpoints via api.ts.
 */

"use client";

import { useSession, signOut } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useState, useEffect, Suspense } from "react";
import { useToast } from "@/hooks/use-toast";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";

/**
 * WHY Suspense: Next.js requires useSearchParams() to be wrapped in a
 * Suspense boundary for static page generation. Without it, the build
 * fails with "should be wrapped in a suspense boundary" error.
 */
export default function SettingsPage() {
  return (
    <Suspense fallback={
      <div className="space-y-6">
        <Skeleton className="h-10 w-[200px]" />
        <Skeleton className="h-[200px] w-full" />
      </div>
    }>
      <SettingsContent />
    </Suspense>
  );
}

function SettingsContent() {
  const { data: session, status, update } = useSession();
  const [name, setName] = useState(session?.user?.name || "");
  const [isSaving, setIsSaving] = useState(false);
  const [isUpgrading, setIsUpgrading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Fetch subscription status from backend
  const { data: subscription } = useSWR("subscription", api.getSubscription, {
    onError: () => {}, // Graceful fallback if backend is down
  });

  // Show upgrade success toast when redirected back from Stripe
  useEffect(() => {
    if (searchParams.get("upgraded") === "true") {
      toast({
        title: "Welcome, Hero!",
        description: "Your subscription has been activated. Enjoy unlimited rulings!",
      });
      // Clean URL without full page reload
      router.replace("/settings", { scroll: false });
    }
  }, [searchParams, toast, router]);

  // Sync name field when session loads
  useEffect(() => {
    if (session?.user?.name && !name) {
      setName(session.user.name);
    }
  }, [session, name]);

  if (status === "loading") {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-[200px]" />
        <Skeleton className="h-[200px] w-full" />
      </div>
    );
  }

  const user = session?.user;

  if (!user) return null; // Should be handled by middleware

  /**
   * Save profile changes to the backend.
   * WHY: We call both api.updateProfile (persists to DB) and NextAuth's
   * update() (refreshes the client-side session) for consistency.
   */
  const handleSave = async () => {
    setIsSaving(true);
    try {
      await api.updateProfile({ name });
      await update({ name }); // Also update NextAuth session
      toast({
        title: "Character Sheet Updated",
        description: "The scribe has noted your new identity in the grand ledger.",
      });
    } catch (error) {
      toast({
        title: "Critical Miss!",
        description: "Failed to update profile. The dice gods are displeased.",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * Redirect to Stripe Checkout for subscription upgrade.
   * WHY: We call POST /billing/checkout which creates a Stripe session
   * and returns a checkout URL. We then redirect the user to Stripe's
   * hosted checkout page. After payment, Stripe redirects back to
   * /settings?upgraded=true, which triggers the success toast above.
   */
  const handleUpgrade = async () => {
    setIsUpgrading(true);
    try {
      const result = await api.createCheckout("PRO");
      // Redirect to Stripe's hosted checkout page
      window.location.href = result.checkout_url;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create checkout";
      toast({
        title: "Upgrade Failed",
        description: message.includes("Stripe not configured")
          ? "Billing is not yet configured. Contact support."
          : message,
        variant: "destructive",
      });
      setIsUpgrading(false);
    }
  };

  /**
   * Delete the user's account after confirmation.
   * WHY: Two-step process — first click shows a confirm dialog,
   * second click actually deletes. We sign out after deletion to
   * clear the NextAuth session.
   */
  const handleDeleteAccount = async () => {
    if (!showDeleteConfirm) {
      setShowDeleteConfirm(true);
      return;
    }

    setIsDeleting(true);
    try {
      await api.deleteAccount();
      toast({
        title: "Farewell, Adventurer",
        description: "Your account has been retired. May your dice roll true in other realms.",
      });
      // Sign out and redirect to landing page
      await signOut({ callbackUrl: "/" });
    } catch (error) {
      toast({
        title: "Deletion Failed",
        description: "Failed to retire your character. Please try again.",
        variant: "destructive",
      });
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  // Determine current tier display text
  const currentTier = subscription?.plan_tier || "FREE";
  const isProUser = currentTier === "PRO" || currentTier === "ADMIN";
  const tierDisplay = isProUser ? "Hero Tier (PRO)" : "Free Tier (NPC)";
  const tierDescription = isProUser
    ? "Unlimited rulings per day. You are a true champion!"
    : "Up to 5 basic rulings per day.";

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h3 className="text-lg font-medium">Character Sheet</h3>
        <p className="text-sm text-muted-foreground">
          Manage your persona and tributes.
        </p>
      </div>
      <Separator />

      {/* Identity Card — Save profile name */}
      <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Identity</CardTitle>
          <CardDescription>
            How you are known in the gaming circles.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email (Soul Bind)</Label>
            <Input id="email" value={user.email || ""} disabled className="bg-zinc-950/50" />
            <p className="text-[0.8rem] text-muted-foreground">
              Your soul is bound to this email address. It cannot be changed.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="name">True Name</Label>
            <Input 
              id="name" 
              value={name} 
              onChange={(e) => setName(e.target.value)} 
              placeholder={user.name || "Enter your name, adventurer"}
              className="bg-zinc-950/50"
            />
          </div>
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? "Scribing..." : "Save Changes"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Subscription Card — Show tier + upgrade button */}
      <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Tribute & Patronage</CardTitle>
          <CardDescription>
            Support the Arbiter and gain favor (and features).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-zinc-800 p-4">
            <div className="space-y-0.5">
              <div className="text-base font-medium">{tierDisplay}</div>
              <div className="text-sm text-muted-foreground">
                {tierDescription}
              </div>
            </div>
            <Button variant="outline" disabled>Current Status</Button>
          </div>
          {!isProUser && (
            <Button
              className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white"
              onClick={handleUpgrade}
              disabled={isUpgrading}
            >
              {isUpgrading ? "Redirecting to Checkout..." : "Upgrade to Hero Tier"}
            </Button>
          )}
        </CardContent>
      </Card>
      
      {/* Danger Zone — Delete account */}
      <div className="pt-4">
        <Button
          variant="destructive"
          className="w-full sm:w-auto"
          onClick={handleDeleteAccount}
          disabled={isDeleting}
        >
          {isDeleting
            ? "Retiring..."
            : showDeleteConfirm
              ? "Confirm: Permanently Delete Account"
              : "Retire Character"}
        </Button>
        <p className="mt-2 text-xs text-muted-foreground">
          {showDeleteConfirm
            ? "⚠️ Click again to permanently delete your account. This cannot be undone."
            : "Permanently delete your account. This action cannot be undone by any spell."}
        </p>
        {showDeleteConfirm && (
          <Button
            variant="ghost"
            size="sm"
            className="mt-2"
            onClick={() => setShowDeleteConfirm(false)}
          >
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
}
