import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from quran_analysis.cache import JsonCache
from quran_analysis.client import DiyanetClient


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ClientTests(unittest.TestCase):
    def test_bearer_header_unwrap_and_cache(self):
        seen = []

        def fake_urlopen(req, timeout):
            seen.append(req)
            return _Resp(json.dumps({"data": [{"SureId": 1}], "meta": {}}).encode())

        with tempfile.TemporaryDirectory() as d, mock.patch("urllib.request.urlopen", fake_urlopen):
            c = DiyanetClient("https://x.test/", "secret", cache=JsonCache(Path(d)), min_interval=0)
            self.assertEqual(c.chapters(), [{"SureId": 1}])
            self.assertEqual(c.chapters(), [{"SureId": 1}])  # önbellekten
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer secret")
        self.assertTrue(seen[0].full_url.startswith("https://x.test/api/v1/chapters"))

    def test_token_not_in_repr(self):
        self.assertNotIn("secret", repr(DiyanetClient("https://x.test", "secret")))

    def test_missing_token(self):
        with self.assertRaises(ValueError):
            DiyanetClient("https://x.test", "")


if __name__ == "__main__":
    unittest.main()
