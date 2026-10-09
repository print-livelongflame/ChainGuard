import unittest
from unittest.mock import Mock, patch

from fetchers.contract_fetcher import decode_metadata_string, get_contract_info, get_token_metadata
from src.main import build_address_context_json


def encoded(text):
    raw = text.encode()
    return "0x" + (32).to_bytes(32, "big").hex() + len(raw).to_bytes(32, "big").hex() + raw.hex().ljust(((len(raw) + 31) // 32) * 64, "0")


class ContractMetadataTests(unittest.TestCase):
    def test_standard_and_legacy_strings_and_invalid_returns(self):
        self.assertEqual(decode_metadata_string(encoded("Example Token")), "Example Token")
        self.assertEqual(decode_metadata_string("0x" + b"EXT".hex().ljust(64, "0")), "EXT")
        for value in ("0x", "not hex", "0xzz", encoded(""), encoded("bad\nname"), encoded("Token")[:-64]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_metadata_string(value)

    @patch("fetchers.contract_fetcher.requests.get")
    @patch("fetchers.contract_fetcher.get_api_key", return_value="test-key")
    def test_identity_survives_fetcher_normalization(self, key, get):
        payloads = [
            {"result": "0x6000"}, {"status": "0", "result": "unverified"},
            {"status": "1", "result": [{"contractCreator": "creator", "txHash": "tx"}]},
            {"result": encoded("Example Token")}, {"result": encoded("EXT")},
        ]
        get.side_effect = [Mock(json=Mock(return_value=value)) for value in payloads]
        address = "0x" + "1" * 40
        data = get_contract_info(address)
        context = build_address_context_json(address, {
            "contract": {"status": "pass", "data": data}
        }, {"chain_family": "evm"})
        metadata = context["contract"]["token_metadata"]
        self.assertEqual(metadata["name"], "Example Token")
        self.assertEqual(metadata["symbol"], "EXT")
        self.assertEqual(metadata["fields"]["name"]["status"], "pass")
        self.assertEqual(get.call_args_list[3].kwargs["params"]["to"], address)
        self.assertEqual(get.call_args_list[3].kwargs["params"]["data"], "0x06fdde03")
        self.assertEqual(get.call_args_list[4].kwargs["params"]["data"], "0x95d89b41")

    @patch("fetchers.contract_fetcher.requests.get")
    def test_partial_failure_and_wallet_skip(self, get):
        get.side_effect = [Mock(json=Mock(return_value={"error": {"message": "revert"}})),
                           Mock(json=Mock(return_value={"result": encoded("EXT")}))]
        metadata = get_token_metadata("target", "0x6000", {"chainid": 1})
        self.assertIsNone(metadata["name"])
        self.assertEqual(metadata["fields"]["name"]["status"], "fail")
        self.assertEqual(metadata["symbol"], "EXT")
        get.reset_mock()
        for bytecode in ("0x", None, "0xef0100" + "1" * 40):
            metadata = get_token_metadata("wallet", bytecode, {"chainid": 1})
            self.assertEqual(metadata["fields"]["name"]["status"], "skip")
        get.assert_not_called()
