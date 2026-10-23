from app import app, get_discount


def client():
    return app.test_client()


def test_health_ok():
    r = client().get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_home_ok():
    r = client().get("/")
    assert r.status_code == 200


def test_existing_user():
    r = client().get("/users/1")
    assert r.status_code == 200
    assert r.get_json()["name"] == "Aman"


def test_missing_user_returns_404():
    r = client().get("/users/99")
    assert r.status_code == 404


def test_discount_calculation():
    assert get_discount(100, 10) == 90
    assert get_discount(200, 50) == 100
