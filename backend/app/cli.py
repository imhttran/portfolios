"""Out-of-band tooling: the ``set-role`` and ``import-album`` subcommands.

Roles are granted CLI-only, so there's no HTTP endpoint and no self-service
escalation.

``set-role`` deliberately does NOT load .env files - it reads DATABASE_URL
directly, matching the Rust backend's set-role, so it works as a bootstrap tool
when the app's config isn't in place yet. ``import-album`` is the opposite: it
honours the app's own config (including MEDIA_ROOT), because it has to write
where the app will read from.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DEFAULT_DATABASE_URL
from app.db.session import build_engine
from app.models import User
from app.services import storage
from app.services.roles import ROLES, role_index


def _usage() -> str:
    return (
        f"Usage: set-role <email> <{'|'.join(ROLES)}>\n"
        "       import-album --artist <email> --dir <folder> --slug <slug> "
        "--title <title> [--access free|paid|premium]\n"
        "       prune-media [--yes]\n"
        "       prune-db [--yes] [--keep-days N]\n"
        "       restore-media [--tier album=level] [--dev-tiers] [--yes]\n"
        "       relayout-media [--yes]"
    )


async def _run(email: str, role: str) -> int:
    dsn = os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
    engine = build_engine(dsn)
    try:
        async with AsyncSession(engine) as session:
            exists = await session.scalar(select(User.id).where(User.email == email))
            if exists is None:
                print(f"No user found with email {email}")
                return 1
            await session.execute(
                update(User).where(User.email == email).values(role=role)
            )
            await session.commit()
    except Exception as err:  # noqa: BLE001 - surface any DB failure like the CLI does
        print(f"Failed to set role: {err}")
        return 1
    finally:
        await engine.dispose()

    print(f"{email} is now {role}")
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


async def _import_album(argv: list[str]) -> int:
    """`import-album`: load a folder of photos into an artist's album."""
    # The app's own config, because MEDIA_ROOT decides where files must land.
    from app.db.session import get_sessionmaker
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

    engine = build_engine(os.environ["DATABASE_URL"])
    try:
        async with get_sessionmaker()() as session:
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
    finally:
        await engine.dispose()

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
    from app.db.session import get_sessionmaker
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

    engine = build_engine(os.environ["DATABASE_URL"])
    try:
        async with get_sessionmaker()() as session:
            rows = (
                await session.execute(
                    select(
                        Photo.filename,
                        Photo.preview_filename,
                        Photo.thumb_filename,
                    )
                )
            ).all()
    finally:
        await engine.dispose()

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
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()

    print(f"deleted {len(orphans)} file(s), {freed / 1e6:.0f} MB freed")
    return 0


async def _prune_db(argv: list[str]) -> int:
    """`prune-db`: remove rows that are dead by definition, and check the rest.

    See services/maintenance.py for what counts as dead and why recent mail is
    kept.
    """
    from app.db.session import get_sessionmaker
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

    engine = build_engine(os.environ["DATABASE_URL"])
    try:
        async with get_sessionmaker()() as session:
            report = await prune_db(
                session,
                keep_days=parsed.keep_days,
                delete_rows=parsed.yes,
            )
    finally:
        await engine.dispose()

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
    from app.db.session import get_sessionmaker
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

    engine = build_engine(os.environ["DATABASE_URL"])
    try:
        async with get_sessionmaker()() as session:
            report = await restore_from_media(
                session,
                tiers=tiers,
                default_tier=parsed.default_tier,
                published=not parsed.hidden,
                apply=parsed.yes,
            )
    finally:
        await engine.dispose()

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
    from app.db.session import get_sessionmaker
    from app.services.relayout import relayout_media

    parser = argparse.ArgumentParser(prog="relayout-media", add_help=True)
    parser.add_argument(
        "--yes", action="store_true", help="apply (otherwise just report)"
    )
    parsed = parser.parse_args(argv)

    await _prepare_db()

    engine = build_engine(os.environ["DATABASE_URL"])
    try:
        async with get_sessionmaker()() as session:
            report = await relayout_media(session, apply=parsed.yes)
    finally:
        await engine.dispose()

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

    if args and args[0] == "import-album":
        return asyncio.run(_import_album(args[1:]))

    if args and args[0] == "prune-media":
        return asyncio.run(_prune_media(args[1:]))

    if args and args[0] == "prune-db":
        return asyncio.run(_prune_db(args[1:]))

    if args and args[0] == "restore-media":
        return asyncio.run(_restore_media(args[1:]))

    if args and args[0] == "relayout-media":
        return asyncio.run(_relayout_media(args[1:]))

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

    return asyncio.run(_run(parsed.email, parsed.role))


if __name__ == "__main__":
    raise SystemExit(main())
