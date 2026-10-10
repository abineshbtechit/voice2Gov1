import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

if TYPE_CHECKING:
    pass

from app.exceptions.base import ConflictException


class ComplaintRepository:
    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self._collection: AsyncCollection[Any] = database["complaints"]

    async def create_indexes(self) -> None:
        """Create the complaints indexes defined by the authoritative Database Design SRS.

        Mirrors scripts/create_indexes.py exactly (14 indexes):
        - complaint_number (unique)
        - user_id
        - organization_id
        - department_id
        - status
        - category_id
        - created_at (descending)
        - priority_score (descending)
        - location (2dsphere)
        - org + status + created_at (compound)
        - dept + status + priority_score (compound)
        - user + created_at (compound)
        - assigned_to
        - sla_deadline (sparse)
        - visibility + status + created_at (compound)
        """
        await self._collection.create_index(
            "complaint_number", unique=True, name="idx_complaints_complaint_number"
        )
        await self._collection.create_index("user_id", name="idx_complaints_user_id")
        await self._collection.create_index("organization_id", name="idx_complaints_org_id")
        await self._collection.create_index("department_id", name="idx_complaints_dept_id")
        await self._collection.create_index("status", name="idx_complaints_status")
        await self._collection.create_index("category_id", name="idx_complaints_category_id")
        await self._collection.create_index("created_at", name="idx_complaints_created_at")
        await self._collection.create_index("priority_score", name="idx_complaints_priority")
        await self._collection.create_index(
            [("location", "2dsphere")], name="idx_complaints_location"
        )
        await self._collection.create_index(
            [("organization_id", 1), ("status", 1), ("created_at", -1)],
            name="idx_complaints_org_status_created",
        )
        await self._collection.create_index(
            [("department_id", 1), ("status", 1), ("priority_score", -1)],
            name="idx_complaints_dept_status_priority",
        )
        await self._collection.create_index(
            [("user_id", 1), ("created_at", -1)], name="idx_complaints_user_created"
        )
        await self._collection.create_index("assigned_to", name="idx_complaints_assigned_to")
        await self._collection.create_index(
            "sla_deadline", sparse=True, name="idx_complaints_sla_deadline"
        )
        await self._collection.create_index(
            [("visibility", 1), ("status", 1), ("created_at", -1)],
            name="idx_complaints_visibility_status_created",
        )

    async def create(self, complaint_data: dict[str, Any]) -> str:
        """Create a new complaint document. Returns the inserted complaint ID."""
        try:
            result = await self._collection.insert_one(complaint_data)
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            error_msg = str(e)
            if "complaint_number" in error_msg:
                raise ConflictException("Complaint number already exists")
            raise ConflictException("Duplicate key error")

    async def find_by_id(self, complaint_id: str) -> dict[str, Any] | None:
        """Find a complaint by ObjectId string (no tenant scoping - for admin/global use)."""
        try:
            object_id = ObjectId(complaint_id)
        except Exception:
            return None
        return await self._collection.find_one({"_id": object_id})

    async def find_by_id_in_organization(
        self, complaint_id: str, organization_id: str
    ) -> dict[str, Any] | None:
        """Find a complaint by ID scoped to an organization (tenant isolation).

        Returns the complaint only if it belongs to the specified organization.
        """
        try:
            object_id = ObjectId(complaint_id)
        except Exception:
            return None
        return await self._collection.find_one(
            {"_id": object_id, "organization_id": organization_id}
        )

    async def find_by_complaint_number(self, complaint_number: str) -> dict[str, Any] | None:
        """Find a complaint by its human-readable complaint number."""
        return await self._collection.find_one({"complaint_number": complaint_number})

    async def count_complaints_by_year(self, year: int) -> int:
        """Count complaints for a given year (for complaint number generation)."""
        return await self._collection.count_documents(
            {"complaint_number": {"$regex": f"^CMP-{year}-\\d{{6}}$"}}
        )

    async def find_by_id_for_user(
        self, complaint_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """Find a complaint by ID scoped to a user (for citizen retrieving own complaint)."""
        try:
            object_id = ObjectId(complaint_id)
        except Exception:
            return None
        return await self._collection.find_one(
            {"_id": object_id, "user_id": user_id}
        )

    async def find_by_id_for_organization_staff(
        self, complaint_id: str, organization_id: str, department_id: str | None = None
    ) -> dict[str, Any] | None:
        """Find a complaint by ID for organization staff with department scoping.

        For organization staff, additionally filter by department_id if provided.
        """
        try:
            object_id = ObjectId(complaint_id)
        except Exception:
            return None
        query = {"_id": object_id, "organization_id": organization_id}
        if department_id:
            query["department_id"] = department_id
        return await self._collection.find_one(query)

    async def find_by_id_for_admin(
        self, complaint_id: str
    ) -> dict[str, Any] | None:
        """Find a complaint by ID with no tenant filtering (admin global access)."""
        try:
            object_id = ObjectId(complaint_id)
        except Exception:
            return None
        return await self._collection.find_one({"_id": object_id})

    async def find_user_complaints(
        self,
        user_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Find complaints for a specific user (citizen's own complaints)."""
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        skip = (page - 1) * page_size
        cursor = self._collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
        return await cursor.to_list(length=page_size)

    async def count_user_complaints(self, user_id: str, status: str | None = None) -> int:
        """Count complaints for a specific user."""
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        return await self._collection.count_documents(query)

    async def find_organization_complaints(
        self,
        organization_id: str,
        status: str | None = None,
        department_id: str | None = None,
        assigned_to: str | None = None,
        sort_by: str = "priority",
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Find complaints for an organization with filtering and pagination."""
        query = {"organization_id": organization_id}
        if status:
            query["status"] = status
        if department_id:
            query["department_id"] = department_id
        if assigned_to:
            query["assigned_to"] = assigned_to

        # Determine sort order
        if sort_by == "priority":
            sort_field = [("priority_score", -1), ("created_at", -1)]
        elif sort_by == "recent":
            sort_field = [("created_at", -1)]
        elif sort_by == "sla":
            sort_field = [("sla_deadline", 1)]
        else:
            sort_field = [("created_at", -1)]

        skip = (page - 1) * page_size
        cursor = self._collection.find(query).sort(sort_field).skip(skip).limit(page_size)
        return await cursor.to_list(length=page_size)

    async def count_organization_complaints(
        self,
        organization_id: str,
        status: str | None = None,
        department_id: str | None = None,
        assigned_to: str | None = None,
    ) -> int:
        """Count complaints for an organization with filtering."""
        query = {"organization_id": organization_id}
        if status:
            query["status"] = status
        if department_id:
            query["department_id"] = department_id
        if assigned_to:
            query["assigned_to"] = assigned_to
        return await self._collection.count_documents(query)

    async def update_by_user(
        self, complaint_id: str, user_id: str, update_data: dict[str, Any]
    ) -> bool:
        """Update a complaint by a citizen (owner).

        Only allows updates to complaints owned by the specified user
        and only when the complaint is in SUBMITTED status.
        """
        try:
            object_id = ObjectId(complaint_id)
        except Exception:
            return False

        # Only allow update if complaint belongs to user and is SUBMITTED
        update_doc = {
            "$set": {**update_data, "updated_at": datetime.now(UTC)},
        }

        result = await self._collection.update_one(
            {"_id": object_id, "user_id": user_id, "status": "SUBMITTED"},
            update_doc,
        )
        return result.modified_count > 0

    async def update_in_organization(
        self,
        complaint_id: str,
        organization_id: str,
        update_data: dict[str, Any],
    ) -> bool:
        """Update a complaint within an organization (for org staff/admin)."""
        try:
            object_id = ObjectId(complaint_id)
        except Exception:
            return False

        update_doc = {
            "$set": {**update_data, "updated_at": datetime.now(UTC)},
        }

        result = await self._collection.update_one(
            {"_id": object_id, "organization_id": organization_id},
            update_doc,
        )
        return result.modified_count > 0

    async def transition_status(
        self,
        complaint_id: str,
        expected_status: str,
        new_status: str,
        update_fields: dict[str, Any],
        organization_id: str | None = None,
    ) -> bool:
        """Atomically transition a complaint status from expected_status to new_status.

        Guards against stale reads and concurrent race conditions by matching on
        `_id`, current `status == expected_status`, and optionally `organization_id`
        for tenant isolation.

        Returns True if the transition was applied (modified_count > 0), False otherwise.
        """
        try:
            object_id = ObjectId(complaint_id)
        except Exception:
            return False

        query: dict[str, Any] = {
            "_id": object_id,
            "status": expected_status,
        }
        if organization_id is not None:
            query["organization_id"] = organization_id

        now = datetime.now(UTC)
        set_payload = {
            **update_fields,
            "status": new_status,
            "updated_at": now,
        }

        result = await self._collection.update_one(
            query,
            {"$set": set_payload},
        )
        return result.modified_count > 0

    async def assign_complaint(
        self,
        complaint_id: str,
        expected_status: str,
        new_status: str,
        assigned_to: str,
        assigned_at: datetime,
        organization_id: str | None = None,
    ) -> bool:
        """Atomically assign/reassign a complaint with optimistic concurrency.

        Matches on `_id`, `status == expected_status`, and optionally `organization_id`.
        Updates `assigned_to`, `assigned_at`, `status`, and `updated_at`.

        Complaint documents store `organization_id` and `assigned_to` as strings
        (the representation written by :meth:`ComplaintService.create_complaint`),
        so the query must use the string form — an ``ObjectId`` here would never
        match and every org-scoped assignment would fail with a spurious 409.

        Returns True if modified_count > 0, False otherwise.
        """
        try:
            cid_oid = ObjectId(complaint_id)
        except Exception:
            return False

        query: dict[str, Any] = {
            "_id": cid_oid,
            "status": expected_status,
        }
        if organization_id is not None:
            query["organization_id"] = organization_id

        now = datetime.now(UTC)
        set_payload = {
            "assigned_to": str(assigned_to),
            "assigned_at": assigned_at,
            "status": new_status,
            "updated_at": now,
        }

        result = await self._collection.update_one(
            query,
            {"$set": set_payload},
        )
        return result.modified_count > 0

    async def complete_complaint(
        self,
        complaint_id: str,
        completed_at: datetime,
        organization_id: str | None = None,
    ) -> bool:
        """Atomically transition complaint from PROCESSING to COMPLETED with optimistic concurrency.

        Matches on `_id`, `status == PROCESSING`, and optionally `organization_id`.
        Updates `status` to `COMPLETED`, `completed_at`, and `updated_at`.

        Complaint documents store `organization_id` as a string (the
        representation written by :meth:`ComplaintService.create_complaint`), so
        the query must use the string form — an ``ObjectId`` here would never
        match and every org-scoped completion would fail with a spurious 409.

        Returns True if modified_count > 0, False otherwise.
        """
        try:
            cid_oid = ObjectId(complaint_id)
        except Exception:
            return False

        query: dict[str, Any] = {
            "_id": cid_oid,
            "status": "PROCESSING",
        }
        if organization_id is not None:
            query["organization_id"] = organization_id

        now = datetime.now(UTC)
        set_payload = {
            "status": "COMPLETED",
            "completed_at": completed_at,
            "updated_at": now,
        }

        result = await self._collection.update_one(
            query,
            {"$set": set_payload},
        )
        return result.modified_count > 0

    async def update_likes_count_and_priority(
        self,
        complaint_id: str,
        likes_count: int,
        priority_score: float,
        community_engagement_score: int,
    ) -> bool:
        """Update denormalized likes_count, priority_score, and community_engagement_score."""
        try:
            cid_oid = ObjectId(complaint_id)
        except Exception:
            return False

        now = datetime.now(UTC)
        result = await self._collection.update_one(
            {"_id": cid_oid},
            {
                "$set": {
                    "likes_count": likes_count,
                    "priority_score": priority_score,
                    "community_engagement_score": community_engagement_score,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count > 0

    @staticmethod
    def _build_feed_match_filter(
        status: str | None,
        category_id: str | None,
        organization_id: str | None,
        q: str | None = None,
    ) -> dict[str, Any]:
        match_filter: dict[str, Any] = {
            "visibility": "public",
        }
        if status:
            match_filter["status"] = status
        else:
            match_filter["status"] = {"$nin": ["REJECTED", "DUPLICATE", "CLOSED"]}

        if category_id:
            # Complaint documents store `category_id` as a string (the
            # representation written by the service layer); an ObjectId here
            # would never match and the filter would silently return nothing.
            match_filter["category_id"] = category_id

        if organization_id:
            # Complaint documents store `organization_id` as a string.
            match_filter["organization_id"] = organization_id

        if q and q.strip():
            safe_q = re.escape(q.strip())
            match_filter["$or"] = [
                {"title": {"$regex": safe_q, "$options": "i"}},
                {"description": {"$regex": safe_q, "$options": "i"}},
                {"complaint_number": {"$regex": safe_q, "$options": "i"}},
            ]

        return match_filter

    async def _query_nearby_feed(
        self,
        match_filter: dict[str, Any],
        lat: float,
        lng: float,
        radius_km: float,
        skip: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        max_distance_meters = radius_km * 1000.0
        pipeline: list[dict[str, Any]] = [
            {
                "$geoNear": {
                    "near": {"type": "Point", "coordinates": [lng, lat]},
                    "distanceField": "distance_meters",
                    "maxDistance": max_distance_meters,
                    "query": match_filter,
                    "spherical": True,
                }
            },
            {"$sort": {"distance_meters": 1, "created_at": -1, "_id": -1}},
            {
                "$facet": {
                    "items": [{"$skip": skip}, {"$limit": page_size}],
                    "total": [{"$count": "count"}],
                }
            },
        ]
        cursor = await self._collection.aggregate(pipeline)
        facet_res = await cursor.to_list(length=1)
        if not facet_res:
            return [], 0

        res = facet_res[0]
        items = res.get("items", [])
        total_items = res.get("total", [{}])[0].get("count", 0) if res.get("total") else 0

        for item in items:
            dist_m = item.pop("distance_meters", None)
            if dist_m is not None:
                item["distance_km"] = round(dist_m / 1000.0, 2)
        return items, total_items

    async def query_public_feed(
        self,
        status: str | None = None,
        category_id: str | None = None,
        organization_id: str | None = None,
        sort: str = "recent",
        page: int = 1,
        page_size: int = 20,
        lat: float | None = None,
        lng: float | None = None,
        radius_km: float = 10.0,
        q: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Query public complaint feed with filtering, pagination, and sorting."""
        match_filter = self._build_feed_match_filter(status, category_id, organization_id, q=q)
        skip = (page - 1) * page_size

        if sort == "nearby" and lat is not None and lng is not None:
            return await self._query_nearby_feed(
                match_filter=match_filter,
                lat=lat,
                lng=lng,
                radius_km=radius_km,
                skip=skip,
                page_size=page_size,
            )

        if sort == "popular":
            sort_spec = [("likes_count", -1), ("created_at", -1), ("_id", -1)]
        elif sort == "priority":
            sort_spec = [("priority_score", -1), ("created_at", -1), ("_id", -1)]
        else:
            sort_spec = [("created_at", -1), ("_id", -1)]

        total_items = await self._collection.count_documents(match_filter)
        cursor = self._collection.find(match_filter).sort(sort_spec).skip(skip).limit(page_size)
        items = await cursor.to_list(length=page_size)
        return items, total_items

    async def count_all(self) -> int:
        """Count all complaints."""
        return await self._collection.count_documents({})

    async def get_dashboard_aggregates(self) -> tuple[dict[str, int], float, float]:
        """Aggregate status breakdown, average resolution hours, and SLA compliance rate."""
        # 1. Status breakdown
        status_pipeline: list[dict[str, Any]] = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        status_cursor = await self._collection.aggregate(status_pipeline)
        status_counts: dict[str, int] = {}
        async for doc in status_cursor:
            if doc.get("_id"):
                status_counts[str(doc["_id"])] = int(doc["count"])

        # 2. Resolution hours and SLA compliance for COMPLETED complaints
        res_pipeline: list[dict[str, Any]] = [
            {
                "$match": {
                    "status": "COMPLETED",
                    "completed_at": {"$ne": None},
                    "created_at": {"$ne": None},
                }
            },
            {
                "$project": {
                    "resolution_hours": {
                        "$divide": [
                            {"$subtract": ["$completed_at", "$created_at"]},
                            1000 * 3600,
                        ]
                    },
                    "sla_compliant": {
                        "$cond": [
                            {"$ifNull": ["$sla_deadline", False]},
                            {"$lte": ["$completed_at", "$sla_deadline"]},
                            True,
                        ]
                    },
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_resolution_hours": {"$avg": "$resolution_hours"},
                    "total_completed": {"$sum": 1},
                    "compliant_count": {
                        "$sum": {"$cond": ["$sla_compliant", 1, 0]}
                    },
                }
            },
        ]

        res_cursor = await self._collection.aggregate(res_pipeline)
        res_docs = await res_cursor.to_list(length=1)

        avg_resolution_hours = 0.0
        sla_compliance_rate = 1.0
        if res_docs:
            row = res_docs[0]
            avg_res = row.get("avg_resolution_hours")
            avg_resolution_hours = round(float(avg_res), 2) if avg_res is not None else 0.0
            tot = row.get("total_completed", 0)
            comp = row.get("compliant_count", 0)
            if tot > 0:
                sla_compliance_rate = round(float(comp) / float(tot), 2)

        return status_counts, avg_resolution_hours, sla_compliance_rate




