# CareerLift Global — Automatic Consolidated XML Sitemap

This isolated project generates a single XML sitemap from CareerLift Global's public Blogger Atom feed and can deploy it to GitHub Pages after explicit approval.

## Safety boundaries

- Reads Blogger's public Atom feed only.
- Does not modify Blogger posts, theme, settings, native sitemap endpoints, DNS, or Search Console.
- Does not publish or edit any CareerLift content.
- Writes only the generated `public/sitemap.xml` Pages artifact.
- Existing Blogger endpoints `/sitemap.xml` and `/sitemap-pages.xml` remain untouched.
- The workflow polls every 15 minutes. Blogger does not expose a native GitHub Actions publish webhook, so this is near-publication detection, not instantaneous.
- The workflow refuses to deploy if fewer than 800 unique posts are discovered.

## Files

- `scripts/generate_sitemap.py`: Blogger Atom pagination, URL normalization, XML generation and safety validation.
- `tests/test_generator.py`: offline regression tests.
- `static-urls.txt`: optional manually verified public static pages.
- `.github/workflows/careerlift-sitemap.yml`: scheduled/manual GitHub Pages deployment workflow.

## Static pages

The initial `static-urls.txt` is intentionally empty except for comments. Add only public, indexable static pages after checking each page's canonical URL. Do not add labels, search pages, archive pages, redirects, or noindex URLs.

## Deployment — intentionally not enabled yet

1. Review and merge the pull request only after approval.
2. In repository **Settings → Pages**, set the source to **GitHub Actions** only when deployment is approved.
3. Open **Actions → CareerLift Global sitemap refresh → Run workflow** only after Pages is configured and deployment is approved.
4. Inspect the workflow log. Confirm the discovered post count is plausible against Blogger's published-post inventory (previously reported as 1,121).
5. Confirm the deployed file at `https://theos250.github.io/careerlift-global-sitemap/sitemap.xml` returns valid XML and includes the newest published post and older posts.
6. Only after verification, decide whether to submit the external sitemap in Search Console. Cross-site sitemap submission requires ownership verification for the site hosting the sitemap and the site whose URLs it lists.
7. Do not remove Blogger's successful native sitemap submissions.

## Important limitations

- The public GitHub Pages URL is an external sitemap URL, not `https://www.careerliftglobal.com/sitemap.xml`. This project does not change DNS or proxy Blogger's native endpoint.
- GitHub scheduled workflows are best-effort and can be delayed.
- A sitemap helps discovery; it does not guarantee crawling, indexing, rankings, impressions, or clicks.
- `lastmod` uses Blogger's Atom `updated` value. It is omitted when unavailable.
- `priority` and `changefreq` are omitted because search engines may ignore them.
- The first live run is required to validate actual Blogger feed pagination and full inventory. Offline tests do not prove live feed completeness.
