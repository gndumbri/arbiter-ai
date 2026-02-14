"use client";

import { useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import { Search, Plus, Star, Gamepad2, Shield, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api, CatalogEntry } from "@/lib/api";

// Common games that are always available (pre-seeded)
const COMMON_GAMES: CatalogEntry[] = [
  { id: "common-dnd5e", game_name: "Dungeons & Dragons 5th Edition", game_slug: "dnd-5e", publisher_name: "Wizards of the Coast", version: "2024", status: "READY" },
  { id: "common-pathfinder2e", game_name: "Pathfinder 2nd Edition", game_slug: "pathfinder-2e", publisher_name: "Paizo", version: "2023", status: "READY" },
  { id: "common-mtg", game_name: "Magic: The Gathering", game_slug: "mtg", publisher_name: "Wizards of the Coast", version: "2024", status: "READY" },
  { id: "common-catan", game_name: "Catan", game_slug: "catan", publisher_name: "Catan Studio", version: "6th Ed", status: "READY" },
  { id: "common-warhammer40k", game_name: "Warhammer 40,000", game_slug: "warhammer-40k", publisher_name: "Games Workshop", version: "10th Ed", status: "READY" },
  { id: "common-ticket-to-ride", game_name: "Ticket to Ride", game_slug: "ticket-to-ride", publisher_name: "Days of Wonder", version: "2024", status: "READY" },
  { id: "common-wingspan", game_name: "Wingspan", game_slug: "wingspan", publisher_name: "Stonemaier Games", version: "2nd Print", status: "READY" },
  { id: "common-gloomhaven", game_name: "Gloomhaven", game_slug: "gloomhaven", publisher_name: "Cephalofair Games", version: "2nd Ed", status: "READY" },
  { id: "common-spirit-island", game_name: "Spirit Island", game_slug: "spirit-island", publisher_name: "Greater Than Games", version: "2022", status: "READY" },
  { id: "common-scythe", game_name: "Scythe", game_slug: "scythe", publisher_name: "Stonemaier Games", version: "2020", status: "READY" },
  { id: "common-7wonders", game_name: "7 Wonders", game_slug: "7-wonders", publisher_name: "Repos Production", version: "2nd Ed", status: "READY" },
  { id: "common-pandemic", game_name: "Pandemic", game_slug: "pandemic", publisher_name: "Z-Man Games", version: "2020", status: "READY" },
];

export default function CatalogPage() {
  const [search, setSearch] = useState("");
  const { data: backendCatalog, isLoading } = useSWR("catalog", api.listCatalog, {
    onError: () => {}, // Gracefully handle backend being down
  });

  // Merge backend catalog with common games (dedup by slug)
  const allGames = [...COMMON_GAMES];
  if (backendCatalog) {
    for (const entry of backendCatalog) {
      if (!allGames.find((g) => g.game_slug === entry.game_slug)) {
        allGames.push(entry);
      }
    }
  }

  const filtered = allGames.filter(
    (g) =>
      g.game_name.toLowerCase().includes(search.toLowerCase()) ||
      g.publisher_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Game Catalog</h1>
          <p className="text-muted-foreground mt-1">
            Browse official rulesets or add a game to your library.
          </p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search games by name or publisher..."
          className="pl-10"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-border/50 text-center">
          <Gamepad2 className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">No games found</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Try a different search term.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((game, i) => (
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
                  <Button className="w-full relative group overflow-hidden" size="sm">
                    <span className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-shimmer" />
                    <Plus className="mr-2 h-4 w-4" />
                    Add to Library
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
