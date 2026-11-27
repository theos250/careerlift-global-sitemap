# CareerLift Global — Automatic Consolidated XML Sitemap

This project discovers all currently published CareerLift Global Blogger posts and builds a consolidated XML sitemap. It uses overlapping direct offsets because the normal Atom `rel=next` chain stopped early during live diagnostics.

## Discovery and future posts

- Each complete refresh starts at the newest published post and scans the Blogger Atom feed with overlapping `start-index` windows.
- Newly published posts are discovered on the next refresh because every refresh rescans the current feed from the beginning and rebuilds the URL set.
- Blogger has no native GitHub Actions publish webhook. Once scheduled publishing is explicitly activated, the intended polling interval is every 15 minutes (best-effort; GitHub may delay scheduled runs).
- Drafts and scheduled-but-not-yet-published Blogger posts are not public feed entries. They enter the sitemap after Blogger actually publishes them.
- The sitemap is rebuilt from the current public feed each time, so deleted or unpublished posts are not deliberately retained as stale entries.
- The 800-unique-post minimum remains a fail-closed safety gate.

## Safety boundaries

- Reads Blogger's public Atom feed only.
- Does not modify Blogger posts, theme, settings, native sitemap endpoints, DNS, or Search Console.
- Does not publish or edit any CareerLift content.
- The current workflow is manual dry-run only, has `contents: read` permission, and does not write files, upload artifacts, configure Pages, or deploy.
- Existing Blogger endpoints `/sitemap.xml` and `/sitemap-pages.xml` remain untouched.
- No automatic schedule or deployment is enabled until separately approved.

## Validation

Run **Actions → CareerLift Global sitemap dry run → Run workflow**. It runs offline regression tests, scans the live public feed, validates the sitemap XML in memory, and reports the discovered URL count without writing an output file.

## Future activation — requires separate explicit approval

To make future published posts appear automatically on the external sitemap, a later approved change must:
1. Enable GitHub Pages with GitHub Actions as its source.
2. Add the 15-minute schedule to the production workflow.
3. Grant only the Pages deployment permissions needed for that workflow.
4. Run and inspect a complete initial deployment, confirming the newest post and older posts are present.
5. Only after verifying the public sitemap, decide whether to submit its external URL in Search Console.

Until that approval, the repository remains in dry-run mode. Existing Blogger sitemaps must not be removed or replaced.

## Important limitations

- The external GitHub Pages sitemap URL is not `https://www.careerliftglobal.com/sitemap.xml`; this project does not change DNS or proxy Blogger's native endpoint.
- Scheduled GitHub Actions runs are best-effort, not instantaneous.
- A sitemap helps discovery; it does not guarantee crawling, indexing, rankings, impressions, or clicks.
- `lastmod` uses Blogger's Atom `updated` value and is omitted when unavailable.
- `priority` and `changefreq` are omitted.
- Live feed inventory previously returned 1,121 unique Blogger entry IDs. The generator retains the 800-post safety minimum and must pass a fresh dry run before any deployment.
