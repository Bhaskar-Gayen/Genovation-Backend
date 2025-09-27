import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_success(app_client: tuple[object, AsyncClient]):
    app, client = app_client
    payload = {
        "mobile_number": "7000000001",
        "password": "StrongPass123!",
        "full_name": "Alice",
        "email": "alice@example.com"
    }
    resp = await client.post("/auth/signup", json=payload)
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["mobile_number"] == payload["mobile_number"]


@pytest.mark.asyncio
async def test_verify_otp_success(app_client: tuple[object, AsyncClient], db_session, monkeypatch):
    # Create a user in DB
    from app.models.user import User
    from app.utils import jwt as jwt_utils

    user = User(mobile_number="7111111111", password_hash="hash", full_name="Bob", email="bob@example.com", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Monkeypatch OTPService.verify_otp to succeed without Redis or throttling
    async def fake_verify(mobile_number: str, otp: str):
        return True
    monkeypatch.setattr("app.services.otp_service.OTPService.verify_otp", staticmethod(fake_verify))

    resp = await client.post("/auth/verify-otp", json={"mobile_number": user.mobile_number, "otp": "123456"})
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert body["data"]["user"]["mobile_number"] == user.mobile_number
