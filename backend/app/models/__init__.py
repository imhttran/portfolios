"""Model registry.

Importing this package registers every table on ``Base.metadata`` so that
``create_all`` and the ORM can resolve them.
"""

from app.models.artist import ArtistProfile
from app.models.email import EmailQueue
from app.models.login import LoginCode, UserDevice
from app.models.photo import Album, Photo
from app.models.subscription import Subscription
from app.models.user import User, UserProfile

__all__ = [
    "Album",
    "ArtistProfile",
    "EmailQueue",
    "LoginCode",
    "Photo",
    "Subscription",
    "User",
    "UserDevice",
    "UserProfile",
]
