"""
seed_catalog.py — Populate the catalog with metadata-only entries for popular games.

LEGAL NOTE: We do NOT seed any rules text or copyrighted content.
We only seed game titles and edition info (publicly known facts).
This enables autocomplete and discovery without copyright violation.
Games are seeded with status="UPLOAD_REQUIRED" so the UI can prompt
users to upload their own legally-owned rulebook.

Usage:
    cd backend
    uv run python -m scripts.seed_catalog
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.tables import OfficialRuleset, Publisher

logger = structlog.get_logger()


# ── The Catalog ──────────────────────────────────────────────────────────────
# WHY: Top-rated BGG + classic games that users are most likely to search for.
# We only store the name, slug, and edition — no rules content.
# Organized by category for maintainability.

# fmt: off
POPULAR_GAMES = [
    # ── Classic / Mass Market ────────────────────────────────────────────────
    {"name": "Catan (6th Ed)",             "slug": "catan-6e",              "pub": "Catan Studio",           "ver": "6th Ed"},
    {"name": "Ticket to Ride",             "slug": "ticket-to-ride",        "pub": "Days of Wonder",         "ver": "2024"},
    {"name": "Pandemic",                   "slug": "pandemic",              "pub": "Z-Man Games",            "ver": "2020"},
    {"name": "7 Wonders (2nd Ed)",         "slug": "7-wonders-2e",          "pub": "Repos Production",       "ver": "2nd Ed"},
    {"name": "Carcassonne (3rd Ed)",       "slug": "carcassonne-3e",        "pub": "Z-Man Games",            "ver": "3rd Ed"},
    {"name": "Codenames",                  "slug": "codenames",             "pub": "Czech Games Edition",    "ver": "2015"},
    {"name": "Azul",                       "slug": "azul",                  "pub": "Plan B Games",           "ver": "2017"},
    {"name": "Splendor",                   "slug": "splendor",              "pub": "Space Cowboys",          "ver": "2014"},
    {"name": "Dixit",                      "slug": "dixit",                 "pub": "Libellud",               "ver": "2021"},
    {"name": "King of Tokyo",              "slug": "king-of-tokyo",         "pub": "IELLO",                  "ver": "2nd Ed"},
    {"name": "Sushi Go Party!",            "slug": "sushi-go-party",        "pub": "Gamewright",             "ver": "2016"},
    {"name": "Clue",                       "slug": "clue",                  "pub": "Hasbro",                 "ver": "Classic"},
    {"name": "Risk",                       "slug": "risk",                  "pub": "Hasbro",                 "ver": "Classic"},
    {"name": "Monopoly",                   "slug": "monopoly",              "pub": "Hasbro",                 "ver": "Classic"},
    {"name": "Scrabble",                   "slug": "scrabble",              "pub": "Mattel",                 "ver": "Classic"},
    {"name": "Chess",                      "slug": "chess",                 "pub": "FIDE",                   "ver": "Standard"},
    {"name": "Trivial Pursuit",            "slug": "trivial-pursuit",       "pub": "Hasbro",                 "ver": "Classic"},
    {"name": "Settlers of Catan: Seafarers", "slug": "catan-seafarers",    "pub": "Catan Studio",           "ver": "2024"},
    {"name": "Ticket to Ride: Europe",     "slug": "ticket-to-ride-europe", "pub": "Days of Wonder",         "ver": "2024"},

    # ── Strategy / Euro ──────────────────────────────────────────────────────
    {"name": "Wingspan (2nd Print)",       "slug": "wingspan",              "pub": "Stonemaier Games",       "ver": "2nd Print"},
    {"name": "Scythe",                     "slug": "scythe",                "pub": "Stonemaier Games",       "ver": "2020"},
    {"name": "Terraforming Mars",          "slug": "terraforming-mars",     "pub": "FryxGames",              "ver": "2023"},
    {"name": "Brass: Birmingham",          "slug": "brass-birmingham",      "pub": "Roxley",                 "ver": "2018"},
    {"name": "Viticulture Essential Ed",   "slug": "viticulture-ee",        "pub": "Stonemaier Games",       "ver": "EE"},
    {"name": "Cascadia",                   "slug": "cascadia",              "pub": "Flatout Games",          "ver": "2022"},
    {"name": "Everdell",                   "slug": "everdell",              "pub": "Starling Games",         "ver": "2023"},
    {"name": "Ark Nova",                   "slug": "ark-nova",              "pub": "Capstone Games",         "ver": "2022"},
    {"name": "Agricola (Revised)",         "slug": "agricola-rev",          "pub": "Lookout Games",          "ver": "Revised"},
    {"name": "Dominion (2nd Ed)",          "slug": "dominion-2e",           "pub": "Rio Grande Games",       "ver": "2nd Ed"},
    {"name": "Power Grid",                 "slug": "power-grid",            "pub": "Rio Grande Games",       "ver": "Recharged"},
    {"name": "Puerto Rico (2022 Ed)",      "slug": "puerto-rico",           "pub": "alea/Ravensburger",      "ver": "2022"},
    {"name": "Concordia",                  "slug": "concordia",             "pub": "PD-Verlag",              "ver": "2013"},
    {"name": "Great Western Trail (2nd Ed)", "slug": "gwt-2e",             "pub": "eggertspiele",           "ver": "2nd Ed"},
    {"name": "Castles of Burgundy",        "slug": "castles-of-burgundy",   "pub": "alea/Ravensburger",      "ver": "20th Ann"},
    {"name": "Orleans",                    "slug": "orleans",               "pub": "dlp Games",              "ver": "2015"},
    {"name": "A Feast for Odin",           "slug": "feast-for-odin",        "pub": "Z-Man Games",            "ver": "2016"},
    {"name": "Clans of Caledonia",         "slug": "clans-of-caledonia",    "pub": "Karma Games",            "ver": "2017"},
    {"name": "Barrage",                    "slug": "barrage",               "pub": "Cranio Creations",       "ver": "2019"},

    # ── Cooperative ──────────────────────────────────────────────────────────
    {"name": "Gloomhaven (2nd Ed)",        "slug": "gloomhaven-2e",         "pub": "Cephalofair Games",      "ver": "2nd Ed"},
    {"name": "Spirit Island",              "slug": "spirit-island",         "pub": "Greater Than Games",     "ver": "2022"},
    {"name": "Pandemic Legacy: S1",        "slug": "pandemic-legacy-s1",    "pub": "Z-Man Games",            "ver": "2015"},
    {"name": "Pandemic Legacy: S2",        "slug": "pandemic-legacy-s2",    "pub": "Z-Man Games",            "ver": "2017"},
    {"name": "Mansions of Madness 2E",     "slug": "mansions-of-madness-2e","pub": "Fantasy Flight Games",   "ver": "2nd Ed"},
    {"name": "Forbidden Desert",           "slug": "forbidden-desert",      "pub": "Gamewright",             "ver": "2013"},
    {"name": "Arkham Horror: LCG",         "slug": "arkham-horror-lcg",     "pub": "Fantasy Flight Games",   "ver": "Revised"},
    {"name": "The Crew: Deep Sea",         "slug": "the-crew-deep-sea",     "pub": "KOSMOS",                 "ver": "2021"},
    {"name": "Frosthaven",                 "slug": "frosthaven",            "pub": "Cephalofair Games",      "ver": "2023"},
    {"name": "Marvel Champions: LCG",      "slug": "marvel-champions-lcg",  "pub": "Fantasy Flight Games",   "ver": "2019"},

    # ── Area Control / War ───────────────────────────────────────────────────
    {"name": "Root",                       "slug": "root",                  "pub": "Leder Games",            "ver": "2018"},
    {"name": "Twilight Imperium 4",        "slug": "ti4",                   "pub": "Fantasy Flight Games",   "ver": "4th Ed"},
    {"name": "Dune: Imperium",             "slug": "dune-imperium",         "pub": "Dire Wolf Digital",      "ver": "2020"},
    {"name": "Eclipse: 2nd Dawn",          "slug": "eclipse-2nd-dawn",      "pub": "Lautapelit.fi",          "ver": "2nd Ed"},
    {"name": "Blood Rage",                 "slug": "blood-rage",            "pub": "CMON",                   "ver": "2015"},
    {"name": "Rising Sun",                 "slug": "rising-sun",            "pub": "CMON",                   "ver": "2018"},
    {"name": "War of the Ring (2nd Ed)",   "slug": "war-of-the-ring-2e",    "pub": "Ares Games",             "ver": "2nd Ed"},
    {"name": "Kemet: Blood and Sand",      "slug": "kemet-blood-and-sand",  "pub": "Matagot",                "ver": "2021"},
    {"name": "Star Wars: Rebellion",       "slug": "sw-rebellion",          "pub": "Fantasy Flight Games",   "ver": "2016"},

    # ── Deck-Building / Engine ───────────────────────────────────────────────
    {"name": "Clank!",                     "slug": "clank",                 "pub": "Renegade Game Studios",  "ver": "2016"},
    {"name": "Star Realms",               "slug": "star-realms",            "pub": "White Wizard Games",     "ver": "2014"},
    {"name": "Aeon's End (3rd Ed)",        "slug": "aeons-end-3e",          "pub": "Indie Boards & Cards",   "ver": "3rd Ed"},
    {"name": "Legendary: A Marvel DBG",    "slug": "legendary-marvel",      "pub": "Upper Deck",             "ver": "2012"},
    {"name": "Undaunted: Normandy",        "slug": "undaunted-normandy",    "pub": "Osprey Games",           "ver": "2019"},
    {"name": "Res Arcana",                 "slug": "res-arcana",            "pub": "Sand Castle Games",      "ver": "2019"},

    # ── Worker Placement ─────────────────────────────────────────────────────
    {"name": "Lords of Waterdeep",         "slug": "lords-of-waterdeep",    "pub": "Wizards of the Coast",   "ver": "2012"},
    {"name": "Paladins of the West Kingdom", "slug": "paladins-wk",        "pub": "Garphill Games",         "ver": "2019"},
    {"name": "Architects of the West Kingdom", "slug": "architects-wk",    "pub": "Garphill Games",         "ver": "2018"},
    {"name": "Caverna",                    "slug": "caverna",               "pub": "Lookout Games",          "ver": "2013"},
    {"name": "Stone Age",                  "slug": "stone-age",             "pub": "Z-Man Games",            "ver": "2008"},

    # ── RPGs / Tabletop ──────────────────────────────────────────────────────
    {"name": "Dungeons & Dragons 5th Edition",   "slug": "dnd-5e",          "pub": "Wizards of the Coast",   "ver": "2024"},
    {"name": "D&D 2024 Player's Handbook",       "slug": "dnd-2024-phb",    "pub": "Wizards of the Coast",   "ver": "2024"},
    {"name": "Pathfinder 2nd Edition",           "slug": "pathfinder-2e",    "pub": "Paizo",                  "ver": "Remaster"},
    {"name": "Starfinder 2nd Edition",           "slug": "starfinder-2e",    "pub": "Paizo",                  "ver": "2024"},
    {"name": "Call of Cthulhu 7th Ed",           "slug": "coc-7e",           "pub": "Chaosium",               "ver": "7th Ed"},
    {"name": "Mothership RPG (1st Ed)",          "slug": "mothership-1e",    "pub": "Tuesday Knight Games",   "ver": "1st Ed"},
    {"name": "Blades in the Dark",               "slug": "blades-in-dark",   "pub": "Evil Hat Productions",   "ver": "2017"},
    {"name": "Mork Borg",                        "slug": "mork-borg",        "pub": "Free League Publishing", "ver": "2020"},
    {"name": "Shadowdark",                       "slug": "shadowdark",       "pub": "Arcane Library",         "ver": "2023"},
    {"name": "GURPS Basic Set",                  "slug": "gurps-basic",      "pub": "Steve Jackson Games",    "ver": "4th Ed"},
    {"name": "Savage Worlds SWADE",              "slug": "savage-worlds",    "pub": "Pinnacle Entertainment", "ver": "SWADE"},

    # ── TCG / Collectible Card Games ─────────────────────────────────────────
    {"name": "Magic: The Gathering",       "slug": "mtg",                   "pub": "Wizards of the Coast",   "ver": "2024"},
    {"name": "Pokémon TCG",                "slug": "pokemon-tcg",           "pub": "The Pokémon Company",    "ver": "2024"},
    {"name": "Yu-Gi-Oh! TCG",              "slug": "yugioh-tcg",            "pub": "Konami",                 "ver": "Master Rules"},
    {"name": "KeyForge",                   "slug": "keyforge",              "pub": "Ghost Galaxy",           "ver": "2024"},
    {"name": "Flesh and Blood",            "slug": "flesh-and-blood",       "pub": "Legend Story Studios",   "ver": "2024"},
    {"name": "Lorcana",                    "slug": "lorcana",               "pub": "Ravensburger",           "ver": "2024"},
    {"name": "Star Wars: Unlimited",       "slug": "sw-unlimited",          "pub": "Fantasy Flight Games",   "ver": "2024"},
    {"name": "One Piece Card Game",        "slug": "one-piece-card",        "pub": "Bandai",                 "ver": "2024"},

    # ── Miniatures / Wargaming ───────────────────────────────────────────────
    {"name": "Warhammer 40,000 (10th Ed)", "slug": "warhammer-40k-10",      "pub": "Games Workshop",         "ver": "10th Ed"},
    {"name": "Warhammer: Age of Sigmar 4", "slug": "aos-4",                 "pub": "Games Workshop",         "ver": "4th Ed"},
    {"name": "Star Wars: Legion",          "slug": "sw-legion",             "pub": "Atomic Mass Games",      "ver": "2023"},
    {"name": "Marvel: Crisis Protocol",    "slug": "marvel-crisis-protocol", "pub": "Atomic Mass Games",     "ver": "2024"},
    {"name": "Bolt Action (3rd Ed)",       "slug": "bolt-action-3e",        "pub": "Warlord Games",          "ver": "3rd Ed"},

    # ── Social / Party ───────────────────────────────────────────────────────
    {"name": "Wavelength",                 "slug": "wavelength",            "pub": "CMYK",                   "ver": "2019"},
    {"name": "Secret Hitler",              "slug": "secret-hitler",         "pub": "Goat Wolf & Cabbage",    "ver": "2016"},
    {"name": "The Resistance: Avalon",     "slug": "avalon",                "pub": "Indie Boards & Cards",   "ver": "2012"},
    {"name": "Coup",                       "slug": "coup",                  "pub": "Indie Boards & Cards",   "ver": "2012"},
    {"name": "One Night Ultimate Werewolf","slug": "one-night-werewolf",    "pub": "Bezier Games",           "ver": "2014"},
    {"name": "Exploding Kittens",          "slug": "exploding-kittens",     "pub": "Exploding Kittens LLC",  "ver": "2015"},
    {"name": "Telestrations",              "slug": "telestrations",         "pub": "The Op",                 "ver": "2009"},
    {"name": "Cards Against Humanity",     "slug": "cah",                   "pub": "Cards Against Humanity", "ver": "2011"},
    {"name": "Unstable Unicorns",          "slug": "unstable-unicorns",     "pub": "Unstable Games",         "ver": "2017"},
    {"name": "Werewolf",                   "slug": "werewolf",              "pub": "Bezier Games",           "ver": "Ultimate"},
    {"name": "Blood on the Clocktower",    "slug": "blood-on-clocktower",   "pub": "The Pandemonium Inst.",  "ver": "2022"},

    # ── Abstract / Puzzle ────────────────────────────────────────────────────
    {"name": "Patchwork",                  "slug": "patchwork",             "pub": "Lookout Games",          "ver": "2014"},
    {"name": "Hive",                       "slug": "hive",                  "pub": "Gen42 Games",            "ver": "Carbon"},
    {"name": "Santorini",                  "slug": "santorini",             "pub": "Roxley",                 "ver": "2016"},
    {"name": "Onitama",                    "slug": "onitama",               "pub": "Arcane Wonders",         "ver": "2014"},
    {"name": "Quarto",                     "slug": "quarto",                "pub": "Gigamic",                "ver": "Classic"},

    # ── Narrative / Legacy ───────────────────────────────────────────────────
    {"name": "Betrayal at House on the Hill", "slug": "betrayal-hoh",       "pub": "Avalon Hill/Hasbro",     "ver": "3rd Ed"},
    {"name": "Clank! Legacy",              "slug": "clank-legacy",          "pub": "Renegade Game Studios",  "ver": "2019"},
    {"name": "Forgotten Waters",           "slug": "forgotten-waters",      "pub": "Plaid Hat Games",        "ver": "2020"},
    {"name": "Descent: Legends of the Dark", "slug": "descent-lotd",       "pub": "Fantasy Flight Games",   "ver": "2021"},
    {"name": "Sleeping Gods",              "slug": "sleeping-gods",         "pub": "Red Raven Games",        "ver": "2021"},
    {"name": "Mice and Mystics",           "slug": "mice-and-mystics",      "pub": "Plaid Hat Games",        "ver": "2012"},

    # ── Recent Hits / 2023-2024 Hotness ──────────────────────────────────────
    {"name": "Earthborne Rangers",         "slug": "earthborne-rangers",    "pub": "Earthborne Games",       "ver": "2024"},
    {"name": "Sky Team",                   "slug": "sky-team",              "pub": "Le Scorpion Masqué",     "ver": "2024"},
    {"name": "Daybreak",                   "slug": "daybreak",              "pub": "CMYK",                   "ver": "2023"},
    {"name": "Harmonies",                  "slug": "harmonies",             "pub": "Libellud",               "ver": "2024"},
    {"name": "Arcs",                       "slug": "arcs",                  "pub": "Leder Games",            "ver": "2024"},
    {"name": "Wyrmspan",                   "slug": "wyrmspan",              "pub": "Stonemaier Games",       "ver": "2024"},
    {"name": "Nucleum",                    "slug": "nucleum",               "pub": "Board&Dice",             "ver": "2023"},
    {"name": "Voidfall",                   "slug": "voidfall",              "pub": "Mindclash Games",        "ver": "2023"},
    {"name": "Heat: Pedal to the Metal",   "slug": "heat",                  "pub": "Days of Wonder",         "ver": "2022"},

    # ── Family Favorites ─────────────────────────────────────────────────────
    {"name": "Kingdomino",                 "slug": "kingdomino",            "pub": "Blue Orange Games",      "ver": "2016"},
    {"name": "Quacks of Quedlinburg",      "slug": "quacks",                "pub": "North Star Games",       "ver": "2018"},
    {"name": "My City",                    "slug": "my-city",               "pub": "KOSMOS",                 "ver": "2020"},
    {"name": "Mysterium",                  "slug": "mysterium",             "pub": "Libellud",               "ver": "2015"},
    {"name": "Jaipur",                     "slug": "jaipur",                "pub": "Space Cowboys",          "ver": "2nd Ed"},
    {"name": "Century: Spice Road",        "slug": "century-spice-road",    "pub": "Plan B Games",           "ver": "2017"},
    {"name": "Photosynthesis",             "slug": "photosynthesis",        "pub": "Blue Orange Games",      "ver": "2017"},
    {"name": "Takenoko",                   "slug": "takenoko",              "pub": "Bombyx",                 "ver": "2011"},
    {"name": "Sagrada",                    "slug": "sagrada",               "pub": "Floodgate Games",        "ver": "2017"},
]
# fmt: on


async def seed() -> None:
    """Seed the database with metadata-only game entries.

    Idempotent: skips any games whose slug already exists in the DB.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        logger.info("seed_catalog_start", game_count=len(POPULAR_GAMES))

        # 1. Upsert a "Community Catalog" publisher (idempotent)
        existing = await db.execute(
            select(Publisher).where(Publisher.slug == "community")
        )
        community_pub = existing.scalar_one_or_none()

        if community_pub is None:
            community_pub = Publisher(
                id=uuid.uuid4(),
                name="Community Catalog",
                slug="community",
                contact_email="support@arbiter-ai.com",
                api_key_hash="seeder_placeholder",
                verified=True,
            )
            db.add(community_pub)
            await db.flush()
            logger.info("seed_publisher_created", publisher_id=str(community_pub.id))
        else:
            logger.info("seed_publisher_exists", publisher_id=str(community_pub.id))

        # 2. Seed games (skip duplicates by slug)
        seeded = 0
        for game in POPULAR_GAMES:
            existing_game = await db.execute(
                select(OfficialRuleset).where(
                    OfficialRuleset.game_slug == game["slug"]
                )
            )
            if existing_game.scalar_one_or_none() is not None:
                logger.debug("seed_game_exists", slug=game["slug"])
                continue

            ruleset = OfficialRuleset(
                publisher_id=community_pub.id,
                game_name=game["name"],
                game_slug=game["slug"],
                publisher_display_name=game["pub"],
                # WHY: "UPLOAD_REQUIRED" signals the frontend to prompt users
                # to upload their own rulebook before they can play.
                status="UPLOAD_REQUIRED",
                pinecone_namespace=f"placeholder_{game['slug']}",
                version=game.get("ver", "1.0"),
            )
            db.add(ruleset)
            seeded += 1

        await db.commit()
        logger.info(
            "seed_catalog_complete",
            seeded=seeded,
            skipped=len(POPULAR_GAMES) - seeded,
            total=len(POPULAR_GAMES),
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
