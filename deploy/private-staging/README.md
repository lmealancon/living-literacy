# Private online staging — operator draft

This is a **synthetic-data-only** staging design for an experienced operator, not a public or production deployment. It has not been deployed or tested with Caddy in this environment. The app uses simulated parent credentials, guardian authority, consent and reviewer identities. It has no verified real-identity provider, production privacy controls or rate limiter. Do not use real personal or student data. Do not call it ready for families, schools or child-facing instruction.

## Requirements

- A Linux host with Python 3.12, the application source, an operator-controlled persistent SQLite path, and Caddy 2.8+ installed. Caddy and the app must run on the **same host and network namespace**; placing them in separate Docker containers will not satisfy the loopback peer check.
- An operator-owned DNS hostname pointing at the host and a valid HTTPS certificate. Caddy's automatic HTTPS requires its own DNS and network prerequisites; see the installed Caddy documentation. No domain, hosting provider or external account is supplied here.
- Access restricted to a specific trusted client IP/CIDR at the gateway. The example uses Caddy's direct `remote_ip` peer, not untrusted forwarded headers; it does not work as-is behind an additional CDN or reverse proxy. Client IPs can change. Use a properly configured authenticated private VPN or trusted identity-aware access gateway if fixed IPs are not suitable.
- Separately provisioned gateway credentials and a cryptographically random gateway secret, 32–256 characters using only ASCII letters, digits, underscore and hyphen (URL-safe). Use a secret manager to generate a value equivalent to Python `secrets.token_urlsafe(32)`; the app checks syntax, not randomness. The gateway must authenticate the visitor, replace any incoming `X-Living-Literacy-Gateway` header with its own secret, and proxy to `127.0.0.1:8765` only. Keep the secret out of source control, browser code, commands/history, logs, URLs and public configuration. Restrict environment and configuration access.
- An operator-reviewed rate-limiting and monitoring arrangement at the gateway. The supplied app and example Caddy configuration do **not** supply rate limiting, complete audit, backups or incident handling. Do not expose the app while these controls are absent.

## Initialize the synthetic app

In a restricted directory owned by the service operator, initialize an **empty** SQLite database once. This command prompts for a fictional parent passphrase and refuses to overwrite an existing database. Do not use a real person's credentials or information. Choose a path appropriate to the host and a `synthetic-` identity.

```sh
python3 -m prototype.app_server --db /path/to/private/staging.sqlite3 --identity synthetic-parent-1 --init
```

Preserve the database on an access-controlled persistent volume. A host's ephemeral filesystem can lose all data on restart, and SQLite is not a horizontally scalable production database. Follow `docs/OPERATIONS.md` for the synthetic backup and restore procedure. Never commit or upload the database.

## Start the app behind the gateway

Securely inject `LIVING_LITERACY_STAGING_PROXY_SECRET` into both the app and proxy service environments from the host's secret manager or restricted configuration. The values must match. The application checks syntax and length only; it cannot verify that the value is random or high-entropy. Do not print the value or place it in command arguments. Start the app on the **same host**, substituting the actual DNS hostname:

```sh
python3 -m prototype.app_server --db /path/to/private/staging.sqlite3 --port 8765 --private-staging-origin https://staging.example.com
```

The staging origin must be the exact HTTPS origin clients use, without a path, trailing slash or query string. If a non-default port is used it must match both Host and browser Origin exactly. The Python process continues to bind `127.0.0.1`, accepts only loopback gateway connections, requires the gateway secret header on every request, and marks the session cookie Secure. Do not publish port 8765. Do not combine this mode with `--container-demo`. Restart invalidates in-memory CSRF secrets; sessions may need a fresh sign-in.

## Configure the gateway

`Caddyfile.example` is a reviewable starting point, **not a verified deployment**. Supply all variables only through the gateway service's restricted environment:

- `LIVING_LITERACY_STAGING_HOST`: hostname whose HTTPS origin matches the app flag exactly. Use the plain hostname for Caddy's standard HTTPS port.
- `LIVING_LITERACY_ALLOWED_CIDR`: your trusted client network in CIDR form. Never use a wildcard or an unverified forwarded client IP.
- `LIVING_LITERACY_GATEWAY_USER`: an adult staging operator username, separate from the app's synthetic identity.
- `LIVING_LITERACY_GATEWAY_PASSWORD_HASH`: a Caddy-supported password hash generated through Caddy's interactive `hash-password` command. Never commit the password or hash.
- `LIVING_LITERACY_STAGING_PROXY_SECRET`: the same server-held secret used by the app. It must never be included in a client response or access log.

Validate the adapted configuration with the installed Caddy version and confirm its `basic_auth`, trusted-client IP and `header_up` replacement behavior. Add gateway rate-limiting and audit/monitoring controls using a trusted, separately reviewed component. Restrict access at the network perimeter where feasible. Do not use the example to support public visitors, real accounts, or real student records.

## Required verification before sharing a private URL

1. Confirm the service is reachable only through HTTPS and an authenticated, CIDR-restricted gateway; app port 8765 is not reachable externally. Confirm a forged or omitted gateway header and unauthorized client are denied. Confirm Host, Origin, cookie and CSRF behavior end to end.
2. Test both allowed and denied test accounts, cross-family isolation, consent revocation, lesson withdrawal and assistance tracking. Review logs for credentials or student content. Test from an actual browser and record the results.
3. Test backup and restore to a separate location, restart behavior, alerting, and the hosting provider's data retention and access controls. Treat all content as synthetic. Inspect the instance and stop it if controls are missing.
4. Obtain the user's specific approval before exposing real child data or claiming a production launch. The repository's source-publication approval is not approval for real-data processing.

No successful host deployment, endpoint, or external URL is asserted by this guide. A standard Render Web Service cannot be pointed directly at the local loopback app: it requires this separate protected gateway or a reviewed hosting architecture that preserves all of the checks.
