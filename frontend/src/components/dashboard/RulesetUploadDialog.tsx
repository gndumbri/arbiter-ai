"use client";

/**
 * RulesetUploadDialog.tsx — 3-step wizard for adding games to Arbiter.
 *
 * Step 1 (Search): User types a game name → queries GET /api/v1/catalog?search=...
 *   Results show status badges: 🟢 READY, 🟡 UPLOAD_REQUIRED.
 *   Fallback: "Create Custom Game" when no results match.
 *
 * Step 2 (Action): Routes the user based on game status:
 *   - READY → creates a session + redirects to chat
 *   - UPLOAD_REQUIRED / Custom → proceeds to Step 3
 *
 * Step 3 (Upload): File upload form for PDF rulebooks.
 *   - Custom games: creates session + uploads file
 *   - Metadata games: links to catalog entry + uploads file
 *
 * Called by: Dashboard page (/dashboard/page.tsx)
 * Depends on: api.ts (searchCatalog, createSession, uploadRuleset)
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2,
  Upload,
  Search,
  ChevronLeft,
  Zap,
  FileUp,
  Sparkles,
  PlusCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { api, CatalogEntry } from "@/lib/api";

/**
 * Status badge component — shows visual indicator for game readiness.
 *
 * WHY: Users need to immediately see whether they can chat right away
 * (READY) or need to upload their own rulebook (UPLOAD_REQUIRED).
 */
function StatusBadge({ status }: { status: string }) {
  if (status === "READY") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400">
        <Zap className="h-3 w-3" />
        Chat Now
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-400">
      <FileUp className="h-3 w-3" />
      Rules Required
    </span>
  );
}

export function RulesetUploadDialog() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CatalogEntry[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedGame, setSelectedGame] = useState<CatalogEntry | null>(null);
  const [customGameName, setCustomGameName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const { toast } = useToast();
  const router = useRouter();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setStep(1);
      setSearchQuery("");
      setSearchResults([]);
      setSelectedGame(null);
      setCustomGameName("");
      setFile(null);
      setIsLoading(false);
      setIsSearching(false);
    }
  }, [open]);

  // ─── Step 1: Debounced search ────────────────────────────────────────────

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await api.searchCatalog(query);
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);
  }, []);

  // ─── Step 2: Handle game selection ───────────────────────────────────────

  const handleSelectGame = async (game: CatalogEntry) => {
    setSelectedGame(game);

    if (game.status === "READY") {
      // Bucket A: Open content → create session → redirect to chat
      setIsLoading(true);
      try {
        await api.createSession({ game_name: game.game_name });
        toast({
          title: "Ready to judge!",
          description: `${game.game_name} rules are loaded. Start asking questions!`,
        });
        setOpen(false);
        router.push("/dashboard");
        router.refresh();
      } catch (error) {
        toast({
          title: "Session failed",
          description: error instanceof Error ? error.message : "Something went wrong",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    } else {
      // Bucket B: Metadata only → need file upload
      setStep(3);
    }
  };

  // ─── Step 1→3: Custom game (Bucket C) ────────────────────────────────────

  const handleCreateCustom = () => {
    setCustomGameName(searchQuery);
    setSelectedGame(null);
    setStep(3);
  };

  // ─── Step 3: Upload handler ──────────────────────────────────────────────

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const gameName = selectedGame?.game_name || customGameName;
    if (!file || !gameName) return;

    setIsLoading(true);
    try {
      // 1. Create session for this game
      const session = await api.createSession({ game_name: gameName });

      // 2. Upload rulebook
      const formData = new FormData();
      formData.append("file", file);
      formData.append("game_name", gameName);
      formData.append("source_type", "BASE");

      await api.uploadRuleset(session.id, formData);

      toast({
        title: "Upload started",
        description: "Your ruleset is being processed. It will appear on the dashboard shortly.",
      });
      setOpen(false);
      router.refresh();
    } catch (error) {
      toast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : "Something went wrong",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button id="upload-ruleset-btn">
          <Upload className="mr-2 h-4 w-4" />
          Add Game
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {step === 1 && "Find Your Game"}
            {step === 3 && (
              <button
                onClick={() => setStep(1)}
                className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-white transition mr-2"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
            {step === 3 && "Upload Rulebook"}
          </DialogTitle>
          <DialogDescription>
            {step === 1 && "Search our catalog of 180+ games, or create a custom one."}
            {step === 3 && `Upload a PDF rulebook for ${selectedGame?.game_name || customGameName}.`}
          </DialogDescription>
        </DialogHeader>

        {/* ── Step 1: Search ─────────────────────────────────────────── */}
        {step === 1 && (
          <div className="space-y-4 py-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="game-search-input"
                className="pl-9"
                placeholder="Search games... (e.g. Catan, D&D, Wingspan)"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                autoFocus
              />
            </div>

            {/* Search results */}
            <div className="max-h-[300px] overflow-y-auto space-y-1">
              {isSearching && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              )}

              {!isSearching && searchResults.length > 0 && searchResults.map((game) => (
                <button
                  key={game.id}
                  onClick={() => handleSelectGame(game)}
                  disabled={isLoading}
                  className="w-full flex items-center justify-between p-3 rounded-lg border border-border/50 hover:border-primary/50 hover:bg-primary/5 transition-all text-left group"
                >
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm truncate">
                      {game.game_name}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {game.publisher_name} · v{game.version}
                    </div>
                  </div>
                  <StatusBadge status={game.status} />
                </button>
              ))}

              {!isSearching && searchQuery.length >= 2 && searchResults.length === 0 && (
                <div className="text-center py-6 space-y-3">
                  <p className="text-sm text-muted-foreground">
                    No games found for &quot;{searchQuery}&quot;
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCreateCustom}
                    className="gap-2"
                  >
                    <PlusCircle className="h-4 w-4" />
                    Create &quot;{searchQuery}&quot; as Custom Game
                  </Button>
                </div>
              )}

              {/* Custom game shortcut when results exist */}
              {!isSearching && searchResults.length > 0 && searchQuery.length >= 2 && (
                <button
                  onClick={handleCreateCustom}
                  className="w-full flex items-center gap-2 p-3 rounded-lg border border-dashed border-border/50 hover:border-primary/50 hover:bg-primary/5 transition-all text-sm text-muted-foreground hover:text-white"
                >
                  <Sparkles className="h-4 w-4" />
                  Don&apos;t see your game? Create &quot;{searchQuery}&quot; as custom
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Step 3: Upload ─────────────────────────────────────────── */}
        {step === 3 && (
          <form onSubmit={handleUpload} className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="gameName">Game Name</Label>
              <Input
                id="gameName"
                value={selectedGame?.game_name || customGameName}
                onChange={(e) => !selectedGame && setCustomGameName(e.target.value)}
                readOnly={!!selectedGame}
                className={selectedGame ? "bg-muted" : ""}
                required
              />
              {selectedGame && (
                <p className="text-xs text-muted-foreground">
                  {selectedGame.publisher_name} · v{selectedGame.version}
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="file">Rulebook PDF</Label>
              <Input
                id="file"
                type="file"
                accept=".pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
              />
              <p className="text-xs text-muted-foreground">
                Upload a PDF of the game&apos;s rulebook (max 50 MB).
              </p>
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setStep(1);
                  setSelectedGame(null);
                  setFile(null);
                }}
              >
                Back
              </Button>
              <Button type="submit" disabled={isLoading || !file}>
                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Upload & Process
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
