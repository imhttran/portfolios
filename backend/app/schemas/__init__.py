"""Pydantic request/response schemas."""

from app.schemas.artist import (
    ArtistProfileInput,
    ArtistProfileOut,
    ArtistSummary,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailRequest,
    LoginRequest,
    MeUser,
    ResendCodeRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyLoginRequest,
)
from app.schemas.base import CamelModel
from app.schemas.media import (
    AlbumDetail,
    AlbumInput,
    AlbumPatch,
    AlbumSummary,
    ManagedAlbum,
    PhotoOut,
)
from app.schemas.profile import ProfileInput, ProfileOut
from app.schemas.users import CreateUserRequest, PatchRoleRequest, UserSummary

__all__ = [
    "AlbumDetail",
    "AlbumInput",
    "AlbumPatch",
    "AlbumSummary",
    "ArtistProfileInput",
    "ArtistProfileOut",
    "ArtistSummary",
    "CamelModel",
    "ChangePasswordRequest",
    "CreateUserRequest",
    "EmailRequest",
    "LoginRequest",
    "MeUser",
    "ManagedAlbum",
    "PatchRoleRequest",
    "PhotoOut",
    "ProfileInput",
    "ProfileOut",
    "ResendCodeRequest",
    "ResetPasswordRequest",
    "SignupRequest",
    "UserSummary",
    "VerifyLoginRequest",
]
