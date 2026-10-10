import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_reverse_geocode_success(client: AsyncClient) -> None:
    response = await client.get("/api/v1/location/reverse", params={"lat": 13.0827, "lng": 80.2707})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert data["data"]["latitude"] == 13.0827
    assert data["data"]["longitude"] == 80.2707
    assert "formatted_address" in data["data"]


@pytest.mark.asyncio
async def test_reverse_geocode_invalid_latitude(client: AsyncClient) -> None:
    response = await client.get("/api/v1/location/reverse", params={"lat": 95.0, "lng": 80.2707})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reverse_geocode_invalid_longitude(client: AsyncClient) -> None:
    response = await client.get("/api/v1/location/reverse", params={"lat": 13.0827, "lng": 185.0})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_forgot_password_and_otp_recovery_flow(client: AsyncClient) -> None:
    # 1. Register a test citizen
    reg_payload = {
        "email": "citizen.recovery@example.com",
        "phone": "+919876543210",
        "full_name": "Recovery Citizen",
        "password": "Password@123",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201

    # 2. Call forgot-password with email
    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"identifier": "citizen.recovery@example.com"},
    )
    assert forgot_resp.status_code == 200
    assert "message" in forgot_resp.json()

    # 3. Call forgot-password with non-existent email (enumeration resistance)
    ghost_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"identifier": "ghost.user@example.com"},
    )
    assert ghost_resp.status_code == 200
    assert "message" in ghost_resp.json()


@pytest.mark.asyncio
async def test_otp_verification_failure_and_security(client: AsyncClient) -> None:
    # Attempt verify-otp with invalid code
    bad_verify = await client.post(
        "/api/v1/auth/verify-otp",
        json={"identifier": "someone@example.com", "otp": "000000"},
    )
    assert bad_verify.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient) -> None:
    # Attempt reset-password with fake token
    bad_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"reset_token": "invalid_fake_reset_token_32_chars_long", "new_password": "NewPassword@123"},
    )
    assert bad_reset.status_code == 400
