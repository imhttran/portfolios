"""Database-backed tests for album delivery and the free/paid rules.

The whole point of the buckets is who may take a copy, so these cover: anyone
signed in for free work, a subscriber for paid work, the artist for their own,
and the fact that *looking* is never what's gated.
"""

from __future__ import annotations

import io
import uuid
import zipfile

from sqlalchemy import delete

from app.db.session import get_sessionmaker
from app.models import Album, Photo, Subscription
from app.models.tiers import TIER_FREE, TIER_PAID, TIER_PREMIUM
from app.services import storage
from app.services.placeholders import gradient_png
from tests.helpers import (
    cleanup,
    do_json,
    fill_profile,
    login,
    own_user_id,
    requires_db,
    set_role,
    signup,
    unique_email,
)

pytestmark = requires_db


async def _artist(client) -> tuple[str, int]:
    email = unique_email("artist")
    await signup(client, email)
    token = await login(client, email)
    await fill_profile(client, token)
    await set_role(email, "artist")
    return email, await own_user_id(client, token)


async def _client(client) -> tuple[str, str, int]:
    email = unique_email("client")
    await signup(client, email)
    token = await login(client, email)
    await fill_profile(client, token)
    return email, token, await own_user_id(client, token)


async def _make_album(
    *, artist_id: int, access: str, published: bool = True
) -> tuple[int, int, str]:
    """An album with one photo on disk; returns (album_id, photo_id, slug)."""
    slug = f"pytest-album-{uuid.uuid4().hex[:8]}"
    filename = f"{slug}/01.png"
    storage.write_bytes(filename, gradient_png(40, 30, 10, 200))

    async with get_sessionmaker()() as session:
        album = Album(
            slug=slug,
            title="Test Album",
            credit="Photography by Test",
            access=access,
            artist_id=artist_id,
            is_published=published,
        )
        session.add(album)
        await session.flush()
        photo = Photo(
            album_id=album.id, filename=filename, title="First Frame", position=1
        )
        session.add(photo)
        await session.flush()
        await session.commit()
        return album.id, photo.id, slug


async def _drop_album(album_id: int) -> None:
    async with get_sessionmaker()() as session:
        # Photos go with it: the FK is ON DELETE CASCADE.
        await session.execute(delete(Album).where(Album.id == album_id))
        await session.commit()


async def _subscribe(subscriber_id: int, artist_id: int, level: str) -> None:
    async with get_sessionmaker()() as session:
        session.add(
            Subscription(subscriber_id=subscriber_id, artist_id=artist_id, level=level)
        )
        await session.commit()


async def test_unpublished_album_is_invisible_and_undownloadable(client):
    _, artist_id = await _artist(client)
    album_id, photo_id, slug = await _make_album(
        artist_id=artist_id, access=TIER_FREE, published=False
    )
    try:
        response, body = await do_json(client, "GET", "/api/media/albums")
        assert response.status_code == 200
        assert all(album["slug"] != slug for album in body["albums"])

        response, body = await do_json(client, "GET", f"/api/media/albums/{slug}")
        assert response.status_code == 404
        assert body["message"] == "Album not found"

        response, body = await do_json(
            client, "GET", f"/api/media/photos/{photo_id}/file"
        )
        assert response.status_code == 404
        assert body["message"] == "Photo not found"
    finally:
        await _drop_album(album_id)


async def test_free_album_downloads_for_any_registered_user(client):
    """No subscription, no relationship to the artist - just signed in."""
    artist_email, artist_id = await _artist(client)
    album_id, photo_id, slug = await _make_album(artist_id=artist_id, access=TIER_FREE)
    email = ""
    try:
        email, token, _ = await _client(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get(
            f"/api/media/photos/{photo_id}/download", headers=headers
        )
        assert response.status_code == 200
        assert response.content.startswith(b"\x89PNG")

        response = await client.get(
            f"/api/media/albums/{slug}/download", headers=headers
        )
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.namelist() == ["first-frame.png"]

        # A visitor with no session still can't take a copy.
        response = await client.get(f"/api/media/photos/{photo_id}/download")
        assert response.status_code == 401
    finally:
        await _drop_album(album_id)
        await cleanup(email)
        await cleanup(artist_email)


async def test_paid_album_needs_a_subscription(client):
    artist_email, artist_id = await _artist(client)
    album_id, photo_id, slug = await _make_album(artist_id=artist_id, access=TIER_PAID)
    email = ""
    try:
        email, token, subscriber_id = await _client(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Looking is not gated: the preview is public and the album is listed.
        response = await client.get(f"/api/media/photos/{photo_id}/file")
        assert response.status_code == 200
        response, body = await do_json(client, "GET", "/api/media/albums")
        listed = next(a for a in body["albums"] if a["slug"] == slug)
        assert listed["access"] == "paid"
        assert listed["canDownload"] is False

        # Taking is gated, both ways.
        response, body = await do_json(
            client, "GET", f"/api/media/photos/{photo_id}/download", token=token
        )
        assert response.status_code == 403
        assert "Subscribe" in body["message"]
        response, body = await do_json(
            client, "GET", f"/api/media/albums/{slug}/download", token=token
        )
        assert response.status_code == 403

        await _subscribe(subscriber_id, artist_id, TIER_PAID)

        response = await client.get(
            f"/api/media/photos/{photo_id}/download", headers=headers
        )
        assert response.status_code == 200
        response = await client.get(
            f"/api/media/albums/{slug}/download", headers=headers
        )
        assert response.status_code == 200

        # And the flag now tells the browser the same thing.
        response = await client.get("/api/media/albums", headers=headers)
        body = response.json()
        listed = next(a for a in body["albums"] if a["slug"] == slug)
        assert listed["canDownload"] is True
    finally:
        await _drop_album(album_id)
        await cleanup(email)
        await cleanup(artist_email)


async def test_artist_downloads_their_own_paid_work(client):
    artist_email, artist_id = await _artist(client)
    album_id, photo_id, _ = await _make_album(artist_id=artist_id, access=TIER_PAID)
    try:
        token = await login(client, artist_email)
        response = await client.get(
            f"/api/media/photos/{photo_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
    finally:
        await _drop_album(album_id)
        await cleanup(artist_email)


async def test_a_subscription_to_one_artist_does_not_open_another(client):
    first_email, first_artist = await _artist(client)
    second_email, second_artist = await _artist(client)
    album_id, photo_id, _ = await _make_album(artist_id=second_artist, access=TIER_PAID)
    email = ""
    try:
        email, token, subscriber_id = await _client(client)
        await _subscribe(subscriber_id, first_artist, TIER_PREMIUM)

        response, body = await do_json(
            client, "GET", f"/api/media/photos/{photo_id}/download", token=token
        )
        assert response.status_code == 403
        assert "Subscribe" in body["message"]
    finally:
        await _drop_album(album_id)
        await cleanup(email)
        await cleanup(first_email)
        await cleanup(second_email)


async def test_an_unrecognised_tier_is_not_treated_as_free(client):
    """Fail closed. A typo in the tier column must not open the work up.

    The column is plain text with no CHECK constraint, so only the code stands
    between a bad value and every registered user downloading it. The value here
    must stay a *misspelling* rather than a real tier, or the test stops
    covering the unknown-value path.
    """
    artist_email, artist_id = await _artist(client)
    album_id, photo_id, _ = await _make_album(artist_id=artist_id, access="premuim")
    email = ""
    try:
        email, token, _ = await _client(client)
        response, body = await do_json(
            client, "GET", f"/api/media/photos/{photo_id}/download", token=token
        )
        assert response.status_code == 403
        assert "Subscribe" in body["message"]
    finally:
        await _drop_album(album_id)
        await cleanup(email)
        await cleanup(artist_email)


async def test_the_ladder_only_reaches_down(client):
    """A premium album needs a premium subscriber; a paid one doesn't.

    The direction matters: a premium subscription opens paid albums as well,
    but a paid subscription must never open a premium album.
    """
    artist_email, artist_id = await _artist(client)
    paid_album, paid_photo, _ = await _make_album(artist_id=artist_id, access=TIER_PAID)
    premium_album, premium_photo, _ = await _make_album(
        artist_id=artist_id, access=TIER_PREMIUM
    )
    email = ""
    try:
        email, token, subscriber_id = await _client(client)
        headers = {"Authorization": f"Bearer {token}"}

        # No subscription at all: neither album opens.
        for photo_id in (paid_photo, premium_photo):
            response = await client.get(
                f"/api/media/photos/{photo_id}/download", headers=headers
            )
            assert response.status_code == 403

        # A paid subscription opens the paid album, and only that.
        await _subscribe(subscriber_id, artist_id, TIER_PAID)
        response = await client.get(
            f"/api/media/photos/{paid_photo}/download", headers=headers
        )
        assert response.status_code == 200
        response, body = await do_json(
            client,
            "GET",
            f"/api/media/photos/{premium_photo}/download",
            token=token,
        )
        assert response.status_code == 403
        assert "Subscribe" in body["message"]

        # Upgrading to premium opens both.
        async with get_sessionmaker()() as session:
            from sqlalchemy import update

            await session.execute(
                update(Subscription)
                .where(Subscription.subscriber_id == subscriber_id)
                .values(level=TIER_PREMIUM)
            )
            await session.commit()

        for photo_id in (paid_photo, premium_photo):
            response = await client.get(
                f"/api/media/photos/{photo_id}/download", headers=headers
            )
            assert response.status_code == 200
    finally:
        await _drop_album(paid_album)
        await _drop_album(premium_album)
        await cleanup(email)
        await cleanup(artist_email)


async def test_download_is_allowed_before_onboarding_is_done(client):
    """The downloads are exempt from the profile/password gates."""
    _, artist_id = await _artist(client)
    album_id, photo_id, slug = await _make_album(artist_id=artist_id, access=TIER_FREE)
    email = unique_email()
    try:
        await signup(client, email)
        token = await login(client, email)  # no profile, no password change
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get(
            f"/api/media/photos/{photo_id}/download", headers=headers
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/media/albums/{slug}/download", headers=headers
        )
        assert response.status_code == 200

        # The exemption is scoped to the downloads: a normal route still gates.
        response, body = await do_json(client, "GET", "/api/users", token=token)
        assert response.status_code == 403
        assert body["message"] == "Profile information required"
    finally:
        await _drop_album(album_id)
        await cleanup(email)


async def test_album_download_404s_when_album_is_empty(client):
    artist_email, artist_id = await _artist(client)
    _, token, _ = await _client(client)
    slug = f"pytest-empty-{uuid.uuid4().hex[:8]}"
    async with get_sessionmaker()() as session:
        album = Album(
            slug=slug,
            title="Empty",
            artist_id=artist_id,
            access=TIER_FREE,
            is_published=True,
        )
        session.add(album)
        await session.flush()
        album_id = album.id
        await session.commit()

    try:
        response, body = await do_json(
            client, "GET", f"/api/media/albums/{slug}/download", token=token
        )
        assert response.status_code == 404
        assert body["message"] == "Album has no photos"
    finally:
        await _drop_album(album_id)
        await cleanup(artist_email)
