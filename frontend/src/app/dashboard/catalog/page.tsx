/**
 * CatalogPage — Browse the full game catalog and add games to your library.
 *
 * The primary data source is GET /api/v1/catalog, which returns all 1000+
 * games seeded into the database by scripts/seed_catalog.py. A small
 * FALLBACK_GAMES list is only shown when the backend is unreachable.
 *
 * Called by: Dashboard layout sidebar "Catalog" link.
 * Depends on: api.ts (listCatalog, listLibrary, addToLibrary).
 */

"use client";

import { useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import { Search, Plus, Star, Gamepad2, Shield, Loader2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { api, CatalogEntry } from "@/lib/api";
import { FALLBACK_CATALOG_GAMES } from "@/lib/catalogFallback";

function normalizeGameKey(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

export default function CatalogPage() {
  const [search, setSearch] = useState("");
  // Track which games the user has added in this session for instant UI feedback
  const [addedSlugs, setAddedSlugs] = useState<Set<string>>(new Set());
  // Track in-flight add requests to show loading spinners
  const [addingSlugs, setAddingSlugs] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  const { data: backendCatalog, error: catalogError, isLoading } = useSWR("catalog", api.listCatalog, {
    onError: () => {}, // Gracefully handle backend being down
  });

  // Fetch user's existing library to show "Already in Library" state
  const { data: libraryEntries, mutate: mutateLibrary } = useSWR("library", api.listLibrary, {
    onError: () => {},
  });

  // Build a set of slugs already in the user's library
  const librarySlugSet = new Set<string>();
  const libraryNameSet = new Set<string>();
  if (libraryEntries) {
    for (const entry of libraryEntries) {
      librarySlugSet.add(entry.game_slug);
      libraryNameSet.add(normalizeGameKey(entry.game_name));
    }
  }

  // Backend catalog is the source of truth. Fallback list is only for
  // backend-unreachable cases so we do not mask a truly empty database.
  const useFallbackCatalog = Boolean(catalogError);
  const allGames: CatalogEntry[] = useFallbackCatalog
    ? FALLBACK_CATALOG_GAMES
    : (backendCatalog ?? []);

  const filtered = allGames.filter(
    (g) =>
      g.game_name.toLowerCase().includes(search.toLowerCase()) ||
      g.publisher_name.toLowerCase().includes(search.toLowerCase())
  );

  const isGameInLibrary = (game: CatalogEntry) => {
    return (
      addedSlugs.has(game.game_slug)
      || librarySlugSet.has(game.game_slug)
      || libraryNameSet.has(normalizeGameKey(game.game_name))
    );
  };

  /**
   * Handle "Add to Library" button click.
   * Calls POST /api/v1/library and updates local state on success.
   * WHY: We track addedSlugs separately from libraryEntries so the
   * button updates instantly without waiting for SWR to refetch.
   */
  const handleAddToLibrary = async (game: CatalogEntry) => {
    if (addingSlugs.has(game.game_slug) || isGameInLibrary(game)) {
      return; // Already adding or already in library
    }

    setAddingSlugs((prev) => new Set(prev).add(game.game_slug));

    try {
      const created = await api.addToLibrary({
        game_slug: game.game_slug,
        game_name: game.game_name,
        // WHY: Only pass official_ruleset_id if the game has a real backend ID (not common-* prefix)
        official_ruleset_id: game.id.startsWith("common-") ? undefined : game.id,
      });

      setAddedSlugs((prev) => new Set(prev).add(game.game_slug));
      mutateLibrary((prev = []) => [created, ...prev], false);
      toast({
        title: "Loot Acquired!",
        description: `${game.game_name} has been added to your shelf.`,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to add game";
      // WHY: 409 means already in library — treat as success, not error
      if (message.includes("already")) {
        setAddedSlugs((prev) => new Set(prev).add(game.game_slug));
        mutateLibrary();
        toast({
          title: "Already in Library",
          description: `${game.game_name} is already in your library.`,
        });
      } else {
        toast({
          title: "Failed to Add",
          description: message,
          variant: "destructive",
        });
      }
    } finally {
      setAddingSlugs((prev) => {
        const next = new Set(prev);
        next.delete(game.game_slug);
        return next;
      });
    }
  };

  /**
   * Determine the button state for a game card.
   * Returns the appropriate button props based on whether the game
   * is already in the library, currently being added, or available.
   */
  const getButtonState = (game: CatalogEntry) => {
    const isInLibrary = isGameInLibrary(game);
    const isAdding = addingSlugs.has(game.game_slug);

    if (isInLibrary) {
      return { disabled: true, icon: <Check className="mr-2 h-4 w-4" />, label: "Claimed ✓" };
    }
    if (isAdding) {
      return { disabled: true, icon: <Loader2 className="mr-2 h-4 w-4 animate-spin" />, label: "Claiming..." };
    }
    return { disabled: false, icon: <Plus className="mr-2 h-4 w-4" />, label: "Claim" };
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">The Armory</h1>
          <p className="text-muted-foreground mt-1">
            Browse 1000+ games. Claim the ones you play.
          </p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search by game name or publisher..."
          className="pl-10"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {useFallbackCatalog && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          Armory is in offline fallback mode (backend unavailable). Showing a limited local list only.
        </div>
      )}

      {isLoading ? (
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : !useFallbackCatalog && allGames.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/50 text-center">
          <Gamepad2 className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">Armory catalog is empty</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Seed the backend catalog and refresh this page.
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/50 text-center">
          <Gamepad2 className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">No quests match that search</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Try a different incantation.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((game, i) => {
            const btnState = getButtonState(game);
            return (
              <motion.div
                key={game.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: i * 0.03 }}
              >
                <Card className="group relative overflow-hidden border-border/50 bg-card hover:border-primary/40 transition-colors h-full flex flex-col">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base">{game.game_name}</CardTitle>
                      {game.id.startsWith("common-") ? (
                        <Badge variant="secondary" className="ml-2 shrink-0 text-xs">
                          <Star className="mr-1 h-3 w-3" /> Popular
                        </Badge>
                      ) : (
                        <Badge variant="default" className="ml-2 shrink-0 text-xs">
                          <Shield className="mr-1 h-3 w-3" /> Official
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="pb-3 flex-1">
                    <div className="space-y-1 text-sm text-muted-foreground">
                      <p>{game.publisher_name}</p>
                      <p className="text-xs">Version {game.version}</p>
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button
                      className="w-full relative group overflow-hidden"
                      size="sm"
                      disabled={btnState.disabled}
                      onClick={() => handleAddToLibrary(game)}
                    >
                      <span className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-shimmer" />
                      {btnState.icon}
                      {btnState.label}
                    </Button>
                  </CardFooter>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
