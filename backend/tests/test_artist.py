"""Database-backed tests for the artist role and the public profile."""

from __future__ import annotations

from sqlalchemy import delete, select

from app.db.session import get_sessionmaker
from app.models import ArtistProfile, User
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

VALID = {
    "displayName": "Test Artist",
    "tagline": "Artist",
    "statement": "Made without asking anyone to hold still.",
    "bio": "Shoots rooms and the people in them.",
    "location": "Austin, TX",
    "contactEmail": "shoot@example.com",
}


async def _artist(client) -> tuple[str, str]:
    """A signed-in user promoted to artist, past the onboarding gate."""
    email = unique_email("artist")
    await signup(client, email)
    token = await login(client, email)
    await fill_profile(client, token)
    await set_role(email, "artist")
    return email, token


async def _drop_profile(email: str) -> None:
    """Best-effort teardown of the profile row for an email."""
    async with get_sessionmaker()() as session:
        user_id = await session.scalar(_user_id_query(email))
        if user_id is not None:
            await session.execute(
                delete(ArtistProfile).where(ArtistProfile.user_id == user_id)
            )
            await session.commit()


def _user_id_query(email: str):
    return select(User.id).where(User.email == email)


async def test_public_profile_is_readable_without_a_session(client):
    response, body = await do_json(client, "GET", "/api/artist/profile")
    assert response.status_code == 200
    # Null, not a 404: "no profile saved yet" is a normal state, and the site
    # falls back to its built-in defaults.
    assert "profile" in body


async def test_client_cannot_write_the_profile(client):
    email = unique_email()
    try:
        await signup(client, email)
        token = await login(client, email)
        await fill_profile(client, token)

        response, body = await do_json(
            client, "PUT", "/api/artist/profile", token=token, json=VALID
        )
        assert response.status_code == 403
        assert body["message"] == "Insufficient permissions"
    finally:
        await cleanup(email)


async def test_artist_saves_and_the_public_reads_it_back(client):
    email, token = await _artist(client)
    try:
        response, body = await do_json(
            client, "GET", "/api/artist/profile/mine", token=token
        )
        assert response.status_code == 200
        assert body["profile"] is None  # nothing saved yet

        response, body = await do_json(
            client, "PUT", "/api/artist/profile", token=token, json=VALID
        )
        assert response.status_code == 200, body
        assert body["success"] is True
        assert body["profile"]["displayName"] == "Test Artist"

        # The public endpoint now serves it, with no session at all.
        response, body = await do_json(client, "GET", "/api/artist/profile")
        assert response.status_code == 200
        assert body["profile"]["statement"] == VALID["statement"]

        # Blank optionals are stored as null rather than empty strings.
        response, body = await do_json(
            client,
            "PUT",
            "/api/artist/profile",
            token=token,
            json={**VALID, "phone": "   ", "instagram": ""},
        )
        assert response.status_code == 200
        assert body["profile"]["phone"] is None
        assert body["profile"]["instagram"] is None
    finally:
        await _drop_profile(email)
        await cleanup(email)


async def test_profile_validation_rejects_missing_and_bad_email(client):
    email, token = await _artist(client)
    try:
        response, body = await do_json(
            client,
            "PUT",
            "/api/artist/profile",
            token=token,
            json={**VALID, "displayName": "", "bio": "  "},
        )
        assert response.status_code == 400
        assert "Missing required field(s): displayName, bio" in body["message"]

        response, body = await do_json(
            client,
            "PUT",
            "/api/artist/profile",
            token=token,
            json={**VALID, "contactEmail": "not-an-email"},
        )
        assert response.status_code == 400
        assert body["message"] == "Contact email is invalid"
    finally:
        await cleanup(email)


async def test_a_profile_cannot_be_edited_by_a_different_artist(client):
    """PUT always writes the caller's own row, never someone else's."""
    first_email, first_token = await _artist(client)
    second_email, second_token = await _artist(client)
    try:
        await do_json(
            client, "PUT", "/api/artist/profile", token=first_token, json=VALID
        )

        # The second artist has no row of their own yet, so the editor
        # opens empty rather than showing the first one's copy.
        response, body = await do_json(
            client, "GET", "/api/artist/profile/mine", token=second_token
        )
        assert response.status_code == 200
        assert body["profile"] is None

        # And saving their own work does not overwrite the first one's.
        response, body = await do_json(
            client,
            "PUT",
            "/api/artist/profile",
            token=second_token,
            json={**VALID, "displayName": "Second Artist"},
        )
        assert response.status_code == 200

        response, body = await do_json(
            client, "GET", "/api/artist/profile/mine", token=first_token
        )
        assert body["profile"]["displayName"] == "Test Artist"
    finally:
        await _drop_profile(first_email)
        await _drop_profile(second_email)
        await cleanup(first_email)
        await cleanup(second_email)


async def test_artist_is_below_staff_in_the_ladder(client):
    email, token = await _artist(client)
    try:
        # A artist must not reach user management...
        response, body = await do_json(client, "GET", "/api/users", token=token)
        assert response.status_code == 403
        assert body["message"] == "Insufficient permissions"

        # ...but the profile endpoint is theirs.
        response, _ = await do_json(
            client, "GET", "/api/artist/profile/mine", token=token
        )
        assert response.status_code == 200
    finally:
        await cleanup(email)


async def test_staff_can_see_artists_in_the_user_list(client):
    """The staff-visible filter has to include the new tier."""
    staff_email = unique_email("staff")
    artist_email = unique_email("artist")
    try:
        await signup(client, staff_email)
        staff_token = await login(client, staff_email)
        await fill_profile(client, staff_token)
        await set_role(staff_email, "staff")

        await signup(client, artist_email)
        artist_token = await login(client, artist_email)
        await fill_profile(client, artist_token)
        await set_role(artist_email, "artist")

        response, body = await do_json(client, "GET", "/api/users", token=staff_token)
        assert response.status_code == 200
        roles = {u["email"]: u["role"] for u in body["users"]}
        assert roles.get(artist_email) == "artist"
    finally:
        await cleanup(staff_email)
        await cleanup(artist_email)
