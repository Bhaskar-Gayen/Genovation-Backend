import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me_requires_auth(app_client: tuple[object, AsyncClient]):
    app, client = app_client
    resp = await client.get("/user/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_and_update_me_success(app_client: tuple[object, AsyncClient], test_user_token):
    app, client = app_client
    token, user_info = test_user_token

    headers = {"Authorization": f"Bearer {token}"}

    # Get profile
    resp = await client.get("/user/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["mobile_number"] == user_info["mobile_number"]

    # Update profile
    new_name = "Updated Name"
    new_email = "updated@example.com"
    resp2 = await client.put(
        "/user/me",
        headers=headers,
        json={"full_name": new_name, "email": new_email},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["success"] is True
    assert data2["data"]["full_name"] == new_name
    assert data2["data"]["email"] == new_email
