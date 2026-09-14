"""Model registry.

Importing this package registers every table on ``Base.metadata`` so that
``create_all`` and the ORM can resolve them.
"""

from app.models.email import EmailQueue
from app.models.login import LoginCode, UserDevice
from app.models.user import User, UserProfile

__all__ = [
    "EmailQueue",
    "LoginCode",
    "User",
    "UserDevice",
    "UserProfile",
]
