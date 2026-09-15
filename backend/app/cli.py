"""Out-of-band tooling: the ``set-role`` and ``import-album`` subcommands.

Roles and subscriptions are granted CLI-only, so there's no HTTP endpoint and
no self-service escalation.

``set-role`` and ``set-subscription`` deliberately do NOT load .env files - they
read DATABASE_URL directly, matching the Rust backend's set-role, so they work
as bootstrap tools when the app's config isn't in place yet. The rest is the
opposite: they honour the app's own config (including MEDIA_ROOT), because they
have to write where the app will read from.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import delete, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEFAULT_DATABASE_URL
from app.db.session import build_engine
from app.models import Subscription, User
from app.services import storage
from app.services.roles import ROLES, role_index

# Who may be the artist side of a subscription: an artist's own account, or an
# admin acting for one. Unchanged from what the HTTP endpoint accepted before
# granting moved to the CLI.
ARTIST_ROLES = ("artist", "admin")


def _usage() -> str:
    return (
        f"Usage: set-role <email> <{'|'.join(ROLES)}>\n"
        "       set-subscription <subscriber-email> <artist-email> "
        "[--level paid|premium]\n"
        "       revoke-subscription <subscriber-email> <artist-email>\n"
        "       import-album --artist <email> --dir <folder> --slug <slug> "
        "--title <title> [--access free|paid|premium]\n"
        "       prune-media [--yes]\n"
        "       prune-db [--yes] [--keep-days N]\n"
        "       restore-media [--tier album=level] [--dev-tiers] [--yes]\n"
        "       relayout-media [--yes]"
    )


@asynccontextmanager
async def _direct_session() -> AsyncIterator[AsyncSession]:
    """A session from DATABASE_URL alone, without loading the app's env files.

    The role and subscription commands are bootstrap tools: they have to work
    when the app's config isn't in place yet, so they read the DSN the caller
    exported (``manage.sh`` does) and nothing else.
    """
    engine = build_engine(os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL)
    try:
        async with AsyncSession(engine) as session:
            yield session
    finally:
        await engine.dispose()


async def _user_by_email(session: AsyncSession, email: str):
    """(id, email, role) for an address, or None if nobody has it."""
    return (
        await session.execute(
            select(User.id, User.email, User.role).where(User.email == email)
        )
    ).first()


async def _set_role(email: str, role: str) -> int:
    try:
        async with _direct_session() as session:
            user = await _user_by_email(session, email)
            if user is None:
                print(f"No user found with email {email}")
                return 1
            await session.execute(
                update(User).where(User.id == user.id).values(role=role)
            )
            await session.commit()
    except Exception as err:  # noqa: BLE001 - surface any DB failure like the CLI does
        print(f"Failed to set role: {err}")
        return 1

    print(f"{email} is now {role}")
    return 0


async def _set_subscription(argv: list[str]) -> int:
    """`set-subscription`: open an artist's paid work to one customer.

    An admin action with no endpoint, the same way roles are: no payment
    provider writes these rows yet, so a human grants them deliberately. The
    level names the highest tier it opens, so ``premium`` also opens ``paid``.
    """
    from app.models.tiers import SUBSCRIPTION_LEVELS, TIER_PAID

    parser = argparse.ArgumentParser(prog="set-subscription", add_help=True)
    parser.add_argument("subscriber", help="the customer's email")
    parser.add_argument("artist", help="the artist's email")
    parser.add_argument("--level", default=TIER_PAID, choices=SUBSCRIPTION_LEVELS)
    parsed = parser.parse_args(argv)

    try:
        async with _direct_session() as session:
            subscriber = await _user_by_email(session, parsed.subscriber)
            if subscriber is None:
                print(f"No user found with email {parsed.subscriber}")
                return 1
            artist = await _user_by_email(session, parsed.artist)
            if artist is None:
                print(f"No user found with email {parsed.artist}")
                return 1
            if artist.role not in ARTIST_ROLES:
                print(f"{artist.email} is not an artist")
                return 1

            existing = await session.scalar(
                select(Subscription).where(
                    Subscription.subscriber_id == subscriber.id,
                    Subscription.artist_id == artist.id,
                )
            )
            # Re-running with another level changes it rather than failing: a
            # CLI has no "already subscribed" error worth returning.
            if existing is None:
                session.add(
                    Subscription(
                        subscriber_id=subscriber.id,
                        artist_id=artist.id,
                        level=parsed.level,
                        note="granted via cli",
                    )
                )
            else:
                existing.level = parsed.level
            await session.commit()
    except Exception as err:  # noqa: BLE001 - surface any DB failure like the CLI does
        print(f"Failed to set subscription: {err}")
        return 1

    print(f"{parsed.subscriber} can now download {parsed.artist}'s {parsed.level} work")
    return 0


async def _revoke_subscription(argv: list[str]) -> int:
    """`revoke-subscription`: close an artist's paid work to one customer."""
    parser = argparse.ArgumentParser(prog="revoke-subscription", add_help=True)
    parser.add_argument("subscriber", help="the customer's email")
    parser.add_argument("artist", help="the artist's email")
    parsed = parser.parse_args(argv)

    try:
        async with _direct_session() as session:
            subscriber = await _user_by_email(session, parsed.subscriber)
            artist = await _user_by_email(session, parsed.artist)
            if subscriber is None or artist is None:
                print("No subscription between those two addresses")
                return 1
            result = await session.execute(
                delete(Subscription).where(
                    Subscription.subscriber_id == subscriber.id,
                    Subscription.artist_id == artist.id,
                )
            )
            await session.commit()
    except Exception as err:  # noqa: BLE001 - surface any DB failure like the CLI does
        print(f"Failed to revoke subscription: {err}")
        return 1

    if result.rowcount == 0:
        print(f"{parsed.subscriber} does not subscribe to {parsed.artist}")
        return 1
    print(f"{parsed.subscriber} can no longer download {parsed.artist}'s paid work")
    return 0


async def _prepare_db() -> bool:
    """Load the app's env, then make sure the schema exists.

    Only the backend creates tables (on boot), but the CLI is often what runs
    first after a schema reset - ``restore-media``, to bring back the work a
    reset erased - where every command used to die on ``relation "users" does
    not exist``.

    Returns True when the schema had to be created, i.e. the database was
    empty. Callers that act on what's *missing* need to know: with no rows at
    all, every file on disk looks like an orphan. ``create_all`` is idempotent
    and only ever creates, so an existing schema passes through untouched.
    """
    from app.config import get_settings, load_env_files
    from app.db.session import create_all, get_engine

    load_env_files()
    os.environ.setdefault("DATABASE_URL", get_settings().database_url)

    async with get_engine().connect() as conn:
        existed = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table("users")
        )
    await create_all()
    return not existed


@asynccontextmanager
async def _session() -> AsyncIterator[AsyncSession]:
    """A session on the app's own config, closed on the way out.

    The same engine the server uses, so a command writes where the app reads,
    and disposing it here leaves nothing open when the process exits.
    """
    from app.db.session import dispose_engine, get_sessionmaker

    try:
        async with get_sessionmaker()() as session:
            yield session
    finally:
        await dispose_engine()


async def _import_album(argv: list[str]) -> int:
    """`import-album`: load a folder of photos into an artist's album."""
    from app.models.tiers import TIERS
    from app.services.importer import import_folder

    parser = argparse.ArgumentParser(prog="import-album", add_help=True)
    parser.add_argument("--artist", required=True, help="the artist's email")
    parser.add_argument("--dir", required=True, help="folder of photos, read in place")
    parser.add_argument("--slug", required=True, help="album slug to create or top up")
    parser.add_argument("--title", default=None, help="album title (default: the slug)")
    parser.add_argument("--access", default="paid", choices=TIERS)
    parser.add_argument(
        "--unpublished",
        action="store_true",
        help="import without publishing the album",
    )
    parsed = parser.parse_args(argv)

    await _prepare_db()

    try:
        async with _session() as session:
            report = await import_folder(
                session,
                artist_email=parsed.artist,
                folder=Path(parsed.dir),
                slug=parsed.slug,
                title=parsed.title or parsed.slug,
                access=parsed.access,
                published=not parsed.unpublished,
            )
    except (ValueError, OSError) as err:
        print(f"Import failed: {err}")
        return 1

    print(f"Album '{report.album_slug}' for {report.artist_email}")
    print(f"  imported:        {report.imported}")
    print(f"  already present: {report.skipped_existing}")
    if report.rejected:
        print(f"  skipped ({len(report.rejected)}):")
        for name, reason in report.rejected[:10]:
            print(f"    {name} — {reason}")
        if len(report.rejected) > 10:
            print(f"    … and {len(report.rejected) - 10} more")
    return 0


async def _prune_media(argv: list[str]) -> int:
    """`prune-media`: delete files no photo row refers to.

    Files are written before the database row is committed, so a run that dies
    in between leaves originals and derived files behind with nothing pointing
    at them. Reports by default; ``--yes`` actually deletes.

    Refuses outright when the schema was just created: an empty database makes
    every file on disk look like an orphan.
    """
    from app.models import Photo
    from app.services.storage import media_root

    parser = argparse.ArgumentParser(prog="prune-media", add_help=True)
    parser.add_argument(
        "--yes", action="store_true", help="delete them (otherwise just report)"
    )
    parsed = parser.parse_args(argv)

    if await _prepare_db():
        print(
            "Database was empty - the schema was just created, so every file on "
            "disk would look like an orphan.\n"
            "Run restore-media first, then prune."
        )
        return 0

    engine_free = None  # rows are read and the session closed before any unlink
    async with _session() as session:
        rows = (
            await session.execute(
                select(
                    Photo.filename,
                    Photo.preview_filename,
                    Photo.thumb_filename,
                )
            )
        ).all()
    del engine_free

    referenced = {name for row in rows for name in row if name}

    root = media_root()
    on_disk = {
        str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
    }
    orphans = sorted(on_disk - referenced)
    missing = sorted(referenced - on_disk)

    print(f"files on disk:    {len(on_disk)}")
    print(f"files referenced: {len(referenced)}")
    print(f"orphans:          {len(orphans)}")
    if missing:
        print(f"rows with no file: {len(missing)}")
        for name in missing[:5]:
            print(f"  missing {name}")

    if not orphans:
        return 0
    if not parsed.yes:
        print("\nRe-run with --yes to delete them.")
        return 0

    freed = 0
    for name in orphans:
        try:
            path = storage.photo_path(name)
        except ValueError:
            continue
        freed += path.stat().st_size if path.exists() else 0
        path.unlink(missing_ok=True)

    # Tidy up the directories that are now empty.
    storage.prune_empty_dirs()

    print(f"deleted {len(orphans)} file(s), {freed / 1e6:.0f} MB freed")
    return 0


async def _prune_db(argv: list[str]) -> int:
    """`prune-db`: remove rows that are dead by definition, and check the rest.

    See services/maintenance.py for what counts as dead and why recent mail is
    kept.
    """
    from app.services.maintenance import DEFAULT_KEEP_DAYS, prune_db

    parser = argparse.ArgumentParser(prog="prune-db", add_help=True)
    parser.add_argument(
        "--yes", action="store_true", help="delete (otherwise just report)"
    )
    parser.add_argument(
        "--keep-days",
        type=int,
        default=DEFAULT_KEEP_DAYS,
        help=f"how long to keep delivered email (default {DEFAULT_KEEP_DAYS})",
    )
    parsed = parser.parse_args(argv)

    await _prepare_db()

    async with _session() as session:
        report = await prune_db(
            session,
            keep_days=parsed.keep_days,
            delete_rows=parsed.yes,
        )

    print(f"dead login codes:        {report.dead_login_codes}")
    print(f"devices whose trust lapsed: {report.expired_devices}")
    print(f"delivered email older than {parsed.keep_days}d: {report.old_emails}")
    print("orphan rows:")
    for label, count in report.orphans.items():
        print(f"  {label:34} {count}")
    if report.empty_albums:
        print(f"albums with no photos:   {', '.join(report.empty_albums)}")

    if not parsed.yes:
        print("\nRe-run with --yes to delete the dead rows.")
        return 0

    print(
        f"\ndeleted {report.deleted_codes} login code(s), "
        f"{report.deleted_devices} device(s) "
        f"and {report.deleted_emails} email(s)"
    )
    return 0


async def _restore_media(argv: list[str]) -> int:
    """`restore-media`: rebuild photo rows from the files on disk.

    For work that didn't come from the seeds - an imported folder, a browser
    upload - which a database reset erases while leaving every file in place.
    """
    from app.models.tiers import TIERS
    from app.services.restore import restore_from_media

    parser = argparse.ArgumentParser(prog="restore-media", add_help=True)
    parser.add_argument(
        "--tier",
        action="append",
        default=[],
        metavar="ALBUM=LEVEL",
        help=(
            "tier for a rebuilt album, e.g. wetlands=paid. Repeatable; albums "
            "not named here get --default-tier. Filenames can't record the "
            "tier, because it lives in the database by design."
        ),
    )
    parser.add_argument("--default-tier", default="free", choices=TIERS)
    parser.add_argument(
        "--dev-tiers",
        action="store_true",
        help=(
            "use the demo albums' declared tiers, so the work that arrived by "
            "importing rather than by seeding comes back in the right buckets"
        ),
    )
    parser.add_argument(
        "--hidden",
        action="store_true",
        help="rebuild albums unpublished instead of published",
    )
    parser.add_argument(
        "--yes", action="store_true", help="apply (otherwise just report)"
    )
    parsed = parser.parse_args(argv)

    tiers: dict[str, str] = {}
    if parsed.dev_tiers:
        from app.services.seeds import DEV_MEDIA_ALBUM_TIERS

        tiers.update(DEV_MEDIA_ALBUM_TIERS)
    for pair in parsed.tier:
        slug, _, level = pair.partition("=")
        if level not in TIERS:
            print(f"Bad --tier {pair!r}; level must be one of: {', '.join(TIERS)}")
            return 1
        # An explicit --tier wins over the demo map.
        tiers[slug] = level

    await _prepare_db()

    async with _session() as session:
        report = await restore_from_media(
            session,
            tiers=tiers,
            default_tier=parsed.default_tier,
            published=not parsed.hidden,
            apply=parsed.yes,
        )

    print(f"albums to create:   {report.albums_created}")
    print(f"photos to restore:  {report.photos_added}")
    print(f"already present:    {report.already_present}")
    if report.skipped:
        print(f"skipped ({len(report.skipped)}):")
        for name in report.skipped[:10]:
            print(f"    {name}")
        if len(report.skipped) > 10:
            print(f"    … and {len(report.skipped) - 10} more")

    if not parsed.yes:
        print("\nRe-run with --yes to rebuild those rows.")
        return 0

    print("\nrows rebuilt")
    return 0


async def _relayout_media(argv: list[str]) -> int:
    """`relayout-media`: move files and rows into the current media layout.

    Only needed once per database - every writer already uses the current layout.
    Re-running it is a no-op.
    """
    from app.services.relayout import relayout_media

    parser = argparse.ArgumentParser(prog="relayout-media", add_help=True)
    parser.add_argument(
        "--yes", action="store_true", help="apply (otherwise just report)"
    )
    parsed = parser.parse_args(argv)

    await _prepare_db()

    async with _session() as session:
        report = await relayout_media(session, apply=parsed.yes)

    print(f"photos:              {report.rows_seen}")
    print(f"already in place:    {report.already_current}")
    print(
        f"to move:             {report.rows_to_move} rows, {report.files_to_move} files"
    )
    if report.missing:
        print(f"row says a file that isn't there ({len(report.missing)}):")
        for name in report.missing[:10]:
            print(f"    {name}")

    if not report.rows_to_move:
        return 0
    if not parsed.yes:
        print("\nRe-run with --yes to move them.")
        return 0

    print("\nmoved")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    # Each subcommand dispatches on its own name and parses the rest itself.
    subcommands = {
        "import-album": _import_album,
        "prune-media": _prune_media,
        "prune-db": _prune_db,
        "restore-media": _restore_media,
        "relayout-media": _relayout_media,
        "set-subscription": _set_subscription,
        "revoke-subscription": _revoke_subscription,
    }
    if args and args[0] in subcommands:
        return asyncio.run(subcommands[args[0]](args[1:]))

    # Tolerate being invoked as `python -m app.cli set-role <email> <role>`.
    if args and args[0] == "set-role":
        args = args[1:]

    parser = argparse.ArgumentParser(prog="set-role", add_help=True)
    parser.add_argument("email", nargs="?")
    parser.add_argument("role", nargs="?")
    parsed = parser.parse_args(args)

    if parsed.email is None or parsed.role is None or role_index(parsed.role) is None:
        print(_usage())
        return 1

    return asyncio.run(_set_role(parsed.email, parsed.role))


if __name__ == "__main__":
    raise SystemExit(main())
