from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema


class ReverseGeocodeResponseData(BaseSchema):
    formatted_address: str = Field(..., description="Full reverse-geocoded address")
    locality: str | None = Field(default=None, description="City, town, or village")
    administrative_area: str | None = Field(default=None, description="State, province, or division")
    postal_code: str | None = Field(default=None, description="Postal or PIN code")
    country: str = Field(default="India", description="Country name")
    latitude: float = Field(..., description="Requested latitude")
    longitude: float = Field(..., description="Requested longitude")
    source: Literal["provider", "fallback"] = Field(
        default="provider",
        description=(
            "'provider' — address resolved by geocoding service; "
            "'fallback' — provider unavailable, coordinate-only description used"
        ),
    )


class ReverseGeocodeResponse(BaseSchema):
    success: bool = Field(default=True)
    message: str = Field(default="Address resolved successfully")
    data: ReverseGeocodeResponseData
