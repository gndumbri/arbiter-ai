/**
 * PartiesPage.tsx — Party management with member controls, JWT invites,
 * and per-game sharing.
 *
 * Create/join/leave/delete parties. Owners can remove members and
 * transfer ownership. Members can self-remove via Leave. Invite links
 * use JWT tokens pointing to /invite/[token] for accept/decline.
 *
 * Used by: /dashboard/parties route
 */
"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { useSession } from "next-auth/react";
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
  ChevronDown,
  ChevronUp,
  Crown,
  UserMinus,
  ArrowRightLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
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
import { api, PartyResponse, PartyMemberResponse } from "@/lib/api";

// ─── Copy JWT Invite Button ─────────────────────────────────────────────────

function CopyInviteButton({ partyId }: { partyId: string }) {
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleCopy = async () => {
    setLoading(true);
    try {
      const { invite_url } = await api.getInviteLink(partyId);
      await navigator.clipboard.writeText(invite_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback — copy a raw party ID
      const fallback = `${window.location.origin}/dashboard/parties?join=${partyId}`;
      await navigator.clipboard.writeText(fallback);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      variant="outline"
      size="sm"
      className="gap-1.5"
      onClick={handleCopy}
      disabled={loading}
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : copied ? (
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

// ─── Member List Panel ──────────────────────────────────────────────────────

function MemberList({
  partyId,
  ownerId,
  isOwner,
}: {
  partyId: string;
  ownerId: string;
  isOwner: boolean;
}) {
  const { data: members } = useSWR(
    `party-members-${partyId}`,
    () => api.getPartyMembers(partyId),
    { onError: () => {} }
  );

  const handleRemove = async (userId: string) => {
    try {
      await api.removeMember(partyId, userId);
      mutate(`party-members-${partyId}`);
      mutate("parties");
    } catch {
      // silent
    }
  };

  const handleTransfer = async (userId: string) => {
    if (!confirm("Transfer ownership to this member? You'll become a regular member.")) return;
    try {
      await api.transferOwnership(partyId, userId);
      mutate(`party-members-${partyId}`);
      mutate("parties");
    } catch {
      // silent
    }
  };

  if (!members) {
    return (
      <div className="flex items-center gap-2 p-2 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading members...
      </div>
    );
  }

  return (
    <div className="space-y-1 p-2">
      {members.map((member: PartyMemberResponse) => (
        <div
          key={member.user_id}
          className="flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-muted/50"
        >
          <div className="flex items-center gap-2">
            <User className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs">
              {member.user_id === ownerId
                ? member.user_id.slice(0, 8) + "…"
                : member.user_id.slice(0, 8) + "…"}
            </span>
            {member.role === "OWNER" && (
              <Badge variant="secondary" className="text-[10px] gap-0.5 px-1 py-0">
                <Crown className="h-2.5 w-2.5" />
                Owner
              </Badge>
            )}
          </div>

          {/* Owner controls — only show for non-owner members */}
          {isOwner && member.user_id !== ownerId && (
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-primary"
                onClick={() => handleTransfer(member.user_id)}
                title="Transfer ownership"
              >
                <ArrowRightLeft className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-destructive"
                onClick={() => handleRemove(member.user_id)}
                title="Remove member"
              >
                <UserMinus className="h-3 w-3" />
              </Button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Party Card ──────────────────────────────────────────────────────────────

function PartyCard({
  party,
  currentUserId,
  onLeave,
  onDelete,
}: {
  party: PartyResponse;
  currentUserId: string;
  onLeave: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isOwner = party.owner_id === currentUserId;

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
            <div className="flex items-center gap-2">
              {isOwner && (
                <Badge variant="default" className="text-[10px] gap-0.5 bg-amber-500/20 text-amber-400 border-amber-500/30">
                  <Crown className="h-2.5 w-2.5" />
                  Owner
                </Badge>
              )}
              <Badge variant="secondary" className="gap-1">
                <Users className="h-3 w-3" />
                {party.member_count}
              </Badge>
            </div>
          </div>
        </CardHeader>

        {/* Expandable member list */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <CardContent className="pt-0 pb-2 border-t border-border/30">
                <MemberList
                  partyId={party.id}
                  ownerId={party.owner_id}
                  isOwner={isOwner}
                />
              </CardContent>
            </motion.div>
          )}
        </AnimatePresence>

        <CardFooter className="gap-2 flex-wrap">
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-muted-foreground"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
            Members
          </Button>
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
          {isOwner && (
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-muted-foreground hover:text-destructive ml-auto"
              onClick={() => onDelete(party.id)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </CardFooter>
      </Card>
    </motion.div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function PartiesPage() {
  const [newPartyName, setNewPartyName] = useState("");
  const [joinId, setJoinId] = useState("");
  const [creating, setCreating] = useState(false);
  const [joining, setJoining] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [joinDialogOpen, setJoinDialogOpen] = useState(false);
  const { data: session } = useSession();

  // WHY: We need the current user ID to determine owner-only UI.
  const currentUserId = (session?.user as { id?: string } | undefined)?.id ?? "";

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
                currentUserId={currentUserId}
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
