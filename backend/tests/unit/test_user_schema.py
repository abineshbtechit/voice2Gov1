"""Phase 1.2.1 — user schema validation tests (authoritative SRS rules).

Covers the SCHEMA requirements:
- valid registration payload
- invalid email / phone / role / status rejected
- organization/department requirements for org-scoped roles (SRS validation rules)
"""

import pytest
from pydantic import ValidationError

from app.schemas.base import ObjectIdStr
from app.schemas.user import (
    UserBase,
    UserRegisterRequest,
    UserResponse,
    UserRole,
    UserStatus,
)

VALID_ORG_ID = "507f1f77bcf86cd799439011"
VALID_DEPT_ID = "507f191e810c19729de860ea"
ORG = ObjectIdStr(VALID_ORG_ID)
DEPT = ObjectIdStr(VALID_DEPT_ID)


class TestUserRegisterRequest:
    def test_valid_payload(self) -> None:
        payload = UserRegisterRequest(
            email="citizen@example.com",
            phone="+15551234567",
            full_name="Jane Citizen",
            password="SecurePass123!",
        )
        assert payload.email == "citizen@example.com"
        assert payload.phone == "+15551234567"
        assert payload.full_name == "Jane Citizen"

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="not-an-email",
                phone="+15551234567",
                full_name="Jane Citizen",
                password="SecurePass123!",
            )

    def test_invalid_phone_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="citizen@example.com",
                phone="12345",  # not E.164 (no leading +)
                full_name="Jane Citizen",
                password="SecurePass123!",
            )

    def test_phone_requires_e164_plus_prefix(self) -> None:
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="citizen@example.com",
                phone="+0123456789",  # leading zero country code invalid
                full_name="Jane Citizen",
                password="SecurePass123!",
            )

    def test_password_min_length_enforced(self) -> None:
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="citizen@example.com",
                phone="+15551234567",
                full_name="Jane Citizen",
                password="Ab1!xyz",  # 7 chars
            )

    def test_password_max_length_enforced(self) -> None:
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="citizen@example.com",
                phone="+15551234567",
                full_name="Jane Citizen",
                password="A" * 126 + "a1!",  # 129 chars
            )

    def test_full_name_required_and_bounded(self) -> None:
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="citizen@example.com",
                phone="+15551234567",
                full_name="",
                password="SecurePass123!",
            )


class TestRoleAndStatusEnums:
    def test_valid_role_accepted(self) -> None:
        user = UserBase(
            email="a@example.com",
            phone="+15551234567",
            full_name="A",
            role=UserRole.CITIZEN,
            status=UserStatus.ACTIVE,
        )
        assert user.role == UserRole.CITIZEN

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserBase(
                email="a@example.com",
                phone="+15551234567",
                full_name="A",
                role="superuser",
            )

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserBase(
                email="a@example.com",
                phone="+15551234567",
                full_name="A",
                status="bogus",
            )

    def test_all_documented_roles_exist(self) -> None:
        assert {r.value for r in UserRole} == {
            "citizen",
            "organization_staff",
            "organization_admin",
            "admin",
        }

    def test_all_documented_statuses_exist(self) -> None:
        values = {s.value for s in UserStatus}
        assert {"active", "inactive", "suspended", "pending_verification", "locked"} <= values


class TestOrganizationScopeValidation:
    """SRS: organization_id required for non-citizen roles; department_id for staff."""

    def test_citizen_does_not_require_organization(self) -> None:
        user = UserBase(
            email="citizen@example.com",
            phone="+15551234567",
            full_name="Citizen",
            role=UserRole.CITIZEN,
        )
        assert user.organization_id is None

    def test_organization_staff_requires_organization_id(self) -> None:
        with pytest.raises(ValidationError):
            UserBase(
                email="staff@example.com",
                phone="+15551234567",
                full_name="Staff",
                role=UserRole.ORGANIZATION_STAFF,
            )

    def test_organization_staff_requires_department_id(self) -> None:
        with pytest.raises(ValidationError):
            UserBase(
                email="staff@example.com",
                phone="+15551234567",
                full_name="Staff",
                role=UserRole.ORGANIZATION_STAFF,
                organization_id=ORG,
            )

    def test_organization_staff_with_org_and_department_valid(self) -> None:
        user = UserBase(
            email="staff@example.com",
            phone="+15551234567",
            full_name="Staff",
            role=UserRole.ORGANIZATION_STAFF,
            organization_id=ORG,
            department_id=DEPT,
        )
        assert user.organization_id == VALID_ORG_ID
        assert user.department_id == VALID_DEPT_ID

    def test_organization_admin_requires_organization_id(self) -> None:
        with pytest.raises(ValidationError):
            UserBase(
                email="admin@example.com",
                phone="+15551234567",
                full_name="Admin",
                role=UserRole.ORGANIZATION_ADMIN,
            )

    def test_organization_admin_with_organization_valid(self) -> None:
        user = UserBase(
            email="admin@example.com",
            phone="+15551234567",
            full_name="Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=ORG,
        )
        assert user.organization_id == VALID_ORG_ID


class TestUserResponseSchema:
    def test_response_has_no_password_fields(self) -> None:
        assert "password" not in UserResponse.model_fields
        assert "password_hash" not in UserResponse.model_fields

    def test_response_serialises_without_credentials(self) -> None:
        from datetime import datetime

        response = UserResponse(
            id=ORG,
            email="a@example.com",
            phone="+15551234567",
            full_name="A",
            role=UserRole.CITIZEN,
            status=UserStatus.ACTIVE,
            is_verified=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        dumped = response.model_dump()
        assert "password" not in dumped
        assert "password_hash" not in dumped
