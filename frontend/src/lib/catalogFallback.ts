import { CatalogEntry } from "@/lib/api";

/**
 * Small fallback set used only when the backend catalog is unavailable.
 * The real source of truth is GET /api/v1/catalog.
 */
export const FALLBACK_CATALOG_GAMES: CatalogEntry[] = [
  { id: "common-dnd5e", game_name: "Dungeons & Dragons 5th Edition", game_slug: "dnd-5e", publisher_name: "Wizards of the Coast", version: "2024", status: "UPLOAD_REQUIRED" },
  { id: "common-pathfinder2e", game_name: "Pathfinder 2nd Edition", game_slug: "pathfinder-2e", publisher_name: "Paizo", version: "Remaster", status: "UPLOAD_REQUIRED" },
  { id: "common-mtg", game_name: "Magic: The Gathering", game_slug: "mtg", publisher_name: "Wizards of the Coast", version: "2024", status: "UPLOAD_REQUIRED" },
  { id: "common-catan", game_name: "Catan (6th Ed)", game_slug: "catan-6e", publisher_name: "Catan Studio", version: "6th Ed", status: "UPLOAD_REQUIRED" },
  { id: "common-warhammer40k", game_name: "Warhammer 40,000 (10th Ed)", game_slug: "warhammer-40k-10", publisher_name: "Games Workshop", version: "10th Ed", status: "UPLOAD_REQUIRED" },
  { id: "common-pandemic", game_name: "Pandemic", game_slug: "pandemic", publisher_name: "Z-Man Games", version: "2020", status: "UPLOAD_REQUIRED" },
];
