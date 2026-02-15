"""publishers.py — Publisher management and API key authentication.

Publishers are game companies (e.g., Wizards of the Coast) that can
push official rulesets to the Arbiter AI catalog. Each publisher gets
a unique API key for authenticating their API calls.

Endpoints:
    POST /api/v1/publishers/                → Register a new publisher (returns API key)
    GET  /api/v1/publishers/{id}            → Get publisher details
    POST /api/v1/publishers/{id}/games      → Add an official ruleset to catalog
    POST /api/v1/publishers/{id}/rotate-key → Rotate API key

Called by: Publisher onboarding flow, game catalog management.
Depends on: deps.py (get_db), tables.py (Publisher, OfficialRuleset)

Architecture note for AI agents:
    Publisher authentication uses API keys (not JWT). Each publisher gets
    a unique key on creation (returned once in plaintext). All subsequent
    requests must include `X-Publisher-Key: <key>` header. The key is
    stored as a SHA-256 hash in the database for security.

    The admin portal (admin.py) also manages publishers — it can verify
    them and update their details. Publishers must be verified=True
    before their official rulesets appear in the public catalog.
"""

import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.tables import OfficialRuleset, Publisher

router = APIRouter(prefix="/api/v1/publishers", tags=["publishers"])


# ─── Schemas ───────────────────────────────────────────────────────────────────


class PublisherCreate(BaseModel):
    """Request body for registering a new publisher.

    Fields:
        name: Publisher display name (e.g., 'Wizards of the Coast').
        slug: URL-safe unique identifier (e.g., 'wizards-of-the-coast').
        contact_email: Primary contact email for the publisher.
    """

    name: str
    slug: str
    contact_email: EmailStr


class PublisherRead(BaseModel):
    """Response shape for publisher details (without API key)."""

    id: uuid.UUID
    name: str
    slug: str
    contact_email: str
    verified: bool


class PublisherCreateResponse(BaseModel):
    """Response for publisher creation — includes the API key (shown once).

    IMPORTANT: The api_key is only returned at creation time. Store it
    securely. If lost, use the rotate-key endpoint to generate a new one.
    """

    id: uuid.UUID
    name: str
    slug: str
    contact_email: str
    verified: bool
    api_key: str  # Only returned once at creation


class OfficialRulesetCreate(BaseModel):
    """Request body for adding an official ruleset to the catalog.

    Fields:
        game_name: Human-readable game name.
        game_slug: URL-safe identifier (must be globally unique).
        version: Version string (e.g., '10th Edition').
        pinecone_namespace: Pinecone namespace where vectors are stored.
    """

    game_name: str
    game_slug: str
    version: str = "1.0"
    pinecone_namespace: str


class OfficialRulesetRead(BaseModel):
    """Response shape for an official ruleset entry."""

    id: uuid.UUID
    game_name: str
    game_slug: str
    version: str
    status: str
    chunk_count: int


# ─── API Key Helpers ──────────────────────────────────────────────────────────


def _generate_api_key() -> tuple[str, str]:
    """Generate a secure API key and its SHA-256 hash.

    Returns:
        Tuple of (plaintext_key, sha256_hash).

    WHY SHA-256 instead of bcrypt: Publisher API keys are used on every
    request and need fast comparison. SHA-256 is sufficient for 256-bit
    random keys (unlike passwords which need slow hashing).
    """
    # WHY: 32-byte key gives 256 bits of entropy — brute-force infeasible
    plaintext = f"arb_{secrets.token_hex(32)}"
    hashed = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, hashed


def _hash_key(key: str) -> str:
    """Hash an API key for comparison against stored hashes."""
    return hashlib.sha256(key.encode()).hexdigest()


async def _verify_publisher_key(
    publisher_id: uuid.UUID,
    x_publisher_key: str,
    db: AsyncSession,
) -> Publisher:
    """Verify a publisher API key and return the publisher record.

    Args:
        publisher_id: UUID of the publisher to verify.
        x_publisher_key: Plaintext API key from X-Publisher-Key header.
        db: Async database session.

    Returns:
        The verified Publisher ORM object.

    Raises:
        HTTPException: 401 if key is missing, 403 if key doesn't match,
                       404 if publisher not found.
    """
    if not x_publisher_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Publisher-Key header.",
        )

    publisher = await db.get(Publisher, publisher_id)
    if not publisher:
        raise HTTPException(status_code=404, detail="Publisher not found")

    # WHY: Compare hashes, never store or compare plaintext keys
    if publisher.api_key_hash != _hash_key(x_publisher_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return publisher


# ─── Create Publisher ──────────────────────────────────────────────────────────


@router.post("/", response_model=PublisherCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_publisher(
    publisher: PublisherCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new publisher and return a one-time API key.

    Auth: None (open registration — admin must verify before catalog access).
    Rate limit: None.
    Tier: N/A.

    IMPORTANT: The API key is only returned in this response. Store it
    securely. If lost, use POST /{id}/rotate-key to generate a new one.

    Args:
        publisher: Publisher registration details.

    Returns:
        Publisher details including the plaintext API key.

    Raises:
        HTTPException: 409 if slug already exists.
    """
    # Check if slug exists
    stmt = select(Publisher).where(Publisher.slug == publisher.slug)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Publisher with this slug already exists",
        )

    # Generate a secure API key
    plaintext_key, hashed_key = _generate_api_key()

    db_publisher = Publisher(
        name=publisher.name,
        slug=publisher.slug,
        contact_email=publisher.contact_email,
        api_key_hash=hashed_key,
        verified=False,  # Must be verified by admin before catalog access
    )
    db.add(db_publisher)
    await db.commit()
    await db.refresh(db_publisher)

    return PublisherCreateResponse(
        id=db_publisher.id,
        name=db_publisher.name,
        slug=db_publisher.slug,
        contact_email=db_publisher.contact_email,
        verified=db_publisher.verified,
        api_key=plaintext_key,
    )


# ─── Get Publisher ─────────────────────────────────────────────────────────────


@router.get("/{publisher_id}", response_model=PublisherRead)
async def get_publisher(
    publisher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get publisher details by ID.

    Auth: None (public endpoint).
    Rate limit: None.
    Tier: N/A.

    Args:
        publisher_id: UUID of the publisher.

    Returns:
        Publisher details (without API key).

    Raises:
        HTTPException: 404 if not found.
    """
    publisher = await db.get(Publisher, publisher_id)
    if not publisher:
        raise HTTPException(status_code=404, detail="Publisher not found")
    return publisher


# ─── Create Official Ruleset ─────────────────────────────────────────────────


@router.post("/{publisher_id}/games", response_model=OfficialRulesetRead, status_code=status.HTTP_201_CREATED)
async def create_official_ruleset(
    publisher_id: uuid.UUID,
    ruleset: OfficialRulesetCreate,
    x_publisher_key: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Add an official ruleset to the catalog under this publisher.

    Auth: X-Publisher-Key header required (publisher API key).
    Rate limit: None.
    Tier: N/A.

    WHY API key auth: Publishers are external companies, not Arbiter users.
    They authenticate with API keys rather than JWT tokens.

    Args:
        publisher_id: UUID of the owning publisher.
        ruleset: Game details (name, slug, version, namespace).

    Returns:
        The created official ruleset entry.

    Raises:
        HTTPException: 401/403 if key invalid, 404 if publisher not found,
                       409 if game slug already exists.
    """
    # Verify publisher and API key
    await _verify_publisher_key(publisher_id, x_publisher_key, db)

    # Check game slug uniqueness globally
    stmt = select(OfficialRuleset).where(OfficialRuleset.game_slug == ruleset.game_slug)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Game with this slug already exists",
        )

    db_ruleset = OfficialRuleset(
        publisher_id=publisher_id,
        game_name=ruleset.game_name,
        game_slug=ruleset.game_slug,
        version=ruleset.version,
        pinecone_namespace=ruleset.pinecone_namespace,
        status="CREATED",
    )
    db.add(db_ruleset)
    await db.commit()
    await db.refresh(db_ruleset)
    return db_ruleset


# ─── Rotate API Key ──────────────────────────────────────────────────────────


@router.post("/{publisher_id}/rotate-key")
async def rotate_api_key(
    publisher_id: uuid.UUID,
    x_publisher_key: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Rotate the publisher's API key. Requires the current key.

    Auth: X-Publisher-Key header required (current key).
    Rate limit: None.
    Tier: N/A.

    WHY: Key rotation is a security best practice. If a key is
    compromised, the publisher can rotate it without admin intervention.
    The old key is immediately invalidated.

    Args:
        publisher_id: UUID of the publisher.

    Returns:
        Dict with the new API key (shown once).

    Raises:
        HTTPException: 401/403 if current key invalid.
    """
    publisher = await _verify_publisher_key(publisher_id, x_publisher_key, db)

    # Generate new key and invalidate the old one
    new_plaintext, new_hash = _generate_api_key()
    publisher.api_key_hash = new_hash
    await db.commit()

    return {
        "message": "API key rotated successfully. Store the new key securely.",
        "api_key": new_plaintext,
    }
