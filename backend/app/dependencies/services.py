"""Shared service-provider dependencies.

Kept in a neutral module so both the API routes and the authentication
dependency can consume the same providers without importing each other.
"""

from typing import Any

from fastapi import Depends
from pymongo.asynchronous.database import AsyncDatabase

from app.db.database import get_database
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.token_service import RefreshTokenService
from app.services.user_service import UserService


def get_user_service(
    database: AsyncDatabase[Any] = Depends(get_database),
) -> UserService:
    """Build a :class:`UserService` bound to the request's database."""
    return UserService(UserRepository(database))


def get_refresh_token_service(
    database: AsyncDatabase[Any] = Depends(get_database),
    user_service: UserService = Depends(get_user_service),
) -> RefreshTokenService:
    """Build a :class:`RefreshTokenService` bound to the request's database."""
    return RefreshTokenService(RefreshTokenRepository(database), user_service)
