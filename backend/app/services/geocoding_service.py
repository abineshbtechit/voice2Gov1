from app.exceptions.base import ValidationException
from app.schemas.location import ReverseGeocodeResponse, ReverseGeocodeResponseData
from app.services.geocoding_provider import GeocodingProvider


class GeocodingService:
    """Reverse geocoding service with coordinate boundary validation and provider resilience."""

    def __init__(self, provider: GeocodingProvider) -> None:
        self._provider = provider

    async def reverse_geocode(self, lat: float, lng: float) -> ReverseGeocodeResponse:
        """Reverse geocode latitude and longitude into human-readable structured address."""
        if not (-90.0 <= lat <= 90.0):
            raise ValidationException(
                "Latitude must be between -90.0 and 90.0 degrees",
                errors=[{"field": "lat", "message": "Latitude out of valid range [-90, 90]", "code": "INVALID_COORDINATES"}],
            )
        if not (-180.0 <= lng <= 180.0):
            raise ValidationException(
                "Longitude must be between -180.0 and 180.0 degrees",
                errors=[{"field": "lng", "message": "Longitude out of valid range [-180, 180]", "code": "INVALID_COORDINATES"}],
            )

        try:
            result = await self._provider.reverse_geocode(lat=lat, lng=lng)
        except Exception:
            # Fallback gracefully to coordinate description on external provider failure
            return ReverseGeocodeResponse(
                success=True,
                message="Reverse geocoded with fallback provider",
                data=ReverseGeocodeResponseData(
                    formatted_address=f"Coordinates ({lat:.4f}, {lng:.4f})",
                    locality="Unknown",
                    administrative_area=None,
                    postal_code=None,
                    country="India",
                    latitude=lat,
                    longitude=lng,
                    source="fallback",
                ),
            )

        return ReverseGeocodeResponse(
            success=True,
            message="Address resolved successfully",
            data=ReverseGeocodeResponseData(
                formatted_address=result.formatted_address,
                locality=result.locality,
                administrative_area=result.administrative_area,
                postal_code=result.postal_code,
                country=result.country,
                latitude=lat,
                longitude=lng,
            ),
        )
