/**
 * RulingsPage.tsx — Saved Rulings with game-based grouping and filtering.
 *
 * Fetches from GET /api/v1/rulings, /api/v1/rulings/games, and /api/v1/rulings/public.
 * Supports game filter tabs, search, privacy badges, confidence indicators,
 * and deletion via SWR.
 *
 * Used by: /dashboard/rulings route
 */
"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { motion, AnimatePresence } from "framer-motion";
import {
  BookOpen,
  Globe,
  Lock,
  Users,
  Trash2,
  Search,
  Gamepad2,
  Loader2,
  ChevronDown,
  ChevronUp,
  LayoutList,
  FolderOpen,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api, SavedRulingResponse, GameRulingCount } from "@/lib/api";

// ─── Privacy Icon ──────────────────────────────────────────────────────────

function PrivacyIcon({ level }: { level: string }) {
  switch (level) {
    case "PUBLIC":
      return <Globe className="h-3.5 w-3.5 text-green-400" />;
    case "PARTY":
      return <Users className="h-3.5 w-3.5 text-blue-400" />;
    default:
      return <Lock className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

const PRIVACY_CYCLE: Record<string, string> = {
  PRIVATE: "PARTY",
  PARTY: "PUBLIC",
  PUBLIC: "PRIVATE",
};

const PRIVACY_LABEL: Record<string, string> = {
  PRIVATE: "Private",
  PARTY: "Party",
  PUBLIC: "Public",
};

// ─── Confidence Badge ──────────────────────────────────────────────────────

function ConfidenceBadge({ confidence }: { confidence: number }) {
  if (confidence >= 0.8)
    return (
      <Badge variant="default" className="bg-green-600/20 text-green-400 border-green-600/30 text-xs">
        High Confidence
      </Badge>
    );
  if (confidence >= 0.5)
    return (
      <Badge variant="default" className="bg-yellow-600/20 text-yellow-400 border-yellow-600/30 text-xs">
        Moderate
      </Badge>
    );
  return (
    <Badge variant="default" className="bg-red-600/20 text-red-400 border-red-600/30 text-xs">
      Low Confidence
    </Badge>
  );
}

// ─── Ruling Card ────────────────────────────────────────────────────────────

function RulingCard({
  ruling,
  onDelete,
  onPrivacyCycle,
  showPrivacyToggle,
}: {
  ruling: SavedRulingResponse;
  onDelete: (id: string) => void;
  onPrivacyCycle?: (id: string, newLevel: string) => void;
  showPrivacyToggle?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const verdict = ruling.verdict_json;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
    >
      <Card className="border-border/50 bg-card hover:border-primary/30 transition-colors">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <CardTitle className="text-base font-medium leading-snug">
                {ruling.query}
              </CardTitle>
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                {showPrivacyToggle && onPrivacyCycle ? (
                  <button
                    className="flex items-center gap-1 rounded px-1.5 py-0.5 text-xs hover:bg-muted transition-colors"
                    onClick={() => onPrivacyCycle(ruling.id, PRIVACY_CYCLE[ruling.privacy_level] || "PRIVATE")}
                    title={`Click to change (${PRIVACY_LABEL[ruling.privacy_level]})`}
                  >
                    <PrivacyIcon level={ruling.privacy_level} />
                    <span className="text-muted-foreground">{PRIVACY_LABEL[ruling.privacy_level]}</span>
                  </button>
                ) : (
                  <PrivacyIcon level={ruling.privacy_level} />
                )}
                {ruling.game_name && (
                  <Badge variant="outline" className="text-xs gap-1">
                    <Gamepad2 className="h-3 w-3" />
                    {ruling.game_name}
                  </Badge>
                )}
                {verdict?.confidence != null && (
                  <ConfidenceBadge confidence={verdict.confidence} />
                )}
                {ruling.tags?.map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-destructive"
                onClick={() => onDelete(ruling.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <CardContent className="pt-0 pb-4">
                {verdict?.verdict && (
                  <div className="mt-2 rounded-md bg-muted/30 p-3 text-sm leading-relaxed">
                    {verdict.verdict}
                  </div>
                )}

                {verdict?.citations && verdict.citations.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-muted-foreground mb-1.5">
                      Citations
                    </p>
                    <div className="space-y-1.5">
                      {verdict.citations.map((c, i) => (
                        <div
                          key={i}
                          className="text-xs text-muted-foreground bg-muted/20 rounded px-2 py-1.5"
                        >
                          <span className="font-medium text-foreground">
                            {c.source}
                            {c.page ? `, p.${c.page}` : ""}
                            {c.section ? ` §${c.section}` : ""}
                          </span>
                          {c.snippet && (
                            <span className="ml-1 italic">— "{c.snippet}"</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {verdict?.reasoning_chain && (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      Reasoning
                    </p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {verdict.reasoning_chain}
                    </p>
                  </div>
                )}

                <p className="text-xs text-muted-foreground mt-3">
                  Saved{" "}
                  {ruling.created_at
                    ? new Date(ruling.created_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                        hour: "numeric",
                        minute: "2-digit",
                      })
                    : "recently"}
                </p>
              </CardContent>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  );
}

// ─── Game Group Component ───────────────────────────────────────────────────

function GameGroup({
  gameName,
  rulings,
  onDelete,
  onPrivacyCycle,
  showPrivacyToggle,
}: {
  gameName: string;
  rulings: SavedRulingResponse[];
  onDelete: (id: string) => void;
  onPrivacyCycle: (id: string, level: string) => void;
  showPrivacyToggle: boolean;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="rounded-lg border border-border/50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Gamepad2 className="h-4 w-4 text-primary" />
          <span className="font-semibold text-sm">{gameName}</span>
          <Badge variant="secondary" className="text-xs">
            {rulings.length} {rulings.length === 1 ? "ruling" : "rulings"}
          </Badge>
        </div>
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {expanded && (
        <div className="divide-y divide-border/30">
          {rulings.map((ruling) => (
            <div key={ruling.id} className="px-4 py-3 space-y-2 hover:bg-muted/10 transition-colors">
              {/* Q&A format */}
              <div className="flex items-start gap-2">
                <span className="text-xs font-bold text-primary mt-0.5 shrink-0">Q:</span>
                <p className="text-sm font-medium">{ruling.query}</p>
              </div>
              {ruling.verdict_json?.verdict && (
                <div className="flex items-start gap-2">
                  <span className="text-xs font-bold text-green-500 mt-0.5 shrink-0">A:</span>
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {ruling.verdict_json.verdict}
                  </p>
                </div>
              )}
              {/* Actions row */}
              <div className="flex items-center gap-2 ml-5">
                {ruling.tags?.map((tag) => (
                  <Badge key={tag} variant="outline" className="text-xs py-0">
                    {tag}
                  </Badge>
                ))}
                {showPrivacyToggle && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs gap-1 ml-auto"
                    onClick={() => {
                      const cycle = { PRIVATE: "PARTY", PARTY: "PUBLIC", PUBLIC: "PRIVATE" };
                      onPrivacyCycle(ruling.id, cycle[ruling.privacy_level as keyof typeof cycle] || "PRIVATE");
                    }}
                  >
                    {ruling.privacy_level === "PRIVATE" ? <Lock className="h-3 w-3" /> : ruling.privacy_level === "PARTY" ? <Users className="h-3 w-3" /> : <Globe className="h-3 w-3" />}
                    {ruling.privacy_level}
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs text-destructive hover:text-destructive"
                  onClick={() => onDelete(ruling.id)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function RulingsPage() {
  const [activeTab, setActiveTab] = useState<"mine" | "party" | "community">("mine");
  const [selectedGame, setSelectedGame] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [groupByGame, setGroupByGame] = useState(true);

  const { data: myRulings, isLoading: loadingMine } = useSWR(
    activeTab === "mine" ? ["rulings", selectedGame] : null,
    () => api.listRulings(selectedGame ?? undefined),
    { onError: () => {} }
  );

  const { data: publicRulings, isLoading: loadingPublic } = useSWR(
    activeTab === "community" ? "rulings-public" : null,
    api.listPublicRulings,
    { onError: () => {} }
  );

  const { data: partyRulings, isLoading: loadingParty } = useSWR(
    activeTab === "party" ? ["rulings-party", selectedGame] : null,
    () => api.listPartyRulings(selectedGame ?? undefined),
    { onError: () => {} }
  );

  const { data: gameList } = useSWR("ruling-games", api.listRulingGames, {
    onError: () => {},
  });

  const handleDelete = async (id: string) => {
    try {
      await api.deleteRuling(id);
      mutate(["rulings", selectedGame]);
    } catch {
      // silent
    }
  };

  const handlePrivacyCycle = async (id: string, newLevel: string) => {
    try {
      await api.updateRuling(id, { privacy_level: newLevel });
      mutate(["rulings", selectedGame]);
    } catch {
      // silent
    }
  };

  const rulings = activeTab === "mine" ? myRulings : activeTab === "party" ? partyRulings : publicRulings;
  const isLoading = activeTab === "mine" ? loadingMine : activeTab === "party" ? loadingParty : loadingPublic;

  const filtered = rulings?.filter(
    (r) =>
      !search ||
      r.query.toLowerCase().includes(search.toLowerCase()) ||
      r.game_name?.toLowerCase().includes(search.toLowerCase()) ||
      r.tags?.some((t) => t.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">The Scroll Archive</h1>
          <p className="text-muted-foreground mt-1">
            Your saved verdicts, organized by game.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border/50 pb-2">
        <Button
          variant={activeTab === "mine" ? "default" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("mine")}
          className="gap-1.5"
        >
          <BookOpen className="h-4 w-4" />
          My Scrolls
        </Button>
        <Button
          variant={activeTab === "party" ? "default" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("party")}
          className="gap-1.5"
        >
          <Users className="h-4 w-4" />
          Party Scrolls
        </Button>
        <Button
          variant={activeTab === "community" ? "default" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("community")}
          className="gap-1.5"
        >
          <Globe className="h-4 w-4" />
          Tavern Board
        </Button>
      </div>

      {/* Game Filter + Search */}
      <div className="flex flex-col gap-3 sm:flex-row">
        {/* Game filter pills — only show for "mine" tab when there are games */}
        {activeTab === "mine" && gameList && gameList.length > 0 && (
          <div className="flex gap-1.5 flex-wrap">
            <Button
              variant={selectedGame === null ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setSelectedGame(null);
                mutate(["rulings", null]);
              }}
              className="text-xs h-7"
            >
              All ({gameList.reduce((a, g) => a + g.count, 0)})
            </Button>
            {gameList.map((game) => (
              <Button
                key={game.game_name}
                variant={selectedGame === game.game_name ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setSelectedGame(game.game_name);
                  mutate(["rulings", game.game_name]);
                }}
                className="text-xs h-7 gap-1"
              >
                <Gamepad2 className="h-3 w-3" />
                {game.game_name} ({game.count})
              </Button>
            ))}
          </div>
        )}

        {/* Group toggle + Search */}
        <div className="flex items-center gap-2 sm:ml-auto">
          <Button
            variant={groupByGame ? "default" : "outline"}
            size="sm"
            className="h-9 gap-1 text-xs"
            onClick={() => setGroupByGame(!groupByGame)}
          >
            {groupByGame ? <FolderOpen className="h-3.5 w-3.5" /> : <LayoutList className="h-3.5 w-3.5" />}
            {groupByGame ? "Grouped" : "List"}
          </Button>
          <div className="relative sm:w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search rulings..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : !filtered || filtered.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/50 text-center">
          <BookOpen className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">
            {search
              ? "No scrolls match that search"
              : selectedGame
                ? `No scrolls for ${selectedGame}`
                : "No scrolls yet"}
          </h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            {search
              ? "Try a different search term."
              : "Save a verdict from the chat to start your archive."}
          </p>
        </div>
      ) : groupByGame ? (
        /* ─── Grouped by Game View ──────────────────────────────────── */
        <div className="space-y-6">
          {Object.entries(
            filtered.reduce<Record<string, SavedRulingResponse[]>>((acc, r) => {
              const key = r.game_name || "Uncategorized";
              if (!acc[key]) acc[key] = [];
              acc[key].push(r);
              return acc;
            }, {})
          ).map(([gameName, gameRulings]) => (
            <GameGroup
              key={gameName}
              gameName={gameName}
              rulings={gameRulings}
              onDelete={handleDelete}
              onPrivacyCycle={handlePrivacyCycle}
              showPrivacyToggle={activeTab === "mine"}
            />
          ))}
        </div>
      ) : (
        /* ─── Flat List View ──────────────────────────────────────── */
        <div className="space-y-3">
          <AnimatePresence>
            {filtered.map((ruling) => (
              <RulingCard
                key={ruling.id}
                ruling={ruling}
                onDelete={handleDelete}
                onPrivacyCycle={handlePrivacyCycle}
                showPrivacyToggle={activeTab === "mine"}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
