import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chatroom_crud_flow(app_client: tuple[object, AsyncClient], test_user_token):
    app, client = app_client
    token, _ = test_user_token
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    payload = {"title": "My Room", "description": "Test room"}
    resp_create = await client.post("/chatroom/", headers=headers, json=payload)
    assert resp_create.status_code in (200, 201)
    body_create = resp_create.json()
    assert body_create["success"] is True
    chatroom = body_create["data"]
    chatroom_id = chatroom["id"]

    # List
    resp_list = await client.get("/chatroom/", headers=headers)
    assert resp_list.status_code == 200
    body_list = resp_list.json()
    assert body_list["success"] is True
    assert body_list["data"]["total"] >= 1

    # Get details (with messages pagination)
    resp_get = await client.get(f"/chatroom/{chatroom_id}", headers=headers)
    assert resp_get.status_code == 200
    body_get = resp_get.json()
    assert body_get["success"] is True
    assert body_get["data"]["chatroom"]["id"] == chatroom_id

    # Update
    update_payload = {"title": "Updated Room"}
    resp_update = await client.put(f"/chatroom/{chatroom_id}", headers=headers, json=update_payload)
    assert resp_update.status_code == 200
    body_update = resp_update.json()
    assert body_update["success"] is True
    assert body_update["data"]["title"] == "Updated Room"

    # Delete
    resp_delete = await client.delete(f"/chatroom/{chatroom_id}", headers=headers)
    assert resp_delete.status_code == 204

    # After delete, get should 404
    resp_get_404 = await client.get(f"/chatroom/{chatroom_id}", headers=headers)
    assert resp_get_404.status_code == 404
