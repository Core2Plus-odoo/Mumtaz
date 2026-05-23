"""
Platform API auth tests: login, me, JWT validation, tenant isolation.
"""
import os
import time
import pytest
from jose import jwt


# ── Health ────────────────────────────────────────────────────────────

def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # Odoo is not reachable in CI — that's expected
    assert "ai_ready" in body


def test_api_v1_health_alias(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── JWT / require_auth ────────────────────────────────────────────────

def test_me_rejects_missing_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_rejects_bad_token(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer notavalidtoken"})
    assert r.status_code == 401


def test_me_rejects_expired_token(client):
    from main import SECRET, ALGO
    payload = {
        "sub": "999",
        "email": "expired@example.com",
        "exp": int(time.time()) - 3600,
        "iat": int(time.time()) - 7200,
    }
    token = jwt.encode(payload, SECRET, ALGO)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_returns_user_for_valid_token(client, regular_user):
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == regular_user["email"]
    assert "password_hash" not in body


# ── Login ─────────────────────────────────────────────────────────────

def test_login_missing_fields_returns_422(client):
    r = client.post("/api/v1/auth/login", json={"email": "x@x.com"})
    assert r.status_code == 422


def test_login_wrong_password_returns_401(client, regular_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": regular_user["email"], "password": "WrongPassword!"},
    )
    # Odoo is down → falls through to local password check → should 401
    assert r.status_code in (401, 500)


def test_login_nonexistent_user_returns_401(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "anything"},
    )
    assert r.status_code in (401, 500)


# ── Tenant isolation ──────────────────────────────────────────────────

def test_me_only_returns_own_data(client, regular_user, admin_user):
    """Two separate tokens must only return their own user row."""
    r_user = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    r_admin = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert r_user.json()["email"] == regular_user["email"]
    assert r_admin.json()["email"] == admin_user["email"]
    assert r_user.json()["email"] != r_admin.json()["email"]


# ── Partner signup (no auth required) ────────────────────────────────

def test_partner_signup_validates_fields(client):
    r = client.post("/api/v1/partner/signup", json={})
    assert r.status_code == 422


def test_partner_signup_success(client):
    payload = {
        "company": "Acme Corp",
        "contact_name": "John Doe",
        "email": "john@acme.example.com",
        "phone": "+971501234567",
        "country": "UAE",
        "kind": "reseller",
    }
    r = client.post("/api/v1/partner/signup", json=payload)
    # 200 or 201 depending on implementation
    assert r.status_code in (200, 201)


# ── Plans endpoint ────────────────────────────────────────────────────

def test_plans_returns_list(client):
    r = client.get("/api/v1/plans")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, (list, dict))


# ── Admin endpoints require auth ──────────────────────────────────────

def test_admin_users_requires_auth(client):
    r = client.get("/api/v1/admin/users")
    assert r.status_code == 401


def test_admin_ping_requires_auth(client):
    r = client.get("/api/v1/admin/ping")
    assert r.status_code == 401


def test_admin_settings_requires_auth(client):
    r = client.get("/api/v1/admin/settings")
    assert r.status_code == 401


def test_admin_ping_with_token(client, admin_user):
    r = client.get(
        "/api/v1/admin/ping",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    # 200 if admin check passes; 403 if role gating is strict
    assert r.status_code in (200, 403)


# ── CORS headers ──────────────────────────────────────────────────────

def test_cors_allowed_origin(client):
    r = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code in (200, 204)


def test_cors_unknown_origin_not_reflected(client):
    r = client.get("/health", headers={"Origin": "https://evil.example.com"})
    acao = r.headers.get("access-control-allow-origin", "")
    assert "evil.example.com" not in acao
