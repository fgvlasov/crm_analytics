def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "X-Request-Id" in response.headers


def test_features_all_disabled_by_default(client):
    response = client.get("/api/v1/features")
    assert response.status_code == 200
    features = response.json()["features"]
    assert features == {
        "odoo_connector": False,
        "fast_ai": False,
        "deep_research": False,
        "smart_rpt": False,
        "web_news_collectors": False,
    }
