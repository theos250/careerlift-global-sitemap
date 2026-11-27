import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_sitemap as sitemap


class SitemapTests(unittest.TestCase):
    def test_normalizes_query_fragment_and_www_host(self):
        self.assertEqual(
            sitemap.canonicalize(
                "https://careerliftglobal.com/2026/11/post.html?m=1#top",
                "www.careerliftglobal.com",
            ),
            "https://www.careerliftglobal.com/2026/11/post.html",
        )

    def test_rejects_external_host(self):
        self.assertIsNone(
            sitemap.canonicalize("https://example.com/post", "www.careerliftglobal.com")
        )

    def test_rejects_non_http_scheme(self):
        self.assertIsNone(
            sitemap.canonicalize("javascript:alert(1)", "www.careerliftglobal.com")
        )

    def test_parses_timestamp_to_utc(self):
        self.assertEqual(
            sitemap.parse_timestamp("2026-11-27T03:00:00+02:00"),
            "2026-11-27T01:00:00Z",
        )

    def test_omits_invalid_timestamp(self):
        self.assertIsNone(sitemap.parse_timestamp("not-a-date"))

    def test_builds_valid_sitemap_and_deduplicates_static_url(self):
        xml = sitemap.build_xml(
            {"https://www.careerliftglobal.com/post.html": "2026-11-27T00:00:00Z"},
            ["https://www.careerliftglobal.com/post.html",
             "https://www.careerliftglobal.com/p/about.html"],
        )
        root = ET.fromstring(xml)
        self.assertEqual(
            root.tag,
            "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset",
        )
        self.assertEqual(
            len(root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")),
            2,
        )


if __name__ == "__main__":
    unittest.main()
