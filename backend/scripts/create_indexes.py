import asyncio
import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.errors import OperationFailure

from app.core.config import settings

logger = logging.getLogger(__name__)

IndexSpec = list[tuple[str, int | str]]
IndexOptions = dict[str, Any]
IndexDefinition = tuple[IndexSpec, IndexOptions]

INDEXES: dict[str, list[tuple[list[tuple[str, int | str]], dict[str, Any]]]] = {
    "users": [
        ([("email", ASCENDING)], {"unique": True, "sparse": True, "name": "idx_users_email"}),
        ([("phone", ASCENDING)], {"unique": True, "sparse": True, "name": "idx_users_phone"}),
        ([("organization_id", ASCENDING)], {"name": "idx_users_organization_id"}),
        ([("department_id", ASCENDING)], {"name": "idx_users_department_id"}),
        ([("role", ASCENDING)], {"name": "idx_users_role"}),
        ([("organization_id", ASCENDING), ("role", ASCENDING)], {"name": "idx_users_org_role"}),
    ],
    "organizations": [
        ([("code", ASCENDING)], {"unique": True, "name": "idx_orgs_code"}),
        ([("name", ASCENDING)], {"unique": True, "name": "idx_orgs_name"}),
        ([("is_active", ASCENDING)], {"name": "idx_orgs_is_active"}),
    ],
    "departments": [
        ([("organization_id", ASCENDING)], {"name": "idx_depts_org_id"}),
        ([("organization_id", ASCENDING), ("code", ASCENDING)], {"unique": True, "name": "idx_depts_org_code"}),
        ([("organization_id", ASCENDING), ("name", ASCENDING)], {"unique": True, "name": "idx_depts_org_name"}),
        ([("organization_id", ASCENDING), ("status", ASCENDING)], {"name": "idx_depts_org_status"}),
    ],
    "categories": [
        ([("organization_id", ASCENDING), ("name", ASCENDING)], {"unique": True, "name": "idx_cats_org_name"}),
        ([("organization_id", ASCENDING)], {"name": "idx_cats_org_id"}),
        ([("organization_id", ASCENDING), ("status", ASCENDING)], {"name": "idx_cats_org_status"}),
        ([("default_department_id", ASCENDING)], {"name": "idx_cats_default_dept"}),
        ([("sort_order", ASCENDING)], {"name": "idx_cats_sort"}),
    ],
    "complaints": [
        ([("complaint_number", ASCENDING)], {"unique": True, "name": "idx_complaints_complaint_number"}),
        ([("user_id", ASCENDING)], {"name": "idx_complaints_user_id"}),
        ([("organization_id", ASCENDING)], {"name": "idx_complaints_org_id"}),
        ([("department_id", ASCENDING)], {"name": "idx_complaints_dept_id"}),
        ([("status", ASCENDING)], {"name": "idx_complaints_status"}),
        ([("category_id", ASCENDING)], {"name": "idx_complaints_category_id"}),
        ([("created_at", DESCENDING)], {"name": "idx_complaints_created_at"}),
        ([("priority_score", DESCENDING)], {"name": "idx_complaints_priority"}),
        ([("location", "2dsphere")], {"name": "idx_complaints_location"}),
        ([("organization_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)], {"name": "idx_complaints_org_status_created"}),
        ([("department_id", ASCENDING), ("status", ASCENDING), ("priority_score", DESCENDING)], {"name": "idx_complaints_dept_status_priority"}),
        ([("user_id", ASCENDING), ("created_at", DESCENDING)], {"name": "idx_complaints_user_created"}),
        ([("assigned_to", ASCENDING)], {"name": "idx_complaints_assigned_to"}),
        ([("sla_deadline", ASCENDING)], {"sparse": True, "name": "idx_complaints_sla_deadline"}),
        ([("visibility", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)], {"name": "idx_complaints_visibility_status_created"}),
    ],
    "complaint_images": [
        ([("complaint_id", ASCENDING)], {"name": "idx_images_complaint_id"}),
        ([("complaint_id", ASCENDING), ("image_type", ASCENDING)], {"name": "idx_images_complaint_type"}),
        ([("uploaded_by", ASCENDING)], {"name": "idx_images_uploaded_by"}),
        ([("created_at", DESCENDING)], {"name": "idx_images_created_at"}),
    ],
    "complaint_likes": [
        ([("complaint_id", ASCENDING), ("user_id", ASCENDING)], {"unique": True, "name": "idx_likes_complaint_user"}),
        ([("user_id", ASCENDING)], {"name": "idx_likes_user_id"}),
        ([("created_at", DESCENDING)], {"name": "idx_likes_created_at"}),
    ],
    "complaint_updates": [
        ([("complaint_id", ASCENDING)], {"name": "idx_updates_complaint_id"}),
        ([("complaint_id", ASCENDING), ("created_at", DESCENDING)], {"name": "idx_updates_complaint_created"}),
        ([("organization_id", ASCENDING)], {"name": "idx_updates_org_id"}),
        ([("department_id", ASCENDING)], {"name": "idx_updates_dept_id"}),
        ([("updated_by", ASCENDING)], {"name": "idx_updates_updated_by"}),
    ],
    "notifications": [
        ([("user_id", ASCENDING)], {"name": "idx_notifs_user_id"}),
        ([("user_id", ASCENDING), ("is_read", ASCENDING)], {"name": "idx_notifs_user_unread"}),
        ([("user_id", ASCENDING), ("created_at", DESCENDING)], {"name": "idx_notifs_user_created"}),
        ([("complaint_id", ASCENDING)], {"name": "idx_notifs_complaint_id"}),
    ],
    "device_tokens": [
        ([("user_id", ASCENDING)], {"name": "idx_device_user_id"}),
        ([("device_token", ASCENDING)], {"name": "idx_device_token"}),
        ([("user_id", ASCENDING), ("is_active", ASCENDING)], {"name": "idx_device_user_active"}),
        ([("user_id", ASCENDING), ("device_token", ASCENDING)], {"unique": True, "name": "idx_device_user_token"}),
    ],
    "audit_logs": [
        ([("actor_id", ASCENDING)], {"name": "idx_audit_actor_id"}),
        ([("entity_type", ASCENDING)], {"name": "idx_audit_entity_type"}),
        ([("entity_id", ASCENDING)], {"name": "idx_audit_entity_id"}),
        ([("action", ASCENDING)], {"name": "idx_audit_action"}),
        ([("created_at", DESCENDING)], {"name": "idx_audit_created_at"}),
        ([("entity_type", ASCENDING), ("entity_id", ASCENDING), ("created_at", DESCENDING)], {"name": "idx_audit_entity_timeline"}),
    ],
    "admin_settings": [
        ([("key", ASCENDING)], {"unique": True, "name": "idx_settings_key"}),
        ([("category", ASCENDING)], {"name": "idx_settings_category"}),
    ],
    "token_blacklist": [
        ([("token_hash", ASCENDING)], {"unique": True, "name": "idx_token_hash"}),
        ([("user_id", ASCENDING)], {"name": "idx_token_user_id"}),
        ([("token_family_id", ASCENDING)], {"name": "idx_token_family_id"}),
        ([("expires_at", ASCENDING)], {"expireAfterSeconds": 0, "name": "idx_token_expires_at_ttl"}),
        ([("user_id", ASCENDING), ("revoked_at", ASCENDING)], {"name": "idx_token_user_revoked"}),
    ],
    "password_reset_otps": [
        ([("identifier", ASCENDING)], {"name": "idx_otps_identifier"}),
        ([("expires_at", ASCENDING)], {"expireAfterSeconds": 0, "name": "idx_otps_expires_at_ttl"}),
        ([("reset_token_hash", ASCENDING)], {"name": "idx_otps_reset_token_hash"}),
    ],
}


async def create_indexes(db: "AsyncDatabase[Any]") -> None:
    for collection_name, indexes in INDEXES.items():
        collection = db[collection_name]
        for keys, options in indexes:
            try:
                await collection.create_index(keys, **options)
                logger.info(f"Created index: {options.get('name', keys)} on {collection_name}")
            except OperationFailure as e:
                logger.warning(f"Index creation failed for {collection_name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error creating index on {collection_name}: {e}")


async def drop_all_indexes(db: "AsyncDatabase[Any]") -> None:
    for collection_name in INDEXES.keys():
        collection = db[collection_name]
        try:
            await collection.drop_indexes()
            logger.info(f"Dropped all indexes on {collection_name}")
        except Exception as e:
            logger.error(f"Error dropping indexes on {collection_name}: {e}")


async def init_database_with_indexes() -> None:
    client: AsyncMongoClient[Any] = AsyncMongoClient[Any](
        settings.mongodb_uri,
        maxPoolSize=settings.mongodb_max_pool_size,
        minPoolSize=settings.mongodb_min_pool_size,
        maxIdleTimeMS=settings.mongodb_max_idle_time_ms,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    )
    try:
        db = client[settings.mongodb_database]
        await db.command("ping")
        await create_indexes(db)
        logger.info("Database indexes initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database indexes: {e}")
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_database_with_indexes())
