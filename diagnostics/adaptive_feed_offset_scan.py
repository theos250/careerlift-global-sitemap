#!/usr/bin/env python3
"""Read-only overlapping Blogger Atom feed scan.

Uses bounded overlapping start-index windows so short responses do not cause
the fixed-stride gaps possible in the earlier diagnostic. Makes no file writes.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

BASE = "https://www.careerliftglobal.com/feeds/posts/default"
ATOM = "http://www.w3.org/2005/Atom"
NS = {"a": ATOM}
ALLOWED_HOSTS = {
    "www.careerliftglobal.com", "careerliftglobal.com",
    "www.blogger.com", "blogger.com",
}
PAGE_SIZE = 25
OVERLAP = 5
MAX_START_INDEX = 2000
CONSECUTIVE_EMPTY_LIMIT = 20
REQUEST_DELAY_SECONDS = 0.15


def fetch(start: int) -> list[ET.Element]:
    query = urlencode({
        "alt": "atom",
        "max-results": str(PAGE_SIZE),
        "start-index": str(start),
    })
    request = Request(
        f"{BASE}?{query}",
        headers={
            "User-Agent": "CareerLiftGlobal-AdaptiveFeedDiagnostic/1.0",
            "Accept": "application/atom+xml",
        },
    )
    with urlopen(request, timeout=30) as response:
        final = urlparse(response.geturl())
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
            raise RuntimeError(f"Unexpected redirect destination: {response.geturl()}")
        root = ET.fromstring(response.read())
    return root.findall("a:entry", NS)


def main() -> int:
    print("READ-ONLY ADAPTIVE BLOGGER FEED SCAN")
    print("No repository files, artifacts, sitemap files, Blogger settings, or deployments are changed.")
    seen: dict[str, str] = {}
    requested: set[int] = set()
    raw_entries = 0
    duplicate_observations = 0
    empty_streak = 0
    start = 1

    while start <= MAX_START_INDEX and empty_streak < CONSECUTIVE_EMPTY_LIMIT:
        if start in requested:
            print(f"STOP: repeated offset {start}; refusing a loop.")
            break
        requested.add(start)
        try:
            entries = fetch(start)
        except Exception as exc:
            print(f"ERROR at start-index={start}: {type(exc).__name__}: {exc}")
            return 2

        raw_entries += len(entries)
        ids: list[str] = []
        dates: list[str] = []
        new_ids = 0
        duplicate_ids = 0
        for entry in entries:
            entry_id = (entry.findtext("a:id", default="", namespaces=NS) or "").strip()
            published = (entry.findtext("a:published", default="", namespaces=NS) or "").strip()
            if published:
                dates.append(published)
            if not entry_id:
                continue
            ids.append(entry_id)
            if entry_id in seen:
                duplicate_ids += 1
                duplicate_observations += 1
            else:
                seen[entry_id] = published
                new_ids += 1

        if entries:
            empty_streak = 0
        else:
            empty_streak += 1

        print(
            f"start={start}; returned={len(entries)}; new_unique={new_ids}; "
            f"overlap_or_repeat_ids={duplicate_ids}; unique_total={len(seen)}; "
            f"empty_streak={empty_streak}; "
            f"published_range={(min(dates) + '..' + max(dates)) if dates else 'n/a'}"
        )

        # Advance by the actual response size, retaining an overlap. Empty
        # responses advance one index at a time so isolated gaps are probed.
        step = max(1, len(entries) - OVERLAP) if entries else 1
        start += step
        time.sleep(REQUEST_DELAY_SECONDS)

    dates = [value for value in seen.values() if value]
    print("----- SUMMARY -----")
    print(f"requests={len(requested)}")
    print(f"raw_entry_observations={raw_entries}")
    print(f"unique_post_ids={len(seen)}")
    print(f"overlap_or_repeat_id_observations={duplicate_observations}")
    print(f"earliest_published={min(dates) if dates else 'n/a'}")
    print(f"latest_published={max(dates) if dates else 'n/a'}")
    print(f"last_requested_start_index={max(requested) if requested else 'n/a'}")
    if empty_streak >= CONSECUTIVE_EMPTY_LIMIT:
        print(f"STOP_REASON={CONSECUTIVE_EMPTY_LIMIT}_consecutive_empty_offsets")
    elif start > MAX_START_INDEX:
        print("STOP_REASON=maximum_start_index_guard")
    print("INTERPRETATION: This is an overlapping lower-bound inventory, not proof of completeness.")
    print("Feed mutations, non-monotonic offset behavior, or long empty gaps can still affect coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
