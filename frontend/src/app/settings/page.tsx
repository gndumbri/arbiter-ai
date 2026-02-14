
"use client";

import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useState } from "react";
import { useToast } from "@/hooks/use-toast";

export default function SettingsPage() {
  const { data: session, status, update } = useSession();
  const [name, setName] = useState(session?.user?.name || "");
  const [isSaving, setIsSaving] = useState(false);
  const { toast } = useToast();

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

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await update({ name }); // Optimistic update
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

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h3 className="text-lg font-medium">Character Sheet</h3>
        <p className="text-sm text-muted-foreground">
          Manage your persona and tributes.
        </p>
      </div>
      <Separator />

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
              <div className="text-base font-medium">Free Tier (NPC)</div>
              <div className="text-sm text-muted-foreground">
                Up to 5 basic rulings per day.
              </div>
            </div>
            <Button variant="outline" disabled>Current Status</Button>
          </div>
          <Button className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white">
            Upgrade to Hero Tier
          </Button>
        </CardContent>
      </Card>
      
      <div className="pt-4">
          <Button variant="destructive" className="w-full sm:w-auto">Retire Character</Button>
          <p className="mt-2 text-xs text-muted-foreground">
            Permanently delete your account. This action cannot be undone by any spell.
          </p>
      </div>
    </div>
  );
}
