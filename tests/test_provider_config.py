"""Offline tests for modular local API configuration and secret non-disclosure."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supahbetting.external_feeds import FootballData, ProviderHub
from supahbetting.live_scores import LiveDataUnavailable
from supahbetting.provider_config import (
    ProviderConfigError, get_api_key, make_local_config, _read_provider_entries,
)


class ProviderConfigTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / ".supahbetting" / "providers.json"

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_first_start_makes_valid_empty_template(self):
        self.assertTrue(make_local_config(self.path))
        self.assertTrue(self.path.exists())
        document = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("providers", document)
        self.assertIn("football-data", document["providers"])
        self.assertEqual(document["providers"]["football-data"]["api_key"], "")
        self.assertEqual(
            get_api_key("football-data", config_path=self.path, environ={}, env_var="FOOTBALL_DATA_API_KEY"),
            "",
        )
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_second_start_never_overwrites_existing_key(self):
        make_local_config(self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["providers"]["football-data"]["api_key"] = "PRIVATE_VALID_TOKEN_123"
        self._write(data)
        self.assertFalse(make_local_config(self.path))
        self.assertEqual(
            get_api_key("football-data", config_path=self.path),
            "PRIVATE_VALID_TOKEN_123",
        )

    def test_file_wins_over_old_env_token(self):
        self._write({"providers": {"football-data": {"api_key": "FROM_LOCAL_JSON"}}})
        self.assertEqual(
            get_api_key(
                "football-data", config_path=self.path,
                env_var="FOOTBALL_DATA_API_KEY",
                environ={"FOOTBALL_DATA_API_KEY": "FROM_ENV"},
            ),
            "FROM_LOCAL_JSON",
        )

    def test_legacy_environment_remains_fallback(self):
        self._write({"providers": {"football-data": {"api_key": ""}}})
        self.assertEqual(
            get_api_key(
                "football-data", config_path=self.path,
                env_var="FOOTBALL_DATA_API_KEY",
                environ={"FOOTBALL_DATA_API_KEY": "OLD_VALID_KEY"},
            ),
            "OLD_VALID_KEY",
        )

    def test_new_provider_can_be_added_without_changing_parser(self):
        self._write({
            "providers": {
                "football-data": {"api_key": "ONE"},
                "future-data-service": {"api_key": "TWO"},
            }
        })
        self.assertEqual(get_api_key("future-data-service", config_path=self.path), "TWO")
        self.assertEqual(get_api_key("football-data", config_path=self.path), "ONE")
        self.assertEqual(get_api_key("missing-provider", config_path=self.path), "")

    def test_invalid_json_does_not_reveal_tokens(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('{"providers": {"football-data": {"api_key": "SECRET_ABC"},', encoding="utf-8")
        with self.assertRaises(ProviderConfigError) as caught:
            get_api_key("football-data", config_path=self.path)
        self.assertNotIn("SECRET_ABC", str(caught.exception))
        self.assertIn("JSON", str(caught.exception))

    def test_invalid_key_types_and_control_chars(self):
        for key in (["token"], 42, {"x": "token"}, "SECRET\nTOKEN", "A" * 513):
            with self.subTest(key=type(key)):
                self._write({"providers": {"football-data": {"api_key": key}}})
                with self.assertRaises(ProviderConfigError):
                    _read_provider_entries(self.path)

    def test_invalid_root_object_and_provider_name(self):
        for document in ([], {"other": {}}, {"providers": []},
                         {"providers": {"../bad": {"api_key": "X"}}},
                         {"providers": {"football-data": ["invalid"]}}):
            with self.subTest(document=type(document)):
                self._write(document)
                with self.assertRaises(ProviderConfigError):
                    get_api_key("football-data", config_path=self.path)

    def test_football_provider_uses_file_without_env(self):
        self._write({"providers": {"football-data": {"api_key": "SAMPLE_SECRET"}}})
        with patch.dict(os.environ, {"FOOTBALL_DATA_API_KEY": ""}, clear=False):
            football = FootballData(config_path=self.path, fetcher=lambda path: {})
        self.assertTrue(football.enabled)
        self.assertEqual(football.token, "SAMPLE_SECRET")
        hub = ProviderHub(football_data=football)
        catalog = hub.catalog()
        self.assertTrue(catalog["providers"][2]["enabled"])
        self.assertNotIn("SAMPLE_SECRET", json.dumps(catalog))

    def test_bad_file_disables_only_configured_provider(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('{ "providers": { "football-data": "UNSAFE_SECRET" } }', encoding="utf-8")
        with patch.dict(os.environ, {"FOOTBALL_DATA_API_KEY": ""}, clear=False):
            football = FootballData(config_path=self.path, fetcher=lambda path: {})
        self.assertFalse(football.enabled)
        catalog = ProviderHub(football_data=football).catalog()
        self.assertTrue(catalog["providers"][0]["enabled"])
        self.assertTrue(catalog["providers"][1]["enabled"])
        self.assertFalse(catalog["providers"][2]["enabled"])
        self.assertNotIn("UNSAFE_SECRET", json.dumps(catalog))
        with self.assertRaises(LiveDataUnavailable):
            football.list_matches("DED")

    def test_instructions_for_missing_key_are_actionable(self):
        make_local_config(self.path)
        with patch.dict(os.environ, {"FOOTBALL_DATA_API_KEY": ""}, clear=False):
            football = FootballData(config_path=self.path, fetcher=lambda path: {})
        with self.assertRaisesRegex(LiveDataUnavailable, "bewerk_api_config.bat"):
            football.list_matches("DED")


if __name__ == "__main__":
    unittest.main()
