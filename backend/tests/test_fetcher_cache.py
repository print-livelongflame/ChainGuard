import tempfile
import time
import unittest
from pathlib import Path

from src.fetcher_cache import (
    build_fetcher_cache_key,
    read_fetcher_cache,
    write_fetcher_cache,
)


class FetcherCacheTests(unittest.TestCase):
    def test_cache_round_trip_reports_disk_source_and_age(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            cache_key = build_fetcher_cache_key(
                "contract",
                "fetchers.contract_fetcher",
                "get_contract_info",
                ("0xabc",),
                {"chain_id": 1},
            )
            written = write_fetcher_cache(
                cache_key, {"bytecode": "0x123"}, 300, cache_dir
            )

            data, metadata = read_fetcher_cache(cache_key, 300, cache_dir)

        self.assertEqual(data, {"bytecode": "0x123"})
        self.assertEqual(written["source"], "network")
        self.assertEqual(metadata["source"], "disk")
        self.assertEqual(metadata["age_seconds"], 0)
        self.assertEqual(metadata["ttl_seconds"], 300)

    def test_expired_cache_is_a_network_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            cache_key = "expired"
            write_fetcher_cache(cache_key, [], 0, cache_dir)
            time.sleep(1)

            data, metadata = read_fetcher_cache(cache_key, 0, cache_dir)

        self.assertIsNone(data)
        self.assertEqual(metadata["source"], "network")
        self.assertTrue(metadata["stale"])

    def test_cache_key_includes_all_fetcher_arguments(self):
        key = build_fetcher_cache_key(
            "contract",
            "fetchers.contract_fetcher",
            "get_contract_info",
            ("0xabc",),
            {"chain_id": 1},
        )
        different_key = build_fetcher_cache_key(
            "contract",
            "fetchers.contract_fetcher",
            "get_contract_info",
            ("0xdef",),
            {"chain_id": 1},
        )

        self.assertNotEqual(key, different_key)

    def test_cache_key_normalizes_hex_address_case(self):
        lowercase_key = build_fetcher_cache_key(
            "contract",
            "fetchers.contract_fetcher",
            "get_contract_info",
            ("0xabcdef",),
            {"chain_id": 1},
        )
        uppercase_key = build_fetcher_cache_key(
            "contract",
            "fetchers.contract_fetcher",
            "get_contract_info",
            ("0xABCDEF",),
            {"chain_id": 1},
        )

        self.assertEqual(lowercase_key, uppercase_key)


if __name__ == "__main__":
    unittest.main()
