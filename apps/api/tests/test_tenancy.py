def _login(client, email: str, password: str, tenant_slug: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "tenant_slug": tenant_slug},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_cannot_read_other_tenant(client, demo_tenant, other_tenant):
    other, _ = other_tenant
    token = _login(client, "admin@coldex-demo.example", "ChangeMeDemo123!", "coldex-demo")
    response = client.get(
        f"/api/v1/tenants/{other.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_secrets_never_return_plaintext(client, demo_tenant):
    token = _login(client, "admin@coldex-demo.example", "ChangeMeDemo123!", "coldex-demo")
    create = client.post(
        "/api/v1/tenants/current/secrets",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "demo-key", "purpose": "test", "value": "super-secret-value"},
    )
    assert create.status_code == 201
    body = create.json()
    assert "ciphertext" not in body
    assert "value" not in body
    assert body["name"] == "demo-key"

    listed = client.get(
        "/api/v1/tenants/current/secrets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert all("ciphertext" not in item for item in listed.json())


def test_login_does_not_cross_tenants(client, demo_tenant, other_tenant):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@coldex-demo.example",
            "password": "ChangeMeDemo123!",
            "tenant_slug": "other-co",
        },
    )
    assert response.status_code == 401
