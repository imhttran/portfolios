"""Database-backed tests for /api/manage - an artist's own album and photo work.

This is the surface where the client's input reaches the filesystem, so the
tests are as interested in what gets *refused* as in what gets stored.
"""

from __future__ import annotations

import io
import uuid

from PIL import Image
from sqlalchemy import func, select

from app.db.session import get_sessionmaker
from app.models import Album, Photo
from app.services import storage
from tests.helpers import (
    cleanup,
    do_json,
    fill_profile,
    login,
    requires_db,
    set_role,
    signup,
    unique_email,
)

pytestmark = requires_db


def _jpeg(width: int = 120, height: int = 80) -> bytes:
    image = Image.new("RGB", (width, height), (90, 120, 150))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


async def _artist(client, name: str = "Managing Artist") -> tuple[str, str]:
    email = unique_email("artist")
    await signup(client, email)
    token = await login(client, email)
    await fill_profile(client, token)
    await set_role(email, "artist")
    await do_json(
        client,
        "PUT",
        "/api/artist/profile",
        token=token,
        json={
            "displayName": name,
            "tagline": "Photographer",
            "statement": "s",
            "bio": "b",
            "location": "Austin, TX",
            "contactEmail": "a@example.com",
        },
    )
    return email, token


async def _client_token(client) -> tuple[str, str]:
    email = unique_email("client")
    await signup(client, email)
    token = await login(client, email)
    await fill_profile(client, token)
    return email, token


async def _create_album(
    client, token: str, *, access: str = "paid", published: bool = True
) -> str:
    """A published album by default: unpublished ones aren't publicly readable,
    which is the point of the flag, so most tests want it on."""
    response, body = await do_json(
        client,
        "POST",
        "/api/manage/albums",
        token=token,
        json={
            "title": f"Album {uuid.uuid4().hex[:6]}",
            "access": access,
            "isPublished": published,
        },
    )
    assert response.status_code == 201, body
    return body["album"]["slug"]


async def test_a_client_cannot_manage_albums(client):
    email, token = await _client_token(client)
    try:
        response, body = await do_json(client, "GET", "/api/manage/albums", token=token)
        assert response.status_code == 403
        assert body["message"] == "Insufficient permissions"

        response, body = await do_json(
            client,
            "POST",
            "/api/manage/albums",
            token=token,
            json={"title": "Not mine", "access": "free"},
        )
        assert response.status_code == 403
    finally:
        await cleanup(email)


async def test_an_artist_creates_albums_in_a_bucket(client):
    email, token = await _artist(client)
    try:
        response, body = await do_json(
            client,
            "POST",
            "/api/manage/albums",
            token=token,
            json={"title": "Autumn Marsh", "access": "premium"},
        )
        assert response.status_code == 201, body
        assert body["album"]["slug"] == "autumn-marsh"
        assert body["album"]["access"] == "premium"
        assert body["album"]["isPublished"] is False
        assert body["album"]["photoCount"] == 0

        # A title is required, and the tier has to be one we know.
        response, body = await do_json(
            client, "POST", "/api/manage/albums", token=token, json={"title": "  "}
        )
        assert response.status_code == 400
        assert body["message"] == "A title is required"

        response, body = await do_json(
            client,
            "POST",
            "/api/manage/albums",
            token=token,
            json={"title": "Bad tier", "access": "gold"},
        )
        assert response.status_code == 400
        assert body["message"] == "access must be one of: free, paid, premium"
    finally:
        await cleanup(email)


async def test_uploading_adds_the_good_files_and_reports_the_rest(client):
    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")

        response = await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=[
                ("files", ("heron.jpg", _jpeg(400, 300), "image/jpeg")),
                ("files", ("egret.jpg", _jpeg(300, 400), "image/jpeg")),
                ("files", ("notes.pdf", b"%PDF-1.4 not an image", "application/pdf")),
            ],
        )
        body = response.json()
        assert response.status_code == 201, body
        assert body["added"] == 2
        assert [r["name"] for r in body["rejected"]] == ["notes.pdf"]
        assert body["album"]["photoCount"] == 2

        # The row records the true dimensions, and the files are where the
        # layout says they should be.
        listing = (await client.get(f"/api/media/albums/{slug}")).json()
        photos = listing["photos"]
        assert len(photos) == 2
        assert {(p["width"], p["height"]) for p in photos} == {(400, 300), (300, 400)}

        for photo in photos:
            assert (await client.get(photo["previewUrl"])).status_code == 200
    finally:
        await cleanup(email)


async def test_a_file_named_like_an_image_but_that_is_not_one_is_refused(client):
    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")
        response = await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=[("files", ("fake.jpg", b"<html>not a photo</html>", "image/jpeg"))],
        )
        assert response.status_code == 400
        body = response.json()
        assert body["added"] == 0
        assert body["rejected"][0]["name"] == "fake.jpg"
    finally:
        await cleanup(email)


async def test_a_traversing_filename_cannot_escape_the_album_folder(client):
    """The client controls the name, so it must never reach the path."""
    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")
        response = await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=[
                ("files", ("../../evil.jpg", _jpeg(), "image/jpeg")),
                ("files", ("/etc/passwd.png", _jpeg(), "image/png")),
            ],
        )
        assert response.status_code == 201, response.json()

        listing = (await client.get(f"/api/media/albums/{slug}")).json()
        # The stored title is the basename, with the traversal stripped off.
        assert {p["title"] for p in listing["photos"]} == {"evil", "passwd"}

        async with get_sessionmaker()() as session:
            names = (
                (
                    await session.execute(
                        select(Photo.filename).where(Photo.filename.like(f"%/{slug}/%"))
                    )
                )
                .scalars()
                .all()
            )

        assert names
        for name in names:
            assert ".." not in name
            # Raises ValueError if a stored name would escape the root.
            assert storage.photo_path(name).is_relative_to(storage.media_root())
    finally:
        await cleanup(email)


async def test_an_artist_cannot_touch_another_artists_album(client):
    first_email, first_token = await _artist(client, "First")
    second_email, second_token = await _artist(client, "Second")
    try:
        slug = await _create_album(client, first_token, access="paid")

        response = await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {second_token}"},
            files=[("files", ("mine.jpg", _jpeg(), "image/jpeg"))],
        )
        assert response.status_code == 403
        assert response.json()["message"] == "That belongs to another artist"

        response, body = await do_json(
            client,
            "PATCH",
            f"/api/manage/albums/{slug}",
            token=second_token,
            json={"access": "free"},
        )
        assert response.status_code == 403
    finally:
        await cleanup(first_email)
        await cleanup(second_email)


async def test_moving_an_album_between_buckets_changes_who_can_download(client):
    """The tier is a column, so this is the whole operation - no file moves."""
    email, token = await _artist(client)
    client_email, client_token = await _client_token(client)
    try:
        slug = await _create_album(client, token, access="free")
        await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=[("files", ("one.jpg", _jpeg(), "image/jpeg"))],
        )
        await do_json(
            client,
            "PATCH",
            f"/api/manage/albums/{slug}",
            token=token,
            json={"isPublished": True},
        )

        photo_id = (await client.get(f"/api/media/albums/{slug}")).json()["photos"][0][
            "id"
        ]
        headers = {"Authorization": f"Bearer {client_token}"}

        # Free: any registered user.
        assert (
            await client.get(f"/api/media/photos/{photo_id}/download", headers=headers)
        ).status_code == 200

        # Paid: the same user is no longer entitled.
        response, body = await do_json(
            client,
            "PATCH",
            f"/api/manage/albums/{slug}",
            token=token,
            json={"access": "paid"},
        )
        assert response.status_code == 200, body
        assert body["album"]["access"] == "paid"
        assert (
            await client.get(f"/api/media/photos/{photo_id}/download", headers=headers)
        ).status_code == 403
    finally:
        await cleanup(email)
        await cleanup(client_email)


async def test_deleting_a_photo_removes_its_files(client):
    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")
        await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=[("files", ("doomed.jpg", _jpeg(), "image/jpeg"))],
        )
        async with get_sessionmaker()() as session:
            photo = (
                await session.execute(
                    select(Photo).where(Photo.filename.like(f"%/{slug}/%"))
                )
            ).scalar_one()
            stored = (photo.id, photo.filename, photo.preview_filename)

        assert storage.photo_path(stored[1]).is_file()
        response, body = await do_json(
            client, "DELETE", f"/api/manage/photos/{stored[0]}", token=token
        )
        assert response.status_code == 200, body

        assert not storage.photo_path(stored[1]).exists()
        assert not storage.photo_path(stored[2]).exists()
    finally:
        await cleanup(email)


async def test_an_album_can_be_deleted_with_its_files(client):
    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")
        await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=[
                ("files", ("a.jpg", _jpeg(), "image/jpeg")),
                ("files", ("b.jpg", _jpeg(), "image/jpeg")),
            ],
        )

        async with get_sessionmaker()() as session:
            stored = (
                await session.execute(
                    select(Photo.filename, Photo.preview_filename).where(
                        Photo.filename.like(f"%/{slug}/%")
                    )
                )
            ).all()
        assert len(stored) == 2
        for original, _preview in stored:
            assert storage.photo_path(original).is_file()

        response, body = await do_json(
            client, "DELETE", f"/api/manage/albums/{slug}", token=token
        )
        assert response.status_code == 200, body
        assert "Deleted" in body["message"]

        # Rows and files both gone, and the album with them.
        async with get_sessionmaker()() as session:
            left = await session.scalar(
                select(func.count(Photo.id)).where(Photo.filename.like(f"%/{slug}/%"))
            )
            album_left = await session.scalar(
                select(func.count(Album.id)).where(Album.slug == slug)
            )
        assert left == 0
        assert album_left == 0
        for original, preview in stored:
            assert not storage.photo_path(original).exists()
            assert not storage.photo_path(preview).exists()
    finally:
        await cleanup(email)


async def test_an_artist_cannot_delete_another_artists_album(client):
    first_email, first_token = await _artist(client, "Owner")
    second_email, second_token = await _artist(client, "Other")
    try:
        slug = await _create_album(client, first_token, access="free")
        response, body = await do_json(
            client, "DELETE", f"/api/manage/albums/{slug}", token=second_token
        )
        assert response.status_code == 403

        # And it's still there.
        assert (await client.get(f"/api/media/albums/{slug}")).status_code == 200
    finally:
        await cleanup(first_email)
        await cleanup(second_email)


async def test_an_unsanitised_stored_name_still_blocks_a_duplicate(client):
    """Regression: the skip check must compare like with like.

    An earlier version of the importer stored file names verbatim, so a row can
    say ``_TED0113.jpg`` while a new upload sanitises to ``ted0113``. Comparing a
    sanitised incoming stem against an unsanitised stored one never matches, and
    a re-import silently duplicated every photo instead of skipping it.
    """
    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")
        async with get_sessionmaker()() as session:
            album_id = await session.scalar(select(Album.id).where(Album.slug == slug))
            session.add(
                Photo(
                    album_id=album_id,
                    filename=f"originals/artists/1/{slug}/_Ted0113.jpg",
                    title="legacy",
                    position=1,
                )
            )
            await session.commit()

        response = await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=[("files", ("ted0113.jpg", _jpeg(), "image/jpeg"))],
        )
        assert response.status_code == 201, response.json()

        async with get_sessionmaker()() as session:
            names = (
                (
                    await session.execute(
                        select(Photo.filename).where(Photo.album_id == album_id)
                    )
                )
                .scalars()
                .all()
            )

        # The legacy name occupies that stem, so the new file is suffixed rather
        # than writing over its preview and thumbnail.
        assert any(name.endswith("ted0113-2.jpg") for name in names), names
    finally:
        await cleanup(email)


async def test_album_copy_can_be_edited_and_blanked(client):
    """Title, credit and description - the copy an album carries.

    Blanking matters as much as setting: taking a credit off work that is your
    own is the same operation with an empty field.
    """
    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")

        response, body = await do_json(
            client,
            "PATCH",
            f"/api/manage/albums/{slug}",
            token=token,
            json={
                "title": "Autumn Marsh",
                "credit": "Shot by someone else",
                "description": "A note about the work.",
            },
        )
        assert response.status_code == 200, body
        album = body["album"]
        assert album["title"] == "Autumn Marsh"
        assert album["credit"] == "Shot by someone else"
        assert album["description"] == "A note about the work."
        # The URL is unaffected: the slug is frozen so links survive a rename.
        assert album["slug"] == slug

        # Empty strings clear the optional fields rather than storing "".
        response, body = await do_json(
            client,
            "PATCH",
            f"/api/manage/albums/{slug}",
            token=token,
            json={"credit": "", "description": "   "},
        )
        assert response.status_code == 200, body
        assert body["album"]["credit"] is None
        assert body["album"]["description"] is None
        assert body["album"]["title"] == "Autumn Marsh"  # untouched

        # And a blank title is ignored rather than emptying a required field.
        response, body = await do_json(
            client,
            "PATCH",
            f"/api/manage/albums/{slug}",
            token=token,
            json={"title": "   "},
        )
        assert response.status_code == 200, body
        assert body["album"]["title"] == "Autumn Marsh"
    finally:
        await cleanup(email)


async def test_a_batch_larger_than_the_cap_is_refused(client):
    from app.services.uploads import MAX_FILES_PER_UPLOAD

    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")
        response = await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=[
                ("files", (f"p{i}.jpg", _jpeg(20, 20), "image/jpeg"))
                for i in range(MAX_FILES_PER_UPLOAD + 1)
            ],
        )
        assert response.status_code == 400
        assert "At most" in response.json()["message"]
    finally:
        await cleanup(email)


async def test_an_upload_with_no_files_is_refused(client):
    email, token = await _artist(client)
    try:
        slug = await _create_album(client, token, access="free")
        response = await client.post(
            f"/api/manage/albums/{slug}/photos",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert response.json()["message"] == "No files were sent"
    finally:
        await cleanup(email)
