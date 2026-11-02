# Restricted synthetic Render staging (experimental)

This is an **unverified private synthetic staging scaffold**, not the completed Living Literacy website, not production hosting, and not a service for real families. Parent identity, guardianship, consent and educational review are fictional fixtures. Never enter real student, family, educator, or personal information. Do not share the staging gateway password publicly. No live deployment has been verified.

The container starts the existing six-stage Python application on loopback and places an authenticated nginx gateway in front of it. Nginx listens on Render's assigned port, replaces client gateway headers, and requires an independent HTTP Basic password. The backend checks the exact HTTPS origin and uses a Secure session cookie. Basic authentication and a simple **global**, single-instance nginx rate limit are not production identity, strong abuse protection or multi-tenant isolation. Real child data, public family signup, legal compliance and production release remain blocked by the project release gates. Render must terminate HTTPS for the exact configured onrender.com hostname. Do not expose the backend directly.

**Data is intentionally discarded on every process restart**, including sleeping, redeploying or changing settings. Render's free web service may spin down after inactivity and does not preserve the local SQLite filesystem. This cannot provide durable saved student progress. Render's free offerings and policies may change; review the [current free tier details](https://render.com/docs/free) and [web service documentation](https://render.com/docs/web-services). Keep the repository free of secret values and actual databases.

## Prerequisites

- An account and service capable of running a Docker-based Render web service on its free plan, if available to the account.
- A GitHub repository containing this revision of the Living Literacy project, including `prototype/`, `content/`, `registry/`, `deploy/render/` and `tests/`. The earlier public GitHub upload may not contain the staging changes yet.
- Three **different cryptographically random** URL-safe secrets, 32–128 ASCII letters, digits, `_` or `-`. Syntax validation does not measure entropy. Generate them locally in a private terminal (one command per value) and enter them only in Render's secret environment-variable editor. Do not put them in source control, a URL, chat, screenshots or command arguments:

  ```sh
  python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
  ```

- A known exact HTTPS origin, such as `https://your-staging-name.onrender.com`. This scaffold accepts only an `onrender.com` origin, no trailing slash or path. Custom domains require a separately reviewed change.

## Operator setup (pending actual verification)

1. In Render, create a Docker web service connected to the updated repository and select the free plan if available. Set **Dockerfile path** to `deploy/render/Dockerfile` and the build context to the repository root. Verify that the service listens on Render's `PORT`. Do not set the app backend port 8765 as a public port. Use the default TCP health check; an unauthenticated HTTP health check would be blocked by the gateway.
2. Add these as environment variables using the provider's secret UI. Do not use the sample placeholders as real passwords:
   - `LL_STAGING_ORIGIN`: the exact assigned HTTPS service origin, for example `https://your-staging-name.onrender.com`. After Render assigns the URL, verify it matches exactly; update and redeploy if needed.
   - `LIVING_LITERACY_STAGING_PROXY_SECRET`: the first randomly generated value. It is used only between nginx and the loopback app.
   - `LL_GATEWAY_PASSWORD`: the second randomly generated value. Browser gateway username is `demo`.
   - `LL_DEMO_PASSWORD`: the third randomly generated value. Synthetic application identity is `synthetic-parent-1`.
   - Render normally supplies `PORT`; if manually configured use an unprivileged port other than 8765.
3. Start the service only after configuring the three independent secrets. If any is missing, reused, too short or contains unsupported characters, the process fails closed. The code verifies format, not entropy. If the exact Render hostname was unknown before creation, set it to the actual service origin before a successful start.
4. Verify the browser prompts for the gateway credentials over HTTPS before showing the app. Authenticate as `demo` with the gateway password, then use the fictional app identity and separate fictional app password. Keep all data fictional. Review Render settings and billing/usage limits; no free-tier availability or lack of charges is guaranteed. Before deployment, publish the corresponding source for the exact deployed revision at the link in the application, as required by the selected AGPL license. The existing public GitHub copy does not yet contain these staging changes; do not deploy it until the matching source is available.

## Checks required before sharing any URL

Confirm that: non-HTTPS access is redirected or denied by the provider; unauthenticated requests do not expose the app; bad gateway credentials and repeated attempts are throttled; spoofed `X-Living-Literacy-Gateway` is replaced; backend port 8765 is not reachable externally; exact Host/Origin, CSRF and Secure cookies work; cross-family access and withdrawn content are denied; and a real browser can navigate every stage. Test restart and confirm the data reset is understood. The global rate limiter can cause denial of service and resets with the instance; the framework has not been penetration tested. Add independently reviewed, durable controls before any broader audience, real identity, or real data use.

Docker build, nginx configuration, TLS/proxy integration and Render behavior have **not been tested in this environment** because its Docker daemon was inaccessible. The accompanying automated tests only verify generated settings and configuration strings, not a running server. Do not claim this scaffold is verified, publicly deployed, free forever, or suitable for children.
