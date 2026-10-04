"""Role checks use isolated sessions and never modify real settings."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api import create_app


class AuthTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "CHAINGUARD_ADMIN_USERNAME": "admin",
            "CHAINGUARD_ADMIN_PASSWORD": "test-password",
            "CHAINGUARD_USER_USERNAME": "user",
            "CHAINGUARD_USER_PASSWORD": "user-password",
        })
        env.start()
        self.addCleanup(env.stop)
        provider = patch("src.api.set_provider", return_value="OpenAI")
        provider.start()
        self.addCleanup(provider.stop)
        self.app = create_app()
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def login(self):
        return self.client.post("/api/auth/login", json={
            "username": "admin", "password": "test-password",
        })

    def test_user_can_chat_but_all_settings_routes_are_blocked(self):
        self.assertEqual(self.client.get("/api/auth/me").json(), {"authenticated": False, "role": None, "username": None})
        self.assertEqual(self.client.post("/api/chats").status_code, 201)
        for path in ("detector", "api-keys"):
            for method in ("GET", "POST"):
                response = self.client.request(method, f"/api/settings/{path}", json={})
                self.assertEqual(response.status_code, 401)

    def test_login_logout_preserves_chat_and_revokes_token(self):
        response = self.login()
        chat = self.client.post("/api/chats").json()["id"]
        self.assertEqual(response.status_code, 200)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        token = self.client.cookies.get("chainguard_auth")
        self.assertEqual(self.client.get("/api/auth/me").json(), {"authenticated": True, "role": "admin", "username": "admin"})
        self.assertEqual(self.client.get("/api/settings/api-keys").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout").json(), {"authenticated": False, "role": None, "username": None})
        self.assertEqual(self.client.get(f"/api/chats/{chat}").status_code, 404)
        self.assertNotIn(token, self.app.state.auth_sessions)
        self.assertEqual(self.client.get("/api/settings/api-keys").status_code, 401)

    def test_wrong_password_expiry_and_session_rotation(self):
        response = self.client.post("/api/auth/login", json={
            "username": "admin", "password": "wrong",
        })
        self.assertEqual(response.status_code, 401)
        self.login()
        old_token = self.client.cookies.get("chainguard_auth")
        self.login()
        self.assertNotIn(old_token, self.app.state.auth_sessions)
        token = self.client.cookies.get("chainguard_auth")
        self.app.state.auth_sessions[token]["expires_at"] = 0
        self.assertEqual(self.client.get("/api/auth/me").json(), {"authenticated": False, "role": None, "username": None})
        self.assertEqual(self.client.get("/api/settings/detector").status_code, 401)

    def test_user_settings_and_account_chat_isolation(self):
        self.login()
        chat = self.client.post("/api/chats").json()["id"]
        self.client.post("/api/auth/logout")
        response = self.client.post("/api/auth/login", json={
            "username": "user", "password": "user-password",
        })
        self.assertEqual(response.json()["role"], "user")
        self.assertEqual(self.client.get("/api/settings/api-keys").status_code, 200)
        self.assertEqual(self.client.get(f"/api/chats/{chat}").status_code, 404)
        self.client.post("/api/auth/logout")
        self.login()
        self.assertEqual(self.client.get(f"/api/chats/{chat}").status_code, 200)
