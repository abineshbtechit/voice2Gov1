from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    categories,
    complaints,
    departments,
    feed,
    health,
    location,
    notifications,
    organizations,
    search,
    users,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(organizations.router)
api_router.include_router(departments.router)
api_router.include_router(categories.router)
api_router.include_router(complaints.router)
api_router.include_router(feed.router)
api_router.include_router(search.router)
api_router.include_router(notifications.router)
api_router.include_router(location.router)
