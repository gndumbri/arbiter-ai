"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  Plus,
  Copy,
  Check,
  LogOut,
  Trash2,
  User,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { api, PartyResponse } from "@/lib/api";

function CopyInviteButton({ partyId }: { partyId: string }) {
  const [copied, setCopied] = useState(false);
  const inviteLink = `${typeof window !== "undefined" ? window.location.origin : ""}/dashboard/parties?join=${partyId}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button variant="outline" size="sm" className="gap-1.5" onClick={handleCopy}>
      {copied ? (
        <>
          <Check className="h-3.5 w-3.5 text-green-400" />
          Copied!
        </>
      ) : (
        <>
          <Copy className="h-3.5 w-3.5" />
          Invite Link
        </>
      )}
    </Button>
  );
}

function PartyCard({
  party,
  onLeave,
  onDelete,
}: {
  party: PartyResponse;
  onLeave: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
    >
      <Card className="border-border/50 bg-card hover:border-primary/30 transition-colors">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-lg">{party.name}</CardTitle>
              <CardDescription className="mt-1">
                Created{" "}
                {party.created_at
                  ? new Date(party.created_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })
                  : "recently"}
              </CardDescription>
            </div>
            <Badge variant="secondary" className="gap-1">
              <Users className="h-3 w-3" />
              {party.member_count} {party.member_count === 1 ? "member" : "members"}
            </Badge>
          </div>
        </CardHeader>
        <CardFooter className="gap-2 flex-wrap">
          <CopyInviteButton partyId={party.id} />
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-muted-foreground hover:text-foreground"
            onClick={() => onLeave(party.id)}
          >
            <LogOut className="h-3.5 w-3.5" />
            Leave
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-muted-foreground hover:text-destructive ml-auto"
            onClick={() => onDelete(party.id)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </CardFooter>
      </Card>
    </motion.div>
  );
}

export default function PartiesPage() {
  const [newPartyName, setNewPartyName] = useState("");
  const [joinId, setJoinId] = useState("");
  const [creating, setCreating] = useState(false);
  const [joining, setJoining] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [joinDialogOpen, setJoinDialogOpen] = useState(false);

  const { data: parties, isLoading } = useSWR("parties", api.listParties, {
    onError: () => {},
  });

  const handleCreate = async () => {
    if (!newPartyName.trim()) return;
    setCreating(true);
    try {
      await api.createParty(newPartyName.trim());
      mutate("parties");
      setNewPartyName("");
      setDialogOpen(false);
    } catch {
      // silent
    } finally {
      setCreating(false);
    }
  };

  const handleJoin = async () => {
    if (!joinId.trim()) return;
    setJoining(true);
    try {
      let partyId = joinId.trim();
      const match = partyId.match(/join=([a-f0-9-]+)/i);
      if (match) partyId = match[1];

      await api.joinParty(partyId);
      mutate("parties");
      setJoinId("");
      setJoinDialogOpen(false);
    } catch {
      // silent
    } finally {
      setJoining(false);
    }
  };

  const handleLeave = async (id: string) => {
    try {
      await api.leaveParty(id);
      mutate("parties");
    } catch {
      // silent
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteParty(id);
      mutate("parties");
    } catch {
      // silent
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Parties</h1>
          <p className="text-muted-foreground mt-1">
            Create a group to share rulings with your game night crew.
          </p>
        </div>
        <div className="flex gap-2">
          <Dialog open={joinDialogOpen} onOpenChange={setJoinDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2">
                <User className="h-4 w-4" />
                Join Party
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Join a Party</DialogTitle>
                <DialogDescription>
                  Paste the invite link or party ID shared by your group.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 py-4">
                <Label htmlFor="join-id">Invite Link or Party ID</Label>
                <Input
                  id="join-id"
                  placeholder="Paste invite link or party ID..."
                  value={joinId}
                  onChange={(e) => setJoinId(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleJoin()}
                />
              </div>
              <DialogFooter>
                <Button onClick={handleJoin} disabled={joining || !joinId.trim()}>
                  {joining ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Join
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="gap-2">
                <Plus className="h-4 w-4" />
                Create Party
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create a New Party</DialogTitle>
                <DialogDescription>
                  Name your adventuring party. You can invite members after creation.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 py-4">
                <Label htmlFor="party-name">Party Name</Label>
                <Input
                  id="party-name"
                  placeholder="e.g. Friday Night Dice Club"
                  value={newPartyName}
                  onChange={(e) => setNewPartyName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                />
              </div>
              <DialogFooter>
                <Button onClick={handleCreate} disabled={creating || !newPartyName.trim()}>
                  {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Create
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : !parties || parties.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/50 text-center">
          <Users className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">No parties yet</h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            Create a party and invite your friends to share rulings during game night.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <AnimatePresence>
            {parties.map((party) => (
              <PartyCard
                key={party.id}
                party={party}
                onLeave={handleLeave}
                onDelete={handleDelete}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
