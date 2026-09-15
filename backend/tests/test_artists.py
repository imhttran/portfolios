"""Database-backed tests for the public roster and an artist's page."""

from __future__ import annotations

import uuid

from sqlalchemy import delete

from app.db.session import get_sessionmaker
from app.models import Album, Photo
from app.models.tiers import TIER_FREE, TIER_PAID
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

PROFILE = {
    "displayName": "Test Artist",
    "tagline": "Photographer",
    "statement": "A statement.",
    "bio": "A bio.",
    "location": "Austin, TX",
    "contactEmail": "shoot@example.com",
}


async def _artist(client, display_name: str) -> tuple[str, str, int, str]:
    """An artist with a saved profile; returns (email, token, id, slug)."""
    email = unique_email("artist")
    await signup(client, email)
    token = await login(client, email)
    await fill_profile(client, token)
    await set_role(email, "artist")

    response, body = await do_json(
        client,
        "PUT",
        "/api/artist/profile",
        token=token,
        json={**PROFILE, "displayName": display_name},
    )
    assert response.status_code == 200, body
    return email, token, await own_user_id(client, token), body["profile"]["slug"]


async def _album(
    *, artist_id: int, access: str, published: bool = True
) -> tuple[int, str]:
    slug = f"pytest-album-{uuid.uuid4().hex[:8]}"
    filename = f"{slug}/01.png"
    storage.write_bytes(filename, gradient_png(40, 30, 10, 200))

    async with get_sessionmaker()() as session:
        album = Album(
            slug=slug,
            title="Test Album",
            access=access,
            artist_id=artist_id,
            is_published=published,
        )
        session.add(album)
        await session.flush()
        session.add(
            Photo(album_id=album.id, filename=filename, title="Frame", position=1)
        )
        await session.commit()
    return album.id, slug


async def _drop(*album_ids: int) -> None:
    async with get_sessionmaker()() as session:
        for album_id in album_ids:
            await session.execute(delete(Album).where(Album.id == album_id))
        await session.commit()


async def test_roster_is_public_and_lists_every_artist(client):
    email, _, _, slug = await _artist(client, "Roster Person")
    try:
        # No session at all.
        response, body = await do_json(client, "GET", "/api/artists")
        assert response.status_code == 200
        entry = next(a for a in body["artists"] if a["slug"] == slug)
        assert entry["displayName"] == "Roster Person"
        assert entry["tagline"] == PROFILE["tagline"]
        assert entry["location"] == PROFILE["location"]
    finally:
        await cleanup(email)


async def test_artist_page_shows_their_work_and_nobody_elses(client):
    first_email, _, first_id, first_slug = await _artist(client, "First Artist")
    second_email, _, second_id, second_slug = await _artist(client, "Second Artist")
    mine, _ = await _album(artist_id=first_id, access=TIER_FREE)
    theirs, _ = await _album(artist_id=second_id, access=TIER_PAID)
    try:
        response, body = await do_json(client, "GET", f"/api/artists/{first_slug}")
        assert response.status_code == 200
        assert body["artist"]["displayName"] == "First Artist"
        assert body["artist"]["statement"] == PROFILE["statement"]
        assert body["artist"]["slug"] == first_slug
        assert [a["id"] for a in body["albums"]] == [mine]

        # And the other artist's page shows only theirs.
        response, body = await do_json(client, "GET", f"/api/artists/{second_slug}")
        assert [a["id"] for a in body["albums"]] == [theirs]
    finally:
        await _drop(mine, theirs)
        await cleanup(first_email)
        await cleanup(second_email)


async def test_unpublished_albums_are_hidden_from_an_artist_page(client):
    email, _, artist_id, slug = await _artist(client, "Private Artist")
    album_id, _ = await _album(artist_id=artist_id, access=TIER_FREE, published=False)
    try:
        response, body = await do_json(client, "GET", f"/api/artists/{slug}")
        assert response.status_code == 200
        assert body["albums"] == []
    finally:
        await _drop(album_id)
        await cleanup(email)


async def test_unknown_artist_slug_is_a_404(client):
    response, body = await do_json(client, "GET", "/api/artists/nobody-here")
    assert response.status_code == 404
    assert body["message"] == "Artist not found"


async def test_slugs_are_derived_and_made_unique(client):
    first_email, _, _, first_slug = await _artist(client, "Same Name")
    second_email, _, _, second_slug = await _artist(client, "Same Name")
    try:
        assert first_slug == "same-name"
        # The second has to differ, or the URL would be ambiguous.
        assert second_slug == "same-name-2"
    finally:
        await cleanup(first_email)
        await cleanup(second_email)


async def test_albums_carry_their_artists_name(client):
    """The gallery needs this to name who a subscribe prompt is for."""
    email, _, artist_id, slug = await _artist(client, "Named Artist")
    album_id, album_slug = await _album(artist_id=artist_id, access=TIER_PAID)
    try:
        response, body = await do_json(client, "GET", f"/api/media/albums/{album_slug}")
        assert body["album"]["artistName"] == "Named Artist"
        assert body["album"]["artistSlug"] == slug

        response, body = await do_json(client, "GET", "/api/media/albums")
        listed = next(a for a in body["albums"] if a["slug"] == album_slug)
        assert listed["artistName"] == "Named Artist"
    finally:
        await _drop(album_id)
        await cleanup(email)
