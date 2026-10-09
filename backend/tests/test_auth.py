"""Role checks use isolated sessions and never modify real settings."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api import create_app
from src.detector_config import DetectorConfig


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

    def test_guest_can_chat_and_read_settings(self):
        self.assertEqual(self.client.get("/api/auth/me").json(), {"authenticated": False, "role": None, "username": None})
        self.assertEqual(self.client.post("/api/chats").status_code, 201)
        for path in ("detector", "api-keys"):
            self.assertEqual(self.client.get(f"/api/settings/{path}").status_code, 200)

    def test_guest_and_user_can_update_normal_settings(self):
        config = DetectorConfig(endpoint="http://127.0.0.1:9000/detect")
        for signed_in in (False, True):
            if signed_in:
                self.client.post("/api/auth/login", json={
                    "username": "user", "password": "user-password",
                })
            with patch("src.api.save_detector_settings", return_value=config) as save:
                response = self.client.post("/api/settings/detector", json=config.model_dump(mode="json"))
                self.assertEqual(response.status_code, 200)
                save.assert_called_once()
            with patch("src.api.save_api_keys") as save, patch("src.api.apply_api_key_updates"):
                keys = {"ETHERSCAN_API_KEY": "test-key", "DETECTOR_API_KEY": None}
                response = self.client.post("/api/settings/api-keys", json={"keys": keys})
                self.assertEqual(response.status_code, 200)
                save.assert_called_once_with(keys)

    def test_ai_key_changes_require_admin_before_any_writes(self):
        for role, expected in ((None, 401), ("user", 403), ("admin", 200)):
            if role:
                self.client.post("/api/auth/login", json={
                    "username": role,
                    "password": "test-password" if role == "admin" else "user-password",
                })
            for name in ("OPENAI_API_KEY", "GEMINI_API_KEY", "CLAUDE_API_KEY", "ANTHROPIC_API_KEY"):
                for value in ("test-key", None):
                    with self.subTest(role=role, name=name, value=value):
                        with patch("src.api.save_api_keys") as save, patch("src.api.apply_api_key_updates") as apply:
                            keys = {name: value, "ETHERSCAN_API_KEY": "shared-key"}
                            response = self.client.post("/api/settings/api-keys", json={"keys": keys})
                            self.assertEqual(response.status_code, expected)
                            if role == "admin":
                                save.assert_called_once_with(keys)
                                apply.assert_called_once_with(keys)
                            else:
                                save.assert_not_called()
                                apply.assert_not_called()

    def test_guest_history_survives_login_and_logout(self):
        chat = self.client.post("/api/chats").json()["id"]
        self.login()
        self.assertEqual(self.client.get(f"/api/chats/{chat}").status_code, 404)
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get(f"/api/chats/{chat}").status_code, 200)

    def test_logout_hides_account_chat_and_revokes_token(self):
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
        self.assertEqual(self.client.get("/api/settings/api-keys").status_code, 200)

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
        self.assertEqual(self.client.get("/api/settings/detector").status_code, 200)

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
