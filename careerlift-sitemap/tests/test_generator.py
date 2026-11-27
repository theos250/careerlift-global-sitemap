import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_sitemap as sitemap

ATOM = "http://www.w3.org/2005/Atom"


def entry(post_id: str, slug: str, updated: str = "2026-11-27T00:00:00Z") -> ET.Element:
    return ET.fromstring(
        f'<entry xmlns="{ATOM}"><id>{post_id}</id><updated>{updated}</updated>'
        f'<link rel="alternate" href="https://www.careerliftglobal.com/{slug}.html"/>'
        f'</entry>'
    )


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
        self.assertIsNone(sitemap.canonicalize("https://example.com/post", "www.careerliftglobal.com"))

    def test_rejects_non_http_scheme(self):
        self.assertIsNone(sitemap.canonicalize("javascript:alert(1)", "www.careerliftglobal.com"))

    def test_parses_timestamp_to_utc(self):
        self.assertEqual(sitemap.parse_timestamp("2026-11-27T03:00:00+02:00"), "2026-11-27T01:00:00Z")

    def test_omits_invalid_timestamp(self):
        self.assertIsNone(sitemap.parse_timestamp("not-a-date"))

    def test_builds_valid_sitemap_and_deduplicates_static_url(self):
        xml = sitemap.build_xml(
            {"https://www.careerliftglobal.com/post.html": "2026-11-27T00:00:00Z"},
            ["https://www.careerliftglobal.com/post.html", "https://www.careerliftglobal.com/p/about.html"],
        )
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")
        self.assertEqual(len(root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")), 2)

    def test_offset_url_preserves_feed_path_and_adds_offset_parameters(self):
        url = sitemap.build_offset_url(
            "https://www.careerliftglobal.com/feeds/posts/default?alt=atom&max-results=150", 21, 25
        )
        self.assertIn("start-index=21", url)
        self.assertIn("max-results=25", url)
        self.assertIn("/feeds/posts/default", url)

    def test_discovery_overlaps_pages_and_deduplicates_entry_ids(self):
        pages = {
            1: [entry("id-1", "post-1"), entry("id-2", "post-2"), entry("id-3", "post-3")],
            3: [entry("id-3", "post-3"), entry("id-4", "post-4")],
            4: [],
            5: [],
        }
        starts = []

        def fake_fetch(_feed, start, _size):
            starts.append(start)
            return pages.get(start, [])

        with patch.object(sitemap, "fetch_feed_page", side_effect=fake_fetch):
            result = sitemap.discover_posts(
                "https://www.careerliftglobal.com/feeds/posts/default",
                "www.careerliftglobal.com",
                page_size=3, overlap=1, empty_offset_limit=2,
                max_start_index=10, max_requests=10, request_delay=0,
            )
        self.assertEqual(len(result), 4)
        self.assertEqual(starts, [1, 3, 4, 5])

    def test_incomplete_scan_fails_closed_at_request_limit(self):
        with patch.object(sitemap, "fetch_feed_page", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "did not reach"):
                sitemap.discover_posts(
                    "https://www.careerliftglobal.com/feeds/posts/default",
                    "www.careerliftglobal.com",
                    empty_offset_limit=3, max_start_index=10,
                    max_requests=2, request_delay=0,
                )


if __name__ == "__main__":
    unittest.main()
