"""Dev-only convenience seeding, ported from the Rust backend's lib.rs."""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import (
    Album,
    ArtistProfile,
    Photo,
    Subscription,
    User,
    UserProfile,
)
from app.models.tiers import TIER_FREE, TIER_PAID, TIER_PREMIUM
from app.services import storage
from app.services.placeholders import gradient_png
from app.services.restore import restore_from_media
from app.services.security import hash_password
from app.services.slugs import artist_media_key

DEV_ADMIN_EMAIL = "admin@mail.com"
DEV_ADMIN_PASSWORD = "Password1234!"
DEV_CLIENT_EMAIL = "client@mail.com"
DEV_CLIENT_PASSWORD = "Password1234!"
DEV_ARTIST_EMAIL = "artist@mail.com"
DEV_ARTIST_PASSWORD = "Password1234!"
DEV_ARTIST2_EMAIL = "ted@mail.com"
DEV_ARTIST2_PASSWORD = "Password1234!"
DEV_PREMIUM_EMAIL = "premium@mail.com"
DEV_PREMIUM_PASSWORD = "Password1234!"


async def seed_dev_admin(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Guarantee a known admin login locally.

    Gated on NODE_ENV=development so these credentials can never appear in a
    qa/prod database.
    """
    if settings.env != "development":
        return
    await _seed_user(sessionmaker, DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD, "admin")


async def _seed_user(
    sessionmaker: async_sessionmaker[AsyncSession],
    email: str,
    password: str,
    role: str,
) -> None:
    """A verified user with a filled profile, so no gate stops it."""
    async with sessionmaker() as session:
        user_id = (
            await session.execute(
                insert(User)
                .values(
                    email=email,
                    password=hash_password(password),
                    role=role,
                    email_verified=True,
                )
                .on_conflict_do_nothing(index_elements=["email"])
                .returning(User.id)
            )
        ).scalar_one_or_none()

        if user_id is None:
            user_id = await session.scalar(select(User.id).where(User.email == email))
            if user_id is None:
                print(f"[seed] failed: {email} could not be created", file=sys.stderr)
                return

        # Pre-fill the profile so the onboarding gate doesn't block the very
        # account that exists to exercise the download path.
        await session.execute(
            insert(UserProfile)
            .values(
                user_id=user_id,
                first_name="Dev",
                last_name=role.capitalize(),
                address="N/A",
                state="N/A",
                zip="00000",
                phone="N/A",
            )
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        await session.commit()

    print(f"[seed] dev {role} ready: {email}", file=sys.stderr)


async def seed_dev_client(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """A known client login, so downloads can be tried without signing up."""
    if settings.env != "development":
        return
    await _seed_user(sessionmaker, DEV_CLIENT_EMAIL, DEV_CLIENT_PASSWORD, "client")


# The default public copy. Mirrors frontend/src/lib/site.ts, which stays in place
# as the fallback for a site whose artist hasn't saved a profile yet.
_DEV_PROFILE = {
    "display_name": "Ethan Tran",
    "tagline": "Artist",
    "statement": (
        "Most of these were made without asking anyone to hold still. "
        "Nothing here is arranged."
    ),
    "bio": "Placeholder. Say who you are, what you make, and who you make it for.",
    "location": "Austin, TX",
    "contact_email": "you@example.com",
}


async def seed_dev_artist(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """A known artist login, plus the profile the public pages render."""
    if settings.env != "development":
        return

    await _seed_user(sessionmaker, DEV_ARTIST_EMAIL, DEV_ARTIST_PASSWORD, "artist")

    async with sessionmaker() as session:
        user_id = await session.scalar(
            select(User.id).where(User.email == DEV_ARTIST_EMAIL)
        )
        if user_id is None:
            return
        existing = await session.scalar(
            select(ArtistProfile.id).where(ArtistProfile.user_id == user_id)
        )
        if existing is not None:
            # Never overwrite copy someone has edited.
            return
        session.add(
            ArtistProfile(
                user_id=user_id,
                slug="ethan-tran",
                is_primary=True,
                **_DEV_PROFILE,
            )
        )
        await session.commit()

    print("[seed] dev artist profile ready", file=sys.stderr)


# Ted Nguy, the second artist. Every field here is invented placeholder copy -
# the email especially, which belongs to whoever is really going to use this
# account.
_DEV_ARTIST2_PROFILE = {
    "display_name": "Ted Nguy",
    "tagline": "Bird & Landscape Photographer",
    "statement": "I spend most mornings waiting for birds to turn up.",
    "bio": (
        "I photograph birds and the places they live. Most of it happens early, "
        "and most of it is quiet."
    ),
    "location": "Sacramento, CA",
    "contact_email": "ted@example.com",
    "instagram": "@tednguy",
}


async def seed_dev_artist_two(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Ted Nguy: a real second artist, with his own page and subscribers."""
    if settings.env != "development":
        return

    await _seed_user(sessionmaker, DEV_ARTIST2_EMAIL, DEV_ARTIST2_PASSWORD, "artist")

    async with sessionmaker() as session:
        user_id = await session.scalar(
            select(User.id).where(User.email == DEV_ARTIST2_EMAIL)
        )
        if user_id is None:
            return
        existing = await session.scalar(
            select(ArtistProfile.id).where(ArtistProfile.user_id == user_id)
        )
        if existing is not None:
            return
        # Not primary: the front page stays the first artist's, and Ted gets
        # his own page at /artist/ted-nguy.
        session.add(
            ArtistProfile(user_id=user_id, slug="ted-nguy", **_DEV_ARTIST2_PROFILE)
        )
        await session.commit()

    print("[seed] dev artist 2 (Ted Nguy) ready", file=sys.stderr)


# Placeholder stand-ins for the first artist: real photos replace these files and
# rows, but the shape - ordered photos in an album of some tier - is the one the
# site serves. Ted has no placeholders: his album comes from an import (see
# `python -m app.cli import-album`), so the seed must not claim a slug his real
# work uses - that's how six gradient tiles ended up in his album once.
_DEV_FREE_ALBUM = "ethan-uncurated"
_DEV_PAID_ALBUM = "night-work"
_DEV_PREMIUM_ALBUM = "long-exposure"

# (title, width, height, top tone, bottom tone). Alternating orientations so the
# grid reads like a real album rather than a wall of identical tiles.
_FREE_PHOTOS = (
    ("Untitled 01", 1600, 1067, 18, 96),
    ("Untitled 02", 1067, 1600, 132, 44),
    ("Untitled 03", 1400, 1400, 58, 148),
    ("Untitled 04", 1600, 900, 203, 82),
    ("Untitled 05", 900, 1600, 30, 152),
    ("Untitled 06", 1600, 1067, 88, 232),
    ("Untitled 07", 1200, 1600, 44, 118),
    ("Untitled 08", 1600, 1067, 150, 46),
    ("Untitled 09", 1067, 1600, 96, 190),
    ("Untitled 10", 1600, 1000, 22, 70),
    ("Untitled 11", 1400, 1050, 176, 108),
    ("Untitled 12", 1600, 1067, 60, 205),
)

_PAID_PHOTOS = (
    ("Frames 01", 1600, 1067, 12, 60),
    ("Frames 02", 1067, 1600, 70, 20),
    ("Frames 03", 1600, 900, 150, 40),
    ("Frames 04", 1200, 1500, 30, 110),
    ("Frames 05", 1600, 1067, 190, 90),
    ("Frames 06", 1067, 1600, 40, 170),
)

_PREMIUM_PHOTOS = (
    ("Plate 01", 1600, 1067, 6, 40),
    ("Plate 02", 1067, 1600, 48, 8),
    ("Plate 03", 1600, 1067, 120, 200),
    ("Plate 04", 1400, 1050, 90, 20),
)


async def _top_up_album(
    session: AsyncSession,
    *,
    slug: str,
    title: str,
    credit: str | None,
    description: str | None,
    access: str,
    artist_id: int,
    photos: tuple,
) -> int:
    """Create the album if needed, then add any placeholder it's missing.

    Tops up rather than all-or-nothing, so editing the lists above and
    restarting is enough to see the change. Deleting a placeholder row in a
    running dev database therefore only lasts until the next restart -
    acceptable while these rows are disposable.
    """
    album = (
        await session.execute(select(Album).where(Album.slug == slug))
    ).scalar_one_or_none()
    if album is None:
        album = Album(
            slug=slug,
            title=title,
            credit=credit,
            description=description,
            access=access,
            artist_id=artist_id,
            is_published=True,
        )
        session.add(album)
        await session.flush()
    else:
        # Keep ownership and the bucket in step if the definition changed.
        album.access = access
        album.artist_id = artist_id

    existing = set(
        (
            await session.execute(
                select(Photo.filename).where(Photo.album_id == album.id)
            )
        )
        .scalars()
        .all()
    )

    # Same layout as an imported or uploaded photo, so the media tree has one
    # scheme rather than placeholders living somewhere else.
    key = await artist_media_key(session, artist_id)

    added = 0
    for index, (photo_title, width, height, top, bottom) in enumerate(photos, start=1):
        stem = f"{index:02d}"
        filename = storage.photo_paths(
            artist_key=key, album_slug=slug, stem=stem, suffix=".png"
        ).original
        if filename in existing:
            continue
        storage.write_bytes(filename, gradient_png(width, height, top, bottom))
        session.add(
            Photo(
                album_id=album.id,
                filename=filename,
                title=photo_title,
                position=index,
                width=width,
                height=height,
            )
        )
        added += 1
    return added


async def seed_dev_gallery(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """One album per tier, so every rung of the ladder is exercisable.

    No descriptions: they were scaffolding explaining each tier ("A paid album.
    Any subscriber can download these."), which is the client area's job - it
    shows the tier and the subscribe prompt. On the public pages the strip names
    the artist and stops.
    """
    if settings.env != "development":
        return

    async with sessionmaker() as session:
        artist_id = await session.scalar(
            select(User.id).where(User.email == DEV_ARTIST_EMAIL)
        )
        if artist_id is None:
            print("[seed] gallery skipped: no dev artist", file=sys.stderr)
            return

        free = await _top_up_album(
            session,
            slug=_DEV_FREE_ALBUM,
            title="Ethan, Uncurated",
            credit="Ethan Tran",
            description=None,
            access=TIER_FREE,
            artist_id=artist_id,
            photos=_FREE_PHOTOS,
        )
        paid = await _top_up_album(
            session,
            slug=_DEV_PAID_ALBUM,
            title="Night Work",
            credit=None,
            description=None,
            access=TIER_PAID,
            artist_id=artist_id,
            photos=_PAID_PHOTOS,
        )
        premium = await _top_up_album(
            session,
            slug=_DEV_PREMIUM_ALBUM,
            title="Long Exposure",
            credit=None,
            description=None,
            access=TIER_PREMIUM,
            artist_id=artist_id,
            photos=_PREMIUM_PHOTOS,
        )
        await session.commit()

    if free or paid or premium:
        print(
            f"[seed] dev gallery: +{free} free, +{paid} paid, "
            f"+{premium} premium placeholder(s)",
            file=sys.stderr,
        )


# Albums that live in the media tree rather than in the seeds above. A tier can't
# be read off a filename - the database is the only place a bucket lives - so the
# demo's tiers are declared here. Public, because `app.cli restore-media
# --dev-tiers` uses the same map rather than repeating it.
DEV_MEDIA_ALBUM_TIERS = {
    "wetlands": TIER_PAID,
    "field-notes": TIER_FREE,
    "studio-selects": TIER_PREMIUM,
}


async def seed_dev_restore_media(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Rebuild rows for photos that are on disk but not in the database.

    A reset drops every row and leaves every file, and anything imported or
    uploaded isn't in the seeds - so without this a reset silently empties an
    artist's page until somebody notices and re-imports. The media tree describes
    itself well enough to rebuild from; this is the automatic form of
    ``app.cli restore-media``.

    Only in development, and only additive: a photo already in its album is left
    alone. If the files aren't there, this does nothing.
    """
    if settings.env != "development":
        return

    async with sessionmaker() as session:
        report = await restore_from_media(
            session, tiers=DEV_MEDIA_ALBUM_TIERS, apply=True
        )

    if report.photos_added or report.albums_created:
        print(
            f"[seed] restored {report.photos_added} photo(s) and "
            f"{report.albums_created} album(s) from the media tree",
            file=sys.stderr,
        )


async def seed_dev_subscribers(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Subscribe the demo customers, so every rung of the ladder is reachable.

    Two customers, deliberately different:

    - ``client@mail.com`` subscribes at ``paid``, so the *premium* album stays
      locked and the ladder is visible on first boot.
    - ``premium@mail.com`` subscribes at ``premium``, so there is a login that
      can open everything.

    Both subscribe to both artists, and per artist, so this doubles as the demo
    of levels being per artist rather than global.
    """
    if settings.env != "development":
        return

    await _seed_user(sessionmaker, DEV_PREMIUM_EMAIL, DEV_PREMIUM_PASSWORD, "client")

    subscriptions = (
        (DEV_CLIENT_EMAIL, DEV_ARTIST_EMAIL, TIER_PAID),
        (DEV_CLIENT_EMAIL, DEV_ARTIST2_EMAIL, TIER_PAID),
        (DEV_PREMIUM_EMAIL, DEV_ARTIST_EMAIL, TIER_PREMIUM),
        (DEV_PREMIUM_EMAIL, DEV_ARTIST2_EMAIL, TIER_PREMIUM),
    )

    added = 0
    async with sessionmaker() as session:
        for subscriber_email, artist_email, level in subscriptions:
            subscriber_id = await session.scalar(
                select(User.id).where(User.email == subscriber_email)
            )
            artist_id = await session.scalar(
                select(User.id).where(User.email == artist_email)
            )
            if subscriber_id is None or artist_id is None:
                continue
            existing = await session.scalar(
                select(Subscription.id).where(
                    Subscription.subscriber_id == subscriber_id,
                    Subscription.artist_id == artist_id,
                )
            )
            if existing is not None:
                continue
            session.add(
                Subscription(
                    subscriber_id=subscriber_id,
                    artist_id=artist_id,
                    level=level,
                    note="dev seed",
                )
            )
            added += 1
        await session.commit()

    if added:
        print(f"[seed] dev subscriptions ready (+{added})", file=sys.stderr)
