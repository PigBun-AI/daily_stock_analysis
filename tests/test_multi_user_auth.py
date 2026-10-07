# -*- coding: utf-8 -*-
"""Multi-user auth: register/login isolation and bcrypt hashes."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.auth as auth
from api.v1.endpoints import auth as auth_endpoint
from src.config import Config
from src.identity import CurrentUser, isolation_owner_id, set_current_user
from src.user_store import (
    authenticate_user,
    create_user,
    get_watchlist_codes,
    reset_user_store,
    set_watchlist_codes,
    verify_password_hash,
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class MultiUserAuthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        reset_user_store()
        set_current_user(None)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=true\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test.db")
        os.environ.pop("DATABASE_URL", None)
        Config.reset_instance()
        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=True)
        self.data_dir_patcher = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self.auth_patcher.start()
        self.data_dir_patcher.start()

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        self.data_dir_patcher.stop()
        set_current_user(None)
        reset_user_store()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    @staticmethod
    def _request(cookies=None):
        return SimpleNamespace(
            headers={},
            url=SimpleNamespace(scheme="http"),
            cookies=cookies or {},
            client=SimpleNamespace(host="127.0.0.1"),
            state=SimpleNamespace(user=None),
        )

    def test_bcrypt_hash_roundtrip(self) -> None:
        record, err = create_user("alice", "secret12")
        self.assertIsNone(err)
        self.assertTrue(verify_password_hash("secret12", record.password_hash))
        self.assertFalse(verify_password_hash("wrong", record.password_hash))
        self.assertIsNotNone(authenticate_user("alice", "secret12"))
        self.assertIsNone(authenticate_user("alice", "wrong"))

    def test_register_and_login_sets_user_session(self) -> None:
        register = asyncio.run(
            auth_endpoint.auth_register(
                self._request(),
                auth_endpoint.RegisterRequest(
                    username="bob",
                    password="secret12",
                    passwordConfirm="secret12",
                ),
            )
        )
        self.assertEqual(register.status_code, 200)
        self.assertIn("dsa_session=", register.headers["set-cookie"])

        login = asyncio.run(
            auth_endpoint.auth_login(
                self._request(),
                auth_endpoint.LoginRequest(username="bob", password="secret12"),
            )
        )
        self.assertEqual(login.status_code, 200)
        cookie = login.headers["set-cookie"].split("dsa_session=", 1)[1].split(";", 1)[0]
        info = auth.verify_session_info(cookie)
        self.assertIsNotNone(info)
        self.assertIsNotNone(info["user_id"])

    def test_watchlists_are_isolated_per_user(self) -> None:
        alice, err_a = create_user("alice", "secret12")
        bob, err_b = create_user("bob", "secret12")
        self.assertIsNone(err_a)
        self.assertIsNone(err_b)
        set_watchlist_codes(alice.id, ["600519"])
        set_watchlist_codes(bob.id, ["AAPL"])
        self.assertEqual(get_watchlist_codes(alice.id), ["600519"])
        self.assertEqual(get_watchlist_codes(bob.id), ["AAPL"])

    def test_isolation_owner_follows_current_user(self) -> None:
        self.assertIsNone(isolation_owner_id())
        set_current_user(CurrentUser(id=7, username="carol", role="user"))
        self.assertEqual(isolation_owner_id(), "7")
        set_current_user(None)
        self.assertIsNone(isolation_owner_id())

    def test_legacy_session_format_still_three_parts(self) -> None:
        token = auth.create_session()
        self.assertEqual(len(token.split(".")), 3)
        self.assertTrue(auth.verify_session(token))
        self.assertIsNone(auth.verify_session_info(token)["user_id"])

    def test_user_session_format_has_four_parts(self) -> None:
        token = auth.create_session(user_id=3)
        self.assertEqual(len(token.split(".")), 4)
        self.assertEqual(auth.verify_session_info(token)["user_id"], 3)
