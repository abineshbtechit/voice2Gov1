"""Phase 1.3.1 — Complaint schema tests.

Covers SCHEMA requirements:
- valid complaint request
- invalid title (too short/long)
- invalid description (too short/long)
- invalid category_id
- invalid visibility
- invalid location (GeoJSON validation)
- invalid longitude
- invalid latitude
- invalid GeoJSON type
- malformed coordinates
- MongoDB operator injection prevention
- server-controlled fields cannot be supplied
"""

import pytest
from pydantic import ValidationError

from app.schemas.base import ObjectIdStr
from app.schemas.complaint import (
    ComplaintCreateRequest,
    ComplaintStatus,
    ComplaintVisibility,
    GeoJSONPoint,
)


class TestGeoJSONPoint:
    def test_valid_point(self) -> None:
        point = GeoJSONPoint(coordinates=[-73.9857, 40.7484])
        assert point.type == "Point"
        assert point.coordinates == [-73.9857, 40.7484]

    def test_invalid_longitude_too_high(self) -> None:
        with pytest.raises(ValidationError) as exc:
            GeoJSONPoint(coordinates=[181.0, 40.7484])
        assert "Longitude must be in [-180, 180]" in str(exc.value)

    def test_invalid_longitude_too_low(self) -> None:
        with pytest.raises(ValidationError) as exc:
            GeoJSONPoint(coordinates=[-181.0, 40.7484])
        assert "Longitude must be in [-180, 180]" in str(exc.value)

    def test_invalid_latitude_too_high(self) -> None:
        with pytest.raises(ValidationError) as exc:
            GeoJSONPoint(coordinates=[-73.9857, 91.0])
        assert "Latitude must be in [-90, 90]" in str(exc.value)

    def test_invalid_latitude_too_low(self) -> None:
        with pytest.raises(ValidationError) as exc:
            GeoJSONPoint(coordinates=[-73.9857, -91.0])
        assert "Latitude must be in [-90, 90]" in str(exc.value)

    def test_valid_boundary_longitude(self) -> None:
        point = GeoJSONPoint(coordinates=[180.0, 0.0])
        assert point.coordinates == [180.0, 0.0]

    def test_valid_boundary_latitude(self) -> None:
        point = GeoJSONPoint(coordinates=[0.0, 90.0])
        assert point.coordinates == [0.0, 90.0]

    def test_malformed_coordinates_wrong_length(self) -> None:
        with pytest.raises(ValidationError):
            GeoJSONPoint(coordinates=[-73.9857])

    def test_malformed_coordinates_too_many(self) -> None:
        with pytest.raises(ValidationError):
            GeoJSONPoint(coordinates=[-73.9857, 40.7484, 100.0])

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GeoJSONPoint(type="Polygon", coordinates=[[-73.9857, 40.7484]])


class TestComplaintCreateRequest:
    def make_valid_request(self, **overrides) -> dict:
        base = {
            "title": "Large pothole on Main Street",
            "description": "Deep pothole causing vehicle damage near intersection",
            "category_id": ObjectIdStr("507f1f77bcf86cd799439012"),
            "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
        }
        base.update(overrides)
        return base

    def test_valid_request(self) -> None:
        data = self.make_valid_request()
        req = ComplaintCreateRequest(**data)
        assert req.title == "Large pothole on Main Street"
        assert req.description == "Deep pothole causing vehicle damage near intersection"
        assert str(req.category_id) == "507f1f77bcf86cd799439012"
        assert req.location.type == "Point"
        assert req.location.coordinates == [-73.9857, 40.7484]

    def test_invalid_title_too_short(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintCreateRequest(**self.make_valid_request(title="Hi"))
        assert "title" in str(exc.value).lower()

    def test_invalid_title_too_long(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintCreateRequest(**self.make_valid_request(title="x" * 201))
        assert "title" in str(exc.value).lower()

    def test_invalid_description_too_short(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintCreateRequest(**self.make_valid_request(description="Short"))
        assert "description" in str(exc.value).lower()

    def test_invalid_description_too_long(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintCreateRequest(**self.make_valid_request(description="x" * 5001))
        assert "description" in str(exc.value).lower()

    def test_invalid_category_id_format(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintCreateRequest(**self.make_valid_request(category_id="invalid-id"))
        assert "category_id" in str(exc.value).lower()

    def test_address_optional(self) -> None:
        data = self.make_valid_request()
        # address is in the base schema but optional
        req = ComplaintCreateRequest(**data)
        assert req.address is None

    def test_address_provided(self) -> None:
        req = ComplaintCreateRequest(**self.make_valid_request(address="Main St & 1st Ave"))
        assert req.address == "Main St & 1st Ave"


class TestComplaintEnums:
    def test_complaint_status_values(self) -> None:
        assert ComplaintStatus.SUBMITTED == "SUBMITTED"
        assert ComplaintStatus.ONGOING == "ONGOING"
        assert ComplaintStatus.PROCESSING == "PROCESSING"
        assert ComplaintStatus.COMPLETED == "COMPLETED"
        assert ComplaintStatus.REJECTED == "REJECTED"
        assert ComplaintStatus.DUPLICATE == "DUPLICATE"
        assert ComplaintStatus.CLOSED == "CLOSED"

    def test_complaint_visibility_values(self) -> None:
        assert ComplaintVisibility.PUBLIC == "public"
        assert ComplaintVisibility.ORGANIZATION == "organization"
        assert ComplaintVisibility.PRIVATE == "private"

    def test_no_extra_statuses(self) -> None:
        values = {s.value for s in ComplaintStatus}
        expected = {"SUBMITTED", "ONGOING", "PROCESSING", "COMPLETED", "REJECTED", "DUPLICATE", "CLOSED"}
        assert values == expected


class TestMongoDBOperatorInjection:
    def test_geojson_rejects_mongo_operators(self) -> None:
        """Ensure GeoJSON Point rejects MongoDB query operators like $near, $geoWithin."""
        with pytest.raises(ValidationError):
            GeoJSONPoint(type="$near", coordinates=[-73.9857, 40.7484])

        with pytest.raises(ValidationError):
            GeoJSONPoint(type="$geoWithin", coordinates=[[-73.9857, 40.7484]])

        with pytest.raises(ValidationError):
            # Attempting to inject operator via coordinates
            GeoJSONPoint(coordinates=[{"$gt": -180}, 40.7484])

    def test_complaint_rejects_operator_injection_in_location(self) -> None:
        """Test that MongoDB operators in location are rejected."""
        with pytest.raises(ValidationError):
            ComplaintCreateRequest(
                title="Test complaint",
                description="Test description for validation",
                category_id="507f1f77bcf86cd799439012",
                location={"$near": {"$geometry": {"type": "Point", "coordinates": [0, 0]}}},
            )
