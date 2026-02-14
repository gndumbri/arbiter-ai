"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { motion, AnimatePresence } from "framer-motion";
import { Bookmark, Trash2, Globe, Lock, Users, Loader2, Search, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, SavedRulingResponse } from "@/lib/api";

function PrivacyIcon({ level }: { level: string }) {
  switch (level) {
    case "PUBLIC":
      return <Globe className="h-3.5 w-3.5" />;
    case "PARTY":
      return <Users className="h-3.5 w-3.5" />;
    default:
      return <Lock className="h-3.5 w-3.5" />;
  }
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const color =
    confidence >= 0.8
      ? "bg-green-500/15 text-green-400 border-green-500/30"
      : confidence >= 0.5
      ? "bg-yellow-500/15 text-yellow-400 border-yellow-500/30"
      : "bg-red-500/15 text-red-400 border-red-500/30";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      {Math.round(confidence * 100)}%
    </span>
  );
}

function RulingCard({ ruling, onDelete }: { ruling: SavedRulingResponse; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const verdict = ruling.verdict_json;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
    >
      <Card className="border-border/50 bg-card hover:border-primary/30 transition-colors">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="text-sm font-medium leading-snug flex-1">
              &ldquo;{ruling.query}&rdquo;
            </CardTitle>
            <div className="flex items-center gap-2 shrink-0">
              {verdict && typeof verdict === "object" && "confidence" in verdict && (
                <ConfidenceBadge confidence={(verdict as { confidence: number }).confidence} />
              )}
              <Badge variant="outline" className="text-xs gap-1">
                <PrivacyIcon level={ruling.privacy_level} />
                {ruling.privacy_level}
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {verdict && typeof verdict === "object" && "verdict" in verdict && (
              <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3">
                {(verdict as { verdict: string }).verdict}
              </p>
            )}

            {ruling.tags && ruling.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {ruling.tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-muted-foreground">
                {ruling.created_at
                  ? new Date(ruling.created_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })
                  : "Unknown date"}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setExpanded(!expanded)}
                >
                  <ChevronDown className={`h-3.5 w-3.5 mr-1 transition-transform ${expanded ? "rotate-180" : ""}`} />
                  {expanded ? "Less" : "More"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs text-muted-foreground hover:text-destructive"
                  onClick={() => onDelete(ruling.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            <AnimatePresence>
              {expanded && verdict && typeof verdict === "object" && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="rounded-lg border border-border/50 bg-muted/30 p-3 text-sm space-y-2">
                    {"reasoning_chain" in verdict && (verdict as { reasoning_chain: string | null }).reasoning_chain && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Reasoning</p>
                        <p className="text-sm">{(verdict as { reasoning_chain: string }).reasoning_chain}</p>
                      </div>
                    )}
                    {"citations" in verdict && Array.isArray((verdict as { citations: unknown[] }).citations) && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Citations</p>
                        {((verdict as { citations: Array<{ source: string; page?: number; snippet?: string }> }).citations).map((c, i) => (
                          <p key={i} className="text-xs text-muted-foreground">
                            {c.source} {c.page ? `(p. ${c.page})` : ""} — {c.snippet?.slice(0, 100)}...
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function RulingsPage() {
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<"mine" | "public">("mine");
  const { data: myRulings, isLoading: loadingMine } = useSWR("rulings-mine", api.listRulings, {
    onError: () => {},
  });
  const { data: publicRulings, isLoading: loadingPublic } = useSWR("rulings-public", api.listPublicRulings, {
    onError: () => {},
  });

  const isLoading = tab === "mine" ? loadingMine : loadingPublic;
  const rulings = tab === "mine" ? myRulings : publicRulings;

  const filtered = (rulings || []).filter(
    (r) =>
      r.query.toLowerCase().includes(search.toLowerCase()) ||
      (r.tags && r.tags.some((t) => t.toLowerCase().includes(search.toLowerCase())))
  );

  const handleDelete = async (id: string) => {
    try {
      await api.deleteRuling(id);
      mutate("rulings-mine");
    } catch {
      // silent fail
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Saved Rulings</h1>
        <p className="text-muted-foreground mt-1">
          Your pinned verdicts and community rulings.
        </p>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex rounded-lg border border-border/50 p-0.5 bg-muted/30">
          <button
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
              tab === "mine" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setTab("mine")}
          >
            My Rulings
          </button>
          <button
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
              tab === "public" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setTab("public")}
          >
            Community
          </button>
        </div>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search rulings by question or tag..."
            className="pl-10"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/50 text-center">
          <Bookmark className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">
            {tab === "mine" ? "No saved rulings yet" : "No community rulings yet"}
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            {tab === "mine"
              ? "Save verdicts from the chat to build your collection."
              : "Public rulings from the community will appear here."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence>
            {filtered.map((ruling) => (
              <RulingCard key={ruling.id} ruling={ruling} onDelete={handleDelete} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
