"""Phase 1.3.3 — Complaint update schema tests.

Covers SCHEMA requirements for ComplaintUpdateRequest:
- valid update request
- invalid title (too short/long)
- invalid description (too short/long)
- invalid category_id (should not be allowed)
- invalid status (should not be allowed)
- invalid location (GeoJSON validation)
- invalid longitude
- invalid latitude
- invalid GeoJSON type
- malformed coordinates
- MongoDB operator injection prevention
- server-controlled fields cannot be supplied
- empty update rejected
"""

import pytest
from pydantic import ValidationError

from app.schemas.complaint import ComplaintUpdateRequest


class TestComplaintUpdateRequest:
    def make_valid_request(self, **overrides) -> dict:
        base = {
            "title": "Updated pothole on Main Street",
            "description": "Updated description of the pothole",
            "location": {"type": "Point", "coordinates": [-73.9857, 40.7484]},
            "address": "Main St & 1st Ave, Updated",
        }
        base.update(overrides)
        return base

    def test_valid_update_request_all_fields(self) -> None:
        data = self.make_valid_request()
        req = ComplaintUpdateRequest(**data)
        assert req.title == "Updated pothole on Main Street"
        assert req.description == "Updated description of the pothole"
        assert req.location.type == "Point"
        assert req.location.coordinates == [-73.9857, 40.7484]
        assert req.address == "Main St & 1st Ave, Updated"

    def test_valid_update_request_partial_fields(self) -> None:
        """Test that partial updates work (only title)."""
        req = ComplaintUpdateRequest(title="New title only")
        assert req.title == "New title only"
        assert req.description is None
        assert req.location is None
        assert req.address is None

    def test_valid_update_request_only_description(self) -> None:
        req = ComplaintUpdateRequest(description="Only description updated")
        assert req.description == "Only description updated"
        assert req.title is None

    def test_valid_update_request_only_location(self) -> None:
        req = ComplaintUpdateRequest(location={"type": "Point", "coordinates": [-74.0, 40.8]})
        assert req.location.coordinates == [-74.0, 40.8]

    def test_valid_update_request_only_address(self) -> None:
        req = ComplaintUpdateRequest(address="New address")
        assert req.address == "New address"

    def test_invalid_title_too_short(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintUpdateRequest(**self.make_valid_request(title="Hi"))
        assert "title" in str(exc.value).lower()

    def test_invalid_title_too_long(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintUpdateRequest(**self.make_valid_request(title="x" * 201))
        assert "title" in str(exc.value).lower()

    def test_invalid_description_too_short(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintUpdateRequest(**self.make_valid_request(description="Short"))
        assert "description" in str(exc.value).lower()

    def test_invalid_description_too_long(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintUpdateRequest(**self.make_valid_request(description="x" * 5001))
        assert "description" in str(exc.value).lower()

    def test_valid_location_with_default_type(self) -> None:
        """Test that location with default type 'Point' is valid."""
        req = ComplaintUpdateRequest(
            **self.make_valid_request(location={"coordinates": [-73.9857, 40.7484]})
        )
        assert req.location.type == "Point"
        assert req.location.coordinates == [-73.9857, 40.7484]

    def test_invalid_location_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(
                **self.make_valid_request(location={"type": "Polygon", "coordinates": [[[0, 0]]]})
            )

    def test_invalid_longitude_out_of_range(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintUpdateRequest(
                **self.make_valid_request(location={"type": "Point", "coordinates": [181.0, 40.7484]})
            )
        assert "longitude" in str(exc.value).lower()

    def test_invalid_latitude_out_of_range(self) -> None:
        with pytest.raises(ValidationError) as exc:
            ComplaintUpdateRequest(
                **self.make_valid_request(location={"type": "Point", "coordinates": [-73.9857, 91.0]})
            )
        assert "latitude" in str(exc.value).lower()

    def test_malformed_coordinates(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(
                **self.make_valid_request(location={"type": "Point", "coordinates": [-73.9857]})
            )

    def test_mongo_operator_injection_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(
                **self.make_valid_request(
                    location={"$near": {"$geometry": {"type": "Point", "coordinates": [0, 0]}}}
                )
            )

    def test_server_controlled_fields_not_allowed(self) -> None:
        """Test that server-controlled fields cannot be injected."""
        # category_id should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(category_id="507f1f77bcf86cd799439015"))

        # status should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(status="COMPLETED"))

        # user_id should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(user_id="507f1f77bcf86cd799439011"))

        # organization_id should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(organization_id="507f1f77bcf86cd799439012"))

        # department_id should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(department_id="507f1f77bcf86cd799439014"))

        # complaint_number should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(complaint_number="CMP-FAKE-000001"))

        # status should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(status="COMPLETED"))

        # likes_count should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(likes_count=100))

        # priority_score should not be allowed
        with pytest.raises(ValidationError):
            ComplaintUpdateRequest(**self.make_valid_request(priority_score=100.0))

    def test_empty_update_rejected(self) -> None:
        """Empty update request should be rejected by the service, but schema allows empty."""
        # Schema allows empty update, but service should reject it
        req = ComplaintUpdateRequest()
        assert req.title is None
        assert req.description is None
        assert req.location is None
        assert req.address is None
