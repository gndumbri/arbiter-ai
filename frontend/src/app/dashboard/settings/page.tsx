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

  // Fetch user profile (includes default_ruling_privacy)
  const { data: profile, mutate: mutateProfile } = useSWR("profile", api.getProfile, {
    onError: () => {},
  });
  const [defaultPrivacy, setDefaultPrivacy] = useState<string>("PRIVATE");

  // Show upgrade success toast when redirected back from Stripe
  useEffect(() => {
    if (searchParams.get("upgraded") === "true") {
      toast({
        title: "Welcome, Hero!",
        description: "Your subscription has been activated. Enjoy unlimited rulings!",
      });
      // Clean URL without full page reload
      router.replace("/dashboard/settings", { scroll: false });
    }
  }, [searchParams, toast, router]);

  // Sync name field when session loads
  useEffect(() => {
    if (session?.user?.name && !name) {
      setName(session.user.name);
    }
  }, [session, name]);

  // Sync default privacy when profile loads
  useEffect(() => {
    if (profile?.default_ruling_privacy) {
      setDefaultPrivacy(profile.default_ruling_privacy);
    }
  }, [profile]);

  const handlePrivacyChange = async (level: string) => {
    setDefaultPrivacy(level);
    try {
      await api.updateProfile({ default_ruling_privacy: level });
      mutateProfile();
      toast({
        title: "Privacy Updated",
        description: `New rulings will default to ${level.toLowerCase()}.`,
      });
    } catch {
      toast({ title: "Failed", description: "Could not update privacy.", variant: "destructive" });
    }
  };

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

  const redirectToTrustedStripeUrl = (url: string) => {
    const parsed = new URL(url);
    const isStripeHost = parsed.hostname === "stripe.com" || parsed.hostname.endsWith(".stripe.com");
    if (parsed.protocol !== "https:" || !isStripeHost) {
      throw new Error("Unexpected redirect URL returned by billing service.");
    }
    window.location.assign(parsed.toString());
  };

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
    } catch {
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
      redirectToTrustedStripeUrl(result.checkout_url);
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
    } catch {
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

      {/* Scroll Privacy — Default ruling visibility */}
      <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Scroll Privacy</CardTitle>
          <CardDescription>
            Choose the default visibility when saving rulings. You can override per-ruling.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {[
              { value: "PRIVATE", icon: "🔒", label: "Private", desc: "Only you" },
              { value: "PARTY", icon: "👥", label: "Party", desc: "Guild members" },
              { value: "PUBLIC", icon: "🌐", label: "Public", desc: "Tavern Board" },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() => handlePrivacyChange(opt.value)}
                className={`flex-1 flex flex-col items-center gap-1 rounded-lg border p-3 text-sm transition-all ${
                  defaultPrivacy === opt.value
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-zinc-800 text-muted-foreground hover:border-zinc-700 hover:bg-zinc-800/50"
                }`}
              >
                <span className="text-lg">{opt.icon}</span>
                <span className="font-medium">{opt.label}</span>
                <span className="text-[10px] opacity-70">{opt.desc}</span>
              </button>
            ))}
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
          {isProUser && (
            <Button
              variant="outline"
              className="w-full"
              onClick={async () => {
                try {
                  const result = await api.createPortalSession();
                  redirectToTrustedStripeUrl(result.portal_url);
                } catch (error) {
                  toast({
                    title: "Portal Unavailable",
                    description: error instanceof Error ? error.message : "Failed to open subscription portal.",
                    variant: "destructive",
                  });
                }
              }}
            >
              Manage Subscription
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
