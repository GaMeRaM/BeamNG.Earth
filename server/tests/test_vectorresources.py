import base64
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vectorresources as vr


class ResourcesTest(unittest.TestCase):
    def tearDown(self):
        vr.resource.cache_clear()

    def test_provider_allowlist(self):
        for url in ['http://tiles.openfreemap.org/planet', 'https://evil.test/',
                    'https://tiles.openfreemap.org.evil.test/',
                    'https://user@tiles.openfreemap.org/planet',
                    'https://tiles.openfreemap.org:443/planet',
                    'https://tiles.openfreemap.org/planet#x', None]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                vr.validate_url(url)

    def test_binary_roundtrip_and_cache(self):
        class Fetcher:
            calls = 0
            def get(self, url, **kwargs):
                self.calls += 1
                return SimpleNamespace(body=b'\x00\xff\x80vector')
        f = Fetcher()
        url = 'https://tiles.openfreemap.org/planet'
        data = vr.resource(f, url)
        self.assertEqual(base64.b64decode(data), b'\x00\xff\x80vector')
        self.assertEqual(vr.resource(f, url), data)
        self.assertEqual(f.calls, 1)

    def test_oversized_response(self):
        # Hashable fake, matching the real Fetcher instance used as an LRU key.
        class Fetcher:
            def get(self, *args, **kwargs):
                return SimpleNamespace(body=b'x' * (vr.MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            vr.resource(Fetcher(), 'https://tiles.openfreemap.org/planet')
