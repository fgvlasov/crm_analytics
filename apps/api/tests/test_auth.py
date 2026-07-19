def test_login_success(client, demo_tenant):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@coldex-demo.example",
            "password": "ChangeMeDemo123!",
            "tenant_slug": "coldex-demo",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]


def test_login_wrong_password(client, demo_tenant):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@coldex-demo.example",
            "password": "WrongPassword1!",
            "tenant_slug": "coldex-demo",
        },
    )
    assert response.status_code == 401


def test_me_requires_auth(client, demo_tenant):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_token(client, demo_tenant):
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@coldex-demo.example",
            "password": "ChangeMeDemo123!",
            "tenant_slug": "coldex-demo",
        },
    )
    token = login.json()["access_token"]
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "admin@coldex-demo.example"
    assert body["tenant"]["slug"] == "coldex-demo"


def test_refresh_token(client, demo_tenant):
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@coldex-demo.example",
            "password": "ChangeMeDemo123!",
            "tenant_slug": "coldex-demo",
        },
    )
    refresh = login.json()["refresh_token"]
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert response.status_code == 200
    assert response.json()["access_token"]
