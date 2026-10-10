from fastapi import APIRouter, Depends, Query

from app.dependencies.services import get_geocoding_service
from app.schemas.location import ReverseGeocodeResponse
from app.services.geocoding_service import GeocodingService

router = APIRouter(prefix="/location", tags=["Location"])


@router.get(
    "/reverse",
    response_model=ReverseGeocodeResponse,
    summary="Reverse geocode coordinates",
    description=(
        "Reverse geocode latitude and longitude coordinates into a structured, "
        "human-readable civic location address. Open to citizens, staff, and public users."
    ),
)
async def reverse_geocode(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180"),
    service: GeocodingService = Depends(get_geocoding_service),
) -> ReverseGeocodeResponse:
    """Reverse geocode geographic coordinates."""
    return await service.reverse_geocode(lat=lat, lng=lng)
