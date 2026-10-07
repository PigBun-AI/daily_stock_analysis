# -*- coding: utf-8 -*-
"""Multi-user auth: bcrypt hashes, watchlist isolation, session payload."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.auth as auth
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
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test.db")
        os.environ.pop("DATABASE_URL", None)
        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=True)
        self.data_dir_patcher = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self.auth_patcher.start()
        self.data_dir_patcher.start()

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        self.data_dir_patcher.stop()
        set_current_user(None)
        reset_user_store()
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_bcrypt_hash_roundtrip(self) -> None:
        record, err = create_user("alice", "secret12")
        self.assertIsNone(err)
        self.assertTrue(verify_password_hash("secret12", record.password_hash))
        self.assertFalse(verify_password_hash("wrong", record.password_hash))
        self.assertIsNotNone(authenticate_user("alice", "secret12"))
        self.assertIsNone(authenticate_user("alice", "wrong"))

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
