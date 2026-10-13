import re
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.exceptions.base import ConflictException


class UserRepository:
    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["users"]

    async def create_indexes(self) -> None:
        """Create the users indexes defined by the authoritative Database Design SRS.

        Mirrors ``scripts/create_indexes.py`` exactly (6 indexes): email (unique,
        sparse), phone (unique, sparse), organization_id, department_id, role, and
        the compound (organization_id, role) index.
        """
        await self._collection.create_index("email", unique=True, sparse=True, name="idx_users_email")
        await self._collection.create_index("phone", unique=True, sparse=True, name="idx_users_phone")
        await self._collection.create_index("organization_id", name="idx_users_organization_id")
        await self._collection.create_index("department_id", name="idx_users_department_id")
        await self._collection.create_index("role", name="idx_users_role")
        await self._collection.create_index([("organization_id", 1), ("role", 1)], name="idx_users_org_role")

    async def create(self, user_data: dict[str, Any]) -> str:
        """Create a new user document. Returns the inserted user ID."""
        try:
            result = await self._collection.insert_one(user_data)
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            error_msg = str(e)
            if "email" in error_msg:
                raise ConflictException("Email already registered")
            elif "phone" in error_msg:
                raise ConflictException("Phone number already registered")
            raise ConflictException("Duplicate key error")

    async def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Find a user by ObjectId string (no tenant scoping - for admin/global use)."""
        try:
            object_id = ObjectId(user_id)
        except Exception:
            return None
        return await self._collection.find_one({"_id": object_id})

    async def find_by_id_in_organization(self, user_id: str, organization_id: str) -> dict[str, Any] | None:
        """Find a user by ID scoped to an organization (tenant isolation).

        Returns the user only if they belong to the specified organization.
        """
        try:
            object_id = ObjectId(user_id)
        except Exception:
            return None
        return await self._collection.find_one({
            "_id": object_id,
            "organization_id": organization_id,
        })

    async def find_by_id_in_department(self, user_id: str, department_id: str) -> dict[str, Any] | None:
        """Find a user by ID scoped to a department (tenant isolation).

        Returns the user only if they belong to the specified department.
        """
        try:
            object_id = ObjectId(user_id)
        except Exception:
            return None
        return await self._collection.find_one({
            "_id": object_id,
            "department_id": department_id,
        })

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        """Find a user by email (case-insensitive)."""
        return await self._collection.find_one({"email": email.lower()})

    async def find_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Find a user by phone."""
        return await self._collection.find_one({"phone": phone})

    async def find_by_email_or_phone(self, email: str, phone: str) -> dict[str, Any] | None:
        """Find a user by email or phone."""
        return await self._collection.find_one({"$or": [{"email": email.lower()}, {"phone": phone}]})

    async def find_by_full_name(self, full_name: str) -> dict[str, Any] | None:
        """Find a user by full_name (case-insensitive)."""
        escaped_name = re.escape(full_name.strip())
        return await self._collection.find_one({
            "full_name": re.compile(f"^{escaped_name}$", re.IGNORECASE)
        })

    async def find_users_in_organization(
        self,
        organization_id: str,
        role: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """Find users belonging to an organization (tenant-scoped).

        Args:
            organization_id: The organization to filter by.
            role: Optional role filter.
            limit: Maximum number of results.
            skip: Number of results to skip.

        Returns:
            List of user documents in the organization.
        """
        query = {"organization_id": organization_id}
        if role:
            query["role"] = role
        cursor = self._collection.find(query).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_users_in_department(
        self,
        department_id: str,
        role: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """Find users belonging to a department (tenant-scoped).

        Args:
            department_id: The department to filter by.
            role: Optional role filter.
            limit: Maximum number of results.
            skip: Number of results to skip.

        Returns:
            List of user documents in the department.
        """
        query = {"department_id": department_id}
        if role:
            query["role"] = role
        cursor = self._collection.find(query).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_users_in_organization_and_department(
        self,
        organization_id: str,
        department_id: str,
        role: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """Find users in a department AND organization (tenant isolation boundary).

        Matching on both fields means a department_id from another organization
        can never be used to list that organization's staff.

        Args:
            organization_id: The organization to scope by.
            department_id: The department to filter by.
            role: Optional role filter.
            limit: Maximum number of results.
            skip: Number of results to skip.

        Returns:
            List of user documents in the department within the organization.
        """
        query: dict[str, Any] = {
            "organization_id": organization_id,
            "department_id": department_id,
        }
        if role:
            query["role"] = role
        cursor = self._collection.find(query).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_users_in_organization(self, organization_id: str, role: str | None = None) -> int:
        """Count users in an organization (tenant-scoped)."""
        query = {"organization_id": organization_id}
        if role:
            query["role"] = role
        return await self._collection.count_documents(query)

    async def update(self, user_id: str, update_data: dict[str, Any]) -> bool:
        """Update a user document. Returns True if updated."""
        try:
            object_id = ObjectId(user_id)
        except Exception:
            return False

        update_data["updated_at"] = datetime.utcnow()
        result = await self._collection.update_one({"_id": object_id}, {"$set": update_data})
        return result.modified_count > 0

    async def update_in_organization(
        self,
        user_id: str,
        organization_id: str,
        update_data: dict[str, Any],
    ) -> bool:
        """Update a user document scoped to an organization (tenant isolation).

        Returns True if updated. The update only succeeds if the user belongs
        to the specified organization.
        """
        try:
            object_id = ObjectId(user_id)
        except Exception:
            return False

        update_data["updated_at"] = datetime.utcnow()
        result = await self._collection.update_one(
            {"_id": object_id, "organization_id": organization_id},
            {"$set": update_data},
        )
        return result.modified_count > 0

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user exists with the given email."""
        return await self._collection.count_documents({"email": email.lower()}, limit=1) > 0

    async def exists_by_phone(self, phone: str) -> bool:
        """Check if a user exists with the given phone."""
        return await self._collection.count_documents({"phone": phone}, limit=1) > 0

    async def exists_by_email_in_organization(self, email: str, organization_id: str) -> bool:
        """Check if a user exists with the given email in an organization."""
        return await self._collection.count_documents(
            {"email": email.lower(), "organization_id": organization_id},
            limit=1,
        ) > 0

    async def find_users(
        self,
        role: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """Find users with filtering and search (Admin use)."""
        query: dict[str, Any] = {}
        if role:
            query["role"] = role
        if status:
            query["status"] = status
        if search:
            # Escape regex metacharacters: the search is a literal substring
            # match, so a user-supplied operator (e.g. ".*") can neither widen
            # the match into a full collection scan nor alter the semantics.
            escaped = re.escape(search.strip())
            query["$or"] = [
                {"email": {"$regex": escaped, "$options": "i"}},
                {"full_name": {"$regex": escaped, "$options": "i"}},
                {"phone": {"$regex": escaped}},
            ]
        cursor = self._collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_users(
        self,
        role: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        """Count users with filtering and search (Admin use)."""
        query: dict[str, Any] = {}
        if role:
            query["role"] = role
        if status:
            query["status"] = status
        if search:
            escaped = re.escape(search.strip())
            query["$or"] = [
                {"email": {"$regex": escaped, "$options": "i"}},
                {"full_name": {"$regex": escaped, "$options": "i"}},
                {"phone": {"$regex": escaped}},
            ]
        return await self._collection.count_documents(query)

    async def count_all(self) -> int:
        """Count all users across system."""
        return await self._collection.count_documents({})
