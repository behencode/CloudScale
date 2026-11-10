import io

from PIL import Image

from app.errors import ProviderError
from conftest import register


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (12, 8), (18, 92, 72)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_reports_local_mode(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["auth_mode"] == "local"
    assert body["database_backend"] == "sqlite"
    assert body["description_provider"] == "local"
    assert body["category_provider"] == "local"
    assert body["warnings"] == []


def test_openapi_documents_bearer_auth(client):
    schema = client.app.openapi()
    assert schema["components"]["securitySchemes"]["BearerAuth"]["type"] == "http"
    assert {"BearerAuth": []} in schema["paths"]["/api/auth/me"]["get"]["security"]


def test_register_login_and_profile(client):
    headers, user = register(client)
    assert user["name"] == "Ada Lovelace"
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "ada@campus.edu"

    login = client.post("/api/auth/login", json={"email": "ada@campus.edu", "password": "correct-horse"})
    assert login.status_code == 200
    assert login.json()["auth_mode"] == "local"

    bad = client.post("/api/auth/login", json={"email": "ada@campus.edu", "password": "wrong-password"})
    assert bad.status_code == 401

    updated = client.patch(
        "/api/auth/me",
        headers=headers,
        json={"campus": "South Campus", "bio": "Library volunteer"},
    )
    assert updated.status_code == 200
    assert updated.json()["campus"] == "South Campus"
    assert updated.json()["bio"] == "Library volunteer"

    duplicate = client.post(
        "/api/auth/register",
        json={"email": "ada@campus.edu", "name": "Ada", "password": "correct-horse", "campus": ""},
    )
    assert duplicate.status_code == 409


def test_listing_crud_search_and_ownership(client):
    ada, _user = register(client)
    grace, _other = register(client, email="grace@campus.edu", name="Grace Hopper")
    created = client.post(
        "/api/listings",
        headers=ada,
        json={
            "title": "Lost keys near the library",
            "description": "A set of keys with a blue tag was lost near the main library entrance.",
            "category": "lost-and-found",
            "intent": "lost",
            "location": "Main library",
            "contact": "ada@campus.edu",
        },
    )
    assert created.status_code == 201, created.text
    listing = created.json()["listing"]
    assert created.json()["notification_warning"] is None
    listing_id = listing["id"]

    fetched = client.get(f"/api/listings/{listing_id}")
    assert fetched.status_code == 200
    assert fetched.json()["owner_name"] == "Ada Lovelace"

    searched = client.get("/api/listings", params={"q": "blue tag", "category": "lost-and-found"})
    assert searched.status_code == 200
    assert [item["id"] for item in searched.json()] == [listing_id]

    housing = client.get("/api/listings", params={"category": "housing"})
    assert housing.json() == []

    edited = client.patch(
        f"/api/listings/{listing_id}",
        headers=ada,
        json={"status": "resolved", "location": "Front desk"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "resolved"
    assert edited.json()["location"] == "Front desk"

    forbidden = client.patch(
        f"/api/listings/{listing_id}",
        headers=grace,
        json={"title": "Taken over"},
    )
    assert forbidden.status_code == 403
    assert client.delete(f"/api/listings/{listing_id}", headers=grace).status_code == 403
    assert client.delete(f"/api/listings/{listing_id}", headers=ada).status_code == 204
    assert client.get(f"/api/listings/{listing_id}").status_code == 404


def test_validation_and_auth_required(client):
    response = client.post(
        "/api/listings",
        json={
            "title": "No",
            "description": "too short",
            "category": "not-real",
        },
    )
    assert response.status_code == 401
    ada, _user = register(client)
    invalid = client.post(
        "/api/listings",
        headers=ada,
        json={"title": "Yo", "description": "short", "category": "sports"},
    )
    assert invalid.status_code == 422


def test_image_upload_and_local_assistants(client):
    headers, _user = register(client)
    upload = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("keys.png", png_bytes(), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    image_key = upload.json()["image_key"]
    assert upload.json()["image_url"] == f"/uploads/{image_key}"
    stored = client.get(upload.json()["image_url"])
    assert stored.status_code == 200
    assert stored.headers["content-type"].startswith("image/")

    created = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Found blue water bottle",
            "description": "A blue bottle was found on the bench outside the science block.",
            "category": "lost-and-found",
            "intent": "found",
            "image_key": image_key,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["listing"]["image_key"] == image_key
    listing_id = created.json()["listing"]["id"]
    removed = client.delete(f"/api/listings/{listing_id}", headers=headers)
    assert removed.status_code == 204
    assert client.get(f"/uploads/{image_key}").status_code == 404
    assert client.app.state.repo.get_upload(image_key) is None

    notes = client.get("/api/notifications", headers=headers)
    assert notes.status_code == 200
    assert "Lambda were not called" in notes.json()[0]["message"]
    assert notes.json()[0]["channel"] == "local-database"

    rejected = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert rejected.status_code == 400

    description = client.post(
        "/api/listings/assist/description",
        headers=headers,
        json={"title": "Spare desk lamp", "category": "community", "details": "Works, needs a bulb."},
    )
    assert description.status_code == 200, description.text
    body = description.json()
    assert body["provider"] == "local-template"
    assert "Amazon Bedrock was not called" in body["notice"]
    assert "Spare desk lamp" in body["description"]

    category = client.post(
        "/api/listings/assist/category",
        headers=headers,
        json={"title": "Lost my keys in the library", "details": "Blue tag"},
    )
    predicted = category.json()
    assert category.status_code == 200
    assert predicted["category"] == "lost-and-found"
    assert predicted["provider"] == "local-keyword-classifier"
    assert "SageMaker was not called" in predicted["notice"]


def test_provider_errors_are_not_replaced(client):
    headers, _user = register(client)

    class Broken:
        def generate(self, **_kwargs):
            raise ProviderError("Amazon Bedrock request failed: AccessDeniedException: denied")

    client.app.state.description_service = Broken()
    response = client.post(
        "/api/listings/assist/description",
        headers=headers,
        json={"title": "Spare desk lamp", "category": "community", "details": ""},
    )
    assert response.status_code == 502
    assert "AccessDeniedException" in response.json()["detail"]
    assert "local development template" not in response.text


def test_cognito_token_stores_profile_by_user_id(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.auth.verify_cognito_token",
        lambda token, **_kwargs: {"id": "cognito-sub", "email": "ada@campus.edu", "name": "Ada Lovelace"},
    )
    client.app.state.settings.auth_mode = "cognito"
    try:
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer signed-id-token"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["id"] == "cognito-sub"
        assert body["email"] == "ada@campus.edu"
        again = client.get("/api/auth/me", headers={"Authorization": "Bearer signed-id-token"})
        assert again.status_code == 200
        assert again.json()["id"] == "cognito-sub"
    finally:
        client.app.state.settings.auth_mode = "local"


def test_cognito_mode_disables_local_login(client):
    client.app.state.settings.auth_mode = "cognito"
    try:
        response = client.post(
            "/api/auth/login",
            json={"email": "ada@campus.edu", "password": "correct-horse"},
        )
        assert response.status_code == 400
        assert "Cognito" in response.json()["detail"]
        register_response = client.post(
            "/api/auth/register",
            json={"email": "ada@campus.edu", "name": "Ada", "password": "correct-horse"},
        )
        assert register_response.status_code == 400
    finally:
        client.app.state.settings.auth_mode = "local"


def test_mine_filter(client):
    ada, _user = register(client)
    grace, _other = register(client, email="grace@campus.edu", name="Grace Hopper")
    client.post(
        "/api/listings",
        headers=ada,
        json={
            "title": "Calculus textbook",
            "description": "Eighth edition calculus textbook, some pencil notes inside.",
            "category": "textbooks",
            "intent": "offer",
        },
    )
    client.post(
        "/api/listings",
        headers=grace,
        json={
            "title": "Room near the station",
            "description": "A single room is available from next month near the station.",
            "category": "housing",
            "intent": "offer",
        },
    )
    mine = client.get("/api/listings", params={"mine": "true"}, headers=ada)
    assert mine.status_code == 200
    assert len(mine.json()) == 1
    assert mine.json()[0]["title"] == "Calculus textbook"


def test_edit_listing_can_clear_photo_and_removes_upload_record(client):
    headers, _user = register(client)
    upload = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("keys.png", png_bytes(), "image/png")},
    )
    image_key = upload.json()["image_key"]
    created = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Found blue water bottle",
            "description": "A blue bottle was found outside the science block.",
            "category": "lost-and-found",
            "intent": "found",
            "image_key": image_key,
        },
    )
    listing_id = created.json()["listing"]["id"]

    updated = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"clear_image": True},
    )

    assert updated.status_code == 200
    assert updated.json()["image_key"] is None
    assert client.get(f"/uploads/{image_key}").status_code == 404
    assert client.app.state.repo.get_upload(image_key) is None
