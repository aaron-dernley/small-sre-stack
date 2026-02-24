"""Integration tests for the /users and /user endpoints."""

import io

# ---------------------------------------------------------------------------
# GET /users
# ---------------------------------------------------------------------------


def test_list_users_empty(client):
    response = client.get("/users")
    assert response.status_code == 200
    assert response.json() == []


def test_list_users_after_create(client, sample_image):
    client.post(
        "/user",
        data={"name": "Alice", "email": "alice@example.com"},
        files={"avatar": ("avatar.png", io.BytesIO(sample_image), "image/png")},
    )
    response = client.get("/users")
    assert response.status_code == 200
    users = response.json()
    assert len(users) == 1
    assert users[0]["name"] == "Alice"
    assert users[0]["email"] == "alice@example.com"
    assert users[0]["avatar_url"].endswith(".png")


def test_list_users_multiple(client, sample_image):
    for i, name in enumerate(["Alice", "Bob", "Carol"]):
        client.post(
            "/user",
            data={"name": name, "email": f"user{i}@example.com"},
            files={"avatar": ("avatar.png", io.BytesIO(sample_image), "image/png")},
        )
    response = client.get("/users")
    assert response.status_code == 200
    assert len(response.json()) == 3


# ---------------------------------------------------------------------------
# POST /user
# ---------------------------------------------------------------------------


def test_create_user_success(client, sample_image):
    response = client.post(
        "/user",
        data={"name": "Test User", "email": "test@example.com"},
        files={"avatar": ("photo.png", io.BytesIO(sample_image), "image/png")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Test User"
    assert body["email"] == "test@example.com"
    assert "avatar_url" in body
    assert body["avatar_url"].endswith(".png")


def test_create_user_jpeg(client, sample_image):
    response = client.post(
        "/user",
        data={"name": "JPEG User", "email": "jpeg@example.com"},
        files={"avatar": ("photo.jpg", io.BytesIO(sample_image), "image/jpeg")},
    )
    assert response.status_code == 201
    assert response.json()["avatar_url"].endswith(".jpg")


def test_create_user_invalid_content_type(client, sample_image):
    response = client.post(
        "/user",
        data={"name": "Bad Actor", "email": "bad@example.com"},
        files={"avatar": ("shell.sh", io.BytesIO(b"#!/bin/bash"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_create_user_missing_name(client, sample_image):
    response = client.post(
        "/user",
        data={"email": "noname@example.com"},
        files={"avatar": ("avatar.png", io.BytesIO(sample_image), "image/png")},
    )
    assert response.status_code == 422


def test_create_user_missing_email(client, sample_image):
    response = client.post(
        "/user",
        data={"name": "No Email"},
        files={"avatar": ("avatar.png", io.BytesIO(sample_image), "image/png")},
    )
    assert response.status_code == 422


def test_create_user_invalid_email(client, sample_image):
    response = client.post(
        "/user",
        data={"name": "Bad Email", "email": "not-an-email"},
        files={"avatar": ("avatar.png", io.BytesIO(sample_image), "image/png")},
    )
    assert response.status_code == 422


def test_create_user_missing_avatar(client):
    response = client.post(
        "/user",
        data={"name": "No Avatar", "email": "noavatar@example.com"},
    )
    assert response.status_code == 422


def test_avatar_url_stored_in_dynamodb(client, sample_image, aws_resources):
    """Avatar URL written by POST /user must match what GET /users returns."""
    post_resp = client.post(
        "/user",
        data={"name": "Verify", "email": "verify@example.com"},
        files={"avatar": ("img.png", io.BytesIO(sample_image), "image/png")},
    )
    assert post_resp.status_code == 201
    created_url = post_resp.json()["avatar_url"]

    # Confirm the URL is consistent via the list endpoint
    get_resp = client.get("/users")
    listed = next(u for u in get_resp.json() if u["email"] == "verify@example.com")
    assert listed["avatar_url"] == created_url


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
