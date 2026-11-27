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

The Netlify workflow checks Blogger's latest feed every five minutes and
deploys only when it detects a newly published URL. GitHub scheduled workflows
are best-effort, so this is not a guaranteed exact five-minute publication SLA.
The full generator still scans the complete feed and fails closed if discovery
is incomplete. The Netlify workflow also retains manual deployment and deploys
the WebSub callback function.

The expected project Pages URL is:

`https://theos250.github.io/careerlift-global-sitemap/sitemap.xml`

This URL is not live until the repository's Pages publishing source is set to
**GitHub Actions** and a deployment succeeds. In repository Settings → Pages →
Build and deployment → Source, select **GitHub Actions**. No custom domain or
DNS change is required.

### Netlify hosting and near-instant Blogger notifications

The workflow at `.github/workflows/deploy-netlify.yml` deploys the posts-only
sitemap and the authenticated Netlify WebSub callback. It checks the latest
Blogger feed every five minutes as a fallback. Blogger's feed supports
low-latency PubSubHubbub/WebSub updates; the callback requests a GitHub Actions
workflow dispatch when a signed notification arrives. The separate
`.github/workflows/subscribe-websub.yml` workflow subscribes and renews the
feed subscription daily.

WebSub notifications are best-effort and depend on Blogger advertising a hub
and the hub accepting the subscription. The five-minute poll remains the
fallback; neither mechanism guarantees that Google crawls or indexes a URL
immediately.

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


### WebSub activation and secrets

After the first deployment has published
`/.netlify/functions/blogger-websub`, configure these Netlify environment
variables under **Project configuration → Environment variables**:

- `GITHUB_DISPATCH_TOKEN` — a fine-grained GitHub personal access token
  restricted to this repository, with **Actions: Read and write** only. It
  lets the callback dispatch the sitemap workflow; do not grant Contents,
  Administration, or organization permissions.
- `WEBSUB_SECRET` — a separate random secret of at least 32 characters.
  This is used to verify signed notifications from the WebSub hub. Do not use
  the GitHub token as this secret.

Add the same `WEBSUB_SECRET` as a GitHub Actions repository secret at
**Settings → Secrets and variables → Actions**. The subscription workflow
needs it to request signed notifications. Never commit either secret or put
them in public files.

After setting the Netlify variables, redeploy the site so the function receives
them. Then run **Actions → Subscribe CareerLift Global Blogger feed to WebSub
→ Run workflow** once. The workflow discovers Blogger's advertised hub,
subscribes the Netlify callback, and the hub must complete its verification
challenge. It renews the subscription daily thereafter. If Blogger does not
advertise a usable hub, the subscription workflow will fail clearly and the
five-minute fallback remains available.
