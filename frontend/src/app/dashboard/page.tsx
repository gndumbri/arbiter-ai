"use client";

import Link from "next/link";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { Loader2, MessageSquare, FileText, CheckCircle, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RulesetUploadDialog } from "@/components/dashboard/RulesetUploadDialog";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const { data: rulesets, error, isLoading } = useSWR("rulesets", api.listRulesets, {
    refreshInterval: 5000, 
  });
  const { data: libraryEntries } = useSWR("library", api.listLibrary, { onError: () => {} });

  // Fetch recent sessions for "Continue" section
  const { data: agents } = useSWR("agents", api.listAgents, { onError: () => {} });
  const recentGames = agents
    ? agents
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        // Deduplicate by game_name — show most recent session per game
        .filter((a, i, arr) => arr.findIndex((x) => x.game_name === a.game_name) === i)
        .slice(0, 4)
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">Your Shelf</h2>
          <p className="text-muted-foreground text-sm sm:text-base">Your uploaded rulebooks, ready for battle.</p>
        </div>
        <RulesetUploadDialog />
      </div>

      {/* ─── Recent Games — Continue where you left off ──────────────── */}
      {recentGames.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-muted-foreground">Continue Asking</h3>
          <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
            {recentGames.map((agent) => (
              <Link
                key={agent.id}
                href={`/session/${agent.id}`}
                className="group flex items-center gap-3 rounded-lg border border-border/50 bg-card p-3 hover:border-primary/50 hover:bg-muted/30 transition-all"
              >
                <MessageSquare className="h-4 w-4 text-primary shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{agent.game_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(agent.created_at), { addSuffix: true })}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* ─── Shelf Games — Claimed from Armory ───────────────────────── */}
      {libraryEntries && libraryEntries.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-muted-foreground">Games on Your Shelf</h3>
          <div className="flex flex-wrap gap-2">
            {libraryEntries.slice(0, 10).map((entry) => (
              <Badge key={entry.id} variant={entry.favorite ? "default" : "secondary"}>
                {entry.game_name}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="rounded-md bg-destructive/15 p-4 text-destructive">
          Failed to load rulesets. Is the backend running?
        </div>
      ) : rulesets?.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/50 text-center">
          <FileText className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">Your shelf is empty, adventurer</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Upload a rulebook to begin your quest.
          </p>
          <RulesetUploadDialog />
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {rulesets?.map((ruleset, index) => (
            <motion.div
              key={ruleset.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, duration: 0.3 }}
            >
              <Card className="flex flex-col h-full hover:shadow-lg hover:border-primary/50 transition-all duration-300">
                <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="overflow-hidden text-ellipsis whitespace-nowrap text-lg font-bold w-full pr-2" title={ruleset.game_name}>
                    {ruleset.game_name}
                  </CardTitle>
                  <StatusBadge status={ruleset.status} />
                </CardHeader>
                <CardContent className="flex-1">
                  <div className="text-sm text-muted-foreground space-y-1">
                    <p className="truncate font-mono text-xs" title={ruleset.filename}>{ruleset.filename}</p>
                    <p className="text-xs">
                      <span className="font-semibold text-foreground">{ruleset.chunk_count}</span> Rules Loaded
                    </p>
                    <p className="text-xs">
                      {ruleset.created_at
                        ? formatDistanceToNow(new Date(ruleset.created_at), { addSuffix: true })
                        : "Recently"}
                    </p>
                  </div>
                </CardContent>
                <CardFooter>
                  <Button asChild className="w-full relative group overflow-hidden" disabled={ruleset.status !== "INDEXED" && ruleset.status !== "COMPLETE" && ruleset.status !== "READY"}> 
                    <Link href={`/session/${ruleset.session_id}`}>
                      <span className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-shimmer" />
                      <MessageSquare className="mr-2 h-4 w-4" />
                      Ask the Arbiter
                    </Link>
                  </Button>
                </CardFooter>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "INDEXED" || status === "COMPLETE" || status === "READY") {
    return (
      <Badge variant="outline" className="border-green-500 text-green-500">
        <CheckCircle className="mr-1 h-3 w-3" />
        Ready to Play
      </Badge>
    );
  }
  if (status === "FAILED") {
    return (
      <Badge variant="destructive">
        <AlertCircle className="mr-1 h-3 w-3" />
        Failed
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="animate-pulse">
      <Loader2 className="mr-1 h-3 w-3 animate-spin" />
      {status}
    </Badge>
  );
}
