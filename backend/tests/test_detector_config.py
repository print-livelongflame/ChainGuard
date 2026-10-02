import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.detector_config import (
    DetectorConfig,
    get_detector_settings,
    load_detector_config,
    save_detector_settings,
)


class DetectorConfigTests(unittest.TestCase):
    def test_missing_config_uses_environment_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "detector_config.json"
            with patch("src.detector_config.CONFIG_PATH", config_path), patch.dict(
                os.environ,
                {
                    "CHAINGUARD_DETECTOR_DEFAULT_ENABLED": "true",
                    "CHAINGUARD_DETECTOR_DEFAULT_NAME": "Compose detector",
                    "CHAINGUARD_DETECTOR_DEFAULT_ENDPOINT": "http://detector:9000/detect",
                },
            ):
                config = load_detector_config()

            self.assertIsNotNone(config)
            self.assertEqual(config.name, "Compose detector")
            self.assertEqual(str(config.endpoint), "http://detector:9000/detect")

    def test_saved_config_overrides_environment_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "detector_config.json"
            with patch("src.detector_config.CONFIG_PATH", config_path), patch.dict(
                os.environ,
                {
                    "CHAINGUARD_DETECTOR_DEFAULT_ENABLED": "true",
                    "CHAINGUARD_DETECTOR_DEFAULT_ENDPOINT": "http://detector:9000/detect",
                },
            ):
                saved = save_detector_settings(DetectorConfig(
                    enabled=False,
                    name="Disabled detector",
                    endpoint="http://detector:9000/detect",
                ))
                loaded = get_detector_settings()

            self.assertFalse(saved.enabled)
            self.assertFalse(loaded.enabled)
            self.assertEqual(loaded.name, "Disabled detector")


if __name__ == "__main__":
    unittest.main()
