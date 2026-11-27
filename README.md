# CareerLift Global automatic sitemap

This repository builds and publishes an external XML sitemap for
[CareerLift Global](https://www.careerliftglobal.com/).

## What it publishes

- `sitemap.xml` — canonical URLs for currently published Blogger posts.
- The generator rediscovers the complete public Blogger post feed on every run,
  rather than only checking the newest page. Newly published posts are eligible
  for inclusion on the next successful refresh.
- Draft and scheduled-but-unpublished Blogger posts are not public feed entries
  and therefore are not included until Blogger actually publishes them.

The generator uses overlapping `start-index` scans, deduplicates Blogger entry
IDs and canonical URLs, requires 20 consecutive empty offsets before treating
the scan as complete, and fails closed if its scan limits are reached. It also
retains the minimum 800-post safety check.

## Refresh and hosting

GitHub Actions is configured to build and deploy on changes to the generator
and on a 15-minute cron schedule. GitHub scheduled workflows are best-effort:
GitHub may delay a scheduled run, so this is not a guaranteed exact 15-minute
publication SLA. A failed or incomplete feed scan does not deploy a partial
sitemap; the last successful Pages deployment remains in place.

The expected project Pages URL is:

`https://theos250.github.io/careerlift-global-sitemap/sitemap.xml`

This URL is not live until the repository's Pages publishing source is set to
**GitHub Actions** and a deployment succeeds. In repository Settings → Pages →
Build and deployment → Source, select **GitHub Actions**. No custom domain or
DNS change is required.

### Netlify alternative hosting (manual first deployment)

A separate, manual-only workflow is available at
`.github/workflows/deploy-netlify.yml`. It rebuilds and validates the same
posts-only sitemap, then deploys the `public/` directory to a Netlify site.
It does not replace or disable the existing GitHub Pages workflow.

To enable it:

1. Create a Netlify account and a new site using a provider-owned
   `netlify.app` subdomain. Do not add a custom domain.
2. In Netlify, obtain the site's Site ID from Site configuration → General →
   Site details.
3. Create a Netlify personal access token.
4. In GitHub, open this repository's Settings → Secrets and variables →
   Actions → New repository secret. Add:
   - `NETLIFY_AUTH_TOKEN` — the Netlify personal access token.
   - `NETLIFY_SITE_ID` — the Netlify Site ID.
5. After the workflow is merged into `main`, run Actions → Deploy CareerLift
   Global sitemap to Netlify → Run workflow.

The first deployment is intentionally manual. It must be tested from the
publisher's computer and mobile connection before any robots.txt or Search
Console change. To support Google HTML-file verification of the Netlify
URL-prefix property, place Google's downloaded verification HTML file at
`careerlift-sitemap/netlify-verification.html` and commit it before deploying.
The workflow copies that file to the deployed site's root.

Once the Netlify URL is verified and Google ownership verification is complete,
the sitemap can be submitted cross-site using Google's documented process.
Do not remove the existing GitHub Pages deployment or change Blogger's
robots.txt until the Netlify endpoint and Search Console processing are
confirmed.

## Blogger sitemap preservation

This external sitemap is posts-only. It does not modify Blogger or replace
Blogger's native endpoints:

- `https://www.careerliftglobal.com/sitemap.xml`
- `https://www.careerliftglobal.com/sitemap-pages.xml`

The native pages sitemap remains responsible for Blogger static pages. The
external sitemap's `careerlift-sitemap/static-urls.txt` is intentionally empty
until individual static pages are verified as public, canonical and indexable.

## Validation and limitations

Every production build runs the offline regression suite, performs a live
Blogger feed scan, enforces the 800-post minimum, generates XML, and parses the
result before uploading the Pages artifact. The last successful live dry run
found 1,121 unique published post URLs across 97 requests and validated the
XML without writing files or deploying.

A sitemap helps search engines discover URLs; it does not guarantee crawling,
indexing, ranking, impressions or clicks. Keep both native Blogger sitemap
submissions in Search Console. Submit the external sitemap only after its
public URL has been verified.
