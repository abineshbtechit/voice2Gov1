from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class ReverseGeocodeResult(BaseModel):
    formatted_address: str = Field(..., description="Full human-readable address")
    locality: str | None = Field(default=None, description="City, town, or village")
    administrative_area: str | None = Field(default=None, description="State, province, or region")
    postal_code: str | None = Field(default=None, description="Postal or PIN code")
    country: str = Field(default="India", description="Country name")


class GeocodingProvider(ABC):
    """Abstract base class for reverse geocoding services."""

    @abstractmethod
    async def reverse_geocode(self, lat: float, lng: float) -> ReverseGeocodeResult:
        """Reverse geocode coordinates into a structured address."""
        raise NotImplementedError


class MockGeocodingProvider(GeocodingProvider):
    """Deterministic mock geocoding provider for testing and offline development."""

    def __init__(self) -> None:
        self.call_count: int = 0
        self.fail_mode: bool = False
        self.custom_lookup: dict[tuple[float, float], ReverseGeocodeResult] = {}

    async def reverse_geocode(self, lat: float, lng: float) -> ReverseGeocodeResult:
        self.call_count += 1
        if self.fail_mode:
            raise RuntimeError("Mock geocoding service unavailable")

        # Round to 3 decimal places for lookup matching
        key = (round(lat, 3), round(lng, 3))
        if key in self.custom_lookup:
            return self.custom_lookup[key]

        return ReverseGeocodeResult(
            formatted_address=f"Location near {lat:.4f}, {lng:.4f}, Ward 12, Civic Zone",
            locality="Civic Center",
            administrative_area="State Division",
            postal_code="600001",
            country="India",
        )
